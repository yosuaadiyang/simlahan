"""Permintaan tidak valid ke API harus dijawab 4xx, bukan galat server (500)."""

import json

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import translation
from rest_framework.test import APIClient

from plotsearch.views.map_service_proxy import owned_areas_wms_proxy


@pytest.mark.parametrize(
    "url_name",
    [
        "v1:lease-billing-periods",
        "v1:lease-preview-invoices-for-year",
        "v1:lease-rent-for-period",
    ],
)
@pytest.mark.parametrize(
    "query, expected_status",
    [("", 400), ("?lease=abc", 400), ("?lease=999999", 404)],
)
def test_lease_query_param_errors_are_client_errors(
    django_db_setup, admin_client, url_name, query, expected_status
):
    response = admin_client.get(reverse(url_name) + query)

    assert response.status_code == expected_status, response.content
    assert "detail" in response.json()


@pytest.mark.parametrize(
    "url_name",
    ["v1:lease-set-invoicing-state", "v1:lease-set-rent-info-completion-state"],
)
def test_lease_state_endpoints_without_lease_return_400(
    django_db_setup, admin_client, url_name
):
    response = admin_client.post(
        reverse(url_name), data={}, content_type="application/json"
    )

    assert response.status_code == 400, response.content


def test_contact_exists_without_identifier_returns_400(django_db_setup, admin_client):
    response = admin_client.get(reverse("v1:contact-exists"))

    assert response.status_code == 400, response.content


def test_decision_copy_without_parameters_returns_400(django_db_setup, admin_client):
    response = admin_client.post(reverse("v1:decision-copy-to-leases"))

    assert response.status_code == 400, response.content
    with translation.override("id"):
        response = admin_client.post(
            reverse("v1:decision-copy-to-leases") + "?decision=999999",
            HTTP_ACCEPT_LANGUAGE="id",
        )
    assert response.status_code == 404, response.content


def test_calculate_increase_validates_parameters(django_db_setup, admin_client):
    url = "/v1/functions/calculate_increase_with_360_day_calendar"

    response = admin_client.get(url)
    assert response.status_code == 400, response.content
    assert set(response.json()) == {"start_date", "end_date", "percentage", "amount"}

    response = admin_client.get(
        url,
        {
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "percentage": "10",
            "amount": "100000",
        },
    )
    assert response.status_code == 200, response.content
    assert "result" in response.json()


def test_invoice_create_without_lease_returns_400(django_db_setup, admin_client):
    response = admin_client.post(
        reverse("v1:invoice-list"), data={}, content_type="application/json"
    )

    assert response.status_code == 400, response.content
    assert "lease" in response.json()


@pytest.mark.parametrize(
    "url_name",
    [
        "v1:regulation-list",
        "v1:statisticaluse-list",
        "v1:supportivehousing-list",
        "v1:specialproject-list",
        "v1:reservationprocedure-list",
    ],
)
def test_name_lookup_requires_name(django_db_setup, admin_client, url_name):
    response = admin_client.post(
        reverse(url_name), data={}, content_type="application/json"
    )
    assert response.status_code == 400, response.content
    assert "name" in response.json()

    response = admin_client.post(
        reverse(url_name), data={"name": "Uji"}, content_type="application/json"
    )
    assert response.status_code == 201, response.content
    assert response.json()["name"] == "Uji"


@pytest.mark.parametrize("url_name", ["v1:target_status-pdf", "v1:area-search-pdf"])
def test_pdf_export_without_matches_returns_404(
    django_db_setup, admin_client, url_name
):
    response = admin_client.get(reverse(url_name), {"id": 999999})

    assert response.status_code == 404, response.content


def test_wms_proxy_error_response_is_renderable(rf, settings):
    settings.MAP_SERVICE_WMS_URL = None
    request = rf.get(reverse("v1:pub_owned_areas_wms_proxy"))

    response = owned_areas_wms_proxy(request)
    response.render()

    assert response.status_code == 500
    assert json.loads(response.content) == "Service misconfigured."


def test_users_permissions_ignore_codenames_of_other_apps(db, user_factory):
    """Izin "view_invoice" milik alokasi tidak boleh membuka fitur tagihan sewa."""
    user = user_factory(username="petugas_alokasi")
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="alokasi", codename="view_invoice"
        )
    )
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(reverse("v1:users-permissions"))

    assert response.status_code == 200
    codenames = {p["codename"] for p in response.json()["permissions"]}
    assert "view_invoice" not in codenames

    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="leasing", codename="view_invoice"
        )
    )
    user = type(user).objects.get(pk=user.pk)
    client.force_authenticate(user=user)
    codenames = {
        p["codename"]
        for p in client.get(reverse("v1:users-permissions")).json()["permissions"]
    }
    assert "view_invoice" in codenames
