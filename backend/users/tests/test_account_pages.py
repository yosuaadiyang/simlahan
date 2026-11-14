from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from alokasi.models import Applicant
from users.management.commands.pengguna_contoh import APPLICANT_EMAIL, OFFICERS
from users.role_guide import APPLICANT_GUIDE, ROLE_GUIDES, render_markdown
from utils.group_permissions import UserGroup

PASSWORD = "Sandi-Lama-2026!x"
DOCS = Path(__file__).resolve().parents[3] / "docs" / "panduan-peran.md"


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def make_user(username, *groups):
    user = get_user_model().objects.create_user(
        username=username, email=f"{username}@instansi.go.id", password=PASSWORD
    )
    for group in groups:
        user.groups.add(
            Group.objects.get_or_create(pk=group, defaults={"name": group.name})[0]
        )
    return user


def test_every_role_has_a_guide_matching_its_sample_account():
    assert set(ROLE_GUIDES) == set(UserGroup)
    samples = {group: username for username, group, *_rest in OFFICERS}
    for group, guide in ROLE_GUIDES.items():
        assert guide.sample == samples[group]
        assert guide.menus and guide.can and guide.limits
    assert APPLICANT_GUIDE.sample == APPLICANT_EMAIL


def test_docs_file_is_generated_from_the_guide():
    # Buat ulang: cd backend && python manage.py panduan_peran > ../docs/panduan-peran.md
    assert DOCS.read_text(encoding="utf-8") == render_markdown()


@pytest.mark.django_db
def test_guide_shows_only_own_role(client):
    client.force_login(make_user("penilai", UserGroup.PENILAI))
    page = client.get("/akun/panduan/").content.decode()
    assert "Penilai Pertanahan" in page
    assert "Petugas Penagihan" not in page
    assert "Menyiapkan akun petugas" not in page
    assert "contoh.penilai" not in page


@pytest.mark.django_db
def test_administrator_sees_every_role(client):
    client.force_login(make_user("admin2", UserGroup.PAAKAYTTAJA))
    page = client.get("/akun/panduan/").content.decode()
    for guide in list(ROLE_GUIDES.values()) + [APPLICANT_GUIDE]:
        assert guide.name in page
    assert "Menyiapkan akun petugas" in page


@pytest.mark.django_db
def test_user_without_role_gets_a_clear_notice(client):
    client.force_login(make_user("tanpaperan"))
    page = client.get("/akun/panduan/").content.decode()
    assert "belum memiliki peran" in page


@pytest.mark.django_db
def test_anonymous_and_applicant_are_sent_elsewhere(client):
    for url in ("/akun/panduan/", "/akun/sandi/"):
        assert client.get(url)["Location"] == "/"
    applicant = make_user("pemohon@contoh.id")
    Applicant.objects.create(
        user=applicant, name="PT A", pic_name="A", phone="1", address="A"
    )
    client.force_login(applicant)
    for url in ("/akun/panduan/", "/akun/sandi/"):
        assert client.get(url)["Location"].startswith("/portal/")


@pytest.mark.django_db
def test_officer_changes_own_password_and_old_tokens_are_revoked(client):
    user = make_user("penyusun", UserGroup.VALMISTELIJA)
    RefreshToken.for_user(user)
    client.force_login(user)
    response = client.post(
        "/akun/sandi/",
        {
            "old_password": PASSWORD,
            "new_password1": "Sandi-Baru-2026!y",
            "new_password2": "Sandi-Baru-2026!y",
        },
    )
    assert response.status_code == 200
    assert "berhasil diganti" in response.content.decode()
    user.refresh_from_db()
    assert user.check_password("Sandi-Baru-2026!y")
    assert not OutstandingToken.objects.filter(
        user=user, blacklistedtoken__isnull=True
    ).exists()
    # Sesi peramban ini tetap berlaku.
    assert client.get("/akun/panduan/").status_code == 200


@pytest.mark.django_db
def test_wrong_old_password_is_limited(client):
    user = make_user("operator", UserGroup.SYOTTAJA)
    client.force_login(user)
    data = {
        "old_password": "salah",
        "new_password1": "Sandi-Baru-2026!y",
        "new_password2": "Sandi-Baru-2026!y",
    }
    for _attempt in range(9):
        assert client.post("/akun/sandi/", data).status_code == 200
    # Kesalahan ke-10 langsung mengunci; sandi benar pun ditolak sementara.
    assert client.post("/akun/sandi/", data).status_code == 429
    data["old_password"] = PASSWORD
    response = client.post("/akun/sandi/", data)
    assert response.status_code == 429
    user.refresh_from_db()
    assert user.check_password(PASSWORD)


@pytest.mark.django_db
def test_admin_header_links_to_the_guide(client):
    client.force_login(make_user("aset", UserGroup.PETUGAS_ASET))
    assert "/akun/panduan/" in client.get("/admin/").content.decode()


@pytest.mark.django_db
def test_password_attempt_limit_is_counted_in_database(client):
    """Batas sandi lama dihitung atomik di basis data, bukan get+set cache."""
    from django.core.cache import cache

    from utils.models import RateCounter

    user = make_user("operator-db", UserGroup.SYOTTAJA)
    client.force_login(user)
    data = {
        "old_password": "salah",
        "new_password1": "Sandi-Baru-2026!y",
        "new_password2": "Sandi-Baru-2026!y",
    }
    for _attempt in range(3):
        client.post("/akun/sandi/", data)
        cache.clear()  # cache yang hilang/terbagi tidak menghapus hitungan
    counter = RateCounter.objects.get(key=f"akun-sandi-gagal:{user.pk}")
    assert counter.count == 3
    # Galat selain sandi lama (sandi baru tidak cocok) tidak memakai jatah.
    data.update(old_password=PASSWORD, new_password2="beda")
    client.post("/akun/sandi/", data)
    counter.refresh_from_db()
    assert counter.count == 3
