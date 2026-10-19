import json
import re

import pytest
from django_extensions.management.commands import show_urls

PK_REPLACEMENT = "12"
ID_REPLACEMENT = "34"
UUID_REPLACEMENT = "001acc16-c45b-4dab-97ee-f79c0292d37b"

REPLACEMENTS = (
    (re.compile("<pk>"), PK_REPLACEMENT),
    (re.compile(r"<\w+_id>"), ID_REPLACEMENT),  # Replaces `<something_id>` with `34`
    (re.compile("<str:uuid>"), UUID_REPLACEMENT),
    (re.compile(r"<uuid:\w+>"), UUID_REPLACEMENT),
    (re.compile(r"<int:\w+>"), PK_REPLACEMENT),
    (re.compile(r"<(?:str|slug):\w+>"), "abc"),
)

# These URLs do not require authentication intentionally
WHITELIST_PUBLIC_URLS = (
    "/v1/pub/answer/",
    "/v1/pub/faq/",
    "/v1/pub/plot_search_ui/0",
    "/v1/pub/plot_search_ui/1",
    "/v1/pub/plot_search_ui/",
    "/v1/pub/plot_search/",
    "/v1/pub/plot_search_stage/",
    "/v1/pub/plot_search_type/",
    "/v1/pub/plot_search_subtype/",
    "/v1/pub/proxy/wms/owned_areas/",
    # Autentikasi lokal (JWT): login, refresh dan logout memang tanpa sesi.
    "/v1/auth/login/",
    "/v1/auth/refresh/",
    "/v1/auth/logout/",
)
WHITELIST_DJANGO_URLS = (
    "/admin/",
    "/auth/",
    "/docs/",
    "/redoc/",
    "/__debug__/",
)

# Aplikasi berbasis sesi (bukan API): tanpa login harus dialihkan ke halaman
# masuk atau ditolak, kecuali halaman yang memang publik di bawah ini.
SESSION_APP_PREFIXES = ("/portal/", "/aset/", "/komando/", "/oauth/")
PUBLIC_SESSION_PAGES = (
    re.compile(
        r"^/portal/("
        r"|lahan/|lahan/[^/]+/|lahan/[^/]+/foto/|layanan/"
        r"|informasi/.*|verifikasi/.*|daftar/|aktivasi/.*|masuk/|keluar/"
        r"|lupa-sandi/.*|atur-sandi/.*|pengaduan/.*|lelang/|lelang/[^/]+/"
        r")$"
    ),
    # Peta berbagi baca-saja; akses dikendalikan token di URL.
    re.compile(r"^/aset/peta/[^/]+/$"),
    # Titik akhir protokol OAuth2; klien diautentikasi oleh protokolnya sendiri.
    re.compile(r"^/oauth/"),
)

WHITELIST = WHITELIST_PUBLIC_URLS + WHITELIST_DJANGO_URLS + SESSION_APP_PREFIXES


def get_url_paths(include=None):
    cmd = show_urls.Command()
    views_str = cmd.handle(
        no_color=True,
        language=None,
        decorator=None,
        format_style="pretty-json",
        urlconf="ROOT_URLCONF",
        unsorted=True,
    )

    def _is_valid_route(route):
        url = route.get("url", "")
        if include is not None:
            return url.startswith(include) and url.endswith("/")
        return (
            len(url) > 0
            and not url.startswith(WHITELIST)
            and url.endswith("/")
            and "<format>" not in url
        )

    try:
        views = filter(_is_valid_route, json.loads(views_str))
    except json.JSONDecodeError:
        return []

    paths = []
    for view in views:
        path = view.get("url", "")
        for pattern, replacement in REPLACEMENTS:
            path = re.sub(pattern, replacement, path)
        paths.append(path)
    return paths


@pytest.mark.django_db
@pytest.mark.parametrize("path", get_url_paths())
def test_urls(client, path):
    for method in ["get", "post", "put", "patch", "delete", "options"]:
        request_method = getattr(client, method)
        response = request_method(path)
        assert (
            response.status_code == 401
        ), f"Found unauthenticated endpoint: {method.upper()} {path}"


def _is_login_redirect(response):
    location = response.get("Location", "")
    return response.status_code == 302 and (
        "/login/" in location or "/masuk/" in location
    )


@pytest.mark.django_db
@pytest.mark.parametrize("path", get_url_paths(include=SESSION_APP_PREFIXES))
def test_session_app_urls(client, path):
    public = any(pattern.match(path) for pattern in PUBLIC_SESSION_PAGES)
    for method in ["get", "post", "put", "patch", "delete", "options"]:
        response = getattr(client, method)(path)
        assert response.status_code < 500, f"{method.upper()} {path}"
        if public:
            continue
        assert response.status_code in (401, 403, 405) or _is_login_redirect(
            response
        ), f"Found unauthenticated endpoint: {method.upper()} {path}"
