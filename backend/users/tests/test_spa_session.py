"""Login aplikasi petugas juga membuat sesi peramban (/admin/, /komando/)."""

import pytest
from django.core.cache import cache
from django.urls import reverse

from users import otp

PASSWORD = "Sandi-Uji-123"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_throttle():
    cache.clear()


@pytest.fixture
def officer(django_user_model):
    return django_user_model.objects.create_user(
        username="petugas",
        email="petugas@contoh.id",
        password=PASSWORD,
        is_staff=True,
        is_superuser=True,
    )


def _login(client, **kwargs):
    return client.post(
        reverse("v1:auth-login"),
        {"username": "petugas", "password": PASSWORD},
        **kwargs,
    )


def test_spa_login_opens_admin_without_second_login(client, officer):
    response = _login(client, content_type="application/json")
    assert response.status_code == 200
    assert "access" in response.json()

    assert client.get("/admin/").status_code == 200
    assert client.session[otp.SESSION_KEY] == officer.pk


def test_spa_logout_ends_browser_session(client, officer):
    tokens = _login(client, content_type="application/json").json()
    response = client.post(
        reverse("v1:auth-logout"),
        {"refresh": tokens["refresh"]},
        content_type="application/json",
    )
    assert response.status_code == 204
    assert client.get("/admin/").status_code == 302


def test_logout_without_refresh_token_still_ends_session(client, officer):
    _login(client, content_type="application/json")
    response = client.post(
        reverse("v1:auth-logout"), {}, content_type="application/json"
    )
    assert response.status_code == 204
    assert client.get("/admin/").status_code == 302


def test_form_post_login_creates_no_session(client, officer):
    # Formulir lintas situs (bukan JSON) tidak boleh memasukkan peramban ke sesi.
    response = _login(client)
    assert response.status_code == 200
    assert "access" in response.json()
    assert client.get("/admin/").status_code == 302


def test_spa_login_with_otp_marks_session_verified(client, officer, settings):
    import re

    from django.core import mail

    settings.OFFICER_OTP_REQUIRED = True
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    data = _login(client, content_type="application/json").json()
    assert data["otp_required"]
    assert client.get("/admin/").status_code == 302

    code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body)[1]
    response = client.post(
        reverse("v1:auth-login-otp"),
        {"otp_token": data["otp_token"], "code": code},
        content_type="application/json",
    )
    assert response.status_code == 200
    # Sudah lolos OTP lewat aplikasi petugas: panel admin tidak meminta OTP lagi.
    assert client.get("/admin/").status_code == 200


def test_stale_unverified_session_does_not_block_spa_login(client, officer, settings):
    settings.OFFICER_OTP_REQUIRED = True
    client.force_login(officer)  # sesi lama tanpa verifikasi OTP
    response = _login(client, content_type="application/json")
    assert response.status_code == 200
    assert response.json()["otp_required"]
