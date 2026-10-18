"""Laporan lintas modul: definisi dataset, filter, dan ekspor (Excel, CSV, PDF).

Dipakai oleh pembuat laporan, ekspor di daftar admin, dan asisten.
"""

import csv
import datetime
import io
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable

from django.db.models import Q
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify

from asetlahan import enums, scope


@dataclass
class Column:
    key: str
    label: str
    getter: Callable


@dataclass
class Dataset:
    key: str
    label: str
    model_path: str
    permission: str
    columns: list[Column]
    search_fields: tuple[str, ...] = ()
    date_field: str = ""
    status_field: str = "status"
    scope_lookup: str = "service_unit"
    select_related: tuple[str, ...] = ()
    module_flag: str = ""
    extra_filters: dict = field(default_factory=dict)

    @property
    def model(self):
        from django.apps import apps

        return apps.get_model(self.model_path)

    def status_choices(self):
        if not self.status_field:
            return []
        try:
            model_field = self.model._meta.get_field(self.status_field)
        except Exception:  # noqa: BLE001
            return []
        return list(model_field.choices or [])

    @property
    def status_label(self) -> str:
        return str(self.model._meta.get_field(self.status_field).verbose_name) if self.status_field else ""

    def allowed(self, user) -> bool:
        if not user.has_perm(self.permission):
            return False
        if self.module_flag:
            from asetlahan.models import ModuleSettings

            return getattr(ModuleSettings.load(), self.module_flag, True)
        return True

    def queryset(self, user):
        queryset = self.model._default_manager.all()
        if self.select_related:
            queryset = queryset.select_related(*self.select_related)
        if self.scope_lookup:
            queryset = scope.scoped(queryset, user, self.scope_lookup)
        return queryset


def _display(attr):
    return lambda obj: getattr(obj, f"get_{attr}_display")()


def _attr(path):
    def getter(obj):
        value = obj
        for part in path.split("."):
            value = getattr(value, part, None)
            if value is None:
                return ""
        return value

    return getter


def _dt(path):
    def getter(obj):
        value = _attr(path)(obj)
        return timezone.localtime(value).strftime("%Y-%m-%d %H:%M") if value else ""

    return getter


C = Column

DATASETS: dict[str, Dataset] = {}


def _register(dataset: Dataset):
    DATASETS[dataset.key] = dataset


_register(Dataset(
    key="aset", label="Aset lahan (bank tanah)", model_path="asetlahan.LandAsset",
    permission="asetlahan.view_landasset", select_related=("category", "service_unit", "municipality"),
    search_fields=("code", "name", "title_number", "village", "district", "registered_owner"),
    date_field="acquisition_date",
    columns=[
        C("code", "Kode", _attr("code")), C("name", "Nama", _attr("name")),
        C("category", "Kategori", _attr("category.name")), C("status", "Status", _display("status")),
        C("area_m2", "Luas (m²)", _attr("area_m2")), C("title_type", "Alas hak", _display("title_type")),
        C("title_number", "Nomor hak", _attr("title_number")), C("title_expiry", "Hak berakhir", _attr("title_expiry")),
        C("registered_owner", "Pemegang hak", _attr("registered_owner")),
        C("village", "Kelurahan/desa", _attr("village")), C("district", "Kecamatan", _attr("district")),
        C("municipality", "Kab/kota", _attr("municipality.name")),
        C("acquisition_date", "Tgl perolehan", _attr("acquisition_date")),
        C("acquisition_cost", "Nilai perolehan", _attr("acquisition_cost")),
        C("njop_per_m2", "NJOP/m²", _attr("njop_per_m2")), C("zoning", "Peruntukan", _attr("zoning")),
        C("service_unit", "Unit layanan", _attr("service_unit.name")),
    ],
))
_register(Dataset(
    key="pajak", label="Pajak & retribusi", model_path="asetlahan.TaxObligation",
    permission="asetlahan.view_taxobligation", select_related=("asset",), scope_lookup="asset__service_unit",
    search_fields=("asset__code", "asset__name", "reference"), date_field="due_date", status_field="tax_type",
    module_flag="enable_valuation",
    columns=[
        C("asset", "Aset", _attr("asset.code")), C("tax_type", "Jenis", _display("tax_type")),
        C("period", "Periode", _attr("period")), C("amount", "Terutang", _attr("amount")),
        C("due_date", "Jatuh tempo", _attr("due_date")), C("paid_date", "Tgl bayar", _attr("paid_date")),
        C("paid_amount", "Dibayar", _attr("paid_amount")), C("reference", "Nomor SPPT", _attr("reference")),
    ],
))
_register(Dataset(
    key="transaksi", label="Transaksi keuangan lahan", model_path="asetlahan.LandTransaction",
    permission="asetlahan.view_landtransaction", select_related=("asset",),
    search_fields=("number", "reference", "counterparty", "description"), date_field="date",
    status_field="transaction_type", module_flag="enable_valuation",
    columns=[
        C("number", "Nomor", _attr("number")), C("date", "Tanggal", _attr("date")),
        C("type", "Jenis", _display("transaction_type")), C("amount", "Jumlah", _attr("amount")),
        C("asset", "Aset", _attr("asset.code")), C("counterparty", "Pihak", _attr("counterparty")),
        C("account_code", "Kode akun", _attr("account_code")), C("reference", "Referensi", _attr("reference")),
        C("description", "Uraian", _attr("description")),
    ],
))
_register(Dataset(
    key="perkara", label="Perkara & litigasi", model_path="asetlahan.LegalCase",
    permission="asetlahan.view_legalcase", search_fields=("number", "court_case_number", "title", "opposing_party"),
    date_field="filed_date", module_flag="enable_litigation",
    columns=[
        C("number", "Nomor", _attr("number")), C("court_case_number", "Nomor perkara", _attr("court_case_number")),
        C("title", "Pokok perkara", _attr("title")), C("case_type", "Jenis", _display("case_type")),
        C("court", "Forum", _display("court")), C("position", "Kedudukan", _display("our_position")),
        C("opposing_party", "Pihak lawan", _attr("opposing_party")), C("status", "Status", _display("status")),
        C("outcome", "Hasil", _display("outcome")), C("filed_date", "Didaftarkan", _attr("filed_date")),
        C("claim_value", "Nilai gugatan", _attr("claim_value")),
    ],
))
_register(Dataset(
    key="sidang", label="Jadwal sidang", model_path="asetlahan.CaseHearing",
    permission="asetlahan.view_casehearing", select_related=("case",), scope_lookup="case__service_unit",
    search_fields=("agenda", "case__number", "case__title"), date_field="scheduled_at", status_field="",
    module_flag="enable_litigation",
    columns=[
        C("scheduled_at", "Jadwal", _dt("scheduled_at")), C("case", "Perkara", _attr("case.number")),
        C("title", "Pokok perkara", _attr("case.title")), C("agenda", "Agenda", _attr("agenda")),
        C("location", "Tempat", _attr("location")), C("result", "Hasil", _attr("result")),
    ],
))
_register(Dataset(
    key="okupasi", label="Okupasi & perambahan", model_path="asetlahan.EncroachmentCase",
    permission="asetlahan.view_encroachmentcase", select_related=("asset",),
    search_fields=("number", "title", "encroacher_name"), date_field="detected_on", module_flag="enable_encroachment",
    columns=[
        C("number", "Nomor", _attr("number")), C("title", "Temuan", _attr("title")),
        C("asset", "Aset", _attr("asset.code")), C("detected_on", "Ditemukan", _attr("detected_on")),
        C("method", "Cara ditemukan", _display("detection_method")),
        C("structure", "Bentuk", _display("structure_type")), C("area", "Luas (m²)", _attr("encroached_area_m2")),
        C("encroacher", "Pihak", _attr("encroacher_name")), C("status", "Status", _display("status")),
        C("resolved_on", "Selesai", _attr("resolved_on")),
    ],
))
_register(Dataset(
    key="survei", label="Survei & pemetaan", model_path="asetlahan.SurveyRequest",
    permission="asetlahan.view_surveyrequest", select_related=("asset", "assigned_to"),
    search_fields=("number", "purpose", "vendor"), date_field="scheduled_date", module_flag="enable_survey",
    columns=[
        C("number", "Nomor", _attr("number")), C("type", "Jenis", _display("survey_type")),
        C("asset", "Aset", _attr("asset.code")), C("status", "Status", _display("status")),
        C("scheduled_date", "Jadwal", _attr("scheduled_date")), C("completed_date", "Selesai", _attr("completed_date")),
        C("vendor", "Penyedia", _attr("vendor")), C("cost", "Biaya", _attr("cost")),
        C("result_area", "Luas hasil ukur", _attr("result_area_m2")),
    ],
))
_register(Dataset(
    key="tugas", label="Tugas & perintah kerja", model_path="asetlahan.Task",
    permission="asetlahan.view_task", select_related=("assignee", "team"),
    search_fields=("number", "title", "description"), date_field="due_date", module_flag="enable_tasks",
    columns=[
        C("number", "Nomor", _attr("number")), C("title", "Judul", _attr("title")),
        C("type", "Jenis", _display("task_type")), C("priority", "Prioritas", _display("priority")),
        C("status", "Status", _display("status")), C("assignee", "Petugas", _attr("assignee")),
        C("team", "Tim", _attr("team.name")), C("start_date", "Mulai", _attr("start_date")),
        C("due_date", "Tenggat", _attr("due_date")), C("progress", "Progres (%)", _attr("progress")),
    ],
))
_register(Dataset(
    key="pengaduan", label="Pengaduan masyarakat", model_path="asetlahan.Grievance",
    permission="asetlahan.view_grievance", select_related=("category",),
    search_fields=("number", "subject", "complainant_name"), date_field="created_at", module_flag="enable_grievance",
    columns=[
        C("number", "Nomor", _attr("number")), C("created_at", "Diterima", _dt("created_at")),
        C("channel", "Saluran", _display("channel")), C("category", "Kategori", _attr("category.name")),
        C("subject", "Perihal", _attr("subject")), C("complainant", "Pelapor", _attr("complainant_name")),
        C("status", "Status", _display("status")), C("due_date", "Batas", _attr("due_date")),
        C("resolved_on", "Selesai", _attr("resolved_on")),
    ],
))
_register(Dataset(
    key="urusan", label="Urusan instansi pemerintah", model_path="asetlahan.LiaisonActivity",
    permission="asetlahan.view_liaisonactivity", select_related=("asset", "facilitator"),
    search_fields=("subject", "agency", "reference_number"), date_field="submitted_on", module_flag="enable_survey",
    columns=[
        C("subject", "Perihal", _attr("subject")), C("agency", "Instansi", _attr("agency")),
        C("status", "Status", _display("status")), C("submitted_on", "Diajukan", _attr("submitted_on")),
        C("next_follow_up", "Tindak lanjut", _attr("next_follow_up")), C("asset", "Aset", _attr("asset.code")),
        C("facilitator", "Fasilitator", _attr("facilitator.name")),
    ],
))
_register(Dataset(
    key="lelang", label="Lelang & seleksi lahan", model_path="asetlahan.Tender",
    permission="asetlahan.view_tender", select_related=("winner",),
    search_fields=("number", "title"), date_field="close_at", module_flag="enable_tender",
    columns=[
        C("number", "Nomor", _attr("number")), C("title", "Judul", _attr("title")),
        C("method", "Metode", _display("method")), C("reserve_price", "Nilai limit", _attr("reserve_price")),
        C("close_at", "Ditutup", _dt("close_at")), C("status", "Status", _display("status")),
        C("winner", "Pemenang", _attr("winner.bidder_name")), C("winning_amount", "Nilai menang", _attr("winner.amount")),
    ],
))
_register(Dataset(
    key="hunian", label="Hunian permukiman kembali", model_path="asetlahan.ResettlementUnit",
    permission="asetlahan.view_resettlementunit", select_related=("site", "household"),
    scope_lookup="site__service_unit", search_fields=("unit_number", "site__name"), date_field="occupied_since",
    module_flag="enable_resettlement",
    columns=[
        C("site", "Kawasan", _attr("site.name")), C("unit", "Unit", _attr("unit_number")),
        C("type", "Tipe", _attr("house_type")), C("area", "Luas (m²)", _attr("area_m2")),
        C("status", "Status", _display("status")), C("household", "Kepala keluarga", _attr("household.head_name")),
        C("occupied_since", "Dihuni sejak", _attr("occupied_since")),
    ],
))
_register(Dataset(
    key="pemangku", label="Pemangku kepentingan", model_path="asetlahan.Stakeholder",
    permission="asetlahan.view_stakeholder", search_fields=("name", "organization"), status_field="stance",
    module_flag="enable_ownership",
    columns=[
        C("name", "Nama", _attr("name")), C("type", "Jenis", _display("stakeholder_type")),
        C("organization", "Organisasi", _attr("organization")), C("position", "Jabatan", _attr("position")),
        C("influence", "Pengaruh", _display("influence")), C("interest", "Kepentingan", _display("interest")),
        C("stance", "Sikap", _display("stance")), C("phone", "Telepon", _attr("phone")),
    ],
))
_register(Dataset(
    key="sewa", label="Kontrak sewa (modul sewa)", model_path="leasing.Lease",
    permission="leasing.view_lease", select_related=("identifier", "municipality", "type"),
    search_fields=("identifier__identifier",), date_field="end_date", status_field="",
    columns=[
        C("identifier", "Nomor sewa", _attr("identifier")), C("type", "Jenis", _attr("type.name")),
        C("municipality", "Kab/kota", _attr("municipality.name")), C("start_date", "Mulai", _attr("start_date")),
        C("end_date", "Berakhir", _attr("end_date")), C("state", "Status", _attr("state")),
    ],
))
_register(Dataset(
    key="pengadaan", label="Bidang pengadaan tanah", model_path="pengadaan.AcquisitionParcel",
    permission="pengadaan.view_acquisitionparcel", select_related=("project",), scope_lookup="",
    search_fields=("parcel_number", "nib", "village", "project__name", "project__identifier"),
    columns=[
        C("project", "Proyek", _attr("project.identifier")), C("project_name", "Nama proyek", _attr("project.name")),
        C("parcel_number", "Nomor bidang", _attr("parcel_number")), C("status", "Status", _display("status")),
        C("right_type", "Alas hak", _display("right_type")), C("measured", "Luas ukur", _attr("measured_area_m2")),
        C("affected", "Luas terkena", _attr("affected_area_m2")), C("village", "Desa", _attr("village")),
        C("disputed", "Sengketa", _attr("is_disputed")),
    ],
))


def available(user) -> list[Dataset]:
    return [d for d in DATASETS.values() if d.allowed(user)]


def dataset(key: str) -> Dataset:
    return DATASETS[key]


def _parse_date(value):
    try:
        return datetime.date.fromisoformat(value) if value else None
    except ValueError:
        return None


def apply_filters(ds: Dataset, queryset, params: dict):
    q = (params.get("q") or "").strip()
    if q and ds.search_fields:
        condition = Q()
        for name in ds.search_fields:
            condition |= Q(**{f"{name}__icontains": q})
        queryset = queryset.filter(condition)
    status = params.get("status")
    if status and ds.status_field:
        queryset = queryset.filter(**{ds.status_field: status})
    if ds.date_field:
        start, end = _parse_date(params.get("dari")), _parse_date(params.get("sampai"))
        is_datetime = ds.model._meta.get_field(ds.date_field).get_internal_type() == "DateTimeField"
        suffix = "__date" if is_datetime else ""
        if start:
            queryset = queryset.filter(**{f"{ds.date_field}{suffix}__gte": start})
        if end:
            queryset = queryset.filter(**{f"{ds.date_field}{suffix}__lte": end})
    unit = params.get("unit")
    if unit and ds.scope_lookup:
        queryset = queryset.filter(**{ds.scope_lookup: unit})
    return queryset


def select_columns(ds: Dataset, keys) -> list[Column]:
    keys = [k for k in (keys or []) if k]
    chosen = [c for c in ds.columns if c.key in keys] if keys else []
    return chosen or ds.columns


def _cell(value):
    if isinstance(value, bool):
        return "Ya" if value else "Tidak"
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return "" if value is None else value if isinstance(value, (int, float)) else str(value)


def rows(columns, queryset, limit=None):
    items = queryset[:limit] if limit else queryset
    for obj in items:
        yield [_cell(c.getter(obj)) for c in columns]


def export_response(ds: Dataset, queryset, fmt: str, columns=None, title: str = ""):
    columns = columns or ds.columns
    title = title or ds.label
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
    filename = f"{slugify(title)}-{stamp}"
    headers = [c.label for c in columns]
    data = list(rows(columns, queryset, limit=50000))
    if fmt == "csv":
        return _csv(filename, headers, data)
    if fmt == "pdf":
        return _pdf(filename, title, headers, data)
    return _xlsx(filename, title, headers, data)


def _csv(filename, headers, data):
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(headers)
    writer.writerows(data)
    response = HttpResponse("﻿" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    return response


def xlsx_bytes(title, headers, data) -> bytes:
    import xlsxwriter

    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {"in_memory": True, "remove_timezone": True})
    sheet = workbook.add_worksheet(title[:31] or "Laporan")
    bold = workbook.add_format({"bold": True, "bg_color": "#DDEBF7", "border": 1})
    for col, header in enumerate(headers):
        sheet.write(0, col, header, bold)
        sheet.set_column(col, col, max(12, min(40, len(header) + 4)))
    for row_index, row in enumerate(data, start=1):
        for col, value in enumerate(row):
            sheet.write(row_index, col, value)
    sheet.freeze_panes(1, 0)
    sheet.autofilter(0, 0, max(len(data), 1), max(len(headers) - 1, 0))
    workbook.close()
    return buffer.getvalue()


def _xlsx(filename, title, headers, data):
    response = HttpResponse(
        xlsx_bytes(title, headers, data),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
    return response


def _pdf(filename, title, headers, data):
    from django.conf import settings
    from xhtml2pdf import pisa

    html = render_to_string(
        "asetlahan/report_pdf.html",
        {"title": title, "headers": headers, "rows": data[:5000], "total": len(data),
         "organization": settings.ORGANIZATION_NAME, "printed_at": timezone.localtime()},
    )
    buffer = io.BytesIO()
    pisa.CreatePDF(html, dest=buffer, encoding="utf-8")
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
    return response


__all__ = ["DATASETS", "available", "dataset", "apply_filters", "select_columns", "rows", "export_response",
           "enums"]
