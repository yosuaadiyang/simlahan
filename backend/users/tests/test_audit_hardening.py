"""Pengerasan autentikasi: OTP atomik, batas tebakan OTP sesi, kunci throttle
per akun yang dinormalisasi, grant OAuth yang melewati OTP, dan pengecualian
OTP yang dicocokkan persis."""

import base64
import re

import pytest
from django.core import mail
from django.urls import reverse
from oauth2_provider.models import Application

from users import otp, otp_views
from users.models import LoginOTP
from utils.models import RateCounter

PASSWORD = "Sandi-Uji-123"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def otp_on(settings):
    settings.OFFICER_OTP_REQUIRED = True
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.TRUST_PROXY_HEADERS = False


@pytest.fixture
def officer(django_user_model):
    return django_user_model.objects.create_user(
        username="petugas",
        email="petugas@contoh.id",
        password=PASSWORD,
        is_staff=True,
        is_superuser=True,
    )


def _last_code() -> str:
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body)[1]


def test_otp_attempt_limit_holds_for_stale_copies(officer):
    otp.issue(officer, LoginOTP.PURPOSE_API)
    code = _last_code()
    LoginOTP.objects.update(attempts=otp.MAX_ATTEMPTS - 1)
    first, second = LoginOTP.objects.get(), LoginOTP.objects.get()
    assert not otp.verify(first, "000000" if code != "000000" else "111111")
    # Salinan kedua dibaca sebelum tebakan pertama tercatat (permintaan paralel).
    assert not otp.verify(second, code)
    assert LoginOTP.objects.get().attempts == otp.MAX_ATTEMPTS


def test_correct_otp_is_accepted_only_once_for_parallel_requests(officer):
    otp.issue(officer, LoginOTP.PURPOSE_API)
    code = _last_code()
    first, second = LoginOTP.objects.get(), LoginOTP.objects.get()
    assert otp.verify(first, code) is True
    assert otp.verify(second, code) is False


def test_session_otp_guesses_are_throttled_per_account(client, officer, monkeypatch):
    monkeypatch.setattr(otp_views, "OTP_POSTS_PER_WINDOW", 2)
    client.force_login(officer)
    client.get(reverse("officer-otp"))
    code = _last_code()
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(2):
        response = client.post(reverse("officer-otp"), {"code": wrong})
        assert response.status_code == 200
    response = client.post(reverse("officer-otp"), {"code": code, "next": "/admin/"})
    assert response.status_code == 200
    assert "Terlalu banyak percobaan" in response.content.decode()
    assert client.session.get(otp.SESSION_KEY) is None


def test_login_throttle_key_is_unicode_normalized(client, officer, settings):
    settings.OFFICER_OTP_REQUIRED = False
    for index in range(10):
        client.post(
            "/admin/login/",
            {"username": "petugas", "password": "salah"},
            REMOTE_ADDR=f"198.51.100.{index}",
        )
    # Huruf lebar penuh dinormalisasi NFKC oleh Django menjadi "petugas".
    response = client.post(
        "/admin/login/",
        {"username": "ｐｅｔｕｇａｓ", "password": PASSWORD},
        REMOTE_ADDR="198.51.100.200",
    )
    assert response.status_code == 429
    assert RateCounter.objects.filter(key="users:login-throttle:petugas").exists()


def test_password_grant_is_refused_even_if_registered(client, officer):
    secret = "rahasia-klien-uji-0123456789"
    application = Application.objects.create(
        name="Aplikasi lama",
        user=officer,
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_PASSWORD,
        client_secret=secret,
    )
    credentials = base64.b64encode(
        f"{application.client_id}:{secret}".encode()
    ).decode()
    response = client.post(
        "/oauth/token/",
        {"grant_type": "password", "username": "petugas", "password": PASSWORD},
        HTTP_AUTHORIZATION=f"Basic {credentials}",
    )
    assert response.status_code in (400, 401)
    assert "access_token" not in response.json()


def test_otp_exemptions_match_exact_paths(client, officer):
    client.force_login(officer)
    response = client.get("/healthz-lain")
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("officer-otp"))
    assert client.get("/healthz").status_code == 200
