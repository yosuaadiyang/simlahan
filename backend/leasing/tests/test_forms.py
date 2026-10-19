import datetime

import pytest
from django.utils import translation

from leasing.enums import LeaseState, TenantContactType


@pytest.mark.django_db
def test_lease_search_form_no_fields_required():
    from leasing.forms import LeaseSearchForm

    form = LeaseSearchForm({})
    assert form.is_valid()


@pytest.mark.parametrize(
    "business_id, expected",
    [
        (None, True),
        ("", True),
        ("0", False),
        (123, False),
        ("something", False),
        ("1234567-8", False),
        ("012345678901000", True),
        ("01.234.567.8-901.000", True),
        ("0012345678901000", True),
        ("123456", False),
    ],
)
@pytest.mark.django_db
def test_lease_search_form_business_id(business_id, expected):
    from leasing.forms import LeaseSearchForm

    form = LeaseSearchForm({"business_id": business_id})

    assert expected == form.is_valid()


@pytest.mark.parametrize(
    "tenantcontact_type, expected",
    [
        (None, True),
        ("", True),
        ("0", False),
        (123, False),
        ("something", False),
        (TenantContactType.TENANT.value, True),
        (TenantContactType.BILLING.value, True),
        (TenantContactType.CONTACT.value, True),
        (
            ",".join([TenantContactType.TENANT.value, TenantContactType.CONTACT.value]),
            True,
        ),
        (
            " , ".join(
                [TenantContactType.TENANT.value, TenantContactType.CONTACT.value]
            ),
            True,
        ),
        (
            ";".join([TenantContactType.TENANT.value, TenantContactType.CONTACT.value]),
            False,
        ),
        (
            " ".join([TenantContactType.TENANT.value, TenantContactType.CONTACT.value]),
            False,
        ),
    ],
)
@pytest.mark.django_db
def test_lease_search_form_tenantcontact_type_choices(tenantcontact_type, expected):
    from leasing.forms import LeaseSearchForm

    form = LeaseSearchForm({"tenantcontact_type": tenantcontact_type})

    assert expected == form.is_valid()


@pytest.mark.parametrize(
    "lease_type, expected",
    [(None, True), ("", True), ("0", False), (123, False), (1, True), (2, True)],
)
@pytest.mark.django_db
def test_lease_search_form_lease_type_choices(lease_type, expected):
    from leasing.forms import LeaseSearchForm

    form = LeaseSearchForm({"lease_type": lease_type})

    assert expected == form.is_valid()


@pytest.mark.parametrize(
    "lease_state, expected",
    [
        (None, True),
        ("", True),
        ("0", False),
        (123, False),
        ("something", False),
        (LeaseState.LEASE.value, True),
        (LeaseState.RESERVATION.value, True),
        (",".join([LeaseState.LEASE.value, LeaseState.RESERVATION.value]), True),
        (" , ".join([LeaseState.LEASE.value, LeaseState.RESERVATION.value]), True),
        (";".join([LeaseState.LEASE.value, LeaseState.RESERVATION.value]), False),
        (" ".join([LeaseState.LEASE.value, LeaseState.RESERVATION.value]), False),
    ],
)
@pytest.mark.django_db
def test_lease_search_form_lease_state_choices(lease_state, expected):
    from leasing.forms import LeaseSearchForm

    form = LeaseSearchForm({"lease_state": lease_state})

    assert expected == form.is_valid()


@pytest.mark.parametrize("value", ["1.2.2026", "01.02.2026", "2026-02-01"])
def test_lease_search_form_accepts_spa_date_formats(value):
    """Tanggal pencarian dari SPA ("d.m.yyyy") harus terbaca di lokal Indonesia."""
    from leasing.forms import LeaseSearchForm

    with translation.override("id"):
        form = LeaseSearchForm(
            {"lease_start_date_start": value, "decision_date": value}
        )
        assert form.is_valid(), form.errors

    assert form.cleaned_data["lease_start_date_start"] == datetime.date(2026, 2, 1)
    assert form.cleaned_data["decision_date"] == datetime.date(2026, 2, 1)
