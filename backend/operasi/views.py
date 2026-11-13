"""Pusat komando di /komando/: halaman peta (PWA) dan API JSON-nya.

Semua API memakai sesi petugas (panel /admin/) dan token CSRF. Laporan yang
direkam luring (kegiatan, uji tanah, SOS) membawa ``client_id`` sehingga
pengiriman ulang dari antrean perangkat tidak membuat data ganda.
"""

import datetime
import functools
import json
import uuid
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from alokasi.templatetags.alokasi_tags import angka
from asetlahan import enums as aset_enums
from asetlahan import scope as aset_scope
from asetlahan.field_views import _parse_captured_at, _parse_location
from asetlahan.geo import collection, feature
from operasi import (
    approvals,
    daily_reports,
    dashboard,
    enums,
    geo,
    patrol,
    reports,
    satellite,
    services,
    spatial,
    task_flow,
)
from operasi.auth_views import command_login_required, forbidden, main_app_url
from operasi.models import (
    MAX_LAND_AREA_M2,
    RELEASED_PARCEL_STATUSES,
    Activity,
    ActivityPhoto,
    AreaAnalysis,
    Attendance,
    ChatMessage,
    CommandSettings,
    DailyReportAttachment,
    GeotechPhoto,
    IllegalFinding,
    Korwil,
    OfficerPosition,
    PatrolPhoto,
    PatrolSession,
    Resident,
    SitePhoto360,
    SoilTest,
    SosAlert,
    StanceChange,
    SystemLock,
    TaskEvent,
    Ticket,
)
from utils.pwa import shell_version

APP_VERSION = "1.0.0"
# Versi dasar; sidik isi SHELL_STATIC ditambahkan otomatis (utils.pwa).
SW_VERSION = "4"
SHELL_STATIC = (
    "operasi/komando.js",
    "operasi/komando.css",
    "operasi/komando-icon.svg",
    "simlahan/tokens.css",
    "simlahan/fonts/inter-latin-wght-normal.woff2",
    "alokasi/vendor/leaflet/leaflet.js",
    "alokasi/vendor/leaflet/leaflet.css",
)
MAX_FEATURES = 5000
MAX_PHOTOS = 5
MAX_STANCE_UPDATES = 50


def _choices(choices) -> list[dict]:
    return [{"value": str(value), "label": str(label)} for value, label in choices]


def _name(user) -> str:
    if user is None:
        return _("Sistem")
    return user.get_full_name() or user.get_username()


def _local(moment) -> str:
    return timezone.localtime(moment).isoformat() if moment else ""


def _decimal_or_none(value, low=None, high=None, places=2):
    """Angka desimal dari isian formulir, dibulatkan ke ``places`` digit (Decimal, bukan float)."""
    if value in (None, ""):
        return None
    try:
        number = Decimal(str(value).replace(",", ".").strip())
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    if (low is not None and number < low) or (high is not None and number > high):
        return None
    return number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _accuracy(value):
    return _decimal_or_none(value, 0, 9_999_999, places=1)


def _int_or_none(value, low=0, high=10_000_000):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def _uuid(value):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _errors(error: ValidationError) -> dict:
    if hasattr(error, "error_dict"):
        return {k: [str(m) for m in v] for k, v in error.message_dict.items()}
    return {"__all__": [str(m) for m in error.messages]}


def _throttled(key: str, limit: int, seconds: int) -> bool:
    # Atomik di basis data (utils.ratelimit); incr DatabaseCache adalah get+set.
    from utils import ratelimit

    return ratelimit.throttled(key, limit, seconds)


# --------------------------------------------------------------------------
# Dekorator
# --------------------------------------------------------------------------


def api(permission: str | None = "operasi.view_korwil", methods=("GET",)):
    """JSON API petugas: sesi wajib, izin dicek, galat dikembalikan sebagai JSON."""

    def decorator(view):
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method not in methods:
                return JsonResponse({"error": _("Metode tidak diizinkan.")}, status=405)
            user = request.user
            if not user.is_authenticated or not user.is_staff:
                return JsonResponse(
                    {"error": _("Sesi berakhir. Silakan masuk kembali.")}, status=401
                )
            if not user.has_perm("operasi.view_korwil") or (
                permission and not user.has_perm(permission)
            ):
                return JsonResponse(
                    {"error": _("Anda tidak berhak melakukan ini.")}, status=403
                )
            try:
                response = view(request, *args, **kwargs)
            except ValidationError as error:
                response = JsonResponse({"errors": _errors(error)}, status=400)
            except PermissionDenied:
                response = JsonResponse(
                    {"error": _("Anda tidak berhak melakukan ini.")}, status=403
                )
            except Http404:
                response = JsonResponse(
                    {"error": _("Data tidak ditemukan.")}, status=404
                )
            response["Cache-Control"] = "private, no-store"
            return response

        return wrapper

    return decorator


# --------------------------------------------------------------------------
# Halaman pusat komando & PWA
# --------------------------------------------------------------------------


def _basemaps():
    from asetlahan.admin_views import _basemaps as aset_basemaps

    return aset_basemaps()


def _extra_layers(request) -> list[dict]:
    """Lapisan modul lain (aset, okupasi, bidang pengadaan, referensi RTRW, dst.)."""
    from asetlahan.admin_views import _map_layers

    if not request.user.has_perm(
        "asetlahan.view_landasset"
    ) and not request.user.has_perm("pengadaan.view_acquisitionparcel"):
        return []
    from asetlahan.models import MapOverlay

    # Lapisan "Tampil di pusat komando" sudah ada di daftar lapisan komando.
    shared = {
        f"ref-{pk}"
        for pk in MapOverlay.objects.filter(show_in_command=True).values_list(
            "pk", flat=True
        )
    }
    layers = [layer for layer in _map_layers(request) if layer["key"] not in shared]
    for layer in layers:
        layer["visible"] = False
    return layers


def _config(request) -> dict:
    data = _base_config(request)
    extra = _spatial_config(request.user)
    for key in ("perms", "urls", "choices", "colors"):
        data[key].update(extra.pop(key))
    data.update(extra)
    return data


def _spatial_config(user) -> dict:
    from operasi import views_spatial, views_tools

    data = views_spatial.config(user)
    extra = views_tools.config(user)
    for key in ("perms", "urls", "choices", "colors"):
        data[key].update(extra.pop(key))
    data.update(extra)
    return data


def _base_config(request) -> dict:
    user = request.user
    config = CommandSettings.load()
    lock = SystemLock.state()
    korwils = services.visible_korwils(user)
    perms = {
        "warga": user.has_perm("operasi.view_resident"),
        "tambahWarga": user.has_perm("operasi.add_resident"),
        "ubahWarga": user.has_perm("operasi.change_resident"),
        "kegiatan": user.has_perm("operasi.view_activity"),
        "lapor": user.has_perm("operasi.add_activity"),
        "verifikasi": user.has_perm("operasi.change_activity"),
        "temuan": user.has_perm("operasi.view_illegalfinding"),
        "tambahTemuan": user.has_perm("operasi.add_illegalfinding"),
        "patroli": user.has_perm("operasi.view_patrolsession"),
        "tanah": user.has_perm("operasi.view_soiltest"),
        "tambahTanah": user.has_perm("operasi.add_soiltest"),
        "absen": user.has_perm("operasi.add_attendance"),
        "chat": user.has_perm("operasi.view_chatmessage"),
        "kirimChat": user.has_perm("operasi.add_chatmessage"),
        "sos": user.has_perm("operasi.add_sosalert"),
        "lihatSos": user.has_perm("operasi.view_sosalert"),
        "tanganiSos": user.has_perm("operasi.change_sosalert"),
        "live": user.has_perm("operasi.add_officerposition"),
        "lihatPetugas": user.has_perm("operasi.view_officerposition"),
        "aiSatelit": user.has_perm("operasi.add_areaanalysis"),
        "tugas": user.has_perm("asetlahan.view_task"),
        "ubahTugas": user.has_perm("asetlahan.change_task"),
        "buatTugas": user.has_perm("asetlahan.add_task"),
        "laporanHarian": user.has_perm("operasi.view_dailyreport"),
        "kirimLaporan": user.has_perm("operasi.add_dailyreport"),
        "rekap": user.has_perm("operasi.view_activity"),
        "tim": services.team_users(user).exclude(pk=user.pk).exists(),
        "historis": dashboard.can_view_history(user),
        "setujuiIzin": services.leave_deciders_q(user) is not None,
        "kunci": user.is_superuser,
        "admin": user.has_perm("operasi.change_korwil"),
    }
    tab = request.GET.get("tab", "")
    return {
        "appName": settings.APP_NAME,
        "version": APP_VERSION,
        "center": [settings.MAP_CENTER_LAT, settings.MAP_CENTER_LNG],
        "zoom": settings.MAP_DEFAULT_ZOOM,
        "basemaps": _basemaps(),
        "extraLayers": _extra_layers(request),
        "initialTab": (
            tab
            if tab
            in (
                "peta",
                "absen",
                "korwil",
                "perf",
                "tasks",
                "warga",
                "chat",
                "laporan",
                "persetujuan",
                "beranda",
                "historis",
                "peringkat",
                "spasial",
                "alat",
                "ujiplts",
            )
            else "peta"
        ),
        "user": {"id": user.pk, "name": _name(user)},
        "perms": perms,
        "korwils": [
            {"id": k.pk, "code": k.code, "name": k.name, "color": k.color}
            for k in korwils
        ],
        "myKorwils": list(geo.user_korwils(user).values_list("pk", flat=True)),
        "choices": {
            "stance": _choices(enums.Stance.choices),
            "land": _choices(enums.LandStatus.choices),
            "rtrw": _choices(enums.RtrwStatus.choices),
            "zone": _choices(enums.RtrwZone.choices),
            "relocation": _choices(enums.RelocationChoice.choices),
            "gender": _choices(enums.Gender.choices),
            "cultivation": _choices(enums.CultivationStatus.choices),
            "activityType": _choices(enums.ActivityType.choices),
            "fieldTypes": [str(t) for t in enums.FIELD_ACTIVITY_TYPES],
            "residency": _choices(enums.ResidencyStatus.choices),
            "impactScope": _choices(enums.ImpactScope.choices),
            "impactRisk": _choices(enums.ImpactRisk.choices),
            "impactResult": _choices(enums.ImpactResult.choices),
            "impactTier": _choices(enums.ImpactTier.choices),
            "illegalKind": _choices(enums.IllegalActivityKind.choices),
            "permit": _choices(enums.PermitStatus.choices),
            "business": _choices(enums.BusinessActivity.choices),
            "patrolRoute": _choices(enums.PatrolRoute.choices),
            "patrolInput": _choices(enums.PatrolInput.choices),
            "situation": _choices(enums.PatrolSituation.choices),
            "personnel": _choices(enums.PersonnelCondition.choices),
            "materiel": _choices(enums.MaterielCondition.choices),
            "weather": _choices(enums.Weather.choices),
            "findingCategory": _choices(enums.FindingCategory.choices),
            "seedling": _choices(enums.SeedlingKind.choices),
            "texture": _choices(enums.SoilTexture.choices),
            "suitability": _choices(enums.SoilSuitability.choices),
            "leave": _choices(
                [
                    c
                    for c in enums.AttendanceStatus.choices
                    if c[0] in enums.ABSENCE_STATUSES
                ]
            ),
            "taskStatus": _choices(aset_enums.TaskStatus.choices),
            "priority": _choices(aset_enums.Priority.choices),
        },
        "colors": {
            "stance": {str(k): v for k, v in enums.STANCE_COLORS.items()},
            "land": {str(k): v for k, v in enums.LAND_STATUS_COLORS.items()},
            "rtrw": {str(k): v for k, v in enums.RTRW_COLORS.items()},
            "activity": {str(k): v for k, v in enums.ACTIVITY_COLORS.items()},
            "soil": {str(k): v for k, v in enums.SOIL_COLORS.items()},
            "illegal": {str(k): v for k, v in enums.ILLEGAL_COLORS.items()},
        },
        "impactPoints": {str(k): v for k, v in enums.IMPACT_POINTS.items()},
        "settings": {
            "requirePhoto": config.require_attendance_photo,
            "workStart": config.work_start.strftime("%H:%M"),
            "workEnd": config.work_end.strftime("%H:%M"),
            "onlineMinutes": config.online_minutes,
        },
        "lock": {**lock, "canDefuse": user.is_superuser},
        "urls": {
            "summary": reverse("operasi-summary"),
            "layer": reverse("operasi-layer", args=["__key__"]),
            "search": reverse("operasi-search"),
            "attendance": reverse("operasi-attendance"),
            "leaveRequests": reverse("operasi-leave-requests"),
            "leaveDecision": reverse("operasi-leave-decision", args=[0]),
            "activities": reverse("operasi-activities"),
            "verify": reverse("operasi-activity-verify", args=[0]),
            "impactConfirm": reverse("operasi-activity-impact", args=[0]),
            "illegalFindings": reverse("operasi-illegal-findings"),
            "patrolPreview": reverse("operasi-patrol-preview"),
            "soil": reverse("operasi-soil"),
            "residents": reverse("operasi-residents"),
            "resident": reverse("operasi-resident", args=[0]),
            "tasks": reverse("operasi-tasks"),
            "task": reverse("operasi-task", args=[0]),
            "taskAssignees": reverse("operasi-task-assignees"),
            "dailyReports": reverse("operasi-daily-reports"),
            "dailyReportCompose": reverse("operasi-daily-report-compose"),
            "dailyReportFinish": reverse("operasi-daily-report-finish"),
            "dailyReportTrace": reverse("operasi-daily-report-trace"),
            "dailyReport": reverse("operasi-daily-report", args=[0]),
            "dailyReportAction": reverse(
                "operasi-daily-report-action", args=[0, "__aksi__"]
            ),
            "approvals": reverse("operasi-approvals"),
            "badges": reverse("operasi-badges"),
            "recap": reverse("operasi-recap"),
            "home": reverse("operasi-home"),
            "korwilDetail": reverse("operasi-korwil-detail", args=[0]),
            "history": reverse("operasi-history"),
            "performance": reverse("operasi-performance"),
            "performanceInsight": reverse("operasi-performance-insight"),
            "leaderboard": reverse("operasi-leaderboard"),
            "leaderboardExcel": reverse("operasi-leaderboard-excel"),
            "leaderboardInsight": reverse("operasi-leaderboard-insight"),
            "structure": reverse("operasi-structure"),
            "feed": reverse("operasi-feed"),
            "aiChat": reverse("operasi-ai-chat"),
            "activityVoice": reverse("operasi-file", args=["kegiatan-suara", 0]),
            "chat": reverse("operasi-chat"),
            "sos": reverse("operasi-sos"),
            "sosAction": reverse("operasi-sos-action", args=[0, "__aksi__"]),
            "position": reverse("operasi-position"),
            "satellite": reverse("operasi-satellite"),
            "lock": reverse("operasi-lock"),
            "serviceWorker": reverse("operasi-sw"),
            "scope": reverse("operasi-command"),
            "admin": reverse("admin:index"),
            "adminKorwil": reverse("admin:app_list", args=["operasi"]),
            "main": main_app_url(user),
            "login": reverse("operasi-login") + "?next=" + reverse("operasi-command"),
            "logout": reverse("operasi-logout"),
        },
    }


@never_cache
@command_login_required
def command_center(request):
    if not request.user.has_perm("operasi.view_korwil"):
        return forbidden(request)
    return render(request, "operasi/komando.html", {"komando_config": _config(request)})


@require_GET
def manifest(request):
    start = reverse("operasi-command")
    shortcut = [
        ("Absen", _("Absen masuk / pulang cepat"), "absen"),
        ("Lapor Kegiatan", _("Input kegiatan baru"), "korwil"),
        ("Kinerja", _("Lihat kinerja (KPI) Anda"), "perf"),
        ("Tugas", _("Lihat daftar tugas Anda"), "tasks"),
    ]
    data = {
        "name": _("%(app)s Pusat Komando") % {"app": settings.APP_NAME},
        "short_name": _("Komando"),
        "description": _(
            "Pusat komando operasi lapangan: peta, absen, kegiatan, kinerja, tugas, chat, SOS."
        ),
        "start_url": start,
        "scope": start,
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#f7faff",
        "theme_color": "#1d82f5",
        "lang": "id",
        "categories": ["business", "productivity", "utilities"],
        "icons": [
            {
                "src": static("operasi/komando-icon.svg"),
                "sizes": "any",
                "type": "image/svg+xml",
                "purpose": "any maskable",
            },
            {
                "src": static("operasi/komando-icon-192.png"),
                "sizes": "192x192",
                "type": "image/png",
            },
            {
                "src": static("operasi/komando-icon-512.png"),
                "sizes": "512x512",
                "type": "image/png",
            },
        ],
        "shortcuts": [
            {
                "name": name,
                "short_name": name,
                "description": description,
                "url": f"{start}?tab={tab}",
            }
            for name, description, tab in shortcut
        ],
    }
    return HttpResponse(json.dumps(data), content_type="application/manifest+json")


@require_GET
def service_worker(request):
    shell = [
        reverse("operasi-command"),
        reverse("operasi-manifest"),
    ] + [static(path) for path in SHELL_STATIC]
    body = render(
        request,
        "operasi/komando_sw.js",
        {
            "shell": json.dumps(shell),
            "layer_prefix": json.dumps(reverse("operasi-layer", args=["x"])[:-2]),
            "version": json.dumps(shell_version(SW_VERSION, *SHELL_STATIC)),
        },
        content_type="application/javascript",
    ).content
    response = HttpResponse(body, content_type="application/javascript; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    return response


# --------------------------------------------------------------------------
# Berkas privat (foto kegiatan, absen, uji tanah, citra AI)
# --------------------------------------------------------------------------

FILE_KINDS = {
    "kegiatan": (ActivityPhoto, "photo", "operasi.view_activity", "activity__korwil"),
    "kegiatan-suara": (Activity, "voice_note", "operasi.view_activity", "korwil"),
    "tanah-foto": (SoilTest, "photo", "operasi.view_soiltest", "korwil"),
    "tanah-lab": (SoilTest, "lab_report", "operasi.view_soiltest", "korwil"),
    "absen-masuk": (Attendance, "check_in_photo", "operasi.view_attendance", ""),
    "absen-pulang": (Attendance, "check_out_photo", "operasi.view_attendance", ""),
    "absen-lampiran": (Attendance, "attachment", "operasi.view_attendance", ""),
    "citra": (AreaAnalysis, "image", "operasi.view_areaanalysis", ""),
    "patroli-foto": (
        PatrolPhoto,
        "photo",
        "operasi.view_patrolsession",
        "observation__session__korwil",
    ),
    "tugas-foto": (TaskEvent, "photo", "asetlahan.view_task", ""),
    "laporan-lampiran": (
        DailyReportAttachment,
        "file",
        "operasi.view_dailyreport",
        "",
    ),
    "foto-360": (SitePhoto360, "image", "operasi.view_sitephoto360", "korwil"),
    "tiket": (Ticket, "attachment", "operasi.view_ticket", ""),
    "uji-plts": (GeotechPhoto, "image", "operasi.view_geotechpoint", "point__korwil"),
}


def attendance_queryset(user):
    """Absensi yang boleh dilihat: semua (Administrator), anggota Korwil yang dipimpin, dan diri sendiri."""
    queryset = Attendance.objects.all()
    if aset_scope.sees_all(user):
        return queryset
    return queryset.filter(Q(user=user) | Q(user__in=services.team_users(user)))


def analysis_queryset(user):
    """Riwayat AI Satelit: milik sendiri, kecuali Administrator yang melihat semuanya."""
    queryset = AreaAnalysis.objects.all()
    if aset_scope.sees_all(user):
        return queryset
    return queryset.filter(requested_by=user)


def file_url(kind: str, obj) -> str:
    return reverse("operasi-file", args=[kind, obj.pk])


@command_login_required
def private_file(request, kind, pk):
    from alokasi.views import serve_file

    if kind not in FILE_KINDS:
        raise Http404
    model, field, permission, lookup = FILE_KINDS[kind]
    if not request.user.has_perm(permission):
        raise PermissionDenied
    if model is Attendance:
        queryset = attendance_queryset(request.user)
    elif model is AreaAnalysis:
        queryset = analysis_queryset(request.user)
    elif model is TaskEvent:
        queryset = TaskEvent.objects.filter(
            task__in=task_flow.visible_tasks(request.user)
        )
    elif model is Ticket:
        from operasi import tools

        queryset = tools.visible_tickets(request.user)
    elif model is DailyReportAttachment:
        queryset = DailyReportAttachment.objects.filter(
            report__in=daily_reports.visible_reports(request.user)
        )
    elif lookup:
        queryset = geo.scoped(model.objects.all(), request.user, lookup)
    else:
        queryset = model.objects.all()
    obj = get_object_or_404(queryset, pk=pk)
    return serve_file(getattr(obj, field), inline=request.GET.get("lihat") == "1")


# --------------------------------------------------------------------------
# Ringkasan & lapisan peta
# --------------------------------------------------------------------------


@api()
def summary(request):
    korwil = None
    if request.GET.get("korwil", "").isdigit():
        korwil = get_object_or_404(
            services.visible_korwils(request.user), pk=request.GET["korwil"]
        )
    data = services.summary(request.user, korwil)
    data["korwil_name"] = str(korwil) if korwil else ""
    return JsonResponse(data)


def _korwil_features(request):
    stats = services.korwil_stats(request.user)
    korwils = services.visible_korwils(request.user).select_related("coordinator")
    for korwil in korwils.exclude(geometry__isnull=True):
        data = stats.get(korwil.pk, {})
        yield feature(
            korwil.geometry,
            {
                "id": korwil.pk,
                "kind": "korwil",
                "code": korwil.code,
                "title": str(korwil),
                "color": korwil.color,
                "stats": data,
                "rows": [
                    [
                        _("Koordinator"),
                        _name(korwil.coordinator) if korwil.coordinator_id else "-",
                    ],
                    [_("Kampung"), korwil.villages or "-"],
                    [_("Warga terdata"), angka(data.get("total", 0))],
                    [
                        _("Pro"),
                        (
                            f"{data['pro_pct']}%"
                            if data.get("pro_pct") is not None
                            else "-"
                        ),
                    ],
                    [
                        _("RTRW sesuai"),
                        (
                            f"{data['rtrw_pct']}%"
                            if data.get("rtrw_pct") is not None
                            else "-"
                        ),
                    ],
                    [
                        _("Lahan sudah / belum"),
                        f"{data.get('released', 0)} / {data.get('pending', 0)}",
                    ],
                    [_("Kegiatan"), angka(data.get("activities", 0))],
                    [_("Uji tanah"), angka(data.get("soil", 0))],
                ],
            },
        )


def _resident_features(request):
    queryset = geo.scoped(
        Resident.objects.exclude(location__isnull=True).select_related(
            "korwil", "pengadaan_parcel"
        ),
        request.user,
    )
    if request.GET.get("korwil", "").isdigit():
        queryset = queryset.filter(korwil_id=request.GET["korwil"])
    for resident in queryset[:MAX_FEATURES]:
        released = resident.land_status == enums.LandStatus.RELEASED or (
            resident.pengadaan_parcel_id
            and resident.pengadaan_parcel.status in RELEASED_PARCEL_STATUSES
        )
        land = enums.LandStatus.RELEASED if released else enums.LandStatus.PENDING
        yield feature(
            resident.location,
            {
                "id": resident.pk,
                "kind": "warga",
                "title": resident.head_name,
                "stance": resident.stance,
                "land": land,
                "rtrw": resident.rtrw_status,
                "color": enums.STANCE_COLORS.get(resident.stance, "#8c959f"),
                "rows": [
                    [_("Nomor"), resident.number],
                    [_("Korwil"), resident.korwil.code if resident.korwil_id else "-"],
                    [_("Kampung"), resident.village or "-"],
                    [_("Sikap"), resident.get_stance_display()],
                    [_("Status lahan"), enums.LandStatus(land).label],
                    [_("RTRW"), resident.get_rtrw_status_display()],
                    [_("Pilihan"), resident.get_relocation_choice_display()],
                ],
            },
        )


def _activity_features(request):
    days = _int_or_none(request.GET.get("hari"), 1, 3650) or 90
    since = timezone.now() - datetime.timedelta(days=days)
    queryset = geo.scoped(
        Activity.objects.filter(started_at__gte=since)
        .exclude(location__isnull=True)
        .select_related("reported_by", "korwil"),
        request.user,
    )
    for activity in queryset[:MAX_FEATURES]:
        yield feature(
            activity.location,
            {
                "id": activity.pk,
                "kind": "kegiatan",
                "type": activity.activity_type,
                "title": activity.title,
                "color": enums.ACTIVITY_COLORS.get(activity.activity_type, "#6e7781"),
                "rows": [
                    [_("Nomor"), activity.number],
                    [_("Jenis"), activity.get_activity_type_display()],
                    [
                        _("Waktu"),
                        timezone.localtime(activity.started_at).strftime(
                            "%d-%m-%Y %H:%M"
                        ),
                    ],
                    [_("Petugas"), _name(activity.reported_by)],
                    [_("Warga hadir"), activity.participants_count or "-"],
                ],
            },
        )


def _soil_features(request):
    queryset = geo.scoped(SoilTest.objects.select_related("korwil"), request.user)
    for test in queryset[:MAX_FEATURES]:
        yield feature(
            test.location,
            {
                "id": test.pk,
                "kind": "tanah",
                "title": test.number,
                "color": enums.SOIL_COLORS.get(test.suitability, "#8c959f"),
                "rows": [
                    [_("Kelayakan"), test.get_suitability_display()],
                    [_("Tekstur"), test.get_texture_display() or "-"],
                    [_("pH"), test.ph if test.ph is not None else "-"],
                    [
                        _("Daya dukung"),
                        (
                            f"{test.bearing_capacity_kpa} kPa"
                            if test.bearing_capacity_kpa is not None
                            else "-"
                        ),
                    ],
                    [
                        _("Diambil"),
                        timezone.localtime(test.sampled_at).strftime("%d-%m-%Y"),
                    ],
                ],
            },
        )


def _officer_features(request):
    config = CommandSettings.load()
    since = timezone.now() - datetime.timedelta(minutes=config.online_minutes)
    for position in OfficerPosition.objects.filter(
        updated_at__gte=since, user__in=services.visible_officers(request.user)
    ).select_related("user"):
        yield feature(
            position.location,
            {
                "id": position.user_id,
                "kind": "petugas",
                "title": _name(position.user),
                "color": "#38bdf8",
                "heading": (
                    float(position.heading) if position.heading is not None else None
                ),
                "self": position.user_id == request.user.pk,
                "rows": [
                    [
                        _("Diperbarui"),
                        timezone.localtime(position.updated_at).strftime("%H:%M:%S"),
                    ],
                    [
                        _("Akurasi"),
                        (
                            f"{position.accuracy_m} m"
                            if position.accuracy_m is not None
                            else "-"
                        ),
                    ],
                    [
                        _("Baterai"),
                        (
                            f"{position.battery_pct}%"
                            if position.battery_pct is not None
                            else "-"
                        ),
                    ],
                ],
            },
        )


def _sos_features(request):
    queryset = geo.scoped(
        SosAlert.objects.filter(status__in=enums.OPEN_SOS_STATUSES).exclude(
            location__isnull=True
        ),
        request.user,
    ).select_related("raised_by")
    for alert in queryset:
        yield feature(
            alert.location,
            {
                "id": alert.pk,
                "kind": "sos",
                "title": f"🆘 {alert.number}",
                "color": "#ff1744",
                "rows": [
                    [_("Petugas"), _name(alert.raised_by)],
                    [_("Status"), alert.get_status_display()],
                    [
                        _("Waktu"),
                        timezone.localtime(alert.created_at).strftime("%d-%m-%Y %H:%M"),
                    ],
                    [_("Pesan"), alert.message or "-"],
                ],
            },
        )


def _illegal_features(request):
    queryset = geo.scoped(
        IllegalFinding.objects.exclude(location__isnull=True).annotate(
            n_visits=Count("visits")
        ),
        request.user,
    )
    for finding in queryset[:MAX_FEATURES]:
        yield feature(
            finding.location,
            {
                "id": finding.pk,
                "kind": "temuan",
                "title": f"⚠ {finding.number}",
                "color": enums.ILLEGAL_COLORS.get(finding.activity_kind, "#cf222e"),
                "rows": [
                    [_("Aktivitas"), finding.get_activity_kind_display()],
                    [_("Lokasi"), finding.location_name],
                    [_("Pemilik"), finding.owner_name or "-"],
                    [
                        _("Luas"),
                        f"{angka(finding.area_ha)} ha" if finding.area_ha else "-",
                    ],
                    [_("Kunjungan"), finding.n_visits],
                ],
            },
        )


def _patrol_features(request):
    queryset = geo.scoped(
        PatrolSession.objects.prefetch_related("observations__photos"), request.user
    )
    for session in queryset[:500]:
        started = (
            timezone.localtime(session.started_at).strftime("%d-%m-%Y %H:%M")
            if session.started_at
            else "-"
        )
        rows = [
            [_("Mulai"), started],
            [_("Ketua tim"), session.leader or "-"],
            [_("Jarak"), f"{angka(session.distance_m)} m"],
        ]
        if session.track is not None:
            yield feature(
                session.track,
                {
                    "id": session.pk,
                    "kind": "patroli",
                    "title": f"{session.number} {session.name}",
                    "color": "#06b6d4",
                    "rows": rows,
                },
            )
        for obs in session.observations.all():
            yield feature(
                obs.location,
                {
                    "id": obs.pk,
                    "kind": "patroli",
                    "title": f"{session.number} · {obs.kind}",
                    "color": {"NewPatrol": "#10b981", "StopPatrol": "#ef4444"}.get(
                        obs.kind, "#f59e0b"
                    ),
                    "rows": [
                        [
                            _("Waktu"),
                            (
                                timezone.localtime(obs.observed_at).strftime(
                                    "%d-%m-%Y %H:%M"
                                )
                                if obs.observed_at
                                else "-"
                            ),
                        ],
                        [_("Catatan"), obs.comment[:300] or "-"],
                    ],
                    "photos": [
                        file_url("patroli-foto", photo) + "?lihat=1"
                        for photo in obs.photos.all()
                    ],
                },
            )


LAYERS = {
    "korwil": ("operasi.view_korwil", _korwil_features),
    "warga": ("operasi.view_resident", _resident_features),
    "kegiatan": ("operasi.view_activity", _activity_features),
    "tanah": ("operasi.view_soiltest", _soil_features),
    "petugas": ("operasi.view_officerposition", _officer_features),
    "sos": ("operasi.view_sosalert", _sos_features),
    "temuan": ("operasi.view_illegalfinding", _illegal_features),
    "patroli": ("operasi.view_patrolsession", _patrol_features),
}


@api(permission=None)
def layer(request, key):
    from operasi import views_spatial, views_tools

    if key.startswith("ref-") and key[4:].isdigit():
        return JsonResponse(collection(views_spatial.overlay_features(int(key[4:]))))
    layers = {**LAYERS, **views_spatial.LAYERS, **views_tools.LAYERS}
    if key not in layers:
        raise Http404
    permission, builder = layers[key]
    if not request.user.has_perm(permission):
        raise PermissionDenied
    return JsonResponse(collection(builder(request)))


@api()
def search(request):
    return JsonResponse(
        {"results": services.search(request.user, request.GET.get("q", ""))}
    )


# --------------------------------------------------------------------------
# Absensi
# --------------------------------------------------------------------------


def _attendance_json(attendance) -> dict | None:
    if attendance is None:
        return None
    return {
        "id": attendance.pk,
        "date": attendance.date.isoformat(),
        "status": attendance.status,
        "status_label": attendance.status_text,
        "approval": attendance.approval,
        "korwil": str(attendance.korwil) if attendance.korwil_id else "",
        "check_in_at": _local(attendance.check_in_at),
        "check_out_at": _local(attendance.check_out_at),
        "check_in_in_area": attendance.check_in_in_area,
        "check_out_in_area": attendance.check_out_in_area,
        "worked_minutes": attendance.worked_minutes,
        "missing_checkout": attendance.missing_checkout,
        "note": attendance.note,
    }


@api(permission="operasi.add_attendance", methods=("GET", "POST"))
def attendance(request):
    user = request.user
    if request.method == "POST":
        data = request.POST
        action = data.get("aksi")
        photo = request.FILES.get("foto")
        location = _parse_location(data)
        accuracy = _accuracy(data.get("accuracy"))
        warnings = []
        with transaction.atomic():
            if action == "masuk":
                record, _created, warnings = services.check_in(
                    user,
                    location=location,
                    accuracy=accuracy,
                    photo=photo,
                    note=data.get("note", ""),
                )
            elif action == "pulang":
                record, _created, warnings = services.check_out(
                    user,
                    location=location,
                    accuracy=accuracy,
                    photo=photo,
                    note=data.get("note", ""),
                )
            elif action == "izin":
                try:
                    day = datetime.date.fromisoformat(data.get("tanggal", ""))
                except ValueError:
                    raise ValidationError(_("Tanggal izin tidak sah."))
                record = services.request_leave(
                    user,
                    status=data.get("jenis", ""),
                    date=day,
                    note=data.get("note", ""),
                    attachment=request.FILES.get("lampiran"),
                )
            else:
                raise ValidationError(_("Tindakan absen tidak dikenal."))
        return JsonResponse(
            {
                "attendance": _attendance_json(record),
                "warnings": [str(w) for w in warnings],
            }
        )
    today = timezone.localdate()
    history = Attendance.objects.filter(
        user=user, date__gte=today - datetime.timedelta(days=30)
    ).select_related("korwil")
    return JsonResponse(
        {
            "today": _attendance_json(
                next((a for a in history if a.date == today), None)
            ),
            "history": [_attendance_json(a) for a in history],
        }
    )


@api(permission="operasi.view_attendance")
def leave_requests(request):
    """Pengajuan izin anggota tim yang menunggu keputusan koordinator / Administrator."""
    results = []
    for record in services.leave_requests(request.user)[:200]:
        item = _attendance_json(record)
        item["user"] = _name(record.user)
        item["attachment"] = (
            file_url("absen-lampiran", record) + "?lihat=1" if record.attachment else ""
        )
        results.append(item)
    return JsonResponse({"results": results})


@api(permission="operasi.view_attendance", methods=("POST",))
def leave_decision(request, pk):
    record = get_object_or_404(services.leave_requests(request.user), pk=pk)
    decision = request.POST.get("keputusan")
    if decision not in ("setuju", "tolak"):
        raise ValidationError({"keputusan": [_("Pilih setuju atau tolak.")]})
    services.decide_leave(record, request.user, decision == "setuju")
    return JsonResponse(_attendance_json(record))


# --------------------------------------------------------------------------
# Kegiatan & uji tanah
# --------------------------------------------------------------------------


def _can_confirm_impact(user, activity) -> bool:
    return approvals.can_confirm_impact(user, activity)


def _activity_json(activity, user=None) -> dict:
    return {
        **reports.describe(activity),
        "id": activity.pk,
        "number": activity.number,
        "client_id": str(activity.client_id),
        "type": activity.activity_type,
        "type_label": activity.get_activity_type_display(),
        "title": activity.title,
        "description": activity.description,
        "started_at": _local(activity.started_at),
        "korwil": activity.korwil.code if activity.korwil_id else "",
        "participants": activity.participants_count,
        "outcome": activity.outcome,
        "voice": file_url("kegiatan-suara", activity) if activity.voice_note else "",
        "reporter": _name(activity.reported_by),
        "verified": activity.verified,
        "location_name": activity.location_name,
        "companion": activity.companion,
        "points": float(activity.effort_points),
        "impact": activity.impact_tier,
        "impact_label": (
            enums.ImpactTier(activity.impact_tier).label if activity.impact_tier else ""
        ),
        "impact_pending": activity.needs_impact_confirmation,
        "can_confirm": bool(user and _can_confirm_impact(user, activity)),
        "ai_stance": activity.ai_stance,
        "residents": activity.residents.count(),
        "lat": activity.location.y if activity.location else None,
        "lng": activity.location.x if activity.location else None,
        "photos": [file_url("kegiatan", p) + "?lihat=1" for p in activity.photos.all()],
    }


def _parse_stance_updates(raw) -> dict[int, str]:
    if not raw:
        return {}
    try:
        updates = json.loads(raw)
    except json.JSONDecodeError:
        raise ValidationError(_("Data perubahan sikap warga tidak sah."))
    if not isinstance(updates, dict) or len(updates) > MAX_STANCE_UPDATES:
        raise ValidationError(_("Data perubahan sikap warga tidak sah."))
    result = {}
    for key, value in updates.items():
        if not str(key).isdigit() or value not in enums.Stance.values:
            raise ValidationError(_("Data perubahan sikap warga tidak sah."))
        result[int(key)] = value
    return result


def _ids(raw) -> list[int]:
    return [int(v) for v in str(raw or "").split(",") if v.strip().isdigit()][:200]


def _client_id(data):
    client_id = _uuid(data.get("client_id"))
    if client_id is None:
        raise ValidationError({"client_id": [_("ID perangkat tidak sah.")]})
    return client_id


def _duplicate(obj) -> JsonResponse:
    """Kiriman ulang antrean luring: kembalikan catatan yang sudah tersimpan."""
    return JsonResponse({"id": obj.pk, "number": obj.number, "duplicate": True})


def _duplicate_or_raise(model, client_id):
    """Ambil catatan duplikat antrean luring; galat integrity lain diteruskan."""
    try:
        return model.objects.get(client_id=client_id)
    except model.DoesNotExist:
        raise  # bukan duplikasi client_id: biarkan galat integrity asli naik


@api(permission="operasi.view_activity", methods=("GET", "POST"))
def activities(request):
    if request.method == "GET":
        return _list_activities(request)
    return _create_activity(request)


def _list_activities(request):
    user = request.user
    queryset = (
        geo.scoped(Activity.objects.all(), user)
        .select_related("korwil", "reported_by")
        .prefetch_related("photos")
    )
    scope = request.GET.get("lingkup")
    if scope == "korwil":
        korwils = list(geo.user_korwils(user)) + list(
            Korwil.objects.filter(coordinator=user)
        )
        queryset = queryset.filter(korwil__in=korwils)
    elif scope != "semua":
        queryset = queryset.filter(reported_by=user)
    queryset = queryset.select_related(
        "illegal_visit__finding", "patrol_report"
    ).prefetch_related("patrol_report__seedlings")
    return JsonResponse({"results": [_activity_json(a, user) for a in queryset[:50]]})


def _activity_relations(activity, data, user):
    if data.get("korwil", "").isdigit():
        activity.korwil = get_object_or_404(
            services.visible_korwils(user), pk=data["korwil"]
        )
    if data.get("tugas", "").isdigit():
        from asetlahan.models import Task

        activity.task = get_object_or_404(
            aset_scope.scoped(Task.objects.all(), user), pk=data["tugas"]
        )


def photo_object(upload, location=None) -> ActivityPhoto:
    item = ActivityPhoto(photo=upload, location=location)
    item.full_clean(exclude=["activity", "hunting_finding"])
    return item


def _save_activity(
    activity, residents, photo_objects, stance_updates, user, parts=None
):
    with transaction.atomic():
        activity.save()
        activity.residents.set(residents)
        for item in photo_objects:
            item.activity = activity
            item.save()
        if parts is not None:
            reports.commit(parts, activity, user)
        for resident in residents:
            new = stance_updates.get(resident.pk)
            if new and new != resident.stance:
                resident.stance = new
                resident._changed_by = user
                resident._activity = activity
                resident.save()
        activity.touch_residents()
        activity.refresh_effort()
        services.schedule_ai_stance(activity, user)


def _create_activity(request):
    user = request.user
    if not user.has_perm("operasi.add_activity"):
        raise PermissionDenied
    data = request.POST
    client_id = _client_id(data)
    existing = Activity.objects.filter(client_id=client_id).first()
    if existing is not None:
        return _duplicate(existing)
    photos = request.FILES.getlist("foto")[:MAX_PHOTOS]
    voice = request.FILES.get("suara") or None
    stance_updates = _parse_stance_updates(data.get("sikap"))
    activity = Activity(
        client_id=client_id,
        activity_type=data.get("jenis") or enums.ActivityType.VISIT,
        title=(data.get("judul") or "").strip()[:255],
        description=(data.get("uraian") or "")[:10000],
        companion=(data.get("pendamping") or "").strip()[:255],
        location_name=(data.get("lokasi") or "").strip()[:255],
        distance_m=_int_or_none(data.get("jarak_m"), 0, 10_000_000),
        impact_scope=_int_or_none(data.get("dampak_cakupan"), 0, 9),
        impact_risk=_int_or_none(data.get("dampak_risiko"), 0, 9),
        impact_result=_int_or_none(data.get("dampak_hasil"), 0, 9),
        started_at=_parse_captured_at(data.get("waktu")),
        duration_minutes=_int_or_none(data.get("durasi"), 0, 100_000),
        location=_parse_location(data),
        accuracy_m=_accuracy(data.get("accuracy")),
        participants_count=_int_or_none(data.get("peserta"), 0, 1_000_000),
        outcome=(data.get("hasil") or "")[:10000],
        voice_note=voice,
        reported_by=user,
    )
    _activity_relations(activity, data, user)
    geo.assign_korwil(activity, user)
    if activity.activity_type not in enums.ActivityType.values:
        raise ValidationError({"jenis": [_("Pilihan tidak sah.")]})
    parts = reports.prepare(activity, data, request.FILES, user)
    if not activity.title and activity.activity_type in AUTO_TITLE_TYPES:
        activity.title = _default_title(activity, parts)
    activity.full_clean(
        exclude=["number", "korwil", "task", "reported_by", "verified_by"],
        validate_unique=False,
    )
    resident_ids = set(_ids(data.get("warga"))) | set(stance_updates)
    residents = list(geo.scoped(Resident.objects.filter(pk__in=resident_ids), user))
    if len(residents) != len(resident_ids):
        raise ValidationError({"warga": [_("Sebagian warga tidak ditemukan.")]})
    if stance_updates and not user.has_perm("operasi.change_resident"):
        raise PermissionDenied
    photo_objects = [photo_object(photo, activity.location) for photo in photos]
    try:
        _save_activity(activity, residents, photo_objects, stance_updates, user, parts)
    except IntegrityError:
        return _duplicate(_duplicate_or_raise(Activity, client_id))
    return JsonResponse(
        {
            "id": activity.pk,
            "number": activity.number,
            "duplicate": False,
            "korwil": str(activity.korwil or ""),
        },
        status=201,
    )


# Jenis yang judulnya boleh kosong (dibuat otomatis); Kegiatan lainnya wajib bernama.
AUTO_TITLE_TYPES = (
    enums.ActivityType.KOMSOS,
    enums.ActivityType.TOPOGRAPHY,
    enums.ActivityType.ILLEGAL,
    enums.ActivityType.HUNTING_PARK,
)


def _default_title(activity, parts) -> str:
    """Judul otomatis bila petugas tidak mengisi (Komsos, Topografi, dst.)."""
    label = activity.get_activity_type_display()
    names = [r.head_name for r in parts.residents]
    if activity.activity_type == enums.ActivityType.KOMSOS and names:
        return f"{label}: {', '.join(names)}"[:255]
    if activity.location_name:
        return f"{label} – {activity.location_name}"[:255]
    return label


@api(permission="operasi.change_activity", methods=("POST",))
def confirm_impact(request, pk):
    activity = get_object_or_404(
        geo.scoped(Activity.objects.select_related("korwil"), request.user), pk=pk
    )
    if not _can_confirm_impact(request.user, activity):
        raise PermissionDenied
    activity.impact_confirmed = True
    activity.impact_confirmed_by = request.user
    activity.impact_confirmed_at = timezone.now()
    activity.save(
        update_fields=[
            "impact_confirmed",
            "impact_confirmed_by",
            "impact_confirmed_at",
            "modified_at",
        ]
    )
    activity.refresh_effort()
    return JsonResponse(_activity_json(activity, request.user))


def _finding_json(finding) -> dict:
    return {
        "id": finding.pk,
        "number": finding.number,
        "kind": finding.activity_kind,
        "kind_label": finding.get_activity_kind_display(),
        "location_name": finding.location_name,
        "owner_name": finding.owner_name,
        "owner_phone": finding.owner_phone,
        "owner_domicile": finding.owner_domicile,
        "manager_name": finding.manager_name,
        "manager_phone": finding.manager_phone,
        "area_ha": str(finding.area_ha) if finding.area_ha is not None else "",
        "forest_status": finding.forest_status,
        "business_started": finding.business_started,
        "korwil": finding.korwil.code if finding.korwil_id else "",
        "lat": finding.location.y if finding.location else None,
        "lng": finding.location.x if finding.location else None,
    }


@api(permission="operasi.view_illegalfinding")
def illegal_findings(request):
    """Cari temuan ilegal yang sudah tercatat (untuk kunjungan berulang)."""
    query = (request.GET.get("q") or "").strip()[:100]
    queryset = geo.scoped(IllegalFinding.objects.select_related("korwil"), request.user)
    if len(query) >= 2:
        queryset = queryset.filter(
            Q(location_name__icontains=query)
            | Q(number__icontains=query)
            | Q(owner_name__icontains=query)
            | Q(manager_name__icontains=query)
        )
    return JsonResponse({"results": [_finding_json(f) for f in queryset[:15]]})


@api(permission="operasi.add_activity", methods=("POST",))
def patrol_preview(request):
    """Baca berkas SMART dan kembalikan isian laporan Taman Buru (tanpa menyimpan)."""
    upload = request.FILES.get("smart")
    if upload is None:
        raise ValidationError({"smart": [_("Pilih berkas SMART (.json).")]})
    if upload.size > patrol.MAX_FILE_BYTES:
        raise ValidationError({"smart": [_("Berkas SMART maksimal 15 MB.")]})
    return JsonResponse(patrol.prefill(patrol.parse(upload.read())))


@api(permission="operasi.change_activity", methods=("POST",))
def verify_activity(request, pk):
    activity = get_object_or_404(
        geo.scoped(Activity.objects.all(), request.user), pk=pk
    )
    leads = activity.korwil_id and activity.korwil.coordinator_id == request.user.pk
    if not (leads or aset_scope.sees_all(request.user)):
        raise PermissionDenied
    activity.verified = request.POST.get("verified", "1") == "1"
    activity.verified_by = request.user if activity.verified else None
    activity.save()
    return JsonResponse(_activity_json(activity, request.user))


def _soil_json(test) -> dict:
    return {
        "id": test.pk,
        "number": test.number,
        "sampled_at": _local(test.sampled_at),
        "korwil": test.korwil.code if test.korwil_id else "",
        "texture": test.get_texture_display(),
        "ph": str(test.ph) if test.ph is not None else "",
        "suitability": test.suitability,
        "suitability_label": test.get_suitability_display(),
        "lat": test.location.y,
        "lng": test.location.x,
    }


@api(permission="operasi.view_soiltest", methods=("GET", "POST"))
def soil_tests(request):
    user = request.user
    if request.method == "GET":
        queryset = geo.scoped(SoilTest.objects.select_related("korwil"), user)
        if request.GET.get("lingkup") != "semua":
            queryset = queryset.filter(sampled_by=user)
        return JsonResponse({"results": [_soil_json(t) for t in queryset[:50]]})
    return _create_soil_test(request)


def _create_soil_test(request):
    user = request.user
    if not user.has_perm("operasi.add_soiltest"):
        raise PermissionDenied
    data = request.POST
    client_id = _client_id(data)
    existing = SoilTest.objects.filter(client_id=client_id).first()
    if existing is not None:
        return _duplicate(existing)
    location = _parse_location(data)
    if location is None:
        raise ValidationError({"location": [_("Lokasi GPS wajib untuk uji tanah.")]})
    texture = data.get("tekstur", "")
    suitability = data.get("kelayakan") or enums.SoilSuitability.PENDING
    test = SoilTest(
        client_id=client_id,
        location=location,
        sampled_at=_parse_captured_at(data.get("waktu")),
        sampled_by=user,
        depth_cm=_int_or_none(data.get("kedalaman"), 0, 100_000),
        texture=texture,
        color=(data.get("warna") or "")[:64],
        ph=_decimal_or_none(data.get("ph"), 0, 14),
        moisture_pct=_decimal_or_none(data.get("kadar_air"), 0, 100),
        organic_c_pct=_decimal_or_none(data.get("c_organik"), 0, 100),
        bearing_capacity_kpa=_decimal_or_none(data.get("daya_dukung"), 0, 999_999),
        cbr_pct=_decimal_or_none(data.get("cbr"), 0, 100),
        suitability=suitability,
        lab_name=(data.get("lab") or "")[:255],
        note=(data.get("catatan") or "")[:10000],
    )
    if request.FILES.get("foto"):
        test.photo = request.FILES["foto"]
    if request.FILES.get("laporan"):
        test.lab_report = request.FILES["laporan"]
    test.full_clean(exclude=["number", "korwil", "sampled_by"], validate_unique=False)
    geo.assign_korwil(test, user)
    try:
        with transaction.atomic():
            test.save()
    except IntegrityError:
        return _duplicate(_duplicate_or_raise(SoilTest, client_id))
    return JsonResponse(
        {"id": test.pk, "number": test.number, "duplicate": False}, status=201
    )


# --------------------------------------------------------------------------
# Warga
# --------------------------------------------------------------------------


def _resident_json(resident) -> dict:
    return {
        "id": resident.pk,
        "number": resident.number,
        "name": resident.head_name,
        "korwil": resident.korwil.code if resident.korwil_id else "",
        "korwil_id": resident.korwil_id,
        "village": resident.village,
        "address": resident.address,
        "phone": resident.phone,
        "members": resident.member_count,
        "gender": resident.gender,
        "age": resident.age,
        "occupation": resident.occupation,
        "origin": resident.origin,
        "years_living": resident.years_living,
        "spouse_name": resident.spouse_name,
        "child_count": resident.child_count,
        "residency": resident.residency_status,
        "spouse_occupation": resident.spouse_occupation,
        "children_detail": resident.children_detail,
        "land_area_m2": str(resident.land_area_m2) if resident.land_area_m2 else None,
        "cultivation": resident.cultivation_status,
        "land_condition": resident.land_condition,
        "stance": resident.stance,
        "land": resident.land_status,
        "rtrw": resident.rtrw_status,
        "zone": resident.rtrw_zone,
        "relocation": resident.relocation_choice,
        "last_visited": (
            resident.last_visited_on.isoformat() if resident.last_visited_on else ""
        ),
        "lat": resident.location.y if resident.location else None,
        "lng": resident.location.x if resident.location else None,
        "note": resident.note,
    }


def _apply_resident_numbers(resident, data):
    """Isian angka dossier warga (opsional; kosong = tidak diketahui)."""
    numbers = (
        ("jiwa", "member_count", 0, 1000),
        ("umur", "age", 0, 130),
        ("anak", "child_count", 0, 50),
        ("menetap", "years_living", 0, 130),
    )
    errors = {}
    for key, field, low, high in numbers:
        if key in data:
            raw = (data.get(key) or "").strip()
            value = _int_or_none(raw, low, high)
            if raw and value is None:
                errors[key] = [
                    _("Isi bilangan bulat %(low)s–%(high)s.")
                    % {"low": low, "high": high}
                ]
            setattr(resident, field, value)
    if "luas_lahan" in data:
        raw = (data.get("luas_lahan") or "").strip()
        value = _decimal_or_none(raw, 0, MAX_LAND_AREA_M2, places=2)
        if raw and value is None:
            errors["luas_lahan"] = [_("Luas lahan harus angka 0 atau lebih.")]
        resident.land_area_m2 = value
    if errors:
        raise ValidationError(errors)


def _apply_resident_fields(resident, data):
    for key, field, choices in (
        ("sikap", "stance", enums.Stance.values),
        ("lahan", "land_status", enums.LandStatus.values),
        ("rtrw", "rtrw_status", enums.RtrwStatus.values),
        ("zona", "rtrw_zone", enums.RtrwZone.values),
        ("pilihan", "relocation_choice", enums.RelocationChoice.values),
        ("gender", "gender", enums.Gender.values),
        ("penggarapan", "cultivation_status", enums.CultivationStatus.values),
        ("status_warga", "residency_status", enums.ResidencyStatus.values),
    ):
        value = data.get(key)
        # Pilihan opsional ("" = belum diketahui) boleh dikosongkan kembali.
        if value or (key in data and "" in choices):
            if value not in choices:
                raise ValidationError({key: [_("Pilihan tidak sah.")]})
            setattr(resident, field, value)
    for key, field, size in (
        ("nama", "head_name", 255),
        ("kampung", "village", 128),
        ("alamat", "address", 255),
        ("telepon", "phone", 32),
        ("pekerjaan", "occupation", 128),
        ("asal", "origin", 128),
        ("pasangan", "spouse_name", 255),
        ("kondisi_lahan", "land_condition", 2000),
        ("pekerjaan_pasangan", "spouse_occupation", 128),
        ("data_anak", "children_detail", 2000),
    ):
        if key in data:
            setattr(resident, field, data.get(key, "").strip()[:size])
    _apply_resident_numbers(resident, data)


def _apply_resident(resident, data, user):
    _apply_resident_fields(resident, data)
    if data.get("catatan", "").strip():
        stamp = timezone.localtime().strftime("%d-%m-%Y %H:%M")
        line = f"[{stamp} {_name(user)}] {data['catatan'].strip()[:2000]}"
        resident.note = "\n".join(filter(None, [resident.note, line]))
    if data.get("lat") and data.get("lng"):
        location = _parse_location(data)
        if location is None:
            raise ValidationError({"location": [_("Lokasi GPS tidak sah.")]})
        resident.location = location
    if data.get("korwil", "").isdigit():
        resident.korwil = get_object_or_404(
            services.visible_korwils(user), pk=data["korwil"]
        )
    if not resident.head_name.strip():
        raise ValidationError({"nama": [_("Nama kepala keluarga wajib diisi.")]})
    resident._changed_by = user


NIK_CONFLICT_LIMIT = 10


def _check_new_nik(nik: str, user) -> None:
    """Tolak NIK ganda tanpa membocorkan apakah NIK itu terdata di wilayah lain."""
    from pengadaan.crypto import fingerprint

    if not Resident.objects.filter(nik_fingerprint=fingerprint(nik)).exists():
        return
    if _throttled(f"operasi:nik:{user.pk}", NIK_CONFLICT_LIMIT, 3600):
        raise ValidationError(
            {"nik": [_("Terlalu banyak percobaan NIK. Coba lagi satu jam lagi.")]}
        )
    if user.has_perm("operasi.view_resident_nik") and aset_scope.sees_all(user):
        raise ValidationError({"nik": [_("NIK ini sudah terdata.")]})
    raise ValidationError(
        {
            "nik": [
                _(
                    "NIK tidak dapat dipakai. Periksa kembali atau hubungi Administrator."
                )
            ]
        }
    )


@api(permission="operasi.view_resident", methods=("GET", "POST"))
def residents(request):
    user = request.user
    if request.method == "POST":
        if not user.has_perm("operasi.add_resident"):
            raise PermissionDenied
        resident = Resident(created_by=user)
        _apply_resident(resident, request.POST, user)
        nik = "".join(ch for ch in request.POST.get("nik", "") if ch.isdigit())
        if nik:
            if len(nik) != 16:
                raise ValidationError({"nik": [_("NIK harus 16 digit.")]})
            _check_new_nik(nik, user)
            resident.nik = nik
        geo.assign_korwil(resident, user)
        resident.save()
        return JsonResponse(_resident_json(resident), status=201)
    queryset = geo.scoped(Resident.objects.select_related("korwil"), user)
    query = request.GET.get("q", "").strip()
    if query:
        queryset = queryset.filter(
            Q(head_name__icontains=query)
            | Q(number__icontains=query)
            | Q(village__icontains=query)
        )
    if request.GET.get("korwil", "").isdigit():
        queryset = queryset.filter(korwil_id=request.GET["korwil"])
    if request.GET.get("sikap") in enums.Stance.values:
        queryset = queryset.filter(stance=request.GET["sikap"])
    return JsonResponse({"results": [_resident_json(r) for r in queryset[:200]]})


@api(permission="operasi.view_resident", methods=("GET", "POST"))
def resident_detail(request, pk):
    resident = get_object_or_404(
        geo.scoped(Resident.objects.select_related("korwil"), request.user), pk=pk
    )
    if request.method == "POST":
        if not request.user.has_perm("operasi.change_resident"):
            raise PermissionDenied
        _apply_resident(resident, request.POST, request.user)
        resident.save()
    data = _resident_json(resident)
    data["history"] = [
        {
            "at": _local(change.changed_at),
            "from": change.get_old_stance_display(),
            "to": change.get_new_stance_display(),
            "by": _name(change.changed_by),
        }
        for change in resident.stance_changes.select_related("changed_by")[:20]
    ]
    data["activities"] = [
        {"number": a.number, "title": a.title, "at": _local(a.started_at)}
        for a in resident.activities.order_by("-started_at")[:20]
    ]
    return JsonResponse(data)


# --------------------------------------------------------------------------
# Chat internal
# --------------------------------------------------------------------------


def _channel(request, value):
    if value in ("", "umum", None):
        return None
    if not str(value).isdigit():
        raise Http404
    return get_object_or_404(services.visible_korwils(request.user), pk=value)


def _message_json(message, user) -> dict:
    return {
        "id": message.pk,
        "sender": _name(message.sender) if message.sender_id else _("Sistem"),
        "mine": message.sender_id == user.pk,
        "system": message.is_system,
        "body": message.body,
        "at": _local(message.created_at),
        "lat": message.location.y if message.location else None,
        "lng": message.location.x if message.location else None,
    }


@api(permission="operasi.view_chatmessage", methods=("GET", "POST"))
def chat(request):
    user = request.user
    if request.method == "POST":
        if not user.has_perm("operasi.add_chatmessage"):
            raise PermissionDenied
        body = (request.POST.get("pesan") or "").strip()
        if not body:
            raise ValidationError({"pesan": [_("Pesan kosong.")]})
        if _throttled(f"operasi:chat:{user.pk}", 30, 60):
            return JsonResponse(
                {"error": _("Terlalu banyak pesan. Tunggu sebentar.")}, status=429
            )
        message = ChatMessage.objects.create(
            korwil=_channel(request, request.POST.get("kanal")),
            sender=user,
            body=body[:2000],
            location=_parse_location(request.POST) if request.POST.get("lat") else None,
        )
        return JsonResponse(_message_json(message, user), status=201)
    channel = _channel(request, request.GET.get("kanal"))
    queryset = ChatMessage.objects.filter(korwil=channel)
    if channel is None:
        # Kanal umum: obrolan umum dan pesan sistem (SOS) dari Korwil yang terlihat.
        queryset = ChatMessage.objects.filter(Q(korwil=None) | Q(is_system=True))
    queryset = queryset.filter(services.chat_q(user)).select_related("sender")
    after = _int_or_none(request.GET.get("setelah"), 0, 2**62)
    if after:
        messages = list(queryset.filter(pk__gt=after).order_by("pk")[:100])
    else:
        messages = list(queryset.order_by("-pk")[:50])[::-1]
    return JsonResponse({"results": [_message_json(m, user) for m in messages]})


# --------------------------------------------------------------------------
# SOS
# --------------------------------------------------------------------------


def _sos_json(alert) -> dict:
    return {
        "id": alert.pk,
        "number": alert.number,
        "status": alert.status,
        "status_label": alert.get_status_display(),
        "by": _name(alert.raised_by),
        "mine": False,
        "korwil": alert.korwil.code if alert.korwil_id else "",
        "message": alert.message,
        "at": _local(alert.created_at),
        "lat": alert.location.y if alert.location else None,
        "lng": alert.location.x if alert.location else None,
        "handler": _name(alert.acknowledged_by) if alert.acknowledged_by_id else "",
    }


def _sos_duplicate_response(alert, user) -> JsonResponse:
    return JsonResponse(
        {**_sos_json(alert), "mine": alert.raised_by_id == user.pk, "duplicate": True}
    )


def _sos_list(user) -> JsonResponse:
    if not user.has_perm("operasi.view_sosalert"):
        return JsonResponse({"results": []})
    alerts = geo.scoped(
        SosAlert.objects.filter(status__in=enums.OPEN_SOS_STATUSES), user
    ).select_related("raised_by", "acknowledged_by", "korwil")
    results = []
    for alert in alerts:
        item = _sos_json(alert)
        item["mine"] = alert.raised_by_id == user.pk
        results.append(item)
    return JsonResponse({"results": results})


@api(permission=None, methods=("GET", "POST"))
def sos(request):
    user = request.user
    if request.method == "POST":
        if not user.has_perm("operasi.add_sosalert"):
            raise PermissionDenied
        # Tiap SOS mengirim surel ke seluruh grup admin: batasi per petugas.
        if _throttled(f"operasi:sos:{user.pk}", 10, 3600):
            return JsonResponse(
                {
                    "error": _(
                        "Terlalu banyak laporan SOS. Hubungi koordinator bila darurat."
                    )
                },
                status=429,
            )
        data = request.POST
        client_id = _uuid(data.get("client_id"))
        if client_id is None:
            raise ValidationError({"client_id": [_("ID perangkat tidak sah.")]})
        existing = SosAlert.objects.filter(client_id=client_id).first()
        if existing is not None:
            return _sos_duplicate_response(existing, user)
        alert = SosAlert(
            client_id=client_id,
            raised_by=user,
            location=_parse_location(data),
            accuracy_m=_accuracy(data.get("accuracy")),
            message=(data.get("pesan") or "")[:2000],
        )
        geo.assign_korwil(alert, user, strict=False)
        try:
            with transaction.atomic():
                alert.save()
        except IntegrityError:
            return _sos_duplicate_response(
                _duplicate_or_raise(SosAlert, client_id), user
            )
        services.raise_sos(alert)
        return JsonResponse(
            {**_sos_json(alert), "mine": True, "duplicate": False}, status=201
        )
    return _sos_list(user)


@api(permission=None, methods=("POST",))
def sos_action(request, pk, action):
    alert = get_object_or_404(geo.scoped(SosAlert.objects.all(), request.user), pk=pk)
    own_close = alert.raised_by_id == request.user.pk and action in ("selesai", "palsu")
    if not (request.user.has_perm("operasi.change_sosalert") or own_close):
        raise PermissionDenied
    services.update_sos(alert, action, request.user, request.POST.get("catatan", ""))
    return JsonResponse(
        {**_sos_json(alert), "mine": alert.raised_by_id == request.user.pk}
    )


# --------------------------------------------------------------------------
# Posisi Live
# --------------------------------------------------------------------------


@api(permission="operasi.add_officerposition", methods=("POST",))
def position(request):
    if request.POST.get("stop") == "1":
        OfficerPosition.objects.filter(user=request.user).delete()
        return JsonResponse({"stopped": True})
    location = _parse_location(request.POST)
    if location is None:
        raise ValidationError({"location": [_("Lokasi GPS tidak sah.")]})
    accuracy = _accuracy(request.POST.get("accuracy"))
    spatial.record_track(request.user, location, accuracy)
    # Jejak lama dibersihkan sekali sehari.
    if cache.add(f"operasi:jejak-bersih:{timezone.localdate()}", 1, 86400):
        spatial.prune_tracks()
    OfficerPosition.objects.update_or_create(
        user=request.user,
        defaults={
            "location": location,
            "accuracy_m": accuracy,
            "heading": _decimal_or_none(request.POST.get("heading"), 0, 360, places=1),
            "speed_mps": _decimal_or_none(request.POST.get("speed"), 0, 9999),
            "battery_pct": _int_or_none(request.POST.get("battery"), 0, 100),
            "updated_at": timezone.now(),
        },
    )
    return JsonResponse({"ok": True})


# --------------------------------------------------------------------------
# AI Satelit
# --------------------------------------------------------------------------


def _analysis_json(analysis) -> dict:
    return {
        "id": analysis.pk,
        "summary": analysis.data_summary,
        "ai": analysis.ai_result,
        "model": analysis.ai_model,
        "error": analysis.error,
        "image": file_url("citra", analysis) + "?lihat=1" if analysis.image else "",
        "admin": reverse("admin:operasi_areaanalysis_change", args=[analysis.pk]),
    }


@api(permission="operasi.add_areaanalysis", methods=("POST",))
def satellite_analysis(request):
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        raise ValidationError(_("Permintaan tidak sah."))
    if not isinstance(payload, dict):
        raise ValidationError(_("Permintaan tidak sah."))
    from asetlahan import ai as ai_client

    if not ai_client.take_budget(request.user, "analisis-satelit", 20):
        return JsonResponse(
            {"error": _("Batas 20 analisis per jam tercapai. Coba lagi nanti.")},
            status=429,
        )
    try:
        analysis = satellite.analyze(payload.get("bbox"), request.user)
    except satellite.AnalysisError as error:
        raise ValidationError(str(error))
    return JsonResponse(_analysis_json(analysis), status=201)


# --------------------------------------------------------------------------
# Struktur, feed, AI chat
# --------------------------------------------------------------------------


@api(permission="operasi.view_korwil", methods=("GET",))
def structure(request):
    """Struktur organisasi tim lapangan: Korwil → koordinator → anggota."""
    rows = []
    for korwil in services.visible_korwils(request.user).filter(is_active=True):
        members = korwil.members.order_by("last_name", "first_name")
        rows.append(
            {
                "id": korwil.pk,
                "code": korwil.code,
                "name": korwil.name,
                "color": korwil.color,
                "coordinator": (
                    _name(korwil.coordinator) if korwil.coordinator_id else ""
                ),
                "coordinator_id": korwil.coordinator_id,
                "villages": korwil.villages,
                "members": [{"id": m.pk, "name": _name(m)} for m in members],
            }
        )
    return JsonResponse({"results": rows})


def _feed_item(kind, title, by, at, korwil, url=""):
    return {
        "kind": kind,
        "title": title,
        "by": by,
        "at": _local(at),
        "korwil": korwil,
        "url": url,
    }


@api(permission="operasi.view_korwil", methods=("GET",))
def feed(request):
    """Feed aktivitas gabungan: kegiatan, uji tanah, perubahan sikap, SOS."""
    korwils = services.visible_korwils(request.user)
    korwil_filter = request.GET.get("korwil", "")
    if korwil_filter.isdigit():
        korwils = korwils.filter(pk=korwil_filter)
    korwil_codes = {k.pk: k.code for k in korwils}
    user = request.user
    items = []
    activities = Activity.objects.none()
    if user.has_perm("operasi.view_activity"):
        activities = Activity.objects.filter(korwil__in=korwils).select_related(
            "reported_by"
        )[:40]
    for activity in activities:
        items.append(
            (
                activity.started_at,
                _feed_item(
                    "kegiatan",
                    f"{activity.get_activity_type_display()}: {activity.title}",
                    _name(activity.reported_by) if activity.reported_by_id else "—",
                    activity.started_at,
                    korwil_codes.get(activity.korwil_id, ""),
                ),
            )
        )
    soil = SoilTest.objects.none()
    if user.has_perm("operasi.view_soiltest"):
        soil = SoilTest.objects.filter(korwil__in=korwils).select_related("sampled_by")[
            :30
        ]
    for test in soil:
        items.append(
            (
                test.sampled_at,
                _feed_item(
                    "tanah",
                    f"Uji tanah {test.number}",
                    _name(test.sampled_by) if test.sampled_by_id else "—",
                    test.sampled_at,
                    korwil_codes.get(test.korwil_id, ""),
                ),
            )
        )
    changes = StanceChange.objects.none()
    if user.has_perm("operasi.view_resident"):
        changes = StanceChange.objects.filter(
            resident__korwil__in=korwils
        ).select_related("resident", "changed_by")[:30]
    for change in changes:
        items.append(
            (
                change.changed_at,
                _feed_item(
                    "sikap",
                    f"{change.resident.head_name}: {change.get_old_stance_display()}"
                    f" → {change.get_new_stance_display()}",
                    _name(change.changed_by) if change.changed_by_id else "—",
                    change.changed_at,
                    korwil_codes.get(change.resident.korwil_id, ""),
                ),
            )
        )
    alerts = SosAlert.objects.none()
    if user.has_perm("operasi.view_sosalert"):
        alerts = (
            SosAlert.objects.filter(korwil__in=korwils)
            .select_related("raised_by")
            .order_by("-created_at")[:20]
        )
    for alert in alerts:
        items.append(
            (
                alert.created_at,
                _feed_item(
                    "sos",
                    f"SOS {alert.get_status_display()}",
                    _name(alert.raised_by) if alert.raised_by_id else "—",
                    alert.created_at,
                    korwil_codes.get(alert.korwil_id, ""),
                ),
            )
        )
    items.sort(key=lambda pair: pair[0], reverse=True)
    return JsonResponse({"results": [item for _, item in items[:60]]})


# --------------------------------------------------------------------------


@api(permission="operasi.view_korwil", methods=("POST",))
def ai_chat(request):
    """Asisten AI pusat komando: tanya data wilayah Anda dengan bahasa bebas.

    Tanpa kunci API, pertanyaan umum tetap dijawab dari ringkasan angka
    (pola sederhana), seperti asisten AI modul aset lahan.
    """
    from asetlahan import ai as ai_client

    user = request.user
    question = (request.POST.get("tanya") or "").strip()[:1000]
    if not question:
        raise ValidationError({"tanya": [_("Pertanyaan kosong.")]})
    if not ai_client.take_budget(user, "tanya-ai", 20):
        return JsonResponse(
            {"error": _("Batas 20 pertanyaan per jam tercapai. Coba lagi nanti.")},
            status=429,
        )
    context = _ai_context(user)
    answer = ""
    if ai_client.enabled():
        try:
            response = ai_client.create(
                max_tokens=700,
                system=_(
                    "Kamu adalah asisten pusat komando operasi lapangan. Jawab singkat, "
                    "konkret, dalam bahasa Indonesia, hanya berdasarkan data berikut. "
                    "Bila data tidak memuat jawabannya, katakan apa yang kurang."
                ),
                messages=[
                    {
                        "role": "user",
                        "content": f"DATA WILAYAH KERJA:\n{context}\n\nPERTANYAAN: {question}",
                    }
                ],
            )
            answer = ai_client.text_of(response)
        except ai_client.AIError as error:
            answer = str(error)
    if not answer:
        answer = _ai_fallback(question, context)
    return JsonResponse({"answer": answer[:4000]})


def _ai_context(user) -> str:
    """Ringkasan angka seluruh Korwil yang boleh dilihat pengguna."""
    stats = services.korwil_stats(user)
    zone_labels = dict(enums.RtrwZone.choices)
    zones = {}
    for row in (
        geo.scoped(Resident.objects.exclude(korwil=None), user)
        .values("korwil", "rtrw_zone")
        .annotate(n=Count("pk"))
        .order_by("rtrw_zone")
    ):
        zones.setdefault(row["korwil"], []).append(
            f"{zone_labels.get(row['rtrw_zone'], row['rtrw_zone'])} {row['n']}"
        )
    lines = []
    for korwil in services.visible_korwils(user):
        row = stats.get(korwil.pk) or {}
        zone_text = ", ".join(zones.get(korwil.pk, [])) or "-"
        lines.append(
            f"Korwil {korwil.code} ({korwil.name}): {row.get('total', 0)} warga, "
            f"Pro {row.get('pro_pct', 0)}%, RTRW sesuai {row.get('rtrw_pct', 0)}%, "
            f"lahan belum {row.get('pending', 0)}, lahan sudah {row.get('released', 0)}, "
            f"kegiatan {row.get('activities', 0)}, zona RTRW: {zone_text}."
        )
    return "\n".join(lines) or _("Belum ada data wilayah.")


def _ai_fallback(question: str, context: str) -> str:
    """Jawaban pola sederhana saat AI tidak terkonfigurasi/gagal."""
    lowered = question.lower()
    topics = (
        (("pro", "dukung", "sikap"), _("Rekap sikap per Korwil:\n")),
        (("rtrw", "ruang", "zona"), _("Rekap kesesuaian RTRW per Korwil:\n")),
        (("lahan", "bebas"), _("Rekap status lahan per Korwil:\n")),
    )
    for words, lead in topics:
        if any(word in lowered for word in words):
            return lead + context
    return (
        _("Asisten AI belum dikonfigurasi. " "Ringkasan data wilayah Anda:\n") + context
    )


# --------------------------------------------------------------------------
# Kunci sistem
# --------------------------------------------------------------------------


@api(permission=None, methods=("POST",))
def system_lock(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    if _throttled(f"operasi:lock:{request.user.pk}", 5, 900):
        return JsonResponse(
            {"error": _("Terlalu banyak percobaan. Coba lagi 15 menit lagi.")},
            status=429,
        )
    lock = SystemLock.load()
    if not lock.is_armed:
        return JsonResponse({"armed": False})
    if not lock.check_passcode(request.POST.get("passcode", "")):
        raise ValidationError({"passcode": [_("Kode rahasia salah.")]})
    lock.defuse(request.user)
    cache.delete(f"operasi:lock:{request.user.pk}")
    return JsonResponse({"armed": False})
