"""Deteksi nilai contoh/placeholder dari repositori (mis. ``.env.example``).

Nilai seperti ``ganti-kata-sandi-admin`` diketahui publik. Dipakai bersama oleh
``mvj.settings`` (SECRET_KEY, FIELD_ENCRYPTION_KEY), ``simlahan_bootstrap``
(sandi admin awal), dan ``cek_produksi``. Modul ini sengaja tanpa impor Django
agar aman dimuat dari settings.
"""

PLACEHOLDER_MARKERS = (
    "ganti-",
    "ganti ",
    "dev-only",
    "changeme",
    "change-me",
    "example",
)


def is_placeholder(value: str) -> bool:
    lowered = (value or "").lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)
