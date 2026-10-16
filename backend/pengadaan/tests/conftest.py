import datetime
import importlib
from decimal import Decimal

import pytest
from django.apps import apps as django_apps
from django.contrib.auth.models import Permission

from pengadaan import enums
from pengadaan.models import AcquisitionParcel, AcquisitionProject, EntitledParty


@pytest.fixture
def seeded_rules(db):
    """Muat aturan tenggat & libur dari migrasi data (tes berjalan --nomigrations)."""
    module = importlib.import_module(
        "pengadaan.migrations.0003_seed_deadline_rules_and_holidays"
    )
    module.seed(django_apps, None)


@pytest.fixture
def project(db, seeded_rules, municipality_factory):
    municipality = municipality_factory(name="Kota Uji", identifier="9971")
    return AcquisitionProject.objects.create(
        name="Pelebaran Jalan Uji",
        requiring_agency="Dinas PUPR",
        municipality=municipality,
        acquisition_type=enums.AcquisitionType.PUBLIC_INTEREST,
        purpose_category=enums.PublicInterestCategory.ROADS,
    )


@pytest.fixture
def parcel(project):
    return AcquisitionParcel.objects.create(
        project=project,
        parcel_number="001",
        right_type=enums.LandRightType.SHM,
        measured_area_m2=Decimal("500"),
        affected_area_m2=Decimal("200"),
    )


@pytest.fixture
def party(parcel):
    return EntitledParty.objects.create(
        parcel=parcel,
        name="Budi Santoso",
        nik="2171010101900001",
        bank_name="Bank Uji",
        bank_account_number="1234567890",
        share_percentage=Decimal("100"),
    )


@pytest.fixture
def make_user(django_user_model):
    def _make(username, perms=(), superuser=False):
        user = django_user_model.objects.create_user(
            username=username, password="RahasiaKuat123!", is_superuser=superuser
        )
        for codename in perms:
            app_label, code = codename.split(".")
            user.user_permissions.add(
                Permission.objects.get(content_type__app_label=app_label, codename=code)
            )
        return user

    return _make


@pytest.fixture
def today():
    return datetime.date.today()
