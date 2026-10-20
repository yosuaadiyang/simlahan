import re
from urllib.parse import urlparse

import pytest
from django.core import mail
from django.core.cache import cache
from django.urls import reverse

from alokasi import enums, services
from alokasi.models import (
    Applicant,
    Application,
    ApplicationDocument,
    InfoPage,
    RequirementDocType,
)

from .conftest import PASSWORD, pdf_file
from .test_workflow import approve_and_pay

S = enums.ApplicationStatus


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def login(client, applicant):
    assert client.login(username=applicant.user.username, password=PASSWORD)
    return client


# --------------------------------------------------------------------------
# Halaman publik
# --------------------------------------------------------------------------


def test_public_pages(client, plot, seeded):
    InfoPage.objects.create(
        category="tutorial",
        title="Cara daftar",
        video_url="https://youtu.be/dQw4w9WgXcQ",
    )
    for name, args in (
        ("portal:home", []),
        ("portal:plot_list", []),
        ("portal:plot_detail", [plot.code]),
        ("portal:services", []),
        ("portal:info_index", []),
        ("portal:info_category", ["regulasi"]),
        ("portal:info_detail", ["tahapan-permohonan-alokasi-tanah"]),
        ("portal:verify", []),
        ("portal:register", []),
        ("portal:login", []),
        ("portal:password_reset", []),
        ("portal:resend_activation", []),
    ):
        response = client.get(reverse(name, args=args))
        assert response.status_code == 200, name
    home = client.get(reverse("portal:home")).content.decode()
    assert "youtube-nocookie.com/embed/dQw4w9WgXcQ" in home
    assert (
        client.get(reverse("portal:info_category", args=["bukan"])).status_code == 404
    )


def test_plot_list_filters_and_geojson(client, make_plot):
    a = make_plot(
        name="Kavling Pariwisata",
        allocation_type=enums.AllocationType.OPEN,
        district="Galang",
    )
    b = make_plot(name="Kavling Industri", district="Bulang")
    make_plot(name="Tersembunyi", is_published=False)
    page = client.get(
        reverse("portal:plot_list"), {"jenis": "terbuka"}
    ).content.decode()
    assert a.code in page and b.code not in page and "Tersembunyi" not in page
    data = client.get(reverse("portal:plot_geojson"), {"kecamatan": "Bulang"}).json()
    assert data["type"] == "FeatureCollection"
    assert [f["properties"]["code"] for f in data["features"]] == [b.code]
    assert data["features"][0]["geometry"]["type"] == "MultiPolygon"


def test_unpublished_plot_hidden(client, make_plot):
    plot = make_plot(is_published=False)
    assert (
        client.get(reverse("portal:plot_detail", args=[plot.code])).status_code == 404
    )


def test_verify_document(client, filled_application, officer, verifier):
    services.submit(filled_application, filled_application.applicant.user)
    approve_and_pay(filled_application, officer, verifier)
    doc = filled_application.issued_documents.get(kind="kpt")
    response = client.get(reverse("portal:verify_token", args=[doc.token]))
    assert response.status_code == 200
    assert doc.number in response.content.decode()
    response = client.get(reverse("portal:verify"), {"code": str(doc.token)})
    assert doc.number in response.content.decode()
    missing = client.get(
        reverse("portal:verify"), {"code": "00000000-0000-0000-0000-000000000000"}
    )
    assert missing.status_code == 404


# --------------------------------------------------------------------------
# Akun
# --------------------------------------------------------------------------


def registration_data(**kwargs):
    data = {
        "email": "Baru@Contoh.id",
        "password1": "SandiSangatKuat#2026",
        "password2": "SandiSangatKuat#2026",
        "applicant_type": "badan_usaha",
        "name": "PT Baru",
        "nib": "1234567890123",
        "npwp": "",
        "nik": "2171010101900001",
        "pic_name": "Budi",
        "pic_position": "Direktur",
        "phone": "08123",
        "address": "Batam",
        "city": "Batam",
        "agree": "on",
    }
    data.update(kwargs)
    return data


def test_register_activate_login(client, seeded):
    response = client.post(reverse("portal:register"), registration_data())
    assert response.status_code == 200
    applicant = Applicant.objects.get(name="PT Baru")
    user = applicant.user
    assert user.email == "baru@contoh.id" and not user.is_active
    assert applicant.nik == "2171010101900001"
    assert user.groups.count() == 0

    assert not client.login(username="baru@contoh.id", password="SandiSangatKuat#2026")
    # Akun belum aktif: pesan aktivasi, bukan "sandi salah" (sandi benar saja).
    response = client.post(
        reverse("portal:login"),
        {"username": "baru@contoh.id", "password": "SandiSangatKuat#2026"},
    )
    assert "belum diaktifkan" in response.content.decode()
    response = client.post(
        reverse("portal:login"),
        {"username": "baru@contoh.id", "password": "SandiSalah#2026"},
    )
    assert "Surel atau kata sandi salah" in response.content.decode()
    link = re.search(r"https?://\S+/portal/aktivasi/\S+/", mail.outbox[-1].body).group(
        0
    )
    path = urlparse(link).path
    assert client.get(path).status_code == 302
    user.refresh_from_db()
    assert user.is_active
    # Tautan sekali pakai.
    assert client.get(path).status_code == 400

    response = client.post(
        reverse("portal:login"),
        {"username": "BARU@contoh.id", "password": "SandiSangatKuat#2026"},
    )
    assert response.status_code == 302 and response.url == reverse("portal:dashboard")
    assert client.get(reverse("portal:dashboard")).status_code == 200


def test_register_validation(client, applicant):
    response = client.post(
        reverse("portal:register"),
        registration_data(
            email=applicant.user.email, nib="", password2="beda", nik="123"
        ),
    )
    form = response.context["form"]
    assert "email" in form.errors
    assert "nib" in form.errors
    assert "password2" in form.errors
    assert "nik" in form.errors


def test_officer_cannot_use_portal_login(client, officer):
    response = client.post(
        reverse("portal:login"), {"username": officer.email, "password": PASSWORD}
    )
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session
    # Petugas yang nama penggunanya berupa surel pun ditolak.
    officer.username = officer.email
    officer.save()
    response = client.post(
        reverse("portal:login"), {"username": officer.email, "password": PASSWORD}
    )
    assert "bukan akun pemohon" in response.content.decode()
    assert "_auth_user_id" not in client.session


def test_login_is_throttled(client, seeded):
    for _ in range(10):
        client.post(
            reverse("portal:login"), {"username": "x@y.id", "password": "salah"}
        )
    assert (
        client.post(
            reverse("portal:login"), {"username": "x@y.id", "password": "salah"}
        ).status_code
        == 429
    )


@pytest.mark.parametrize(
    "hops,chain",
    [
        # Compose saja: nginx kontainer menambahkan alamat klien.
        (1, "{ip}"),
        # nginx host (TLS) -> nginx kontainer: entri terakhir = gateway docker.
        (2, "{ip}, 172.18.0.1"),
    ],
)
def test_throttle_per_visitor_behind_proxy(client, seeded, settings, hops, chain):
    # Di belakang proxy semua permintaan datang dari alamat proxy; kuota harus
    # tetap per pengunjung.
    settings.TRUST_PROXY_HEADERS = True
    settings.TRUSTED_PROXY_COUNT = hops
    data = {"username": "x@y.id", "password": "salah"}
    url = reverse("portal:login")

    def post(ip, prefix=""):
        forwarded = prefix + chain.format(ip=ip)
        return client.post(url, data, HTTP_X_FORWARDED_FOR=forwarded).status_code

    for _ in range(10):
        assert post("203.0.113.5") == 200
    assert post("203.0.113.5") == 429
    # Alamat palsu di depan rantai tidak bisa dipakai untuk mengelak.
    assert post("203.0.113.5", prefix="198.51.100.1, ") == 429
    # Pengunjung lain tidak ikut terblokir.
    assert post("203.0.113.9") == 200


def test_client_ip_hop_count_bounds(rf, settings):
    from alokasi.views import _client_ip

    request = rf.get("/", HTTP_X_FORWARDED_FOR="203.0.113.5", REMOTE_ADDR="10.0.0.2")
    settings.TRUST_PROXY_HEADERS = True
    settings.TRUSTED_PROXY_COUNT = 3
    assert _client_ip(request) == "203.0.113.5"
    settings.TRUSTED_PROXY_COUNT = 0
    assert _client_ip(request) == "203.0.113.5"
    assert _client_ip(rf.get("/", REMOTE_ADDR="10.0.0.2")) == "10.0.0.2"
    settings.TRUST_PROXY_HEADERS = False
    assert _client_ip(request) == "10.0.0.2"


def test_email_links_use_public_url(client, seeded, applicant, settings):
    # Tautan surel memakai alamat publik, bukan Host dari proxy (port hilang).
    settings.OFFICER_UI_URL = "https://lahan.contoh.go.id"
    client.post(reverse("portal:register"), registration_data())
    assert "https://lahan.contoh.go.id/portal/aktivasi/" in mail.outbox[-1].body
    client.post(reverse("portal:password_reset"), {"email": applicant.user.email})
    assert "https://lahan.contoh.go.id/portal/atur-sandi/" in mail.outbox[-1].body


def test_password_reset_only_for_applicants(client, applicant, officer):
    client.post(reverse("portal:password_reset"), {"email": officer.email})
    assert len(mail.outbox) == 0
    client.post(reverse("portal:password_reset"), {"email": applicant.user.email})
    assert len(mail.outbox) == 1
    assert "/portal/atur-sandi/" in mail.outbox[0].body


def test_applicant_isolated_from_officer_app(client, applicant):
    login(client, applicant)
    assert client.get("/v1/auth/me/").status_code == 403
    response = client.get("/admin/")
    assert response.status_code == 302 and response.url == reverse("portal:dashboard")


def test_applicant_jwt_login_rejected(client, applicant):
    response = client.post(
        "/v1/auth/login/",
        {"username": applicant.user.username, "password": PASSWORD},
        content_type="application/json",
    )
    assert response.status_code == 403


def test_officer_sees_notice_on_applicant_pages(client, officer):
    client.force_login(officer)
    assert client.get(reverse("portal:dashboard")).status_code == 403


def test_profile_update(client, applicant):
    login(client, applicant)
    data = {
        "applicant_type": "badan_usaha",
        "name": "PT Contoh Baru",
        "nib": "999",
        "npwp": "",
        "nik": "",
        "pic_name": "Siti",
        "pic_position": "",
        "phone": "0778",
        "address": "Batam Centre",
        "city": "Batam",
    }
    assert client.post(reverse("portal:profile"), data).status_code == 302
    applicant.refresh_from_db()
    assert applicant.name == "PT Contoh Baru"
    assert applicant.user.first_name == "Siti"


# --------------------------------------------------------------------------
# Permohonan lewat portal
# --------------------------------------------------------------------------


def test_application_via_portal(client, applicant, plot):
    login(client, applicant)
    response = client.post(reverse("portal:application_create", args=[plot.code]))
    application = Application.objects.get(applicant=applicant)
    assert response.url == reverse(
        "portal:application_detail", args=[application.number]
    )
    detail = reverse("portal:application_detail", args=[application.number])
    assert client.get(detail).status_code == 200

    response = client.post(
        reverse("portal:application_edit", args=[application.number]),
        {
            "activity": "Gudang logistik",
            "investment_value": "1500000000",
            "workforce": "40",
            "development_months": "18",
            "description": "Gudang dan kantor.",
        },
    )
    assert response.status_code == 302

    # Unggah berkas yang tidak diizinkan ditolak.
    doc_type = (
        RequirementDocType.for_application(application).filter(is_required=True).first()
    )
    from django.core.files.uploadedfile import SimpleUploadedFile

    client.post(
        reverse("portal:document_upload", args=[application.number]),
        {"doc_type": doc_type.pk, "file": SimpleUploadedFile("virus.exe", b"MZ")},
    )
    assert not application.documents.exists()

    for doc_type in RequirementDocType.for_application(application).filter(
        is_required=True
    ):
        client.post(
            reverse("portal:document_upload", args=[application.number]),
            {"doc_type": doc_type.pk, "file": pdf_file("syarat.pdf")},
        )
    assert (
        application.documents.count()
        == RequirementDocType.for_application(application)
        .filter(is_required=True)
        .count()
    )
    document = application.documents.first()
    download = client.get(
        reverse("portal:document_download", args=[application.number, document.pk])
    )
    assert download.status_code == 200
    assert b"".join(download.streaming_content).startswith(b"%PDF")

    client.post(reverse("portal:application_submit", args=[application.number]))
    application.refresh_from_db()
    assert application.status == S.SUBMITTED
    plot.refresh_from_db()
    assert plot.status == enums.PlotStatus.RESERVED

    # Setelah diajukan, dokumen tidak bisa dihapus/diubah.
    client.post(
        reverse("portal:document_delete", args=[application.number, document.pk])
    )
    assert ApplicationDocument.objects.filter(pk=document.pk).exists()
    assert (
        client.get(
            reverse("portal:application_edit", args=[application.number])
        ).status_code
        == 302
    )

    client.post(reverse("portal:application_cancel", args=[application.number]))
    application.refresh_from_db()
    assert application.status == S.CANCELLED


def test_other_applicant_cannot_access(client, filled_application, make_applicant):
    other = make_applicant()
    login(client, other)
    number = filled_application.number
    document = filled_application.documents.first()
    assert (
        client.get(reverse("portal:application_detail", args=[number])).status_code
        == 404
    )
    assert (
        client.get(
            reverse("portal:document_download", args=[number, document.pk])
        ).status_code
        == 404
    )
    assert (
        client.post(reverse("portal:application_submit", args=[number])).status_code
        == 404
    )
    assert (
        client.post(reverse("portal:application_cancel", args=[number])).status_code
        == 404
    )


def test_login_required(client, filled_application):
    response = client.get(
        reverse("portal:application_detail", args=[filled_application.number])
    )
    assert response.status_code == 302
    assert response.url.startswith(reverse("portal:login"))


def test_invoice_and_issued_documents(
    client, filled_application, officer, verifier, make_applicant
):
    application = filled_application
    services.submit(application, application.applicant.user)
    services.start_verification(application, officer)
    from .conftest import score_all

    score_all(application, verifier, 85)
    services.approve(application, officer)
    login(client, application.applicant)

    invoice = application.invoices.first()
    pdf = client.get(reverse("portal:invoice_pdf", args=[invoice.number]))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    response = client.post(
        reverse("portal:invoice_proof_upload", args=[invoice.number]),
        {"payment_proof": pdf_file("bukti.pdf")},
    )
    assert response.status_code == 302
    invoice.refresh_from_db()
    assert invoice.status == enums.InvoiceStatus.PROOF_UPLOADED
    assert (
        client.get(reverse("portal:invoice_proof", args=[invoice.number])).status_code
        == 200
    )

    for inv in application.invoices.all():
        services.verify_payment(inv, officer)
    application.refresh_from_db()
    assert application.status == S.ISSUED
    kpt = application.issued_documents.get(kind="kpt")
    response = client.get(reverse("portal:issued_download", args=[kpt.token]))
    assert response.status_code == 200
    assert b"".join(response.streaming_content).startswith(b"%PDF")

    other = make_applicant()
    client.logout()
    login(client, other)
    assert (
        client.get(reverse("portal:issued_download", args=[kpt.token])).status_code
        == 404
    )
    assert (
        client.get(reverse("portal:invoice_pdf", args=[invoice.number])).status_code
        == 404
    )


def test_allocation_reporting_and_transfer(
    client, filled_application, officer, verifier, make_applicant
):
    application = filled_application
    services.submit(application, application.applicant.user)
    approve_and_pay(application, officer, verifier)
    allocation = application.allocation
    login(client, application.applicant)
    url = reverse("portal:allocation_detail", args=[allocation.pk])
    page = client.get(url)
    assert page.status_code == 200
    assert "Batas memulai pembangunan" in page.content.decode()

    # Laporan izin: status terbit wajib nomor & tanggal.
    response = client.post(
        reverse("portal:permit_report_save", args=[allocation.pk]),
        {"izin-permit_type": "pkkpr", "izin-status": "terbit"},
    )
    assert not allocation.permit_reports.exists()
    # Galat ditampilkan pada formulir yang sama, isian tidak hilang.
    assert response.status_code == 200
    assert response.context["permit_form"].errors["permit_number"]
    assert response.context["permit_form"]["status"].value() == "terbit"
    client.post(
        reverse("portal:permit_report_save", args=[allocation.pk]),
        {
            "izin-permit_type": "pkkpr",
            "izin-status": "terbit",
            "izin-permit_number": "PKKPR-001",
            "izin-issued_date": "2026-10-01",
            "izin-document": pdf_file("pkkpr.pdf"),
        },
    )
    report = allocation.permit_reports.get()
    assert report.permit_number == "PKKPR-001"
    # Laporan jenis yang sama menggantikan laporan sebelumnya.
    client.post(
        reverse("portal:permit_report_save", args=[allocation.pk]),
        {"izin-permit_type": "pkkpr", "izin-status": "proses", "izin-note": "revisi"},
    )
    assert allocation.permit_reports.count() == 1
    assert (
        client.get(
            reverse("portal:permit_document", args=[allocation.pk, report.pk])
        ).status_code
        == 200
    )

    client.post(
        reverse("portal:development_report_create", args=[allocation.pk]),
        {
            "progres-report_date": "2026-10-10",
            "progres-stage": "konstruksi",
            "progres-progress_percent": "15",
            "progres-description": "Pondasi",
        },
    )
    assert allocation.development_reports.count() == 1
    assert allocation.has_started_development
    response = client.post(
        reverse("portal:development_report_create", args=[allocation.pk]),
        {
            "progres-report_date": "2026-10-10",
            "progres-stage": "konstruksi",
            "progres-progress_percent": "150",
            "progres-description": "x",
        },
    )
    assert allocation.development_reports.count() == 1
    assert response.status_code == 200
    form = response.context["development_form"]
    assert form.errors["progress_percent"] and form["stage"].value() == "konstruksi"

    recipient = make_applicant(name="PT Penerima")
    response = client.post(
        reverse("portal:transfer_create", args=[allocation.pk]),
        {"recipient_email": "tidak@ada.id", "transfer_reason": "Jual beli"},
    )
    assert "harus sudah memiliki akun" in response.content.decode()
    response = client.post(
        reverse("portal:transfer_create", args=[allocation.pk]),
        {
            "recipient_email": recipient.user.email.upper(),
            "transfer_reason": "Jual beli",
        },
    )
    transfer = Application.objects.get(service_type=enums.ServiceType.TRANSFER)
    assert response.url == reverse("portal:application_detail", args=[transfer.number])
    assert transfer.recipient == recipient

    # Penerima hak hanya melihat setelah diajukan.
    client.logout()
    login(client, recipient)
    assert (
        client.get(
            reverse("portal:application_detail", args=[transfer.number])
        ).status_code
        == 404
    )
    Application.objects.filter(pk=transfer.pk).update(status=S.SUBMITTED)
    assert (
        client.get(
            reverse("portal:application_detail", args=[transfer.number])
        ).status_code
        == 200
    )
    # Bukan pemegang: tidak bisa membuka alokasi.
    assert client.get(url).status_code == 404


def test_application_detail_shows_missing_documents(client, applicant, plot):
    application = services.create_allocation_application(applicant, plot)
    login(client, applicant)
    page = client.get(
        reverse("portal:application_detail", args=[application.number])
    ).content.decode()
    assert "Dokumen wajib belum diunggah" in page


def test_logout_by_typed_address_redirects_without_logging_out(client, applicant):
    login(client, applicant)
    response = client.get(reverse("portal:logout"))
    assert response.status_code == 302
    assert response.url == reverse("portal:home")
    assert client.get(reverse("portal:dashboard")).status_code == 200

    response = client.post(reverse("portal:logout"))
    assert response.status_code == 302
    assert client.get(reverse("portal:dashboard")).status_code == 302
