"""Tulisan "Django" tidak boleh tampil kepada pengguna; semua bermerek SimLahan."""

import re

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db

PAGES = [
    "/admin/",
    "/admin/oauth2_provider/application/",
    "/admin/django_q/schedule/",
    "/admin/batchrun/command/add/",
    "/admin/password_change/",
    "/v1/aset/asset/?format=api",
    "/docs/",
    "/oauth/authorize/",
]
PUBLIC_PAGES = ["/admin/login/", "/admin/password_reset/", "/auth/login/", "/docs/"]


def _visible_text(response) -> str:
    body = response.content.decode()
    body = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", body)
    texts = re.findall(r">([^<]+)<", body)
    texts += re.findall(r'(?:title|alt|placeholder|aria-label)="([^"]*)"', body)
    # Nilai <option> tidak tampil; hanya tombol yang menampilkan atribut value.
    texts += re.findall(
        r'<input[^>]*type="(?:submit|button)"[^>]*value="([^"]*)"', body
    )
    return " ".join(texts)


@pytest.mark.parametrize("language", ["id", "en"])
def test_no_django_wording_for_officers(admin_client, language):
    admin_client.defaults["HTTP_ACCEPT_LANGUAGE"] = language
    for url in PAGES:
        response = admin_client.get(url, follow=True)
        assert response.status_code in (200, 400), url
        text = _visible_text(response)
        assert "django" not in text.lower(), (
            url,
            re.findall(r".{0,40}django.{0,40}", text, re.I),
        )


@pytest.mark.parametrize("language", ["id", "en"])
def test_no_django_wording_for_visitors(language):
    client = Client(HTTP_ACCEPT_LANGUAGE=language)
    for url in PUBLIC_PAGES:
        response = client.get(url, follow=True)
        assert response.status_code == 200, url
        assert "django" not in _visible_text(response).lower(), url


@pytest.mark.parametrize(
    "language,header,title",
    [
        ("en", "SimLahan administration", "SimLahan site admin"),
        ("id", "Administrasi SimLahan", "Admin situs SimLahan"),
    ],
)
def test_admin_header_uses_app_name(language, header, title):
    response = Client(HTTP_ACCEPT_LANGUAGE=language).get("/admin/login/")
    page = response.content.decode()
    assert f">{header}</a>" in page
    assert f"| {title}</title>" in page


def test_app_name_is_configurable(settings):
    settings.APP_NAME = "Lahan Kita"
    page = Client(HTTP_ACCEPT_LANGUAGE="en").get("/auth/login/").content.decode()
    assert "Lahan Kita API" in page
