import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from asetlahan import enums, scope
from asetlahan.models import (
    AssetValuation,
    EncroachmentActionLog,
    EncroachmentCase,
    Grievance,
    GrievanceCategory,
    HeirMember,
    Heirship,
    LandAsset,
    TaxObligation,
    Tender,
    ValuationItem,
)

pytestmark = pytest.mark.django_db


def test_asset_area_is_computed_from_geometry(make_asset):
    asset = make_asset()
    # ±111 m × 111 m di dekat khatulistiwa.
    assert Decimal("12000") < asset.area_m2 < Decimal("12700")


def test_numbers_are_sequential_per_prefix(seeded):
    first = Grievance.objects.create(complainant_name="A", subject="S", description="D")
    second = Grievance.objects.create(
        complainant_name="B", subject="S", description="D"
    )
    year = timezone.localdate().year
    assert first.number == f"ADU-{year}-0001"
    assert second.number == f"ADU-{year}-0002"
    assert len(first.access_code) == 8 and first.access_code != second.access_code


def test_grievance_due_date_uses_category_sla_then_module_setting(seeded):
    category = GrievanceCategory.objects.create(name="Uji", sla_days=3)
    with_category = Grievance.objects.create(
        complainant_name="A", subject="S", description="D", category=category
    )
    without = Grievance.objects.create(
        complainant_name="B", subject="S", description="D"
    )
    today = timezone.localdate()
    assert with_category.due_date == today + datetime.timedelta(days=3)
    assert without.due_date == today + datetime.timedelta(
        days=seeded.grievance_sla_days
    )
    without.status = enums.GrievanceStatus.RESOLVED
    without.save()
    assert without.resolved_on == today
    without.status = enums.GrievanceStatus.IN_PROGRESS
    without.save()
    assert without.resolved_on is None


def test_tax_amount_from_njop_and_rate(make_asset):
    asset = make_asset(area_m2=Decimal("1000"), njop_per_m2=Decimal("100000"))
    tax = TaxObligation.objects.create(
        asset=asset,
        rate_percent=Decimal("0.5"),
        deduction=Decimal("10000000"),
        due_date=timezone.localdate(),
    )
    assert tax.amount == Decimal("450000.00")
    assert tax.is_overdue is False


def test_valuation_totals_include_items(make_asset):
    asset = make_asset(area_m2=Decimal("200"))
    valuation = AssetValuation.objects.create(
        asset=asset, land_value_per_m2=Decimal("500000")
    )
    ValuationItem.objects.create(
        valuation=valuation,
        description="Rumah",
        quantity=Decimal("50"),
        unit_value=Decimal("2000000"),
    )
    valuation.recompute()
    valuation.refresh_from_db()
    assert valuation.land_value == Decimal("100000000.00")
    assert valuation.structures_value == Decimal("100000000.00")
    assert valuation.total_value == Decimal("200000000.00")


def test_heirship_rejects_cycles(make_asset):
    heirship = Heirship.objects.create(asset=make_asset(), decedent_name="Pewaris")
    parent = HeirMember.objects.create(heirship=heirship, name="Anak")
    child = HeirMember.objects.create(heirship=heirship, name="Cucu", parent=parent)
    parent.parent = child
    with pytest.raises(ValidationError):
        parent.clean()


def test_tender_requires_object_and_valid_window(seeded):
    now = timezone.now()
    tender = Tender(title="T", description="D", open_at=now, close_at=now)
    with pytest.raises(ValidationError):
        tender.clean()


def test_encroachment_action_updates_status(make_asset):
    case = EncroachmentCase.objects.create(title="Pagar liar", asset=make_asset())
    EncroachmentActionLog.objects.create(
        case=case, action=enums.EncroachmentAction.WARNING_1
    )
    case.refresh_from_db()
    assert case.status == enums.EncroachmentStatus.WARNING_1


def test_encroachment_finds_asset_from_location(make_asset):
    asset = make_asset()
    case = EncroachmentCase.objects.create(
        title="Temuan", location=asset.geometry.centroid
    )
    assert case.asset == asset


def test_scope_limits_officer_to_own_units(make_asset, officer, admin, units):
    own = make_asset(service_unit=units[0])
    other = make_asset(service_unit=units[1])
    shared = make_asset()
    visible = set(scope.scoped(LandAsset.objects.all(), officer))
    assert visible == {own, shared}
    assert set(scope.scoped(LandAsset.objects.all(), admin)) == {own, other, shared}
    assert scope.default_unit(officer) == units[0]
