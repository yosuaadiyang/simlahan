import datetime
from decimal import Decimal

import pytest
from django.core import mail
from django.core.exceptions import ValidationError

from alokasi import enums, services
from alokasi.models import Allocation, Application, Invoice, IssuedDocument

from .conftest import pdf_file, score_all

S = enums.ApplicationStatus


def approve_and_pay(application, officer, verifier):
    services.start_verification(application, officer)
    if application.is_allocation:
        score_all(application, verifier, 80)
    services.approve(application, officer, "Memenuhi syarat.")
    for invoice in Invoice.objects.filter(application=application):
        services.upload_payment_proof(
            invoice, pdf_file("bukti.pdf"), application.applicant.user
        )
        services.verify_payment(invoice, officer)
    application.refresh_from_db()
    return application


def test_full_allocation_flow(filled_application, officer, verifier, seeded):
    application = filled_application
    plot = application.plot
    services.submit(application, application.applicant.user)
    application.refresh_from_db()
    plot.refresh_from_db()
    assert application.status == S.SUBMITTED
    assert application.submitted_at is not None
    assert plot.status == enums.PlotStatus.RESERVED

    services.start_verification(application, officer)
    with pytest.raises(ValidationError, match="Semua kriteria"):
        services.approve(application, officer)

    score_all(application, verifier, 80)
    services.approve(application, officer, "Memenuhi syarat.")
    application.refresh_from_db()
    assert application.status == S.APPROVED
    assert application.score == Decimal("80.00")

    invoices = {i.kind: i for i in application.invoices.all()}
    # UWT = 10.000 m² × Rp1.000 × 30 tahun
    assert invoices[enums.InvoiceKind.UWT].amount == Decimal("300000000")
    assert invoices[enums.InvoiceKind.ALLOCATION_FEE].amount == Decimal("2500000")
    assert invoices[
        enums.InvoiceKind.UWT
    ].due_date == datetime.date.today() + datetime.timedelta(days=30)

    uwt = invoices[enums.InvoiceKind.UWT]
    services.upload_payment_proof(
        uwt, pdf_file("bukti.pdf"), application.applicant.user
    )
    services.verify_payment(uwt, officer)
    application.refresh_from_db()
    assert application.status == S.APPROVED  # masih ada tagihan administrasi

    fee = invoices[enums.InvoiceKind.ALLOCATION_FEE]
    services.verify_payment(
        fee, officer
    )  # petugas boleh memverifikasi pembayaran tanpa unggahan
    application.refresh_from_db()
    assert application.status == S.ISSUED

    allocation = Allocation.objects.get(application=application)
    plot.refresh_from_db()
    assert plot.status == enums.PlotStatus.ALLOCATED
    assert allocation.holder == application.applicant
    assert allocation.kpt_number.startswith("KPT-")
    assert allocation.ppt_number.startswith("PPT-")
    assert allocation.end_date == allocation.start_date.replace(
        year=allocation.start_date.year + 30
    ) - datetime.timedelta(days=1)
    docs = {d.kind: d for d in IssuedDocument.objects.filter(allocation=allocation)}
    assert set(docs) == {"kpt", "ppt"}
    for doc in docs.values():
        with doc.file.open("rb") as fh:
            assert fh.read(5) == b"%PDF-"
    subjects = [m.subject for m in mail.outbox]
    assert any("Dokumen permohonan" in s for s in subjects)
    assert list(application.events.values_list("status", flat=True)) == [
        S.DRAFT,
        S.SUBMITTED,
        S.VERIFYING,
        S.APPROVED,
        S.PAID,
        S.ISSUED,
    ]


def test_submit_requires_data_and_documents(applicant, plot):
    application = services.create_allocation_application(applicant, plot)
    with pytest.raises(ValidationError) as excinfo:
        services.submit(application, applicant.user)
    messages = " ".join(excinfo.value.messages)
    assert "Nilai investasi wajib diisi" in messages
    assert "Dokumen wajib belum diunggah" in messages


def test_create_application_is_idempotent_per_plot(applicant, plot):
    first = services.create_allocation_application(applicant, plot)
    second = services.create_allocation_application(applicant, plot)
    assert first.pk == second.pk


def test_plot_cannot_be_reserved_twice(
    filled_application, make_applicant, upload_required_docs
):
    services.submit(filled_application, filled_application.applicant.user)
    other = make_applicant()
    with pytest.raises(ValidationError, match="tidak tersedia"):
        services.create_allocation_application(other, filled_application.plot)


def test_low_score_cannot_be_approved(filled_application, officer, verifier):
    services.submit(filled_application, filled_application.applicant.user)
    services.start_verification(filled_application, officer)
    score_all(filled_application, verifier, 50)
    with pytest.raises(ValidationError, match="di bawah nilai minimum"):
        services.approve(filled_application, officer)


def test_score_is_weighted_average_of_verifiers(
    filled_application, officer, verifier, make_officer
):
    from utils.group_permissions import UserGroup

    second = make_officer("verifikator2", UserGroup.TIM_VERIFIKASI)
    score_all(filled_application, verifier, 70)
    score_all(filled_application, second, 90)
    assert filled_application.compute_score() == Decimal("80.00")


def test_revision_and_resubmission(filled_application, officer):
    application = filled_application
    services.submit(application, application.applicant.user)
    with pytest.raises(ValidationError):
        services.request_revision(application, officer, "  ")
    services.request_revision(application, officer, "Perbaiki rencana tapak.")
    application.refresh_from_db()
    assert application.status == S.REVISION
    assert application.is_editable
    services.submit(application, application.applicant.user)
    application.refresh_from_db()
    assert application.status == S.SUBMITTED
    assert application.events.last().note == "Diajukan ulang setelah perbaikan."


def test_reject_releases_plot(filled_application, officer):
    services.submit(filled_application, filled_application.applicant.user)
    services.reject(filled_application, officer, "Tidak sesuai peruntukan.")
    filled_application.plot.refresh_from_db()
    assert filled_application.plot.status == enums.PlotStatus.AVAILABLE
    assert "Tidak sesuai peruntukan." in mail.outbox[-1].body


def test_cancel_releases_plot(filled_application):
    services.submit(filled_application, filled_application.applicant.user)
    services.cancel(filled_application, filled_application.applicant.user)
    filled_application.plot.refresh_from_db()
    assert filled_application.plot.status == enums.PlotStatus.AVAILABLE
    with pytest.raises(ValidationError):
        services.cancel(filled_application, filled_application.applicant.user)


def test_rejected_payment_proof_returns_to_unpaid(
    filled_application, officer, verifier
):
    services.submit(filled_application, filled_application.applicant.user)
    services.start_verification(filled_application, officer)
    score_all(filled_application, verifier, 90)
    services.approve(filled_application, officer)
    invoice = filled_application.invoices.first()
    services.upload_payment_proof(
        invoice, pdf_file(), filled_application.applicant.user
    )
    services.reject_payment(invoice, officer, "Nominal tidak sesuai.")
    invoice.refresh_from_db()
    assert invoice.status == enums.InvoiceStatus.UNPAID
    assert invoice.note == "Nominal tidak sesuai."


def test_payment_proof_rejects_bad_extension(filled_application, officer, verifier):
    from django.core.files.uploadedfile import SimpleUploadedFile

    services.submit(filled_application, filled_application.applicant.user)
    services.start_verification(filled_application, officer)
    score_all(filled_application, verifier, 90)
    services.approve(filled_application, officer)
    invoice = filled_application.invoices.first()
    with pytest.raises(ValidationError):
        services.upload_payment_proof(
            invoice,
            SimpleUploadedFile("x.exe", b"MZ"),
            filled_application.applicant.user,
        )


def test_free_plot_issues_documents_on_approval(
    make_plot, applicant, upload_required_docs, officer, verifier, seeded
):
    seeded.allocation_admin_fee = 0
    seeded.save()
    plot = make_plot(uwt_rate_per_m2_year=0)
    application = services.create_allocation_application(applicant, plot)
    Application.objects.filter(pk=application.pk).update(
        activity="Fasilitas umum",
        investment_value=1,
        workforce=1,
        development_months=1,
        description="x",
    )
    application.refresh_from_db()
    upload_required_docs(application)
    services.submit(application, applicant.user)
    services.start_verification(application, officer)
    score_all(application, verifier, 75)
    services.approve(application, officer)
    application.refresh_from_db()
    assert application.status == S.ISSUED
    assert not application.invoices.exists()


def test_transfer_flow(
    filled_application, officer, verifier, make_applicant, upload_required_docs
):
    application = filled_application
    services.submit(application, application.applicant.user)
    approve_and_pay(application, officer, verifier)
    allocation = application.allocation
    holder = application.applicant
    recipient = make_applicant(name="PT Penerima")

    with pytest.raises(ValidationError):
        services.create_transfer_application(
            recipient, allocation, holder, "bukan pemegang"
        )
    with pytest.raises(ValidationError):
        services.create_transfer_application(holder, allocation, holder, "diri sendiri")

    transfer = services.create_transfer_application(
        holder, allocation, recipient, "Jual beli"
    )
    assert transfer.number.startswith("PRL-")
    with pytest.raises(ValidationError, match="Masih ada"):
        services.create_transfer_application(holder, allocation, recipient, "lagi")
    upload_required_docs(transfer)
    services.submit(transfer, holder.user)
    transfer = approve_and_pay(transfer, officer, verifier)
    assert transfer.status == S.ISSUED

    fee = transfer.invoices.get()
    assert fee.kind == enums.InvoiceKind.TRANSFER_FEE
    assert fee.amount == Decimal("1000000") + Decimal("100") * allocation.area_m2

    allocation.refresh_from_db()
    assert allocation.holder == recipient
    iph = transfer.issued_documents.get()
    assert iph.kind == "iph" and iph.number.startswith("IPH-")
    assert iph.holder_name == "PT Penerima"
    assert any("Peralihan hak" in m.subject for m in mail.outbox)


def test_revoke_allocation(filled_application, officer, verifier):
    services.submit(filled_application, filled_application.applicant.user)
    approve_and_pay(filled_application, officer, verifier)
    allocation = filled_application.allocation
    with pytest.raises(ValidationError):
        services.revoke_allocation(allocation, officer, "")
    services.revoke_allocation(allocation, officer, "Lahan tidur.")
    allocation.refresh_from_db()
    allocation.plot.refresh_from_db()
    assert allocation.status == enums.AllocationStatus.REVOKED
    assert allocation.plot.status == enums.PlotStatus.AVAILABLE
    assert allocation.plot.is_published is False


def test_numbers_are_sequential(applicant, make_plot):
    first = services.create_allocation_application(applicant, make_plot())
    second = services.create_allocation_application(applicant, make_plot())
    year = datetime.date.today().year
    assert first.number == f"ALK-{year}-00001"
    assert second.number == f"ALK-{year}-00002"
