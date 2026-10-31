"""Peta & spasial pusat komando: penguasaan lahan, tumpang tindih, audit RTRW,
anomali, peta panas, jejak GPS, zona ancaman, dan foto situs 360°."""

import datetime
import json
from decimal import Decimal

import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from asetlahan.models import MapOverlay, MapOverlayFeature
from operasi import enums, spatial
from operasi.models import (
    LandPlot,
    LandPlotChange,
    OfficerPosition,
    OfficerTrackPoint,
    Resident,
    SitePhoto360,
    SosAlert,
    ThreatZone,
)
from operasi.tests.conftest import inside, login, make_user, png_bytes, square
from utils.group_permissions import UserGroup

pytestmark = pytest.mark.django_db

BASE = "/komando/api/"
Stance = enums.Stance


def box(x, y, size=0.002):
    return MultiPolygon(
        Polygon(((x, y), (x + size, y), (x + size, y + size), (x, y + size), (x, y))),
        srid=4326,
    )


def plot(korwil, x=104.102, y=0.802, size=0.002, **extra):
    return LandPlot.objects.create(
        korwil=korwil,
        geometry=box(x, y, size),
        name=extra.pop("name", "Bidang"),
        **extra,
    )


def overlay(name="RTRW", kind="tata_ruang", command=True):
    return MapOverlay.objects.create(name=name, kind=kind, show_in_command=command)


def geojson_file(*features, name="bidang.geojson"):
    data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": props,
                "geometry": json.loads(geom.geojson),
            }
            for props, geom in features
        ],
    }
    return SimpleUploadedFile(name, json.dumps(data).encode(), "application/geo+json")


@pytest.fixture
def asset_officer(seeded, units):
    return make_user("aset", UserGroup.PETUGAS_ASET, units=[units[0]])


# --------------------------------------------------------------------------
# Skor prioritas & zona
# --------------------------------------------------------------------------


def test_priority_score_uses_effective_area_zone_and_urgency():
    assert spatial.priority_score(2, "luar", "rendah") == 20.0
    # 9 ha → 5 + √4 = 7 ha efektif.
    assert spatial.priority_score(9, "inti", "mendesak") == 210.0
    assert spatial.priority_score(Decimal("1"), "penyangga", "tinggi") == 19.2
    assert spatial.priority_score(0, "inti", "mendesak") == 0


def test_feature_zone_reads_name_properties_and_kind():
    assert spatial.feature_zone("tata_ruang", "Zona Khusus", {}) == "khusus"
    assert (
        spatial.feature_zone("tata_ruang", "", {"NAMZON": "Hutan Lindung"}) == "lindung"
    )
    assert spatial.feature_zone("tata_ruang", "Kawasan Budi Daya", {}) == "budi_daya"
    assert spatial.feature_zone("hutan", "HL Rempang", {}) == "lindung"
    assert spatial.feature_zone("proyek", "Rencana kegiatan", {}) == "khusus"
    assert spatial.feature_zone("tata_ruang", "Permukiman", {}) == ""


def test_plot_zone_from_command_overlays_only(field, korwil):
    item = plot(korwil)
    hidden = overlay("Rahasia", "proyek", command=False)
    MapOverlayFeature.objects.create(overlay=hidden, geometry=square(), name="Proyek")
    assert spatial.plot_zones([item])[item.pk]["tier"] == "luar"
    shown = overlay("Hutan", "hutan")
    MapOverlayFeature.objects.create(overlay=shown, geometry=square(), name="HL")
    zone = spatial.plot_zones([item])[item.pk]
    assert zone["tier"] == "penyangga"
    assert zone["layers"] == ["Hutan"]
    overlaps = spatial.plot_overlaps(item)
    assert overlaps[0]["layer"] == "Hutan"
    assert overlaps[0]["pct"] == 100.0


def test_plot_measured_area_computed(korwil):
    item = plot(korwil, size=0.002)
    # ±222 m × 221 m ≈ 4,9 ha
    assert Decimal("4.8") < item.measured_area_ha < Decimal("5.0")
    assert item.number.startswith("BDG-")
    item.official_area_ha = Decimal("3")
    item.save(update_fields=["official_area_ha"])
    assert item.area_ha == Decimal("3")


# --------------------------------------------------------------------------
# Bidang penguasaan: daftar, ubah status, impor
# --------------------------------------------------------------------------


def test_plots_scoped_to_korwil(field, other_field, korwil, korwil_b):
    mine = plot(korwil)
    theirs = plot(korwil_b, x=104.202)
    response = login(field).get(f"{BASE}bidang/")
    assert response.status_code == 200
    data = response.json()
    assert [r["id"] for r in data["rows"]] == [mine.pk]
    assert data["summary"]["pending"] == 1
    assert login(field).get(f"{BASE}bidang/{theirs.pk}/").status_code == 404
    assert login(other_field).get(f"{BASE}bidang/{theirs.pk}/").status_code == 200


def test_status_change_logged_and_requires_permission(field, asset_officer, korwil):
    item = plot(korwil)
    response = login(asset_officer).post(
        f"{BASE}bidang/{item.pk}/", {"status": "sudah"}
    )
    assert response.status_code == 403
    response = login(field).post(
        f"{BASE}bidang/{item.pk}/",
        {"status": "sudah", "tim": "Tim 1", "catatan": "Dipatok", "urgensi": "tinggi"},
    )
    assert response.status_code == 200, response.content
    data = response.json()
    assert data["status"] == "sudah"
    assert data["controlled_on"] == timezone.localdate().isoformat()
    assert data["history"][0]["note"] == "Dipatok"
    item.refresh_from_db()
    assert item.control_team == "Tim 1"
    assert item.urgency == "tinggi"
    change = LandPlotChange.objects.get()
    assert (change.old_status, change.new_status, change.changed_by) == (
        "belum",
        "sudah",
        field,
    )
    # Status sama tidak menambah riwayat.
    login(field).post(f"{BASE}bidang/{item.pk}/", {"status": "sudah"})
    assert LandPlotChange.objects.count() == 1
    response = login(field).post(f"{BASE}bidang/{item.pk}/", {"status": "asal"})
    assert response.status_code == 400


def test_import_new_plots_then_mark_controlled(field, korwil):
    first = box(104.102, 0.802)
    second = box(104.106, 0.806)
    client = login(field)

    def upload(mode, stage="pratinjau", **extra):
        return client.post(
            f"{BASE}bidang/impor/",
            {
                "mode": mode,
                "tahap": stage,
                "berkas": geojson_file(
                    ({"name": "Satu", "pemilik": "Pak A"}, first),
                    ({"name": "Dua", "luas": "1,5"}, second),
                    ({"name": "Titik"}, Point(104.103, 0.803, srid=4326)),
                ),
                **extra,
            },
        )

    preview = upload("baru").json()
    assert [r["match"] for r in preview["rows"]] == ["new", "new"]
    result = upload("baru", "terapkan", pilih="0,1").json()
    assert result == {"created": 2, "updated": 0, "skipped": 0}
    one = LandPlot.objects.get(name="Satu")
    two = LandPlot.objects.get(name="Dua")
    assert one.owner_name == "Pak A" and one.korwil == korwil
    assert two.official_area_ha == Decimal("1.5")
    assert one.changes.get().new_status == "belum"
    # Impor ulang sebagai bidang baru: ditandai mirip yang sudah ada.
    assert [r["match"] for r in upload("baru").json()["rows"]] == [
        "duplicate",
        "duplicate",
    ]
    # Hasil penguasaan: "Satu" cocok luasnya; "Dua" beda luas tapi berpasangan.
    two.official_area_ha = None
    two.save(update_fields=["official_area_ha"])
    rows = upload("penguasaan").json()["rows"]
    assert [r["match"] for r in rows] == ["match", "match"]
    result = upload(
        "penguasaan", "terapkan", pilih="0", tanggal="2026-10-01", tim="Tim A"
    ).json()
    assert result == {"created": 0, "updated": 1, "skipped": 0}
    one.refresh_from_db()
    assert one.control_status == "sudah"
    assert one.controlled_on == datetime.date(2026, 10, 1)
    assert one.control_team == "Tim A"
    rows = upload("penguasaan").json()["rows"]
    assert rows[0]["match"] == "already"


def test_import_controlled_polygon_without_match_creates_plot(field, korwil):
    item = plot(korwil, size=0.002)
    client = login(field)
    far = box(104.108, 0.808, 0.0005)
    shifted_big = box(item.geometry.extent[0], item.geometry.extent[1], 0.004)
    data = {
        "mode": "penguasaan",
        "berkas": geojson_file(
            ({"name": "Jauh"}, far), ({"name": "Besar"}, shifted_big)
        ),
    }
    rows = client.post(f"{BASE}bidang/impor/", data).json()["rows"]
    assert rows[0]["match"] == "nomatch"
    # Titik tengah ±110 m dari bidang (≤200 m), luas 4× → cocok lemah.
    assert rows[1]["match"] == "weak"
    data["berkas"] = geojson_file(
        ({"name": "Jauh"}, far), ({"name": "Besar"}, shifted_big)
    )
    data.update({"tahap": "terapkan", "pilih": "0"})
    assert client.post(f"{BASE}bidang/impor/", data).json()["created"] == 1
    created = LandPlot.objects.get(name="Jauh")
    assert created.control_status == "sudah"
    assert created.controlled_on == timezone.localdate()


def test_import_permissions_and_validation(asset_officer, field, korwil):
    upload = geojson_file(({"name": "A"}, box(104.102, 0.802)))
    response = login(asset_officer).post(
        f"{BASE}bidang/impor/", {"mode": "baru", "berkas": upload}
    )
    assert response.status_code == 403
    response = login(field).post(f"{BASE}bidang/impor/", {"mode": "baru"})
    assert response.status_code == 400
    response = login(field).post(
        f"{BASE}bidang/impor/",
        {
            "mode": "baru",
            "berkas": geojson_file(({"name": "T"}, Point(104.1, 0.8, srid=4326))),
        },
    )
    assert response.status_code == 400
    assert "poligon" in response.content.decode()


def test_import_outside_scope_rejected(field, korwil, korwil_b):
    response = login(field).post(
        f"{BASE}bidang/impor/",
        {
            "mode": "baru",
            "tahap": "terapkan",
            "pilih": "0",
            "berkas": geojson_file(({"name": "B"}, box(104.202, 0.802))),
            "korwil": str(korwil_b.pk),
        },
    )
    assert response.status_code == 404
    assert not LandPlot.objects.exists()


# --------------------------------------------------------------------------
# Tumpang tindih & audit RTRW
# --------------------------------------------------------------------------


def test_overlap_between_plots_and_overlay(field, korwil):
    plot(korwil, x=104.102, y=0.802, size=0.002)
    ref = overlay("Proyek", "proyek")
    MapOverlayFeature.objects.create(
        overlay=ref, name="Blok 1", geometry=box(104.103, 0.802, 0.002)
    )
    hidden = overlay("Rahasia", command=False)
    client = login(field)
    sources = client.get(f"{BASE}tumpang-tindih/").json()["sources"]
    assert [s["key"] for s in sources] == ["bidang", f"ref-{ref.pk}"]
    data = client.get(f"{BASE}tumpang-tindih/", {"a": "bidang", "b": f"ref-{ref.pk}"})
    assert data.status_code == 200
    data = data.json()
    assert data["pct_a"] == pytest.approx(50, abs=1)
    assert data["overlap_ha"] == pytest.approx(2.46, abs=0.05)
    assert data["pairs"][0]["b"] == "Blok 1"
    csv = client.get(
        f"{BASE}tumpang-tindih/", {"a": "bidang", "b": f"ref-{ref.pk}", "format": "csv"}
    )
    assert csv["Content-Type"].startswith("text/csv")
    assert "Blok 1" in csv.content.decode()
    response = client.get(
        f"{BASE}tumpang-tindih/", {"a": "bidang", "b": f"ref-{hidden.pk}"}
    )
    assert response.status_code == 400


def test_overlap_same_layer_finds_duplicate_plots(field, korwil, korwil_b):
    plot(korwil, x=104.102, y=0.802, name="Satu")
    plot(korwil, x=104.103, y=0.802, name="Dua")
    plot(korwil_b, x=104.202, y=0.802, name="Lain")
    data = login(field).get(f"{BASE}tumpang-tindih/", {"a": "bidang", "b": "bidang"})
    pairs = data.json()["pairs"]
    assert len(pairs) == 1
    assert "Satu" in pairs[0]["a"] and "Dua" in pairs[0]["b"]


def test_rtrw_audit_categories(field, korwil):
    ref = overlay("RTRW")
    MapOverlayFeature.objects.create(
        overlay=ref, name="Zona Khusus", geometry=box(104.100, 0.800, 0.005)
    )
    MapOverlayFeature.objects.create(
        overlay=ref, name="Permukiman", geometry=box(104.105, 0.805, 0.005)
    )

    def warga(name, x, y, zone):
        return Resident.objects.create(
            head_name=name,
            korwil=korwil,
            rtrw_zone=zone,
            location=Point(x, y, srid=4326) if x else None,
        )

    warga("Sesuai", 104.101, 0.801, "khusus")
    warga("Beda", 104.102, 0.801, "lindung")
    warga("Belum", 104.103, 0.801, "belum")
    warga("Tak dikenali", 104.107, 0.807, "khusus")
    warga("Luar", 104.109, 0.801, "khusus")
    warga("Tanpa lokasi", None, None, "khusus")
    data = login(field).get(f"{BASE}audit-rtrw/").json()
    by_name = {r["name"]: r["category"] for r in data["rows"]}
    assert by_name == {
        "Sesuai": "sesuai",
        "Beda": "beda",
        "Belum": "belum_dinilai",
        "Tak dikenali": "tak_dikenali",
        "Luar": "di_luar",
        "Tanpa lokasi": "tanpa_lokasi",
    }
    assert data["conform_pct"] == 50
    csv = login(field).get(f"{BASE}audit-rtrw/", {"format": "csv"}).content.decode()
    assert "Beda" in csv and "Zona Khusus / Ditunjuk" in csv


# --------------------------------------------------------------------------
# Anomali, peta panas, jejak GPS
# --------------------------------------------------------------------------


def test_anomalies_contra_sos_and_threat_zone(admin_user, field, korwil):
    for i in range(6):
        Resident.objects.create(
            head_name=f"W{i}",
            korwil=korwil,
            stance=Stance.OPPOSE if i < 4 else Stance.SUPPORT,
        )
    alert = SosAlert.objects.create(
        raised_by=field, korwil=korwil, location=inside(korwil)
    )
    SosAlert.objects.filter(pk=alert.pk).update(
        created_at=timezone.now() - datetime.timedelta(hours=1)
    )
    ThreatZone.objects.create(
        name="Rawan", level="kritis", geometry=square(), korwil=korwil
    )
    OfficerPosition.objects.create(
        user=field, location=inside(korwil), updated_at=timezone.now()
    )
    data = login(admin_user).get(f"{BASE}anomali/").json()
    kinds = {a["kind"]: a for a in data["anomalies"]}
    assert set(kinds) >= {"kontra", "sos", "zona"}
    assert kinds["kontra"]["level"] == "kritis"
    assert data["anomalies"][0]["level"] == "kritis"
    risk = next(r for r in data["risks"] if r["code"] == "A")
    assert (risk["contra_pct"], risk["level"]) == (67, "kritis")


def test_anomaly_outside_own_korwil_and_small_samples(
    coordinator, field, korwil, korwil_b
):
    Resident.objects.create(head_name="Satu", korwil=korwil, stance=Stance.OPPOSE)
    OfficerPosition.objects.create(
        user=field, location=inside(korwil_b), updated_at=timezone.now()
    )
    data = login(coordinator).get(f"{BASE}anomali/").json()
    kinds = {a["kind"] for a in data["anomalies"]}
    assert "kontra" not in kinds  # baru 1 warga bersikap
    assert "luar" in kinds
    assert data["risks"][0]["level"] == ""


def test_heatmap_sources_and_permissions(field, coordinator, korwil):
    for i in range(3):
        Resident.objects.create(
            head_name=f"W{i}", korwil=korwil, location=Point(104.101, 0.801, srid=4326)
        )
    data = login(field).get(f"{BASE}peta-panas/", {"sumber": "warga"}).json()
    assert data["total"] == 3
    assert data["max"] == 3
    assert len(data["cells"]) == 1
    response = login(field).get(f"{BASE}peta-panas/", {"sumber": "posisi"})
    assert response.status_code == 400
    response = login(coordinator).get(f"{BASE}peta-panas/", {"sumber": "posisi"})
    assert response.status_code == 200


def test_position_records_track_with_throttle(field, korwil):
    client = login(field)
    point = inside(korwil)
    client.post(f"{BASE}posisi/", {"lat": point.y, "lng": point.x})
    client.post(f"{BASE}posisi/", {"lat": point.y + 0.00005, "lng": point.x})
    assert OfficerTrackPoint.objects.count() == 1
    client.post(f"{BASE}posisi/", {"lat": point.y + 0.001, "lng": point.x})
    assert OfficerTrackPoint.objects.count() == 2
    old = OfficerTrackPoint.objects.create(
        user=field,
        location=point,
        recorded_at=timezone.now() - datetime.timedelta(days=90),
    )
    assert spatial.prune_tracks() == 1
    assert not OfficerTrackPoint.objects.filter(pk=old.pk).exists()


def test_track_visible_only_to_leaders_in_scope(
    coordinator, field, other_field, korwil, korwil_b
):
    now = timezone.now()
    for i, user in enumerate((field, other_field, field)):
        OfficerTrackPoint.objects.create(
            user=user,
            location=Point(104.101 + i * 0.001, 0.801, srid=4326),
            recorded_at=now - datetime.timedelta(minutes=10 - i),
        )
    assert login(field).get(f"{BASE}jejak/").status_code == 403
    client = login(coordinator)
    data = client.get(f"{BASE}jejak/").json()
    assert [o["id"] for o in data["officers"]] == [field.pk]
    data = client.get(f"{BASE}jejak/", {"petugas": field.pk}).json()
    assert len(data["points"]) == 2
    assert data["distance_km"] == pytest.approx(0.22, abs=0.01)
    assert client.get(f"{BASE}jejak/", {"petugas": other_field.pk}).status_code == 404


# --------------------------------------------------------------------------
# Zona ancaman
# --------------------------------------------------------------------------


def test_threat_zone_lifecycle(manager, coordinator, field, korwil):
    point = inside(korwil)
    payload = {"name": "Blokade", "level": "tinggi", "lat": point.y, "lng": point.x}
    assert login(field).post(f"{BASE}zona-ancaman/", payload).status_code == 403
    response = login(coordinator).post(
        f"{BASE}zona-ancaman/", {**payload, "radius": "5"}
    )
    assert response.status_code == 400
    response = login(coordinator).post(
        f"{BASE}zona-ancaman/", {**payload, "radius": "300"}
    )
    assert response.status_code == 201, response.content
    zone = response.json()
    assert zone["korwil"] == "A"
    assert zone["area_ha"] == pytest.approx(28.2, abs=0.3)
    assert zone["can_change"] and not zone["can_delete"]
    assert [
        z["id"] for z in login(field).get(f"{BASE}zona-ancaman/").json()["zones"]
    ] == [zone["id"]]
    url = f"{BASE}zona-ancaman/{zone['id']}/"
    assert login(field).post(url + "nonaktif/").status_code == 403
    assert login(coordinator).post(url + "nonaktif/").json()["active"] is False
    assert login(field).get(f"{BASE}zona-ancaman/").json()["zones"] == []
    assert login(coordinator).post(url + "hapus/").status_code == 403
    assert login(manager).post(url + "hapus/").json() == {"deleted": True}


def test_threat_zone_polygon_input(coordinator, korwil):
    geometry = json.dumps(json.loads(box(104.102, 0.802).geojson))
    response = login(coordinator).post(
        f"{BASE}zona-ancaman/", {"name": "Poligon", "geometry": geometry}
    )
    assert response.status_code == 201, response.content
    assert ThreatZone.objects.get().level == "sedang"
    response = login(coordinator).post(
        f"{BASE}zona-ancaman/", {"name": "Rusak", "geometry": "{bukan json"}
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------
# Foto 360°
# --------------------------------------------------------------------------


def test_site_photo_upload_view_and_delete(
    coordinator, field, other_field, korwil, korwil_b
):
    point = inside(korwil)
    upload = SimpleUploadedFile("pano.png", png_bytes((8, 4)), "image/png")
    response = login(field).post(
        f"{BASE}foto-360/",
        {"title": "Dermaga", "lat": point.y, "lng": point.x, "foto": upload},
    )
    assert response.status_code == 201, response.content
    data = response.json()
    assert data["korwil"] == "A" and data["can_delete"] is False
    photo = SitePhoto360.objects.get()
    assert login(field).get(data["url"]).status_code == 200
    assert login(other_field).get(data["url"]).status_code == 404
    assert login(other_field).get(f"{BASE}foto-360/").json()["photos"] == []
    assert login(field).post(f"{BASE}foto-360/{photo.pk}/hapus/").status_code == 403
    assert login(coordinator).post(f"{BASE}foto-360/{photo.pk}/hapus/").json() == {
        "deleted": True
    }


def test_site_photo_rejects_non_image(field, korwil):
    point = inside(korwil)
    fake = SimpleUploadedFile("pano.jpg", b"bukan gambar", "image/jpeg")
    response = login(field).post(
        f"{BASE}foto-360/",
        {"title": "X", "lat": point.y, "lng": point.x, "foto": fake},
    )
    assert response.status_code == 400
    assert not SitePhoto360.objects.exists()


# --------------------------------------------------------------------------
# Lapisan & konfigurasi
# --------------------------------------------------------------------------


def test_layers_and_config(field, korwil):
    plot(korwil)
    ThreatZone.objects.create(name="Rawan", geometry=square(), korwil=korwil)
    ref = overlay("RTRW Rempang")
    MapOverlayFeature.objects.create(
        overlay=ref,
        name="Zona Khusus",
        geometry=square(),
        properties={"warna": "#123456"},
    )
    hidden = overlay("Biasa", command=False)
    client = login(field)
    for key, count in (
        ("bidang", 1),
        ("ancaman", 1),
        ("foto360", 0),
        (f"ref-{ref.pk}", 1),
    ):
        response = client.get(f"{BASE}lapisan/{key}/")
        assert response.status_code == 200, key
        assert len(response.json()["features"]) == count, key
    feature = client.get(f"{BASE}lapisan/ref-{ref.pk}/").json()["features"][0]
    assert feature["properties"]["color"] == "#123456"
    assert client.get(f"{BASE}lapisan/ref-{hidden.pk}/").status_code == 404
    page = client.get("/komando/")
    config = page.context["komando_config"]
    assert [layer["key"] for layer in config["commandLayers"]] == [f"ref-{ref.pk}"]
    assert all(layer["key"] != f"ref-{ref.pk}" for layer in config["extraLayers"])
    assert config["perms"]["bidang"] and not config["perms"]["jejak"]
    assert config["urls"]["plots"] == "/komando/api/bidang/"


def test_asset_officer_reads_but_cannot_edit(asset_officer, korwil):
    item = plot(korwil)
    client = login(asset_officer)
    assert client.get(f"{BASE}bidang/{item.pk}/").status_code == 200
    assert (
        client.post(f"{BASE}bidang/{item.pk}/", {"status": "sudah"}).status_code == 403
    )
    point = inside(korwil)
    response = client.post(
        f"{BASE}zona-ancaman/",
        {"name": "Z", "lat": point.y, "lng": point.x, "radius": "100"},
    )
    assert response.status_code == 201
