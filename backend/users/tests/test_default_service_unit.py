"""Petugas tanpa unit layanan tidak lagi melihat galat di aplikasi petugas."""

import importlib

import pytest
from django.apps import apps as django_apps
from django.core.cache import cache
from django.urls import reverse

from alokasi.models import Applicant
from leasing.models import ServiceUnit

PASSWORD = "Sandi-Uji-123"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_throttle():
    cache.clear()


@pytest.fixture(autouse=True)
def no_service_units():
    # Migrasi 0004 sudah membuat unit bawaan di basis data uji; tiap tes
    # menyiapkan unitnya sendiri.
    ServiceUnit.objects.all().delete()


def _user(django_user_model, username, **kwargs):
    return django_user_model.objects.create_user(
        username=username, email=f"{username}@contoh.id", password=PASSWORD, **kwargs
    )


def test_login_assigns_the_only_service_unit(client, django_user_model):
    unit = ServiceUnit.objects.create(name="Unit Layanan Utama")
    officer = _user(django_user_model, "petugas", is_staff=True)
    response = client.post(
        reverse("v1:auth-login"),
        {"username": "petugas", "password": PASSWORD},
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
    assert list(officer.service_units.all()) == [unit]
    assert response.json()["user"]["service_units"][0]["id"] == unit.id


def test_no_automatic_choice_between_several_units(django_user_model):
    ServiceUnit.objects.create(name="Unit A")
    ServiceUnit.objects.create(name="Unit B")
    officer = _user(django_user_model, "petugas")
    officer.update_service_units()
    assert not officer.service_units.exists()


def test_portal_applicants_get_no_service_unit(django_user_model):
    ServiceUnit.objects.create(name="Unit Layanan Utama")
    user = _user(django_user_model, "pemohon")
    Applicant.objects.create(user=user, name="PT Uji", pic_name="Uji", phone="0778")
    user.refresh_from_db()
    user.update_service_units()
    assert not user.service_units.exists()


def test_migration_creates_default_unit_for_officers(django_user_model):
    officer = _user(django_user_model, "petugas")
    applicant_user = _user(django_user_model, "pemohon")
    Applicant.objects.create(
        user=applicant_user, name="PT Uji", pic_name="Uji", phone="0778"
    )
    migration = importlib.import_module("users.migrations.0004_default_service_unit")
    migration.create_default_service_unit(django_apps, None)
    unit = ServiceUnit.objects.get()
    assert unit.name == "Unit Layanan Utama"
    assert list(officer.service_units.all()) == [unit]
    assert not applicant_user.service_units.exists()
    # Dijalankan ulang tidak membuat unit kedua.
    migration.create_default_service_unit(django_apps, None)
    assert ServiceUnit.objects.count() == 1
