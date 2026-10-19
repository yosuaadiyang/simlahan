import base64
import datetime

import pytest
from django.urls import reverse
from django.utils import timezone
from oauth2_provider.models import AccessToken, Application

from alokasi import enums as alokasi_enums
from alokasi.models import Applicant

pytestmark = pytest.mark.django_db

SECRET = "rahasia-klien-uji-0123456789"
ASSETS = "/v1/aset/asset/"
PROJECTS = "/v1/pengadaan/project/"


@pytest.fixture
def service_user(django_user_model):
    return django_user_model.objects.create_user(
        username="layanan-erp", password="Sandi-Uji-123", is_superuser=True
    )


def _application(user, name="ERP"):
    return Application.objects.create(
        name=name,
        user=user,
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        client_secret=SECRET,
    )


def _token(client, application, scope="read"):
    credentials = base64.b64encode(
        f"{application.client_id}:{SECRET}".encode()
    ).decode()
    return client.post(
        "/oauth/token/",
        {"grant_type": "client_credentials", "scope": scope},
        HTTP_AUTHORIZATION=f"Basic {credentials}",
    )


def _bearer(token):
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def test_client_credentials_token_reads_api(client, service_user):
    application = _application(service_user)
    assert application.client_secret != SECRET  # disimpan sebagai hash
    response = _token(client, application)
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["token_type"] == "Bearer" and body["scope"] == "read"
    assert body["expires_in"] == 3600
    response = client.get(ASSETS, **_bearer(body["access_token"]))
    assert response.status_code == 200, response.content


def test_read_scope_cannot_write(client, service_user):
    token = _token(client, _application(service_user)).json()["access_token"]
    response = client.post(
        PROJECTS, {}, content_type="application/json", **_bearer(token)
    )
    assert response.status_code == 403
    assert "write" in response.json()["detail"]


def test_write_scope_reaches_validation(client, service_user):
    response = _token(client, _application(service_user), scope="read write")
    token = response.json()["access_token"]
    response = client.post(
        PROJECTS, {}, content_type="application/json", **_bearer(token)
    )
    assert response.status_code == 400  # lolos autentikasi, ditolak validasi


def test_wrong_secret_rejected(client, service_user):
    application = _application(service_user)
    credentials = base64.b64encode(f"{application.client_id}:salah".encode()).decode()
    response = client.post(
        "/oauth/token/",
        {"grant_type": "client_credentials"},
        HTTP_AUTHORIZATION=f"Basic {credentials}",
    )
    assert response.status_code == 401


def _issue(application, user=None, scope="read", **kwargs):
    return AccessToken.objects.create(
        application=application,
        user=user,
        token=kwargs.pop("token", "tok-uji-1234567890"),
        scope=scope,
        expires=timezone.now() + datetime.timedelta(hours=1),
        **kwargs,
    )


def test_application_without_service_account_is_401(client):
    application = _application(None)
    _issue(application)
    response = client.get(ASSETS, **_bearer("tok-uji-1234567890"))
    assert response.status_code == 401


def test_inactive_service_account_is_401(client, service_user):
    application = _application(service_user)
    _issue(application)
    service_user.is_active = False
    service_user.save()
    response = client.get(ASSETS, **_bearer("tok-uji-1234567890"))
    assert response.status_code == 401


def test_expired_token_is_401(client, service_user):
    token = _issue(_application(service_user))
    token.expires = timezone.now() - datetime.timedelta(seconds=1)
    token.save()
    response = client.get(ASSETS, **_bearer("tok-uji-1234567890"))
    assert response.status_code == 401


def test_applicant_token_rejected(client, django_user_model, service_user):
    user = django_user_model.objects.create_user(
        username="pemohon@contoh.id", password="Sandi-Uji-123"
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
    _issue(_application(service_user), user=user)
    response = client.get(ASSETS, **_bearer("tok-uji-1234567890"))
    assert response.status_code == 401


def test_jwt_login_still_works(client, django_user_model):
    django_user_model.objects.create_user(
        username="petugas", password="Sandi-Uji-123", is_superuser=True
    )
    response = client.post(
        reverse("v1:auth-login"),
        {"username": "petugas", "password": "Sandi-Uji-123"},
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
    access = response.json()["access"]
    assert client.get(ASSETS, **_bearer(access)).status_code == 200


def test_authorize_page_requires_officer_login(client):
    response = client.get("/oauth/authorize/")
    assert response.status_code == 302
    assert response["Location"].startswith("/admin/login/")


def test_oauth_application_admin(admin_client):
    response = admin_client.get("/admin/oauth2_provider/application/add/")
    assert response.status_code == 200


def test_authorization_code_consent_page(client, service_user):
    application = Application.objects.create(
        name="Dasbor GIS",
        user=service_user,
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="https://gis.contoh.id/callback",
        client_secret=SECRET,
    )
    client.force_login(service_user)
    params = {
        "client_id": application.client_id,
        "response_type": "code",
        "redirect_uri": "https://gis.contoh.id/callback",
        "scope": "read",
        "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
        "code_challenge_method": "S256",
    }
    page = client.get("/oauth/authorize/", params)
    assert page.status_code == 200
    assert "Dasbor GIS" in page.content.decode() and "Izinkan" in page.content.decode()
    response = client.post("/oauth/authorize/", {**params, "allow": "Izinkan"})
    assert response.status_code == 302
    assert response["Location"].startswith("https://gis.contoh.id/callback?code=")
    invalid = client.get("/oauth/authorize/", {"client_id": "tidak-ada"})
    assert invalid.status_code == 400
    assert "tidak valid" in invalid.content.decode()
