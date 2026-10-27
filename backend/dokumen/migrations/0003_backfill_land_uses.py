"""Buat pemanfaatan lahan untuk alokasi dan sewa/kerja sama yang sudah ada, lalu
pindahkan laporan perizinan lama (alokasi.PermitReport) ke dokumen perizinan.

Berkas lama tidak disalin: versi 1 menunjuk berkas yang sama di penyimpanan
privat. Laporan yang dulu dilaporkan "terbit" menjadi "menunggu verifikasi"
agar diperiksa petugas.
"""

import datetime
import hashlib
import os

from django.db import migrations
from django.utils import timezone
from sequences import get_next_value

ALLOCATION_STATUS = {
    "aktif": "aktif",
    "dialihkan": "berakhir",
    "berakhir": "berakhir",
    "dicabut": "dicabut",
}
OLD_STATUS = {"belum": "belum", "proses": "proses", "terbit": "diajukan", "tidak_wajib": "tidak_wajib"}
SCHEME_FLAGS = {
    "alokasi": "applies_allocation",
    "sewa": "applies_lease",
    "kerja_sama": "applies_partnership",
    "lainnya": "applies_other",
}


def _number():
    year = timezone.localdate().year
    return f"PML-{year}-{get_next_value(f'dokumen_pml_{year}'):05d}"


def _add_years(date, years):
    try:
        return date.replace(year=date.year + years)
    except ValueError:
        return date.replace(year=date.year + years, day=28)


def _ensure_records(apps, land_use):
    PermitType = apps.get_model("dokumen", "PermitType")
    PermitRecord = apps.get_model("dokumen", "PermitRecord")
    flag = SCHEME_FLAGS.get(land_use.scheme, "applies_other")
    existing = set(PermitRecord.objects.filter(land_use=land_use).values_list("permit_type_id", flat=True))
    for permit_type in PermitType.objects.filter(is_active=True, **{flag: True}):
        sectors = set(permit_type.sectors.values_list("pk", flat=True))
        if sectors and land_use.sector_id not in sectors:
            continue
        if permit_type.pk not in existing:
            PermitRecord.objects.create(land_use=land_use, permit_type=permit_type)


def _digest(storage, name):
    try:
        digest = hashlib.sha256()
        size = 0
        with storage.open(name, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        return digest.hexdigest(), size
    except OSError:
        return "", 0


def backfill_allocations(apps):
    Allocation = apps.get_model("alokasi", "Allocation")
    LandUse = apps.get_model("dokumen", "LandUse")
    Activity = apps.get_model("dokumen", "Activity")
    for allocation in Allocation.objects.select_related("plot", "holder").order_by("pk"):
        if LandUse.objects.filter(allocation=allocation).exists():
            continue
        land_use = LandUse.objects.create(
            number=_number(),
            title=allocation.activity or allocation.plot.name,
            scheme="alokasi",
            status=ALLOCATION_STATUS.get(allocation.status, "aktif"),
            holder=allocation.holder,
            holder_name=allocation.holder.name,
            plot=allocation.plot,
            allocation=allocation,
            sector_id=allocation.plot.sector_id,
            reference=allocation.kpt_number,
            area_m2=allocation.area_m2,
            start_date=allocation.start_date,
            end_date=allocation.end_date,
        )
        Activity.objects.create(
            action="dibuat", land_use=land_use, actor_name="Sistem", detail=f"Dari alokasi {allocation.kpt_number}"
        )
        _ensure_records(apps, land_use)


def backfill_investments(apps):
    InvestmentRequest = apps.get_model("alokasi", "InvestmentRequest")
    LandUse = apps.get_model("dokumen", "LandUse")
    Activity = apps.get_model("dokumen", "Activity")
    completed = InvestmentRequest.objects.filter(
        status="selesai", offer_scheme__in=("sewa", "kerja_sama")
    ).select_related("applicant", "offer_plot")
    for investment in completed.order_by("pk"):
        if LandUse.objects.filter(investment=investment).exists():
            continue
        start = (investment.closed_at or timezone.now()).date()
        end = None
        if investment.offer_term_years:
            end = _add_years(start, investment.offer_term_years) - datetime.timedelta(days=1)
        plot = investment.offer_plot
        land_use = LandUse.objects.create(
            number=_number(),
            title=investment.project_name,
            scheme="sewa" if investment.offer_scheme == "sewa" else "kerja_sama",
            status="aktif" if plot is None or plot.status == "disewa" else "berakhir",
            holder=investment.applicant,
            holder_name=investment.applicant.name,
            plot=plot,
            investment=investment,
            sector_id=investment.sector_id or (plot.sector_id if plot else None),
            reference=investment.contract_number,
            area_m2=investment.offer_area_m2 or investment.requested_area_m2,
            start_date=start,
            end_date=end,
            assigned_to_id=investment.assigned_to_id,
        )
        Activity.objects.create(
            action="dibuat", land_use=land_use, actor_name="Sistem", detail=f"Dari permintaan investasi {investment.number}"
        )
        _ensure_records(apps, land_use)


def move_permit_reports(apps):
    PermitReport = apps.get_model("alokasi", "PermitReport")
    LandUse = apps.get_model("dokumen", "LandUse")
    PermitType = apps.get_model("dokumen", "PermitType")
    PermitRecord = apps.get_model("dokumen", "PermitRecord")
    DocumentVersion = apps.get_model("dokumen", "DocumentVersion")
    Activity = apps.get_model("dokumen", "Activity")
    storage = DocumentVersion._meta.get_field("file").storage
    types = {t.code: t for t in PermitType.objects.all()}
    fallback = types.get("lainnya")
    for report in PermitReport.objects.order_by("pk"):
        land_use = LandUse.objects.filter(allocation_id=report.allocation_id).first()
        permit_type = types.get(report.permit_type) or fallback
        if land_use is None or permit_type is None:
            continue
        record, _created = PermitRecord.objects.get_or_create(land_use=land_use, permit_type=permit_type)
        has_file = bool(report.document and report.document.name)
        status = OLD_STATUS.get(report.status, "belum")
        if status == "diajukan" and not has_file and not report.permit_number:
            status = "proses"
        record.status = status
        record.number = report.permit_number or record.number
        record.issued_date = report.issued_date or record.issued_date
        record.holder_note = report.note or record.holder_note
        if record.status == "tidak_wajib":
            record.review_note = "Dilaporkan tidak wajib oleh pemegang hak (data lama)."
        record.save()
        if has_file and not DocumentVersion.objects.filter(record=record, file=report.document.name).exists():
            digest, size = _digest(storage, report.document.name)
            number = (DocumentVersion.objects.filter(record=record).count() or 0) + 1
            DocumentVersion.objects.create(
                record=record,
                number=number,
                file=report.document.name,
                original_name=os.path.basename(report.document.name)[:255],
                size=size,
                sha256=digest,
                source="migrasi",
                note="Dipindahkan dari laporan perizinan lama.",
                created_at=report.modified_at or timezone.now(),
            )
        Activity.objects.create(
            action="status",
            land_use=land_use,
            record=record,
            actor_name="Sistem",
            detail="Dipindahkan dari laporan perizinan lama.",
        )


def forwards(apps, schema_editor):
    backfill_allocations(apps)
    backfill_investments(apps)
    move_permit_reports(apps)


class Migration(migrations.Migration):
    dependencies = [
        ("dokumen", "0002_seed_defaults"),
        ("alokasi", "0010_seed_investasi"),
        ("sequences", "__latest__"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
