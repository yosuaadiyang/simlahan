"""Regresi audit layanan portal: migrasi katalog, PIN lama, alokasi dicabut
saat layanan berjalan, kalkulator, dan tampilan panel."""

import importlib
from decimal import Decimal

import pytest
from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.urls import reverse

from alokasi import enums, services
from alokasi.models import Application, Invoice, ServiceCatalog

from .conftest import PASSWORD
from .test_workflow import approve_and_pay

S = enums.ApplicationStatus


@pytest.fixture
def allocation(filled_application, officer, verifier):
    services.submit(filled_application, filled_application.applicant.user)
    approve_and_pay(filled_application, officer, verifier)
    return filled_application.allocation


def test_catalog_seed_fills_unique_slugs_with_historical_models(seeded, monkeypatch):
    # Model historis saat `manage.py migrate` tidak memakai save() kustom
    # yang mengisi slug; tirukan agar seed tetap mengisi slug unik sendiri.
    ServiceCatalog.objects.all().delete()
    monkeypatch.setattr(ServiceCatalog, "save", models.Model.save)
    module = importlib.import_module("alokasi.migrations.0007_seed_layanan")
    module.seed(django_apps, None)
    slugs = list(ServiceCatalog.objects.values_list("slug", flat=True))
    assert len(slugs) == len(module.SERVICE_CATALOG)
    assert all(slugs) and len(set(slugs)) == len(slugs)


def test_backfill_tracking_pin_for_old_applications(filled_application):
    Application.objects.filter(pk=filled_application.pk).update(tracking_pin="")
    module = importlib.import_module("alokasi.migrations.0008_backfill_tracking_pin")

    class _Editor:
        connection = connection

    module.backfill(django_apps, _Editor())
    filled_application.refresh_from_db()
    assert len(filled_application.tracking_pin) == 8


@pytest.mark.parametrize(
    "service_type", [enums.ServiceType.EXTENSION, enums.ServiceType.SPLIT]
)
def test_revoked_allocation_is_not_revived_by_service(
    allocation, officer, upload_required_docs, seeded, service_type
):
    seeded.extension_admin_fee = Decimal("500000")
    seeded.service_admin_fee = Decimal("250000")
    seeded.save()
    holder = allocation.holder
    application = services.create_service_application(
        holder, allocation, service_type, "Uraian."
    )
    upload_required_docs(application)
    services.submit(application, holder.user)
    services.start_verification(application, officer)
    services.approve(application, officer, "OK")
    assert application.invoices.exists()

    services.revoke_allocation(allocation, officer, "Lahan tidur.")
    allocation.refresh_from_db()
    application.refresh_from_db()
    assert allocation.status == enums.AllocationStatus.REVOKED
    assert application.status == S.REJECTED
    assert "dicabut" in application.officer_note
    assert not application.invoices.exclude(
        status=enums.InvoiceStatus.CANCELLED
    ).exists()
    assert application.issued_documents.count() == 0


def test_service_issue_refuses_revoked_allocation(
    allocation, officer, upload_required_docs, seeded
):
    holder = allocation.holder
    application = services.create_service_application(
        holder, allocation, enums.ServiceType.EXTENSION, "Uraian."
    )
    upload_required_docs(application)
    services.submit(application, holder.user)
    services.start_verification(application, officer)
    # Dicabut langsung di basis data (mis. data lama) di tengah proses.
    type(allocation).objects.filter(pk=allocation.pk).update(
        status=enums.AllocationStatus.REVOKED
    )
    with pytest.raises(ValidationError, match="Alokasi tidak lagi"):
        services.approve(application, officer, "OK")
    allocation.refresh_from_db()
    assert allocation.status == enums.AllocationStatus.REVOKED


def test_revoke_cancels_draft_service_application(allocation, officer):
    application = services.create_service_application(
        allocation.holder, allocation, enums.ServiceType.REMEASURE, "Uraian."
    )
    services.revoke_allocation(allocation, officer, "Pelanggaran PPT.")
    application.refresh_from_db()
    assert application.status == S.CANCELLED


def test_uwt_calculator_ignores_non_numeric_plot(client, seeded):
    response = client.get(reverse("portal:uwt_calculator"), {"plot": "abc"})
    assert response.status_code == 200


def test_service_form_preselect_and_expired_allocation(allocation, client, seeded):
    assert client.login(username=allocation.holder.user.username, password=PASSWORD)
    url = reverse("portal:service_create", args=[allocation.pk])
    form = client.get(url, {"jenis": "pecah_pl"}).context["form"]
    assert form["service_type"].value() == "pecah_pl"

    allocation.status = enums.AllocationStatus.EXPIRED
    allocation.save(update_fields=["status"])
    form = client.get(url).context["form"]
    assert [v for v, _ in form.fields["service_type"].choices] == [
        enums.ServiceType.RENEWAL
    ]
    detail = client.get(reverse("portal:allocation_detail", args=[allocation.pk]))
    body = detail.content.decode()
    assert "?jenis=pembaruan" in body and "?jenis=pecah_pl" not in body


def test_admin_header_for_service_application(allocation, admin_client, seeded):
    application = services.create_service_application(
        allocation.holder, allocation, enums.ServiceType.SPLIT, "Uraian."
    )
    url = reverse("admin:alokasi_application_change", args=[application.pk])
    body = admin_client.get(url).content.decode()
    assert (
        f"{application.get_service_type_display()} atas "
        f"{allocation.kpt_number}" in body
    )
    assert "Peralihan " + allocation.kpt_number not in body


def test_invoice_model_untouched_for_other_applications(allocation, officer):
    # Pencabutan tidak menyentuh tagihan permohonan alokasi asal yang sudah lunas.
    services.revoke_allocation(allocation, officer, "Alasan.")
    assert not Invoice.objects.filter(
        application=allocation.application, status=enums.InvoiceStatus.CANCELLED
    ).exists()


def test_officer_can_manage_service_catalog(officer, verifier, seeded):
    assert officer.has_perm("alokasi.change_servicecatalog")
    assert officer.has_perm("alokasi.add_servicecatalog")
    assert verifier.has_perm("alokasi.view_servicecatalog")
    assert not verifier.has_perm("alokasi.change_servicecatalog")


def test_uwt_calculator_prefills_from_plot(client, plot):
    response = client.get(reverse("portal:uwt_calculator"), {"plot": plot.pk})
    form = response.context["form"]
    assert not form.is_bound and not form.errors
    assert form["area_m2"].value() == plot.area_m2
    assert form["years"].value() == plot.effective_term_years
