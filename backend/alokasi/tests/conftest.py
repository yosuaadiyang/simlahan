import importlib
import io
from decimal import Decimal

import pytest
from django.apps import apps as django_apps
from django.contrib.auth.models import Group
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from alokasi import enums, services
from alokasi.models import (
    AllocationSettings,
    Applicant,
    ApplicationDocument,
    LandPlot,
    RequirementDocType,
    VerificationCriterion,
)
from file_operations.private_files import PrivateFileField
from utils.group_permissions import UserGroup

PASSWORD = "RahasiaKuat123!"


@pytest.fixture(autouse=True)
def private_storage(tmp_path):
    """Simpan berkas privat uji di direktori sementara."""
    storages = set()
    for model in django_apps.get_app_config("alokasi").get_models():
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
    module = importlib.import_module("alokasi.migrations.0002_seed_defaults")
    module.seed(django_apps, None)
    call_command("set_group_model_permissions", verbosity=0, stdout=io.StringIO())
    config = AllocationSettings.load()
    config.allocation_admin_fee = Decimal("2500000")
    config.transfer_admin_fee = Decimal("1000000")
    config.transfer_fee_per_m2 = Decimal("100")
    config.save()
    return config


def square(x=104.10, y=0.80, size=0.001):
    return MultiPolygon(
        Polygon(((x, y), (x + size, y), (x + size, y + size), (x, y + size), (x, y))),
        srid=4326,
    )


@pytest.fixture
def make_plot(seeded):
    def _make(**kwargs):
        values = {
            "name": "Kavling Industri Rempang",
            "area_m2": Decimal("10000"),
            "uwt_rate_per_m2_year": Decimal("1000"),
            "term_years": 30,
            "district": "Galang",
            "village": "Rempang Cate",
            "intended_use": "Industri",
            "geometry": square(),
        }
        values.update(kwargs)
        return LandPlot.objects.create(**values)

    return _make


@pytest.fixture
def plot(make_plot):
    return make_plot()


@pytest.fixture
def make_applicant(db, django_user_model):
    counter = {"n": 0}

    def _make(name=None, active=True, **kwargs):
        counter["n"] += 1
        n = counter["n"]
        email = f"pemohon{n}@contoh.id"
        user = django_user_model.objects.create_user(
            username=email, email=email, password=PASSWORD, is_active=active
        )
        values = {
            "applicant_type": enums.ApplicantType.COMPANY,
            "name": name or f"PT Contoh {n}",
            "nib": f"91200000000{n:02d}",
            "pic_name": f"Direktur {n}",
            "phone": "0778000000",
            "address": "Jl. Contoh No. 1, Batam",
        }
        values.update(kwargs)
        return Applicant.objects.create(user=user, **values)

    return _make


@pytest.fixture
def applicant(make_applicant):
    return make_applicant()


@pytest.fixture
def make_officer(seeded, django_user_model):
    def _make(username, group):
        user = django_user_model.objects.create_user(
            username=username, email=f"{username}@instansi.go.id", password=PASSWORD
        )
        user.groups.add(Group.objects.get(pk=group))
        user.refresh_from_db()
        return user

    return _make


@pytest.fixture
def officer(make_officer):
    return make_officer("petugas", UserGroup.PETUGAS_ALOKASI)


@pytest.fixture
def verifier(make_officer):
    return make_officer("verifikator", UserGroup.TIM_VERIFIKASI)


def pdf_file(name="dokumen.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4\n%uji\n", content_type="application/pdf")


@pytest.fixture
def upload_required_docs():
    def _upload(application):
        for doc_type in RequirementDocType.for_application(application).filter(
            is_required=True
        ):
            ApplicationDocument.objects.create(
                application=application,
                doc_type=doc_type,
                file=pdf_file(),
                original_name="dokumen.pdf",
            )

    return _upload


@pytest.fixture
def filled_application(applicant, plot, upload_required_docs):
    application = services.create_allocation_application(applicant, plot)
    application.activity = "Pabrik komponen elektronik"
    application.investment_value = Decimal("5000000000")
    application.workforce = 120
    application.development_months = 24
    application.description = "Pembangunan pabrik dua tahap."
    application.save()
    upload_required_docs(application)
    return application


def score_all(application, verifier, value):
    from alokasi.models import VerificationScore

    for criterion in VerificationCriterion.objects.filter(is_active=True):
        VerificationScore.objects.update_or_create(
            application=application,
            criterion=criterion,
            verifier=verifier,
            defaults={"score": Decimal(value)},
        )
