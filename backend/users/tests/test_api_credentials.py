import datetime

import pytest
from django.utils import timezone
from oauth2_provider.models import AccessToken, Application
from oauth2_provider.models import RefreshToken as OAuthRefreshToken
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from alokasi import enums as alokasi_enums
from alokasi.models import Applicant

pytestmark = pytest.mark.django_db

ASSETS = "/v1/aset/asset/"
PASSWORD = "Sandi-Uji-2026!x"


@pytest.fixture
def officer(django_user_model):
    return django_user_model.objects.create_user(
        username="petugas-token", password=PASSWORD, is_superuser=True
    )


def _token_header(token):
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def _oauth_tokens(user):
    application = Application.objects.create(
        name="Aplikasi uji",
        user=user,
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="https://contoh.invalid/callback",
    )
    access = AccessToken.objects.create(
        application=application,
        user=user,
        token="akses-uji-1234567890",
        scope="read",
        expires=timezone.now() + datetime.timedelta(hours=1),
    )
    OAuthRefreshToken.objects.create(
        application=application, user=user, token="segar-uji-1234", access_token=access
    )
    return application


def test_static_token_works_when_otp_not_required(client, officer, settings):
    settings.OFFICER_OTP_REQUIRED = False
    token = Token.objects.create(user=officer)
    response = client.get(ASSETS, **_token_header(token))
    assert response.status_code == 200, response.content


def test_static_token_rejected_when_officer_otp_required(client, officer, settings):
    settings.OFFICER_OTP_REQUIRED = True
    token = Token.objects.create(user=officer)
    response = client.get(ASSETS, **_token_header(token))
    assert response.status_code == 401
    assert "OAuth2" in response.json()["detail"]


def test_static_token_rejected_for_applicant(client, django_user_model, settings):
    settings.OFFICER_OTP_REQUIRED = False
    user = django_user_model.objects.create_user(
        username="pemohon-token", password=PASSWORD
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
    token = Token.objects.create(user=user)
    response = client.get(ASSETS, **_token_header(token))
    assert response.status_code == 401


def test_password_change_from_any_path_revokes_api_credentials(officer):
    static = Token.objects.create(user=officer)
    _oauth_tokens(officer)
    RefreshToken.for_user(officer)
    other = type(officer).objects.create_user(username="lain", password=PASSWORD)
    other_static = Token.objects.create(user=other)

    # Jalur admin Django / lupa sandi: set_password lalu save.
    officer.set_password("Sandi-Baru-2026!y")
    officer.save()

    assert not Token.objects.filter(pk=static.pk).exists()
    assert not AccessToken.objects.filter(user=officer).exists()
    assert not OAuthRefreshToken.objects.filter(
        user=officer, revoked__isnull=True
    ).exists()
    assert not OutstandingToken.objects.filter(
        user=officer, blacklistedtoken__isnull=True
    ).exists()
    # Pengguna lain tidak terpengaruh.
    assert Token.objects.filter(pk=other_static.pk).exists()


def test_password_hash_upgrade_and_other_saves_keep_credentials(officer):
    static = Token.objects.create(user=officer)
    # Peningkatan hash saat login memanggil set_password lalu mengosongkan
    # _password sebelum save; itu bukan ganti sandi.
    officer.set_password(PASSWORD)
    officer._password = None
    officer.save(update_fields=["password"])
    officer.first_name = "Nama Baru"
    officer.save()
    assert Token.objects.filter(pk=static.pk).exists()


def test_password_change_api_returns_fresh_working_tokens(client, officer):
    old = RefreshToken.for_user(officer)
    client.force_login(officer)
    response = client.post(
        "/v1/auth/password/",
        {"old_password": PASSWORD, "new_password": "Sandi-Baru-2026!y"},
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
    fresh = response.json()["access"]
    assert OutstandingToken.objects.filter(
        jti=old["jti"], blacklistedtoken__isnull=False
    ).exists()
    response = client.get(ASSETS, HTTP_AUTHORIZATION=f"Bearer {fresh}")
    assert response.status_code == 200, response.content
