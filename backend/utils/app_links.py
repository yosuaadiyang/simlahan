"""Tautan pindah antaraplikasi SimLahan.

SimLahan punya beberapa pintu: aplikasi utama (SPA di ``/``), panel admin
(``/admin/``), pusat komando (``/komando/``), aplikasi lapangan aset
(``/aset/lapangan/``), dan portal publik (``/portal/``). Setiap halaman
menampilkan tautan ke pintu lain yang boleh dibuka penggunanya; pengunjung
yang belum masuk mendapat tautan ke halaman masuk tiap aplikasi.
"""

from dataclasses import dataclass

from django.urls import reverse


@dataclass(frozen=True)
class AppLink:
    key: str
    label: str
    url: str
    icon: str


def app_links(user) -> list[AppLink]:
    """Aplikasi yang boleh dibuka ``user`` (urutan tetap: utama, panel, komando,
    lapangan, portal). Templat melewati tautan ke aplikasi yang sedang dibuka.

    Portal selalu terakhir, jadi ``app_links.0.key != "portal"`` berarti
    pengguna punya aplikasi petugas (atau belum masuk)."""
    from operasi.auth_views import SPA_HOME_PERMISSIONS

    portal = AppLink("portal", "Portal", reverse("portal:home"), "🌐")
    if user is None or not user.is_authenticated:
        return [
            AppLink("utama", "Aplikasi utama", "/", "🏠"),
            AppLink("admin", "Panel admin", reverse("admin:login"), "🛠️"),
            AppLink("komando", "Pusat Komando", reverse("operasi-login"), "🛰️"),
            portal,
        ]
    if not user.is_active:
        return [portal]
    links = []
    if any(user.has_perm(permission) for permission in SPA_HOME_PERMISSIONS):
        links.append(AppLink("utama", "Aplikasi utama", "/", "🏠"))
    if user.is_staff:
        links.append(AppLink("admin", "Panel admin", reverse("admin:index"), "🛠️"))
        if user.has_perm("operasi.view_korwil"):
            links.append(
                AppLink("komando", "Pusat Komando", reverse("operasi-command"), "🛰️")
            )
        if user.has_perm("asetlahan.add_fieldreport"):
            links.append(
                AppLink(
                    "lapangan", "Aplikasi lapangan", reverse("asetlahan-field"), "📋"
                )
            )
    links.append(portal)
    return links


def app_links_context(request):
    """Pemroses konteks: ``app_links`` dihitung hanya bila templat memakainya."""
    user = getattr(request, "user", None)
    cache = []

    def links():
        if not cache:
            cache.append(app_links(user))
        return cache[0]

    return {"app_links": links}
