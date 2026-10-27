import io

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command

from leasing.models import ServiceUnit
from operasi.management.commands.operasi_contoh_rempang import MARK
from operasi.models import Korwil
from pengadaan.management.commands.pengadaan_contoh_rempang import (
    SAMPLE_PROJECT_NAME,
)
from pengadaan.models import AcquisitionProject
from utils.group_permissions import UserGroup


@pytest.fixture
def groups(db):
    for group in UserGroup:
        Group.objects.get_or_create(pk=group.value, defaults={"name": group.name})
    call_command("set_group_model_permissions", verbosity=0, stdout=io.StringIO())


@pytest.fixture
def unit(db):
    return ServiceUnit.objects.create(name="Unit Contoh")


@pytest.fixture
def samples(groups, unit, municipality_factory):
    project = AcquisitionProject.objects.create(
        name=SAMPLE_PROJECT_NAME,
        requiring_agency="Instansi Contoh",
        municipality=municipality_factory(name="Kota Contoh", identifier="9981"),
    )
    korwil = Korwil.objects.create(code="A", name="Contoh", note=f"{MARK} Contoh.")
    return project, korwil
