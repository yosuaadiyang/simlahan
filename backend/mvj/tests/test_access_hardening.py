"""Batas hak akses lintas modul: batchrun, login, dokumentasi API, token, formulir."""

import io

import pytest
from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import User
from utils.group_permissions import UserGroup

pytestmark = pytest.mark.django_db

PASSWORD = "RahasiaKuat123!"


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def groups(db):
    for group in UserGroup:
        Group.objects.get_or_create(
            pk=group.value, defaults={"name": group.name.title()}
        )
    call_command("set_group_model_permissions", verbosity=0, stdout=io.StringIO())


def _user(username, *perms, staff=False, group=None):
    user = User.objects.create_user(
        username=username, password=PASSWORD, is_staff=staff
    )
    for perm in perms:
        app_label, codename = perm.split(".")
        user.user_permissions.add(
            Permission.objects.get(content_type__app_label=app_label, codename=codename)
        )
    if group is not None:
        user.groups.add(Group.objects.get(pk=group))
    return User.objects.get(pk=user.pk)


def _api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


# --------------------------------------------------------------------------
# Batchrun: perintah "executable" menjalankan program di server
# --------------------------------------------------------------------------


def test_only_superuser_writes_batchrun_jobs(groups, client, job_factory):
    administrator = _user("adm", staff=True, group=UserGroup.PAAKAYTTAJA)
    for model in ("command", "job", "scheduledjob"):
        assert administrator.has_perm(f"batchrun.view_{model}")
        for action in ("add", "change", "delete"):
            assert not administrator.has_perm(f"batchrun.{action}_{model}")

    # Walau izin model diberikan manual, admin tetap menolak non-superuser.
    granted = _user(
        "granted",
        "batchrun.view_command",
        "batchrun.add_command",
        "batchrun.change_command",
        "batchrun.delete_command",
        staff=True,
    )
    job = job_factory(name="uji")
    client.force_login(granted)
    assert client.get(reverse("admin:batchrun_command_add")).status_code == 403
    response = client.post(
        reverse("admin:batchrun_command_change", args=[job.command.pk]),
        {"type": "executable", "name": "/bin/sh"},
    )
    assert response.status_code == 403
    job.command.refresh_from_db()
    assert job.command.type.value == "django-manage"

    root = User.objects.create_superuser("root", "r@x.id", PASSWORD)
    client.force_login(root)
    assert client.get(reverse("admin:batchrun_command_add")).status_code == 200


def test_job_log_download_needs_view_permission(client, job_run_log_factory):
    now = timezone.now()
    log = job_run_log_factory(
        content="rahasia", start=now, end=now, entry_count=0, error_count=0
    )
    url = reverse("admin:batchrun_jobrunlog_download_content", args=[log.pk])
    client.force_login(_user("staf", staff=True))
    assert client.get(url).status_code == 403
    client.force_login(_user("pembaca", "batchrun.view_jobrunlog", staff=True))
    response = client.get(url)
    assert response.status_code == 200 and b"rahasia" in response.content


# --------------------------------------------------------------------------
# Login, dokumentasi API, dan token
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/admin/login/", "/auth/login/"])
def test_session_login_is_throttled(path):
    client = Client()
    for _ in range(10):
        response = client.post(path, {"username": "x", "password": "salah"})
        assert response.status_code != 429
    response = client.post(path, {"username": "x", "password": "salah"})
    assert response.status_code == 429


def test_throttle_ignores_spoofed_forwarded_for(settings):
    from rest_framework.settings import api_settings

    assert settings.REST_FRAMEWORK["NUM_PROXIES"] == (
        settings.TRUSTED_PROXY_COUNT if settings.TRUST_PROXY_HEADERS else 0
    )
    assert api_settings.NUM_PROXIES is not None


@pytest.mark.parametrize("path", ["/docs/", "/redoc/", "/swagger.json"])
def test_api_docs_need_login(path):
    response = Client().get(path)
    assert response.status_code == 302
    assert response.url.startswith("/auth/login/")
    client = Client()
    client.force_login(_user("petugas"))
    assert client.get(path).status_code == 200


def test_password_change_revokes_old_tokens():
    user = _user("ganti")
    client = APIClient()
    login = client.post(
        "/v1/auth/login/", {"username": "ganti", "password": PASSWORD}, format="json"
    ).json()
    old = APIClient()
    old.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    assert old.get("/v1/auth/me/").status_code == 200

    response = old.post(
        "/v1/auth/password/",
        {"old_password": PASSWORD, "new_password": "SandiBaru987!x"},
        format="json",
    )
    assert response.status_code == 200
    fresh = response.json()
    # Access token lama langsung ditolak; refresh token lama masuk daftar hitam.
    assert old.get("/v1/auth/me/").status_code == 401
    assert (
        client.post(
            "/v1/auth/refresh/", {"refresh": login["refresh"]}, format="json"
        ).status_code
        == 401
    )
    new = APIClient()
    new.credentials(HTTP_AUTHORIZATION=f"Bearer {fresh['access']}")
    assert new.get("/v1/auth/me/").json()["username"] == user.username


# --------------------------------------------------------------------------
# Pencarian lahan & formulir (warisan modul sewa)
# --------------------------------------------------------------------------


def test_plot_search_target_update_needs_permission(
    plot_search_target_factory_with_sub_factories,
):
    target = plot_search_target_factory_with_sub_factories()
    response = _api(_user("biasa")).patch(
        f"/v1/plot_search_target/{target.pk}/", {"info_links": []}, format="json"
    )
    assert response.status_code == 403


@pytest.mark.parametrize("path", ["/v1/area_search/", "/v1/answer/", "/v1/attachment/"])
def test_create_needs_add_permission(path):
    assert _api(_user("biasa")).post(path, {}, format="json").status_code == 403


def test_preparer_only_reaches_own_plot_search_answers(
    user_factory, target_status_factory
):
    preparer = user_factory(username="penyusun")
    own = target_status_factory()
    other = target_status_factory()
    own.plot_search_target.plot_search.preparers.add(preparer)
    client = _api(preparer)
    assert client.get(f"/v1/answer/{other.answer.pk}/").status_code == 404
    assert client.delete(f"/v1/answer/{other.answer.pk}/").status_code == 404
    assert type(other.answer).objects.filter(pk=other.answer.pk).exists()
    listed = client.get("/v1/answer/").json()["results"]
    assert [row["id"] for row in listed] == [own.answer.pk]


# --------------------------------------------------------------------------
# Sewa: perubahan hanya untuk unit layanan sendiri
# --------------------------------------------------------------------------


def test_create_charge_limited_to_own_service_unit(lease_factory, service_unit_factory):
    own_unit = service_unit_factory()
    lease = lease_factory()
    user = _user("penagih", "leasing.add_invoice")
    user.service_units.add(own_unit)
    response = _api(user).post(
        "/v1/lease_create_charge/",
        {"lease": lease.pk, "due_date": "2026-11-01", "rows": []},
        format="json",
    )
    assert response.status_code == 403, response.content
    assert not lease.invoices.exists()


def test_decision_copy_limited_to_own_service_unit(
    lease_factory, decision_factory, service_unit_factory
):
    lease = lease_factory()
    target = lease_factory(service_unit=lease.service_unit)
    foreign = lease_factory(service_unit=service_unit_factory())
    decision = decision_factory(lease=lease)
    user = _user("penyalin", "leasing.add_decision")
    user.service_units.add(service_unit_factory())
    url = f"/v1/decision_copy_to_leases/?decision={decision.pk}&leases={target.pk}"
    assert _api(user).post(url).status_code == 403
    assert target.decisions.count() == 0
    user.service_units.add(lease.service_unit)
    assert _api(user).post(f"{url}&leases={foreign.pk}").status_code == 200
    assert target.decisions.count() == 1
    # Sewa unit lain dilewati.
    assert foreign.decisions.count() == 0
