"""Batas akses setiap peran, diuji dengan akun dari ``pengguna_contoh``."""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client

from pengadaan.models import AcquisitionProject
from users.management.commands.pengguna_contoh import APPLICANT_EMAIL, OFFICERS

from .test_sample_users import run

ROLES = [username.split(".", 1)[1] for username, *_rest in OFFICERS] + ["pemohon"]
LEASING = {"penelusur", "penyusun", "kontrak", "operator", "ahlihukum", "penagihan"}
ACQUISITION = {"pelaksana", "satgas", "penilai", "instansi"}
PANEL = {
    "administrator",
    "alokasi",
    "verifikasi",
    "aset",
    "hukum",
    "lapangan",
    "korwil",
}
COMMAND = {"administrator", "aset", "lapangan", "korwil"}

ALLOWED = {
    "/admin/": PANEL,
    "/admin/alokasi/application/": {"administrator", "alokasi", "verifikasi"},
    "/admin/alokasi/invoice/": {"administrator", "alokasi", "verifikasi"},
    "/admin/asetlahan/dasbor/": {
        "administrator",
        "aset",
        "hukum",
        "lapangan",
        "korwil",
    },
    "/admin/asetlahan/legalcase/": {"administrator", "aset", "hukum"},
    "/admin/operasi/resident/": COMMAND,
    "/admin/users/user/": {"administrator"},
    "/admin/leasing/lease/": {"administrator"},
    "/admin/pengadaan/acquisitionproject/": {"administrator"},
    "/komando/": COMMAND,
    "/komando/api/warga/": COMMAND,
    "/aset/lapangan/": {"administrator", "aset", "lapangan"},
    "/v1/lease/": LEASING | {"administrator"},
    "/v1/invoice/": (LEASING - {"penelusur"}) | {"administrator"},
    "/v1/pengadaan/project/": LEASING | ACQUISITION | {"administrator"},
    "/v1/aset/asset/": {"administrator", "aset", "hukum", "lapangan", "korwil"},
    "/portal/akun/": {"pemohon"},
}


@pytest.fixture
def accounts(samples):
    run()
    users = {u.username: u for u in get_user_model().objects.all()}
    accounts = {role: users[f"contoh.{role}"] for role in ROLES if role != "pemohon"}
    accounts["pemohon"] = users[APPLICANT_EMAIL]
    return accounts


def test_every_role_reaches_only_its_own_pages(accounts):
    wrong = []
    for role, user in accounts.items():
        cache.clear()
        client = Client()
        client.force_login(user)
        for url, allowed in ALLOWED.items():
            response = client.get(url, HTTP_ACCEPT="application/json")
            status = response.status_code
            if role in allowed:
                if status != 200:
                    wrong.append(f"{role} {url}: {status}, seharusnya 200")
            elif status == 302:
                # Ditolak berarti diarahkan ke halaman masuk atau ke portal.
                location = response["Location"]
                if "login" not in location and not location.startswith("/portal/"):
                    wrong.append(f"{role} {url}: diarahkan ke {location}")
            elif status not in (401, 403):
                wrong.append(f"{role} {url}: {status}, seharusnya ditolak")
    assert not wrong, "\n".join(wrong)


def test_appraiser_and_agency_only_see_assigned_projects(accounts, samples):
    project, _korwil = samples
    AcquisitionProject.objects.create(
        name="Proyek lain", requiring_agency="Lain", municipality=project.municipality
    )
    for role, expected in (("penilai", 1), ("instansi", 1), ("pelaksana", 2)):
        client = Client()
        client.force_login(accounts[role])
        data = client.get("/v1/pengadaan/project/").json()
        names = [row["name"] for row in data["results"]]
        assert len(names) == expected, (role, names)
        assert project.name in names


def test_applicant_cannot_use_officer_login(accounts):
    response = Client().post(
        "/v1/auth/login/",
        {"username": APPLICANT_EMAIL, "password": "x"},
        content_type="application/json",
    )
    assert response.status_code in (401, 403)
