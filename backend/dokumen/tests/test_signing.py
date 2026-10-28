import base64
import io
import re

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from PIL import Image

from dokumen import enums, signing
from dokumen.models import (
    DocumentRecipient,
    DocumentTemplate,
    DownloadLog,
    SigningDocument,
)

from .conftest import pdf_upload, record_of

S = enums.SigningStatus


def signature_png():
    image = Image.new("RGBA", (300, 100), (0, 0, 0, 0))
    for x in range(20, 280):
        image.putpixel((x, 50), (0, 0, 80, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


@pytest.fixture
def statement(dokumen_seeded):
    return DocumentTemplate.objects.get(name__istartswith="Surat pernyataan")


@pytest.fixture
def draft(land_use, officer, statement):
    return signing.create(
        user=officer,
        title="Pernyataan",
        template=statement,
        land_use=land_use,
        extra={"batas_waktu": "6 bulan"},
    )


def add_external(
    document, order=2, action=enums.RecipientAction.SIGN, email="notaris@contoh.id"
):
    return document.recipients.create(
        order=order, role="Notaris", action=action, name="Notaris Uji", email=email
    )


def test_create_fills_fields_and_adds_holder(draft, land_use):
    assert draft.status == S.DRAFT
    assert land_use.holder.name in draft.body
    assert "6 bulan" in draft.body
    holder = draft.recipients.get()
    assert holder.user == land_use.holder.user and holder.order == 1
    assert signing.problems(draft) == []


def test_problems_block_sending(land_use, officer, statement):
    document = signing.create(
        user=officer, title="X", template=statement, land_use=land_use
    )
    issues = signing.problems(document)
    assert any("isian.batas_waktu" in i for i in issues)
    with pytest.raises(ValidationError):
        signing.send(document, officer)
    signing.fill_fields(document, {"batas_waktu": "3 bulan"}, officer)
    document.refresh_from_db()
    assert signing.problems(document) == []


def test_sequential_signing_completes_and_attaches_to_record(
    land_use, officer, statement, django_capture_on_commit_callbacks
):
    record = (
        record_of(land_use, "lainnya")
        if land_use.records.filter(permit_type__code="lainnya").exists()
        else record_of(land_use, "nib")
    )
    document = signing.create(
        user=officer,
        title="Pernyataan",
        template=statement,
        land_use=land_use,
        record=record,
        extra={"batas_waktu": "6 bulan"},
    )
    external = add_external(document)
    copy = add_external(
        document, order=3, action=enums.RecipientAction.COPY, email="arsip@contoh.id"
    )
    with django_capture_on_commit_callbacks(execute=True):
        signing.send(document, officer)
    document.refresh_from_db()
    assert document.status == S.SENT and document.content_sha256
    holder = document.recipients.get(order=1)
    # Hanya giliran pertama yang diberi surel.
    assert [m.to for m in mail.outbox] == [[holder.email]]
    assert (
        signing.is_turn(holder)
        and not signing.is_turn(external)
        and not signing.is_turn(copy)
    )
    with pytest.raises(ValidationError):
        signing.act(external, name="Notaris Uji", signature=signature_png())

    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        signing.act(holder, name="Direktur Uji", signature=signature_png())
    assert [m.to for m in mail.outbox] == [[external.email]]
    external.refresh_from_db()
    # Penerima tanpa akun wajib kode surel.
    with pytest.raises(ValidationError, match="kode verifikasi"):
        signing.act(external, name="Notaris Uji", signature=signature_png())
    signing.send_otp(external)
    code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
    assert not signing.check_otp(external, "000000" if code != "000000" else "111111")
    assert signing.check_otp(external, code)
    external.refresh_from_db()
    with pytest.raises(ValidationError, match="tanda tangan"):
        signing.act(external, name="Notaris Uji", signature="")
    with django_capture_on_commit_callbacks(execute=True):
        signing.act(external, name="Notaris Uji", signature=signature_png())
    document.refresh_from_db()
    assert document.status == S.COMPLETED
    assert document.final_file and len(document.final_sha256) == 64
    record.refresh_from_db()
    assert record.status == enums.RecordStatus.VERIFIED
    assert record.latest_version.source == enums.VersionSource.SIGNED
    assert any(copy.email in m.to for m in mail.outbox)


def test_otp_attempts_are_limited(draft, officer):
    external = add_external(draft, order=1, email="luar@contoh.id")
    draft.recipients.filter(user__isnull=False).delete()
    signing.send(draft, officer)
    signing.send_otp(external)
    for _i in range(5):
        signing.check_otp(external, "999999")
    code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
    assert not signing.check_otp(external, code)


def test_decline_closes_document(draft, officer):
    signing.send(draft, officer)
    holder = draft.recipients.get()
    with pytest.raises(ValidationError):
        signing.decline(holder, " ")
    signing.decline(holder, "Nama perusahaan salah")
    draft.refresh_from_db()
    assert draft.status == S.DECLINED and "Nama perusahaan salah" in draft.closed_reason
    with pytest.raises(ValidationError):
        signing.act(holder, name="Direktur", signature=signature_png())


def test_internal_approval_cannot_be_self_approved(
    land_use, officer, administrator, dokumen_seeded
):
    template = DocumentTemplate.objects.get(name__istartswith="Perjanjian sewa")
    assert template.needs_approval
    document = signing.create(
        user=officer, title="Perjanjian", template=template, land_use=land_use
    )
    leftovers = signing.problems(document)
    if any("isian" in p for p in leftovers):
        from dokumen import merge

        signing.fill_fields(
            document, {k: "x" for k in merge.custom_fields(document.body)}, officer
        )
    with pytest.raises(ValidationError, match="disetujui internal"):
        signing.send(document, officer)
    signing.submit_for_approval(document, officer)
    document.refresh_from_db()
    assert not signing.can_approve(
        officer, document
    )  # Petugas alokasi tidak punya izin setujui.
    administrator.user_permissions.clear()
    assert signing.can_approve(administrator, document)
    signing.approve(document, administrator)
    signing.send(document, officer)
    document.refresh_from_db()
    assert document.status == S.SENT
    assert document.confidentiality == enums.Confidentiality.SECRET


def test_admin_creator_cannot_approve_own_document(land_use, administrator, statement):
    document = signing.create(
        user=administrator,
        title="X",
        template=statement,
        land_use=land_use,
        extra={"batas_waktu": "1"},
    )
    signing.submit_for_approval(document, administrator)
    with pytest.raises(ValidationError):
        signing.approve(document, administrator)


def test_expire_and_reminders(draft, officer, django_capture_on_commit_callbacks):
    import datetime

    from django.utils import timezone

    signing.send(draft, officer)
    SigningDocument.objects.filter(pk=draft.pk).update(
        sent_at=timezone.now() - datetime.timedelta(days=5)
    )
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        assert signing.send_due_reminders() == 1
    assert (
        signing.send_due_reminders() == 0
    )  # tidak dikirim ulang sebelum jeda berikutnya
    assert mail.outbox and "Pengingat:" in mail.outbox[0].subject
    SigningDocument.objects.filter(pk=draft.pk).update(
        expires_on=timezone.localdate() - datetime.timedelta(days=1)
    )
    assert [d.pk for d in signing.expire_documents()] == [draft.pk]
    draft.refresh_from_db()
    assert draft.status == S.EXPIRED


def test_duplicate_and_cancel(draft, officer):
    signing.send(draft, officer)
    copy = signing.duplicate(draft, officer)
    assert (
        copy.status == S.DRAFT and copy.recipients.count() == draft.recipients.count()
    )
    signing.cancel(draft, officer, "Salah kirim")
    draft.refresh_from_db()
    assert draft.status == S.CANCELLED


def test_pdf_signing_flow(land_use, officer):
    document = signing.create(
        user=officer,
        title="Kontrak PDF",
        land_use=land_use,
        upload=pdf_upload("kontrak.pdf"),
    )
    assert document.source == enums.SigningSource.PDF
    signing.send(document, officer)
    holder = document.recipients.get()
    signing.act(holder, name="Direktur Uji", signature=signature_png())
    document.refresh_from_db()
    assert document.status == S.COMPLETED
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(document.final_file.read()))
    assert len(reader.pages) >= 2  # dokumen asli + lembar pengesahan


def test_signature_must_be_real_png(draft, officer):
    signing.send(draft, officer)
    holder = draft.recipients.get()
    for bad in (
        "data:image/png;base64,bm90cG5n",
        "data:image/svg+xml;base64,PHN2Zz4=",
        "data:image/png;base64,***",
    ):
        with pytest.raises(ValidationError):
            signing.act(holder, name="Direktur", signature=bad)
    blank = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    buffer = io.BytesIO()
    blank.save(buffer, format="PNG")
    with pytest.raises(ValidationError, match="kosong"):
        signing.act(
            holder,
            name="Direktur",
            signature="data:image/png;base64,"
            + base64.b64encode(buffer.getvalue()).decode(),
        )


# --- Halaman portal -------------------------------------------------------


def test_sign_page_requires_recipient_account(client, draft, officer, make_applicant):
    signing.send(draft, officer)
    holder = draft.recipients.get()
    url = reverse("dokumen_portal:sign", args=[holder.token])
    response = client.get(url)
    assert response.status_code == 302 and "/portal/masuk/" in response["Location"]
    other = make_applicant()
    client.force_login(other.user)
    response = client.get(url)
    assert response.status_code == 403
    client.force_login(holder.user)
    response = client.get(url)
    assert response.status_code == 200 and b"dk-sign-form" in response.content
    holder.refresh_from_db()
    assert holder.status == enums.RecipientStatus.VIEWED


def test_sign_page_external_otp_flow(client, draft, officer):
    draft.recipients.all().delete()
    external = add_external(draft, order=1, email="luar@contoh.id")
    signing.send(draft, officer)
    url = reverse("dokumen_portal:sign", args=[external.token])
    response = client.get(url)
    assert response.status_code == 200
    assert (
        b"kirim_kode" in response.content
        and draft.body.encode()[:40] not in response.content
    )
    client.post(url, {"aksi": "kirim_kode"})
    code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
    response = client.post(url, {"aksi": "cek_kode", "code": code})
    assert response.status_code == 302
    # Kode yang sudah dimasukkan hanya berlaku di peramban itu: pemegang
    # tautan lain (mis. surel yang diteruskan) tetap harus memasukkan kode.
    other = Client()
    response = other.get(url)
    assert b"kirim_kode" in response.content
    assert draft.body.encode()[:40] not in response.content
    other.post(
        url,
        {
            "aksi": "tanda_tangan",
            "name": "Penyusup",
            "signature": signature_png(),
            "agree": "on",
        },
    )
    external.refresh_from_db()
    assert external.status != enums.RecipientStatus.DONE
    response = client.post(
        url,
        {
            "aksi": "tanda_tangan",
            "name": "Notaris Uji",
            "signature": signature_png(),
            "agree": "on",
        },
    )
    assert response.status_code == 302
    draft.refresh_from_db()
    assert draft.status == S.COMPLETED
    # Penandatangan tanpa akun tidak bisa mengunduh PDF lewat tautan tanda tangan setelah selesai.
    assert (
        client.get(
            reverse("dokumen_portal:sign_pdf", args=[external.token])
        ).status_code
        == 404
    )


def test_unknown_token_and_draft_are_404(client, draft):
    holder = draft.recipients.get()
    client.force_login(holder.user)
    assert (
        client.get(reverse("dokumen_portal:sign", args=[holder.token])).status_code
        == 404
    )
    assert (
        client.get(
            reverse(
                "dokumen_portal:sign", args=["6f1c0d64-5d43-4bd1-9a33-0d4b2f9f0c11"]
            )
        ).status_code
        == 404
    )


def test_verify_page_and_hash_match(client, draft, officer):
    signing.send(draft, officer)
    holder = draft.recipients.get()
    signing.act(holder, name="Direktur Uji", signature=signature_png())
    draft.refresh_from_db()
    url = reverse("dokumen_portal:verify_token", args=[draft.verify_token])
    response = client.get(url)
    assert response.status_code == 200 and draft.number.encode() in response.content
    assert (
        holder.email.encode() not in response.content
    )  # surel penanda tangan tidak dibuka ke publik
    from django.core.files.uploadedfile import SimpleUploadedFile

    data = draft.final_file.read()
    response = client.post(
        url, {"file": SimpleUploadedFile("a.pdf", data, content_type="application/pdf")}
    )
    assert "identik" in response.content.decode()
    response = client.post(
        url,
        {
            "file": SimpleUploadedFile(
                "b.pdf", data + b"x", content_type="application/pdf"
            )
        },
    )
    assert "Tidak cocok" in response.content.decode()
    # Salinan resmi bertanda air dikenali dari catatan unduhan.
    DownloadLog.objects.create(
        user=holder.user,
        user_name="Direktur Uji",
        signing=draft,
        filename="x.pdf",
        sha256=__import__("hashlib").sha256(b"salinan").hexdigest(),
    )
    response = client.post(
        url,
        {
            "file": SimpleUploadedFile(
                "c.pdf", b"salinan", content_type="application/pdf"
            )
        },
    )
    assert "salinan resmi" in response.content.decode()
    response = client.get(reverse("dokumen_portal:verify") + "?kode=bukan-uuid")
    assert response.status_code == 200


def test_recipient_tokens_are_unique(draft):
    other = add_external(draft)
    assert DocumentRecipient.objects.filter(token=other.token).count() == 1
