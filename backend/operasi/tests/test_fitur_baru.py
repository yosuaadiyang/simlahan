"""Tes fitur pusat komando baru: peringkat+tren, struktur, feed, AI chat,
dossier warga, zona RTRW, bobot kegiatan, dan voice note."""

import uuid

import pytest
from django.urls import reverse

from operasi import enums
from operasi.models import Activity, ActivityWeight, Resident, StanceChange

from .conftest import inside, login

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------
# Peringkat & tren
# --------------------------------------------------------------------------


def test_leaderboard_with_trend(admin_user, coordinator, korwil):
    client = login(coordinator)
    response = client.get(reverse("operasi-leaderboard"), {"periode": "bulan"})
    assert response.status_code == 200
    rows = response.json()["results"]
    assert rows
    codes = {row["trend"] for row in rows}
    assert codes <= {"naik", "turun", "baru", "stabil"}
    scores = [row["score"] for row in rows]
    assert scores == sorted(scores, reverse=True)
    # Peringkat kompetisi: skor sama berperingkat sama (1, 1, 3, …).
    assert [row["rank"] for row in rows] == [
        1 + sum(1 for other in scores if other > score) for score in scores
    ]


def test_leaderboard_denied_for_anonymous(client, korwil):
    response = client.get(reverse("operasi-leaderboard"))
    assert response.status_code in (302, 401, 403)


# --------------------------------------------------------------------------
# Struktur
# --------------------------------------------------------------------------


def test_structure_lists_korwil_coordinator_members(coordinator, field, korwil):
    client = login(coordinator)
    response = client.get(reverse("operasi-structure"))
    assert response.status_code == 200
    rows = response.json()["results"]
    target = [row for row in rows if row["code"] == "A"]
    assert target
    row = target[0]
    assert row["coordinator"] == coordinator.get_full_name()
    names = [m["name"] for m in row["members"]]
    assert field.get_full_name() in names


# --------------------------------------------------------------------------
# Feed
# --------------------------------------------------------------------------


def test_feed_combines_activities_soil_sos(coordinator, field, korwil, db):
    from operasi.models import SoilTest, SosAlert

    client = login(coordinator)
    point = inside(korwil)
    Activity.objects.create(
        title="Sosialisasi program",
        activity_type=enums.ActivityType.SOCIALIZATION,
        korwil=korwil,
        location=point,
        reported_by=field,
    )
    SoilTest.objects.create(
        korwil=korwil, location=point, sampled_by=field, texture=enums.SoilTexture.CLAY
    )
    SosAlert.objects.create(
        korwil=korwil, raised_by=field, location=point, message="Butuh bantuan"
    )
    response = client.get(reverse("operasi-feed"))
    assert response.status_code == 200
    kinds = {item["kind"] for item in response.json()["results"]}
    assert {"kegiatan", "tanah", "sos"} <= kinds


def test_feed_includes_stance_change(admin_user, field, korwil):
    resident = Resident.objects.create(
        head_name="Warga Contoh", korwil=korwil, stance=enums.Stance.SUPPORT
    )
    StanceChange.objects.create(
        resident=resident,
        old_stance=enums.Stance.NEUTRAL,
        new_stance=enums.Stance.SUPPORT,
        changed_by=field,
    )
    client = login(admin_user)
    response = client.get(reverse("operasi-feed"))
    items = response.json()["results"]
    assert any(
        item["kind"] == "sikap" and "Warga Contoh" in item["title"] for item in items
    )


# --------------------------------------------------------------------------
# AI chat
# --------------------------------------------------------------------------


def test_ai_chat_fallback_without_api_key(coordinator, korwil):
    client = login(coordinator)
    response = client.post(reverse("operasi-ai-chat"), {"tanya": "Berapa warga pro?"})
    assert response.status_code == 200
    answer = response.json()["answer"]
    assert "Korwil" in answer or "belum dikonfigurasi" in answer


def test_ai_chat_rejects_empty_question(coordinator):
    client = login(coordinator)
    response = client.post(reverse("operasi-ai-chat"), {"tanya": "   "})
    assert response.status_code == 400


# --------------------------------------------------------------------------
# Dossier warga + zona
# --------------------------------------------------------------------------


def test_resident_dossier_fields_roundtrip(coordinator, korwil):
    client = login(coordinator)
    point = inside(korwil)
    data = {
        "nama": "Warga Dossier",
        "korwil": korwil.pk,
        "lat": point.y,
        "lng": point.x,
        "gender": "L",
        "umur": "45",
        "pekerjaan": "Nelayan",
        "asal": "Tanjung Pinang",
        "menetap": "30",
        "pasangan": "Ibu Contoh",
        "anak": "3",
        "luas_lahan": "1250.50",
        "penggarapan": "digarapi",
        "kondisi_lahan": "Berbatu di bagian utara.",
        "zona": "lindung",
    }
    response = client.post(reverse("operasi-residents"), data)
    assert response.status_code == 201, getattr(response, "context", None)
    body = response.json()
    assert body["gender"] == "L"
    assert body["age"] == 45
    assert body["occupation"] == "Nelayan"
    assert body["zone"] == enums.RtrwZone.PROTECTED
    resident = Resident.objects.get(pk=body["id"])
    assert float(resident.land_area_m2) == 1250.50
    assert resident.spouse_name == "Ibu Contoh"
    assert resident.cultivation_status == enums.CultivationStatus.CULTIVATED


def test_resident_rejects_bad_zone(coordinator, korwil):
    client = login(coordinator)
    point = inside(korwil)
    response = client.post(
        reverse("operasi-residents"),
        {
            "nama": "Warga Zona",
            "korwil": korwil.pk,
            "lat": point.y,
            "lng": point.x,
            "zona": "ngaco",
        },
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------
# Bobot kegiatan pada KPI
# --------------------------------------------------------------------------


def test_activity_weight_counts_in_performance(coordinator, field, korwil):
    from operasi import services

    ActivityWeight.objects.create(activity_type=enums.ActivityType.PATROL, points=5)
    point = inside(korwil)
    Activity.objects.create(
        title="Patroli kawasan",
        activity_type=enums.ActivityType.PATROL,
        korwil=korwil,
        location=point,
        reported_by=field,
        started_at="2026-10-24T08:00:00Z",
    )
    import datetime

    start = datetime.date(2026, 10, 19)
    end = datetime.date(2026, 10, 25)
    row = services.performance(field, start, end)
    # Poin usaha: bobot patroli 5 + bonus lokasi GPS 1.
    assert row["activities"] == 6 and row["activity_count"] == 1
    from operasi.models import CommandSettings

    config = CommandSettings.load()
    config.scoring_mode = enums.ScoringMode.COUNT
    config.save()
    row = services.performance(field, start, end)
    assert row["activities"] == 5  # mode jumlah: satu patroli bernilai 5


# --------------------------------------------------------------------------
# Voice note kegiatan
# --------------------------------------------------------------------------


def test_activity_voice_note_upload_and_json(coordinator, field, korwil):
    client = login(field)
    point = inside(korwil)
    from django.core.files.uploadedfile import SimpleUploadedFile

    audio = SimpleUploadedFile(
        "catatan.mp3", b"ID3\x03\x00\x00\x00\x00\x00", content_type="audio/mpeg"
    )
    response = client.post(
        reverse("operasi-activities"),
        data={
            "client_id": str(uuid.uuid4()),
            "judul": "Kegiatan dengan suara",
            "jenis": enums.ActivityType.VISIT,
            "waktu": "2026-10-24T08:00:00Z",
            "lat": point.y,
            "lng": point.x,
            "korwil": korwil.pk,
            "suara": audio,
        },
    )
    assert response.status_code == 201, response.content
    body = response.json()
    activity = Activity.objects.get(pk=body["id"])
    assert activity.voice_note
