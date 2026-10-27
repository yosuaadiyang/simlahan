import datetime

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone

from dokumen import enums, services
from dokumen.models import LandUse, PermitType

from .conftest import pdf_upload, record_of

RS = enums.RecordStatus


def test_records_follow_scheme_and_sector(land_use):
    codes = set(land_use.records.values_list("permit_type__code", flat=True))
    # Perjanjian sewa/kerja sama hanya untuk skema sewa & kerja sama.
    assert {"nib", "pkkpr", "lingkungan", "pbg", "perjanjian"} <= codes
    other = LandUse.objects.create(
        title="Lain", scheme=enums.Scheme.OTHER, holder_name="CV Uji"
    )
    services.ensure_records(other)
    assert not other.records.filter(permit_type__code="perjanjian").exists()
    assert services.ensure_records(other) == 0


def test_new_permit_type_is_applied_to_active_land_uses(land_use):
    permit_type = PermitType.objects.create(
        code="baru", name="Izin baru", applies_lease=True
    )
    assert services.sync_permit_type(permit_type) == 1
    assert land_use.records.filter(permit_type=permit_type).exists()
    assert services.sync_permit_type(permit_type) == 0


def test_holder_upload_submits_and_officer_verifies(
    land_use, officer, django_capture_on_commit_callbacks, mailoutbox
):
    record = record_of(land_use, "nib")
    with django_capture_on_commit_callbacks(execute=True):
        services.holder_update(
            record,
            land_use.holder.user,
            upload=pdf_upload(),
            number="NIB-1",
            note="Mohon dicek",
        )
    record.refresh_from_db()
    assert record.status == RS.SUBMITTED
    assert record.versions.count() == 1
    assert record.latest_version.sha256 and record.latest_version.size > 0
    assert any(officer.email in m.to for m in mailoutbox)

    services.verify(record, officer, note="Sesuai OSS")
    record.refresh_from_db()
    assert record.status == RS.VERIFIED and record.verified_by == officer
    with pytest.raises(ValidationError):
        services.verify(record, officer)
    with pytest.raises(ValidationError, match="diatur petugas"):
        services.holder_update(record, land_use.holder.user, status=RS.IN_PROGRESS)
    progress = land_use.progress()
    assert progress["done"] == 1


def test_upload_rejects_fake_pdf(land_use):
    record = record_of(land_use, "nib")
    fake = SimpleUploadedFile(
        "izin.pdf", b"MZ\x90\x00 bukan pdf", content_type="application/pdf"
    )
    with pytest.raises(ValidationError):
        services.holder_update(record, land_use.holder.user, upload=fake)
    assert record.versions.count() == 0


def test_upload_rejects_unknown_extension(land_use):
    record = record_of(land_use, "nib")
    with pytest.raises(ValidationError):
        services.holder_update(
            record,
            land_use.holder.user,
            upload=SimpleUploadedFile(
                "x.exe", b"MZ", content_type="application/x-msdownload"
            ),
        )


def test_revision_waive_reopen(land_use, officer):
    record = record_of(land_use, "pbg")
    services.holder_update(record, land_use.holder.user, upload=pdf_upload())
    with pytest.raises(ValidationError):
        services.request_revision(record, officer, "  ")
    services.request_revision(record, officer, "Halaman 2 buram")
    record.refresh_from_db()
    assert record.status == RS.REVISION and record.review_note == "Halaman 2 buram"
    # Pemegang hak boleh mengunggah perbaikan.
    services.holder_update(record, land_use.holder.user, upload=pdf_upload())
    record.refresh_from_db()
    assert record.status == RS.SUBMITTED and record.versions.count() == 2

    services.waive(record, officer, "Tidak membangun gedung")
    record.refresh_from_db()
    assert record.status == RS.WAIVED
    services.reopen(record, officer, "Ternyata membangun")
    record.refresh_from_db()
    assert record.status == RS.SUBMITTED and record.verified_by is None


def test_verify_without_file_needs_note(land_use, officer):
    record = record_of(land_use, "nib")
    with pytest.raises(ValidationError, match="Belum ada berkas"):
        services.verify(record, officer)
    services.verify(record, officer, note="Dicek di OSS")
    record.refresh_from_db()
    assert record.status == RS.VERIFIED


def test_default_expiry_and_daily_job(
    land_use, officer, django_capture_on_commit_callbacks, mailoutbox
):
    record = record_of(land_use, "pkkpr")  # masa berlaku bawaan 36 bulan
    issued = timezone.localdate() - datetime.timedelta(days=30)
    services.officer_upload(
        record, officer, pdf_upload(), issued_date=issued, verify_now=True
    )
    record.refresh_from_db()
    assert record.expiry_date is not None and record.expiry_date > issued

    soon = record_of(land_use, "nib")
    services.officer_upload(
        soon,
        officer,
        pdf_upload(),
        expiry_date=timezone.localdate() + datetime.timedelta(days=10),
        verify_now=True,
    )
    late = record_of(land_use, "lingkungan")
    services.officer_upload(late, officer, pdf_upload(), verify_now=True)
    type(late).objects.filter(pk=late.pk).update(
        expiry_date=timezone.localdate() - datetime.timedelta(days=1)
    )

    with django_capture_on_commit_callbacks(execute=True):
        call_command("dokumen_pengingat", "--email", stdout=open("/dev/null", "w"))
    late.refresh_from_db()
    soon.refresh_from_db()
    assert late.status == RS.EXPIRED
    assert soon.expiry_warned_for == soon.expiry_date
    subjects = [m.subject for m in mailoutbox]
    assert any("kedaluwarsa" in s for s in subjects)
    assert any("akan kedaluwarsa" in s for s in subjects)
    # Peringatan hanya sekali per tanggal kedaluwarsa.
    count = len(mailoutbox)
    with django_capture_on_commit_callbacks(execute=True):
        call_command("dokumen_pengingat", stdout=open("/dev/null", "w"))
    assert not any("akan kedaluwarsa" in m.subject for m in mailoutbox[count:])


def test_expired_verified_on_upload_with_past_date(land_use, officer):
    record = record_of(land_use, "nib")
    services.officer_upload(
        record,
        officer,
        pdf_upload(),
        expiry_date=timezone.localdate() - datetime.timedelta(days=2),
        verify_now=True,
    )
    record.refresh_from_db()
    assert record.status == RS.EXPIRED


def test_inactive_land_use_is_read_only_for_holder(land_use):
    land_use.status = enums.LandUseStatus.ENDED
    land_use.save()
    record = record_of(land_use, "nib")
    with pytest.raises(ValidationError, match="tidak aktif"):
        services.holder_update(record, land_use.holder.user, upload=pdf_upload())


def test_allocation_creates_and_syncs_land_use(
    dokumen_seeded, filled_application, officer, verifier
):
    from alokasi import services as alokasi_services
    from alokasi.tests.test_workflow import approve_and_pay

    alokasi_services.submit(filled_application, filled_application.applicant.user)
    approve_and_pay(filled_application, officer, verifier)
    allocation = filled_application.allocation
    land_use = allocation.land_use
    assert land_use.scheme == enums.Scheme.ALLOCATION
    assert land_use.holder == allocation.holder
    assert land_use.reference == allocation.kpt_number
    assert land_use.records.filter(permit_type__code="nib").exists()
    assert not land_use.records.filter(permit_type__code="perjanjian").exists()


def test_end_land_uses_for_plots(land_use, officer):
    assert services.end_land_uses_for_plots([land_use.plot_id], actor=officer) == 1
    land_use.refresh_from_db()
    assert land_use.status == enums.LandUseStatus.ENDED
