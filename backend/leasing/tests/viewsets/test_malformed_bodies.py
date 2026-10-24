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


@pytest.mark.django_db
def test_out_of_range_value_is_bad_request(admin_client):
    from leasing.models import Municipality

    municipality = Municipality.objects.create(
        id=987654, name="Kota Uji", identifier="987654"
    )
    response = admin_client.patch(
        reverse("v1:municipality-detail", args=[municipality.id]),
        json.dumps({"id": 10**30}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert admin_client.get(reverse("v1:municipality-list")).status_code == 200


@pytest.mark.django_db
def test_notice_period_duration_must_be_iso8601(admin_client):
    from leasing.models import NoticePeriod

    period = NoticePeriod.objects.create(
        name="Tiga bulan", type="time_period", duration="P3M"
    )
    url = reverse("v1:noticeperiod-detail", args=[period.id])
    response = admin_client.patch(
        url, json.dumps({"duration": "x"}), content_type="application/json"
    )
    assert response.status_code == 400
    period.refresh_from_db()
    assert period.duration == "P3M"
    assert admin_client.get(reverse("v1:noticeperiod-list")).status_code == 200
