"""Pemeriksaan kesiapan sebelum SimLahan dibuka untuk publik.

Dipakai perintah ``python manage.py cek_produksi``. Melengkapi
``manage.py check --deploy`` (pengaturan keamanan Django) dengan hal yang
khas SimLahan: akun & data contoh, surel, alamat publik, dan sandi admin awal.
"""

import os
from dataclasses import dataclass
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model

from utils.placeholders import is_placeholder

FAIL = "GAGAL"
WARN = "PERINGATAN"
INFO = "INFO"

NON_SENDING_BACKENDS = (
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
    "django.core.mail.backends.filebased.EmailBackend",
)


@dataclass(frozen=True)
class Finding:
    level: str
    message: str


def _config() -> list[Finding]:
    found = []
    if settings.DEBUG:
        found.append(Finding(FAIL, "DEBUG aktif. Isi DEBUG=0 di .env."))
    if "*" in settings.ALLOWED_HOSTS:
        found.append(
            Finding(FAIL, "ALLOWED_HOSTS memuat '*'. Isi dengan nama domain saja.")
        )
    if settings.EMAIL_BACKEND in NON_SENDING_BACKENDS:
        found.append(
            Finding(
                FAIL,
                "Surel tidak benar-benar dikirim (EMAIL_URL belum SMTP): pendaftar "
                "portal, lupa sandi, kode OTP tanda tangan, dan pengingat tidak "
                "sampai.",
            )
        )
    elif (
        "example" in settings.DEFAULT_FROM_EMAIL
        or settings.DEFAULT_FROM_EMAIL.endswith(".local")
    ):
        found.append(
            Finding(
                WARN,
                f"DEFAULT_FROM_EMAIL masih {settings.DEFAULT_FROM_EMAIL}; surel "
                "mudah dianggap spam.",
            )
        )
    url = (settings.OFFICER_UI_URL or "").strip()
    parts = urlsplit(url)
    if not url or parts.hostname in (None, "localhost", "127.0.0.1"):
        found.append(
            Finding(
                FAIL,
                "OFFICER_UI_URL belum alamat publik; tautan di surel dan kode QR "
                "dokumen akan salah.",
            )
        )
    elif parts.scheme != "https":
        found.append(
            Finding(WARN, "OFFICER_UI_URL bukan https://; pakai HTTPS untuk publik.")
        )
    else:
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in settings.CSRF_TRUSTED_ORIGINS:
            found.append(
                Finding(
                    FAIL,
                    f"CSRF_TRUSTED_ORIGINS tidak memuat {origin}; formulir masuk "
                    "dan unggah akan ditolak.",
                )
            )
        if not (settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE):
            found.append(
                Finding(
                    FAIL,
                    "SESSION_COOKIE_SECURE/CSRF_COOKIE_SECURE harus 1 bila memakai "
                    "HTTPS.",
                )
            )
    if not settings.FLAG_FILE_SCAN:
        found.append(
            Finding(
                WARN,
                "Pemindaian virus unggahan mati (FLAG_FILE_SCAN). Disarankan untuk "
                "portal publik.",
            )
        )
    return found


def _sample_data() -> list[Finding]:
    from alokasi.models import ContactMessage, LandPlot, UwtRegion
    from asetlahan.models import LandAsset, MapOverlay
    from dokumen.models import LandUse
    from leasing.models import Contact, Lease
    from operasi.models import Korwil, Ticket
    from pengadaan.models import AcquisitionProject
    from plotsearch.models import AreaSearch

    found = []
    users = get_user_model().objects.filter(
        email__iendswith="@contoh.simlahan.invalid", is_active=True
    )
    if users.exists():
        found.append(
            Finding(
                FAIL,
                f"{users.count()} akun contoh masih aktif dan bisa dipakai masuk.",
            )
        )
    checks = (
        (
            FAIL,
            LandPlot.objects.filter(code__startswith="CONTOH-RMP-"),
            "lahan contoh tampil di peta portal publik",
        ),
        (
            FAIL,
            UwtRegion.objects.filter(name__endswith="(CONTOH)"),
            "wilayah tarif UWT contoh tampil di simulasi biaya portal publik",
        ),
        (
            WARN,
            AcquisitionProject.objects.filter(name__startswith="[CONTOH]"),
            "proyek pengadaan contoh",
        ),
        (
            WARN,
            LandAsset.objects.filter(code__startswith="CONTOH-AST-"),
            "aset lahan contoh",
        ),
        (
            WARN,
            Korwil.objects.filter(note__startswith="[contoh]"),
            "Korwil contoh",
        ),
        (
            WARN,
            Ticket.objects.filter(title__startswith="[contoh]"),
            "tiket contoh",
        ),
        (
            WARN,
            LandUse.objects.filter(reference__startswith="CONTOH-DOK-"),
            "pemanfaatan lahan contoh",
        ),
        (
            WARN,
            MapOverlay.objects.filter(note__startswith="[contoh]"),
            "lapisan referensi contoh",
        ),
        (
            WARN,
            Lease.objects.filter(note__startswith="[CONTOH]"),
            "sewa contoh (beserta tagihannya)",
        ),
        (
            WARN,
            Contact.objects.filter(email__iendswith="@contoh.simlahan.invalid"),
            "kontak contoh",
        ),
        (
            WARN,
            AreaSearch.objects.filter(description_intended_use__startswith="[CONTOH]"),
            "pencarian area contoh",
        ),
        (
            WARN,
            ContactMessage.objects.filter(email__iendswith="@contoh.simlahan.invalid"),
            "pesan kontak contoh",
        ),
    )
    for level, queryset, label in checks:
        count = queryset.count()
        if count:
            found.append(Finding(level, f"{count} {label}."))
    if found:
        found.append(
            Finding(
                INFO,
                "Hapus semua akun & data contoh sekaligus: python manage.py "
                "hapus_data_contoh",
            )
        )
    return found


def _initial_admin() -> list[Finding]:
    username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "")
    password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
    if not username or not password:
        return []
    user = get_user_model().objects.filter(username=username).first()
    if user is not None and user.is_active and user.check_password(password):
        if is_placeholder(password):
            # Sandi contoh dari .env.example diketahui publik: siapa pun bisa
            # masuk sebagai superuser.
            return [
                Finding(
                    FAIL,
                    f"Akun '{username}' memakai sandi contoh dari .env.example. "
                    "Segera ganti di /akun/sandi/ lalu kosongkan "
                    "DJANGO_SUPERUSER_PASSWORD.",
                )
            ]
        return [
            Finding(
                WARN,
                f"Akun '{username}' masih memakai sandi awal dari .env. Ganti di "
                "/akun/sandi/ lalu kosongkan DJANGO_SUPERUSER_PASSWORD.",
            )
        ]
    return []


def run_checks() -> list[Finding]:
    return _config() + _sample_data() + _initial_admin()
