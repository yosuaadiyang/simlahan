"""Pintu masuk tersendiri pusat komando dan perpindahan dengan aplikasi utama."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from operasi.models import SystemLock
from operasi.tests.conftest import PASSWORD, login, make_user
from utils.group_permissions import UserGroup

pytestmark = pytest.mark.django_db

LOGIN = "/komando/masuk/"
LOGOUT = "/komando/keluar/"


@pytest.fixture(autouse=True)
def _reset_throttle():
    cache.clear()
    yield
    cache.clear()


def _config(response) -> dict:
    body = response.content.decode()
    return json.loads(
        body.split('id="komando-config" type="application/json">')[1].split(
            "</script>"
        )[0]
    )


def test_login_page_is_standalone(seeded):
    response = Client().get(LOGIN + "?next=/komando/%3Ftab%3Dabsen")
    assert response.status_code == 200
    body = response.content.decode()
    assert "Pusat Komando" in body
    assert 'name="next" value="/komando/?tab=absen"' in body
    # Bukan halaman masuk panel admin, tanpa kata "Django".
    assert "admin/css" not in body and "Django" not in body
    assert 'href="/"' in body


def test_field_officer_logs_in_and_lands_on_command_center(field):
    client = Client()
    response = client.post(
        LOGIN,
        {
            "username": field.username,
            "password": PASSWORD,
            "next": "/komando/?tab=absen",
        },
    )
    assert response.status_code == 302
    assert response["Location"] == "/komando/?tab=absen"
    assert client.get("/komando/").status_code == 200
    # Sudah masuk: halaman masuk langsung meneruskan ke pusat komando.
    response = client.get(LOGIN)
    assert response.status_code == 302 and response["Location"] == "/komando/"


def test_login_rejects_unsafe_next(field):
    response = Client().post(
        LOGIN,
        {
            "username": field.username,
            "password": PASSWORD,
            "next": "https://jahat.example/",
        },
    )
    assert response.status_code == 302 and response["Location"] == "/komando/"


def test_wrong_password_and_accounts_without_access(seeded, units, field):
    response = Client().post(LOGIN, {"username": field.username, "password": "salah"})
    assert response.status_code == 200
    assert "Nama pengguna atau kata sandi salah" in response.content.decode()

    plain = make_user("staf", units=[units[0]])
    client = Client()
    response = client.post(LOGIN, {"username": plain.username, "password": PASSWORD})
    assert response.status_code == 200
    assert "belum diberi akses pusat komando" in response.content.decode()
    assert "_auth_user_id" not in client.session

    legal = make_user("hukum", UserGroup.PETUGAS_HUKUM, units=[units[0]])
    response = Client().post(LOGIN, {"username": legal.username, "password": PASSWORD})
    assert "belum diberi akses pusat komando" in response.content.decode()


def test_login_is_throttled_per_account(field):
    client = Client()
    for _ in range(10):
        client.post(LOGIN, {"username": field.username, "password": "salah"})
    response = client.post(LOGIN, {"username": field.username, "password": PASSWORD})
    assert response.status_code == 429


def test_logout_requires_post_and_revokes_main_app_token(field):
    client = login(field)
    assert client.get(LOGOUT).status_code == 302
    assert client.get("/komando/").status_code == 200  # GET tidak mengeluarkan

    refresh = RefreshToken.for_user(field)
    response = client.post(LOGOUT, {"refresh": str(refresh)})
    assert response.status_code == 302 and response["Location"] == LOGIN
    assert BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists()
    response = client.get("/komando/")
    assert response.status_code == 302 and response["Location"].startswith(LOGIN)
    # Token rusak/kosong tetap mengeluarkan tanpa galat.
    client = login(field)
    assert client.post(LOGOUT, {"refresh": "bukan-token"}).status_code == 302
    assert Client().post(LOGOUT).status_code == 302


def test_forbidden_page_offers_switch_and_other_account(seeded, units):
    plain = make_user("staf", units=[units[0]])
    response = login(plain).get("/komando/")
    assert response.status_code == 403
    body = response.content.decode()
    assert "Aplikasi utama" in body and 'action="/komando/keluar/"' in body

    plain.is_staff = False
    plain.save()
    response = login(plain).get("/komando/berkas/kegiatan/1/")
    assert response.status_code == 403


def test_private_file_redirects_to_command_login(seeded):
    response = Client().get("/komando/berkas/kegiatan/1/")
    assert response.status_code == 302 and response["Location"].startswith(LOGIN)


def test_main_switch_points_to_the_users_main_app(field, manager):
    config = _config(login(field).get("/komando/"))
    # Petugas lapangan tidak punya halaman di aplikasi petugas: panel admin.
    assert config["urls"]["main"] == "/admin/"
    assert config["urls"]["login"] == "/komando/masuk/?next=/komando/"
    assert config["urls"]["logout"] == LOGOUT
    response = login(manager).get("/komando/")
    assert _config(response)["urls"]["main"] == "/"
    body = response.content.decode()
    assert 'id="ke-utama"' in body and 'href="/"' in body


def test_admin_header_links_to_command_center(field, seeded, units):
    body = login(field).get("/admin/").content.decode()
    assert 'href="/komando/"' in body and "Pusat Komando" in body
    legal = make_user("hukum", UserGroup.PETUGAS_HUKUM, units=[units[0]])
    assert 'href="/komando/"' not in login(legal).get("/admin/").content.decode()


def test_session_from_command_login_opens_main_app_without_second_login(field):
    client = Client(enforce_csrf_checks=True)
    client.get(LOGIN)
    csrf = client.cookies["csrftoken"].value
    client.post(
        LOGIN,
        {"username": field.username, "password": PASSWORD, "csrfmiddlewaretoken": csrf},
    )
    csrf = client.cookies["csrftoken"].value
    # Tanpa token CSRF ditolak (formulir lintas situs tidak bisa mencetak token).
    assert client.post("/v1/auth/session/").status_code == 403
    response = client.post(
        "/v1/auth/session/", content_type="application/json", HTTP_X_CSRFTOKEN=csrf
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["username"] == field.username
    me = Client().get("/v1/auth/me/", HTTP_AUTHORIZATION=f"Bearer {data['access']}")
    assert me.status_code == 200


def test_session_exchange_requires_session_and_rejects_applicants(seeded):
    assert Client().post("/v1/auth/session/").status_code in (401, 403)
    # Token JWT tidak bisa dipakai untuk mencetak token baru.
    user = make_user("petugas")
    access = RefreshToken.for_user(user).access_token
    response = Client().post("/v1/auth/session/", HTTP_AUTHORIZATION=f"Bearer {access}")
    assert response.status_code in (401, 403)

    from alokasi.models import Applicant

    applicant = get_user_model().objects.create_user(
        username="pemohon@example.invalid",
        email="pemohon@example.invalid",
        password=PASSWORD,
    )
    Applicant.objects.create(
        user=applicant, name="PT Uji", pic_name="Uji", phone="0778"
    )
    response = login(applicant).post("/v1/auth/session/")
    assert response.status_code == 403


def test_superuser_can_reach_command_login_while_locked(seeded, field):
    from datetime import timedelta

    from django.utils import timezone

    lock = SystemLock.load()
    lock.set_passcode("rahasia123")
    lock.is_armed = True
    lock.shutdown_at = timezone.now() - timedelta(minutes=1)
    lock.save()
    assert Client().get(LOGIN).status_code == 200
    assert login(field).get("/komando/").status_code == 503
