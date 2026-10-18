import json

import pytest
from django.urls import reverse

from alokasi import enums, services
from alokasi.models import (
    Allocation,
    Application,
    Invoice,
    LandPlot,
    VerificationCriterion,
)
from utils.group_permissions import UserGroup

from .conftest import PASSWORD, pdf_file, score_all
from .test_workflow import approve_and_pay

S = enums.ApplicationStatus

CHANGELISTS = (
    "allocationsettings",
    "landplot",
    "infopage",
    "applicant",
    "requirementdoctype",
    "verificationcriterion",
    "application",
    "invoice",
    "allocation",
    "issueddocument",
    "permitreport",
    "developmentreport",
)


def test_group_members_become_staff(officer, verifier):
    assert officer.is_staff and verifier.is_staff
    assert not officer.is_superuser


def test_officer_pages_render(client, officer, filled_application, verifier):
    services.submit(filled_application, filled_application.applicant.user)
    approve_and_pay(filled_application, officer, verifier)
    client.force_login(officer)
    assert client.get("/admin/").status_code == 200
    for model in CHANGELISTS:
        response = client.get(reverse(f"admin:alokasi_{model}_changelist"), follow=True)
        assert response.status_code == 200, model
    allocation = filled_application.allocation
    for url in (
        reverse("admin:alokasi_application_change", args=[filled_application.pk]),
        reverse("admin:alokasi_allocation_change", args=[allocation.pk]),
        reverse(
            "admin:alokasi_invoice_change",
            args=[filled_application.invoices.first().pk],
        ),
        reverse("admin:alokasi_landplot_change", args=[filled_application.plot.pk]),
        reverse("admin:alokasi_landplot_add"),
        reverse("admin:alokasi_landplot_import"),
        reverse("admin:alokasi_allocation_changelist") + "?lahan_tidur=ya",
        reverse("admin:alokasi_allocation_changelist") + "?lapor=terlambat",
        reverse("admin:alokasi_application_changelist") + "?nilai_saya=belum",
    ):
        assert client.get(url).status_code == 200, url


def test_admin_process_flow(client, officer, verifier, filled_application):
    application = filled_application
    services.submit(application, application.applicant.user)

    def process(action):
        return reverse(
            "admin:alokasi_application_process", args=[application.pk, action]
        )

    # Verifikator tidak boleh memutuskan.
    client.force_login(verifier)
    assert client.post(process("verifikasi")).status_code == 403

    client.force_login(officer)
    page = client.get(
        reverse("admin:alokasi_application_change", args=[application.pk])
    ).content.decode()
    assert "Mulai verifikasi teknis" in page
    client.post(process("verifikasi"), {"note": ""})
    application.refresh_from_db()
    assert application.status == S.VERIFYING
    # Petugas alokasi tidak menilai.
    assert (
        client.get(
            reverse("admin:alokasi_application_score", args=[application.pk])
        ).status_code
        == 403
    )

    client.force_login(verifier)
    criteria = list(VerificationCriterion.objects.filter(is_active=True))
    data = {f"score_{c.pk}": "88" for c in criteria}
    data[f"note_{criteria[0].pk}"] = "Sesuai RDTR"
    response = client.post(
        reverse("admin:alokasi_application_score", args=[application.pk]), data
    )
    assert response.status_code == 302
    application.refresh_from_db()
    assert application.score == 88
    # Nilai di luar 0–100 ditolak.
    bad = {f"score_{c.pk}": "120" for c in criteria}
    response = client.post(
        reverse("admin:alokasi_application_score", args=[application.pk]), bad
    )
    assert response.status_code == 200 and response.context["form"].errors

    client.force_login(officer)
    client.post(process("setujui"), {"note": "Lanjut"})
    application.refresh_from_db()
    assert application.status == S.APPROVED

    invoice = application.invoices.first()
    services.upload_payment_proof(invoice, pdf_file(), application.applicant.user)
    assert (
        client.get(
            reverse("alokasi-officer-file", args=["bukti", invoice.pk])
        ).status_code
        == 200
    )
    client.post(
        reverse("admin:alokasi_invoice_reject", args=[invoice.pk]), {"note": "Buram"}
    )
    invoice.refresh_from_db()
    assert invoice.status == enums.InvoiceStatus.UNPAID
    pdf = client.get(reverse("admin:alokasi_invoice_pdf", args=[invoice.pk]))
    assert pdf.content.startswith(b"%PDF")
    for inv in application.invoices.all():
        client.post(
            reverse("admin:alokasi_invoice_verify", args=[inv.pk]), {"note": ""}
        )
    application.refresh_from_db()
    assert application.status == S.ISSUED

    allocation = application.allocation
    client.post(
        reverse("admin:alokasi_allocation_revoke", args=[allocation.pk]), {"note": ""}
    )
    allocation.refresh_from_db()
    assert allocation.status == enums.AllocationStatus.ACTIVE  # alasan wajib
    client.post(
        reverse("admin:alokasi_allocation_revoke", args=[allocation.pk]),
        {"note": "Tidak dibangun"},
    )
    allocation.refresh_from_db()
    assert allocation.status == enums.AllocationStatus.REVOKED


def test_admin_rejects_and_revision_need_note(client, officer, filled_application):
    services.submit(filled_application, filled_application.applicant.user)
    client.force_login(officer)
    url = reverse(
        "admin:alokasi_application_process", args=[filled_application.pk, "tolak"]
    )
    response = client.post(url, {"note": ""})
    assert response.status_code == 200 and response.context["form"].errors
    client.post(
        reverse(
            "admin:alokasi_application_process",
            args=[filled_application.pk, "perbaikan"],
        ),
        {"note": "Lengkapi NPWP"},
    )
    filled_application.refresh_from_db()
    assert filled_application.status == S.REVISION


def test_invalid_transition_shows_error(client, officer, filled_application):
    client.force_login(officer)
    url = reverse(
        "admin:alokasi_application_process", args=[filled_application.pk, "setujui"]
    )
    response = client.post(url, {"note": ""}, follow=True)
    filled_application.refresh_from_db()
    assert filled_application.status == S.DRAFT
    assert "Hanya permohonan dalam verifikasi teknis" in response.content.decode()


def test_officer_file_permissions(
    client, filled_application, make_officer, django_user_model
):
    document = filled_application.documents.first()
    url = reverse("alokasi-officer-file", args=["dokumen", document.pk])
    reader = make_officer("penelusur", UserGroup.SELAILIJA)
    reader.is_staff = True
    reader.save()
    client.force_login(reader)
    assert (
        client.get(url).status_code == 403
    )  # tidak punya izin melihat dokumen permohonan
    verifier = make_officer("verif", UserGroup.TIM_VERIFIKASI)
    client.force_login(verifier)
    assert client.get(url).status_code == 200
    assert (
        client.get(reverse("alokasi-officer-file", args=["tidakada", 1])).status_code
        == 404
    )
    client.logout()
    assert client.get(url).status_code == 302  # ke halaman login admin


def test_admin_cannot_create_or_edit_applications(client, officer, filled_application):
    client.force_login(officer)
    assert client.get(reverse("admin:alokasi_application_add")).status_code == 403
    response = client.post(
        reverse("admin:alokasi_application_change", args=[filled_application.pk]),
        {"status": "terbit"},
    )
    assert response.status_code == 403
    filled_application.refresh_from_db()
    assert filled_application.status == S.DRAFT


def test_geojson_import(client, officer):
    client.force_login(officer)
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "kode": "RMP-01",
                    "nama": "Blok A",
                    "kecamatan": "Galang",
                    "tarif_uwt": "1500",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [104.1, 0.8],
                            [104.101, 0.8],
                            [104.101, 0.801],
                            [104.1, 0.801],
                            [104.1, 0.8],
                        ]
                    ],
                },
            }
        ],
    }
    from django.core.files.uploadedfile import SimpleUploadedFile

    upload = SimpleUploadedFile(
        "lahan.geojson",
        json.dumps(payload).encode(),
        content_type="application/geo+json",
    )
    response = client.post(
        reverse("admin:alokasi_landplot_import"),
        {"file": upload, "allocation_type": "terbuka", "is_published": "on"},
    )
    assert response.status_code == 302
    plot = LandPlot.objects.get(code="RMP-01")
    assert plot.allocation_type == enums.AllocationType.OPEN
    assert plot.is_published and plot.district == "Galang"
    # ±111 m × 111 m di dekat ekuator
    assert 12000 < plot.area_m2 < 12600
    bad = SimpleUploadedFile("x.geojson", b"{bukan json")
    response = client.post(
        reverse("admin:alokasi_landplot_import"),
        {"file": bad, "allocation_type": "reguler"},
    )
    assert response.status_code == 200 and response.context["form"].errors


def test_settings_singleton(client, officer, seeded):
    client.force_login(officer)
    response = client.get(reverse("admin:alokasi_allocationsettings_changelist"))
    assert response.status_code == 302
    assert response.url == reverse("admin:alokasi_allocationsettings_change", args=[1])


def test_bulk_verify_action(client, officer, verifier, filled_application):
    services.submit(filled_application, filled_application.applicant.user)
    services.start_verification(filled_application, officer)
    score_all(filled_application, verifier, 90)
    services.approve(filled_application, officer)
    for invoice in filled_application.invoices.all():
        services.upload_payment_proof(
            invoice, pdf_file(), filled_application.applicant.user
        )
    client.force_login(officer)
    response = client.post(
        reverse("admin:alokasi_invoice_changelist"),
        {
            "action": "verify_selected",
            "_selected_action": list(
                filled_application.invoices.values_list("pk", flat=True)
            ),
        },
    )
    assert response.status_code == 302
    assert not Invoice.objects.exclude(status=enums.InvoiceStatus.PAID).exists()
    assert Application.objects.get(pk=filled_application.pk).status == S.ISSUED
    assert Allocation.objects.count() == 1


@pytest.mark.parametrize("password", [PASSWORD])
def test_superuser_sees_everything(client, django_user_model, password, seeded):
    admin = django_user_model.objects.create_superuser("root", "root@x.id", password)
    client.force_login(admin)
    for model in CHANGELISTS:
        assert (
            client.get(
                reverse(f"admin:alokasi_{model}_changelist"), follow=True
            ).status_code
            == 200
        )
