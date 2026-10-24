"""Badan permintaan yang salah bentuk dijawab 400, bukan galat 500."""

import json

import pytest
from django.urls import reverse


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name", ["v1:lease-list", "v1:invoice-list", "v1:ui_data-list"]
)
def test_list_body_is_rejected(admin_client, name):
    response = admin_client.post(
        reverse(name), json.dumps([]), content_type="application/json"
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_intended_use_can_be_created_through_api(admin_client, service_unit_factory):
    unit = service_unit_factory()
    response = admin_client.post(
        reverse("v1:intendeduse-list"),
        json.dumps({"name": "Industri", "service_unit": unit.id}),
        content_type="application/json",
    )
    assert response.status_code == 201, response.content
