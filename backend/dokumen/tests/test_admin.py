import io
import zipfile

import docx
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from dokumen import enums, signing
from dokumen.models import DocumentTemplate, SigningDocument

from .conftest import pdf_upload, record_of


def docx_bytes(text):
    document = docx.Document()
    document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def pages(land_use, officer):
    record = record_of(land_use, "nib")
    template = DocumentTemplate.objects.get(name__istartswith="Surat pernyataan")
    document = signing.create(
        user=officer,
        title="Uji",
        template=template,
        land_use=land_use,
        extra={"batas_waktu": "1 bulan"},
    )
    return {
        "dasbor": reverse("dokumen-dashboard"),
        "indeks": reverse("admin:app_list", args=["dokumen"]),
        "pemanfaatan": reverse("admin:dokumen_landuse_changelist"),
        "pemanfaatan_ubah": reverse("admin:dokumen_landuse_change", args=[land_use.pk]),
        "izin": reverse("admin:dokumen_permitrecord_changelist"),
        "izin_ubah": reverse("admin:dokumen_permitrecord_change", args=[record.pk]),
        "izin_verifikasi": reverse(
            "admin:dokumen_permitrecord_process", args=[record.pk, "verifikasi"]
        ),
        "izin_templat": reverse(
            "admin:dokumen_permitrecord_generate", args=[record.pk]
        ),
        "ttd": reverse("admin:dokumen_signingdocument_changelist"),
        "ttd_ubah": reverse("admin:dokumen_signingdocument_change", args=[document.pk]),
        "ttd_tambah": reverse("admin:dokumen_signingdocument_add"),
        "ttd_pratinjau": reverse(
            "admin:dokumen_signingdocument_preview", args=[document.pk]
        ),
        "templat": reverse("admin:dokumen_documenttemplate_changelist"),
        "templat_ubah": reverse(
            "admin:dokumen_documenttemplate_change", args=[template.pk]
        ),
        "templat_pratinjau": reverse(
            "admin:dokumen_documenttemplate_preview", args=[template.pk]
        ),
        "templat_impor": reverse("admin:dokumen_documenttemplate_import"),
        "unduh": reverse("admin:dokumen_downloadrequest_changelist"),
        "riwayat_unduh": reverse("admin:dokumen_downloadlog_changelist"),
        "aktivitas": reverse("admin:dokumen_activity_changelist"),
        "jenis": reverse("admin:dokumen_permittype_changelist"),
        "pengaturan": reverse("admin:dokumen_documentsettings_changelist"),
    }


EXPECTED = {
    # nama halaman yang DITOLAK per peran (selain itu harus terbuka)
    "officer": set(),
    "verifier": {"ttd_tambah", "templat_impor", "riwayat_unduh", "pengaturan"},
    "legal": {"izin_verifikasi", "izin_templat", "riwayat_unduh", "pengaturan"},
    "administrator": set(),
}


@pytest.mark.parametrize("role", ["officer", "verifier", "legal", "administrator"])
def test_admin_pages_per_role(client, request, pages, role):
    user = request.getfixturevalue(role)
    client.force_login(user)
    denied = EXPECTED[role]
    for name, url in pages.items():
        response = client.get(url, follow=False)
        if name in denied:
            assert response.status_code in (
                302,
                403,
            ), f"{role} {name} {response.status_code}"
            if response.status_code == 302:
                assert "/login/" in response["Location"] or response[
                    "Location"
                ].startswith("/admin/")
        else:
            assert response.status_code in (
                200,
                302,
            ), f"{role} {name} {response.status_code}"
            if name == "pengaturan":
                assert (
                    response.status_code == 302 and "/change/" in response["Location"]
                )
            elif name not in ("ttd_pratinjau",):
                assert response.status_code == 200, f"{role} {name}"


def test_applicant_cannot_open_admin(client, land_use, pages):
    client.force_login(land_use.holder.user)
    response = client.get(pages["dasbor"])
    assert response.status_code == 302 and "/admin/dokumen/" not in response["Location"]


def test_verifier_processes_record_in_panel(client, land_use, verifier):
    record = record_of(land_use, "nib")
    client.force_login(verifier)
    url = reverse("admin:dokumen_permitrecord_process", args=[record.pk, "unggah"])
    response = client.post(
        url, {"file": pdf_upload(), "number": "NIB-9", "verify_now": "on"}
    )
    assert response.status_code == 302
    record.refresh_from_db()
    assert record.status == enums.RecordStatus.VERIFIED and record.number == "NIB-9"
    page = client.get(reverse("admin:dokumen_permitrecord_change", args=[record.pk]))
    assert b"Pratinjau" in page.content and b"Minta unduh" in page.content


def test_generate_version_from_template(client, land_use, officer):
    record = record_of(land_use, "bast")
    client.force_login(officer)
    url = reverse("admin:dokumen_permitrecord_generate", args=[record.pk])
    page = client.get(url)
    assert page.status_code == 200
    response = client.post(
        url, {"template": record.permit_type.template_id, "note": "Draf BAST"}
    )
    assert response.status_code == 302
    assert record.versions.get().source == enums.VersionSource.TEMPLATE


def test_signing_admin_flow(client, land_use, officer, legal):
    client.force_login(officer)
    response = client.post(
        reverse("admin:dokumen_signingdocument_add"),
        {
            "title": "Kontrak",
            "land_use": land_use.pk,
            "source_file": pdf_upload("kontrak.pdf"),
        },
    )
    assert response.status_code == 302, response.content[:500]
    document = SigningDocument.objects.get(title="Kontrak")
    assert document.recipients.count() == 1
    change = reverse("admin:dokumen_signingdocument_change", args=[document.pk])
    assert client.get(change).status_code == 200
    # Tindakan cepat hanya lewat POST.
    process = reverse(
        "admin:dokumen_signingdocument_process", args=[document.pk, "kirim"]
    )
    assert client.get(process).status_code == 302
    document.refresh_from_db()
    assert document.status == enums.SigningStatus.DRAFT
    client.post(
        reverse("admin:dokumen_signingdocument_comment", args=[document.pk]),
        {"body": "Cek pasal 3", "internal": "1"},
    )
    assert document.comments.get().is_internal
    response = client.post(process)
    document.refresh_from_db()
    assert document.status == enums.SigningStatus.SENT
    page = client.get(change)
    assert b"Kirim pengingat" in page.content
    assert b'name="_save"' not in page.content  # dokumen terkirim tidak dapat diedit
    # Penerima tanpa izin kirim tidak dapat mengirim pengingat.
    client.force_login(legal)
    response = client.post(
        reverse("admin:dokumen_signingdocument_process", args=[document.pk, "ingatkan"])
    )
    assert response.status_code == 302


def test_template_import_zip_and_word(client, officer):
    client.force_login(officer)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Surat_kuasa.docx", docx_bytes("Kuasa dari {{ pemohon.nama }}"))
        zf.writestr(
            "formulir/Pernyataan-ahli.html",
            "<h1>Pernyataan</h1><script>alert(1)</script><p>{{ pemohon.nama }}</p>",
        )
        zf.writestr("catatan.exe", b"MZ")
        zf.writestr("__MACOSX/._x", b"")
    upload = SimpleUploadedFile(
        "paket.zip", archive.getvalue(), content_type="application/zip"
    )
    response = client.post(
        reverse("admin:dokumen_documenttemplate_import"),
        {"files": [upload], "category": "perizinan", "docx_mode": "docx"},
    )
    assert response.status_code == 302
    word = DocumentTemplate.objects.get(name="Surat kuasa")
    assert word.kind == enums.TemplateKind.DOCX and word.file
    html = DocumentTemplate.objects.get(name="Pernyataan ahli")
    assert html.kind == enums.TemplateKind.HTML and "script" not in html.body
    page = client.get(reverse("admin:dokumen_documenttemplate_change", args=[word.pk]))
    assert b"pemohon.nama" in page.content
    response = client.get(
        reverse("admin:dokumen_documenttemplate_download", args=[word.pk])
    )
    assert response.status_code == 200 and response.content[:2] == b"PK"


def test_template_import_word_as_editable(client, officer):
    client.force_login(officer)
    upload = SimpleUploadedFile(
        "Berita acara.docx", docx_bytes("Berita acara {{ pemanfaatan.nomor }}")
    )
    response = client.post(
        reverse("admin:dokumen_documenttemplate_import"),
        {"files": [upload], "category": "kontrak", "docx_mode": "html"},
    )
    template = DocumentTemplate.objects.get(name="Berita acara")
    assert response.status_code == 302 and template.kind == enums.TemplateKind.HTML
    assert "pemanfaatan.nomor" in template.body


def test_template_import_rejects_disguised_file(client, officer):
    client.force_login(officer)
    upload = SimpleUploadedFile("berbahaya.pdf", b"MZ\x90 bukan pdf")
    response = client.post(
        reverse("admin:dokumen_documenttemplate_import"),
        {"files": [upload], "category": "lainnya", "docx_mode": "docx"},
    )
    assert response.status_code == 200
    assert not DocumentTemplate.objects.filter(name="Berbahaya").exists()


def test_template_version_bumps_on_body_change(client, dokumen_seeded, officer):
    template = DocumentTemplate.objects.get(name__istartswith="Surat pernyataan")
    client.force_login(officer)
    url = reverse("admin:dokumen_documenttemplate_change", args=[template.pk])
    data = {
        "name": template.name,
        "category": template.category,
        "kind": template.kind,
        "description": "",
        "is_active": "on",
        "body": template.body + "<p>Tambahan</p>",
        "signer_roles": template.signer_roles,
        "expiry_days": template.expiry_days or "",
        "confidentiality": template.confidentiality,
    }
    response = client.post(url, data)
    assert response.status_code == 302, (
        response.context["adminform"].form.errors if response.context else ""
    )
    template.refresh_from_db()
    assert template.version == 2


def test_app_index_shortcuts(client, land_use, officer):
    client.force_login(officer)
    page = client.get(reverse("admin:app_list", args=["dokumen"]))
    assert page.status_code == 200
    assert reverse("dokumen-dashboard").encode() in page.content


@pytest.mark.parametrize("mode", ["docx", "html"])
def test_template_import_rejects_unreadable_word(client, officer, mode):
    client.force_login(officer)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("bukan-word.txt", "isi")
    upload = SimpleUploadedFile("Rusak.docx", archive.getvalue())
    response = client.post(
        reverse("admin:dokumen_documenttemplate_import"),
        {"files": [upload], "category": "lainnya", "docx_mode": mode},
    )
    assert response.status_code == 200
    assert "tidak dapat dibaca" in response.content.decode()
    assert not DocumentTemplate.objects.filter(name="Rusak").exists()
