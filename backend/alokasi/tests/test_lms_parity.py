"""Tes fitur kesetaraan portal LMS: layanan perubahan dokumen baru, blokir
penetapan lokasi, penerbitan ulang KPT/PPT, PL + sketsa bidang, simulasi UWT
per wilayah, pemenang alokasi terbuka, formulir kontak, dan halaman informasi."""

import datetime
import re
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from alokasi import documents, enums, services
from alokasi.forms import service_choices
from alokasi.models import (
    AllocationSettings,
    ContactMessage,
    InfoPage,
    ServiceCatalog,
    UwtRegion,
    UwtTariff,
)

from .test_workflow import approve_and_pay

S = enums.ApplicationStatus


@pytest.fixture
def allocation(filled_application, officer, verifier):
    services.submit(filled_application, filled_application.applicant.user)
    approve_and_pay(filled_application, officer, verifier)
    return filled_application.allocation


def run_service(allocation, service_type, officer, upload_required_docs, note="Uji"):
    holder = allocation.holder
    application = services.create_service_application(
        holder, allocation, service_type, note
    )
    upload_required_docs(application)
    services.submit(application, holder.user)
    approve_and_pay(application, officer, None)
    application.refresh_from_db()
    return application


# --------------------------------------------------------------------------
# Katalog & layanan baru
# --------------------------------------------------------------------------


def test_catalog_seeded_with_lms_services(seeded):
    seeded_types = set(ServiceCatalog.objects.values_list("service_type", flat=True))
    for service in (
        enums.ServiceType.REVISE_PL,
        enums.ServiceType.MERGE_PL,
        enums.ServiceType.ADJUSTMENT,
        enums.ServiceType.RECOMMENDATION,
        enums.ServiceType.UNBLOCK,
        enums.ServiceType.REPLACEMENT,
        enums.ServiceType.MORTGAGE,
        enums.ServiceType.AUCTION,
        enums.ServiceType.KPT_CHANGE,
        enums.ServiceType.KPT_NEW,
    ):
        assert service in seeded_types, service
    allocation_types = set(
        ServiceCatalog.objects.exclude(allocation_type="").values_list(
            "allocation_type", flat=True
        )
    )
    assert {enums.AllocationType.ARRANGEMENT, enums.AllocationType.KSB} <= (
        allocation_types
    )


@pytest.mark.parametrize(
    "service_type",
    [
        enums.ServiceType.REVISE_PL,
        enums.ServiceType.RECOMMENDATION,
        enums.ServiceType.MORTGAGE,
    ],
)
def test_document_change_services_issue_letter(
    allocation, officer, upload_required_docs, service_type
):
    kpt = allocation.kpt_number
    application = run_service(allocation, service_type, officer, upload_required_docs)
    allocation.refresh_from_db()
    assert application.status == S.ISSUED
    assert allocation.kpt_number == kpt  # alokasi tidak berubah
    assert application.issued_documents.exists()


def test_reissue_replaces_kpt_ppt_and_pl(allocation, officer, upload_required_docs):
    old_kpt, old_ppt = allocation.kpt_number, allocation.ppt_number
    old_docs = list(
        allocation.issued_documents.filter(kind__in=("kpt", "ppt", "pl")).values_list(
            "pk", flat=True
        )
    )
    assert allocation.issued_documents.filter(kind="pl").exists()
    application = run_service(
        allocation, enums.ServiceType.REPLACEMENT, officer, upload_required_docs
    )
    allocation.refresh_from_db()
    assert application.status == S.ISSUED
    assert allocation.kpt_number != old_kpt and allocation.ppt_number != old_ppt
    old = allocation.issued_documents.filter(pk__in=old_docs)
    assert old.count() == 3
    assert all(d.replaced_at and d.replaced_by_id for d in old)
    current = allocation.issued_documents.filter(replaced_at__isnull=True)
    assert set(current.values_list("kind", flat=True)) >= {"kpt", "ppt", "pl"}


# --------------------------------------------------------------------------
# Blokir penetapan lokasi
# --------------------------------------------------------------------------


def test_blocked_allocation_only_allows_unblock(
    allocation, officer, upload_required_docs
):
    holder = allocation.holder
    with pytest.raises(ValidationError):
        services.block_allocation(allocation, officer, "  ")
    services.block_allocation(allocation, officer, "Sengketa batas")
    allocation.refresh_from_db()
    assert allocation.is_blocked and allocation.block_reason == "Sengketa batas"
    choices = {value for value, _label in service_choices(allocation)}
    assert choices == {enums.ServiceType.UNBLOCK}
    with pytest.raises(ValidationError, match="diblokir"):
        services.create_service_application(
            holder, allocation, enums.ServiceType.EXTENSION, "perpanjang"
        )
    application = run_service(
        allocation, enums.ServiceType.UNBLOCK, officer, upload_required_docs
    )
    allocation.refresh_from_db()
    assert application.status == S.ISSUED and not allocation.is_blocked
    assert enums.ServiceType.UNBLOCK not in {
        value for value, _label in service_choices(allocation)
    }


def test_officer_can_unblock_directly(allocation, officer):
    services.block_allocation(allocation, officer, "Tunggakan UWT")
    with pytest.raises(ValidationError):
        services.block_allocation(allocation, officer, "lagi")
    services.unblock_allocation(allocation, officer, "Lunas")
    allocation.refresh_from_db()
    assert not allocation.is_blocked
    with pytest.raises(ValidationError):
        services.unblock_allocation(allocation, officer)


def test_admin_block_views(client, allocation, make_officer):
    from utils.group_permissions import UserGroup

    admin = make_officer("admin-lms", UserGroup.PAAKAYTTAJA)
    client.force_login(admin)
    url = reverse("admin:alokasi_allocation_block", args=[allocation.pk])
    assert client.get(url).status_code == 200
    response = client.post(url, {"note": "Sengketa"})
    assert response.status_code == 302
    allocation.refresh_from_db()
    assert allocation.is_blocked
    page = client.get(reverse("admin:alokasi_allocation_change", args=[allocation.pk]))
    assert page.status_code == 200 and "diblokir" in page.content.decode().lower()


# --------------------------------------------------------------------------
# Penetapan lokasi + sketsa bidang
# --------------------------------------------------------------------------


def test_plot_sketch_and_pl_pdf(allocation):
    sketch, vertices = documents.plot_sketch(allocation.plot.geometry)
    assert sketch.startswith("data:image/png;base64,")
    assert 3 <= len(vertices) <= 200
    assert documents._nice_length(137) in (100, 200, 50)
    pl = allocation.issued_documents.get(kind="pl")
    assert pl.file and pl.number


# --------------------------------------------------------------------------
# Simulasi UWT per wilayah
# --------------------------------------------------------------------------


def test_months_late():
    end = datetime.date(2026, 1, 15)
    assert services.months_late(end, datetime.date(2026, 1, 15)) == 0
    assert services.months_late(end, datetime.date(2026, 1, 16)) == 1
    assert services.months_late(end, datetime.date(2026, 2, 15)) == 1
    assert services.months_late(end, datetime.date(2026, 2, 16)) == 2
    assert services.months_late(None, datetime.date(2030, 1, 1)) == 0


@pytest.fixture
def tariff(seeded):
    region = UwtRegion.objects.create(name="Rempang", sub_name="Sembulang")
    return UwtTariff.objects.create(
        region=region,
        land_use="Industri",
        kind=UwtTariff.Kind.RENEWAL,
        rate_per_m2_year=Decimal("1000"),
        term_years=20,
    )


def test_uwt_simulation_with_penalty_and_cap(tariff):
    config = AllocationSettings.load()
    config.uwt_penalty_percent = Decimal("2")
    config.uwt_penalty_max_months = 24
    today = datetime.date(2026, 11, 1)
    result = services.uwt_simulation(
        tariff, Decimal("100"), datetime.date(2026, 8, 1), today=today, config=config
    )
    assert result["uwt_total"] == Decimal("2000000")
    assert result["late_months"] == 3
    assert result["penalty"] == Decimal("120000")
    assert result["grand_total"] == Decimal("2120000")
    assert not result["capped"]
    capped = services.uwt_simulation(
        tariff, Decimal("100"), datetime.date(2020, 1, 1), today=today, config=config
    )
    assert capped["late_months"] == 24 and capped["capped"]


def test_calculator_page_per_region(client, tariff):
    url = reverse("portal:uwt_calculator")
    page = client.get(url)
    assert page.status_code == 200 and "Per wilayah" in page.content.decode()
    UwtRegion.objects.update(is_active=False)
    fallback = client.get(url, {"mode": "wilayah"}).content.decode()
    assert "Per wilayah" not in fallback and "harus diisi" not in fallback
    UwtRegion.objects.update(is_active=True)
    response = client.get(
        url,
        {
            "mode": "wilayah",
            "w-region": tariff.region_id,
            "w-land_use": "Industri",
            "w-area_m2": "100",
            "w-kind": UwtTariff.Kind.RENEWAL,
            "w-end_date": "2099-01-01",
        },
    )
    body = response.content.decode()
    text = re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", body))
    assert response.status_code == 200
    assert "TotaltagihanUWT" in text and "Rp2.000.000" in text
    assert "Rp Rp" not in body
    missing = client.get(
        url,
        {
            "mode": "wilayah",
            "w-region": tariff.region_id,
            "w-land_use": "Industri",
            "w-area_m2": "100",
            "w-kind": UwtTariff.Kind.RENEWAL,
        },
    )
    assert "Total tagihan UWT" not in missing.content.decode()


# --------------------------------------------------------------------------
# Halaman publik baru
# --------------------------------------------------------------------------


def test_contact_form_creates_message_and_blocks_bots(client, seeded):
    url = reverse("portal:contact")
    assert client.get(url).status_code == 200
    data = {
        "name": "Warga Uji",
        "email": "warga@contoh.id",
        "phone": "0812 3456 7890",
        "subject": "Tanya alokasi",
        "body": "Bagaimana cara mengajukan alokasi lahan?",
    }
    response = client.post(url, data)
    assert response.status_code == 302
    assert ContactMessage.objects.filter(subject="Tanya alokasi").count() == 1
    client.post(url, {**data, "subject": "Bot", "website": "http://spam"})
    assert not ContactMessage.objects.filter(subject="Bot").exists()
    client.post(url, {**data, "subject": "Telepon salah", "phone": "abc"})
    assert not ContactMessage.objects.filter(subject="Telepon salah").exists()


def test_public_information_pages(client, seeded):
    InfoPage.objects.create(
        title="Panduan pengguna portal",
        slug="panduan-portal",
        category=enums.InfoCategory.GUIDE,
        body="Langkah-langkah memakai portal.",
        is_published=True,
    )
    assert client.get(reverse("portal:forms")).status_code == 200
    winners = client.get(reverse("portal:open_winners"))
    assert winners.status_code in (200, 404)
    info = client.get(reverse("portal:info_category", args=["panduan"]))
    assert (
        info.status_code == 200 and "Panduan pengguna portal" in info.content.decode()
    )
