import io

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import override_settings

from utils.production_check import FAIL, WARN, run_checks

READY = {
    "DEBUG": False,
    "ALLOWED_HOSTS": ["simlahan.example.go.id"],
    "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
    "DEFAULT_FROM_EMAIL": "noreply@pemda.go.id",
    "OFFICER_UI_URL": "https://simlahan.pemda.go.id",
    "CSRF_TRUSTED_ORIGINS": ["https://simlahan.pemda.go.id"],
    "SESSION_COOKIE_SECURE": True,
    "CSRF_COOKIE_SECURE": True,
    "FLAG_FILE_SCAN": True,
}


def messages(level):
    return [f.message for f in run_checks() if f.level == level]


@pytest.mark.django_db
def test_ready_configuration_passes(monkeypatch):
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)
    with override_settings(**READY):
        assert run_checks() == []
        out = io.StringIO()
        call_command("cek_produksi", stdout=out)
    assert "Siap dibuka untuk publik." in out.getvalue()


@pytest.mark.django_db
def test_unready_configuration_fails(monkeypatch):
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)
    settings = dict(
        READY,
        DEBUG=True,
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
        OFFICER_UI_URL="http://localhost:8080",
    )
    with override_settings(**settings):
        failed = messages(FAIL)
        with pytest.raises(CommandError):
            call_command("cek_produksi", stdout=io.StringIO())
    assert any("DEBUG" in m for m in failed)
    assert any("Surel" in m for m in failed)
    assert any("OFFICER_UI_URL" in m for m in failed)


@pytest.mark.django_db
def test_https_needs_secure_cookies_and_trusted_origin(monkeypatch):
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)
    settings = dict(READY, CSRF_TRUSTED_ORIGINS=[], SESSION_COOKIE_SECURE=False)
    with override_settings(**settings):
        failed = messages(FAIL)
    assert any("CSRF_TRUSTED_ORIGINS" in m for m in failed)
    assert any("COOKIE_SECURE" in m for m in failed)


@pytest.mark.django_db
def test_sample_accounts_and_initial_password_are_reported(monkeypatch):
    User = get_user_model()
    User.objects.create_user("contoh.uji", "contoh.uji@contoh.simlahan.invalid", "x")
    User.objects.create_user(
        "contoh.mati", "contoh.mati@contoh.simlahan.invalid", "x", is_active=False
    )
    User.objects.create_superuser("admin", "a@pemda.go.id", "Sandi-Awal-123")
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "admin")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "Sandi-Awal-123")
    with override_settings(**READY):
        failed = messages(FAIL)
        warned = messages(WARN)
    assert failed == ["1 akun contoh masih aktif dan bisa dipakai masuk."]
    assert any("sandi awal" in m for m in warned)


@pytest.mark.django_db
def test_delete_all_samples_command_runs_on_empty_db():
    out = io.StringIO()
    call_command("hapus_data_contoh", stdout=out)
    for name in ("dokumen", "operasi", "asetlahan", "sewa", "pengadaan", "alokasi"):
        assert f"{name}_contoh_rempang --hapus" in out.getvalue()
    assert "pengguna_contoh --hapus" in out.getvalue()
