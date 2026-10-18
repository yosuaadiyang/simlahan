import importlib
import io

import pytest
from django.apps import apps as django_apps
from django.contrib.auth.models import Group
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.management import call_command

from asetlahan.models import LandAsset, ModuleSettings
from file_operations.private_files import PrivateFileField
from leasing.models import ServiceUnit
from users.models import User
from utils.group_permissions import UserGroup


@pytest.fixture(autouse=True)
def private_storage(tmp_path):
    """Simpan berkas privat uji di direktori sementara."""
    storages = set()
    for model in django_apps.get_app_config("asetlahan").get_models():
        for field in model._meta.fields:
            if isinstance(field, PrivateFileField):
                storages.add(field.storage)
    saved = []
    for storage in storages:
        saved.append((storage, storage._location))
        storage._location = str(tmp_path)
        storage.__dict__.pop("base_location", None)
        storage.__dict__.pop("location", None)
    yield tmp_path
    for storage, location in saved:
        storage._location = location
        storage.__dict__.pop("base_location", None)
        storage.__dict__.pop("location", None)


@pytest.fixture
def seeded(db):
    """Data awal dari migrasi (tes berjalan --nomigrations) + izin grup."""
    for group in UserGroup:
        Group.objects.get_or_create(
            pk=group.value, defaults={"name": group.name.title()}
        )
    module = importlib.import_module("asetlahan.migrations.0002_seed_defaults")
    module.seed(django_apps, _SchemaEditor())
    call_command("set_group_model_permissions", verbosity=0, stdout=io.StringIO())
    return ModuleSettings.load()


class _SchemaEditor:
    class connection:
        alias = "default"


@pytest.fixture
def units(db):
    return (
        ServiceUnit.objects.create(name="Unit Rempang"),
        ServiceUnit.objects.create(name="Unit Galang"),
    )


def make_user(username, *groups, units=(), superuser=False, email=None):
    user = User.objects.create_user(
        username=username,
        password="RahasiaKuat123!",
        email=email if email is not None else f"{username}@example.go.id",
        is_superuser=superuser,
        is_staff=True,
    )
    for group in groups:
        user.groups.add(Group.objects.get(pk=group))
    if units:
        user.service_units.set(units)
    return user


@pytest.fixture
def admin(seeded):
    return make_user("kepala", superuser=True)


@pytest.fixture
def officer(seeded, units):
    return make_user("aset", UserGroup.PETUGAS_ASET, units=[units[0]])


@pytest.fixture
def field_officer(seeded, units):
    return make_user("lapangan", UserGroup.PETUGAS_LAPANGAN, units=[units[0]])


@pytest.fixture
def lawyer(seeded, units):
    return make_user("hukum", UserGroup.PETUGAS_HUKUM, units=[units[0]])


def square(x=104.10, y=0.80, size=0.001):
    return MultiPolygon(
        Polygon(((x, y), (x + size, y), (x + size, y + size), (x, y + size), (x, y))),
        srid=4326,
    )


@pytest.fixture
def make_asset(seeded):
    counter = {"n": 0}

    def _make(**kwargs):
        counter["n"] += 1
        values = {
            "code": f"AST-T{counter['n']:03d}",
            "name": f"Aset uji {counter['n']}",
            "geometry": square(104.10 + counter["n"] * 0.01),
        }
        values.update(kwargs)
        return LandAsset.objects.create(**values)

    return _make
