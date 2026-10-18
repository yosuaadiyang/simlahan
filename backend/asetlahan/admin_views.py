"""Halaman alat petugas modul aset lahan di /admin/asetlahan/….

Dasbor, peta tematik (GeoJSON), Gantt, pembuat laporan, analisis tumpang
tindih, pembanding citra, matriks pemangku kepentingan, buku besar gabungan,
pencarian dokumen lintas modul, asisten AI, dan unduhan berkas privat.
"""

import datetime
import functools
import json
from decimal import Decimal

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from alokasi.templatetags.alokasi_tags import angka
from asetlahan import enums, geo, scope
from asetlahan.models import (
    Bid,
    Document,
    EncroachmentCase,
    FieldReport,
    Grievance,
    LandAsset,
    LandTransaction,
    LegalCase,
    ModuleSettings,
    ResettlementSite,
    ResettlementUnit,
    SatelliteImage,
    Stakeholder,
    SurveyRequest,
    Task,
    Tender,
)

# --------------------------------------------------------------------------
# Berkas privat
# --------------------------------------------------------------------------

FILE_KINDS = {
    "dokumen": (Document, "file", "service_unit"),
    "citra": (SatelliteImage, "file", ""),
    "lapangan": (FieldReport, "photo", "service_unit"),
    "penawaran": (Bid, "proposal", "tender__service_unit"),
    "pengaduan": (Grievance, "attachment", "service_unit"),
}


def file_url(kind: str, obj) -> str:
    return reverse("asetlahan-file", args=[kind, obj.pk])


def file_link(kind: str, obj, label: str = "") -> str:
    _model, field, _lookup = FILE_KINDS[kind]
    fieldfile = getattr(obj, field)
    if not fieldfile:
        return "–"
    return format_html(
        '<a href="{}" target="_blank" rel="noopener">{}</a>',
        file_url(kind, obj),
        label or fieldfile.name.rsplit("/", 1)[-1],
    )


@staff_member_required
def officer_file(request, kind, pk):
    from alokasi.views import serve_file

    if kind not in FILE_KINDS:
        raise Http404
    model, field, lookup = FILE_KINDS[kind]
    if not request.user.has_perm(f"asetlahan.view_{model._meta.model_name}"):
        raise PermissionDenied
    queryset = (
        scope.scoped(model.objects.all(), request.user, lookup)
        if lookup
        else model.objects.all()
    )
    obj = get_object_or_404(queryset, pk=pk)
    return serve_file(getattr(obj, field), inline=request.GET.get("lihat") == "1")


# --------------------------------------------------------------------------
# Kerangka halaman alat
# --------------------------------------------------------------------------

TOOLS = (
    (
        "asetlahan-dashboard",
        "Dasbor",
        "Ringkasan lintas modul, grafik, dan peringatan tenggat.",
        "asetlahan.view_landasset",
        "",
    ),
    (
        "asetlahan-map",
        "Peta tematik",
        "Aset per status/kategori, okupasi, bidang pengadaan, lahan alokasi, hunian.",
        "asetlahan.view_landasset",
        "",
    ),
    (
        "asetlahan-gantt",
        "Jadwal (Gantt)",
        "Tugas, ketergantungan, dan tonggak proyek pengadaan.",
        "asetlahan.view_task",
        "enable_tasks",
    ),
    (
        "asetlahan-reports",
        "Pembuat laporan",
        "Pilih data, kolom, dan filter; ekspor Excel, CSV, atau PDF.",
        "asetlahan.view_landasset",
        "",
    ),
    (
        "asetlahan-ledger",
        "Buku besar gabungan",
        "Transaksi aset, ganti kerugian, dan tagihan alokasi.",
        "asetlahan.view_landtransaction",
        "enable_valuation",
    ),
    (
        "asetlahan-overlaps",
        "Tumpang tindih",
        "Aset yang batasnya beririsan satu sama lain atau dengan bidang lain.",
        "asetlahan.view_landasset",
        "",
    ),
    (
        "asetlahan-imagery-compare",
        "Pembanding citra",
        "Geser untuk membandingkan citra sebelum dan sesudah.",
        "asetlahan.view_satelliteimage",
        "enable_encroachment",
    ),
    (
        "asetlahan-stakeholder-matrix",
        "Matriks pemangku kepentingan",
        "Pemetaan pengaruh × kepentingan.",
        "asetlahan.view_stakeholder",
        "enable_ownership",
    ),
    (
        "asetlahan-search",
        "Pencarian",
        "Cari aset, perkara, dokumen (termasuk isi teks), dan data modul lain.",
        "asetlahan.view_landasset",
        "",
    ),
    (
        "asetlahan-assistant",
        "Asisten AI",
        "Tanya data lahan dengan bahasa sehari-hari.",
        "asetlahan.view_landasset",
        "",
    ),
)


def available_tools(user) -> list[dict]:
    config = ModuleSettings.load()
    return [
        {"url": reverse(name), "label": label, "description": description, "name": name}
        for name, label, description, permission, flag in TOOLS
        if user.has_perm(permission) and (not flag or getattr(config, flag))
    ]


def tool_view(permission: str, flag: str = ""):
    def decorator(view):
        @staff_member_required
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.has_perm(permission):
                raise PermissionDenied
            if flag and not getattr(ModuleSettings.load(), flag):
                raise Http404(_("Modul ini sedang dinonaktifkan."))
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def render(request, template: str, title: str, context: dict | None = None):
    full = {
        **admin.site.each_context(request),
        "title": title,
        "tools": available_tools(request.user),
        "current": request.resolver_match.url_name if request.resolver_match else "",
        **(context or {}),
    }
    return TemplateResponse(request, template, full)


def _date(value, default=None):
    try:
        return datetime.date.fromisoformat(value) if value else default
    except ValueError:
        return default


def _choices_label(model, field: str) -> dict:
    return {str(k): str(v) for k, v in model._meta.get_field(field).choices}


def bars(rows, color_map=None, default_color="#0969da") -> list[dict]:
    """Data grafik batang horizontal: [(kunci, label, nilai)] → persen terhadap nilai tertinggi."""
    rows = [r for r in rows if r[2]]
    peak = max((float(r[2]) for r in rows), default=0) or 1
    return [
        {
            "label": label,
            "value": value,
            "pct": round(float(value) * 100 / peak, 1),
            "color": (color_map or {}).get(key, default_color),
        }
        for key, label, value in rows
    ]


def _admin_link(name: str, *args) -> str:
    try:
        return reverse(name, args=args)
    except NoReverseMatch:
        return ""


# --------------------------------------------------------------------------
# Dasbor
# --------------------------------------------------------------------------


def _asset_section(user):
    assets = scope.scoped(LandAsset.objects.all(), user)
    totals = assets.aggregate(
        n=Count("id"), area=Sum("area_m2"), cost=Sum("acquisition_cost")
    )
    labels = _choices_label(LandAsset, "status")
    by_status = (
        assets.values("status")
        .annotate(n=Count("id"), area=Sum("area_m2"))
        .order_by("-n")
    )
    by_category = (
        assets.values("category__name", "category__color")
        .annotate(n=Count("id"))
        .order_by("-n")[:10]
    )
    portfolio = Decimal(0)
    for asset in assets.prefetch_related("valuations"):
        latest = max(
            asset.valuations.all(), key=lambda v: (v.valuation_date, v.pk), default=None
        )
        if latest:
            portfolio += latest.total_value
    return {
        "count": totals["n"],
        "area": totals["area"] or 0,
        "cost": totals["cost"] or 0,
        "portfolio": portfolio,
        "status_bars": bars(
            [
                (r["status"], labels.get(r["status"], r["status"]), r["n"])
                for r in by_status
            ],
            enums.ASSET_STATUS_COLORS,
        ),
        "area_bars": bars(
            [
                (r["status"], labels.get(r["status"], r["status"]), r["area"] or 0)
                for r in by_status
            ],
            enums.ASSET_STATUS_COLORS,
        ),
        "category_bars": bars(
            [
                (
                    r["category__name"],
                    r["category__name"] or _("Tanpa kategori"),
                    r["n"],
                )
                for r in by_category
            ],
            {
                r["category__name"]: r["category__color"] or "#57606a"
                for r in by_category
            },
        ),
    }


def _status_bars(queryset, model, field="status", colors=None):
    labels = _choices_label(model, field)
    rows = queryset.values(field).annotate(n=Count("id")).order_by("-n")
    return bars(
        [(r[field], labels.get(r[field], r[field]), r["n"]) for r in rows], colors
    )


def _legal_section(user):
    cases = scope.scoped(LegalCase.objects.all(), user)
    return {
        "open": cases.filter(status__in=enums.OPEN_CASE_STATUSES).count(),
        "claims": cases.filter(status__in=enums.OPEN_CASE_STATUSES).aggregate(
            s=Sum("claim_value")
        )["s"]
        or 0,
        "bars": _status_bars(cases, LegalCase),
        "outcomes": _status_bars(cases.exclude(outcome=""), LegalCase, "outcome"),
    }


def _encroachment_section(user):
    cases = scope.scoped(EncroachmentCase.objects.all(), user)
    open_cases = cases.filter(status__in=enums.OPEN_ENCROACHMENT_STATUSES)
    return {
        "open": open_cases.count(),
        "area": open_cases.aggregate(s=Sum("encroached_area_m2"))["s"] or 0,
        "resolved_year": cases.filter(
            status=enums.EncroachmentStatus.RESOLVED,
            resolved_on__year=timezone.localdate().year,
        ).count(),
        "bars": _status_bars(cases, EncroachmentCase),
    }


def _finance_section(user):
    year = timezone.localdate().year
    transactions = scope.scoped(LandTransaction.objects.filter(date__year=year), user)
    income = (
        transactions.filter(transaction_type__in=enums.INCOME_TYPES).aggregate(
            s=Sum("amount")
        )["s"]
        or 0
    )
    expense = (
        transactions.exclude(transaction_type__in=enums.INCOME_TYPES).aggregate(
            s=Sum("amount")
        )["s"]
        or 0
    )
    labels = _choices_label(LandTransaction, "transaction_type")
    rows = (
        transactions.values("transaction_type").annotate(s=Sum("amount")).order_by("-s")
    )
    return {
        "year": year,
        "income": income,
        "expense": expense,
        "net": income - expense,
        "bars": bars(
            [
                (r["transaction_type"], labels[r["transaction_type"]], r["s"])
                for r in rows
            ]
        ),
    }


def _task_section(user):
    tasks = scope.scoped(Task.objects.all(), user)
    open_tasks = tasks.filter(status__in=enums.OPEN_TASK_STATUSES)
    return {
        "open": open_tasks.count(),
        "mine": open_tasks.filter(assignee=user).count(),
        "overdue": open_tasks.filter(due_date__lt=timezone.localdate()).count(),
        "bars": _status_bars(tasks, Task),
    }


def _grievance_section(user):
    grievances = scope.scoped(Grievance.objects.all(), user)
    open_items = grievances.filter(status__in=enums.OPEN_GRIEVANCE_STATUSES)
    return {
        "open": open_items.count(),
        "overdue": open_items.filter(due_date__lt=timezone.localdate()).count(),
        "bars": _status_bars(grievances, Grievance),
    }


def _resettlement_section(user):
    units = scope.scoped(ResettlementUnit.objects.all(), user, "site__service_unit")
    return {
        "total": units.count(),
        "bars": _status_bars(units, ResettlementUnit, colors=enums.RESETTLEMENT_COLORS),
    }


def _tender_section(user):
    tenders = scope.scoped(Tender.objects.all(), user)
    return {
        "active": tenders.filter(status=enums.TenderStatus.ANNOUNCED).count(),
        "bars": _status_bars(tenders, Tender),
    }


def _other_modules(user):
    """Ringkasan modul pengadaan tanah, alokasi lahan, dan sewa."""
    result = []
    if user.has_perm("pengadaan.view_acquisitionproject"):
        from pengadaan.models import AcquisitionParcel, AcquisitionProject

        result.append(
            {
                "label": _("Proyek pengadaan tanah aktif"),
                "value": AcquisitionProject.objects.filter(status="active").count(),
            }
        )
        result.append(
            {
                "label": _("Bidang pengadaan bersengketa"),
                "value": AcquisitionParcel.objects.filter(is_disputed=True).count(),
            }
        )
    if user.has_perm("alokasi.view_application"):
        from alokasi.enums import FINAL_STATUSES, AllocationStatus, ApplicationStatus
        from alokasi.models import Allocation, Application

        result.append(
            {
                "label": _("Permohonan alokasi diproses"),
                "value": Application.objects.exclude(status=ApplicationStatus.DRAFT)
                .exclude(status__in=FINAL_STATUSES)
                .count(),
            }
        )
        result.append(
            {
                "label": _("Alokasi lahan aktif"),
                "value": Allocation.objects.filter(
                    status=AllocationStatus.ACTIVE
                ).count(),
            }
        )
    if user.has_perm("leasing.view_lease"):
        from leasing.models import Lease

        today = timezone.localdate()
        result.append(
            {
                "label": _("Kontrak sewa berlaku"),
                "value": scope.scoped(
                    Lease.objects.filter(
                        Q(end_date__isnull=True) | Q(end_date__gte=today)
                    ),
                    user,
                ).count(),
            }
        )
    return result


DASHBOARD_SECTIONS = (
    ("assets", "asetlahan.view_landasset", "", _asset_section),
    ("legal", "asetlahan.view_legalcase", "enable_litigation", _legal_section),
    (
        "encroachment",
        "asetlahan.view_encroachmentcase",
        "enable_encroachment",
        _encroachment_section,
    ),
    ("finance", "asetlahan.view_landtransaction", "enable_valuation", _finance_section),
    ("tasks", "asetlahan.view_task", "enable_tasks", _task_section),
    ("grievances", "asetlahan.view_grievance", "enable_grievance", _grievance_section),
    (
        "resettlement",
        "asetlahan.view_resettlementunit",
        "enable_resettlement",
        _resettlement_section,
    ),
    ("tenders", "asetlahan.view_tender", "enable_tender", _tender_section),
)


@tool_view("asetlahan.view_landasset")
def dashboard(request):
    from asetlahan.monitoring import alerts

    config = ModuleSettings.load()
    sections = {
        key: build(request.user)
        for key, permission, flag, build in DASHBOARD_SECTIONS
        if request.user.has_perm(permission) and (not flag or getattr(config, flag))
    }
    context = {
        "s": sections,
        "alerts": alerts(request.user),
        "others": _other_modules(request.user),
    }
    return render(
        request,
        "admin/asetlahan/dashboard.html",
        _("Dasbor manajemen aset lahan"),
        context,
    )


# --------------------------------------------------------------------------
# Peta tematik
# --------------------------------------------------------------------------

MAX_FEATURES = 5000


def _basemaps() -> list[dict]:
    layers = [
        {
            "name": "OpenStreetMap",
            "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "attribution": "&copy; OpenStreetMap contributors",
            "maxZoom": 19,
        },
        {
            "name": "Citra satelit (Esri)",
            "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            "attribution": "Tiles &copy; Esri",
            "maxZoom": 19,
        },
        {
            "name": "Topografi (OpenTopoMap)",
            "url": "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
            "attribution": "&copy; OpenTopoMap (CC-BY-SA)",
            "maxZoom": 17,
        },
    ]
    try:
        extra = (
            json.loads(settings.MAP_EXTRA_BASEMAPS)
            if settings.MAP_EXTRA_BASEMAPS
            else []
        )
    except json.JSONDecodeError:
        extra = []
    for item in extra if isinstance(extra, list) else []:
        if isinstance(item, dict) and item.get("url") and item.get("name"):
            layers.append(
                {
                    "name": str(item["name"]),
                    "url": str(item["url"]),
                    "attribution": str(item.get("attribution", "")),
                    "maxZoom": (
                        item["maxZoom"] if isinstance(item.get("maxZoom"), int) else 20
                    ),
                }
            )
    return layers


def _overlays(user) -> list[dict]:
    overlays = []
    if settings.MAP_WMS_URL and settings.MAP_WMS_LAYERS:
        overlays.append(
            {
                "name": settings.MAP_WMS_NAME,
                "wms": settings.MAP_WMS_URL,
                "layers": settings.MAP_WMS_LAYERS,
            }
        )
    if user.has_perm("asetlahan.view_satelliteimage"):
        for image in SatelliteImage.objects.exclude(tile_url="", wms_url="")[:30]:
            if image.is_viewable:
                overlays.append(_imagery_layer(image))
    return overlays


def _imagery_layer(image) -> dict:
    if image.tile_url:
        return {
            "name": str(image),
            "url": image.tile_url,
            "attribution": image.provider,
        }
    return {
        "name": str(image),
        "wms": image.wms_url,
        "layers": image.wms_layers,
        "attribution": image.provider,
    }


MAP_LAYERS = (
    ("aset", "Aset lahan", "asetlahan.view_landasset", "", True),
    (
        "okupasi",
        "Okupasi & perambahan",
        "asetlahan.view_encroachmentcase",
        "enable_encroachment",
        True,
    ),
    (
        "pengadaan",
        "Bidang pengadaan tanah",
        "pengadaan.view_acquisitionparcel",
        "",
        False,
    ),
    ("alokasi", "Lahan alokasi", "alokasi.view_landplot", "", False),
    (
        "hunian",
        "Hunian permukiman kembali",
        "asetlahan.view_resettlementunit",
        "enable_resettlement",
        False,
    ),
    (
        "survei",
        "Hasil survei & pengukuran",
        "asetlahan.view_surveyrequest",
        "enable_survey",
        False,
    ),
    ("lapangan", "Laporan lapangan (90 hari)", "asetlahan.view_fieldreport", "", False),
)


def _map_layers(request) -> list[dict]:
    config = ModuleSettings.load()
    query = request.GET.urlencode()
    layers = []
    for key, name, permission, flag, visible in MAP_LAYERS:
        if request.user.has_perm(permission) and (not flag or getattr(config, flag)):
            url = reverse("asetlahan-map-layer", args=[key]) + (
                f"?{query}" if query else ""
            )
            layers.append(
                {
                    "key": key,
                    "name": name,
                    "url": url,
                    "visible": visible or key in request.GET,
                }
            )
    if request.GET.get("permukiman"):
        for layer in layers:
            layer["visible"] = layer["key"] in ("aset", "hunian")
    return layers


@tool_view("asetlahan.view_landasset")
def thematic_map(request):
    status_labels = _choices_label(LandAsset, "status")
    config = {
        "center": [settings.MAP_CENTER_LAT, settings.MAP_CENTER_LNG],
        "zoom": settings.MAP_DEFAULT_ZOOM,
        "basemaps": _basemaps(),
        "overlays": _overlays(request.user),
        "layers": _map_layers(request),
        "legend": [
            {"label": status_labels[k], "color": c}
            for k, c in enums.ASSET_STATUS_COLORS.items()
        ],
    }
    categories = (
        scope.scoped(LandAsset.objects.all(), request.user)
        .values_list("category__id", "category__name")
        .distinct()
    )
    context = {
        "map_config": config,
        "categories": [c for c in categories if c[0]],
        "statuses": enums.AssetStatus.choices,
        "params": request.GET,
    }
    return render(request, "admin/asetlahan/map.html", _("Peta tematik"), context)


def _asset_features(request):
    queryset = scope.scoped(
        LandAsset.objects.exclude(geometry__isnull=True), request.user
    ).select_related("category")
    if request.GET.get("status"):
        queryset = queryset.filter(status=request.GET["status"])
    if request.GET.get("kategori", "").isdigit():
        queryset = queryset.filter(category_id=request.GET["kategori"])
    by_category = request.GET.get("warna") == "kategori"
    for asset in queryset[:MAX_FEATURES]:
        color = (
            (asset.category.color if asset.category_id else "#57606a")
            if by_category
            else asset.status_color
        )
        yield geo.feature(
            asset.geometry,
            {
                "title": f"{asset.code} – {asset.name}",
                "color": color,
                "rows": [
                    [_("Status"), asset.get_status_display()],
                    [_("Kategori"), asset.category.name if asset.category_id else "-"],
                    [_("Luas"), f"{angka(asset.area_m2 or 0, 2)} m²"],
                    [
                        _("Alas hak"),
                        f"{asset.get_title_type_display()} {asset.title_number}".strip(),
                    ],
                ],
                "url": reverse("admin:asetlahan_landasset_change", args=[asset.pk]),
            },
        )


def _encroachment_features(request):
    queryset = scope.scoped(EncroachmentCase.objects.all(), request.user)
    if not request.GET.get("semua_okupasi"):
        queryset = queryset.filter(status__in=enums.OPEN_ENCROACHMENT_STATUSES)
    for case in queryset.exclude(area_geometry__isnull=True, location__isnull=True)[
        :MAX_FEATURES
    ]:
        yield geo.feature(
            case.area_geometry or case.location,
            {
                "title": f"{case.number} {case.title}",
                "color": "#cf222e",
                "rows": [
                    [_("Status"), case.get_status_display()],
                    [_("Ditemukan"), case.detected_on.isoformat()],
                    [_("Luas"), f"{angka(case.encroached_area_m2 or 0, 2)} m²"],
                ],
                "url": reverse(
                    "admin:asetlahan_encroachmentcase_change", args=[case.pk]
                ),
            },
        )


def _pengadaan_features(request):
    from pengadaan.models import AcquisitionParcel

    queryset = AcquisitionParcel.objects.exclude(geometry__isnull=True).select_related(
        "project"
    )
    if request.GET.get("proyek", "").isdigit():
        queryset = queryset.filter(project_id=request.GET["proyek"])
    for parcel in queryset[:MAX_FEATURES]:
        yield geo.feature(
            parcel.geometry,
            {
                "title": f"{parcel.project.identifier} / {parcel.parcel_number}",
                "color": "#bf3989" if parcel.is_disputed else "#8250df",
                "rows": [
                    [_("Proyek"), parcel.project.name],
                    [_("Status"), parcel.get_status_display()],
                    [_("Luas terkena"), f"{angka(parcel.affected_area_m2 or 0, 2)} m²"],
                ],
                "url": _admin_link(
                    "admin:pengadaan_acquisitionparcel_change", parcel.pk
                ),
            },
        )


def _alokasi_features(request):
    from alokasi.models import LandPlot

    colors = {
        "tersedia": "#1a7f37",
        "dipesan": "#d4a72c",
        "dialokasikan": "#8250df",
        "ditutup": "#6e7781",
    }
    for plot in LandPlot.objects.exclude(geometry__isnull=True)[:MAX_FEATURES]:
        yield geo.feature(
            plot.geometry,
            {
                "title": f"{plot.code} – {plot.name}",
                "color": colors.get(plot.status, "#0b4f8a"),
                "rows": [
                    [_("Status"), plot.get_status_display()],
                    [_("Peruntukan"), plot.zoning or "-"],
                ],
                "url": _admin_link("admin:alokasi_landplot_change", plot.pk),
            },
        )


def _resettlement_features(request):
    sites = scope.scoped(ResettlementSite.objects.all(), request.user)
    units = (
        ResettlementUnit.objects.filter(site__in=sites)
        .exclude(geometry__isnull=True)
        .select_related("site", "household")
    )
    if request.GET.get("permukiman", "").isdigit():
        sites = sites.filter(pk=request.GET["permukiman"])
        units = units.filter(site_id=request.GET["permukiman"])
    for site in sites.exclude(geometry__isnull=True):
        yield geo.feature(
            site.geometry,
            {
                "title": site.name,
                "color": "#0969da",
                "outline": True,
                "rows": [],
                "url": reverse(
                    "admin:asetlahan_resettlementsite_change", args=[site.pk]
                ),
            },
        )
    for unit in units[:MAX_FEATURES]:
        yield geo.feature(
            unit.geometry,
            {
                "title": f"{unit.site.name} / {unit.unit_number}",
                "color": enums.RESETTLEMENT_COLORS.get(unit.status, "#57606a"),
                "rows": [
                    [_("Status"), unit.get_status_display()],
                    [
                        _("Kepala keluarga"),
                        unit.household.head_name if unit.household_id else "-",
                    ],
                ],
                "url": reverse(
                    "admin:asetlahan_resettlementunit_change", args=[unit.pk]
                ),
            },
        )


def _survey_features(request):
    queryset = scope.scoped(
        SurveyRequest.objects.exclude(result_geometry__isnull=True), request.user
    )
    for survey in queryset[:MAX_FEATURES]:
        yield geo.feature(
            survey.result_geometry,
            {
                "title": str(survey),
                "color": "#0a3069",
                "outline": True,
                "rows": [
                    [_("Status"), survey.get_status_display()],
                    [_("Luas ukur"), f"{survey.result_area_m2 or 0} m²"],
                ],
                "url": reverse(
                    "admin:asetlahan_surveyrequest_change", args=[survey.pk]
                ),
            },
        )


def _field_features(request):
    since = timezone.now() - datetime.timedelta(days=90)
    queryset = scope.scoped(
        FieldReport.objects.filter(captured_at__gte=since), request.user
    )
    for report in queryset.select_related("reported_by")[:MAX_FEATURES]:
        yield geo.feature(
            report.location,
            {
                "title": str(report),
                "color": "#9a6700",
                "rows": [
                    [_("Petugas"), str(report.reported_by or "-")],
                    [_("Catatan"), report.note[:120]],
                ],
                "url": reverse("admin:asetlahan_fieldreport_change", args=[report.pk]),
            },
        )


LAYER_BUILDERS = {
    "aset": _asset_features,
    "okupasi": _encroachment_features,
    "pengadaan": _pengadaan_features,
    "alokasi": _alokasi_features,
    "hunian": _resettlement_features,
    "survei": _survey_features,
    "lapangan": _field_features,
}


@require_GET
@staff_member_required
def map_layer(request, layer):
    spec = next((item for item in MAP_LAYERS if item[0] == layer), None)
    if spec is None:
        raise Http404
    _key, _name, permission, flag, _visible = spec
    if not request.user.has_perm(permission) or (
        flag and not getattr(ModuleSettings.load(), flag)
    ):
        raise PermissionDenied
    return JsonResponse(geo.collection(LAYER_BUILDERS[layer](request)))


# --------------------------------------------------------------------------
# Gantt
# --------------------------------------------------------------------------


def _bar(start, end, window_start, window_days):
    start = max(start, window_start)
    end = max(end, start)
    left = (start - window_start).days * 100 / window_days
    width = max(((end - start).days + 1) * 100 / window_days, 0.6)
    return round(left, 2), round(min(width, 100 - left), 2)


def _gantt_tasks(request, window_start, window_end):
    tasks = scope.scoped(Task.objects.all(), request.user).select_related(
        "assignee", "team", "depends_on"
    )
    tasks = tasks.filter(
        Q(due_date__gte=window_start) | Q(due_date__isnull=True)
    ).exclude(status=enums.TaskStatus.CANCELLED)
    if request.GET.get("tim", "").isdigit():
        tasks = tasks.filter(team_id=request.GET["tim"])
    if request.GET.get("petugas") == "saya":
        tasks = tasks.filter(assignee=request.user)
    rows = []
    for task in tasks.order_by("start_date", "due_date", "id")[:300]:
        start = task.start_date or timezone.localtime(task.created_at).date()
        end = task.due_date or start
        if start > window_end:
            continue
        left, width = _bar(
            start, end, window_start, (window_end - window_start).days + 1
        )
        rows.append(
            {
                "kind": "task",
                "obj": task,
                "start": start,
                "end": end,
                "left": left,
                "width": width,
                "url": reverse("admin:asetlahan_task_change", args=[task.pk]),
                "overdue": task.is_overdue,
            }
        )
    return rows


def _gantt_milestones(request, window_start, window_end):
    if not request.user.has_perm("pengadaan.view_acquisitionmilestone"):
        return []
    from pengadaan.models import AcquisitionMilestone

    milestones = AcquisitionMilestone.objects.filter(
        planned_date__gte=window_start, planned_date__lte=window_end
    ).select_related("project", "responsible")
    if request.GET.get("proyek", "").isdigit():
        milestones = milestones.filter(project_id=request.GET["proyek"])
    days = (window_end - window_start).days + 1
    return [
        {
            "kind": "milestone",
            "obj": m,
            "start": m.planned_date,
            "end": m.actual_date or m.planned_date,
            "left": round((m.planned_date - window_start).days * 100 / days, 2),
            "done": m.status == "done",
        }
        for m in milestones.order_by("planned_date")[:300]
    ]


@tool_view("asetlahan.view_task", "enable_tasks")
def gantt(request):
    today = timezone.localdate()
    window_start = _date(request.GET.get("dari"), today - datetime.timedelta(days=30))
    window_end = _date(request.GET.get("sampai"), today + datetime.timedelta(days=150))
    if window_end <= window_start:
        window_end = window_start + datetime.timedelta(days=30)
    days = (window_end - window_start).days + 1
    months, cursor = [], window_start.replace(day=1)
    while cursor <= window_end:
        nxt = (cursor + datetime.timedelta(days=32)).replace(day=1)
        left = max((cursor - window_start).days, 0) * 100 / days
        right = min((nxt - window_start).days, days) * 100 / days
        months.append(
            {
                "label": cursor.strftime("%m/%Y"),
                "left": round(left, 2),
                "width": round(right - left, 2),
            }
        )
        cursor = nxt
    from asetlahan.models import Team

    context = {
        "rows": _gantt_tasks(request, window_start, window_end),
        "milestones": _gantt_milestones(request, window_start, window_end),
        "months": months,
        "window_start": window_start,
        "window_end": window_end,
        "today_left": (
            round((today - window_start).days * 100 / days, 2)
            if window_start <= today <= window_end
            else None
        ),
        "teams": scope.scoped(Team.objects.all(), request.user),
        "params": request.GET,
    }
    return render(
        request,
        "admin/asetlahan/gantt.html",
        _("Jadwal tugas & tonggak (Gantt)"),
        context,
    )


# --------------------------------------------------------------------------
# Pembuat laporan
# --------------------------------------------------------------------------


@tool_view("asetlahan.view_landasset")
def report_builder(request):
    from asetlahan import reports

    datasets = reports.available(request.user)
    key = request.GET.get("data") or (datasets[0].key if datasets else "")
    ds = next((d for d in datasets if d.key == key), None)
    context = {"datasets": datasets, "ds": ds, "params": request.GET}
    if ds is not None:
        columns = reports.select_columns(ds, request.GET.getlist("kolom"))
        queryset = reports.apply_filters(ds, ds.queryset(request.user), request.GET)
        fmt = request.GET.get("format")
        if fmt in ("xlsx", "csv", "pdf"):
            return reports.export_response(ds, queryset, fmt, columns)
        context.update(
            {
                "columns": columns,
                "chosen": {c.key for c in columns},
                "total": queryset.count(),
                "preview": list(reports.rows(columns, queryset, limit=100)),
                "units": (
                    request.user.service_units.all()
                    if not scope.sees_all(request.user)
                    else _all_units()
                ),
            }
        )
    return render(
        request, "admin/asetlahan/reports.html", _("Pembuat laporan"), context
    )


def _all_units():
    from leasing.models import ServiceUnit

    return ServiceUnit.objects.all()


# --------------------------------------------------------------------------
# Tumpang tindih
# --------------------------------------------------------------------------


@tool_view("asetlahan.view_landasset")
def overlaps(request):
    assets = scope.scoped(LandAsset.objects.all(), request.user)
    pairs = geo.asset_overlaps(assets)
    external = []
    for asset in assets.exclude(geometry__isnull=True)[:300]:
        found = geo.external_overlaps(asset)
        if found["parcels"] or found["plots"]:
            external.append({"asset": asset, **found})
    context = {"pairs": pairs, "external": external}
    return render(
        request, "admin/asetlahan/overlaps.html", _("Analisis tumpang tindih"), context
    )


# --------------------------------------------------------------------------
# Pembanding citra
# --------------------------------------------------------------------------


@tool_view("asetlahan.view_satelliteimage", "enable_encroachment")
def imagery_compare(request):
    images = [i for i in SatelliteImage.objects.all() if i.is_viewable]
    by_id = {str(i.pk): i for i in images}
    case = None
    left = by_id.get(request.GET.get("kiri", ""))
    right = by_id.get(request.GET.get("kanan", ""))
    if request.GET.get("okupasi", "").isdigit():
        case = get_object_or_404(
            scope.scoped(EncroachmentCase.objects.all(), request.user),
            pk=request.GET["okupasi"],
        )
        left = left or (
            case.before_image
            if case.before_image and case.before_image.is_viewable
            else None
        )
        right = right or (
            case.after_image
            if case.after_image and case.after_image.is_viewable
            else None
        )
    focus = None
    if case is not None:
        focus = geo.collection(
            [
                geo.feature(case.area_geometry or case.location, {"title": str(case)}),
                geo.feature(
                    case.asset.geometry if case.asset_id else None,
                    {"title": str(case.asset)},
                ),
            ]
        )
    config = {
        "center": [settings.MAP_CENTER_LAT, settings.MAP_CENTER_LNG],
        "zoom": settings.MAP_DEFAULT_ZOOM,
        "left": _imagery_layer(left) if left else _basemaps()[1],
        "right": _imagery_layer(right) if right else _basemaps()[0],
        "focus": focus,
    }
    context = {
        "images": images,
        "left": left,
        "right": right,
        "case": case,
        "map_config": config,
    }
    return render(
        request,
        "admin/asetlahan/imagery_compare.html",
        _("Pembanding citra sebelum / sesudah"),
        context,
    )


# --------------------------------------------------------------------------
# Matriks pemangku kepentingan
# --------------------------------------------------------------------------

STANCE_COLORS = {
    enums.Stance.SUPPORT: "#1a7f37",
    enums.Stance.NEUTRAL: "#57606a",
    enums.Stance.OPPOSE: "#cf222e",
    enums.Stance.UNKNOWN: "#9a6700",
}


@tool_view("asetlahan.view_stakeholder", "enable_ownership")
def stakeholder_matrix(request):
    queryset = scope.scoped(Stakeholder.objects.all(), request.user)
    if request.GET.get("aset", "").isdigit():
        queryset = queryset.filter(assets__id=request.GET["aset"])
    if request.GET.get("proyek", "").isdigit():
        queryset = queryset.filter(pengadaan_project_id=request.GET["proyek"])
    levels = [enums.Level.HIGH, enums.Level.MEDIUM, enums.Level.LOW]
    grid = {(i, j): [] for i in levels for j in levels}
    for person in queryset.distinct():
        grid[(person.influence, person.interest)].append(
            {
                "obj": person,
                "color": STANCE_COLORS.get(person.stance, "#57606a"),
                "url": reverse("admin:asetlahan_stakeholder_change", args=[person.pk]),
            }
        )
    advice = {
        (enums.Level.HIGH, enums.Level.HIGH): _("Kelola erat"),
        (enums.Level.HIGH, enums.Level.LOW): _("Jaga kepuasan"),
        (enums.Level.LOW, enums.Level.HIGH): _("Informasikan rutin"),
        (enums.Level.LOW, enums.Level.LOW): _("Pantau"),
    }
    rows = [
        {
            "influence": enums.Level(i).label,
            "cells": [
                {"people": grid[(i, j)], "advice": advice.get((i, j), "")}
                for j in reversed(levels)
            ],
        }
        for i in levels
    ]
    context = {
        "rows": rows,
        "interest_labels": [enums.Level(j).label for j in reversed(levels)],
        "stances": [(enums.Stance(k).label, c) for k, c in STANCE_COLORS.items()],
        "total": queryset.count(),
    }
    return render(
        request,
        "admin/asetlahan/stakeholder_matrix.html",
        _("Matriks pengaruh × kepentingan"),
        context,
    )


# --------------------------------------------------------------------------
# Buku besar gabungan
# --------------------------------------------------------------------------


@tool_view("asetlahan.view_landtransaction", "enable_valuation")
def ledger_view(request):
    from asetlahan import finance

    year = timezone.localdate().year
    start = _date(request.GET.get("dari"), datetime.date(year, 1, 1))
    end = _date(request.GET.get("sampai"), datetime.date(year, 12, 31))
    data = finance.ledger(request.user, start, end)
    fmt = request.GET.get("format")
    if fmt in ("xlsx", "csv"):
        return finance.erp_export(
            finance.ledger_rows(data["entries"]),
            fmt,
            finance.LEDGER_HEADERS,
            "Buku besar lahan",
        )
    context = {
        **data,
        "start": start,
        "end": end,
        "entries": data["entries"][:1000],
        "truncated": len(data["entries"]) > 1000,
    }
    return render(
        request, "admin/asetlahan/ledger.html", _("Buku besar keuangan lahan"), context
    )


# --------------------------------------------------------------------------
# Pencarian lintas modul
# --------------------------------------------------------------------------

SEARCH_TARGETS = (
    (
        "Aset lahan",
        "asetlahan.LandAsset",
        (
            "code",
            "name",
            "title_number",
            "nib",
            "registered_owner",
            "village",
            "address",
            "note",
        ),
        "service_unit",
        "admin:asetlahan_landasset_change",
    ),
    (
        "Dokumen",
        "asetlahan.Document",
        ("title", "number", "extracted_text", "note"),
        "service_unit",
        "admin:asetlahan_document_change",
    ),
    (
        "Perkara",
        "asetlahan.LegalCase",
        ("number", "court_case_number", "title", "opposing_party", "decision_summary"),
        "service_unit",
        "admin:asetlahan_legalcase_change",
    ),
    (
        "Okupasi",
        "asetlahan.EncroachmentCase",
        ("number", "title", "encroacher_name", "description"),
        "service_unit",
        "admin:asetlahan_encroachmentcase_change",
    ),
    (
        "Pengaduan",
        "asetlahan.Grievance",
        ("number", "subject", "complainant_name", "description"),
        "service_unit",
        "admin:asetlahan_grievance_change",
    ),
    (
        "Tugas",
        "asetlahan.Task",
        ("number", "title", "description"),
        "service_unit",
        "admin:asetlahan_task_change",
    ),
    (
        "Pemangku kepentingan",
        "asetlahan.Stakeholder",
        ("name", "organization", "note"),
        "service_unit",
        "admin:asetlahan_stakeholder_change",
    ),
    (
        "Lelang",
        "asetlahan.Tender",
        ("number", "title", "description"),
        "service_unit",
        "admin:asetlahan_tender_change",
    ),
    (
        "Urusan instansi",
        "asetlahan.LiaisonActivity",
        ("subject", "agency", "reference_number", "outcome"),
        "service_unit",
        "admin:asetlahan_liaisonactivity_change",
    ),
    (
        "Proyek pengadaan",
        "pengadaan.AcquisitionProject",
        ("identifier", "name", "requiring_agency", "location_description"),
        "",
        "admin:pengadaan_acquisitionproject_change",
    ),
    (
        "Bidang pengadaan",
        "pengadaan.AcquisitionParcel",
        ("parcel_number", "nib", "village", "certificate_number"),
        "",
        "admin:pengadaan_acquisitionparcel_change",
    ),
    (
        "Dokumen pengadaan",
        "pengadaan.AcquisitionDocument",
        ("title", "number"),
        "",
        "admin:pengadaan_acquisitiondocument_change",
    ),
    (
        "Permohonan alokasi",
        "alokasi.Application",
        ("number", "activity", "applicant__name"),
        "",
        "admin:alokasi_application_change",
    ),
    (
        "Lahan alokasi",
        "alokasi.LandPlot",
        ("code", "name", "village", "zoning"),
        "",
        "admin:alokasi_landplot_change",
    ),
    (
        "Kontrak sewa",
        "leasing.Lease",
        ("identifier__identifier",),
        "service_unit",
        "admin:leasing_lease_change",
    ),
)


def search_all(user, query: str, limit: int = 20) -> list[dict]:
    from django.apps import apps

    groups = []
    for label, model_path, fields, lookup, url_name in SEARCH_TARGETS:
        model = apps.get_model(model_path)
        if not user.has_perm(f"{model._meta.app_label}.view_{model._meta.model_name}"):
            continue
        condition = Q()
        for name in fields:
            condition |= Q(**{f"{name}__icontains": query})
        queryset = model._default_manager.filter(condition)
        if lookup:
            queryset = scope.scoped(queryset, user, lookup)
        items = list(queryset.distinct()[: limit + 1])
        if items:
            groups.append(
                {
                    "label": label,
                    "more": len(items) > limit,
                    "items": [
                        {
                            "text": str(o),
                            "url": _admin_link(url_name, o.pk),
                            "snippet": _snippet(o, query),
                        }
                        for o in items[:limit]
                    ],
                }
            )
    return groups


def _snippet(obj, query: str) -> str:
    text = getattr(obj, "extracted_text", "") or ""
    position = text.lower().find(query.lower())
    if position < 0:
        return ""
    start = max(position - 80, 0)
    return (
        ("…" if start else "")
        + text[start : position + len(query) + 120].replace("\n", " ")
        + "…"
    )


@tool_view("asetlahan.view_landasset")
def search(request):
    query = (request.GET.get("q") or "").strip()
    groups = search_all(request.user, query) if len(query) >= 2 else []
    context = {"q": query, "groups": groups, "searched": len(query) >= 2}
    return render(
        request, "admin/asetlahan/search.html", _("Pencarian lintas modul"), context
    )


# --------------------------------------------------------------------------
# Asisten AI
# --------------------------------------------------------------------------

SESSION_KEY = "asetlahan_asisten"


@tool_view("asetlahan.view_landasset")
def assistant(request):
    from asetlahan import ai
    from asetlahan import assistant as engine

    history = request.session.get(SESSION_KEY, [])
    if request.method == "POST":
        if request.POST.get("reset"):
            request.session[SESSION_KEY] = []
            return HttpResponseRedirect(reverse("asetlahan-assistant"))
        question = (request.POST.get("q") or "").strip()[:2000]
        if question:
            result = engine.answer(request.user, question, history)
            if result.get("error"):
                messages.warning(request, result["error"])
            history = (history + [{"q": question, **result}])[-10:]
            request.session[SESSION_KEY] = history
        return HttpResponseRedirect(reverse("asetlahan-assistant"))
    context = {
        "history": history,
        "ai_enabled": ai.enabled(),
        "examples": engine.EXAMPLES,
    }
    return render(request, "admin/asetlahan/assistant.html", _("Asisten AI"), context)
