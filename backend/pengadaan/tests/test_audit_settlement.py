"""Penyelesaian ganti kerugian (konsinyasi & pembayaran) tidak bisa dipakai
untuk melompati validasi Ketua Pelaksana atau meninggalkan status basi."""

import datetime
import io
import itertools
from decimal import Decimal

import pytest
from django.contrib.admin.sites import site as admin_site
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from pengadaan import enums
from pengadaan.models import (
    AcquisitionParcel,
    Compensation,
    CompensationPayment,
    Consignment,
    EntitledParty,
)
from utils.group_permissions import UserGroup

API = "/v1/pengadaan"
D = datetime.date
_counter = itertools.count()

pytestmark = pytest.mark.django_db

DEPOSIT = {
    "reason": "refused",
    "status": "deposited",
    "decree_number": "1/Pdt.P.Kons/2026/PN",
    "deposited_on": "2026-02-01",
    "amount": "1000",
}


@pytest.fixture
def client_in(db, django_user_model):
    for group in UserGroup:
        Group.objects.get_or_create(id=group.value, defaults={"name": group.name})
    call_command("set_group_model_permissions", stdout=io.StringIO())

    def _make(*group_ids):
        user = django_user_model.objects.create_user(
            username=f"penyelesaian{next(_counter)}", password="RahasiaKuat123!"
        )
        for gid in group_ids:
            user.groups.add(Group.objects.get(id=gid))
        client = APIClient()
        client.force_authenticate(user)
        return client

    return _make


def _compensation(parcel, party, status, amount="1000"):
    return Compensation.objects.create(
        parcel=parcel,
        party=party,
        amount=Decimal(amount),
        status=status,
        validated_on=(
            D(2026, 1, 5) if status == enums.CompensationStatus.VALIDATED else None
        ),
    )


def _parcel_status(parcel):
    return AcquisitionParcel.all_objects.get(pk=parcel.pk).status


# NV-28: konsinyasi dititipkan butuh bukti & ganti rugi tervalidasi


def test_deposited_consignment_requires_validated_compensation(
    client_in, parcel, party
):
    compensation = _compensation(parcel, party, enums.CompensationStatus.DETERMINED)
    vac = client_in(UserGroup.PERINTALAKIMIES)

    for payload in (
        {"parcel": parcel.id, **DEPOSIT},  # tanpa pihak = seluruh bidang
        {"parcel": parcel.id, "party": party.id, **DEPOSIT},
    ):
        response = vac.post(f"{API}/consignment/", payload, format="json")
        assert response.status_code == 400, response.content
        assert "status" in response.json()

    # Konsinyasi baru diajukan tetap boleh dicatat, tapi tidak boleh
    # dinaikkan ke dititipkan selama ganti rugi belum divalidasi.
    response = vac.post(
        f"{API}/consignment/",
        {"parcel": parcel.id, "party": party.id, "reason": "refused"},
        format="json",
    )
    assert response.status_code == 201, response.content
    consignment_id = response.json()["id"]
    response = vac.patch(
        f"{API}/consignment/{consignment_id}/",
        {k: v for k, v in DEPOSIT.items() if k != "reason"},
        format="json",
    )
    assert response.status_code == 400, response.content

    compensation.refresh_from_db()
    assert compensation.status == enums.CompensationStatus.DETERMINED
    assert _parcel_status(parcel) != enums.ParcelStatus.CONSIGNED

    # Setelah divalidasi Ketua Pelaksana, penitipan diterima.
    Compensation.objects.filter(pk=compensation.pk).update(
        status=enums.CompensationStatus.VALIDATED, validated_on=D(2026, 1, 5)
    )
    response = vac.patch(
        f"{API}/consignment/{consignment_id}/",
        {k: v for k, v in DEPOSIT.items() if k != "reason"},
        format="json",
    )
    assert response.status_code == 200, response.content
    compensation.refresh_from_db()
    assert compensation.status == enums.CompensationStatus.CONSIGNED


def test_deposited_consignment_requires_court_evidence(client_in, parcel, party):
    _compensation(parcel, party, enums.CompensationStatus.VALIDATED)
    vac = client_in(UserGroup.PERINTALAKIMIES)
    response = vac.post(
        f"{API}/consignment/",
        {
            "parcel": parcel.id,
            "party": party.id,
            "reason": "refused",
            "status": "deposited",
        },
        format="json",
    )
    assert response.status_code == 400
    assert {"decree_number", "deposited_on", "amount"} <= set(response.json())
    assert not Consignment.objects.exists()


def test_deposited_consignment_without_any_compensation_is_rejected(client_in, parcel):
    vac = client_in(UserGroup.PERINTALAKIMIES)
    response = vac.post(
        f"{API}/consignment/", {"parcel": parcel.id, **DEPOSIT}, format="json"
    )
    assert response.status_code == 400
    assert _parcel_status(parcel) != enums.ParcelStatus.CONSIGNED


def test_consignment_model_clean_matches_api(parcel, party):
    _compensation(parcel, party, enums.CompensationStatus.DETERMINED)
    consignment = Consignment(
        parcel=parcel,
        party=party,
        reason=enums.ConsignmentReason.REFUSED,
        status=enums.ConsignmentStatus.DEPOSITED,
    )
    with pytest.raises(ValidationError) as excinfo:
        consignment.full_clean()
    assert {"status", "decree_number", "deposited_on", "amount"} <= set(
        excinfo.value.message_dict
    )


# NV-31: induk pembayaran/konsinyasi tidak bisa dipindah


def test_payment_cannot_move_to_another_compensation(client_in, parcel, party):
    first = _compensation(parcel, party, enums.CompensationStatus.VALIDATED)
    second_party = EntitledParty.objects.create(parcel=parcel, name="Siti")
    second = _compensation(parcel, second_party, enums.CompensationStatus.VALIDATED)
    payment = CompensationPayment.objects.create(
        compensation=first, paid_on=D(2026, 1, 6), amount=Decimal("1000")
    )
    first.refresh_from_db()
    assert first.status == enums.CompensationStatus.PAID

    billing = client_in(UserGroup.LASKUTTAJA)
    response = billing.patch(
        f"{API}/payment/{payment.id}/", {"compensation": second.id}, format="json"
    )
    assert response.status_code == 400
    assert "compensation" in response.json()
    payment.refresh_from_db()
    assert payment.compensation_id == first.id

    # Bidang lain (tanggal, catatan) tetap bisa diubah.
    response = billing.patch(
        f"{API}/payment/{payment.id}/", {"note": "Koreksi"}, format="json"
    )
    assert response.status_code == 200, response.content


def test_consignment_cannot_move_to_another_parcel(client_in, project, parcel, party):
    _compensation(parcel, party, enums.CompensationStatus.VALIDATED)
    consignment = Consignment.objects.create(
        parcel=parcel,
        party=None,
        reason=enums.ConsignmentReason.REFUSED,
        status=enums.ConsignmentStatus.DEPOSITED,
        decree_number="1/2026",
        deposited_on=D(2026, 2, 1),
        amount=Decimal("1000"),
    )
    other = AcquisitionParcel.objects.create(project=project, parcel_number="B2")
    vac = client_in(UserGroup.PERINTALAKIMIES)
    response = vac.patch(
        f"{API}/consignment/{consignment.id}/", {"parcel": other.id}, format="json"
    )
    assert response.status_code == 400
    assert "parcel" in response.json()
    consignment.refresh_from_db()
    assert consignment.parcel_id == parcel.id


def test_admin_keeps_payment_and_consignment_parent_read_only(rf, parcel, party):
    compensation = _compensation(parcel, party, enums.CompensationStatus.VALIDATED)
    payment = CompensationPayment.objects.create(
        compensation=compensation, paid_on=D(2026, 1, 6), amount=Decimal("10")
    )
    consignment = Consignment.objects.create(
        parcel=parcel, reason=enums.ConsignmentReason.REFUSED
    )
    request = rf.get("/")
    payment_admin = admin_site._registry[CompensationPayment]
    consignment_admin = admin_site._registry[Consignment]
    assert "compensation" in payment_admin.get_readonly_fields(request, payment)
    assert "compensation" not in payment_admin.get_readonly_fields(request, None)
    assert "parcel" in consignment_admin.get_readonly_fields(request, consignment)
    assert "parcel" not in consignment_admin.get_readonly_fields(request, None)


# NV-27: aksi status ganti rugi mengunci barisnya


@pytest.mark.parametrize("action", ["validate", "cancel"])
def test_compensation_status_actions_lock_the_row(client_in, parcel, party, action):
    compensation = _compensation(parcel, party, enums.CompensationStatus.DETERMINED)
    chair = client_in(UserGroup.PAAKAYTTAJA)
    table = Compensation._meta.db_table
    with CaptureQueriesContext(connection) as queries:
        response = chair.post(f"{API}/compensation/{compensation.id}/{action}/")
    assert response.status_code in (200, 201), response.content
    assert any(
        "FOR UPDATE" in q["sql"] and f'FROM "{table}"' in q["sql"]
        for q in queries.captured_queries
    ), "status Compensation harus dibaca dengan SELECT ... FOR UPDATE"
