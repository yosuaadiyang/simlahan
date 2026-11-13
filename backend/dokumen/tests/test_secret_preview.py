"""Pratinjau tanpa permintaan unduh tidak berlaku untuk dokumen rahasia
kecuali bagi pejabat penyetuju unduhan rahasia (dan penyusun dokumen TTE)."""

import pytest
from django.urls import reverse

from dokumen import enums, services, signing
from dokumen.models import DocumentTemplate, DownloadLog

from .conftest import pdf_upload, record_of

pytestmark = pytest.mark.django_db


@pytest.fixture
def secret_version(land_use, officer):
    record = record_of(land_use, "perjanjian")
    assert record.permit_type.confidentiality == enums.Confidentiality.SECRET
    return services.officer_upload(
        record, officer, pdf_upload(title="Perjanjian"), verify_now=True
    )


@pytest.fixture
def secret_signing(dokumen_seeded, land_use, officer):
    document = signing.create(
        user=officer,
        title="Pernyataan rahasia",
        template=DocumentTemplate.objects.get(name__istartswith="Surat pernyataan"),
        land_use=land_use,
        extra={"batas_waktu": "6 bulan"},
    )
    document.confidentiality = enums.Confidentiality.SECRET
    document.save(update_fields=["confidentiality"])
    return document


def test_verifier_cannot_preview_secret_version(
    client, secret_version, verifier, administrator
):
    url = reverse("dokumen-version-preview", args=[secret_version.pk])
    client.force_login(verifier)
    response = client.get(url)
    assert response.status_code == 302
    assert not DownloadLog.objects.filter(user=verifier).exists()

    client.force_login(administrator)
    response = client.get(url)
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"


def test_secret_signing_preview_needs_preparer_or_confidential_approver(
    client, secret_signing, verifier, officer
):
    url = reverse("admin:dokumen_signingdocument_preview", args=[secret_signing.pk])
    client.force_login(verifier)
    response = client.get(url)
    assert response.status_code == 302
    assert not DownloadLog.objects.filter(user=verifier).exists()

    client.force_login(officer)
    response = client.get(url)
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
