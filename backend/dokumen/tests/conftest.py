import importlib

import pytest
from django.apps import apps as django_apps
from django.core.files.uploadedfile import SimpleUploadedFile

from alokasi.tests import conftest as _alokasi
from dokumen import enums, services
from dokumen.management.commands.dokumen_contoh_rempang import sample_pdf
from dokumen.models import LandUse
from file_operations.private_files import PrivateFileField
from utils.group_permissions import UserGroup

# Fixture alokasi dipakai ulang (diikat sebagai nama modul agar pytest menemukannya).
PASSWORD = _alokasi.PASSWORD
applicant = _alokasi.applicant
filled_application = _alokasi.filled_application
make_applicant = _alokasi.make_applicant
make_officer = _alokasi.make_officer
make_plot = _alokasi.make_plot
plot = _alokasi.plot
seeded = _alokasi.seeded
upload_required_docs = _alokasi.upload_required_docs


@pytest.fixture(autouse=True)
def private_storage(tmp_path):
    """Berkas privat alokasi & dokumen disimpan di direktori sementara."""
    storages = set()
    for label in ("alokasi", "dokumen"):
        for model in django_apps.get_app_config(label).get_models():
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
def dokumen_seeded(seeded):
    importlib.import_module("dokumen.migrations.0002_seed_defaults").seed(
        django_apps, None
    )
    return seeded


def pdf_upload(name="izin.pdf", title="Dokumen uji"):
    return SimpleUploadedFile(name, sample_pdf(title), content_type="application/pdf")


@pytest.fixture
def land_use(dokumen_seeded, applicant, plot):
    item = LandUse.objects.create(
        title="Pabrik uji",
        scheme=enums.Scheme.LEASE,
        holder=applicant,
        plot=plot,
        reference="KTR-1",
    )
    services.ensure_records(item)
    return item


@pytest.fixture
def officer(make_officer):
    return make_officer("petugas", UserGroup.PETUGAS_ALOKASI)


@pytest.fixture
def verifier(make_officer):
    return make_officer("verifikator", UserGroup.TIM_VERIFIKASI)


@pytest.fixture
def legal(make_officer):
    return make_officer("hukum", UserGroup.PETUGAS_HUKUM)


@pytest.fixture
def administrator(make_officer):
    return make_officer("administrator", UserGroup.PAAKAYTTAJA)


def record_of(land_use, code):
    return land_use.records.select_related("permit_type").get(permit_type__code=code)
