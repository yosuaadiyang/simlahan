import re

import pytest
from django.core import mail
from django.core.cache import cache
from django.urls import reverse

from alokasi import enums as alokasi_enums
from alokasi.models import Applicant
from users import otp
from users.models import LoginOTP

PASSWORD = "Sandi-Uji-123"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def otp_on(settings):
    settings.OFFICER_OTP_REQUIRED = True
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
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


def _last_code() -> str:
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body)[1]


def _api_login(client, username="petugas"):
    return client.post(
        reverse("v1:auth-login"),
        {"username": username, "password": PASSWORD},
        content_type="application/json",
    )


def test_api_login_requires_otp(client, officer):
    response = _api_login(client)
    assert response.status_code == 200
    data = response.json()
    assert data["otp_required"] and "access" not in data
    assert data["email"] == "p******@contoh.id"
    assert LoginOTP.objects.get().code_hash != _last_code()

    response = client.post(
        reverse("v1:auth-login-otp"),
        {"otp_token": data["otp_token"], "code": _last_code()},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert (
        response.json()["access"] and response.json()["user"]["username"] == "petugas"
    )

    # Kode hanya berlaku sekali.
    response = client.post(
        reverse("v1:auth-login-otp"),
        {"otp_token": data["otp_token"], "code": _last_code()},
        content_type="application/json",
    )
    assert response.status_code == 401


def test_api_login_wrong_code_locks_after_max_attempts(client, officer):
    token = _api_login(client).json()["otp_token"]
    code = _last_code()
    wrong = "000000" if code != "000000" else "111111"
    challenge = LoginOTP.objects.get()
    for _ in range(otp.MAX_ATTEMPTS):
        assert not otp.verify(challenge, wrong)
    assert not otp.verify(challenge, code)
    response = client.post(
        reverse("v1:auth-login-otp"),
        {"otp_token": token, "code": code},
        content_type="application/json",
    )
    assert response.status_code == 401


def test_api_login_without_email_is_refused(client, officer):
    officer.email = ""
    officer.save()
    response = _api_login(client)
    assert response.status_code == 403
    assert not LoginOTP.objects.exists()


def test_api_login_without_otp_when_disabled(client, officer, settings):
    settings.OFFICER_OTP_REQUIRED = False
    response = _api_login(client)
    assert response.status_code == 200 and "access" in response.json()
    assert not mail.outbox


def test_resend_within_a_minute_reuses_code(officer):
    first = otp.issue(officer, LoginOTP.PURPOSE_API)
    second = otp.issue(officer, LoginOTP.PURPOSE_API)
    assert first.pk == second.pk and len(mail.outbox) == 1


def test_admin_session_requires_otp(client, officer):
    client.force_login(officer)
    response = client.get("/admin/")
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("officer-otp"))

    response = client.get(response["Location"])
    assert response.status_code == 200 and len(mail.outbox) == 1

    response = client.post(reverse("officer-otp"), {"code": "abc", "next": "/admin/"})
    assert response.status_code == 200
    assert client.get("/admin/").status_code == 302

    response = client.post(
        reverse("officer-otp"), {"code": _last_code(), "next": "/admin/"}
    )
    assert response.status_code == 302 and response["Location"] == "/admin/"
    assert client.get("/admin/").status_code == 200


def test_admin_otp_rejects_external_next(client, officer):
    client.force_login(officer)
    client.get(reverse("officer-otp"))
    response = client.post(
        reverse("officer-otp"), {"code": _last_code(), "next": "https://contoh.com/"}
    )
    assert response["Location"] == "/admin/"


def test_api_session_request_gets_json_403(client, officer):
    client.force_login(officer)
    response = client.get(reverse("v1:auth-me"))
    assert response.status_code == 403
    assert response.json()["detail"] == "Verifikasi OTP diperlukan."


def test_new_login_clears_verification(client, officer):
    client.force_login(officer)
    session = client.session
    session[otp.SESSION_KEY] = officer.pk
    session.save()
    assert client.get("/admin/").status_code == 200
    client.logout()
    client.force_login(officer)
    assert client.get("/admin/").status_code == 302


def test_applicants_are_exempt(django_user_model):
    user = django_user_model.objects.create_user(
        username="pemohon@contoh.id", email="pemohon@contoh.id", password=PASSWORD
    )
    Applicant.objects.create(
        user=user,
        applicant_type=alokasi_enums.ApplicantType.COMPANY,
        name="PT Contoh",
        nib="9120000000001",
        pic_name="Direktur",
        phone="0778000000",
        address="Jl. Contoh No. 1",
    )
    user.refresh_from_db()
    assert not otp.required_for(user)


def test_mask_email():
    assert otp.mask_email("ab@contoh.id") == "a**@contoh.id"
    assert otp.mask_email("") == ""
