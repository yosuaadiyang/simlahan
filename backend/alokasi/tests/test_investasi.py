"""Portal investasi: halaman publik, permintaan investor, dan proses petugas."""

import datetime
import json
from decimal import Decimal

import pytest
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from alokasi import enums
from alokasi import investment_services as inv
from alokasi.investment_forms import InvestmentRequestForm, parse_area
from alokasi.models import (
    InvestmentEvent,
    InvestmentMessage,
    InvestmentRequest,
    InvestmentSector,
    InvestmentZone,
    LandPlot,
    SavedPlot,
)
from utils.group_permissions import UserGroup

from .conftest import pdf_file, square
from .test_portal import login

IS = enums.InvestmentStatus
SQUARE_GEOJSON = json.dumps(
    {
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
    }
)


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def sector(seeded):
    return InvestmentSector.objects.get(name="Industri")


@pytest.fixture
def zone(seeded, sector):
    zone = InvestmentZone.objects.create(
        name="Kawasan Industri Uji",
        summary="Kawasan uji",
        incentives="Perizinan cepat\nTarif awal",
        geometry=square(104.09, 0.79, 0.03),
    )
    zone.sectors.add(sector)
    return zone


@pytest.fixture
def lease_plot(make_plot, sector, zone):
    return make_plot(
        code="SEWA-01",
        name="Gudang Sewa",
        sector=sector,
        zone=zone,
        offer_lease=True,
        offer_allocation=False,
        lease_rate_per_m2_year=Decimal("5000"),
        lease_min_years=2,
        lease_max_years=10,
        highlights="Dekat pelabuhan\nAkses truk",
        distance_port_km=Decimal("3.5"),
        has_power=True,
        has_road_access=True,
        is_featured=True,
    )


@pytest.fixture
def alloc_plot(make_plot, sector):
    return make_plot(code="ALOK-01", name="Kavling Alokasi", sector=sector)


def _form_data(**overrides):
    data = {
        "scheme": enums.InvestmentScheme.LEASE,
        "sector": InvestmentSector.objects.get(name="Industri").pk,
        "project_name": "Pabrik Panel Surya",
        "activity": "Produksi panel surya untuk pasar ekspor.",
        "investment_value": "25000000000",
        "workforce": "150",
        "capital_origin": enums.CapitalOrigin.DOMESTIC,
        "agree": "on",
    }
    data.update(overrides)
    return data


def _request(applicant, plots=(), **overrides):
    form = InvestmentRequestForm(_form_data(plots=[p.pk for p in plots], **overrides))
    assert form.is_valid(), form.errors
    return inv.submit_request(applicant, form)


# --------------------------------------------------------------------------
# Halaman publik
# --------------------------------------------------------------------------


def test_public_investment_pages(client, lease_plot, alloc_plot, zone):
    pages = (
        reverse("portal:investment_home"),
        reverse("portal:investment_map"),
        reverse("portal:investment_zone", args=[zone.slug]),
        reverse("portal:investment_compare")
        + f"?lahan={lease_plot.code},{alloc_plot.code},TIDAK-ADA",
        reverse("portal:plot_detail", args=[lease_plot.code]),
        reverse("portal:plot_detail", args=[alloc_plot.code]),
        reverse("portal:home"),
    )
    for url in pages:
        response = client.get(url)
        assert response.status_code == 200, url
        assert b"Investasi" in response.content
    home = client.get(reverse("portal:investment_home")).content.decode()
    assert "Gudang Sewa" in home and "Kawasan Industri Uji" in home
    detail = client.get(reverse("portal:plot_detail", args=[lease_plot.code]))
    body = detail.content.decode()
    assert "data-simulator" in body and 'data-lease-rate="5000.00"' in body
    assert "Dekat pelabuhan" in body and "Perizinan cepat" in body  # insentif kawasan
    assert "Ajukan minat investasi" in body
    # Lahan sewa saja tidak menampilkan tombol permohonan alokasi langsung.
    assert "Langsung ajukan permohonan alokasi" not in body
    compare = client.get(
        reverse("portal:investment_compare")
        + f"?lahan={lease_plot.code},{alloc_plot.code}"
    )
    assert list(compare.context["plots"]) == [lease_plot, alloc_plot]


def test_unpublished_zone_hidden(client, zone):
    zone.is_published = False
    zone.save()
    assert (
        client.get(reverse("portal:investment_zone", args=[zone.slug])).status_code
        == 404
    )


def test_investment_data_json(client, lease_plot, alloc_plot, make_plot, zone):
    make_plot(code="TUTUP-01", status=enums.PlotStatus.CLOSED)
    make_plot(code="RAHASIA-01", is_published=False)
    response = client.get(reverse("portal:investment_data"))
    assert response.status_code == 200
    data = response.json()
    codes = {f["properties"]["code"] for f in data["plots"]["features"]}
    assert codes == {lease_plot.code, alloc_plot.code}
    lease = next(
        f["properties"]
        for f in data["plots"]["features"]
        if f["properties"]["code"] == "SEWA-01"
    )
    assert lease["lease"] is True and lease["allocation"] is False
    assert lease["lease_rate"] == "5000.00"  # teks: presisi nominal besar terjaga
    assert lease["sector"] == "industri" and lease["zone"] == zone.slug
    assert data["zones"]["features"][0]["properties"]["slug"] == zone.slug


def test_plot_profile_pdf(client, lease_plot):
    response = client.get(reverse("portal:plot_profile_pdf", args=[lease_plot.code]))
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_leased_status_badge_and_color(client, lease_plot):
    lease_plot.status = enums.PlotStatus.LEASED
    lease_plot.save()
    body = client.get(
        reverse("portal:plot_detail", args=[lease_plot.code])
    ).content.decode()
    assert "badge-disewa" in body
    assert "Ajukan minat investasi" not in body


def test_plot_flags():
    plot = LandPlot(
        status=enums.PlotStatus.AVAILABLE,
        is_published=True,
        offer_allocation=False,
        offer_lease=True,
        lease_rate_per_m2_year=Decimal("1000"),
        area_m2=Decimal("100"),
        lease_min_years=3,
    )
    assert plot.is_available and not plot.is_open_for_application
    assert plot.lease_estimate == Decimal("300000")
    assert [s for s, _label in plot.schemes] == [enums.InvestmentScheme.LEASE]


def test_plot_clean_rules(make_plot):
    plot = make_plot(code="X-1")
    plot.offer_lease = True
    plot.lease_rate_per_m2_year = Decimal("0")
    with pytest.raises(ValidationError):
        plot.full_clean()
    plot.lease_rate_per_m2_year = Decimal("10")
    plot.lease_min_years = 10
    plot.lease_max_years = 5
    with pytest.raises(ValidationError):
        plot.full_clean()


# --------------------------------------------------------------------------
# Formulir & gambar lokasi
# --------------------------------------------------------------------------


def test_parse_area_valid_and_invalid():
    geom = parse_area(SQUARE_GEOJSON)
    assert geom.geom_type == "MultiPolygon" and geom.srid == 4326
    feature = json.dumps({"type": "Feature", "geometry": json.loads(SQUARE_GEOJSON)})
    assert parse_area(feature).geom_type == "MultiPolygon"
    assert parse_area("") is None
    from django import forms

    for bad in (
        "bukan json",
        json.dumps({"type": "Point", "coordinates": [104, 0.8]}),
        json.dumps(
            {
                "type": "Polygon",
                "coordinates": [[[500, 0], [501, 0], [501, 1], [500, 0]]],
            }
        ),
        json.dumps(
            {
                "type": "Polygon",
                "coordinates": [[[104, 0.8], [104, 0.8], [104, 0.8], [104, 0.8]]],
            }
        ),
        json.dumps(
            {
                "type": "Polygon",
                "coordinates": [[[0, 0], [60, 0], [60, 60], [0, 60], [0, 0]]],
            }
        ),
    ):
        with pytest.raises(forms.ValidationError):
            parse_area(bad)


def test_form_requires_location_and_country(seeded):
    form = InvestmentRequestForm(_form_data())
    assert not form.is_valid()
    assert "requested_area_m2" in form.errors
    form = InvestmentRequestForm(
        _form_data(requested_area_m2="5000", capital_origin=enums.CapitalOrigin.FOREIGN)
    )
    assert not form.is_valid() and "origin_country" in form.errors
    form = InvestmentRequestForm(
        _form_data(requested_area_geojson=SQUARE_GEOJSON, target_start="2000-01-01")
    )
    assert not form.is_valid() and "target_start" in form.errors
    form = InvestmentRequestForm(_form_data(requested_area_geojson=SQUARE_GEOJSON))
    assert form.is_valid(), form.errors


def test_form_rejects_unavailable_plot(seeded, make_plot):
    taken = make_plot(code="TERIKAT", status=enums.PlotStatus.ALLOCATED)
    form = InvestmentRequestForm(_form_data(plots=[taken.pk]))
    assert not form.is_valid() and "plots" in form.errors


# --------------------------------------------------------------------------
# Investor
# --------------------------------------------------------------------------


def test_request_create_requires_login(client, seeded):
    response = client.get(reverse("portal:investment_request_create"))
    assert response.status_code == 302 and "/masuk/" in response["Location"]


def test_investor_submits_request(
    client, applicant, officer, lease_plot, django_capture_on_commit_callbacks
):
    login(client, applicant)
    url = reverse("portal:investment_request_create")
    page = client.get(url + f"?lahan={lease_plot.code}")
    assert page.status_code == 200
    assert page.context["form"].initial["scheme"] == enums.InvestmentScheme.LEASE
    assert any(o["selected"] for o in page.context["plot_options"])
    mail.outbox.clear()
    with_attachment = _form_data(
        plots=[lease_plot.pk], requested_area_geojson=SQUARE_GEOJSON
    )
    with_attachment["attachment"] = pdf_file("proposal.pdf")
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(url, with_attachment)
    investment = InvestmentRequest.objects.get()
    assert response.status_code == 302
    assert response["Location"] == reverse(
        "portal:investment_request", args=[investment.number]
    )
    assert investment.number.startswith("INV-")
    assert investment.status == IS.SUBMITTED
    assert list(investment.plots.all()) == [lease_plot]
    assert investment.requested_area is not None
    assert investment.attachment_name == "proposal.pdf"
    assert investment.events.get().status == IS.SUBMITTED
    recipients = {address for m in mail.outbox for address in m.to}
    assert applicant.user.email in recipients and officer.email in recipients
    detail = client.get(response["Location"])
    assert detail.status_code == 200 and b"Pabrik Panel Surya" in detail.content
    attachment = client.get(
        reverse("portal:investment_request_attachment", args=[investment.number])
    )
    assert attachment.status_code == 200


def test_requests_are_private(client, make_applicant, lease_plot):
    owner = make_applicant()
    other = make_applicant()
    investment = _request(owner, [lease_plot])
    login(client, other)
    for name in (
        "portal:investment_request",
        "portal:investment_request_attachment",
    ):
        assert client.get(reverse(name, args=[investment.number])).status_code == 404
    for name in (
        "portal:investment_request_accept",
        "portal:investment_request_decline",
        "portal:investment_request_cancel",
    ):
        assert client.post(reverse(name, args=[investment.number])).status_code == 404
    assert (
        list(client.get(reverse("portal:investment_requests")).context["requests"])
        == []
    )


def test_messages_both_ways(client, applicant, officer, lease_plot):
    investment = _request(applicant, [lease_plot])
    login(client, applicant)
    url = reverse("portal:investment_request", args=[investment.number])
    mail.outbox.clear()
    response = client.post(url, {"body": "Apakah bisa kunjungan lapangan?"})
    assert response.status_code == 302
    message = InvestmentMessage.objects.get()
    assert not message.from_officer and message.author == applicant.user
    assert officer.email in mail.outbox[-1].to
    # Balasan petugas lewat panel admin, dengan lampiran.
    client.force_login(officer)
    mail.outbox.clear()
    response = client.post(
        reverse("admin:alokasi_investmentrequest_message", args=[investment.pk]),
        {"body": "Bisa, Selasa pukul 10.00.", "attachment": pdf_file("peta.pdf")},
    )
    assert response.status_code == 302
    reply = InvestmentMessage.objects.get(from_officer=True)
    assert reply.attachment_name == "peta.pdf"
    assert applicant.user.email in mail.outbox[-1].to
    login(client, applicant)
    download = client.get(
        reverse(
            "portal:investment_message_attachment", args=[investment.number, reply.pk]
        )
    )
    assert download.status_code == 200


def test_message_rejected_when_closed(applicant, officer, lease_plot):
    investment = _request(applicant, [lease_plot])
    inv.reject(investment, officer, "Tidak sesuai arahan ruang")
    investment.refresh_from_db()
    with pytest.raises(ValidationError):
        inv.post_message(investment, applicant.user, "Halo", officer=False)


def test_save_toggle(client, applicant, lease_plot):
    login(client, applicant)
    url = reverse("portal:plot_save", args=[lease_plot.code])
    response = client.post(url, HTTP_X_REQUESTED_WITH="fetch")
    assert response.json() == {"saved": True, "code": lease_plot.code}
    assert SavedPlot.objects.filter(applicant=applicant).count() == 1
    saved_page = client.get(reverse("portal:investment_saved"))
    assert lease_plot.code in saved_page.content.decode()
    response = client.post(url, {"next": "https://jahat.example/"})
    assert response.status_code == 302
    assert response["Location"] == reverse("portal:plot_detail", args=[lease_plot.code])
    assert not SavedPlot.objects.exists()
    assert client.get(url).status_code == 405


def test_dashboard_shows_investment(client, applicant, officer, lease_plot):
    investment = _request(applicant, [lease_plot])
    inv.make_offer(
        investment,
        officer,
        scheme=enums.InvestmentScheme.LEASE,
        plot=lease_plot,
        area_m2=None,
        rate_per_m2_year=None,
        term_years=5,
        valid_until=timezone.localdate() + datetime.timedelta(days=7),
    )
    login(client, applicant)
    body = client.get(reverse("portal:dashboard")).content.decode()
    assert investment.number in body and "Penawaran menunggu jawaban" in body


# --------------------------------------------------------------------------
# Alur lengkap
# --------------------------------------------------------------------------


def test_lease_flow_marks_plot_leased(client, applicant, officer, lease_plot):
    investment = _request(applicant, [lease_plot])
    inv.start_review(investment, officer)
    investment.refresh_from_db()
    assert investment.status == IS.REVIEW and investment.assigned_to == officer
    inv.schedule_consultation(
        investment,
        officer,
        timezone.now() + datetime.timedelta(days=2),
        "Kantor layanan",
        "Bawa profil perusahaan",
    )
    investment.refresh_from_db()
    assert investment.status == IS.CONSULTATION
    inv.make_offer(
        investment,
        officer,
        scheme=enums.InvestmentScheme.LEASE,
        plot=lease_plot,
        area_m2=None,
        rate_per_m2_year=None,
        term_years=5,
        valid_until=timezone.localdate() + datetime.timedelta(days=14),
        note="Pembayaran per tahun di muka",
    )
    investment.refresh_from_db()
    assert investment.status == IS.OFFERED
    assert investment.offer_area_m2 == lease_plot.area_m2
    assert investment.offer_rate_per_m2_year == Decimal("5000")
    assert investment.offer_total == Decimal("250000000")

    login(client, applicant)
    detail = client.get(reverse("portal:investment_request", args=[investment.number]))
    assert b"Terima penawaran" in detail.content
    response = client.post(
        reverse("portal:investment_request_accept", args=[investment.number])
    )
    assert response.status_code == 302
    investment.refresh_from_db()
    assert investment.status == IS.ACCEPTED
    # Investor tidak dapat membatalkan setelah menerima penawaran.
    client.post(reverse("portal:investment_request_cancel", args=[investment.number]))
    investment.refresh_from_db()
    assert investment.status == IS.ACCEPTED

    with pytest.raises(ValidationError):
        inv.complete(investment, officer)  # nomor kontrak wajib
    inv.complete(investment, officer, contract_number="KS-001/2026")
    investment.refresh_from_db()
    lease_plot.refresh_from_db()
    assert investment.status == IS.COMPLETED and investment.closed_at
    assert lease_plot.status == enums.PlotStatus.LEASED
    assert list(investment.events.values_list("status", flat=True)) == [
        IS.SUBMITTED,
        IS.REVIEW,
        IS.CONSULTATION,
        IS.OFFERED,
        IS.ACCEPTED,
        IS.COMPLETED,
    ]
    # Lahan yang sudah disewa tidak lagi muncul sebagai pilihan.
    form = InvestmentRequestForm(_form_data(plots=[lease_plot.pk]))
    assert not form.is_valid()


def test_allocation_flow_creates_draft_application(applicant, officer, alloc_plot):
    investment = _request(
        applicant, [alloc_plot], scheme=enums.InvestmentScheme.ALLOCATION
    )
    with pytest.raises(ValidationError):
        inv.make_offer(
            investment,
            officer,
            scheme=enums.InvestmentScheme.ALLOCATION,
            plot=None,
            area_m2=None,
            rate_per_m2_year=None,
            term_years=None,
            valid_until=timezone.localdate(),
        )
    inv.make_offer(
        investment,
        officer,
        scheme=enums.InvestmentScheme.ALLOCATION,
        plot=alloc_plot,
        area_m2=None,
        rate_per_m2_year=None,
        term_years=None,
        valid_until=timezone.localdate(),
    )
    investment.refresh_from_db()
    assert investment.offer_term_years == alloc_plot.effective_term_years
    assert investment.offer_total == alloc_plot.uwt_total
    inv.accept_offer(investment, applicant.user)
    inv.complete(investment, officer, note="Silakan lengkapi dokumen")
    investment.refresh_from_db()
    application = investment.application
    assert investment.status == IS.COMPLETED
    assert application.status == enums.ApplicationStatus.DRAFT
    assert application.plot == alloc_plot and application.applicant == applicant
    assert application.investment_value == investment.investment_value
    assert application.workforce == 150


def test_decline_and_reoffer(applicant, officer, lease_plot):
    investment = _request(applicant, [lease_plot])
    offer = dict(
        scheme=enums.InvestmentScheme.LEASE,
        plot=lease_plot,
        area_m2=Decimal("5000"),
        rate_per_m2_year=Decimal("4500"),
        term_years=3,
        valid_until=timezone.localdate() + datetime.timedelta(days=3),
    )
    inv.make_offer(investment, officer, **offer)
    with pytest.raises(ValidationError):
        inv.decline_offer(investment, applicant.user, "  ")
    inv.decline_offer(investment, applicant.user, "Tarif terlalu tinggi")
    investment.refresh_from_db()
    assert investment.status == IS.REVIEW
    inv.make_offer(
        investment, officer, **{**offer, "rate_per_m2_year": Decimal("4000")}
    )
    investment.refresh_from_db()
    assert investment.status == IS.OFFERED
    assert investment.offer_rate_per_m2_year == Decimal("4000")


def test_expired_offer_cannot_be_accepted(applicant, officer, lease_plot):
    investment = _request(applicant, [lease_plot])
    inv.make_offer(
        investment,
        officer,
        scheme=enums.InvestmentScheme.LEASE,
        plot=lease_plot,
        area_m2=None,
        rate_per_m2_year=None,
        term_years=2,
        valid_until=timezone.localdate(),
    )
    InvestmentRequest.objects.filter(pk=investment.pk).update(
        offer_valid_until=timezone.localdate() - datetime.timedelta(days=1)
    )
    investment.refresh_from_db()
    assert investment.offer_expired and not investment.can_accept_offer
    with pytest.raises(ValidationError):
        inv.accept_offer(investment, applicant.user)


def test_offer_for_taken_plot_cannot_be_accepted(applicant, officer, lease_plot):
    investment = _request(applicant, [lease_plot])
    inv.make_offer(
        investment,
        officer,
        scheme=enums.InvestmentScheme.LEASE,
        plot=lease_plot,
        area_m2=None,
        rate_per_m2_year=None,
        term_years=2,
        valid_until=timezone.localdate(),
    )
    LandPlot.objects.filter(pk=lease_plot.pk).update(status=enums.PlotStatus.LEASED)
    with pytest.raises(ValidationError):
        inv.accept_offer(investment, applicant.user)


def test_huge_offer_total_is_rejected(applicant, officer, lease_plot):
    investment = _request(applicant, [lease_plot])
    with pytest.raises(ValidationError):
        inv.make_offer(
            investment,
            officer,
            scheme=enums.InvestmentScheme.PARTNERSHIP,
            plot=None,
            area_m2=Decimal("99999999"),
            rate_per_m2_year=Decimal("999999999999999999"),
            term_years=99,
            valid_until=timezone.localdate(),
        )


def test_invalid_transitions(applicant, officer, lease_plot):
    investment = _request(applicant, [lease_plot])
    with pytest.raises(ValidationError):
        inv.accept_offer(investment, applicant.user)
    with pytest.raises(ValidationError):
        inv.complete(investment, officer, contract_number="X")
    with pytest.raises(ValidationError):
        inv.reject(investment, officer, "")
    with pytest.raises(ValidationError):
        inv.schedule_consultation(
            investment, officer, timezone.now() - datetime.timedelta(hours=1), "Kantor"
        )
    inv.cancel(investment, applicant.user, "Batal rencana")
    investment.refresh_from_db()
    assert investment.status == IS.CANCELLED and investment.is_final
    for func in (
        lambda: inv.start_review(investment, officer),
        lambda: inv.reject(investment, officer, "x"),
        lambda: inv.cancel(investment, applicant.user),
    ):
        with pytest.raises(ValidationError):
            func()


# --------------------------------------------------------------------------
# Panel petugas & hak akses
# --------------------------------------------------------------------------


def test_officer_admin_pages(client, applicant, officer, lease_plot, zone):
    investment = _request(
        applicant, [lease_plot], requested_area_geojson=SQUARE_GEOJSON
    )
    InvestmentMessage.objects.create(
        request=investment, body="Halo", author=applicant.user
    )
    client.force_login(officer)
    for name in ("investmentrequest", "investmentsector", "investmentzone", "landplot"):
        assert (
            client.get(reverse(f"admin:alokasi_{name}_changelist")).status_code == 200
        )
    change = client.get(
        reverse("admin:alokasi_investmentrequest_change", args=[investment.pk])
    )
    assert change.status_code == 200
    body = change.content.decode()
    assert "Mulai tinjau" in body and "Kirim penawaran" in body and "Halo" in body
    assert 'id="inv-reply-form"' in body
    for name in ("investmentzone", "investmentsector"):
        obj = zone if name == "investmentzone" else lease_plot.sector
        url = reverse(f"admin:alokasi_{name}_change", args=[obj.pk])
        assert client.get(url).status_code == 200
    assert (
        client.get(
            reverse("admin:alokasi_landplot_change", args=[lease_plot.pk])
        ).status_code
        == 200
    )
    for action in ("tinjau", "konsultasi", "penawaran", "selesaikan", "tolak"):
        url = reverse(
            "admin:alokasi_investmentrequest_process", args=[investment.pk, action]
        )
        assert client.get(url).status_code == 200, action
    # Assign & catatan internal dapat diedit; isian investor tidak.
    response = client.post(
        reverse("admin:alokasi_investmentrequest_change", args=[investment.pk]),
        {
            "assigned_to": officer.pk,
            "internal_note": "Prioritas",
            "project_name": "Diubah petugas",
            "events-TOTAL_FORMS": "0",
            "events-INITIAL_FORMS": "0",
        },
    )
    assert response.status_code == 302
    investment.refresh_from_db()
    assert investment.internal_note == "Prioritas"
    assert investment.project_name == "Pabrik Panel Surya"


def test_officer_process_through_admin(client, applicant, officer, lease_plot):
    investment = _request(applicant, [lease_plot])
    client.force_login(officer)
    process = lambda action: reverse(  # noqa: E731
        "admin:alokasi_investmentrequest_process", args=[investment.pk, action]
    )
    assert client.post(process("tinjau"), {"note": ""}).status_code == 302
    when = (timezone.localtime() + datetime.timedelta(days=1)).strftime(
        "%Y-%m-%dT%H:%M"
    )
    assert (
        client.post(
            process("konsultasi"), {"meeting_at": when, "place": "Kantor"}
        ).status_code
        == 302
    )
    valid = (timezone.localdate() + datetime.timedelta(days=10)).isoformat()
    response = client.post(
        process("penawaran"),
        {
            "scheme": "sewa",
            "plot": lease_plot.pk,
            "term_years": "3",
            "valid_until": valid,
        },
    )
    assert response.status_code == 302
    investment.refresh_from_db()
    assert investment.status == IS.OFFERED
    # Gagal di layanan (skema alokasi tanpa lahan alokasi) → formulir tampil lagi.
    response = client.post(
        process("penawaran"), {"scheme": "alokasi", "plot": "", "valid_until": valid}
    )
    assert response.status_code == 200
    inv.accept_offer(investment, applicant.user)
    response = client.post(process("selesaikan"), {"contract_number": "KS-9"})
    assert response.status_code == 302
    investment.refresh_from_db()
    assert investment.status == IS.COMPLETED and investment.contract_number == "KS-9"


def test_verifier_reads_but_cannot_process(client, applicant, verifier, lease_plot):
    investment = _request(applicant, [lease_plot])
    client.force_login(verifier)
    change = client.get(
        reverse("admin:alokasi_investmentrequest_change", args=[investment.pk])
    )
    assert change.status_code == 200
    assert "Mulai tinjau" not in change.content.decode()
    for action in ("tinjau", "tolak"):
        url = reverse(
            "admin:alokasi_investmentrequest_process", args=[investment.pk, action]
        )
        assert client.post(url, {"note": "x"}).status_code == 403
    url = reverse("admin:alokasi_investmentrequest_message", args=[investment.pk])
    assert client.post(url, {"body": "x"}).status_code == 403
    assert client.get(reverse("admin:alokasi_investmentsector_add")).status_code == 403
    investment.refresh_from_db()
    assert investment.status == IS.SUBMITTED


def test_other_staff_cannot_open_investment_admin(
    client, make_officer, applicant, lease_plot
):
    investment = _request(applicant, [lease_plot])
    asset_officer = make_officer("aset", UserGroup.PETUGAS_ASET)
    client.force_login(asset_officer)
    url = reverse("admin:alokasi_investmentrequest_change", args=[investment.pk])
    assert client.get(url).status_code in (302, 403)
    url = reverse(
        "admin:alokasi_investmentrequest_process", args=[investment.pk, "tinjau"]
    )
    assert client.post(url, {"note": ""}).status_code in (302, 403)


def test_officer_file_download(client, applicant, officer, lease_plot):
    form = InvestmentRequestForm(
        _form_data(plots=[lease_plot.pk]), {"attachment": pdf_file("profil.pdf")}
    )
    assert form.is_valid(), form.errors
    investment = inv.submit_request(applicant, form)
    client.force_login(officer)
    response = client.get(
        reverse("alokasi-officer-file", args=["investasi", investment.pk])
    )
    assert response.status_code == 200
    assert "profil.pdf" in response["Content-Disposition"]


def test_events_logged_with_actor(applicant, officer, lease_plot):
    investment = _request(applicant, [lease_plot])
    inv.start_review(investment, officer, "Mulai")
    event = InvestmentEvent.objects.filter(request=investment).last()
    assert event.actor == officer and event.note == "Mulai"


# --------------------------------------------------------------------------
# Data contoh
# --------------------------------------------------------------------------


def test_sample_data_idempotent_and_removable(seeded, applicant):
    call_command("alokasi_contoh_rempang", verbosity=0)
    call_command("alokasi_contoh_rempang", verbosity=0)
    plots = LandPlot.objects.filter(code__startswith="CONTOH-RMP-")
    assert plots.count() == 8
    assert plots.filter(offer_lease=True).exists()
    assert InvestmentZone.objects.filter(slug__startswith="contoh-").count() == 2
    kept = plots.get(code="CONTOH-RMP-07")
    _request(applicant, [kept])
    call_command("alokasi_contoh_rempang", "--hapus", verbosity=0)
    assert list(LandPlot.objects.filter(code__startswith="CONTOH-RMP-")) == [kept]
    assert not InvestmentZone.objects.filter(slug__startswith="contoh-").exists()


def test_status_emails_sent_after_commit(
    applicant, officer, lease_plot, django_capture_on_commit_callbacks
):
    investment = _request(applicant, [lease_plot])
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        inv.reject(investment, officer, "Lokasi tidak sesuai RTRW")
    assert mail.outbox and applicant.user.email in mail.outbox[-1].to
    assert "Lokasi tidak sesuai RTRW" in mail.outbox[-1].body
