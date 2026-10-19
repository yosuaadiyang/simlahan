import io

import pytest
from django.apps import apps as django_apps
from django.contrib.auth.models import Group
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client

from file_operations.private_files import PrivateFileField
from leasing.models import ServiceUnit
from operasi.models import Korwil
from users.models import User
from utils.group_permissions import UserGroup

PASSWORD = "RahasiaKuat123!"


@pytest.fixture(autouse=True)
def private_storage(tmp_path):
    """Simpan berkas privat uji di direktori sementara."""
    storages = set()
    for model in django_apps.get_app_config("operasi").get_models():
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


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def seeded(db):
    """Grup bawaan (tes berjalan --nomigrations) + izin grup."""
    for group in UserGroup:
        Group.objects.get_or_create(
            pk=group.value, defaults={"name": group.name.title()}
        )
    call_command("set_group_model_permissions", verbosity=0, stdout=io.StringIO())


@pytest.fixture
def units(db):
    return (
        ServiceUnit.objects.create(name="Unit Rempang"),
        ServiceUnit.objects.create(name="Unit Galang"),
    )


def make_user(username, *groups, units=(), superuser=False, email=None):
    user = User.objects.create_user(
        username=username,
        password=PASSWORD,
        email=email if email is not None else f"{username}@example.go.id",
        first_name=username.title(),
        is_superuser=superuser,
        is_staff=True,
    )
    for group in groups:
        user.groups.add(Group.objects.get(pk=group))
    if units:
        user.service_units.set(units)
    return user


def login(user) -> Client:
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def admin_user(seeded):
    return make_user("kepala", UserGroup.PAAKAYTTAJA, superuser=True)


@pytest.fixture
def manager(seeded, units):
    """Administrator (grup) bukan superuser."""
    return make_user("pengelola", UserGroup.PAAKAYTTAJA, units=[units[0]])


@pytest.fixture
def coordinator(seeded, units):
    return make_user("korwil", UserGroup.KOORDINATOR_WILAYAH, units=[units[0]])


@pytest.fixture
def field(seeded, units):
    return make_user("lapangan", UserGroup.PETUGAS_LAPANGAN, units=[units[0]])


@pytest.fixture
def other_field(seeded, units):
    return make_user("lapangan2", UserGroup.PETUGAS_LAPANGAN, units=[units[1]])


def square(x=104.10, y=0.80, size=0.01):
    return MultiPolygon(
        Polygon(((x, y), (x + size, y), (x + size, y + size), (x, y + size), (x, y))),
        srid=4326,
    )


def inside(korwil) -> Point:
    centroid = korwil.geometry.centroid
    return Point(centroid.x, centroid.y, srid=4326)


@pytest.fixture
def korwil(coordinator, field, units):
    item = Korwil.objects.create(
        code="A",
        name="Pasir Panjang",
        geometry=square(),
        coordinator=coordinator,
        service_unit=units[0],
    )
    item.members.add(field)
    return item


@pytest.fixture
def korwil_b(other_field, units):
    item = Korwil.objects.create(
        code="B", name="Sembulang", geometry=square(104.20), service_unit=units[1]
    )
    item.members.add(other_field)
    return item


def png_bytes(size=(4, 4), color=(16, 185, 129)) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def photo(name="foto.png") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, png_bytes(), content_type="image/png")
