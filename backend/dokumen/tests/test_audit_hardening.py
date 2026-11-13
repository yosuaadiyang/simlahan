"""Pengerasan modul dokumen: persetujuan unduh mengikuti sifat dokumen terkini,
data permintaan rahasia hanya untuk penyetuju rahasia, format rahasia tidak
diunduh bebas, komentar hanya pada dokumen terbuka, dan isian DOCX di-escape."""

import io

import pytest
from django.contrib.admin.sites import site as admin_site
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.urls import reverse

from dokumen import downloads, enums, merge, services, views
from dokumen.models import DownloadRequest

from .conftest import pdf_upload, record_of

pytestmark = pytest.mark.django_db


@pytest.fixture
def version(land_use, officer):
    record = record_of(land_use, "nib")
    return services.officer_upload(
        record, officer, pdf_upload(title="NIB asli"), verify_now=True
    )


def _ask(user, version):
    return downloads.request_download(
        user,
        version=version,
        purpose=enums.DownloadPurpose.FINANCING,
        reason="Untuk pengajuan bank",
    )


def test_approval_lapses_when_document_becomes_secret(land_use, version, officer):
    holder = land_use.holder.user
    dl = _ask(holder, version)
    downloads.approve(dl, officer)
    permit_type = version.record.permit_type
    permit_type.confidentiality = enums.Confidentiality.SECRET
    permit_type.save(update_fields=["confidentiality"])
    with pytest.raises(ValidationError, match="rahasia"):
        downloads.consume(dl, holder)


def test_normal_approver_does_not_list_others_secret_requests(
    rf, land_use, officer, administrator
):
    secret_record = record_of(land_use, "perjanjian")
    secret = services.officer_upload(
        secret_record, officer, pdf_upload(title="Perjanjian"), verify_now=True
    )
    dl = _ask(land_use.holder.user, secret)
    assert dl.confidentiality == enums.Confidentiality.SECRET
    model_admin = admin_site._registry[DownloadRequest]
    request = rf.get("/")
    request.user = officer
    assert officer.has_perm("dokumen.approve_downloadrequest")
    assert dl not in model_admin.get_queryset(request)
    request.user = administrator
    assert dl in model_admin.get_queryset(request)


def test_secret_template_is_not_freely_downloadable(client, land_use):
    record = record_of(land_use, "bast")
    template = record.permit_type.template
    template.confidentiality = enums.Confidentiality.SECRET
    template.save(update_fields=["confidentiality"])
    client.force_login(land_use.holder.user)
    response = client.get(reverse("dokumen_portal:template_download", args=[record.pk]))
    assert response.status_code == 302
    assert not response.get("Content-Disposition")


def test_comment_rejected_on_closed_document():
    recipient = type(
        "R",
        (),
        {"document": type("D", (), {"status": enums.SigningStatus.COMPLETED})()},
    )()
    request = RequestFactory().post("/", {"body": "Komentar"})
    with pytest.raises(ValidationError):
        views._sign_comment(request, recipient)


def test_docx_merge_escapes_markup_in_values(land_use):
    import docx

    document = docx.Document()
    document.add_paragraph("Nama: {{ pemohon.nama }}")
    buffer = io.BytesIO()
    document.save(buffer)
    holder = land_use.holder
    holder.name = 'PT <w:p/> & "Rekan"'
    holder.save(update_fields=["name"])
    context = merge.build_context(land_use=land_use)
    data = merge.render_docx(buffer.getvalue(), context)
    rendered = docx.Document(io.BytesIO(data))
    text = "\n".join(p.text for p in rendered.paragraphs)
    assert 'PT <w:p/> & "Rekan"' in text
    assert len(rendered.paragraphs) == 1


def test_normal_approver_cannot_approve_after_document_becomes_secret(
    land_use, version, officer, administrator
):
    dl = _ask(land_use.holder.user, version)
    permit_type = version.record.permit_type
    permit_type.confidentiality = enums.Confidentiality.SECRET
    permit_type.save(update_fields=["confidentiality"])
    with pytest.raises(ValidationError, match="tidak berwenang"):
        downloads.approve(dl, officer)
    downloads.approve(dl, administrator)
