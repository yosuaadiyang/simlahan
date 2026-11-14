import re
from urllib.parse import urlparse

import pytest
from django.contrib.admin.sites import AdminSite
from django.core import mail
from django.core.cache import cache
from django.test import RequestFactory
from django.urls import reverse

from alokasi.admin import ApplicantAdmin
from alokasi.models import Applicant
from alokasi.views import activation_token

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("seeded")]


@pytest.fixture(autouse=True)
def clear_throttle():
    cache.clear()
    yield
    cache.clear()


def _activation_path():
    link = re.search(r"https?://\S+/portal/aktivasi/\S+/", mail.outbox[-1].body)
    return urlparse(link.group(0)).path


def _resend(client, applicant):
    mail.outbox.clear()
    response = client.post(
        reverse("portal:resend_activation"), {"email": applicant.user.email}
    )
    assert response.status_code == 200
    return len(mail.outbox)


def _admin_action(name, applicant, officer):
    request = RequestFactory().post("/")
    request.user = officer
    request._messages = type("M", (), {"add": lambda *a, **k: None})()
    model_admin = ApplicantAdmin(Applicant, AdminSite())
    getattr(model_admin, name)(request, Applicant.objects.filter(pk=applicant.pk))


def test_pending_account_can_still_resend_and_activate(client, make_applicant):
    applicant = make_applicant(active=False)
    assert not applicant.email_activation_closed
    assert _resend(client, applicant) == 1
    assert client.post(_activation_path()).status_code == 302
    applicant.refresh_from_db()
    applicant.user.refresh_from_db()
    assert applicant.user.is_active and applicant.email_activation_closed


def test_officer_deactivated_account_cannot_reactivate_by_email(
    client, make_applicant, admin_user
):
    applicant = make_applicant(active=False)
    _resend(client, applicant)
    old_link = _activation_path()
    assert client.post(old_link).status_code == 302  # pemohon mengaktifkan

    _admin_action("deactivate_accounts", applicant, admin_user)
    applicant.user.refresh_from_db()
    assert not applicant.user.is_active

    # Tidak ada surel aktivasi baru, dan tautan lama tidak berlaku lagi.
    assert _resend(client, applicant) == 0
    assert client.get(old_link).status_code == 400
    token = activation_token.make_token(applicant.user)
    uid = old_link.rstrip("/").split("/")[-2]
    forged = reverse("portal:activate", args=[uid, token])
    assert client.get(forged).status_code == 400
    applicant.user.refresh_from_db()
    assert not applicant.user.is_active

    # Petugas tetap bisa mengaktifkan kembali.
    _admin_action("activate_accounts", applicant, admin_user)
    applicant.user.refresh_from_db()
    assert applicant.user.is_active


def test_officer_deactivating_pending_account_blocks_activation(
    client, make_applicant, admin_user
):
    applicant = make_applicant(active=False)
    _admin_action("deactivate_accounts", applicant, admin_user)
    assert _resend(client, applicant) == 0


def test_account_deactivated_through_user_admin_cannot_reactivate(
    client, make_applicant
):
    applicant = make_applicant(active=True)
    assert Applicant.objects.get(pk=applicant.pk).email_activation_closed
    user = applicant.user
    user.is_active = False
    user.save()
    assert _resend(client, applicant) == 0
