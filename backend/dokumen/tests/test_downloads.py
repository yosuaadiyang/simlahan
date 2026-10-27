import datetime

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from dokumen import downloads, enums, services
from dokumen.models import DocumentSettings, DownloadLog, DownloadRequest
from utils.group_permissions import UserGroup

from .conftest import pdf_upload, record_of

D = enums.DownloadStatus


@pytest.fixture
def version(land_use, officer):
    record = record_of(land_use, "nib")
    return services.officer_upload(
        record, officer, pdf_upload(title="NIB asli"), verify_now=True
    )


@pytest.fixture
def secret_version(land_use, officer):
    record = record_of(land_use, "perjanjian")
    assert record.permit_type.confidentiality == enums.Confidentiality.SECRET
    return services.officer_upload(
        record, officer, pdf_upload(title="Perjanjian"), verify_now=True
    )


def ask(user, version, reason="Untuk pengajuan bank"):
    return downloads.request_download(
        user, version=version, purpose=enums.DownloadPurpose.FINANCING, reason=reason
    )


def test_holder_download_needs_approval_and_is_watermarked(
    land_use, version, officer, django_capture_on_commit_callbacks, mailoutbox
):
    holder = land_use.holder.user
    with django_capture_on_commit_callbacks(execute=True):
        dl = ask(holder, version)
    assert dl.status == D.PENDING and not dl.is_usable
    assert any(
        officer.email in m.to for m in mailoutbox
    )  # pemberi persetujuan diberi tahu
    with pytest.raises(ValidationError, match="belum disetujui"):
        downloads.consume(dl, holder)
    # Permintaan ganda tidak membuat baris baru.
    assert ask(holder, version).pk == dl.pk

    downloads.approve(dl, officer, max_count=2)
    data, filename, content_type, marked = downloads.consume(dl, holder)
    original = version.file.open("rb").read()
    assert marked and data != original and data.startswith(b"%PDF")
    assert content_type == "application/pdf"
    downloads.consume(dl, holder)
    with pytest.raises(ValidationError, match="Kuota"):
        downloads.consume(dl, holder)
    logs = DownloadLog.objects.filter(request=dl)
    assert logs.count() == 2 and all(log.watermarked and log.sha256 for log in logs)


def test_only_requester_can_use_approval(land_use, version, officer, make_applicant):
    dl = ask(land_use.holder.user, version)
    downloads.approve(dl, officer)
    with pytest.raises(PermissionDenied):
        downloads.consume(dl, make_applicant().user)


def test_expired_approval(land_use, version, officer):
    dl = ask(land_use.holder.user, version)
    downloads.approve(dl, officer, hours=1)
    DownloadRequest.objects.filter(pk=dl.pk).update(
        valid_until=timezone.now() - datetime.timedelta(minutes=1)
    )
    with pytest.raises(ValidationError, match="kedaluwarsa"):
        downloads.consume(DownloadRequest.objects.get(pk=dl.pk), land_use.holder.user)


def test_other_applicant_cannot_request(version, make_applicant):
    with pytest.raises(ValidationError, match="tidak berhak"):
        ask(make_applicant().user, version)


def test_officer_cannot_approve_own_request(version, officer, make_officer):
    dl = ask(officer, version)
    assert not downloads.can_decide(officer, dl)
    with pytest.raises(ValidationError):
        downloads.approve(dl, officer)
    assert dl not in downloads.pending_for(officer)
    colleague = make_officer("petugas2", UserGroup.PETUGAS_ALOKASI)
    assert dl in downloads.pending_for(colleague)
    downloads.approve(dl, colleague)
    assert DownloadRequest.objects.get(pk=dl.pk).is_usable


def test_self_approval_setting(version, officer):
    config = DocumentSettings.load()
    config.allow_self_approval = True
    config.save()
    dl = ask(officer, version)
    downloads.approve(dl, officer)
    assert DownloadRequest.objects.get(pk=dl.pk).is_usable


def test_verifier_and_legal_cannot_approve(version, verifier, legal, land_use):
    dl = ask(land_use.holder.user, version)
    for user in (verifier, legal):
        assert not downloads.can_decide(user, dl)
        with pytest.raises(ValidationError):
            downloads.approve(dl, user)


def test_secret_document_needs_administrator(
    land_use, secret_version, officer, administrator
):
    dl = ask(land_use.holder.user, secret_version)
    assert dl.confidentiality == enums.Confidentiality.SECRET
    assert not downloads.can_decide(officer, dl)
    assert dl not in downloads.pending_for(officer)
    assert downloads.can_decide(administrator, dl)
    downloads.approve(dl, administrator)


def test_reject_needs_reason(land_use, version, officer):
    dl = ask(land_use.holder.user, version)
    with pytest.raises(ValidationError):
        downloads.reject(dl, officer, "")
    downloads.reject(dl, officer, "Tidak relevan")
    assert DownloadRequest.objects.get(pk=dl.pk).status == D.REJECTED


def test_auto_approval_only_for_own_normal_documents(land_use, version, secret_version):
    config = DocumentSettings.load()
    config.applicant_needs_approval = False
    config.save()
    assert ask(land_use.holder.user, version).is_usable
    assert not ask(land_use.holder.user, secret_version).is_usable


def test_cancel(land_use, version, officer):
    dl = ask(land_use.holder.user, version)
    with pytest.raises(ValidationError):
        downloads.cancel(dl, officer)
    downloads.cancel(dl, land_use.holder.user)
    assert DownloadRequest.objects.get(pk=dl.pk).status == D.CANCELLED


# --- Portal ---------------------------------------------------------------


def test_portal_download_flow(client, land_use, version, officer):
    holder = land_use.holder.user
    client.force_login(holder)
    url = reverse("dokumen_portal:request_version_download", args=[version.pk])
    response = client.post(url, {"purpose": "arsip", "reason": "Arsip kantor"})
    assert response.status_code == 302
    dl = DownloadRequest.objects.get(requester=holder)
    response = client.get(reverse("dokumen_portal:download", args=[dl.number]))
    assert response.status_code == 302  # belum disetujui → kembali dengan pesan
    downloads.approve(dl, officer)
    response = client.get(reverse("dokumen_portal:download", args=[dl.number]))
    assert response.status_code == 200
    assert response["Content-Disposition"].startswith("attachment")
    assert response["Cache-Control"] == "private, no-store"
    page = client.get(reverse("dokumen_portal:downloads"))
    assert dl.number.encode() in page.content


def test_portal_isolation(client, land_use, version, make_applicant):
    dl = ask(land_use.holder.user, version)
    client.force_login(make_applicant().user)
    assert (
        client.get(
            reverse("dokumen_portal:land_use", args=[land_use.number])
        ).status_code
        == 404
    )
    assert (
        client.get(reverse("dokumen_portal:download", args=[dl.number])).status_code
        == 404
    )
    assert (
        client.post(
            reverse("dokumen_portal:request_version_download", args=[version.pk]),
            {"purpose": "arsip", "reason": "xxxxx"},
        ).status_code
        == 404
    )
    record = version.record
    assert (
        client.post(
            reverse("dokumen_portal:record_update", args=[record.pk]),
            {"r%d-status" % record.pk: "proses"},
        ).status_code
        == 404
    )
    assert (
        client.get(
            reverse("dokumen_portal:template_download", args=[record.pk])
        ).status_code
        == 404
    )


def test_portal_upload_and_template_download(client, land_use, officer):
    client.force_login(land_use.holder.user)
    record = record_of(land_use, "bast")
    page = client.get(reverse("dokumen_portal:land_use", args=[land_use.number]))
    assert page.status_code == 200 and record.permit_type.name.encode() in page.content
    prefix = f"r{record.pk}"
    response = client.post(
        reverse("dokumen_portal:record_update", args=[record.pk]),
        {
            f"{prefix}-file": pdf_upload(),
            f"{prefix}-number": "BAST-1",
            f"{prefix}-note": "Terlampir",
        },
    )
    assert response.status_code == 302
    record.refresh_from_db()
    assert record.status == enums.RecordStatus.SUBMITTED and record.number == "BAST-1"
    response = client.post(
        reverse("dokumen_portal:record_update", args=[record.pk]),
        {f"{prefix}-number": "x"},
    )
    assert response.status_code == 400  # unggah atau pilih status
    # Format BAST (templat isian) dapat diunduh tanpa persetujuan, berisi data sendiri.
    response = client.get(reverse("dokumen_portal:template_download", args=[record.pk]))
    assert response.status_code == 200 and response.content.startswith(b"%PDF")
    assert DownloadLog.objects.filter(
        template__isnull=False, user=land_use.holder.user
    ).exists()


def test_portal_requires_applicant(client, officer):
    response = client.get(reverse("dokumen_portal:index"))
    assert response.status_code == 302
    client.force_login(officer)
    response = client.get(reverse("dokumen_portal:index"))
    assert response.status_code in (302, 403)


def test_dashboard_card(client, land_use):
    client.force_login(land_use.holder.user)
    response = client.get(reverse("portal:dashboard"))
    assert response.status_code == 200
    assert reverse("dokumen_portal:index").encode() in response.content


# --- Panel petugas ---------------------------------------------------------


def test_staff_download_and_preview(
    client, land_use, version, officer, verifier, make_officer
):
    client.force_login(verifier)
    response = client.get(reverse("dokumen-version-preview", args=[version.pk]))
    assert response.status_code == 200 and response["Content-Disposition"].startswith(
        "inline"
    )
    assert DownloadLog.objects.filter(user=verifier, is_preview=True).exists()
    response = client.post(
        reverse("dokumen-staff-request", args=["versi", version.pk]),
        {"purpose": "audit", "reason": "Pemeriksaan rutin"},
    )
    assert response.status_code == 302
    dl = DownloadRequest.objects.get(requester=verifier)
    assert (
        client.get(reverse("dokumen-staff-download", args=[dl.number])).status_code
        == 302
    )
    downloads.approve(dl, officer)
    response = client.get(reverse("dokumen-staff-download", args=[dl.number]))
    assert response.status_code == 200
    # Permintaan orang lain tidak bisa dipakai.
    client.force_login(officer)
    assert (
        client.get(reverse("dokumen-staff-download", args=[dl.number])).status_code
        == 404
    )
    legal = make_officer("hukum2", UserGroup.PETUGAS_HUKUM)
    client.force_login(legal)
    assert (
        client.get(reverse("dokumen-version-preview", args=[version.pk])).status_code
        == 403
    )


def test_admin_decide_view(client, land_use, version, officer):
    dl = ask(land_use.holder.user, version)
    client.force_login(officer)
    page = client.get(reverse("admin:dokumen_downloadrequest_change", args=[dl.pk]))
    assert page.status_code == 200 and b"dk-decide" in page.content
    response = client.post(
        reverse("admin:dokumen_downloadrequest_decide", args=[dl.pk]),
        {"decision": "tolak", "note": ""},
    )
    assert DownloadRequest.objects.get(pk=dl.pk).status == D.PENDING
    response = client.post(
        reverse("admin:dokumen_downloadrequest_decide", args=[dl.pk]),
        {"decision": "setuju", "hours": "2", "max_count": "1"},
    )
    assert response.status_code == 302
    dl.refresh_from_db()
    assert dl.status == D.APPROVED and dl.max_downloads == 1


def test_download_request_list_scoped(client, land_use, version, verifier, officer):
    mine = ask(verifier, version)
    other = ask(land_use.holder.user, version)
    client.force_login(verifier)
    page = client.get(reverse("admin:dokumen_downloadrequest_changelist"))
    assert (
        mine.number.encode() in page.content
        and other.number.encode() not in page.content
    )
    assert (
        client.get(
            reverse("admin:dokumen_downloadrequest_change", args=[other.pk])
        ).status_code
        == 302
    )
