"""Tautan pindah antaraplikasi (utama, panel admin, pusat komando, aplikasi
lapangan, portal) di setiap pintu masuk, sesuai hak pengguna."""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import Client

from operasi.tests.conftest import login, make_user
from utils.app_links import app_links
from utils.group_permissions import UserGroup

pytestmark = pytest.mark.django_db


def keys(user):
    return [link.key for link in app_links(user)]


def hrefs(body: str, *urls: str) -> list[str]:
    """URL yang TIDAK ditautkan di halaman."""
    return [url for url in urls if f'href="{url}"' not in body]


def test_links_follow_roles(seeded, units, manager, field):
    assert keys(AnonymousUser()) == ["utama", "admin", "komando", "portal"]
    assert [link.url for link in app_links(AnonymousUser())] == [
        "/",
        "/admin/login/",
        "/komando/masuk/",
        "/portal/",
    ]
    applicant = make_user("pemohon")
    applicant.is_staff = False
    applicant.save()
    assert keys(applicant) == ["portal"]
    reader = make_user("penelusur", UserGroup.SELAILIJA, units=[units[0]])
    reader.is_staff = False
    reader.save()
    assert keys(reader) == ["utama", "portal"]
    assert keys(field) == ["admin", "komando", "lapangan", "portal"]
    assert keys(manager)[:3] == ["utama", "admin", "komando"]
    asset = make_user("aset", UserGroup.PETUGAS_ASET, units=[units[0]])
    assert keys(asset) == ["admin", "komando", "lapangan", "portal"]
    manager.is_active = False
    assert keys(manager) == ["portal"]


def test_every_officer_surface_links_to_the_others(manager):
    client = login(manager)
    expected = {
        "/admin/": ("/", "/komando/", "/aset/lapangan/", "/portal/"),
        "/komando/": ("/", "/admin/", "/aset/lapangan/", "/portal/"),
        "/aset/lapangan/": ("/", "/admin/", "/komando/", "/portal/"),
        "/portal/": ("/", "/admin/", "/komando/", "/aset/lapangan/"),
        "/akun/panduan/": ("/", "/admin/", "/komando/", "/aset/lapangan/", "/portal/"),
    }
    for page, urls in expected.items():
        response = client.get(page)
        assert response.status_code == 200, page
        assert hrefs(response.content.decode(), *urls) == [], page


def test_field_officer_sees_only_permitted_apps(field):
    body = login(field).get("/admin/").content.decode()
    assert hrefs(body, "/komando/", "/aset/lapangan/", "/portal/") == []
    assert "⇄ Aplikasi utama" not in body  # tanpa halaman di aplikasi utama
    body = login(field).get("/portal/akun/").content.decode()
    assert hrefs(body, "/admin/", "/komando/") == []


def test_login_pages_link_to_other_doors(seeded):
    client = Client()
    body = client.get("/admin/login/").content.decode()
    assert hrefs(body, "/", "/komando/masuk/", "/portal/") == []
    body = client.get("/komando/masuk/").content.decode()
    assert hrefs(body, "/", "/admin/login/", "/portal/") == []
    body = client.get("/portal/").content.decode()
    assert hrefs(body, "/", "/admin/login/", "/komando/masuk/") == []


def test_applicant_portal_has_no_officer_links(seeded):
    applicant = make_user("pemohon2")
    applicant.is_staff = False
    applicant.save()
    body = login(applicant).get("/portal/").content.decode()
    assert "Aplikasi petugas" not in body and "Masuk petugas" not in body
    assert 'href="/komando/masuk/"' not in body


def test_error_page_lists_apps(seeded, settings, manager):
    settings.DEBUG = False
    response = Client().get("/tidak-ada-halaman/")
    assert response.status_code == 404
    assert hrefs(response.content.decode(), "/admin/login/", "/portal/") == []
    response = login(manager).get("/tidak-ada-halaman/")
    assert hrefs(response.content.decode(), "/admin/", "/komando/", "/portal/") == []
