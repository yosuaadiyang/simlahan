"""Nilai sangat besar tidak boleh membuat galat server (500)."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from pengadaan.models import DeadlineRule, InventoryItem, Valuation

BIG = Decimal("987654321987654321.99")


@pytest.mark.django_db
def test_inventory_total_beyond_column_size_is_serialized(admin_client, parcel):
    InventoryItem.objects.create(
        parcel=parcel,
        item_type="building",
        description="Gedung",
        quantity=Decimal("987654321987.99"),
        unit="m2",
        unit_value=BIG,
    )
    response = admin_client.get(reverse("v1:inventoryitem-list"), {"parcel": parcel.pk})
    assert response.status_code == 200, response.content
    item = response.json()["results"][0]
    total = Decimal(item["quantity"]) * Decimal(item["unit_value"])
    assert Decimal(item["total_value"]) == total.quantize(Decimal("0.01"))


@pytest.mark.django_db
def test_valuation_total_overflow_is_rejected_not_500(admin_client, parcel):
    payload = {
        "parcel": parcel.pk,
        "appraiser_name": "KJPP Uji",
        "valuation_date": "2026-01-10",
        "value_land": str(BIG),
        "value_building": str(BIG),
    }
    response = admin_client.post(
        reverse("v1:valuation-list"), payload, content_type="application/json"
    )
    assert response.status_code == 400, response.content
    assert "terlalu besar" in str(response.json())
    assert not Valuation.objects.exists()

    payload["value_building"] = "1000"
    response = admin_client.post(
        reverse("v1:valuation-list"), payload, content_type="application/json"
    )
    assert response.status_code == 201, response.content
    assert Decimal(response.json()["total_value"]) == BIG + 1000


@pytest.mark.django_db
def test_valuation_model_clean_checks_total(parcel):
    valuation = Valuation(parcel=parcel, value_land=BIG, value_plants=BIG)
    with pytest.raises(ValidationError):
        valuation.clean()


@pytest.mark.django_db
def test_deadline_rule_amount_is_limited(admin_client, seeded_rules):
    rule = DeadlineRule.objects.first()
    response = admin_client.patch(
        reverse("v1:deadlinerule-detail", kwargs={"pk": rule.pk}),
        {"amount": 2147483000},
        content_type="application/json",
    )
    assert response.status_code == 400, response.content
    response = admin_client.get(reverse("v1:acquisitionproject-list"))
    assert response.status_code == 200
