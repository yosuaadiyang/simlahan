import datetime
from decimal import Decimal

import pytest

from pengadaan import enums
from pengadaan.deadlines import collect_deadlines
from pengadaan.models import (
    Deliberation,
    DeliberationResult,
    Holiday,
    Objection,
    Valuation,
    apply_rule,
)
from pengadaan.workdays import add_workdays, add_years, workdays_between

D = datetime.date


@pytest.mark.django_db
def test_add_workdays_skips_weekend_and_holidays():
    Holiday.objects.create(date=D(2025, 8, 18), name="Cuti bersama")
    # Jumat 15 Agustus 2025 + 1 hari kerja: Sabtu/Minggu, Senin 18 cuti bersama
    assert add_workdays(D(2025, 8, 15), 1) == D(2025, 8, 19)
    # Tanpa libur: Jumat + 1 = Senin
    assert add_workdays(D(2025, 8, 8), 1) == D(2025, 8, 11)
    assert add_workdays(D(2025, 8, 8), 0) == D(2025, 8, 8)


@pytest.mark.django_db
def test_workdays_between_is_inverse_of_add_workdays():
    Holiday.objects.create(date=D(2025, 12, 25), name="Natal")
    Holiday.objects.create(date=D(2025, 12, 26), name="Cuti bersama")
    start = D(2025, 12, 19)
    end = add_workdays(start, 14)
    assert workdays_between(start, end) == 14
    assert workdays_between(end, start) == -14
    assert workdays_between(start, start) == 0


def test_add_years_handles_leap_day():
    assert add_years(D(2024, 2, 29), 3) == D(2027, 2, 28)
    assert add_years(D(2025, 1, 10), 3) == D(2028, 1, 10)


@pytest.mark.django_db
def test_seeded_rules_follow_law(seeded_rules):
    # Keberatan ke PN: 14 hari kerja setelah musyawarah (UU 2/2012 Ps. 38(1)).
    held = D(2026, 3, 2)  # Senin, sebelum libur Nyepi/Idulfitri 2026
    due = apply_rule("compensation_objection", held)
    assert due == add_workdays(held, 14)
    # Libur Nyepi & Idulfitri 2026 (18–24 Maret) tidak dihitung.
    assert due == D(2026, 3, 27)
    # Penlok berlaku 3 tahun.
    assert apply_rule("penlok_validity", D(2025, 5, 2)) == D(2028, 5, 2)
    assert apply_rule("unknown_rule", held) is None
    assert apply_rule("penlok_validity", None) is None


@pytest.mark.django_db
def test_penlok_expiry_with_extension(project):
    project.location_decree_date = D(2025, 5, 2)
    project.save()
    assert project.location_decree_expires_on == D(2028, 5, 2)
    project.location_decree_extended = True
    project.save()
    assert project.location_decree_expires_on == D(2029, 5, 2)


@pytest.mark.django_db
def test_collect_deadlines_for_deliberation_and_objection(project, parcel, party):
    today = D(2026, 1, 5)
    Valuation.objects.create(
        parcel=parcel,
        status=enums.ValuationStatus.FINAL,
        submitted_on=D(2026, 1, 2),
        value_land=Decimal("1000000"),
    )
    items = collect_deadlines(today=today)
    kinds = {i.kind for i in items}
    assert "deliberation" in kinds
    deliberation_item = next(i for i in items if i.kind == "deliberation")
    assert deliberation_item.due_date == add_workdays(D(2026, 1, 2), 30)
    assert deliberation_item.parcel_number == parcel.parcel_number

    deliberation = Deliberation.objects.create(project=project, held_on=D(2026, 1, 6))
    DeliberationResult.objects.create(
        deliberation=deliberation,
        parcel=parcel,
        party=party,
        outcome=enums.DeliberationOutcome.REJECTED,
    )
    items = collect_deadlines(today=today)
    kinds = {i.kind for i in items}
    assert "deliberation" not in kinds
    objection_item = next(i for i in items if i.kind == "compensation_objection")
    assert objection_item.due_date == add_workdays(D(2026, 1, 6), 14)

    Objection.objects.create(
        project=project,
        parcel=parcel,
        party=party,
        objection_type=enums.ObjectionType.COMPENSATION,
        status=enums.ObjectionStatus.FILED,
        filed_on=D(2026, 1, 10),
        received_on=D(2026, 1, 12),
    )
    items = collect_deadlines(today=today)
    kinds = {i.kind for i in items}
    assert "compensation_objection" not in kinds
    court_item = next(i for i in items if i.kind == "court_decision")
    assert court_item.due_date == add_workdays(D(2026, 1, 12), 30)


@pytest.mark.django_db
def test_deadline_states(project, parcel):
    Valuation.objects.create(
        parcel=parcel,
        status=enums.ValuationStatus.FINAL,
        submitted_on=D(2026, 1, 2),
    )
    due = add_workdays(D(2026, 1, 2), 30)
    (item,) = collect_deadlines(today=due + datetime.timedelta(days=1))
    assert item.state == "overdue"
    (item,) = collect_deadlines(today=D(2026, 1, 5))
    assert item.state == "upcoming"
    (item,) = collect_deadlines(today=due - datetime.timedelta(days=1))
    assert item.state == "due_soon"
