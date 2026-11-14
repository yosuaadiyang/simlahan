"""Data sewa boleh dibaca lintas unit layanan, tetapi hanya anggota unit sewa
yang boleh membuat, mengubah, atau menghapus catatan turunannya."""

import json

import pytest
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse

from leasing.enums import ContactType
from leasing.models import Contact, Decision, InspectionAttachment, Lease

pytestmark = pytest.mark.django_db


def _json(data):
    return json.dumps(data, cls=DjangoJSONEncoder)


@pytest.fixture
def units(service_unit_factory):
    return service_unit_factory(name="Unit A"), service_unit_factory(name="Unit B")


@pytest.fixture
def officer_a(client, user_factory, units):
    """Petugas unit A dengan seluruh izin model & kolom pada model terkait."""
    user = user_factory(username="petugas_a")
    user.service_units.add(units[0])
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="leasing",
            content_type__model__in=[
                "decision",
                "contact",
                "inspection",
                "inspectionattachment",
                "lease",
            ],
        )
    )
    client.force_login(user)
    return user


@pytest.fixture
def leases(lease_factory, units):
    return (
        lease_factory(service_unit=units[0], start_date="2020-01-01"),
        lease_factory(service_unit=units[1], start_date="2020-01-01"),
    )


def test_decision_create_only_on_own_unit_lease(client, officer_a, leases):
    url = reverse("v1:decision-list")
    own = client.post(
        url, _json({"lease": leases[0].id}), content_type="application/json"
    )
    assert own.status_code == 201, own.content
    other = client.post(
        url, _json({"lease": leases[1].id}), content_type="application/json"
    )
    assert other.status_code == 403
    assert not Decision.objects.filter(lease=leases[1]).exists()


def test_decision_of_other_unit_cannot_be_changed_moved_or_deleted(
    client, officer_a, leases, decision_factory
):
    foreign = decision_factory(lease=leases[1])
    url = reverse("v1:decision-detail", kwargs={"pk": foreign.id})
    assert client.get(url).status_code == 200  # membaca lintas unit tetap boleh
    patch = client.patch(
        url, _json({"lease": leases[0].id}), content_type="application/json"
    )
    assert patch.status_code == 403
    assert client.delete(url).status_code == 403
    foreign.refresh_from_db()
    assert foreign.lease_id == leases[1].id

    # Memindahkan keputusan milik sendiri ke sewa unit lain juga ditolak.
    mine = decision_factory(lease=leases[0])
    moved = client.patch(
        reverse("v1:decision-detail", kwargs={"pk": mine.id}),
        _json({"lease": leases[1].id}),
        content_type="application/json",
    )
    assert moved.status_code == 403
    mine.refresh_from_db()
    assert mine.lease_id == leases[0].id


def test_inspection_attachment_delete_bound_to_lease_unit(
    client, officer_a, leases, inspection_factory
):
    inspection = inspection_factory(lease=leases[1])
    attachment = InspectionAttachment.objects.create(
        inspection=inspection,
        file=SimpleUploadedFile("tarkastus.pdf", b"%PDF-1.4"),
        uploader=officer_a,
    )
    url = reverse("v1:inspectionattachment-detail", kwargs={"pk": attachment.id})
    assert client.delete(url).status_code == 403
    assert InspectionAttachment.objects.filter(pk=attachment.pk).exists()


def test_contact_update_and_delete_bound_to_contact_unit(
    client, officer_a, units, contact_factory
):
    foreign = contact_factory(
        type=ContactType.BUSINESS, name="Kontak B", service_unit=units[1]
    )
    own = contact_factory(
        type=ContactType.BUSINESS, name="Kontak A", service_unit=units[0]
    )
    foreign_url = reverse("v1:contact-detail", kwargs={"pk": foreign.id})
    assert client.get(foreign_url).status_code == 200
    response = client.patch(
        foreign_url, _json({"name": "Diubah"}), content_type="application/json"
    )
    assert response.status_code == 403
    assert client.delete(foreign_url).status_code == 403
    foreign.refresh_from_db()
    assert foreign.name == "Kontak B"

    response = client.patch(
        reverse("v1:contact-detail", kwargs={"pk": own.id}),
        _json({"name": "Diubah"}),
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
    assert Contact.objects.get(pk=own.pk).name == "Diubah"


def test_rent_info_completion_bound_to_lease_unit(client, officer_a, leases):
    url = reverse("v1:lease-set-rent-info-completion-state")
    other = client.post(
        f"{url}?lease={leases[1].id}",
        _json({"rent_info_complete": False}),
        content_type="application/json",
    )
    assert other.status_code == 403
    own = client.post(
        f"{url}?lease={leases[0].id}",
        _json({"rent_info_complete": False}),
        content_type="application/json",
    )
    assert own.status_code == 200, own.content
    assert Lease.objects.get(pk=leases[0].pk).rent_info_completed_at is None
