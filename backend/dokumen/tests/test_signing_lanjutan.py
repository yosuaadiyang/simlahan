"""Tes fitur tanda tangan lanjutan (setara PandaDoc): kolom isian penerima,
kode akses, tanda tangan langsung, ganti penerima, kirim massal, tanda tangan
tersimpan, cap tanda tangan pada PDF, dan penghitung dibuka."""

import io
import re

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from dokumen import enums, signing
from dokumen.models import (
    Activity,
    DocumentTemplate,
    LandUse,
    SavedSignature,
    SigningField,
)

from . import test_signing as _base
from .conftest import PASSWORD, pdf_upload

# Fixture dan pembantu tes dasar dipakai ulang.
add_external = _base.add_external
signature_png = _base.signature_png
draft = _base.draft
statement = _base.statement

S = enums.SigningStatus
K = SigningField.Kind
BODY = (
    "<p>Saya {{ pemohon.nama }} menyatakan alamat surat: {{ kolom.alamat_surat }}.</p>"
    "<p>Tanggal mulai: {{ kolom.mulai }}. Setuju: {{ kolom.setuju }}.</p>"
    "<p>Lampiran KTP: {{ kolom.ktp }}</p>"
)


@pytest.fixture
def form_template(dokumen_seeded):
    return DocumentTemplate.objects.create(
        name="Formulir isian penerima",
        kind=enums.TemplateKind.HTML,
        body=BODY,
    )


@pytest.fixture
def form_doc(land_use, officer, form_template):
    document = signing.create(
        user=officer, title="Formulir", template=form_template, land_use=land_use
    )
    document.fields.filter(key="mulai").update(kind=K.DATE)
    document.fields.filter(key="setuju").update(kind=K.CHECKBOX)
    document.fields.filter(key="ktp").update(kind=K.FILE)
    return document


def jpg_upload(name="ktp.jpg"):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


# --------------------------------------------------------------------------
# Kolom isian penerima
# --------------------------------------------------------------------------


def test_fields_created_from_template_and_filled_on_sign(form_doc, officer):
    holder = form_doc.recipients.get()
    keys = list(form_doc.fields.values_list("key", flat=True))
    assert keys == ["alamat_surat", "mulai", "setuju", "ktp"]
    assert set(form_doc.fields.values_list("recipient", flat=True)) == {holder.pk}
    assert signing.problems(form_doc) == []
    assert "{{ kolom.alamat_surat }}" in form_doc.body
    signing.send(form_doc, officer)

    with pytest.raises(ValidationError) as error:
        signing.act(
            holder,
            name="Direktur Uji",
            signature=signature_png(),
            field_values={"alamat_surat": "", "mulai": "31-12-2026"},
        )
    messages = " ".join(error.value.messages)
    assert "alamat_surat".replace("_", " ").capitalize() in messages
    assert "Tanggal tidak valid" in messages and "KTP" in messages.upper()
    holder.refresh_from_db()
    assert holder.status != enums.RecipientStatus.DONE
    assert not form_doc.fields.filter(filled_at__isnull=False).exists()

    signing.act(
        holder,
        name="Direktur Uji",
        signature=signature_png(),
        field_values={
            "alamat_surat": "Jl. Uji  No. 1",
            "mulai": "2026-12-31",
            "setuju": "on",
        },
        field_files={"ktp": jpg_upload()},
    )
    form_doc.refresh_from_db()
    assert form_doc.status == S.COMPLETED and form_doc.final_file
    values = {f.key: f for f in form_doc.fields.all()}
    assert values["alamat_surat"].value == "Jl. Uji No. 1"
    assert values["mulai"].display_value == "31-12-2026"
    assert values["setuju"].value == "1"
    assert values["ktp"].file and len(values["ktp"].file_sha256) == 64
    rendered = signing.render_body(form_doc)
    assert "Jl. Uji No. 1" in rendered and "{{" not in rendered
    holder.refresh_from_db()
    assert "akun SimLahan" in holder.verification_note


def test_problems_flag_undefined_and_unassigned_fields(form_doc):
    form_doc.fields.filter(key="ktp").delete()
    form_doc.fields.filter(key="mulai").update(recipient=None)
    SigningField.objects.create(
        document=form_doc,
        recipient=form_doc.recipients.get(),
        key="pilih",
        label="Pilih skema",
        kind=K.CHOICE,
    )
    issues = " ".join(str(i) for i in signing.problems(form_doc))
    assert "kolom.ktp" in issues
    assert "Mulai belum ditetapkan" in issues
    assert "Pilih skema belum punya pilihan" in issues
    assert signing.sync_fields(form_doc) == 1
    assert form_doc.fields.filter(key="ktp").exists()


def test_choice_and_number_validation(form_doc, officer):
    holder = form_doc.recipients.get()
    form_doc.fields.filter(key="ktp").update(required=False)
    form_doc.fields.filter(key="mulai").update(kind=K.NUMBER)
    form_doc.fields.filter(key="alamat_surat").update(
        kind=K.CHOICE, options="Batam\nRempang"
    )
    signing.send(form_doc, officer)
    base = {"setuju": "1", "mulai": "12,5"}
    with pytest.raises(ValidationError, match="Pilihan tidak dikenal"):
        signing.act(
            holder,
            name="Direktur",
            signature=signature_png(),
            field_values={**base, "alamat_surat": "Jakarta"},
        )
    with pytest.raises(ValidationError, match="Isi angka"):
        signing.act(
            holder,
            name="Direktur",
            signature=signature_png(),
            field_values={**base, "alamat_surat": "Rempang", "mulai": "abc"},
        )
    signing.act(
        holder,
        name="Direktur",
        signature=signature_png(),
        field_values={**base, "alamat_surat": "Rempang"},
    )
    assert form_doc.fields.get(key="mulai").value == "12.5"


def test_sign_page_renders_fields_and_accepts_upload(client, form_doc, officer):
    signing.send(form_doc, officer)
    holder = form_doc.recipients.get()
    client.force_login(holder.user)
    url = reverse("dokumen_portal:sign", args=[holder.token])
    page = client.get(url).content.decode()
    assert 'enctype="multipart/form-data"' in page
    assert 'name="kolom_alamat_surat"' in page and 'type="date"' in page
    assert "own-field" in page
    response = client.post(
        url,
        {
            "aksi": "tanda_tangan",
            "name": "Direktur Uji",
            "signature": signature_png(),
            "agree": "on",
            "kolom_alamat_surat": "Jl. Portal",
        },
    )
    assert response.status_code == 200  # tanggal, centang, dan KTP masih kosong
    assert "Jl. Portal" in response.content.decode()
    response = client.post(
        url,
        {
            "aksi": "tanda_tangan",
            "name": "Direktur Uji",
            "signature": signature_png(),
            "agree": "on",
            "kolom_alamat_surat": "Jl. Portal",
            "kolom_mulai": "2027-01-02",
            "kolom_setuju": "1",
            "kolom_ktp": jpg_upload(),
        },
    )
    assert response.status_code == 302
    form_doc.refresh_from_db()
    assert form_doc.status == S.COMPLETED


def test_duplicate_copies_field_definitions(form_doc, officer):
    copy = signing.duplicate(form_doc, officer)
    assert list(copy.fields.values_list("key", "kind")) == list(
        form_doc.fields.values_list("key", "kind")
    )
    assert copy.fields.first().recipient.document_id == copy.pk


# --------------------------------------------------------------------------
# Kode akses & penghitung dibuka
# --------------------------------------------------------------------------


def test_access_code_required_with_email_code(client, draft, officer):
    draft.recipients.all().delete()
    external = add_external(draft, order=1, email="luar@contoh.id")
    signing.set_access_code(external, "Rahasia-77")
    external.save()
    assert external.has_access_code and "Rahasia" not in external.access_code_hash
    signing.send(draft, officer)
    signing.send_otp(external)
    code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
    assert "Rahasia" not in mail.outbox[-1].body
    assert not signing.check_otp(external, code)
    assert not signing.check_otp(external, code, "salah")
    assert signing.check_otp(external, code, "Rahasia-77")

    url = reverse("dokumen_portal:sign", args=[external.token])
    page = client.get(url).content.decode()
    assert 'name="access_code"' in page


def test_account_recipient_with_access_code_needs_otp(draft, officer):
    holder = draft.recipients.get()
    assert not holder.needs_otp
    signing.set_access_code(holder, "1234")
    holder.save()
    assert holder.needs_otp


def test_view_count_increments(client, draft, officer):
    signing.send(draft, officer)
    holder = draft.recipients.get()
    client.force_login(holder.user)
    url = reverse("dokumen_portal:sign", args=[holder.token])
    client.get(url)
    client.get(url)
    holder.refresh_from_db()
    assert holder.view_count == 2 and holder.last_viewed_at


# --------------------------------------------------------------------------
# Tanda tangan langsung di hadapan petugas
# --------------------------------------------------------------------------


@pytest.fixture
def in_person_doc(draft):
    draft.recipients.all().delete()
    recipient = draft.recipients.create(
        order=1, name="Warga Tanpa Surel", in_person=True, role="Warga"
    )
    return draft, recipient


def test_in_person_requires_hosted_session(in_person_doc, officer):
    document, recipient = in_person_doc
    assert signing.problems(document) == []
    signing.send(document, officer)
    assert not mail.outbox or all(
        recipient.name not in " ".join(m.to) for m in mail.outbox
    )
    with pytest.raises(ValidationError):
        signing.send_otp(recipient)
    with pytest.raises(ValidationError, match="kode verifikasi"):
        signing.act(recipient, name="Warga Uji", signature=signature_png())
    with pytest.raises(ValidationError, match="identitas"):
        signing.start_hosted(recipient, officer, " ")
    signing.start_hosted(recipient, officer, "KTP 2171000000000001")
    recipient.refresh_from_db()
    assert recipient.hosted_for(officer)
    signing.act(recipient, name="Warga Uji", signature=signature_png(), host=officer)
    recipient.refresh_from_db()
    assert recipient.status == enums.RecipientStatus.DONE
    assert "KTP 2171000000000001" in recipient.verification_note
    assert recipient.hosted_by_id is None
    document.refresh_from_db()
    assert document.status == S.COMPLETED
    assert Activity.objects.filter(signing=document, action=enums.Action.HOSTED)


def test_problems_require_email_unless_in_person(draft):
    draft.recipients.all().delete()
    draft.recipients.create(order=1, name="Tanpa Surel")
    assert any("Surel Tanpa Surel" in str(i) for i in signing.problems(draft))


def test_hosted_flow_through_admin_and_portal(in_person_doc, officer, client):
    document, recipient = in_person_doc
    signing.send(document, officer)
    sign_url = reverse("dokumen_portal:sign", args=[recipient.token])
    page = Client().get(sign_url).content.decode()
    assert "langsung di hadapan petugas" in page and "kirim_kode" not in page

    client.force_login(officer)
    hosted = reverse("admin:dokumen_signingdocument_hosted", args=[recipient.pk])
    assert client.get(hosted).status_code == 200
    response = client.post(hosted, {"evidence": "KTP 2171", "confirm": "on"})
    assert response.status_code == 302 and response["Location"] == sign_url
    page = client.get(sign_url).content.decode()
    assert "dk-sign-form" in page and "Tanda tangan langsung" in page
    response = client.post(
        sign_url,
        {
            "aksi": "tanda_tangan",
            "name": "Warga Uji",
            "signature": signature_png(),
            "agree": "on",
        },
    )
    assert response.status_code == 302
    assert response["Location"] == reverse(
        "admin:dokumen_signingdocument_change", args=[document.pk]
    )
    recipient.refresh_from_db()
    assert recipient.status == enums.RecipientStatus.DONE


def test_hosted_session_is_bound_to_officer(in_person_doc, officer, administrator):
    document, recipient = in_person_doc
    signing.send(document, officer)
    signing.start_hosted(recipient, officer, "KTP 2171")
    recipient.refresh_from_db()
    assert not recipient.hosted_for(administrator)
    with pytest.raises(ValidationError, match="Sesi"):
        signing.act(
            recipient, name="Warga Uji", signature=signature_png(), host=administrator
        )


# --------------------------------------------------------------------------
# Ganti penerima
# --------------------------------------------------------------------------


def test_reassign_recipient_resets_link(
    client, draft, officer, django_capture_on_commit_callbacks
):
    draft.recipients.all().delete()
    external = add_external(draft, order=1, email="lama@contoh.id")
    with django_capture_on_commit_callbacks(execute=True):
        signing.send(draft, officer)
    old_token = external.token
    mail.outbox.clear()
    with pytest.raises(ValidationError, match="alasan"):
        signing.reassign(
            external,
            name="Pejabat Baru",
            email="baru@contoh.id",
            user=None,
            officer=officer,
            reason="",
        )
    with django_capture_on_commit_callbacks(execute=True):
        signing.reassign(
            external,
            name="Pejabat Baru",
            email="baru@contoh.id",
            user=None,
            officer=officer,
            reason="Pejabat berganti",
        )
    external.refresh_from_db()
    assert external.token != old_token and external.email == "baru@contoh.id"
    assert [m.to for m in mail.outbox] == [["baru@contoh.id"]]
    assert (
        client.get(reverse("dokumen_portal:sign", args=[old_token])).status_code == 404
    )
    assert Activity.objects.filter(
        signing=draft, action=enums.Action.REASSIGNED, detail__contains="lama@contoh.id"
    ).exists()


def test_cannot_reassign_after_signing(draft, officer):
    signing.send(draft, officer)
    holder = draft.recipients.get()
    signing.act(holder, name="Direktur", signature=signature_png())
    with pytest.raises(ValidationError):
        signing.reassign(
            holder,
            name="Orang Lain",
            email="lain@contoh.id",
            user=None,
            officer=officer,
            reason="x",
        )


def test_admin_reassign_view(client, draft, officer):
    signing.send(draft, officer)
    external = add_external(draft, order=2)
    client.force_login(officer)
    url = reverse("admin:dokumen_signingdocument_reassign", args=[external.pk])
    assert client.get(url).status_code == 200
    response = client.post(
        url, {"name": "Notaris Baru", "email": "baru@contoh.id", "reason": "Cuti"}
    )
    assert response.status_code == 302
    external.refresh_from_db()
    assert external.name == "Notaris Baru"
    change = client.get(
        reverse("admin:dokumen_signingdocument_change", args=[draft.pk])
    )
    assert change.status_code == 200 and "Ganti" in change.content.decode()


def test_reassign_and_hosted_need_send_permission(client, draft, verifier):
    holder = draft.recipients.get()
    client.force_login(verifier)
    for name in ("reassign", "hosted"):
        url = reverse(f"admin:dokumen_signingdocument_{name}", args=[holder.pk])
        assert client.get(url).status_code == 403


# --------------------------------------------------------------------------
# Kirim massal
# --------------------------------------------------------------------------


def test_bulk_send_one_document_per_land_use(
    land_use, officer, form_template, make_applicant, plot
):
    form_template.body = "<p>Pernyataan {{ pemohon.nama }}</p>"
    form_template.save()
    other = LandUse.objects.create(
        title="Gudang", scheme=enums.Scheme.LEASE, holder=make_applicant(), plot=plot
    )
    no_account = LandUse.objects.create(
        title="Tanpa akun", scheme=enums.Scheme.LEASE, holder_name="Warga", plot=plot
    )
    results = signing.bulk_send(
        template=form_template,
        land_uses=[land_use, other, no_account],
        user=officer,
        title="Pernyataan {nomor}",
        extra_recipient={
            "user": officer,
            "name": "Petugas",
            "email": officer.email or "petugas@contoh.id",
            "role": "Petugas",
        },
    )
    statuses = [r["status"] for r in results]
    assert statuses == ["dikirim", "dikirim", "gagal"]
    assert results[0]["document"].title == f"Pernyataan {land_use.number}"
    assert results[0]["document"].recipients.count() == 2
    assert "akun portal" in results[2]["note"]
    assert Activity.objects.filter(action=enums.Action.BULK_SENT).count() == 2


def test_bulk_send_admin_action(client, land_use, officer, form_template):
    client.force_login(officer)
    changelist = reverse("admin:dokumen_landuse_changelist")
    response = client.post(
        changelist,
        {"action": "bulk_send_documents", "_selected_action": [land_use.pk]},
    )
    assert response.status_code == 302 and "kirim-massal" in response["Location"]
    page = client.get(response["Location"])
    assert page.status_code == 200
    form_template.body = "<p>Halo {{ pemohon.nama }}</p>"
    form_template.save()
    result = client.post(response["Location"], {"template": form_template.pk})
    assert result.status_code == 200 and "Hasil kirim massal" in result.content.decode()
    assert land_use.signing_documents.filter(status=S.SENT).count() == 1


# --------------------------------------------------------------------------
# Tanda tangan tersimpan
# --------------------------------------------------------------------------


def test_saved_signature_page_and_use(client, draft, officer):
    holder = draft.recipients.get()
    url = reverse("dokumen_portal:saved_signature")
    assert client.get(url).status_code == 302
    client.force_login(holder.user)
    assert client.get(url).status_code == 200
    response = client.post(
        url,
        {"name": "Direktur Uji", "signature": signature_png(), "password": "salah"},
    )
    assert response.status_code == 200 and not SavedSignature.objects.exists()
    response = client.post(
        url,
        {"name": "Direktur Uji", "signature": signature_png(), "password": PASSWORD},
    )
    assert response.status_code == 302
    saved = SavedSignature.objects.get(user=holder.user)

    signing.send(draft, officer)
    sign_url = reverse("dokumen_portal:sign", args=[holder.token])
    assert 'data-mode="tersimpan"' in client.get(sign_url).content.decode()
    response = client.post(
        sign_url,
        {
            "aksi": "tanda_tangan",
            "name": "Direktur Uji",
            "signature": "",
            "use_saved": "1",
            "agree": "on",
        },
    )
    assert response.status_code == 302
    holder.refresh_from_db()
    assert holder.status == enums.RecipientStatus.DONE
    assert holder.signature_image == saved.image


def test_saved_signature_not_usable_by_other_recipient(client, draft, officer):
    draft.recipients.all().delete()
    external = add_external(draft, order=1, email="luar@contoh.id")
    signing.send(draft, officer)
    # Penerima tanpa akun tidak pernah mendapat tanda tangan tersimpan.
    from dokumen.views import _saved_signature

    class Request:
        user = officer

    assert _saved_signature(Request(), external) is None


# --------------------------------------------------------------------------
# Cap tanda tangan pada PDF unggahan
# --------------------------------------------------------------------------


def test_signature_stamped_on_uploaded_pdf(land_use, officer):
    from pypdf import PdfReader

    document = signing.create(
        user=officer, title="Kontrak", land_use=land_use, upload=pdf_upload()
    )
    holder = document.recipients.get()
    holder.stamp_page = -1
    holder.stamp_x, holder.stamp_y, holder.stamp_width = 55, 70, 30
    holder.save()
    signing.send(document, officer)
    signing.act(holder, name="Direktur Uji", signature=signature_png())
    document.refresh_from_db()
    reader = PdfReader(io.BytesIO(document.final_file.read()))
    first = reader.pages[0]
    images = list(first.images)
    assert images, "cap tanda tangan tidak ditemukan pada halaman dokumen"
