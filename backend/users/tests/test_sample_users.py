import io

import pytest
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command

from alokasi.models import Applicant
from leasing.models import ServiceUnit
from pengadaan.management.commands.pengadaan_contoh_rempang import (
    SAMPLE_PROJECT_NAME,
)
from pengadaan.models import AcquisitionProject
from users.management.commands.pengguna_contoh import (
    APPLICANT_EMAIL,
    OFFICERS,
    sample_users,
)
from utils.group_permissions import ADMIN_PANEL_GROUPS, UserGroup

PASSWORD = "Contoh-Uji-2026!x"


def run(*args) -> str:
    out = io.StringIO()
    call_command("pengguna_contoh", *args, stdout=out)
    return out.getvalue()


def test_creates_one_account_per_role_with_scopes(samples):
    project, korwil = samples
    output = run()

    users = {user.username: user for user in sample_users()}
    assert len(users) == len(OFFICERS) + 2
    for username, group, _role, _where in OFFICERS:
        user = users[username]
        assert [g.pk for g in user.groups.all()] == [group]
        assert user.is_staff == (group in ADMIN_PANEL_GROUPS)
        assert not user.is_superuser
        assert set(user.service_units.all()) == set(ServiceUnit.objects.all())
        # Sandi acak tampil sekali dan bisa dipakai masuk.
        password = output.split(username, 1)[1].split()[0]
        assert authenticate(username=username, password=password) == user

    applicant = users[APPLICANT_EMAIL]
    assert Applicant.objects.filter(user=applicant).exists()
    assert not applicant.groups.exists() and not applicant.is_staff
    assert not applicant.service_units.exists()

    assert set(project.assigned_users.values_list("username", flat=True)) == {
        "contoh.penilai",
        "contoh.instansi",
    }
    korwil.refresh_from_db()
    assert korwil.coordinator.username == "contoh.korwil"
    assert list(korwil.members.values_list("username", flat=True)) == [
        "contoh.lapangan"
    ]


def test_rerun_keeps_passwords_and_resets_roles(samples):
    run("--sandi", PASSWORD)
    user = get_user_model().objects.get(username="contoh.penilai")
    user.groups.add(Group.objects.get(pk=UserGroup.PAAKAYTTAJA))

    output = run()

    assert "(sandi tidak diubah)" in output
    assert PASSWORD not in output
    assert authenticate(username="contoh.penilai", password=PASSWORD) == user
    # Hak tambahan dicabut kembali: satu akun, satu peran.
    assert [g.pk for g in user.groups.all()] == [UserGroup.PENILAI]
    user.refresh_from_db()
    assert not user.is_staff

    output = run("--sandi-baru")
    assert "(sandi tidak diubah)" not in output
    assert authenticate(username="contoh.penilai", password=PASSWORD) is None


def test_without_sample_data_explains_missing_scopes(groups, unit):
    output = run()
    assert "pengadaan_contoh_rempang" in output
    assert "operasi_contoh_rempang" in output
    assert sample_users().count() == len(OFFICERS) + 2


def test_rejects_weak_password_and_missing_groups(groups, unit):
    with pytest.raises(CommandError):
        run("--sandi", "123")
    assert not sample_users().exists()

    Group.objects.filter(pk=UserGroup.KOORDINATOR_WILAYAH).delete()
    with pytest.raises(CommandError, match="simlahan_bootstrap"):
        run()


def test_never_touches_real_account_with_same_username(groups, unit):
    real = get_user_model().objects.create_user(
        username="contoh.aset", email="aset@instansi.go.id", password=PASSWORD
    )
    with pytest.raises(CommandError):
        run()
    real.refresh_from_db()
    assert real.email == "aset@instansi.go.id"
    assert not real.groups.exists()
    assert not sample_users().exists()


def test_delete_removes_only_sample_accounts(samples):
    real = get_user_model().objects.create_user(
        username="petugas", email="petugas@instansi.go.id", password=PASSWORD
    )
    run()
    worked = get_user_model().objects.get(username="contoh.alokasi")
    LogEntry.objects.create(user=worked, object_repr="Data kerja", action_flag=ADDITION)

    output = run("--hapus")

    remaining = list(sample_users())
    assert remaining == [worked]
    worked.refresh_from_db()
    # Akun dengan catatan kerja dinonaktifkan, bukan dihapus.
    assert not worked.is_active and not worked.is_staff
    assert not worked.has_usable_password() and not worked.groups.exists()
    assert "contoh.alokasi" in output
    assert LogEntry.objects.filter(user=worked).exists()
    assert not Applicant.objects.exists()
    assert get_user_model().objects.filter(pk=real.pk).exists()
    assert AcquisitionProject.objects.filter(name=SAMPLE_PROJECT_NAME).exists()


def test_recreate_after_delete_gives_deactivated_account_a_password(samples):
    run()
    worked = get_user_model().objects.get(username="contoh.korwil")
    LogEntry.objects.create(user=worked, object_repr="Data kerja", action_flag=ADDITION)
    run("--hapus")

    output = run()

    password = output.split("contoh.korwil", 1)[1].split()[0]
    worked.refresh_from_db()
    assert worked.is_active and worked.is_staff
    assert authenticate(username="contoh.korwil", password=password) == worked
