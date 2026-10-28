"""Akun investor: pendaftaran, profil, dasbor investor, dan panel petugas."""

import datetime
import importlib
from decimal import Decimal

import pytest
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from alokasi import enums
from alokasi import investment_services as inv
from alokasi.investment_forms import InvestmentRequestForm
from alokasi.models import Applicant, InvestmentSector, SavedPlot

from .conftest import PASSWORD, square
from .test_portal import login

IS = enums.InvestmentStatus


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def industry(seeded):
    return InvestmentSector.objects.get(name="Industri")


@pytest.fixture
def tourism(seeded):
    return InvestmentSector.objects.get(name="Pariwisata & perhotelan")


@pytest.fixture
def plots(make_plot, industry, tourism):
    lease = dict(
        offer_lease=True,
        offer_allocation=False,
        lease_rate_per_m2_year=Decimal("5000"),
        lease_min_years=2,
    )
    return {
        "ind1": make_plot(code="IND-01", sector=industry, **lease),
        "ind2": make_plot(code="IND-02", sector=industry, geometry=square(104.2)),
        "ind3": make_plot(code="IND-03", sector=industry, geometry=square(104.3)),
        "wis1": make_plot(code="WIS-01", sector=tourism, geometry=square(104.4)),
    }


def _submit(applicant, plots=(), **overrides):
    data = {
        "scheme": enums.InvestmentScheme.LEASE,
        "sector": InvestmentSector.objects.get(name="Industri").pk,
        "project_name": "Pabrik Panel Surya",
        "activity": "Produksi panel surya.",
        "investment_value": "25000000000",
        "capital_origin": enums.CapitalOrigin.DOMESTIC,
        "agree": "on",
        "plots": [p.pk for p in plots],
    }
    data.update(overrides)
    if not plots:
        data["requested_area_m2"] = "5000"
    form = InvestmentRequestForm(data)
    assert form.is_valid(), form.errors
    return inv.submit_request(applicant, form)


def _registration(**overrides):
    data = {
        "email": "Investor@Contoh.ID",
        "password1": "SandiInvestor-2026",
        "password2": "SandiInvestor-2026",
        "applicant_type": enums.ApplicantType.COMPANY,
        "name": "PT Investor Baru",
        "nib": "9120000000099",
        "pic_name": "Budi",
        "phone": "0778123456",
        "address": "Batam",
        "agree": "on",
    }
    data.update(overrides)
    return data


# --------------------------------------------------------------------------
# Pendaftaran & profil
# --------------------------------------------------------------------------


def test_investor_registration_creates_investor_profile(client, industry, tourism):
    url = reverse("portal:investor_register")
    page = client.get(url)
    assert page.status_code == 200
    assert "Daftar akun investor" in page.content.decode()
    assert "is_investor" not in page.context["form"].fields

    data = _registration(
        interest_sectors=[industry.pk, tourism.pk],
        capital_origin=enums.CapitalOrigin.FOREIGN,
        origin_country="Singapura",
        website="https://investor.example",
    )
    response = client.post(url, data)
    assert response.status_code == 200, response.context["form"].errors
    applicant = Applicant.objects.get(user__email="investor@contoh.id")
    assert applicant.is_investor
    assert not applicant.user.is_active
    assert set(applicant.interest_sectors.all()) == {industry, tourism}
    assert applicant.capital_origin == enums.CapitalOrigin.FOREIGN
    assert applicant.origin_country == "Singapura"
    assert len(mail.outbox) == 1


def test_investor_registration_validates_sector_and_country(client, seeded):
    url = reverse("portal:investor_register")
    form = client.post(
        url, _registration(capital_origin=enums.CapitalOrigin.FOREIGN)
    ).context["form"]
    assert "interest_sectors" in form.errors
    assert "origin_country" in form.errors
    assert not Applicant.objects.exists()


def test_regular_registration_has_no_investor_fields(client, seeded):
    url = reverse("portal:register")
    page = client.get(url)
    fields = page.context["form"].fields
    assert "interest_sectors" not in fields and "is_investor" not in fields
    assert reverse("portal:investor_register") in page.content.decode()
    client.post(url, _registration(email="pemohon@contoh.id"))
    applicant = Applicant.objects.get()
    assert not applicant.is_investor
    assert applicant.capital_origin == enums.CapitalOrigin.DOMESTIC


def test_logged_in_applicant_is_sent_to_dashboard(client, applicant):
    login(client, applicant)
    response = client.get(reverse("portal:investor_register"))
    assert response["Location"] == reverse("portal:dashboard")


def test_profile_toggles_investor_and_requires_country_for_foreign_capital(
    client, applicant, industry
):
    login(client, applicant)
    data = {
        "applicant_type": enums.ApplicantType.COMPANY,
        "name": applicant.name,
        "nib": applicant.nib,
        "pic_name": "Siti",
        "phone": "0778",
        "address": "Batam",
        "is_investor": "on",
        "interest_sectors": [industry.pk],
        "capital_origin": enums.CapitalOrigin.FOREIGN,
    }
    response = client.post(reverse("portal:profile"), data)
    assert "origin_country" in response.context["form"].errors
    data["origin_country"] = "Jepang"
    assert client.post(reverse("portal:profile"), data).status_code == 302
    applicant.refresh_from_db()
    assert applicant.is_investor and applicant.origin_country == "Jepang"
    assert list(applicant.interest_sectors.all()) == [industry]
    page = client.get(reverse("portal:profile")).content.decode()
    assert "Profil investor" in page


# --------------------------------------------------------------------------
# Pengajuan minat & isi otomatis
# --------------------------------------------------------------------------


def test_first_request_turns_applicant_into_investor(applicant, plots, tourism):
    assert not applicant.is_investor
    _submit(
        applicant,
        [plots["wis1"]],
        sector=tourism.pk,
        capital_origin=enums.CapitalOrigin.FOREIGN,
        origin_country="Malaysia",
    )
    applicant.refresh_from_db()
    assert applicant.is_investor
    assert applicant.capital_origin == enums.CapitalOrigin.FOREIGN
    assert applicant.origin_country == "Malaysia"
    assert list(applicant.interest_sectors.all()) == [tourism]

    # Permintaan berikutnya tidak menimpa profil yang sudah ada.
    _submit(applicant, [plots["ind1"]])
    applicant.refresh_from_db()
    assert applicant.origin_country == "Malaysia"
    assert list(applicant.interest_sectors.all()) == [tourism]


def test_request_form_is_prefilled_from_profile(
    client, make_applicant, industry, tourism
):
    investor = make_applicant(
        is_investor=True,
        capital_origin=enums.CapitalOrigin.FOREIGN,
        origin_country="Korea Selatan",
    )
    investor.interest_sectors.add(industry)
    login(client, investor)
    initial = (
        client.get(reverse("portal:investment_request_create")).context["form"].initial
    )
    assert initial["capital_origin"] == enums.CapitalOrigin.FOREIGN
    assert initial["origin_country"] == "Korea Selatan"
    assert initial["sector"] == industry.pk
    # Tautan dari peta (sektor lain) tetap menang.
    initial = (
        client.get(
            reverse("portal:investment_request_create") + f"?sektor={tourism.slug}"
        )
        .context["form"]
        .initial
    )
    assert initial["sector"] == tourism.pk


# --------------------------------------------------------------------------
# Dasbor
# --------------------------------------------------------------------------


def test_regular_applicant_keeps_applicant_dashboard(client, applicant, plots):
    login(client, applicant)
    response = client.get(reverse("portal:dashboard"))
    assert [t.name for t in response.templates][0] == "alokasi/portal/dashboard.html"
    assert "Dasbor investor" not in response.content.decode()


def test_investor_dashboard(client, make_applicant, officer, plots, industry):
    investor = make_applicant(is_investor=True)
    investor.interest_sectors.add(industry)
    SavedPlot.objects.create(applicant=investor, plot=plots["ind2"])
    consult = _submit(investor, [plots["ind1"]], project_name="Pabrik A")
    inv.start_review(consult, officer)
    meeting = timezone.now() + datetime.timedelta(days=3)
    inv.schedule_consultation(consult, officer, meeting, "Ruang rapat 1")
    offered = _submit(investor, [plots["ind3"]], project_name="Gudang B")
    inv.make_offer(
        offered,
        officer,
        scheme=enums.InvestmentScheme.LEASE,
        plot=plots["ind3"],
        area_m2=None,
        rate_per_m2_year=Decimal("5000"),
        term_years=5,
        valid_until=timezone.localdate() + datetime.timedelta(days=14),
    )
    cancelled = _submit(investor, project_name="Batal C")
    inv.cancel(cancelled, investor.user)
    other = make_applicant()
    _submit(other, [plots["wis1"]], project_name="Milik orang lain")

    login(client, investor)
    response = client.get(reverse("portal:dashboard"))
    assert response.status_code == 200
    assert [t.name for t in response.templates][0] == (
        "alokasi/portal/dashboard_investor.html"
    )
    ctx = response.context
    assert ctx["active_investments"] == 2
    assert [r.pk for r in ctx["pending_offers"]] == [offered.pk]
    assert [r.pk for r in ctx["upcoming_meetings"]] == [consult.pk]
    assert ctx["saved_codes"] == ["IND-02"]
    # Rekomendasi: sektor minat saja, tanpa lahan tersimpan/sedang diminta.
    assert [p.code for p in ctx["recommended"]] == []
    page = response.content.decode()
    assert "Dasbor investor" in page
    assert "Tinjau penawaran" in page
    assert "Ruang rapat 1" in page
    assert "Milik orang lain" not in page
    assert "Batal C" in page and "Ditutup." in page
    # Bagian alokasi/permohonan disembunyikan bila kosong.
    assert "Alokasi lahan saya" not in page

    # Permintaan yang ditutup melepas lahannya kembali ke rekomendasi.
    inv.cancel(consult, investor.user)
    SavedPlot.objects.all().delete()
    response = client.get(reverse("portal:dashboard"))
    assert {p.code for p in response.context["recommended"]} == {"IND-01", "IND-02"}


def test_investor_without_sectors_sees_featured_plots(client, make_applicant, plots):
    plots["wis1"].is_featured = True
    plots["wis1"].save()
    investor = make_applicant(is_investor=True)
    login(client, investor)
    recommended = client.get(reverse("portal:dashboard")).context["recommended"]
    assert recommended[0].code == "WIS-01"
    assert {p.code for p in recommended} == {"IND-01", "IND-02", "IND-03", "WIS-01"}


# --------------------------------------------------------------------------
# Migrasi & panel petugas
# --------------------------------------------------------------------------


def test_migration_marks_existing_investors(make_applicant, plots, tourism):
    investor = make_applicant()
    _submit(
        investor,
        [plots["wis1"]],
        sector=tourism.pk,
        capital_origin=enums.CapitalOrigin.FOREIGN,
        origin_country="Jepang",
    )
    Applicant.objects.update(
        is_investor=False, capital_origin=enums.CapitalOrigin.DOMESTIC
    )
    investor.interest_sectors.clear()
    bystander = make_applicant()
    module = importlib.import_module("alokasi.migrations.0012_akun_investor")
    module.mark_existing_investors(django_apps, None)
    investor.refresh_from_db()
    bystander.refresh_from_db()
    assert investor.is_investor and investor.origin_country == "Jepang"
    assert list(investor.interest_sectors.all()) == [tourism]
    assert not bystander.is_investor


def test_officer_admin_filters_investors(client, make_applicant, officer, industry):
    investor = make_applicant(name="PT Investor Panel", is_investor=True)
    investor.interest_sectors.add(industry)
    make_applicant(name="PT Pemohon Biasa")
    _submit(investor, project_name="Proyek Panel")
    admin = get_user_model().objects.create_superuser("root", "root@x.id", PASSWORD)
    client.force_login(admin)
    url = reverse("admin:alokasi_applicant_changelist")
    page = client.get(url + "?is_investor__exact=1").content.decode()
    assert "PT Investor Panel" in page and "PT Pemohon Biasa" not in page
    change = client.get(
        reverse("admin:alokasi_applicant_change", args=[investor.pk])
    ).content.decode()
    assert "Profil investor" in change
    assert f"applicant__id__exact={investor.pk}" in change
