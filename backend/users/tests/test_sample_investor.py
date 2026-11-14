"""Investor contoh dari ``pengguna_contoh``: profil, data investasi, batas akses,
dan penghapusan bersama data contoh lain."""

import datetime
import io

import pytest
from django.core import mail
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from alokasi import enums
from alokasi import investment_services as inv
from alokasi.models import Applicant, InvestmentRequest, LandPlot, SavedPlot
from users.management.commands.pengguna_contoh import (
    APPLICANT_EMAIL,
    INVESTOR_EMAIL,
    sample_users,
)

from .test_sample_users import run

IS = enums.InvestmentStatus


def call(*args) -> str:
    out = io.StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


@pytest.fixture
def plots(samples):
    call("alokasi_contoh_rempang")
    return LandPlot.objects.filter(code__startswith="CONTOH-RMP-")


@pytest.fixture
def investor(plots):
    run()
    return Applicant.objects.select_related("user").get(user__email=INVESTOR_EMAIL)


def test_investor_account_with_sample_data(investor):
    user = investor.user
    assert investor.is_investor
    assert not user.groups.exists() and not user.is_staff and not user.is_superuser
    assert not user.service_units.exists()
    assert set(investor.interest_sectors.values_list("name", flat=True)) == {
        "Industri",
        "Logistik & pergudangan",
    }
    assert set(investor.saved_plots.values_list("plot__code", flat=True)) == {
        "CONTOH-RMP-01",
        "CONTOH-RMP-04",
        "CONTOH-RMP-07",
    }
    statuses = dict(investor.investment_requests.values_list("project_name", "status"))
    assert sorted(statuses.values()) == sorted(
        [IS.SUBMITTED, IS.CONSULTATION, IS.OFFERED]
    )
    consult = investor.investment_requests.get(status=IS.CONSULTATION)
    assert consult.meeting_at > timezone.now()
    assert consult.messages.count() == 2 and consult.events.count() == 3
    assert consult.assigned_to.username == "contoh.alokasi"
    offered = investor.investment_requests.get(status=IS.OFFERED)
    assert offered.offer_plot.code == "CONTOH-RMP-07"
    assert not offered.offer_expired and offered.offer_total
    # Data contoh tidak pernah mengirim surel.
    assert mail.outbox == []
    # Pemohon contoh tetap pemohon biasa.
    assert not Applicant.objects.get(user__email=APPLICANT_EMAIL).is_investor


def test_rerun_is_idempotent_and_renews_expired_offer(investor):
    offered = investor.investment_requests.get(status=IS.OFFERED)
    offered.offer_valid_until = timezone.localdate() - datetime.timedelta(days=1)
    offered.save()
    run()
    assert investor.investment_requests.count() == 3
    assert investor.saved_plots.count() == 3
    offered.refresh_from_db()
    assert not offered.offer_expired


def test_without_sample_plots_explains(samples):
    output = run()
    assert "alokasi_contoh_rempang" in output
    investor = Applicant.objects.get(user__email=INVESTOR_EMAIL)
    assert investor.is_investor and not investor.investment_requests.exists()


def test_demo_investor_works_end_to_end_and_stays_private(investor):
    run("--sandi", "Contoh-Uji-2026!x")
    client = Client()
    assert (
        client.post(
            reverse("portal:login"),
            {"username": INVESTOR_EMAIL, "password": "Contoh-Uji-2026!x"},
        ).status_code
        == 302
    )
    page = client.get(reverse("portal:dashboard"))
    assert "Dasbor investor" in page.content.decode()
    assert len(page.context["pending_offers"]) == 1
    offered = investor.investment_requests.get(status=IS.OFFERED)
    response = client.post(
        reverse("portal:investment_request_accept", args=[offered.number]),
        {"offered_at": offered.offered_at.isoformat()},
    )
    assert response.status_code == 302
    offered.refresh_from_db()
    assert offered.status == IS.ACCEPTED

    # Pemohon contoh tidak melihat atau mengubah permintaan investor contoh.
    other = Client()
    other.force_login(Applicant.objects.get(user__email=APPLICANT_EMAIL).user)
    number = investor.investment_requests.get(status=IS.CONSULTATION).number
    assert (
        other.get(reverse("portal:investment_request", args=[number])).status_code
        == 404
    )
    assert (
        other.post(
            reverse("portal:investment_request_cancel", args=[number])
        ).status_code
        == 404
    )
    assert (
        other.get(reverse("portal:investment_requests")).context["requests"].count()
        == 0
    )


def test_delete_all_samples_removes_investor_and_plots(investor):
    output = call("hapus_data_contoh")
    assert "permintaan investasi akun contoh dihapus" in output
    assert "dilewati" not in output
    assert not sample_users().exists()
    assert not InvestmentRequest.objects.exists()
    assert not SavedPlot.objects.exists()
    assert not LandPlot.objects.filter(code__startswith="CONTOH-RMP-").exists()


def test_completed_sample_contract_keeps_account_deactivated(investor):
    offered = investor.investment_requests.get(status=IS.OFFERED)
    officer = sample_users().get(username="contoh.alokasi")
    inv.accept_offer(offered, investor.user)
    inv.complete(offered, officer, contract_number="KTR-CONTOH-1")

    run("--hapus")

    investor.user.refresh_from_db()
    assert not investor.user.is_active
    assert not investor.user.has_usable_password()
    # Kontrak yang sudah dicatat tidak ikut terhapus; sisanya hilang.
    assert list(InvestmentRequest.objects.values_list("pk", flat=True)) == [offered.pk]
