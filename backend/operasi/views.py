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
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
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
from operasi import enums, geo, satellite, services
from operasi.models import (
    RELEASED_PARCEL_STATUSES,
    Activity,
    ActivityPhoto,
    AreaAnalysis,
    Attendance,
    ChatMessage,
    CommandSettings,
    Korwil,
    OfficerPosition,
    Resident,
    SoilTest,
    SosAlert,
    SystemLock,
)

APP_VERSION = "1.0.0"
SW_VERSION = "4"  # naikkan setiap kali berkas cangkang (JS/CSS) berubah
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
    count = cache.get(key, 0)
    if count >= limit:
        return True
    cache.set(key, count + 1, seconds)
    return False


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
    layers = _map_layers(request)
    for layer in layers:
        layer["visible"] = False
    return layers


def _config(request) -> dict:
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
        "tim": services.team_users(user).exclude(pk=user.pk).exists(),
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
            if tab in ("peta", "absen", "korwil", "perf", "tasks", "warga", "chat")
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
            "relocation": _choices(enums.RelocationChoice.choices),
            "activityType": _choices(enums.ActivityType.choices),
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
        },
        "colors": {
            "stance": {str(k): v for k, v in enums.STANCE_COLORS.items()},
            "land": {str(k): v for k, v in enums.LAND_STATUS_COLORS.items()},
            "rtrw": {str(k): v for k, v in enums.RTRW_COLORS.items()},
            "activity": {str(k): v for k, v in enums.ACTIVITY_COLORS.items()},
            "soil": {str(k): v for k, v in enums.SOIL_COLORS.items()},
        },
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
            "soil": reverse("operasi-soil"),
            "residents": reverse("operasi-residents"),
            "resident": reverse("operasi-resident", args=[0]),
            "tasks": reverse("operasi-tasks"),
            "task": reverse("operasi-task", args=[0]),
            "performance": reverse("operasi-performance"),
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
            "login": reverse("admin:login") + "?next=" + reverse("operasi-command"),
            "logout": reverse("admin:logout"),
        },
    }


@never_cache
@staff_member_required
def command_center(request):
    if not request.user.has_perm("operasi.view_korwil"):
        return render(request, "operasi/forbidden.html", status=403)
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
        "background_color": "#0a0f1a",
        "theme_color": "#10b981",
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
        static("operasi/komando.js"),
        static("operasi/komando.css"),
        static("operasi/komando-icon.svg"),
        static("alokasi/vendor/leaflet/leaflet.js"),
        static("alokasi/vendor/leaflet/leaflet.css"),
    ]
    body = render(
        request,
        "operasi/komando_sw.js",
        {
            "shell": json.dumps(shell),
            "layer_prefix": json.dumps(reverse("operasi-layer", args=["x"])[:-2]),
            "version": json.dumps(SW_VERSION),
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
    "tanah-foto": (SoilTest, "photo", "operasi.view_soiltest", "korwil"),
    "tanah-lab": (SoilTest, "lab_report", "operasi.view_soiltest", "korwil"),
    "absen-masuk": (Attendance, "check_in_photo", "operasi.view_attendance", ""),
    "absen-pulang": (Attendance, "check_out_photo", "operasi.view_attendance", ""),
    "absen-lampiran": (Attendance, "attachment", "operasi.view_attendance", ""),
    "citra": (AreaAnalysis, "image", "operasi.view_areaanalysis", ""),
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


@staff_member_required
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


LAYERS = {
    "korwil": ("operasi.view_korwil", _korwil_features),
    "warga": ("operasi.view_resident", _resident_features),
    "kegiatan": ("operasi.view_activity", _activity_features),
    "tanah": ("operasi.view_soiltest", _soil_features),
    "petugas": ("operasi.view_officerposition", _officer_features),
    "sos": ("operasi.view_sosalert", _sos_features),
}


@api(permission=None)
def layer(request, key):
    if key not in LAYERS:
        raise Http404
    permission, builder = LAYERS[key]
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


def _activity_json(activity) -> dict:
    return {
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
        "reporter": _name(activity.reported_by),
        "verified": activity.verified,
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
    return JsonResponse({"results": [_activity_json(a) for a in queryset[:50]]})


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


def _save_activity(activity, residents, photo_objects, stance_updates, user):
    with transaction.atomic():
        activity.save()
        activity.residents.set(residents)
        for item in photo_objects:
            item.activity = activity
            item.save()
        for resident in residents:
            new = stance_updates.get(resident.pk)
            if new and new != resident.stance:
                resident.stance = new
                resident._changed_by = user
                resident._activity = activity
                resident.save()
        activity.touch_residents()


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
    stance_updates = _parse_stance_updates(data.get("sikap"))
    activity = Activity(
        client_id=client_id,
        activity_type=data.get("jenis") or enums.ActivityType.VISIT,
        title=(data.get("judul") or "").strip()[:255],
        description=(data.get("uraian") or "")[:10000],
        started_at=_parse_captured_at(data.get("waktu")),
        duration_minutes=_int_or_none(data.get("durasi"), 0, 100_000),
        location=_parse_location(data),
        accuracy_m=_accuracy(data.get("accuracy")),
        participants_count=_int_or_none(data.get("peserta"), 0, 1_000_000),
        outcome=(data.get("hasil") or "")[:10000],
        reported_by=user,
    )
    _activity_relations(activity, data, user)
    geo.assign_korwil(activity, user)
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
    photo_objects = []
    for photo in photos:
        item = ActivityPhoto(photo=photo)
        item.full_clean(exclude=["activity"])
        photo_objects.append(item)
    try:
        _save_activity(activity, residents, photo_objects, stance_updates, user)
    except IntegrityError:
        return _duplicate(Activity.objects.get(client_id=client_id))
    return JsonResponse(
        {
            "id": activity.pk,
            "number": activity.number,
            "duplicate": False,
            "korwil": str(activity.korwil or ""),
        },
        status=201,
    )


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
    return JsonResponse(_activity_json(activity))


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
        return _duplicate(SoilTest.objects.get(client_id=client_id))
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
        "stance": resident.stance,
        "land": resident.land_status,
        "rtrw": resident.rtrw_status,
        "relocation": resident.relocation_choice,
        "last_visited": (
            resident.last_visited_on.isoformat() if resident.last_visited_on else ""
        ),
        "lat": resident.location.y if resident.location else None,
        "lng": resident.location.x if resident.location else None,
        "note": resident.note,
    }


def _apply_resident_fields(resident, data):
    for key, field, choices in (
        ("sikap", "stance", enums.Stance.values),
        ("lahan", "land_status", enums.LandStatus.values),
        ("rtrw", "rtrw_status", enums.RtrwStatus.values),
        ("pilihan", "relocation_choice", enums.RelocationChoice.values),
    ):
        value = data.get(key)
        if value:
            if value not in choices:
                raise ValidationError({key: [_("Pilihan tidak sah.")]})
            setattr(resident, field, value)
    for key, field, size in (
        ("nama", "head_name", 255),
        ("kampung", "village", 128),
        ("alamat", "address", 255),
        ("telepon", "phone", 32),
    ):
        if key in data:
            setattr(resident, field, data.get(key, "").strip()[:size])
    if "jiwa" in data:
        resident.member_count = _int_or_none(data.get("jiwa"), 0, 1000)


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
# Tugas (modul aset lahan) untuk petugas
# --------------------------------------------------------------------------


def _task_json(task) -> dict:
    return {
        "id": task.pk,
        "number": task.number,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "status_label": task.get_status_display(),
        "priority": task.priority,
        "priority_label": task.get_priority_display(),
        "due_date": task.due_date.isoformat() if task.due_date else "",
        "progress": task.progress,
        "overdue": task.is_overdue,
        "korwil": task.korwil.code if task.korwil_id else "",
        "assignee": _name(task.assignee) if task.assignee_id else "",
        "mine": task.assignee_id is not None,
        "can_cancel": False,
    }


def _can_cancel_task(user, task) -> bool:
    """Batal hanya oleh pembuat tugas, koordinator Korwil terkait, atau Administrator."""
    if aset_scope.sees_all(user):
        return True
    if task.created_by_id == user.pk and task.assignee_id != user.pk:
        return True
    led = Korwil.objects.filter(coordinator=user, is_active=True)
    if task.korwil_id and led.filter(pk=task.korwil_id).exists():
        return True
    return bool(
        task.assignee_id
        and task.assignee_id != user.pk
        and led.filter(members=task.assignee_id).exists()
    )


def _tasks_for(user):
    from asetlahan.models import Task

    led = Korwil.objects.filter(coordinator=user)
    return aset_scope.scoped(
        Task.objects.filter(Q(assignee=user) | Q(korwil__in=led)), user
    ).select_related("assignee", "korwil")


@api(permission="asetlahan.view_task")
def tasks(request):
    queryset = _tasks_for(request.user)
    if request.GET.get("status") != "semua":
        queryset = queryset.filter(status__in=aset_enums.OPEN_TASK_STATUSES)
    results = []
    for task in queryset[:200]:
        item = _task_json(task)
        item["mine"] = task.assignee_id == request.user.pk
        item["can_cancel"] = _can_cancel_task(request.user, task)
        results.append(item)
    return JsonResponse({"results": results})


@api(permission="asetlahan.change_task", methods=("POST",))
def task_update(request, pk):
    task = get_object_or_404(_tasks_for(request.user), pk=pk)
    status = request.POST.get("status")
    if status:
        if status not in aset_enums.TaskStatus.values:
            raise ValidationError({"status": [_("Status tidak sah.")]})
        cancelling = (
            status == aset_enums.TaskStatus.CANCELLED
            and task.status != aset_enums.TaskStatus.CANCELLED
        )
        if cancelling and not _can_cancel_task(request.user, task):
            return JsonResponse(
                {
                    "error": _(
                        "Tugas hanya dapat dibatalkan oleh pembuat tugas, koordinator "
                        "Korwil, atau Administrator."
                    )
                },
                status=403,
            )
        task.status = status
    if "progress" in request.POST:
        progress = _int_or_none(request.POST.get("progress"), 0, 100)
        if progress is None:
            raise ValidationError({"progress": [_("Progres harus 0–100.")]})
        task.progress = progress
    task.full_clean()
    task.save()
    data = _task_json(task)
    data["mine"] = task.assignee_id == request.user.pk
    data["can_cancel"] = _can_cancel_task(request.user, task)
    return JsonResponse(data)


# --------------------------------------------------------------------------
# Kinerja (KPI)
# --------------------------------------------------------------------------


@api()
def performance(request):
    start, end = services.period_bounds(request.GET.get("periode", "bulan"))
    team = services.team_users(request.user)
    target = request.user
    if request.GET.get("petugas", "").isdigit():
        target = get_object_or_404(team, pk=request.GET["petugas"])
    data = {"me": services.performance(target, start, end)}
    if team.exclude(pk=request.user.pk).exists():
        data["team"] = services.leaderboard(request.user, start, end)
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


@api(permission=None, methods=("GET", "POST"))
def sos(request):
    user = request.user
    if request.method == "POST":
        if not user.has_perm("operasi.add_sosalert"):
            raise PermissionDenied
        data = request.POST
        client_id = _uuid(data.get("client_id"))
        if client_id is None:
            raise ValidationError({"client_id": [_("ID perangkat tidak sah.")]})
        existing = SosAlert.objects.filter(client_id=client_id).first()
        if existing is not None:
            return JsonResponse({**_sos_json(existing), "duplicate": True})
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
            existing = SosAlert.objects.get(client_id=client_id)
            return JsonResponse({**_sos_json(existing), "duplicate": True})
        services.raise_sos(alert)
        return JsonResponse({**_sos_json(alert), "duplicate": False}, status=201)
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


@api(permission=None, methods=("POST",))
def sos_action(request, pk, action):
    alert = get_object_or_404(geo.scoped(SosAlert.objects.all(), request.user), pk=pk)
    own_close = alert.raised_by_id == request.user.pk and action in ("selesai", "palsu")
    if not (request.user.has_perm("operasi.change_sosalert") or own_close):
        raise PermissionDenied
    services.update_sos(alert, action, request.user, request.POST.get("catatan", ""))
    return JsonResponse(_sos_json(alert))


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
    OfficerPosition.objects.update_or_create(
        user=request.user,
        defaults={
            "location": location,
            "accuracy_m": _accuracy(request.POST.get("accuracy")),
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
    if _throttled(f"operasi:ai:{request.user.pk}", 20, 3600):
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
# Kunci hidup sistem
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
