"""Halaman publik /aset/: peta berbagi baca-saja dan aplikasi petugas lapangan (PWA).

Aplikasi lapangan dapat dipasang di ponsel (Android/iOS) dari peramban,
bekerja luring (batas bidang & antrean laporan disimpan di perangkat), dan
menyinkronkan laporan saat sinyal kembali. Sinkronisasi idempoten lewat
``client_id`` sehingga pengiriman ulang tidak membuat laporan ganda.
"""

import datetime
import json
import uuid

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from alokasi.templatetags.alokasi_tags import angka
from asetlahan import enums, geo, scope
from asetlahan.models import EncroachmentCase, FieldReport, LandAsset, MapShare

MAX_FEATURES = 5000
SW_VERSION = "1"

# --------------------------------------------------------------------------
# Peta berbagi (tautan publik baca-saja)
# --------------------------------------------------------------------------


def _valid_share(token) -> MapShare:
    share = get_object_or_404(MapShare, token=token)
    if not share.is_valid:
        raise Http404
    return share


@require_GET
def shared_map(request, token):
    share = _valid_share(token)
    MapShare.objects.filter(pk=share.pk).update(view_count=F("view_count") + 1)
    config = {
        "center": [settings.MAP_CENTER_LAT, settings.MAP_CENTER_LNG],
        "zoom": settings.MAP_DEFAULT_ZOOM,
        "data": reverse("asetlahan-share-data", args=[share.token]),
    }
    legend = []
    if share.assets.exists():
        labels = dict(enums.AssetStatus.choices)
        legend += [
            {"label": labels[key], "color": color}
            for key, color in enums.ASSET_STATUS_COLORS.items()
        ]
    if share.pengadaan_project_id:
        legend += [
            {"label": _("Bidang pengadaan"), "color": "#8250df"},
            {"label": _("Bidang sengketa"), "color": "#bf3989"},
        ]
    if share.resettlement_site_id:
        labels = dict(enums.ResettlementUnitStatus.choices)
        legend += [
            {"label": labels[key], "color": color}
            for key, color in enums.RESETTLEMENT_COLORS.items()
        ]
    response = render(
        request,
        "asetlahan/share_map.html",
        {"share": share, "map_config": config, "legend": legend},
    )
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _share_asset_features(share):
    for asset in share.assets.exclude(geometry__isnull=True)[:MAX_FEATURES]:
        rows = [
            [_("Status"), asset.get_status_display()],
            [_("Luas"), f"{angka(asset.area_m2 or 0, 2)} m²"],
            [
                _("Alas hak"),
                f"{asset.get_title_type_display()} {asset.title_number}".strip(),
            ],
        ]
        if share.show_owner_names and asset.registered_owner:
            rows.append([_("Pemegang hak"), asset.registered_owner])
        yield geo.feature(
            asset.geometry,
            {
                "title": f"{asset.code} – {asset.name}",
                "color": asset.status_color,
                "rows": rows,
            },
        )


def _share_parcel_features(share):
    from pengadaan.enums import PartyRole
    from pengadaan.models import AcquisitionParcel

    parcels = AcquisitionParcel.objects.filter(
        project_id=share.pengadaan_project_id
    ).exclude(geometry__isnull=True)
    for parcel in parcels.prefetch_related("parties")[:MAX_FEATURES]:
        rows = [
            [_("Status"), parcel.get_status_display()],
            [_("Luas terkena"), f"{angka(parcel.affected_area_m2 or 0, 2)} m²"],
        ]
        if share.show_owner_names:
            owners = [p.name for p in parcel.parties.all() if p.role == PartyRole.OWNER]
            if owners:
                rows.append([_("Pihak yang berhak"), ", ".join(owners)])
        yield geo.feature(
            parcel.geometry,
            {
                "title": _("Bidang %s") % parcel.parcel_number,
                "color": "#bf3989" if parcel.is_disputed else "#8250df",
                "rows": rows,
            },
        )


def _share_resettlement_features(share):
    site = share.resettlement_site
    yield geo.feature(
        site.geometry,
        {"title": site.name, "color": "#0969da", "outline": True, "rows": []},
    )
    for unit in site.units.exclude(geometry__isnull=True).select_related("household")[
        :MAX_FEATURES
    ]:
        rows = [
            [_("Status"), unit.get_status_display()],
            [_("Tipe"), unit.house_type or "-"],
        ]
        if share.show_owner_names and unit.household_id:
            rows.append([_("Kepala keluarga"), unit.household.head_name])
        yield geo.feature(
            unit.geometry,
            {
                "title": _("Kavling %s") % unit.unit_number,
                "color": enums.RESETTLEMENT_COLORS.get(unit.status, "#57606a"),
                "rows": rows,
            },
        )


@require_GET
def shared_map_data(request, token):
    share = _valid_share(token)
    features = list(_share_asset_features(share))
    if share.pengadaan_project_id:
        features.extend(_share_parcel_features(share))
    if share.resettlement_site_id:
        features.extend(_share_resettlement_features(share))
    response = JsonResponse(geo.collection(features))
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


# --------------------------------------------------------------------------
# Aplikasi petugas lapangan (PWA)
# --------------------------------------------------------------------------


def _field_user(request):
    if not request.user.has_perm("asetlahan.add_fieldreport"):
        return render(request, "asetlahan/field_forbidden.html", status=403)
    return None


@never_cache
@staff_member_required
def field_app(request):
    denied = _field_user(request)
    if denied:
        return denied
    config = {
        "center": [settings.MAP_CENTER_LAT, settings.MAP_CENTER_LNG],
        "zoom": settings.MAP_DEFAULT_ZOOM,
        "boundaries": reverse("asetlahan-field-boundaries"),
        "sync": reverse("asetlahan-field-sync"),
        "serviceWorker": reverse("asetlahan-field-sw"),
        "scope": reverse("asetlahan-field"),
        "login": reverse("admin:login") + "?next=" + reverse("asetlahan-field"),
        "reportTypes": [
            {"value": value, "label": str(label)}
            for value, label in enums.FieldReportType.choices
        ],
        "user": request.user.get_full_name() or request.user.get_username(),
    }
    return render(request, "asetlahan/field_app.html", {"field_config": config})


@require_GET
def field_manifest(request):
    start = reverse("asetlahan-field")
    manifest = {
        "name": _("SimLahan Lapangan"),
        "short_name": _("Lapangan"),
        "description": _(
            "Patroli, temuan okupasi, dan foto lapangan, termasuk saat tanpa sinyal."
        ),
        "start_url": start,
        "scope": start,
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#ffffff",
        "theme_color": "#0b4f8a",
        "lang": "id",
        "icons": [
            {
                "src": static("asetlahan/field-icon.svg"),
                "sizes": "any",
                "type": "image/svg+xml",
                "purpose": "any",
            },
            {
                "src": static("asetlahan/field-icon-192.png"),
                "sizes": "192x192",
                "type": "image/png",
            },
            {
                "src": static("asetlahan/field-icon-512.png"),
                "sizes": "512x512",
                "type": "image/png",
            },
        ],
    }
    return HttpResponse(json.dumps(manifest), content_type="application/manifest+json")


@require_GET
def field_service_worker(request):
    shell = [
        reverse("asetlahan-field"),
        reverse("asetlahan-field-manifest"),
        static("asetlahan/field.js"),
        static("asetlahan/field.css"),
        static("asetlahan/field-icon.svg"),
        static("alokasi/vendor/leaflet/leaflet.js"),
        static("alokasi/vendor/leaflet/leaflet.css"),
        static("alokasi/vendor/leaflet/images/marker-icon.png"),
        static("alokasi/vendor/leaflet/images/marker-shadow.png"),
    ]
    body = render(
        request,
        "asetlahan/field_sw.js",
        {
            "shell": json.dumps(shell),
            "boundaries": json.dumps(reverse("asetlahan-field-boundaries")),
            "version": json.dumps(SW_VERSION),
        },
        content_type="application/javascript",
    ).content
    response = HttpResponse(body, content_type="application/javascript; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    return response


@require_GET
@staff_member_required
def field_boundaries(request):
    denied = _field_user(request)
    if denied:
        return denied
    assets = scope.scoped(
        LandAsset.objects.exclude(geometry__isnull=True), request.user
    )
    features = [
        geo.feature(
            asset.geometry,
            {
                "id": asset.pk,
                "title": f"{asset.code} – {asset.name}",
                "color": asset.status_color,
                "kind": "aset",
                "rows": [
                    [_("Status"), asset.get_status_display()],
                    [_("Luas"), f"{angka(asset.area_m2 or 0, 2)} m²"],
                ],
            },
        )
        for asset in assets[:MAX_FEATURES]
    ]
    cases = scope.scoped(
        EncroachmentCase.objects.filter(status__in=enums.OPEN_ENCROACHMENT_STATUSES),
        request.user,
    )
    features.extend(
        geo.feature(
            case.area_geometry or case.location,
            {
                "title": f"{case.number} {case.title}",
                "color": "#cf222e",
                "kind": "okupasi",
                "rows": [[_("Status"), case.get_status_display()]],
            },
        )
        for case in cases.exclude(area_geometry__isnull=True, location__isnull=True)[
            :MAX_FEATURES
        ]
    )
    response = JsonResponse(geo.collection(features))
    response["Cache-Control"] = "private, no-cache"
    return response


def _parse_location(data):
    try:
        lat, lng = float(data.get("lat", "")), float(data.get("lng", ""))
    except ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return Point(lng, lat, srid=4326)


def _parse_captured_at(value):
    now = timezone.now()
    captured_at = parse_datetime(value or "") or now
    if timezone.is_naive(captured_at):
        captured_at = timezone.make_aware(captured_at)
    # Jam perangkat yang terlalu maju tidak boleh menghasilkan waktu di masa depan.
    return min(captured_at, now + datetime.timedelta(minutes=10))


def _parse_accuracy(value):
    try:
        accuracy = round(float(value), 1) if value else None
    except ValueError:
        return None
    return accuracy if accuracy is not None and 0 <= accuracy < 10_000_000 else None


def _parse_report(request):
    data = request.POST
    errors = {}
    try:
        client_id = uuid.UUID(data.get("client_id", ""))
    except ValueError:
        client_id = None
        errors["client_id"] = _("ID perangkat tidak sah.")
    location = _parse_location(data)
    if location is None:
        errors["location"] = _("Lokasi GPS tidak sah.")
    report_type = data.get("report_type") or enums.FieldReportType.PATROL
    if report_type not in enums.FieldReportType.values:
        errors["report_type"] = _("Jenis laporan tidak dikenal.")
    values = {
        "client_id": client_id,
        "report_type": report_type,
        "captured_at": _parse_captured_at(data.get("captured_at")),
        "location": location,
        "accuracy_m": _parse_accuracy(data.get("accuracy")),
        "note": (data.get("note") or "")[:5000],
    }
    return values, errors


@require_POST
@staff_member_required
def field_sync(request):
    if not request.user.has_perm("asetlahan.add_fieldreport"):
        return JsonResponse(
            {"error": _("Tidak berhak mengirim laporan lapangan.")}, status=403
        )
    values, errors = _parse_report(request)
    if errors:
        return JsonResponse({"errors": errors}, status=400)
    existing = FieldReport.objects.filter(client_id=values["client_id"]).first()
    if existing is not None:
        return JsonResponse({"id": existing.pk, "duplicate": True})
    report = FieldReport(**values, reported_by=request.user)
    if request.FILES.get("photo"):
        report.photo = request.FILES["photo"]
    try:
        report.full_clean(
            exclude=["asset", "service_unit", "encroachment", "reported_by"],
            validate_unique=False,
        )
        report.asset = geo.asset_at(report.location)
        if report.asset is None:
            report.service_unit = scope.default_unit(request.user)
        with transaction.atomic():
            report.save()
    except ValidationError as error:
        return JsonResponse({"errors": error.message_dict}, status=400)
    except IntegrityError:
        existing = FieldReport.objects.get(client_id=values["client_id"])
        return JsonResponse({"id": existing.pk, "duplicate": True})
    return JsonResponse(
        {"id": report.pk, "duplicate": False, "asset": str(report.asset or "")},
        status=201,
    )
