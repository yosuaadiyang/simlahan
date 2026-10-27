import importlib
import io

import pytest
from django.apps import apps as django_apps
from django.core.management import call_command

from dokumen.models import DownloadRequest, LandUse, SigningDocument

backfill = importlib.import_module("dokumen.migrations.0003_backfill_land_uses")


def test_backfill_allocations_is_idempotent(
    dokumen_seeded, filled_application, officer, verifier
):
    from alokasi import services as alokasi_services
    from alokasi.tests.test_workflow import approve_and_pay

    alokasi_services.submit(filled_application, filled_application.applicant.user)
    approve_and_pay(filled_application, officer, verifier)
    allocation = filled_application.allocation
    LandUse.objects.all().delete()  # tirukan data sebelum modul ada
    backfill.backfill_allocations(django_apps)
    backfill.backfill_allocations(django_apps)
    land_use = LandUse.objects.get(allocation=allocation)
    assert land_use.number.startswith("PML-") and land_use.records.exists()
    # Nomor berikutnya dari model tidak bentrok dengan nomor migrasi.
    other = LandUse.objects.create(title="Lain", holder_name="CV", scheme="lainnya")
    assert other.number != land_use.number


def test_seed_is_idempotent_and_keeps_edits(dokumen_seeded):
    from dokumen.models import PermitType

    PermitType.objects.filter(code="nib").update(name="NIB (diubah)")
    importlib.import_module("dokumen.migrations.0002_seed_defaults").seed(
        django_apps, None
    )
    assert PermitType.objects.get(code="nib").name == "NIB (diubah)"
    assert PermitType.objects.filter(code="nib").count() == 1


def test_sample_command_create_twice_and_delete(
    dokumen_seeded, make_officer, make_plot
):
    from utils.group_permissions import UserGroup

    make_officer("contoh.alokasi", UserGroup.PETUGAS_ALOKASI)
    out = io.StringIO()
    call_command("dokumen_contoh_rempang", stdout=out)
    call_command("dokumen_contoh_rempang", stdout=out)
    assert LandUse.objects.filter(reference__startswith="CONTOH-DOK-").count() == 3
    call_command("dokumen_contoh_rempang", "--hapus", stdout=out)
    assert not LandUse.objects.filter(reference__startswith="CONTOH-DOK-").exists()
    assert not SigningDocument.objects.exists() and not DownloadRequest.objects.exists()


@pytest.mark.django_db
def test_reminder_command_runs_on_empty_db(dokumen_seeded):
    out = io.StringIO()
    call_command("dokumen_pengingat", stdout=out)
    assert "Izin kedaluwarsa hari ini: 0" in out.getvalue()
