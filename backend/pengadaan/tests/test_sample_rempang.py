import pytest
from django.core.management import call_command

from leasing.models import District, Municipality
from pengadaan.management.commands.pengadaan_contoh_rempang import (
    PARCELS,
    SAMPLE_PROJECT_NAME,
)
from pengadaan.models import (
    AcquisitionMilestone,
    AcquisitionParcel,
    AcquisitionProject,
    EntitledParty,
)


@pytest.mark.django_db
def test_sample_rempang_create_is_idempotent_and_delete_removes_everything(
    seeded_rules,
):
    # Fixture leasing (dimuat sekali per sesi oleh modul lain) sudah berisi
    # Kota Batam dan Galang; jangan membuat duplikatnya.
    batam, _created = Municipality.objects.get_or_create(
        identifier="2171", defaults={"name": "Kota Batam"}
    )
    galang, _created = District.objects.get_or_create(
        municipality=batam, identifier="8", defaults={"name": "Galang"}
    )

    call_command("pengadaan_contoh_rempang")
    call_command("pengadaan_contoh_rempang")

    project = AcquisitionProject.objects.get(name=SAMPLE_PROJECT_NAME)
    assert project.municipality == batam
    assert "DATA CONTOH" in project.description
    assert project.geometry.valid
    parcels = AcquisitionParcel.objects.filter(project=project)
    assert parcels.count() == len(PARCELS)
    assert all(p.district == galang and p.geometry.valid for p in parcels)
    assert all(project.geometry.contains(p.geometry) for p in parcels)
    assert EntitledParty.objects.filter(parcel__project=project).count() == 5
    assert AcquisitionMilestone.objects.filter(project=project).exists()

    # Data lain tidak boleh ikut terhapus.
    other = AcquisitionProject.objects.create(
        name="Proyek Lain", requiring_agency="Dinas Uji"
    )

    call_command("pengadaan_contoh_rempang", "--hapus")

    assert not AcquisitionProject.all_objects.filter(name=SAMPLE_PROJECT_NAME).exists()
    assert not AcquisitionParcel.all_objects.filter(project_id=project.pk).exists()
    assert not EntitledParty.all_objects.filter(parcel__project_id=project.pk).exists()
    assert not AcquisitionMilestone.objects.filter(project_id=project.pk).exists()
    assert AcquisitionProject.objects.filter(pk=other.pk).exists()

    # Menghapus ketika tidak ada data contoh tidak galat.
    call_command("pengadaan_contoh_rempang", "--hapus")
