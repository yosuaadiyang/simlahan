"""Beranda, detail Korwil, Historis, peringkat bertingkat, dan rincian kinerja."""

import datetime
import io
import zipfile
from decimal import Decimal

import pytest
from django.test import override_settings
from django.utils import timezone

from operasi import dashboard, enums, ranking, services
from operasi.models import Activity, LandAreaChange, OfficerProfile, Resident
from operasi.tests.conftest import inside, login, make_user
from utils.group_permissions import UserGroup

pytestmark = pytest.mark.django_db

BASE = "/komando/api/"
Stance = enums.Stance


def komsos(user, korwil, residents=(), registered=(), days_ago=0):
    item = Activity.objects.create(
        korwil=korwil,
        title="Komsos",
        activity_type=enums.ActivityType.KOMSOS,
        started_at=timezone.now() - datetime.timedelta(days=days_ago, hours=1),
        location=inside(korwil),
        reported_by=user,
    )
    item.residents.add(*residents, *registered)
    for resident in registered:
        resident.registered_activity = item
        resident.save(update_fields=["registered_activity"])
    return item


def resident(korwil, name="Warga", stance=Stance.UNKNOWN, **extra):
    return Resident.objects.create(
        head_name=name, korwil=korwil, stance=stance, **extra
    )


# --------------------------------------------------------------------------
# Periode & riwayat luas lahan
# --------------------------------------------------------------------------


def test_period_bounds_day_quarter_year():
    today = datetime.date(2026, 8, 14)
    assert services.period_bounds("hari", today) == (today, today)
    assert services.period_bounds("kuartal", today) == (
        datetime.date(2026, 7, 1),
        datetime.date(2026, 9, 30),
    )
    assert services.period_bounds("kuartal", datetime.date(2026, 12, 31)) == (
        datetime.date(2026, 10, 1),
        datetime.date(2026, 12, 31),
    )
    assert services.period_bounds("tahun", today) == (
        datetime.date(2026, 1, 1),
        datetime.date(2026, 12, 31),
    )
    assert services.period_bounds("asal", today) == (
        datetime.date(2026, 8, 1),
        datetime.date(2026, 8, 31),
    )


def test_land_area_change_recorded_once_per_real_change(field, korwil):
    item = resident(korwil, land_area_m2=Decimal("100"))
    assert not LandAreaChange.objects.exists()
    client = login(field)
    response = client.post(f"{BASE}warga/{item.pk}/", {"luas_lahan": "150.5"})
    assert response.status_code == 200, response.content
    change = LandAreaChange.objects.get()
    assert change.old_area_m2 == Decimal("100.00")
    assert change.new_area_m2 == Decimal("150.50")
    assert change.delta_m2 == Decimal("50.50")
    assert change.changed_by == field
    # Nilai sama (beda format) dan simpan dengan field yang tidak dimuat: tidak dicatat.
    client.post(f"{BASE}warga/{item.pk}/", {"luas_lahan": "150.50"})
    partial = Resident.objects.only("pk", "head_name", "number").get(pk=item.pk)
    partial.head_name = "Warga Baru"
    partial.save(update_fields=["head_name"])
    assert LandAreaChange.objects.count() == 1


# --------------------------------------------------------------------------
# Beranda & detail Korwil
# --------------------------------------------------------------------------


def test_home_is_scoped_and_trend_reconstructs_past_stance(
    field, korwil, korwil_b, manager
):
    old = resident(korwil, "Lama", Stance.NEUTRAL)
    Resident.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - datetime.timedelta(days=30)
    )
    old.refresh_from_db()
    old.stance = Stance.SUPPORT
    old.save()
    resident(korwil, "Baru", Stance.OPPOSE)
    resident(korwil_b, "Korwil B", Stance.SUPPORT)

    data = login(field).get(f"{BASE}beranda/").json()
    assert [row["code"] for row in data["korwils"]] == ["A"]
    assert data["counts"]["total"] == 2
    assert data["stances"][Stance.SUPPORT] == 1
    assert data["stances"][Stance.OPPOSE] == 1
    first, last = data["trend"][0], data["trend"][-1]
    # 11 pekan lalu belum ada warga; 3 pekan lalu warga lama masih netral.
    assert first["total"] == 0 and first["pro_pct"] is None
    three_weeks = data["trend"][-4]
    assert three_weeks["total"] == 1 and three_weeks[Stance.NEUTRAL] == 1
    assert last["total"] == 2 and last["pro_pct"] == 50 and last["contra_pct"] == 50

    everyone = login(manager).get(f"{BASE}beranda/").json()
    assert {row["code"] for row in everyone["korwils"]} == {"A", "B"}


def test_korwil_detail_hides_scores_outside_team(field, coordinator, korwil, korwil_b):
    resident(korwil, "Ahmad", Stance.SUPPORT)
    detail = login(field).get(f"{BASE}korwil/{korwil.pk}/").json()
    scores = {m["id"]: m["score"] for m in detail["members"]}
    assert scores[field.pk] is not None
    assert scores[coordinator.pk] is None
    assert detail["show_residents"] is True
    assert detail["residents"][Stance.SUPPORT][0]["name"] == "Ahmad"
    # Korwil lain: tidak terlihat.
    assert login(field).get(f"{BASE}korwil/{korwil_b.pk}/").status_code == 404
    # Koordinator melihat skor seluruh anggota Korwil yang dipimpinnya.
    led = login(coordinator).get(f"{BASE}korwil/{korwil.pk}/").json()
    assert all(m["score"] is not None for m in led["members"])


# --------------------------------------------------------------------------
# Historis
# --------------------------------------------------------------------------


def test_history_gated_and_counts_new_vs_repeat_komsos(
    field, coordinator, korwil, korwil_b, other_field
):
    known = resident(korwil, "Kenal", Stance.NEUTRAL, land_area_m2=Decimal("200"))
    fresh = resident(korwil, "Baru")
    komsos(field, korwil, residents=[known], registered=[fresh])
    komsos(field, korwil, residents=[known, fresh])
    komsos(other_field, korwil_b)
    known._changed_by = field
    known.stance = Stance.SUPPORT
    known.land_area_m2 = Decimal("120")
    known.save()
    fresh.stance = Stance.OPPOSE
    fresh.save()

    assert login(field).get(f"{BASE}historis/").status_code == 403
    response = login(coordinator).get(f"{BASE}historis/", {"periode": "tahun"})
    assert response.status_code == 200
    data = response.json()
    assert [
        (r["user_id"], r["activities"], r["new"], r["repeat"], r["unique"])
        for r in data["komsos"]
    ] == [(field.pk, 2, 1, 3, 2)]
    assert data["stance"]["totals"] == {
        "membaik": 1,
        "memburuk": 0,
        "teridentifikasi": 1,
        "lainnya": 0,
    }
    assert data["stance"]["per_korwil"] == [
        {"korwil": "A", "membaik": 1, "memburuk": 0, "teridentifikasi": 1, "net": 1}
    ]
    assert data["land"]["decreased"] == 1 and data["land"]["net_m2"] == -80.0
    assert data["land"]["items"][0]["by"]
    # Filter Korwil di luar wilayah ditolak.
    assert (
        login(coordinator).get(f"{BASE}historis/", {"korwil": korwil_b.pk}).status_code
        == 404
    )


# --------------------------------------------------------------------------
# Peringkat
# --------------------------------------------------------------------------


def test_tiers(field, coordinator, manager, korwil, units):
    supervisor = make_user("aset", UserGroup.PETUGAS_ASET, units=[units[0]])
    tiers = ranking.tiers_for([field, coordinator, manager, supervisor])
    assert tiers == {
        field.pk: "lapangan",
        coordinator.pk: "koordinator",
        manager.pk: "manajemen",
        supervisor.pk: "manajemen",
    }
    # Koordinator yang membawahi petugas di luar Korwil-nya naik ke manajemen.
    outsider = make_user("luar", UserGroup.PETUGAS_LAPANGAN, units=[units[0]])
    OfficerProfile.objects.create(user=outsider, supervisor=coordinator)
    assert ranking.tiers_for([coordinator])[coordinator.pk] == "manajemen"


def test_leaderboard_filters_badges_and_views(manager, coordinator, field, korwil):
    komsos(field, korwil, residents=[resident(korwil)])
    client = login(manager)
    data = client.get(f"{BASE}peringkat/", {"periode": "bulan"}).json()
    ids = {r["user_id"] for r in data["results"]}
    assert {field.pk, coordinator.pk} <= ids
    row = next(r for r in data["results"] if r["user_id"] == field.pk)
    assert row["tier"] == "lapangan" and row["korwils"] == ["A"]
    assert row["komsos"] == 1 and "komsos" in row["badges"]
    assert set(data["badges"]) == set(ranking.BADGES)
    assert data["count"] == len(data["results"])
    assert sum(data["grades"].values()) == data["count"]

    only_field = client.get(f"{BASE}peringkat/", {"tier": "lapangan"}).json()
    assert [r["user_id"] for r in only_field["results"]] == [field.pk]
    assert only_field["results"][0]["rank"] == 1

    in_korwil = client.get(f"{BASE}peringkat/", {"korwil": korwil.pk}).json()
    assert {r["user_id"] for r in in_korwil["results"]} == {field.pk, coordinator.pk}

    bottom = client.get(f"{BASE}peringkat/", {"tampilan": "bawah"}).json()
    assert bottom["results"][0]["score"] <= bottom["results"][-1]["score"]
    assert len(bottom["results"]) <= ranking.VIEW_SIZE
    # Nilai tidak dikenal diabaikan, bukan galat.
    loose = client.get(f"{BASE}peringkat/", {"tier": "x", "periode": "y"})
    assert loose.status_code == 200


def test_leaderboard_korwil_filter_limited_to_scope(field, korwil, korwil_b):
    response = login(field).get(f"{BASE}peringkat/", {"korwil": korwil_b.pk})
    assert response.status_code == 404
    data = login(field).get(f"{BASE}peringkat/").json()
    assert [r["user_id"] for r in data["results"]] == [field.pk]


def test_leaderboard_excel_is_formula_safe(manager, field, korwil):
    field.first_name = '=HYPERLINK("http://contoh.invalid","klik")'
    field.save()
    response = login(manager).get(f"{BASE}peringkat/excel/", {"periode": "bulan"})
    assert response.status_code == 200
    assert "peringkat-" in response["Content-Disposition"]
    book = zipfile.ZipFile(io.BytesIO(response.content))
    sheets = [n for n in book.namelist() if n.startswith("xl/worksheets/sheet")]
    xml = "".join(book.read(name).decode() for name in sheets)
    assert "<f>" not in xml
    assert "HYPERLINK" in book.read("xl/sharedStrings.xml").decode()


# --------------------------------------------------------------------------
# Rincian kinerja & wawasan
# --------------------------------------------------------------------------


def test_performance_detail_and_scope(field, coordinator, other_field, korwil):
    komsos(field, korwil)
    data = (
        login(coordinator)
        .get(
            f"{BASE}kinerja/", {"rinci": "1", "petugas": field.pk, "periode": "minggu"}
        )
        .json()
    )
    detail = data["detail"]
    assert [r["key"] for r in detail["radar"]] == [
        "hadir",
        "tepat",
        "volume",
        "tugas",
        "lengkap",
    ]
    assert len(detail["heat"]) == ranking.HEAT_DAYS
    assert sum(d["activities"] for d in detail["daily"]) == 1
    assert detail["points"] and detail["points"][0]["kind"] == "kegiatan"
    assert detail["recent"][0]["title"] == "Komsos"
    # Tanpa rinci: tetap ringan seperti sebelumnya.
    assert "detail" not in login(field).get(f"{BASE}kinerja/").json()
    # Petugas di luar tim tidak bisa dilihat.
    response = login(coordinator).get(f"{BASE}kinerja/", {"petugas": other_field.pk})
    assert response.status_code == 404
    response = login(field).get(f"{BASE}kinerja/", {"petugas": coordinator.pk})
    assert response.status_code == 404


@override_settings(ANTHROPIC_API_KEY="")
def test_insights_use_rule_based_fallback_and_throttle(coordinator, field, korwil):
    client = login(coordinator)
    assert client.get(f"{BASE}peringkat/wawasan/").status_code == 405
    board = client.post(f"{BASE}peringkat/wawasan/", {"periode": "bulan"}).json()
    assert board["ai"] is False and "Teratas" in board["text"]
    personal = client.post(
        f"{BASE}kinerja/wawasan/", {"periode": "bulan", "petugas": field.pk}
    ).json()
    assert personal["ai"] is False and "Terkuat" in personal["text"]
    for _i in range(18):
        client.post(f"{BASE}kinerja/wawasan/")
    assert client.post(f"{BASE}kinerja/wawasan/").status_code == 429


def test_config_flags_and_tabs(field, coordinator, korwil):
    from django.test import RequestFactory

    from operasi.views import _config

    request = RequestFactory().get("/komando/", {"tab": "historis"})
    request.user = coordinator
    config = _config(request)
    assert config["perms"]["historis"] is True
    assert config["initialTab"] == "historis"
    assert config["urls"]["korwilDetail"].endswith("/korwil/0/")
    request.user = field
    assert _config(request)["perms"]["historis"] is False
    assert dashboard.can_view_history(field) is False
