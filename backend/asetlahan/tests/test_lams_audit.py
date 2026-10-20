"""Fitur hasil audit LAMS: pemantauan berkala, lapisan referensi, impor 3D,
jenis citra & urusan instansi, dan asisten (zona, pemantauan, unduhan)."""

import datetime
import io
import json
import uuid

import pytest
from django.contrib.gis.geos import GEOSGeometry, Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from asetlahan import assistant, enums, geo, importers, monitoring
from asetlahan.models import (
    EncroachmentCase,
    FieldReport,
    LandAsset,
    LiaisonActivity,
    MapOverlay,
    ModuleSettings,
    SatelliteImage,
)
from utils.geometry import force_2d

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate


def _ago(days):
    return TODAY() - datetime.timedelta(days=days)


# --------------------------------------------------------------------------
# Pemantauan lapangan berkala
# --------------------------------------------------------------------------


def test_monitoring_overdue_uses_default_and_asset_interval(make_asset):
    stale = make_asset(acquisition_date=_ago(200))
    fresh = make_asset(acquisition_date=_ago(10))
    custom = make_asset(acquisition_date=_ago(40), monitoring_interval_days=30)
    off = make_asset(acquisition_date=_ago(400), monitoring_interval_days=0)
    released = make_asset(acquisition_date=_ago(400), status=enums.AssetStatus.RELEASED)
    overdue = list(monitoring.monitoring_overdue(default_days=90))
    assert stale in overdue and custom in overdue
    assert fresh not in overdue and off not in overdue and released not in overdue
    row = next(a for a in overdue if a.pk == stale.pk)
    assert row.monitoring_due == stale.monitoring_due_on(90) == _ago(110)
    assert (
        monitoring.monitoring_overdue(default_days=0).filter(pk=stale.pk).count() == 0
    )
    assert released.monitoring_due_on(90) is None
    assert off.monitoring_due_on(90) is None


def test_field_report_updates_last_monitored(make_asset):
    asset = make_asset(acquisition_date=_ago(200))
    assert asset in monitoring.monitoring_overdue(default_days=90)
    FieldReport.objects.create(
        client_id=uuid.uuid4(),
        location=asset.geometry.centroid,
        captured_at=timezone.now(),
        asset=asset,
    )
    asset.refresh_from_db()
    assert asset.last_monitored_on == TODAY()
    assert asset not in monitoring.monitoring_overdue(default_days=90)
    # Laporan susulan yang lebih lama tidak memundurkan tanggal pantau.
    FieldReport.objects.create(
        client_id=uuid.uuid4(),
        location=asset.geometry.centroid,
        captured_at=timezone.now() - datetime.timedelta(days=30),
        asset=asset,
    )
    asset.refresh_from_db()
    assert asset.last_monitored_on == TODAY()


def test_monitoring_in_reminder_dashboard_and_assistant(admin, make_asset, settings):
    settings.ANTHROPIC_API_KEY = ""
    asset = make_asset(acquisition_date=_ago(200))
    out = io.StringIO()
    call_command("asetlahan_pengingat", stdout=out)
    assert f"[PEMANTAUAN] {asset.code}" in out.getvalue()

    labels = {a["label"]: a["count"] for a in monitoring.alerts(admin)}
    assert labels["Aset belum dipantau sesuai jadwal"] == 1

    result = assistant.answer(admin, "aset mana yang belum dipantau?")
    assert asset.code in str(result["tables"])


def test_monitoring_settings_and_asset_admin(client, admin, make_asset):
    config = ModuleSettings.load()
    config.monitoring_interval_days = 30
    config.save()
    asset = make_asset(acquisition_date=_ago(45))
    assert asset in monitoring.monitoring_overdue()
    client.force_login(admin)
    page = client.get(reverse("admin:asetlahan_landasset_change", args=[asset.pk]))
    assert page.status_code == 200
    assert "terlambat" in page.content.decode()
    settings_page = client.get(
        reverse("admin:asetlahan_modulesettings_change", args=[config.pk])
    )
    assert settings_page.status_code == 200


# --------------------------------------------------------------------------
# Lapisan peta referensi
# --------------------------------------------------------------------------

OVERLAY = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"nama": "Sungai Rempang", "orde": 2},
            "geometry": {
                "type": "LineString",
                "coordinates": [[104.1, 0.8, 5.0], [104.12, 0.81, 4.0]],
            },
        },
        {
            "type": "Feature",
            "properties": {"name": "Kantor Kelurahan"},
            "geometry": {"type": "Point", "coordinates": [104.11, 0.805]},
        },
        {
            "type": "Feature",
            "properties": {"nama": "Batas Kelurahan", "kosong": None},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [104.1, 0.8],
                        [104.2, 0.8],
                        [104.2, 0.9],
                        [104.1, 0.9],
                        [104.1, 0.8],
                    ]
                ],
            },
        },
    ],
}


def _overlay_upload():
    return SimpleUploadedFile("sungai.geojson", json.dumps(OVERLAY).encode())


def test_overlay_admin_import_and_map_layer(client, admin, field_officer):
    client.force_login(admin)
    response = client.post(
        reverse("admin:asetlahan_mapoverlay_add"),
        {
            "name": "Sungai & batas",
            "kind": enums.OverlayKind.WATER,
            "color": "",
            "source": "Peta RBI",
            "is_active": "on",
            "show_by_default": "on",
            "import_file": _overlay_upload(),
            "note": "",
        },
    )
    assert response.status_code == 302, response.content.decode()[:2000]
    overlay = MapOverlay.objects.get()
    assert overlay.features.count() == 3
    assert not any(f.geometry.hasz for f in overlay.features.all())
    names = set(overlay.features.values_list("name", flat=True))
    assert names == {"Sungai Rempang", "Kantor Kelurahan", "Batas Kelurahan"}
    assert "kosong" not in overlay.features.get(name="Batas Kelurahan").properties

    changelist = client.get(reverse("admin:asetlahan_mapoverlay_changelist"))
    assert (
        changelist.status_code == 200
        and "Sungai &amp; batas" in changelist.content.decode()
    )

    # Petugas lapangan boleh melihat lapisan referensi di peta tematik.
    client.force_login(field_officer)
    page = client.get(reverse("asetlahan-map"))
    assert page.status_code == 200
    assert f"ref-{overlay.pk}" in page.content.decode()
    data = client.get(reverse("asetlahan-map-layer", args=[f"ref-{overlay.pk}"]))
    assert data.status_code == 200
    features = data.json()["features"]
    assert len(features) == 3
    assert features[0]["properties"]["color"] == enums.OVERLAY_COLORS["perairan"]

    overlay.is_active = False
    overlay.save()
    hidden = client.get(reverse("asetlahan-map-layer", args=[f"ref-{overlay.pk}"]))
    assert hidden.status_code == 404


def test_overlay_requires_file_and_rejects_bad_file(client, admin):
    client.force_login(admin)
    url = reverse("admin:asetlahan_mapoverlay_add")
    base = {"name": "Uji", "kind": enums.OverlayKind.ROAD, "color": "", "note": ""}
    response = client.post(url, base)
    assert response.status_code == 200
    assert "Unggah berkas peta" in response.content.decode()
    bad = SimpleUploadedFile("x.geojson", b"bukan json")
    response = client.post(url, {**base, "import_file": bad})
    assert response.status_code == 200
    assert not MapOverlay.objects.exists()
    response = client.post(
        url, {**base, "color": "merah", "import_file": _overlay_upload()}
    )
    assert "#RRGGBB" in response.content.decode()


def test_overlay_edit_keeps_features_without_new_file(client, admin):
    overlay = MapOverlay.objects.create(name="Jalan", kind=enums.OverlayKind.ROAD)
    importers.replace_overlay_features(
        overlay,
        importers.read_overlay_features(json.dumps(OVERLAY).encode(), "a.geojson"),
    )
    client.force_login(admin)
    response = client.post(
        reverse("admin:asetlahan_mapoverlay_change", args=[overlay.pk]),
        {
            "name": "Jalan utama",
            "kind": enums.OverlayKind.ROAD,
            "color": "#112233",
            "note": "",
        },
    )
    assert response.status_code == 302
    overlay.refresh_from_db()
    assert overlay.name == "Jalan utama" and overlay.features.count() == 3
    assert overlay.display_color == "#112233"


# --------------------------------------------------------------------------
# Koordinat 3D (KML/GPS) pada impor
# --------------------------------------------------------------------------

KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark>
<name>KML-1</name>
<Polygon><outerBoundaryIs><LinearRing><coordinates>
104.10,0.80,12 104.101,0.80,12 104.101,0.801,13 104.10,0.801,13 104.10,0.80,12
</coordinates></LinearRing></outerBoundaryIs></Polygon>
</Placemark></Document></kml>"""


def test_force_2d():
    geom = GEOSGeometry("POINT Z (104.1 0.8 12)", srid=4326)
    flat = force_2d(geom)
    assert not flat.hasz and flat.srid == 4326 and flat.coords == (104.1, 0.8)
    assert force_2d(None) is None
    point = Point(1, 2, srid=4326)
    assert force_2d(point) is point


def test_import_assets_with_z_coordinates(seeded):
    feature = {
        "type": "Feature",
        "properties": {"kode": "Z-1"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [104.1, 0.8, 3],
                    [104.101, 0.8, 3],
                    [104.101, 0.801, 3],
                    [104.1, 0.801, 3],
                    [104.1, 0.8, 3],
                ]
            ],
        },
    }
    data = json.dumps({"type": "FeatureCollection", "features": [feature]})
    assert importers.import_assets(data.encode(), filename="a.geojson") == (1, 0)
    assert importers.import_assets(KML.encode(), filename="b.kml")[0] == 1
    for asset in LandAsset.objects.all():
        assert not asset.geometry.hasz
    geom = geo.parse_geojson_geometry(json.dumps(feature["geometry"]))
    assert not geom.hasz


# --------------------------------------------------------------------------
# Citra & urusan instansi
# --------------------------------------------------------------------------


def test_imagery_types_and_liaison_types_in_admin(client, admin, make_asset):
    asset = make_asset()
    SatelliteImage.objects.create(
        title="Ortofoto drone 2026",
        coverage=asset.geometry,
        platform=enums.ImageryPlatform.DRONE,
        data_type=enums.ImageryType.LIDAR,
        gcp_count=8,
    )
    LiaisonActivity.objects.create(
        subject="Balik nama SHGB",
        agency="Kantor Pertanahan",
        activity_type=enums.LiaisonType.MUTATION,
        asset=asset,
    )
    client.force_login(admin)
    for name, filter_query, text in (
        ("satelliteimage", "data_type=lidar", "Ortofoto drone 2026"),
        ("liaisonactivity", "activity_type=balik_nama", "Balik nama SHGB"),
    ):
        url = reverse(f"admin:asetlahan_{name}_changelist") + "?" + filter_query
        page = client.get(url)
        assert page.status_code == 200
        assert text in page.content.decode()


# --------------------------------------------------------------------------
# Asisten: zona & unduhan laporan
# --------------------------------------------------------------------------


def test_assistant_filters_encroachment_by_zone(admin, make_asset, settings):
    settings.ANTHROPIC_API_KEY = ""
    industri = make_asset(zoning="Kawasan Industri Kabil")
    wisata = make_asset(zoning="Pariwisata")
    EncroachmentCase.objects.create(title="Pagar A", asset=industri)
    EncroachmentCase.objects.create(title="Pagar B", asset=wisata)
    result = assistant.answer(admin, "okupasi di zona industri")
    text = str(result["tables"])
    assert industri.code in text and wisata.code not in text


@pytest.mark.parametrize(
    "fmt,content_type",
    [
        ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("pdf", "application/pdf"),
        ("csv", "text/csv"),
    ],
)
def test_assistant_table_download(
    client, admin, make_asset, settings, fmt, content_type
):
    settings.ANTHROPIC_API_KEY = ""
    make_asset(acquisition_date=_ago(200))
    client.force_login(admin)
    client.post(reverse("asetlahan-assistant"), {"q": "aset belum dipantau"})
    page = client.get(reverse("asetlahan-assistant")).content.decode()
    url = reverse("asetlahan-assistant-export", args=[0, 0])
    assert url in page
    response = client.get(url, {"format": fmt})
    assert response.status_code == 200
    assert response["Content-Type"].startswith(content_type)
    assert "attachment" in response["Content-Disposition"]


def test_assistant_download_unknown_table_is_404(client, admin):
    client.force_login(admin)
    url = reverse("asetlahan-assistant-export", args=[3, 0])
    assert client.get(url).status_code == 404


def test_assistant_period_and_zone_parsing():
    assert (
        assistant._zone("okupasi di zona industri kabil bulan ini") == "industri kabil"
    )
    assert assistant._zone("okupasi terbaru") == ""
    assert assistant._allocation_period("alokasi maret 2025") == (2025, 3)
    assert assistant._allocation_period("alokasi tahun 2024") == (2024, None)
    assert assistant._allocation_period("alokasi bulan ini")[1] == TODAY().month


def test_import_assets_and_overlays_from_kmz(seeded, make_kmz):
    kmz = make_kmz([("Aset KMZ", {"kode": "KMZ-A"}), ("Tanpa kode", {})])
    assert importers.import_assets(kmz, filename="aset.kmz") == (2, 0)
    asset = LandAsset.objects.get(code="KMZ-A")
    assert asset.name == "Aset KMZ" and not asset.geometry.hasz
    features = importers.read_overlay_features(kmz, "lapisan.KMZ")
    assert [name for name, _geom, _props in features] == ["Aset KMZ", "Tanpa kode"]
    with pytest.raises(importers.AssetImportError, match="KMZ"):
        importers.import_assets(b"bukan zip", filename="aset.kmz")
