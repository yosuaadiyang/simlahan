"""Nominal & luas sangat besar: tampil utuh, rapi, dan tidak membuat galat 500."""

import io
import zipfile
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from asetlahan import enums, reports
from asetlahan.models import (
    AssetValuation,
    LandTransaction,
    TaxObligation,
    ValuationItem,
)

pytestmark = pytest.mark.django_db

BIG = Decimal("987654321987654321.99")
BIG_AREA = Decimal("98765432198765.43")


@pytest.fixture
def big_asset(make_asset):
    asset = make_asset(area_m2=BIG_AREA, acquisition_cost=BIG)
    LandTransaction.objects.create(
        transaction_type=enums.TransactionType.LEASE_INCOME, amount=BIG, asset=asset
    )
    return asset


def test_dashboard_breaks_long_numbers_instead_of_overflowing(client, admin, big_asset):
    client.force_login(admin)
    response = client.get(reverse("asetlahan-dashboard"))
    assert response.status_code == 200
    html = response.content.decode()
    # Titik ribuan diberi <wbr> sehingga nominal pindah baris di dalam kartu.
    assert "Rp987.<wbr>654.<wbr>321.<wbr>987.<wbr>654.<wbr>322" in html


def test_report_keeps_every_digit(client, admin, big_asset):
    client.force_login(admin)
    url = reverse("asetlahan-reports")
    response = client.get(url, {"data": "aset"})
    assert response.status_code == 200
    preview = " ".join(" ".join(map(str, row)) for row in response.context["preview"])
    assert "987.654.321.987.654.321,99" in preview
    assert "98.765.432.198.765,43" in preview

    response = client.get(url, {"data": "aset", "format": "csv"})
    assert "987654321987654321.99" in response.content.decode("utf-8-sig")

    response = client.get(url, {"data": "aset", "format": "xlsx"})
    with zipfile.ZipFile(io.BytesIO(response.content)) as workbook:
        strings = workbook.read("xl/sharedStrings.xml").decode()
    # Di atas 15 digit Excel tidak presisi, jadi ditulis sebagai teks utuh.
    assert "987654321987654321.99" in strings


def test_display_cell_formats_decimals():
    assert reports.display_cell(Decimal("1234567.5")) == "1.234.567,5"
    assert reports.display_cell(Decimal("10")) == "10"
    assert reports.display_cell("teks") == "teks"


def test_valuation_with_huge_land_value_is_rejected(big_asset):
    valuation = AssetValuation(
        asset=big_asset, valuation_date="2026-01-01", land_value_per_m2=BIG
    )
    with pytest.raises(ValidationError):
        valuation.clean()
    item = ValuationItem(
        valuation=valuation, description="Gedung", quantity=BIG_AREA, unit_value=BIG
    )
    with pytest.raises(ValidationError):
        item.clean()


def test_valuation_admin_rejects_overflowing_items(client, admin, make_asset):
    asset = make_asset(area_m2=Decimal("100"))
    client.force_login(admin)
    response = client.post(
        reverse("admin:asetlahan_assetvaluation_add"),
        {
            "asset": asset.pk,
            "valuation_date": "2026-01-01",
            "method": enums.ValuationMethod.choices[0][0],
            "land_value_per_m2": "1000",
            "items-TOTAL_FORMS": "2",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-item_type": enums.ValuationItemType.choices[0][0],
            "items-0-description": "Gedung A",
            "items-0-quantity": "900000000",
            "items-0-unit_value": "900000000000",
            "items-1-item_type": enums.ValuationItemType.choices[0][0],
            "items-1-description": "Gedung B",
            "items-1-quantity": "900000000",
            "items-1-unit_value": "900000000000",
        },
    )
    assert response.status_code == 200
    assert "terlalu besar" in response.content.decode()
    assert not AssetValuation.objects.exists()


def test_tax_with_overflowing_computed_amount_is_rejected(big_asset):
    big_asset.njop_per_m2 = BIG
    big_asset.save()
    tax = TaxObligation(
        asset=big_asset,
        tax_type=enums.TaxType.choices[0][0],
        period=2026,
        rate_percent=Decimal("0.5"),
        due_date="2026-08-31",
    )
    with pytest.raises(ValidationError):
        tax.clean()


def test_admin_lists_group_thousands(client, admin, big_asset):
    client.force_login(admin)
    response = client.get(reverse("admin:asetlahan_landasset_changelist"))
    assert response.status_code == 200
    assert "98.765.432.198.765,43" in response.content.decode()
