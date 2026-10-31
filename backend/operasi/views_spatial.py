"""API peta & spasial pusat komando: penguasaan lahan, tumpang tindih, audit
RTRW, anomali, peta panas, jejak GPS, zona ancaman, dan foto situs 360°."""

import datetime
import json
import os
import re
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from alokasi.templatetags.alokasi_tags import angka
from asetlahan import enums as aset_enums
from asetlahan import geo as aset_geo
from asetlahan.field_views import _parse_location
from operasi import enums, geo, services, spatial
from operasi.models import LandPlot, OfficerTrackPoint, SitePhoto360, ThreatZone
from operasi.views import _local, _name, api, file_url

MAX_IMPORT_BYTES = 20 * 1024 * 1024
MAX_PHOTO_BYTES = 20 * 1024 * 1024
MAX_PLOT_ROWS = 2000
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _visible_korwil(request, key="korwil"):
    value = request.GET.get(key) or request.POST.get(key) or ""
    if not value:
        return None
    if not str(value).isdigit():
        raise ValidationError({key: [_("Korwil tidak dikenal.")]})
    return get_object_or_404(services.visible_korwils(request.user), pk=value)


def _date(value, field):
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise ValidationError({field: [_("Tanggal tidak sah.")]})


def _csv(text: str, filename: str) -> HttpResponse:
    response = HttpResponse("﻿" + text, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# --------------------------------------------------------------------------
# Lapisan peta
# --------------------------------------------------------------------------


def _plot_features(request):
    plots = spatial.visible_plots(request.user).select_related("korwil", "resident")
    if request.GET.get("status") in enums.ControlStatus.values:
        plots = plots.filter(control_status=request.GET["status"])
    plots = list(plots[:5000])
    zones = spatial.plot_zones(plots)
    for plot in plots:
        row = spatial.plot_row(plot, zones[plot.pk])
        yield aset_geo.feature(
            plot.geometry,
            {
                "id": plot.pk,
                "kind": "bidang",
                "status": plot.control_status,
                "title": str(plot),
                "color": row["color"],
                "rows": [
                    [_("Status"), row["status_label"]],
                    [_("Pemilik"), plot.owner_name or "-"],
                    [_("Korwil"), row["korwil"] or "-"],
                    [_("Luas"), f"{angka(plot.area_ha)} ha"],
                    [_("Zona"), row["zone_label"]],
                    [_("Urgensi"), row["urgency_label"]],
                    [_("Skor prioritas"), angka(row["score"])],
                ],
            },
        )


def _threat_features(request):
    zones = geo.scoped(ThreatZone.objects.filter(is_active=True), request.user)
    for zone in zones.select_related("korwil"):
        yield aset_geo.feature(
            zone.geometry,
            {
                "id": zone.pk,
                "kind": "ancaman",
                "level": zone.level,
                "title": f"⚠ {zone.name}",
                "color": enums.THREAT_COLORS.get(zone.level, "#f59e0b"),
                "rows": [
                    [_("Tingkat"), zone.get_level_display()],
                    [_("Korwil"), zone.korwil.code if zone.korwil_id else "-"],
                    [_("Keterangan"), zone.note[:300] or "-"],
                ],
            },
        )


def _photo_json(photo) -> dict:
    return {
        "id": photo.pk,
        "title": photo.title,
        "korwil": photo.korwil.code if photo.korwil_id else "",
        "captured_on": photo.captured_on.isoformat() if photo.captured_on else "",
        "uploaded_by": _name(photo.uploaded_by) if photo.uploaded_by_id else "-",
        "created_at": _local(photo.created_at),
        "note": photo.note,
        "lat": photo.location.y,
        "lng": photo.location.x,
        "url": file_url("foto-360", photo) + "?lihat=1",
    }


def _photo_features(request):
    photos = geo.scoped(SitePhoto360.objects.all(), request.user).select_related(
        "korwil", "uploaded_by"
    )
    for photo in photos[:2000]:
        data = _photo_json(photo)
        yield aset_geo.feature(
            photo.location,
            {
                "id": photo.pk,
                "kind": "foto360",
                "title": f"◉ {photo.title}",
                "color": "#0ea5e9",
                "photo360": data["url"],
                "rows": [
                    [_("Korwil"), data["korwil"] or "-"],
                    [_("Tanggal"), data["captured_on"] or "-"],
                    [_("Diunggah oleh"), data["uploaded_by"]],
                ],
            },
        )


def _overlay_color(properties: dict, default: str) -> str:
    for key in ("color", "warna", "fill", "stroke"):
        value = str((properties or {}).get(key, "")).strip()
        if HEX.match(value):
            return value
    return default


def _zoned(overlay) -> bool:
    """Lapisan tata ruang tanpa warna khusus diwarnai per zona."""
    return overlay.kind == aset_enums.OverlayKind.SPATIAL_PLAN and not overlay.color


def overlay_features(pk: int):
    overlay = get_object_or_404(spatial.command_overlays(), pk=pk)
    zoned = _zoned(overlay)
    for item in overlay.features.all()[:20000]:
        rows = [[str(k), str(v)] for k, v in list(item.properties.items())[:12]]
        zone = spatial.feature_zone(overlay.kind, item.name, item.properties)
        color = overlay.display_color
        if zone:
            rows.insert(0, [_("Zona"), str(enums.RtrwZone(zone).label)])
            if zoned:
                color = enums.RTRW_ZONE_COLORS.get(zone, color)
        yield aset_geo.feature(
            item.geometry,
            {
                "kind": "referensi",
                "title": item.name or overlay.name,
                "color": _overlay_color(item.properties, color),
                "rows": rows,
            },
        )


LAYERS = {
    "bidang": ("operasi.view_landplot", _plot_features),
    "ancaman": ("operasi.view_threatzone", _threat_features),
    "foto360": ("operasi.view_sitephoto360", _photo_features),
}


def command_layers() -> list[dict]:
    return [
        {
            "key": f"ref-{overlay.pk}",
            "name": overlay.name,
            "kind": overlay.get_kind_display(),
            "color": overlay.display_color,
            "zoned": _zoned(overlay),
            "visible": overlay.show_by_default,
        }
        for overlay in spatial.command_overlays()
    ]


# --------------------------------------------------------------------------
# Bidang penguasaan
# --------------------------------------------------------------------------


@api(permission="operasi.view_landplot")
def plots(request):
    queryset = spatial.visible_plots(request.user).select_related("korwil", "resident")
    korwil = _visible_korwil(request)
    if korwil is not None:
        queryset = queryset.filter(korwil=korwil)
    status = request.GET.get("status", "")
    if status in enums.ControlStatus.values:
        queryset = queryset.filter(control_status=status)
    q = request.GET.get("q", "").strip()[:100]
    if q:
        queryset = queryset.filter(
            Q(number__icontains=q)
            | Q(name__icontains=q)
            | Q(owner_name__icontains=q)
            | Q(guard_name__icontains=q)
        )
    total = queryset.count()
    rows = spatial.plot_rows(queryset.order_by("number")[:MAX_PLOT_ROWS])
    order = request.GET.get("urut", "skor")
    if order == "skor":
        rows.sort(
            key=lambda r: (r["status"] == enums.ControlStatus.CONTROLLED, -r["score"])
        )
    elif order == "luas":
        rows.sort(key=lambda r: -r["area_ha"])
    return JsonResponse(
        {
            "rows": rows,
            "summary": spatial.plot_summary(rows),
            "total": total,
            "truncated": total > MAX_PLOT_ROWS,
            "can_add": request.user.has_perm("operasi.add_landplot"),
            "can_change": request.user.has_perm("operasi.change_landplot"),
        }
    )


def _can_change_plot(user, plot) -> bool:
    """Bidang yang terlihat (sudah dibatasi Korwil) boleh diubah pemegang izin ubah."""
    return user.has_perm("operasi.change_landplot")


@api(permission="operasi.view_landplot", methods=("GET", "POST"))
def plot_detail(request, pk):
    plot = get_object_or_404(
        spatial.visible_plots(request.user).select_related("korwil", "resident"),
        pk=pk,
    )
    if request.method == "POST":
        if not _can_change_plot(request.user, plot):
            raise PermissionDenied
        data = request.POST
        urgency = data.get("urgensi", "")
        with transaction.atomic():
            plot = LandPlot.objects.select_for_update().get(pk=plot.pk)
            if urgency:
                if urgency not in enums.PlotUrgency.values:
                    raise ValidationError({"urgensi": [_("Urgensi tidak dikenal.")]})
                if urgency != plot.urgency:
                    plot.urgency = urgency
                    plot.save(update_fields=["urgency", "modified_at"])
            status = data.get("status", "")
            if status:
                spatial.set_control_status(
                    plot,
                    request.user,
                    status,
                    note=data.get("catatan", ""),
                    controlled_on=_date(data.get("tanggal"), "tanggal"),
                    team=data.get("tim") if "tim" in data else None,
                )
        plot = LandPlot.objects.select_related("korwil", "resident").get(pk=plot.pk)
    row = spatial.plot_rows([plot])[0]
    row["overlaps"] = spatial.plot_overlaps(plot)
    row["official_ha"] = (
        float(plot.official_area_ha) if plot.official_area_ha is not None else None
    )
    row["measured_ha"] = (
        float(plot.measured_area_ha) if plot.measured_area_ha is not None else None
    )
    row["source"] = plot.source
    row["history"] = [
        {
            "time": _local(change.changed_at),
            "old": change.get_old_status_display() if change.old_status else "",
            "new": change.get_new_status_display(),
            "by": _name(change.changed_by) if change.changed_by_id else "-",
            "note": change.note,
        }
        for change in plot.changes.select_related("changed_by")[:50]
    ]
    row["geometry"] = json.loads(plot.geometry.geojson)
    row["can_change"] = _can_change_plot(request.user, plot)
    row["admin"] = (
        reverse("admin:operasi_landplot_change", args=[plot.pk])
        if request.user.has_perm("operasi.change_landplot")
        else ""
    )
    return JsonResponse(row)


def _import_items(request):
    upload = request.FILES.get("berkas")
    if upload is None:
        raise ValidationError({"berkas": [_("Pilih berkas KML/KMZ/GeoJSON.")]})
    if upload.size > MAX_IMPORT_BYTES:
        raise ValidationError({"berkas": [_("Berkas maksimal 20 MB.")]})
    name = os.path.basename(upload.name or "impor")
    return name, spatial.read_plot_file(upload.read(), name)


@api(permission="operasi.add_landplot", methods=("POST",))
def plot_import(request):
    """Impor dua langkah: ``pratinjau`` mengklasifikasi, ``terapkan`` menyimpan."""
    mode = request.POST.get("mode", "baru")
    if mode not in ("baru", "penguasaan"):
        raise ValidationError({"mode": [_("Mode impor tidak dikenal.")]})
    if mode == "penguasaan" and not request.user.has_perm("operasi.change_landplot"):
        raise PermissionDenied
    name, items = _import_items(request)
    if request.POST.get("tahap") != "terapkan":
        data = spatial.preview_import(request.user, items, mode)
        data["file"] = name
        return JsonResponse(data)
    selected = []
    for part in request.POST.get("pilih", "").split(","):
        if part.strip().isdigit():
            selected.append(int(part))
    if not selected:
        raise ValidationError({"pilih": [_("Pilih minimal satu objek.")]})
    urgency = request.POST.get("urgensi") or enums.PlotUrgency.LOW
    if urgency not in enums.PlotUrgency.values:
        raise ValidationError({"urgensi": [_("Urgensi tidak dikenal.")]})
    result = spatial.apply_import(
        request.user,
        items,
        mode,
        selected,
        korwil=_visible_korwil(request),
        controlled_on=_date(request.POST.get("tanggal"), "tanggal"),
        team=request.POST.get("tim", "")[:255],
        urgency=urgency,
        source=name,
    )
    return JsonResponse(result)


# --------------------------------------------------------------------------
# Analisis
# --------------------------------------------------------------------------


@api()
def overlap(request):
    if "a" not in request.GET:
        return JsonResponse({"sources": spatial.overlap_sources(request.user)})
    data = spatial.overlap(
        request.user, request.GET.get("a", ""), request.GET.get("b", "")
    )
    if request.GET.get("format") == "csv":
        return _csv(spatial.overlap_csv(data), "tumpang-tindih.csv")
    return JsonResponse(data)


@api(permission="operasi.view_resident")
def rtrw_audit(request):
    data = spatial.rtrw_audit(request.user, _visible_korwil(request))
    if request.GET.get("format") == "csv":
        return _csv(spatial.audit_csv(data), "audit-rtrw.csv")
    return JsonResponse(data)


@api()
def anomalies(request):
    return JsonResponse(spatial.anomalies(request.user))


@api()
def heatmap(request):
    period = request.GET.get("periode") or "bulan"
    if period not in services.PERIODS:
        period = "bulan"
    start, end = services.period_bounds(period)
    return JsonResponse(
        spatial.heat_cells(request.user, request.GET.get("sumber", ""), start, end)
    )


@api(permission="operasi.view_officertrackpoint")
def track(request):
    day = _date(request.GET.get("tanggal"), "tanggal") or timezone.localdate()
    officers = services.visible_officers(request.user)
    value = request.GET.get("petugas", "")
    data = {}
    if str(value).isdigit():
        data = spatial.track(get_object_or_404(officers, pk=value), day)
    with_track = (
        OfficerTrackPoint.objects.filter(recorded_at__date=day, user__in=officers)
        .order_by()
        .values_list("user", flat=True)
        .distinct()
    )
    data["officers"] = [
        {"id": user.pk, "name": _name(user)}
        for user in officers.filter(pk__in=with_track).order_by(
            "first_name", "username"
        )
    ]
    data["date"] = day.isoformat()
    return JsonResponse(data)


# --------------------------------------------------------------------------
# Zona ancaman
# --------------------------------------------------------------------------


def _zone_json(zone, user) -> dict:
    return {
        "id": zone.pk,
        "name": zone.name,
        "level": zone.level,
        "level_label": zone.get_level_display(),
        "color": enums.THREAT_COLORS.get(zone.level, "#f59e0b"),
        "korwil": zone.korwil.code if zone.korwil_id else "",
        "active": zone.is_active,
        "note": zone.note,
        "by": _name(zone.created_by) if zone.created_by_id else "-",
        "created_at": _local(zone.created_at),
        "area_ha": float((aset_geo.area_m2(zone.geometry) or 0) / Decimal("10000")),
        "center": [zone.geometry.point_on_surface.y, zone.geometry.point_on_surface.x],
        "can_change": _can_change_zone(user, zone),
        "can_delete": user.has_perm("operasi.delete_threatzone")
        and _can_change_zone(user, zone, "delete"),
    }


def _can_change_zone(user, zone, action="change") -> bool:
    if not user.has_perm(f"operasi.{action}_threatzone"):
        return False
    if geo.is_supervisor(user) or zone.created_by_id == user.pk:
        return True
    return bool(zone.korwil_id and zone.korwil.coordinator_id == user.pk)


@api(permission="operasi.view_threatzone", methods=("GET", "POST"))
def threat_zones(request):
    user = request.user
    if request.method == "POST":
        if not user.has_perm("operasi.add_threatzone"):
            raise PermissionDenied
        data = request.POST
        name = data.get("name", "").strip()[:255]
        if not name:
            raise ValidationError({"name": [_("Nama zona wajib diisi.")]})
        level = data.get("level", enums.ThreatLevel.MEDIUM)
        if level not in enums.ThreatLevel.values:
            raise ValidationError({"level": [_("Tingkat ancaman tidak dikenal.")]})
        geometry = spatial.threat_geometry(data)
        korwil = _visible_korwil(request) or geo.korwil_for_write(
            user, geometry.point_on_surface
        )
        zone = ThreatZone.objects.create(
            name=name,
            level=level,
            geometry=geometry,
            korwil=korwil,
            note=data.get("note", "")[:2000],
            created_by=user,
        )
        return JsonResponse(_zone_json(zone, user), status=201)
    zones = geo.scoped(ThreatZone.objects.all(), user).select_related(
        "korwil", "created_by"
    )
    if request.GET.get("semua") != "1":
        zones = zones.filter(is_active=True)
    return JsonResponse({"zones": [_zone_json(z, user) for z in zones[:500]]})


@api(permission="operasi.view_threatzone", methods=("POST",))
def threat_zone_action(request, pk, action):
    zone = get_object_or_404(
        geo.scoped(ThreatZone.objects.select_related("korwil"), request.user), pk=pk
    )
    if action in ("nonaktif", "aktif"):
        if not _can_change_zone(request.user, zone):
            raise PermissionDenied
        zone.is_active = action == "aktif"
        zone.save(update_fields=["is_active", "modified_at"])
        return JsonResponse(_zone_json(zone, request.user))
    if action == "hapus":
        if not _can_change_zone(request.user, zone, "delete"):
            raise PermissionDenied
        zone.delete()
        return JsonResponse({"deleted": True})
    raise ValidationError(_("Tindakan tidak dikenal."))


# --------------------------------------------------------------------------
# Foto situs 360°
# --------------------------------------------------------------------------


def _can_delete_photo(user, photo) -> bool:
    if not user.has_perm("operasi.delete_sitephoto360"):
        return False
    if geo.is_supervisor(user) or photo.uploaded_by_id == user.pk:
        return True
    return bool(photo.korwil_id and photo.korwil.coordinator_id == user.pk)


@api(permission="operasi.view_sitephoto360", methods=("GET", "POST"))
def site_photos(request):
    user = request.user
    if request.method == "POST":
        if not user.has_perm("operasi.add_sitephoto360"):
            raise PermissionDenied
        data = request.POST
        image = request.FILES.get("foto")
        if image is None:
            raise ValidationError({"foto": [_("Pilih foto 360°.")]})
        if image.size > MAX_PHOTO_BYTES:
            raise ValidationError({"foto": [_("Foto maksimal 20 MB.")]})
        location = _parse_location(data)
        if location is None:
            raise ValidationError({"location": [_("Lokasi foto wajib diisi.")]})
        title = data.get("title", "").strip()[:255]
        if not title:
            raise ValidationError({"title": [_("Judul wajib diisi.")]})
        korwil = _visible_korwil(request) or geo.korwil_for_write(user, location)
        photo = SitePhoto360(
            title=title,
            korwil=korwil,
            location=location,
            captured_on=_date(data.get("tanggal"), "tanggal"),
            image=image,
            uploaded_by=user,
            note=data.get("note", "")[:2000],
        )
        photo.full_clean()
        photo.save()
        return JsonResponse(
            {**_photo_json(photo), "can_delete": _can_delete_photo(user, photo)},
            status=201,
        )
    photos = geo.scoped(SitePhoto360.objects.all(), user).select_related(
        "korwil", "uploaded_by"
    )
    return JsonResponse(
        {
            "photos": [
                {**_photo_json(p), "can_delete": _can_delete_photo(user, p)}
                for p in photos[:300]
            ]
        }
    )


@api(permission="operasi.delete_sitephoto360", methods=("POST",))
def site_photo_delete(request, pk):
    photo = get_object_or_404(
        geo.scoped(SitePhoto360.objects.select_related("korwil"), request.user), pk=pk
    )
    if not _can_delete_photo(request.user, photo):
        raise PermissionDenied
    photo.delete()
    return JsonResponse({"deleted": True})


def config(user) -> dict:
    """Bagian konfigurasi /komando/ untuk fitur spasial."""
    return {
        "perms": {
            "bidang": user.has_perm("operasi.view_landplot"),
            "tambahBidang": user.has_perm("operasi.add_landplot"),
            "ubahBidang": user.has_perm("operasi.change_landplot"),
            "ancaman": user.has_perm("operasi.view_threatzone"),
            "tambahAncaman": user.has_perm("operasi.add_threatzone"),
            "foto360": user.has_perm("operasi.view_sitephoto360"),
            "tambahFoto360": user.has_perm("operasi.add_sitephoto360"),
            "jejak": user.has_perm("operasi.view_officertrackpoint"),
        },
        "urls": {
            "plots": reverse("operasi-plots"),
            "plot": reverse("operasi-plot", args=[0]),
            "plotImport": reverse("operasi-plot-import"),
            "overlap": reverse("operasi-overlap"),
            "rtrwAudit": reverse("operasi-rtrw-audit"),
            "anomalies": reverse("operasi-anomalies"),
            "heatmap": reverse("operasi-heatmap"),
            "track": reverse("operasi-track"),
            "threatZones": reverse("operasi-threat-zones"),
            "threatZoneAction": reverse(
                "operasi-threat-zone-action", args=[0, "__aksi__"]
            ),
            "sitePhotos": reverse("operasi-site-photos"),
            "sitePhotoDelete": reverse("operasi-site-photo-delete", args=[0]),
        },
        "choices": {
            "control": [
                {"value": str(v), "label": str(label)}
                for v, label in enums.ControlStatus.choices
            ],
            "urgency": [
                {"value": str(v), "label": str(label)}
                for v, label in enums.PlotUrgency.choices
            ],
            "threat": [
                {"value": str(v), "label": str(label)}
                for v, label in enums.ThreatLevel.choices
            ],
        },
        "colors": {
            "control": {str(k): v for k, v in enums.CONTROL_COLORS.items()},
            "threat": {str(k): v for k, v in enums.THREAT_COLORS.items()},
            "zone": {str(k): v for k, v in enums.RTRW_ZONE_COLORS.items()},
        },
        "commandLayers": command_layers(),
    }
