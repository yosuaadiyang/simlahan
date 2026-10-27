"""Perbaikan audit fitur pusat komando (peringkat, feed, AI, dossier, PWA)."""

import datetime
import uuid

import pytest
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from operasi import enums, services
from operasi.importers import AssetImportError, import_residents
from operasi.models import Activity, Resident, SosAlert

from .conftest import inside, login, make_user

pytestmark = pytest.mark.django_db


def _veteran(*users):
    """Anggota yang sudah aktif sejak jauh sebelum periode sebelumnya."""
    for user in users:
        user.date_joined = timezone.now() - datetime.timedelta(days=120)
        user.save(update_fields=["date_joined"])


# --------------------------------------------------------------------------
# Peringkat & tren
# --------------------------------------------------------------------------


def test_previous_period_is_previous_calendar_month():
    assert services.previous_period(
        datetime.date(2026, 10, 1), datetime.date(2026, 10, 31)
    ) == (datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
    assert services.previous_period(
        datetime.date(2026, 3, 1), datetime.date(2026, 3, 31)
    ) == (datetime.date(2026, 2, 1), datetime.date(2026, 2, 28))
    # Mingguan: tujuh hari tepat sebelumnya.
    assert services.previous_period(
        datetime.date(2026, 10, 19), datetime.date(2026, 10, 25)
    ) == (datetime.date(2026, 10, 12), datetime.date(2026, 10, 18))


def test_leaderboard_ties_are_stable_not_falling(coordinator, field, korwil):
    _veteran(coordinator, field)
    start, end = services.period_bounds("bulan-lalu")
    rows = services.leaderboard(coordinator, start, end)
    assert len(rows) == 2
    # Tanpa data sama sekali skornya sama: peringkat sama, tren stabil.
    assert rows[0]["score"] == rows[1]["score"]
    assert {row["rank"] for row in rows} == {1}
    assert {row["trend"] for row in rows} == {"stabil"}


def test_leaderboard_trend_up_and_new_member(coordinator, field, korwil):
    _veteran(coordinator, field)
    start, end = services.period_bounds("minggu")
    prev_start, _prev_end = services.previous_period(start, end)
    old_scores = {
        row["user_id"]: row["score"]
        for row in services.leaderboard(coordinator, prev_start, _prev_end, False)
    }
    rows = {r["user_id"]: r for r in services.leaderboard(coordinator, start, end)}
    for user_id, row in rows.items():
        assert row["trend"] in ("naik", "turun", "stabil")
        assert user_id in old_scores
    newcomer = make_user("baru", *[g.pk for g in field.groups.all()])
    korwil.members.add(newcomer)
    rows = {r["user_id"]: r for r in services.leaderboard(coordinator, start, end)}
    assert rows[newcomer.pk]["trend"] == "baru"


def test_performance_view_team_has_no_trend(coordinator, field, korwil):
    response = login(coordinator).get(reverse("operasi-performance"))
    assert response.status_code == 200
    team = response.json()["team"]
    assert team and all("trend" not in row for row in team)


# --------------------------------------------------------------------------
# Feed: setiap jenis butuh izin lihatnya
# --------------------------------------------------------------------------


def test_feed_respects_per_kind_view_permissions(seeded, field, korwil):
    point = inside(korwil)
    Activity.objects.create(
        title="Rahasia", korwil=korwil, location=point, reported_by=field
    )
    SosAlert.objects.create(korwil=korwil, raised_by=field, location=point)
    viewer = make_user("pemantau")
    viewer.is_staff = True
    viewer.save()
    viewer.user_permissions.add(Permission.objects.get(codename="view_korwil"))
    korwil.members.add(viewer)
    response = login(viewer).get(reverse("operasi-feed"))
    assert response.status_code == 200
    assert response.json()["results"] == []


# --------------------------------------------------------------------------
# Asisten AI: angka warga dari ringkasan Korwil
# --------------------------------------------------------------------------


def test_ai_fallback_counts_residents_and_zones(coordinator, korwil):
    Resident.objects.create(
        head_name="Warga Satu",
        korwil=korwil,
        stance=enums.Stance.SUPPORT,
        rtrw_zone=enums.RtrwZone.PROTECTED,
    )
    response = login(coordinator).post(
        reverse("operasi-ai-chat"), {"tanya": "berapa warga pro?"}
    )
    answer = response.json()["answer"]
    assert "Korwil A (Pasir Panjang): 1 warga" in answer
    assert "Zona Lindung 1" in answer


# --------------------------------------------------------------------------
# Dossier warga
# --------------------------------------------------------------------------


def _resident(korwil, user):
    return Resident.objects.create(head_name="Warga Dossier", korwil=korwil)


@pytest.mark.parametrize(
    "key,value",
    [
        ("luas_lahan", "1e20"),
        ("luas_lahan", "-5"),
        ("luas_lahan", "abc"),
        ("umur", "200"),
        ("anak", "x"),
        ("jiwa", "99999"),
    ],
)
def test_resident_numbers_out_of_range_rejected(coordinator, korwil, key, value):
    resident = _resident(korwil, coordinator)
    response = login(coordinator).post(
        reverse("operasi-resident", args=[resident.pk]), {key: value}
    )
    assert response.status_code == 400
    assert key in response.json()["errors"]


def test_resident_optional_choices_and_numbers_can_be_cleared(coordinator, korwil):
    resident = _resident(korwil, coordinator)
    client = login(coordinator)
    url = reverse("operasi-resident", args=[resident.pk])
    data = {
        "gender": "P",
        "penggarapan": "disewakan",
        "umur": "40",
        "luas_lahan": "250,5",
    }
    assert client.post(url, data).status_code == 200
    resident.refresh_from_db()
    assert resident.gender == "P" and resident.age == 40
    assert str(resident.land_area_m2) == "250.50"
    cleared = {"gender": "", "penggarapan": "", "umur": "", "luas_lahan": ""}
    body = client.post(url, cleared).json()
    resident.refresh_from_db()
    assert resident.gender == "" and resident.cultivation_status == ""
    assert resident.age is None and resident.land_area_m2 is None
    assert body["gender"] == "" and body["land_area_m2"] is None
    # Kolom pilihan wajib tetap tidak bisa dikosongkan.
    assert client.post(url, {"zona": ""}).status_code == 200
    resident.refresh_from_db()
    assert resident.rtrw_zone == enums.RtrwZone.UNASSESSED


# --------------------------------------------------------------------------
# Impor warga: angka di luar batas kolom tidak membuat galat 500
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "column,value,message",
    [
        ("luas_lahan", "1e30", "terlalu besar"),
        ("luas_lahan", "NaN", "bukan angka"),
        ("luas_lahan", "-3", "bukan angka"),
        ("jiwa", "99999", "terlalu besar"),
    ],
)
def test_import_rejects_out_of_range_numbers(korwil, column, value, message):
    data = f"nama;korwil;{column}\nWarga Impor;A;{value}\n".encode()
    with pytest.raises(AssetImportError, match=message):
        import_residents(data, "warga.csv")


def test_import_dossier_columns(korwil):
    data = (
        "nama;korwil;jenis_kelamin;umur;anak;luas_lahan;penggarapan;zona\n"
        "Warga Impor;A;P;40000;2;1234,5;sewa;budidaya\n"
    ).encode()
    import_residents(data, "warga.csv")
    resident = Resident.objects.get(head_name="Warga Impor")
    assert resident.gender == "P"
    assert resident.age is None  # di luar batas, diabaikan
    assert resident.child_count == 2
    assert str(resident.land_area_m2) == "1234.50"
    assert resident.cultivation_status == enums.CultivationStatus.LEASED
    assert resident.rtrw_zone == enums.RtrwZone.CULTIVATION


# --------------------------------------------------------------------------
# Rekaman suara di panel & daftar kegiatan
# --------------------------------------------------------------------------


def test_voice_note_visible_in_admin_and_list(admin_user, field, korwil):
    point = inside(korwil)
    response = login(field).post(
        reverse("operasi-activities"),
        {
            "client_id": str(uuid.uuid4()),
            "judul": "Kunjungan bersuara",
            "jenis": enums.ActivityType.VISIT,
            "lat": point.y,
            "lng": point.x,
            "korwil": korwil.pk,
            "suara": SimpleUploadedFile(
                "rekaman.wav", b"RIFF\x24\x00\x00\x00WAVEfmt ", content_type="audio/wav"
            ),
        },
    )
    assert response.status_code == 201, response.content
    activity = Activity.objects.get(pk=response.json()["id"])
    voice_url = reverse("operasi-file", args=["kegiatan-suara", activity.pk])
    admin = login(admin_user)
    page = admin.get(reverse("admin:operasi_activity_change", args=[activity.pk]))
    assert page.status_code == 200
    assert voice_url in page.content.decode()
    listed = login(field).get(reverse("operasi-activities")).json()["results"]
    assert listed[0]["voice"] == voice_url
    assert admin.get(voice_url).status_code == 200


# --------------------------------------------------------------------------
# PWA: versi cache cangkang mengikuti isi berkas
# --------------------------------------------------------------------------


def test_shell_version_follows_file_content(field, korwil):
    from operasi.views import SHELL_STATIC, SW_VERSION
    from utils.pwa import shell_version

    version = shell_version(SW_VERSION, *SHELL_STATIC)
    assert version.startswith(f"{SW_VERSION}-") and len(version) > len(SW_VERSION) + 8
    assert shell_version(SW_VERSION, "operasi/komando.css") != shell_version(
        SW_VERSION, "operasi/komando.js"
    )
    body = login(field).get("/komando/sw.js").content.decode()
    assert f'var VERSION = "{version}";' in body


def test_field_app_shell_version_follows_file_content(admin_user):
    from asetlahan.field_views import SHELL_STATIC, SW_VERSION
    from utils.pwa import shell_version

    version = shell_version(SW_VERSION, *SHELL_STATIC)
    body = login(admin_user).get(reverse("asetlahan-field-sw")).content.decode()
    assert f'"{version}"' in body


# --------------------------------------------------------------------------
# Bilah tab muat di layar ponsel
# --------------------------------------------------------------------------


def test_tabbar_fits_columns(field, korwil):
    import re

    from django.contrib.staticfiles import finders

    page = login(field).get(reverse("operasi-command")).content.decode()
    tabbar = page.split('<nav class="tabbar"')[1].split("</nav>")[0]
    buttons = tabbar.count("<button")
    css = open(finders.find("operasi/komando.css")).read()
    rule = re.search(r"\.tabbar \{([^}]*)\}", css).group(1)
    # Kolom dibagi rata di antara tombol yang tampil (tombol tanpa izin
    # disembunyikan); lebih dari 8 tombol tidak muat di ponsel 320 px.
    assert "grid-auto-flow: column" in rule
    assert buttons <= 8
    assert 'data-tab="chat"' in tabbar
    for tab in ("peringkat", "struktur", "feed", "ai"):
        assert f'data-buka="{tab}"' in page
