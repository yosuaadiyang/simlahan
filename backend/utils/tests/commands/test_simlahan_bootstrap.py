import pytest
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command

from leasing.models import Municipality, ServiceUnit
from users.models import User
from utils.group_permissions import UserGroup


@pytest.mark.django_db
def test_bootstrap_loads_master_data_and_creates_admin(monkeypatch):
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "adminuji")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "KataSandiUji123")
    # Data master bisa sudah dimuat oleh fikstur sesi paket lain; paksa muat ulang
    # agar tes tidak bergantung pada urutan eksekusi.
    call_command("simlahan_bootstrap", "--force-fixtures")

    assert Municipality.objects.filter(name="Kota Batam").exists()
    assert Group.objects.filter(pk=UserGroup.PELAKSANA_PENGADAAN).exists()
    admin = User.objects.get(username="adminuji")
    assert admin.is_superuser
    assert admin.check_password("KataSandiUji123")
    assert admin.service_units.count() == ServiceUnit.objects.count() > 0
    assert admin.groups.filter(pk=UserGroup.PAAKAYTTAJA).exists()
    pelaksana = Group.objects.get(pk=UserGroup.PELAKSANA_PENGADAAN)
    assert pelaksana.permissions.filter(codename="add_acquisitionproject").exists()

    # Idempoten: dijalankan ulang tanpa galat dan tanpa menggandakan admin.
    call_command("simlahan_bootstrap")
    assert User.objects.filter(username="adminuji").count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "password, message",
    [
        ("ganti-kata-sandi-admin", "nilai contoh"),
        ("1234567890", "aturan sandi"),
        ("pendek", "aturan sandi"),
    ],
)
def test_bootstrap_refuses_placeholder_or_weak_admin_password_in_production(
    monkeypatch, settings, password, message
):
    settings.DEBUG = False
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "adminuji")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", password)
    with pytest.raises(CommandError, match=message):
        call_command("simlahan_bootstrap")
    assert not User.objects.filter(username="adminuji").exists()


@pytest.mark.django_db
def test_bootstrap_accepts_strong_admin_password_in_production(monkeypatch, settings):
    settings.DEBUG = False
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "adminuji")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "Rahasia-Kuat-9481")
    call_command("simlahan_bootstrap")
    assert User.objects.get(username="adminuji").check_password("Rahasia-Kuat-9481")
