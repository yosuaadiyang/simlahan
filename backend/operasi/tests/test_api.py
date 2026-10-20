import json
import uuid

import pytest
from django.core import mail
from django.test import Client

from asetlahan import enums as aset_enums
from asetlahan.models import Task
from operasi import enums
from operasi.models import (
    Activity,
    AreaAnalysis,
    Attendance,
    ChatMessage,
    OfficerPosition,
    Resident,
    SoilTest,
    SosAlert,
    StanceChange,
)
from operasi.tests.conftest import inside, login, make_user, photo, png_bytes

pytestmark = pytest.mark.django_db

BASE = "/komando/"


def api(path):
    return f"{BASE}api/{path}"


# --------------------------------------------------------------------------
# Halaman & PWA
# --------------------------------------------------------------------------


def test_page_renders_with_config(field, korwil):
    response = login(field).get(BASE + "?tab=absen")
    assert response.status_code == 200
    body = response.content.decode()
    config = json.loads(
        body.split('id="komando-config" type="application/json">')[1].split(
            "</script>"
        )[0]
    )
    assert config["initialTab"] == "absen"
    assert config["korwils"][0]["code"] == "A"
    assert config["myKorwils"] == [korwil.pk]
    assert (
        config["perms"]["lapor"] and config["perms"]["absen"] and config["perms"]["sos"]
    )
    assert not config["perms"]["kunci"]
    assert "Django" not in body
    assert (
        response["Cache-Control"].startswith("max-age=0")
        or "no-cache" in response["Cache-Control"]
    )


def test_page_requires_login_and_permission(seeded, units):
    response = Client().get(BASE)
    assert response.status_code == 302 and "/admin/login/" in response["Location"]
    plain = make_user("staf", units=[units[0]])
    response = login(plain).get(BASE)
    assert response.status_code == 403


def test_manifest_and_service_worker(field):
    client = login(field)
    manifest = client.get(BASE + "manifest.webmanifest").json()
    urls = [s["url"] for s in manifest["shortcuts"]]
    assert urls == [
        f"{BASE}?tab=absen",
        f"{BASE}?tab=korwil",
        f"{BASE}?tab=perf",
        f"{BASE}?tab=tasks",
    ]
    assert manifest["start_url"] == BASE and manifest["display"] == "standalone"
    response = client.get(BASE + "sw.js")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/javascript")
    assert "komando-shell-" in response.content.decode()


def test_static_assets_exist():
    from django.contrib.staticfiles import finders

    for name in (
        "operasi/komando.js",
        "operasi/komando.css",
        "operasi/komando-icon.svg",
        "operasi/komando-icon-192.png",
        "operasi/komando-icon-512.png",
    ):
        assert finders.find(name), name


def test_api_requires_session(seeded):
    response = Client().get(api("ringkasan/"))
    assert response.status_code == 401


# --------------------------------------------------------------------------
# Ringkasan, lapisan, pencarian
# --------------------------------------------------------------------------


def test_summary_and_layers(field, korwil, korwil_b):
    Resident.objects.create(
        head_name="Pro",
        korwil=korwil,
        stance=enums.Stance.SUPPORT,
        location=inside(korwil),
    )
    Resident.objects.create(
        head_name="Kontra", korwil=korwil, stance=enums.Stance.OPPOSE
    )
    Resident.objects.create(
        head_name="Lain", korwil=korwil_b, stance=enums.Stance.SUPPORT
    )
    client = login(field)
    data = client.get(api("ringkasan/")).json()
    # Korwil B milik unit lain tidak terlihat.
    assert data["total"] == 2 and data["pro_pct"] == 50 and data["korwil"] == 1
    korwils = client.get(api("lapisan/korwil/")).json()
    assert [f["properties"]["code"] for f in korwils["features"]] == ["A"]
    assert korwils["features"][0]["properties"]["stats"]["pro_pct"] == 50
    warga = client.get(api("lapisan/warga/")).json()
    assert len(warga["features"]) == 1
    for key in ("kegiatan", "tanah", "sos", "petugas"):
        assert client.get(api(f"lapisan/{key}/")).status_code == 200, key
    assert client.get(api("lapisan/tidakada/")).status_code == 404


def test_search(field, manager, korwil):
    Resident.objects.create(
        head_name="Zulkifli",
        korwil=korwil,
        nik="2171010101010009",
        location=inside(korwil),
    )
    client = login(field)
    kinds = {r["kind"] for r in client.get(api("cari/?q=zulk")).json()["results"]}
    assert "warga" in kinds
    # Cari dengan NIK hanya bagi pemegang izin NIK (Administrator).
    assert client.get(api("cari/?q=2171010101010009")).json()["results"] == []
    by_nik = login(manager).get(api("cari/?q=2171010101010009")).json()["results"]
    assert by_nik and by_nik[0]["label"] == "Zulkifli"
    assert any(
        r["kind"] == "korwil"
        for r in client.get(api("cari/?q=pasir")).json()["results"]
    )


# --------------------------------------------------------------------------
# Kegiatan & uji tanah
# --------------------------------------------------------------------------


def test_activity_report_with_photos_stance_and_idempotency(field, korwil):
    resident = Resident.objects.create(head_name="Rusli", korwil=korwil)
    client = login(field)
    client_id = str(uuid.uuid4())
    point = inside(korwil)
    payload = {
        "client_id": client_id,
        "jenis": "kunjungan",
        "judul": "Kunjungan rumah",
        "lat": point.y,
        "lng": point.x,
        "accuracy": "8.27",
        "peserta": "3",
        "warga": str(resident.pk),
        "sikap": json.dumps({str(resident.pk): "mendukung"}),
        "foto": [photo("a.png"), photo("b.png")],
    }
    response = client.post(api("kegiatan/"), payload)
    assert response.status_code == 201, response.content
    activity = Activity.objects.get()
    assert activity.korwil == korwil and activity.photos.count() == 2
    resident.refresh_from_db()
    assert resident.stance == enums.Stance.SUPPORT and resident.last_visited_on
    change = StanceChange.objects.get()
    assert change.activity == activity and change.changed_by == field
    again = client.post(api("kegiatan/"), {**payload, "foto": []})
    assert again.status_code == 200 and again.json()["duplicate"] is True
    assert Activity.objects.count() == 1
    listing = client.get(api("kegiatan/")).json()["results"]
    assert listing[0]["number"] == activity.number and len(listing[0]["photos"]) == 2
    photo_url = listing[0]["photos"][0]
    assert client.get(photo_url).status_code == 200


def test_activity_rejects_bad_input(field, korwil, korwil_b):
    client = login(field)
    base = {"client_id": str(uuid.uuid4()), "judul": "Uji"}
    assert client.post(api("kegiatan/"), {**base, "client_id": "x"}).status_code == 400
    assert client.post(api("kegiatan/"), {**base, "judul": ""}).status_code == 400
    other = Resident.objects.create(head_name="Unit lain", korwil=korwil_b)
    response = client.post(api("kegiatan/"), {**base, "warga": str(other.pk)})
    assert response.status_code == 400
    response = client.post(api("kegiatan/"), {**base, "foto": [photo("x.exe")]})
    assert response.status_code == 400
    assert not Activity.objects.exists()


def test_field_officer_cannot_change_stance_without_permission(field, korwil, units):
    from django.contrib.auth.models import Permission

    field.groups.clear()
    for codename in ("view_korwil", "view_activity", "add_activity", "view_resident"):
        field.user_permissions.add(
            Permission.objects.get(codename=codename, content_type__app_label="operasi")
        )
    resident = Resident.objects.create(head_name="Musa", korwil=korwil)
    response = login(field).post(
        api("kegiatan/"),
        {
            "client_id": str(uuid.uuid4()),
            "judul": "Uji",
            "sikap": json.dumps({str(resident.pk): "menolak"}),
        },
    )
    assert response.status_code == 403


def test_verify_activity_only_by_coordinator(field, coordinator, korwil):
    activity = Activity.objects.create(title="Rapat", korwil=korwil, reported_by=field)
    url = api(f"kegiatan/{activity.pk}/verifikasi/")
    assert login(field).post(url).status_code == 403
    response = login(coordinator).post(url, {"verified": "1"})
    assert response.status_code == 200 and response.json()["verified"] is True
    activity.refresh_from_db()
    assert activity.verified_by == coordinator


def test_soil_test(field, korwil):
    client = login(field)
    point = inside(korwil)
    # Nilai pecahan dari perangkat (6.2, 14.37) harus lolos validasi desimal.
    base = {
        "client_id": str(uuid.uuid4()),
        "ph": "6.2",
        "kadar_air": "23.456",
        "accuracy": "14.37",
        "kelayakan": "layak",
        "tekstur": "lempung",
    }
    assert client.post(api("tanah/"), base).status_code == 400  # tanpa lokasi
    response = client.post(
        api("tanah/"), {**base, "lat": point.y, "lng": point.x, "foto": photo()}
    )
    assert response.status_code == 201, response.content
    test = SoilTest.objects.get()
    assert test.korwil == korwil and str(test.ph) == "6.20" and test.sampled_by == field
    assert str(test.moisture_pct) == "23.46"
    assert client.get(f"{BASE}berkas/tanah-foto/{test.pk}/").status_code == 200
    bad = {
        **base,
        "client_id": str(uuid.uuid4()),
        "lat": point.y,
        "lng": point.x,
        "tekstur": "batu",
    }
    assert client.post(api("tanah/"), bad).status_code == 400


# --------------------------------------------------------------------------
# Warga
# --------------------------------------------------------------------------


def test_resident_create_update_and_scope(field, other_field, korwil, korwil_b):
    client = login(field)
    point = inside(korwil)
    response = client.post(
        api("warga/"),
        {
            "nama": "Kamal",
            "nik": "2171010101010002",
            "sikap": "netral",
            "lat": point.y,
            "lng": point.x,
            "jiwa": "4",
        },
    )
    assert response.status_code == 201, response.content
    data = response.json()
    assert data["korwil"] == "A" and data["stance"] == "netral" and data["members"] == 4
    duplicate = client.post(
        api("warga/"), {"nama": "Kamal lagi", "nik": "2171010101010002"}
    )
    assert duplicate.status_code == 400
    assert (
        client.post(api("warga/"), {"nama": "NIK pendek", "nik": "123"}).status_code
        == 400
    )
    detail = client.post(
        api(f"warga/{data['id']}/"),
        {"sikap": "mendukung", "rtrw": "sesuai", "catatan": "Setuju relokasi"},
    ).json()
    assert detail["stance"] == "mendukung" and detail["rtrw"] == "sesuai"
    assert (
        detail["history"][0]["to"] == "Mendukung"
        and "Setuju relokasi" in detail["note"]
    )
    assert (
        client.post(api(f"warga/{data['id']}/"), {"sikap": "acak"}).status_code == 400
    )
    # Petugas unit lain tidak melihat warga ini.
    assert login(other_field).get(api(f"warga/{data['id']}/")).status_code == 404
    names = [r["name"] for r in client.get(api("warga/?q=kam")).json()["results"]]
    assert names == ["Kamal"]


# --------------------------------------------------------------------------
# Tugas & kinerja
# --------------------------------------------------------------------------


def test_tasks_for_assignee_and_coordinator(field, coordinator, korwil):
    mine = Task.objects.create(title="Pendataan RT 01", assignee=field)
    area = Task.objects.create(title="Tugas wilayah A", korwil=korwil)
    Task.objects.create(title="Tugas orang lain")
    titles = {t["title"] for t in login(field).get(api("tugas/")).json()["results"]}
    assert titles == {mine.title}
    titles = {
        t["title"] for t in login(coordinator).get(api("tugas/")).json()["results"]
    }
    assert titles == {area.title}
    response = login(field).post(
        api(f"tugas/{mine.pk}/"), {"status": aset_enums.TaskStatus.DONE}
    )
    assert response.status_code == 200
    mine.refresh_from_db()
    assert mine.status == aset_enums.TaskStatus.DONE and mine.progress == 100
    assert (
        login(field).post(api(f"tugas/{area.pk}/"), {"progress": "50"}).status_code
        == 404
    )
    assert (
        login(field).post(api(f"tugas/{mine.pk}/"), {"progress": "150"}).status_code
        == 400
    )


def test_performance_and_team(field, coordinator, korwil):
    data = login(field).get(api("kinerja/?periode=minggu")).json()
    assert data["me"]["user_id"] == field.pk and "team" not in data
    data = login(coordinator).get(api("kinerja/?periode=bulan")).json()
    assert {row["user_id"] for row in data["team"]} == {field.pk, coordinator.pk}
    data = login(coordinator).get(api(f"kinerja/?petugas={field.pk}")).json()
    assert data["me"]["user_id"] == field.pk
    # Petugas tidak dapat melihat kinerja orang lain.
    assert (
        login(field).get(api(f"kinerja/?petugas={coordinator.pk}")).status_code == 404
    )


# --------------------------------------------------------------------------
# Chat, SOS, Live
# --------------------------------------------------------------------------


def test_chat_channels(field, coordinator, other_field, korwil, korwil_b):
    client = login(field)
    assert client.post(api("chat/"), {"pesan": ""}).status_code == 400
    assert client.post(api("chat/"), {"pesan": "Halo semua"}).status_code == 201
    assert (
        client.post(
            api("chat/"), {"pesan": "Halo Korwil A", "kanal": korwil.pk}
        ).status_code
        == 201
    )
    general = login(coordinator).get(api("chat/?kanal=umum")).json()["results"]
    assert [m["body"] for m in general] == ["Halo semua"]
    channel = login(coordinator).get(api(f"chat/?kanal={korwil.pk}")).json()["results"]
    assert [m["body"] for m in channel] == ["Halo Korwil A"]
    after = (
        login(coordinator)
        .get(api(f"chat/?kanal=umum&setelah={general[0]['id']}"))
        .json()
    )
    assert after["results"] == []
    # Kanal Korwil unit lain tidak dapat dibuka.
    assert client.get(api(f"chat/?kanal={korwil_b.pk}")).status_code == 404


def test_sos_flow(settings, field, coordinator, manager, korwil):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    client = login(field)
    point = inside(korwil)
    client_id = str(uuid.uuid4())
    response = client.post(
        api("sos/"),
        {"client_id": client_id, "lat": point.y, "lng": point.x, "pesan": "Dihadang"},
    )
    assert response.status_code == 201, response.content
    alert = SosAlert.objects.get()
    assert alert.korwil == korwil and alert.status == enums.SosStatus.ACTIVE
    assert ChatMessage.objects.filter(is_system=True, body__contains="SOS").exists()
    recipients = set(mail.outbox[0].to)
    assert {coordinator.email, manager.email} <= recipients
    assert "google.com/maps" in mail.outbox[0].body
    assert (
        client.post(api("sos/"), {"client_id": client_id}).json()["duplicate"] is True
    )
    feed = login(coordinator).get(api("sos/")).json()["results"]
    assert feed[0]["number"] == alert.number
    assert client.post(api(f"sos/{alert.pk}/tangani/")).status_code == 403
    assert login(coordinator).post(api(f"sos/{alert.pk}/tangani/")).status_code == 200
    assert (
        client.post(api(f"sos/{alert.pk}/selesai/"), {"catatan": "Aman"}).status_code
        == 200
    )
    alert.refresh_from_db()
    assert alert.status == enums.SosStatus.RESOLVED and alert.resolution_note == "Aman"
    assert client.post(api(f"sos/{alert.pk}/palsu/")).status_code == 400


def test_live_position(field, korwil):
    client = login(field)
    point = inside(korwil)
    assert client.post(api("posisi/"), {"lat": "x"}).status_code == 400
    response = client.post(
        api("posisi/"),
        {
            "lat": point.y,
            "lng": point.x,
            "battery": "80",
            "heading": "90.27",
            "speed": "1.234",
            "accuracy": "5.55",
        },
    )
    assert response.status_code == 200
    assert OfficerPosition.objects.get(user=field).battery_pct == 80
    features = client.get(api("lapisan/petugas/")).json()["features"]
    assert features[0]["properties"]["self"] is True
    client.post(api("posisi/"), {"stop": "1"})
    assert not OfficerPosition.objects.exists()


# --------------------------------------------------------------------------
# AI Satelit & berkas privat
# --------------------------------------------------------------------------


def test_satellite_analysis_without_ai(monkeypatch, field, korwil):
    from operasi import satellite

    monkeypatch.setattr(satellite, "_fetch_tile", lambda url: png_bytes((256, 256)))
    monkeypatch.setattr(satellite.ai, "enabled", lambda: False)
    Resident.objects.create(
        head_name="Dalam area", korwil=korwil, location=inside(korwil)
    )
    c = inside(korwil)
    bbox = [c.y - 0.002, c.x - 0.002, c.y + 0.002, c.x + 0.002]
    client = login(field)
    response = client.post(
        api("ai-satelit/"), json.dumps({"bbox": bbox}), content_type="application/json"
    )
    assert response.status_code == 201, response.content
    data = response.json()
    assert data["summary"]["warga"]["total"] == 1 and data["ai"] == {}
    assert client.get(data["image"]).status_code == 200
    too_big = client.post(
        api("ai-satelit/"),
        json.dumps({"bbox": [0.5, 104.0, 0.9, 104.4]}),
        content_type="application/json",
    )
    assert too_big.status_code == 400


def test_satellite_analysis_with_ai(monkeypatch, field, korwil):
    from operasi import satellite

    monkeypatch.setattr(satellite, "_fetch_tile", lambda url: png_bytes((256, 256)))
    monkeypatch.setattr(satellite.ai, "enabled", lambda: True)
    monkeypatch.setattr(satellite.ai, "model", lambda: "model-uji")
    result = {
        "tutupan_lahan": {
            "vegetasi_pct": 60,
            "bangunan_pct": 20,
            "lahan_terbuka_pct": 10,
            "air_pct": 5,
            "jalan_pct": 5,
        },
        "perkiraan_jumlah_bangunan": 12,
        "temuan": ["Permukiman di pesisir"],
        "rekomendasi": ["Verifikasi lapangan"],
        "ringkasan": "Area didominasi vegetasi.",
    }
    monkeypatch.setattr(satellite, "ai_analyze", lambda image, summary: result)
    c = inside(korwil)
    response = login(field).post(
        api("ai-satelit/"),
        json.dumps({"bbox": [c.y - 0.002, c.x - 0.002, c.y + 0.002, c.x + 0.002]}),
        content_type="application/json",
    )
    assert response.status_code == 201
    assert response.json()["ai"]["ringkasan"] == "Area didominasi vegetasi."
    assert AreaAnalysis.objects.get().ai_model == "model-uji"


def test_satellite_tile_failure_is_reported(monkeypatch, field, korwil):
    from operasi import satellite

    monkeypatch.setattr(satellite, "_fetch_tile", lambda url: None)
    c = inside(korwil)
    response = login(field).post(
        api("ai-satelit/"),
        json.dumps({"bbox": [c.y - 0.002, c.x - 0.002, c.y + 0.002, c.x + 0.002]}),
        content_type="application/json",
    )
    assert response.status_code == 201
    assert response.json()["error"] and response.json()["image"] == ""


def test_private_files_are_scoped(field, other_field, coordinator, korwil, korwil_b):
    from operasi import services
    from operasi.tests.conftest import photo as make_photo

    attendance, _created, _warnings = services.check_in(
        field, location=inside(korwil), photo=make_photo()
    )
    url = f"{BASE}berkas/absen-masuk/{attendance.pk}/"
    assert login(field).get(url).status_code == 200
    assert login(coordinator).get(url).status_code == 200
    assert login(other_field).get(url).status_code == 404
    assert login(field).get(f"{BASE}berkas/tidakada/1/").status_code == 404
    assert Attendance.objects.count() == 1
