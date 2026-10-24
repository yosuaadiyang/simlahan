"""Tes layanan portal baru: katalog layanan, kalkulator UWT, lacak publik,
perpanjangan/pembaruan hak, pecah PL, dan pengukuran ulang."""

import datetime
import importlib
from decimal import Decimal

import pytest
from django.core import mail
from django.urls import reverse

from alokasi import enums, services
from alokasi.models import Application, ServiceCatalog

from .conftest import PASSWORD
from .test_workflow import approve_and_pay

S = enums.ApplicationStatus


def seed_layanan():
    module = importlib.import_module("alokasi.migrations.0007_seed_layanan")
    from django.apps import apps

    module.seed(apps, None)


def login(client, applicant):
    assert client.login(username=applicant.user.username, password=PASSWORD)
    return client


@pytest.fixture
def allocation(filled_application, officer, verifier):
    services.submit(filled_application, filled_application.applicant.user)
    approve_and_pay(filled_application, officer, verifier)
    return filled_application.allocation


# --------------------------------------------------------------------------
# Alur perpanjangan / pembaruan / pecah PL / pengukuran ulang
# --------------------------------------------------------------------------


def test_extension_flow(allocation, officer, upload_required_docs, seeded):
    config = seeded
    config.extension_admin_fee = Decimal("500000")
    config.save()
    holder = allocation.holder
    old_end = allocation.end_date

    application = services.create_service_application(
        holder, allocation, enums.ServiceType.EXTENSION, "Tambah jangka usaha."
    )
    assert application.number.startswith("PPJ-")
    assert application.tracking_pin
    with pytest.raises(Exception, match="Masih ada"):
        services.create_service_application(
            holder, allocation, enums.ServiceType.SPLIT, "permohonan lain"
        )

    upload_required_docs(application)
    services.submit(application, holder.user)
    approve_and_pay(application, officer, None)

    application.refresh_from_db()
    allocation.refresh_from_db()
    assert application.status == S.ISSUED
    assert allocation.status == enums.AllocationStatus.ACTIVE
    assert allocation.end_date > old_end
    years = allocation.plot.effective_term_years
    assert allocation.end_date == (
        services._add_years(old_end, years) - datetime.timedelta(days=1)
    )

    kinds = set(application.invoices.values_list("kind", flat=True))
    assert enums.InvoiceKind.UWT in kinds
    assert enums.InvoiceKind.EXTENSION_FEE in kinds
    uwt = application.invoices.get(kind=enums.InvoiceKind.UWT)
    assert uwt.amount == (
        allocation.area_m2 * allocation.plot.uwt_rate_per_m2_year * years
    ).quantize(Decimal("1"))

    document = application.issued_documents.get()
    assert document.kind == "sph" and document.number.startswith("SPH-")
    assert any("terbit" in m.subject for m in mail.outbox)
    assert any("perpanjangan" in m.body.lower() for m in mail.outbox)


def test_renewal_on_expired_allocation(allocation, officer, upload_required_docs):
    allocation.status = enums.AllocationStatus.EXPIRED
    allocation.save(update_fields=["status"])
    holder = allocation.holder

    # Perpanjangan tertolak atas alokasi berakhir; pembaruan boleh.
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        services.create_service_application(
            holder, allocation, enums.ServiceType.EXTENSION, "tidak boleh"
        )
    application = services.create_service_application(
        holder, allocation, enums.ServiceType.RENEWAL, "Pembaruan setelah berakhir."
    )
    assert application.number.startswith("PMB-")

    upload_required_docs(application)
    services.submit(application, holder.user)
    approve_and_pay(application, officer, None)
    allocation.refresh_from_db()
    assert allocation.status == enums.AllocationStatus.ACTIVE
    today = datetime.date.today()
    years = allocation.plot.effective_term_years
    assert allocation.start_date == today
    assert allocation.end_date == (
        services._add_years(today, years) - datetime.timedelta(days=1)
    )


def test_split_and_remeasure_issue_approval_letter(
    allocation, officer, upload_required_docs, seeded
):
    seeded.service_admin_fee = Decimal("250000")
    seeded.save()
    holder = allocation.holder

    split = services.create_service_application(
        holder, allocation, enums.ServiceType.SPLIT, "Pecah menjadi dua bidang."
    )
    assert split.number.startswith("PCH-")
    upload_required_docs(split)
    services.submit(split, holder.user)
    approve_and_pay(split, officer, None)
    split.refresh_from_db()
    allocation.refresh_from_db()
    assert split.status == S.ISSUED
    assert allocation.status == enums.AllocationStatus.ACTIVE  # tidak berubah
    document = split.issued_documents.get()
    assert document.kind == "spt" and document.number.startswith("SPT-")
    fee = split.invoices.get()
    assert fee.kind == enums.InvoiceKind.SERVICE_FEE
    assert fee.amount == Decimal("250000")

    remeasure = services.create_service_application(
        holder, allocation, enums.ServiceType.REMEASURE, "Ukur ulang batas."
    )
    assert remeasure.number.startswith("PGU-")


def test_service_create_view_and_pin(allocation, applicant, client, seeded):
    holder = allocation.holder
    login(client, holder)
    url = reverse("portal:service_create", args=[allocation.pk])
    assert client.get(url).status_code == 200
    response = client.post(
        url,
        {"service_type": enums.ServiceType.EXTENSION, "reason": "Perpanjang 30 tahun."},
    )
    assert response.status_code == 302
    application = Application.objects.filter(
        applicant=holder, service_type=enums.ServiceType.EXTENSION
    ).get()
    assert response.url == reverse(
        "portal:application_detail", args=[application.number]
    )
    detail = client.get(response.url).content.decode()
    assert application.tracking_pin in detail


# --------------------------------------------------------------------------
# Lacak permohonan publik (nomor + PIN, tanpa login)
# --------------------------------------------------------------------------


def test_public_tracking(client, filled_application, seeded):
    services.submit(filled_application, filled_application.applicant.user)
    application = filled_application
    url = reverse("portal:track")

    assert client.get(url).status_code == 200
    # Salah PIN: pesan galat, tanpa membocorkan keberadaan nomor.
    bad = client.post(url, {"number": application.number, "pin": "XXXXXXXX"})
    assert "tidak ditemukan" in bad.content.decode()
    good = client.post(
        url, {"number": application.number, "pin": application.tracking_pin}
    )
    body = good.content.decode()
    assert application.number in body
    assert application.get_service_type_display() in body
    # Data pribadi pemohon tidak tampil.
    assert application.applicant.name not in body


# --------------------------------------------------------------------------
# Kalkulator UWT & katalog layanan
# --------------------------------------------------------------------------


def test_uwt_calculator(client, plot, seeded):
    seeded.allocation_admin_fee = Decimal("100000")
    seeded.save()
    url = reverse("portal:uwt_calculator")
    assert client.get(url).status_code == 200
    response = client.get(
        url,
        {"plot": plot.pk, "area_m2": "5000", "years": "10"},
    )
    assert response.status_code == 200
    result = response.context["result"]
    assert result["uwt_total"] == Decimal("1000") * 5000 * 10
    assert result["grand_total"] == Decimal("1000") * 5000 * 10 + Decimal("100000")


def test_service_catalog_pages(client, seeded):
    seed_layanan()
    assert ServiceCatalog.objects.count() >= 9
    listing = client.get(reverse("portal:services"))
    assert listing.status_code == 200
    body = listing.content.decode()
    assert "Perpanjangan Hak Atas Tanah" in body

    entry = ServiceCatalog.objects.get(service_type=enums.ServiceType.EXTENSION)
    detail = client.get(reverse("portal:service_detail", args=[entry.slug]))
    assert detail.status_code == 200
    detail_body = detail.content.decode()
    for section in ("Deskripsi", "Syarat", "Alur layanan", "Dasar hukum"):
        assert section in detail_body
    assert entry.legal_basis in detail_body
    assert client.get(reverse("portal:service_terms")).status_code == 200
    assert client.get(reverse("portal:help")).status_code == 200


def test_new_service_docs_seeded(client, seeded):
    seed_layanan()
    from alokasi.models import RequirementDocType

    for service_type in (
        enums.ServiceType.EXTENSION,
        enums.ServiceType.RENEWAL,
        enums.ServiceType.SPLIT,
        enums.ServiceType.REMEASURE,
    ):
        assert RequirementDocType.objects.filter(service_type=service_type).exists()
