"""Alur kerja permohonan alokasi lahan dan peralihan hak.

Setiap perubahan status lewat fungsi di modul ini supaya aturan, riwayat
(ApplicationEvent), status lahan, dan notifikasi surel selalu konsisten.
"""

import datetime
import logging
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from alokasi import enums
from alokasi.models import (
    Allocation,
    AllocationSettings,
    Applicant,
    Application,
    ApplicationEvent,
    Invoice,
    IssuedDocument,
    LandPlot,
    _next_number,
)
from utils.money import check_fits

LOG = logging.getLogger(__name__)
S = enums.ApplicationStatus


# --------------------------------------------------------------------------
# Notifikasi
# --------------------------------------------------------------------------


def portal_url(path: str = "") -> str:
    base = (getattr(settings, "OFFICER_UI_URL", "") or "").rstrip("/")
    return (
        f"{base}/portal/{path.lstrip('/')}" if base else f"/portal/{path.lstrip('/')}"
    )


def send_email(recipients: list[str], subject: str, body: str) -> bool:
    """Kirim surel; kegagalan SMTP dicatat dan tidak menggagalkan proses."""
    recipients = [r for r in recipients if r]
    if not recipients:
        return False
    org = AllocationSettings.load().authority_short_name
    try:
        send_mail(
            subject=f"[{org}] {subject}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception:  # noqa: BLE001
        LOG.exception("Gagal mengirim surel ke %s", ", ".join(recipients))
        return False
    return True


def notify(applicant: Applicant | None, subject: str, body: str) -> None:
    if applicant is None:
        return
    send_email([applicant.user.email], subject, body)


def _notify_status(application: Application, note: str = "") -> None:
    lines = [
        _("Yth. %(name)s,") % {"name": application.applicant.name},
        "",
        _("Status permohonan %(number)s (%(service)s) kini: %(status)s.")
        % {
            "number": application.number,
            "service": application.get_service_type_display(),
            "status": application.get_status_display(),
        },
    ]
    if note:
        lines += ["", _("Catatan petugas:"), note]
    lines += [
        "",
        _("Lihat rincian: %s") % portal_url(f"permohonan/{application.number}/"),
    ]
    notify(
        application.applicant,
        _("Permohonan %(number)s: %(status)s")
        % {"number": application.number, "status": application.get_status_display()},
        "\n".join(lines),
    )


def _set_status(
    application: Application, status: str, actor=None, note: str = ""
) -> None:
    application.status = status
    application.save()
    ApplicationEvent.objects.create(
        application=application, status=status, note=note, actor=actor
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


# --------------------------------------------------------------------------
# Pemohon
# --------------------------------------------------------------------------


@transaction.atomic
def create_allocation_application(applicant: Applicant, plot: LandPlot) -> Application:
    plot = LandPlot.objects.select_for_update().get(pk=plot.pk)
    _require(
        plot.is_open_for_application, _("Lahan ini tidak tersedia untuk dimohonkan.")
    )
    existing = applicant.applications.filter(
        plot=plot, status__in=(S.DRAFT, S.SUBMITTED, S.VERIFYING, S.REVISION)
    ).first()
    if existing:
        return existing
    application = Application.objects.create(
        service_type=enums.ServiceType.ALLOCATION,
        applicant=applicant,
        plot=plot,
        activity=plot.intended_use,
    )
    ApplicationEvent.objects.create(
        application=application, status=S.DRAFT, actor=applicant.user
    )
    return application


@transaction.atomic
def create_service_application(
    applicant: Applicant, allocation: Allocation, service_type: str, reason: str
) -> Application:
    """Permohonan layanan atas alokasi sendiri: perpanjangan, pembaruan,
    pecah PL, atau pengukuran ulang."""
    allocation = Allocation.objects.select_for_update().get(pk=allocation.pk)
    _require(
        allocation.holder_id == applicant.pk, _("Anda bukan pemegang alokasi ini.")
    )
    if service_type == enums.ServiceType.RENEWAL:
        _require(
            allocation.status
            in (enums.AllocationStatus.ACTIVE, enums.AllocationStatus.EXPIRED),
            _("Hanya alokasi aktif atau yang sudah berakhir yang dapat diperbarui."),
        )
    else:
        _require(
            allocation.status == enums.AllocationStatus.ACTIVE,
            _("Hanya alokasi aktif yang dapat diajukan layanan ini."),
        )
    open_application = allocation.transfer_applications.exclude(
        status__in=enums.FINAL_STATUSES
    ).filter(applicant=applicant)
    _require(
        not open_application.exists(),
        _("Masih ada permohonan Anda untuk alokasi ini yang sedang diproses."),
    )
    application = Application.objects.create(
        service_type=service_type,
        applicant=applicant,
        source_allocation=allocation,
        transfer_reason=reason,
        activity=allocation.activity,
    )
    ApplicationEvent.objects.create(
        application=application, status=S.DRAFT, actor=applicant.user
    )
    return application


def _require_service_allocation(application: Application, allocation) -> None:
    """Layanan atas alokasi sendiri hanya boleh berlanjut selama alokasinya
    masih milik pemohon dan belum dicabut (perpanjangan yang terbit atas
    alokasi yang sudah dicabut akan menghidupkannya kembali)."""
    _require(
        allocation.holder_id == application.applicant_id
        and allocation.status
        in (enums.AllocationStatus.ACTIVE, enums.AllocationStatus.EXPIRED),
        _("Alokasi tidak lagi dapat diajukan layanan ini oleh pemohon ini."),
    )


@transaction.atomic
def create_transfer_application(
    applicant: Applicant, allocation: Allocation, recipient: Applicant, reason: str
) -> Application:
    allocation = Allocation.objects.select_for_update().get(pk=allocation.pk)
    _require(
        allocation.holder_id == applicant.pk, _("Anda bukan pemegang alokasi ini.")
    )
    _require(
        allocation.status == enums.AllocationStatus.ACTIVE,
        _("Hanya alokasi aktif yang dapat dialihkan."),
    )
    _require(
        recipient.pk != applicant.pk, _("Penerima hak tidak boleh pemohon sendiri.")
    )
    open_transfer = allocation.transfer_applications.exclude(
        status__in=enums.FINAL_STATUSES
    ).exists()
    _require(
        not open_transfer, _("Masih ada permohonan peralihan yang sedang diproses.")
    )
    application = Application.objects.create(
        service_type=enums.ServiceType.TRANSFER,
        applicant=applicant,
        source_allocation=allocation,
        recipient=recipient,
        transfer_reason=reason,
        activity=allocation.activity,
    )
    ApplicationEvent.objects.create(
        application=application, status=S.DRAFT, actor=applicant.user
    )
    return application


def validate_for_submission(application: Application) -> list[str]:
    errors = []
    if application.is_allocation:
        if not application.plot_id:
            errors.append(_("Lahan belum dipilih."))
        for field, label in (
            ("activity", _("Rencana kegiatan")),
            ("investment_value", _("Nilai investasi")),
            ("workforce", _("Rencana tenaga kerja")),
            ("development_months", _("Jangka waktu pembangunan")),
            ("description", _("Uraian rencana usaha")),
        ):
            if getattr(application, field) in (None, ""):
                errors.append(_("%s wajib diisi.") % label)
    else:
        if application.is_transfer and not application.recipient_id:
            errors.append(_("Penerima hak belum dipilih."))
        if not application.transfer_reason:
            errors.append(_("Alasan / uraian permohonan wajib diisi."))
    for doc in application.missing_required_documents():
        errors.append(_("Dokumen wajib belum diunggah: %s") % doc.name)
    return errors


@transaction.atomic
def submit(application: Application, user) -> Application:
    application = Application.objects.select_for_update().get(pk=application.pk)
    _require(application.is_editable, _("Permohonan ini tidak dapat diajukan lagi."))
    errors = validate_for_submission(application)
    if errors:
        raise ValidationError(errors)
    if application.is_allocation:
        plot = LandPlot.objects.select_for_update().get(pk=application.plot_id)
        reserved_by_other = plot.applications.exclude(pk=application.pk).filter(
            status__in=(S.SUBMITTED, S.VERIFYING, S.REVISION, S.APPROVED, S.PAID)
        )
        _require(
            not reserved_by_other.exists()
            and plot.status in (enums.PlotStatus.AVAILABLE, enums.PlotStatus.RESERVED),
            _("Lahan ini sedang dimohonkan pihak lain atau sudah tidak tersedia."),
        )
        _require(plot.is_published, _("Lahan ini tidak lagi ditawarkan."))
        plot.status = enums.PlotStatus.RESERVED
        plot.save(update_fields=["status", "modified_at"])
    else:
        allocation = application.source_allocation
        allowed_status = (enums.AllocationStatus.ACTIVE,)
        if application.service_type == enums.ServiceType.RENEWAL:
            # Pembaruan diajukan setelah jangka waktu alokasi berakhir.
            allowed_status += (enums.AllocationStatus.EXPIRED,)
        _require(
            allocation.status in allowed_status
            and allocation.holder_id == application.applicant_id,
            _("Alokasi tidak lagi dapat diajukan layanan ini oleh pemohon ini."),
        )
    resubmission = application.status == S.REVISION
    application.submitted_at = timezone.now()
    if application.is_transfer:
        # Data peralihan bisa berubah saat perbaikan, jadi penerima hak
        # menyetujui ulang setiap kali permohonan diajukan.
        application.recipient_accepted_at = None
    _set_status(
        application,
        S.SUBMITTED,
        actor=user,
        note=_("Diajukan ulang setelah perbaikan.") if resubmission else "",
    )
    _notify_status(application)
    if application.is_transfer:
        _notify_recipient_to_accept(application)
    return application


def _notify_recipient_to_accept(application: Application) -> None:
    notify(
        application.recipient,
        _("Persetujuan peralihan hak %s") % application.number,
        _(
            "%(holder)s mengajukan peralihan hak alokasi KPT %(kpt)s kepada Anda. "
            "Peralihan baru dapat diproses setelah Anda menyetujuinya di %(url)s"
        )
        % {
            "holder": application.applicant.name,
            "kpt": application.source_allocation.kpt_number,
            "url": portal_url(f"permohonan/{application.number}/"),
        },
    )


@transaction.atomic
def accept_transfer(
    application: Application, applicant: Applicant, user
) -> Application:
    """Penerima hak menyetujui peralihan yang diajukan kepadanya."""
    application = Application.objects.select_for_update().get(pk=application.pk)
    _require(
        application.is_transfer and application.recipient_id == applicant.pk,
        _("Hanya penerima hak yang dapat menyetujui peralihan ini."),
    )
    _require(
        application.status in (S.SUBMITTED, S.VERIFYING),
        _("Peralihan pada tahap ini tidak dapat disetujui."),
    )
    _require(
        application.recipient_accepted_at is None,
        _("Peralihan ini sudah Anda setujui."),
    )
    application.recipient_accepted_at = timezone.now()
    application.save(update_fields=["recipient_accepted_at", "modified_at"])
    ApplicationEvent.objects.create(
        application=application,
        status=application.status,
        note=_("Penerima hak %s menyetujui peralihan.") % applicant.name,
        actor=user,
    )
    return application


def _release_plot(application: Application) -> None:
    if not application.is_allocation or not application.plot_id:
        return
    plot = LandPlot.objects.select_for_update().get(pk=application.plot_id)
    still_reserved = plot.applications.exclude(pk=application.pk).filter(
        status__in=(S.SUBMITTED, S.VERIFYING, S.REVISION, S.APPROVED, S.PAID)
    )
    if plot.status == enums.PlotStatus.RESERVED and not still_reserved.exists():
        plot.status = enums.PlotStatus.AVAILABLE
        plot.save(update_fields=["status", "modified_at"])


@transaction.atomic
def cancel(application: Application, user, note: str = "") -> Application:
    application = Application.objects.select_for_update().get(pk=application.pk)
    _require(
        application.status in (S.DRAFT, S.SUBMITTED, S.REVISION),
        _("Permohonan pada tahap ini tidak dapat dibatalkan."),
    )
    was_submitted = application.status != S.DRAFT
    _set_status(application, S.CANCELLED, actor=user, note=note)
    if was_submitted:
        _release_plot(application)
    return application


# --------------------------------------------------------------------------
# Petugas
# --------------------------------------------------------------------------


@transaction.atomic
def start_verification(application: Application, officer) -> Application:
    application = Application.objects.select_for_update().get(pk=application.pk)
    _require(
        application.status == S.SUBMITTED, _("Hanya permohonan berstatus Diajukan.")
    )
    _set_status(application, S.VERIFYING, actor=officer)
    _notify_status(application)
    return application


@transaction.atomic
def request_revision(application: Application, officer, note: str) -> Application:
    application = Application.objects.select_for_update().get(pk=application.pk)
    _require(
        application.status in (S.SUBMITTED, S.VERIFYING),
        _("Perbaikan hanya dapat diminta saat permohonan diajukan atau diverifikasi."),
    )
    _require(bool(note.strip()), _("Tuliskan apa yang harus diperbaiki."))
    # Nilai verifikasi berlaku untuk data yang dinilai; setelah diperbaiki
    # pemohon, verifikator wajib menilai ulang.
    application.scores.all().delete()
    application.score = None
    application.officer_note = note
    _set_status(application, S.REVISION, actor=officer, note=note)
    _notify_status(application, note)
    return application


def refresh_score(application: Application) -> Decimal | None:
    application.score = application.compute_score()
    application.save(update_fields=["score", "modified_at"])
    return application.score


@transaction.atomic
def approve(application: Application, officer, note: str = "") -> Application:
    application = Application.objects.select_for_update().get(pk=application.pk)
    _require(
        application.status == S.VERIFYING,
        _("Hanya permohonan dalam verifikasi teknis."),
    )
    config = AllocationSettings.load()
    if application.is_allocation:
        score = refresh_score(application)
        _require(
            score is not None,
            _("Semua kriteria verifikasi teknis harus dinilai sebelum disetujui."),
        )
        _require(
            score >= config.passing_score,
            _("Nilai verifikasi %(score)s di bawah nilai minimum %(min)s.")
            % {"score": score, "min": config.passing_score},
        )
    elif application.is_transfer:
        _require(
            application.recipient_accepted_at is not None,
            _("Penerima hak belum menyetujui peralihan ini di portal."),
        )
    else:
        _require_service_allocation(application, application.source_allocation)
    application.decided_at = timezone.now()
    application.decided_by = officer
    if note:
        application.officer_note = note
    _set_status(application, S.APPROVED, actor=officer, note=note)
    _create_invoices(application, config)
    _notify_status(application, note)
    # Tanpa tagihan bernilai (mis. tarif 0) dokumen langsung diterbitkan.
    _maybe_complete_payment(application, officer)
    return application


@transaction.atomic
def reject(application: Application, officer, note: str) -> Application:
    application = Application.objects.select_for_update().get(pk=application.pk)
    _require(
        application.status in (S.SUBMITTED, S.VERIFYING, S.REVISION),
        _("Permohonan pada tahap ini tidak dapat ditolak."),
    )
    _require(bool(note.strip()), _("Alasan penolakan wajib diisi."))
    application.decided_at = timezone.now()
    application.decided_by = officer
    application.officer_note = note
    _set_status(application, S.REJECTED, actor=officer, note=note)
    _release_plot(application)
    _notify_status(application, note)
    return application


def _create_invoices(  # noqa: C901
    application: Application, config: AllocationSettings
) -> None:
    due = timezone.localdate() + datetime.timedelta(days=config.invoice_due_days)
    items = []
    if application.is_allocation:
        plot = application.plot
        if plot.uwt_total > 0:
            items.append(
                (
                    enums.InvoiceKind.UWT,
                    _("UWT lahan %(code)s: %(area)s m² × Rp%(rate)s × %(years)s tahun")
                    % {
                        "code": plot.code,
                        "area": plot.area_m2,
                        "rate": plot.uwt_rate_per_m2_year,
                        "years": plot.effective_term_years,
                    },
                    plot.uwt_total,
                )
            )
        if config.allocation_admin_fee > 0:
            items.append(
                (
                    enums.InvoiceKind.ALLOCATION_FEE,
                    _("Biaya administrasi alokasi lahan %s") % plot.code,
                    config.allocation_admin_fee,
                )
            )
    elif application.is_transfer:
        area = application.source_allocation.area_m2
        amount = (
            config.transfer_admin_fee + config.transfer_fee_per_m2 * area
        ).quantize(Decimal("1"))
        if amount > 0:
            items.append(
                (
                    enums.InvoiceKind.TRANSFER_FEE,
                    _("Biaya administrasi peralihan hak %s")
                    % application.source_allocation.kpt_number,
                    amount,
                )
            )
    elif application.is_extension:
        allocation = application.source_allocation
        plot = allocation.plot
        years = plot.effective_term_years
        uwt = (allocation.area_m2 * plot.uwt_rate_per_m2_year * years).quantize(
            Decimal("1")
        )
        if uwt > 0:
            items.append(
                (
                    enums.InvoiceKind.UWT,
                    _(
                        "UWT KPT %(kpt)s periode %(service)s: "
                        "%(area)s m² × Rp%(rate)s × %(years)s tahun"
                    )
                    % {
                        "kpt": allocation.kpt_number,
                        "service": application.get_service_type_display(),
                        "area": allocation.area_m2,
                        "rate": plot.uwt_rate_per_m2_year,
                        "years": years,
                    },
                    uwt,
                ),
            )
        if config.extension_admin_fee > 0:
            items.append(
                (
                    enums.InvoiceKind.EXTENSION_FEE,
                    _("Biaya administrasi %s KPT %s")
                    % (
                        application.get_service_type_display(),
                        allocation.kpt_number,
                    ),
                    config.extension_admin_fee,
                )
            )
    else:  # Pecah PL dan pengukuran ulang.
        if config.service_admin_fee > 0:
            items.append(
                (
                    enums.InvoiceKind.SERVICE_FEE,
                    _("Biaya administrasi %s KPT %s")
                    % (
                        application.get_service_type_display(),
                        application.source_allocation.kpt_number,
                    ),
                    config.service_admin_fee,
                )
            )
    for kind, description, amount in items:
        check_fits(Invoice, "amount", amount)
    for kind, description, amount in items:
        Invoice.objects.create(
            application=application,
            kind=kind,
            description=description,
            amount=amount,
            due_date=due,
        )


@transaction.atomic
def upload_payment_proof(invoice: Invoice, file, user) -> Invoice:
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    _require(
        invoice.status
        in (enums.InvoiceStatus.UNPAID, enums.InvoiceStatus.PROOF_UPLOADED),
        _("Tagihan ini tidak menunggu pembayaran."),
    )
    invoice.payment_proof = file
    invoice.full_clean(exclude=["application", "verified_by"])
    invoice.status = enums.InvoiceStatus.PROOF_UPLOADED
    invoice.proof_uploaded_at = timezone.now()
    invoice.save()
    return invoice


@transaction.atomic
def verify_payment(invoice: Invoice, officer, note: str = "") -> Invoice:
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    _require(
        invoice.status
        in (enums.InvoiceStatus.UNPAID, enums.InvoiceStatus.PROOF_UPLOADED),
        _("Tagihan ini sudah lunas atau dibatalkan."),
    )
    if invoice.status == enums.InvoiceStatus.UNPAID:
        # Tanpa bukti bayar dari pemohon, petugas wajib mencatat dasar
        # pelunasan (mis. nomor rekening koran) sebagai jejak audit.
        _require(
            bool(note.strip()),
            _("Belum ada bukti bayar: tuliskan dasar pelunasan tagihan ini."),
        )
    if note.strip():
        invoice.note = note.strip()
    invoice.status = enums.InvoiceStatus.PAID
    invoice.paid_at = timezone.now()
    invoice.verified_by = officer
    invoice.save()
    _maybe_complete_payment(invoice.application, officer)
    return invoice


@transaction.atomic
def reject_payment(invoice: Invoice, officer, note: str) -> Invoice:
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    _require(
        invoice.status == enums.InvoiceStatus.PROOF_UPLOADED,
        _("Hanya bukti bayar yang menunggu verifikasi yang dapat ditolak."),
    )
    _require(bool(note.strip()), _("Alasan penolakan bukti bayar wajib diisi."))
    invoice.status = enums.InvoiceStatus.UNPAID
    invoice.note = note
    invoice.save()
    notify(
        invoice.application.applicant,
        _("Bukti bayar tagihan %s ditolak") % invoice.number,
        _(
            "Bukti pembayaran untuk tagihan %(number)s ditolak: %(note)s\n\nUnggah ulang di %(url)s"
        )
        % {
            "number": invoice.number,
            "note": note,
            "url": portal_url(f"permohonan/{invoice.application.number}/"),
        },
    )
    return invoice


def _maybe_complete_payment(application: Application, officer) -> None:
    application = Application.objects.select_for_update().get(pk=application.pk)
    if application.status != S.APPROVED:
        return
    open_invoices = application.invoices.exclude(
        status__in=(enums.InvoiceStatus.PAID, enums.InvoiceStatus.CANCELLED)
    )
    if open_invoices.exists():
        return
    _set_status(application, S.PAID, actor=officer)
    issue_documents(application, officer)


# --------------------------------------------------------------------------
# Penerbitan
# --------------------------------------------------------------------------


def _add_years(date: datetime.date, years: int) -> datetime.date:
    try:
        return date.replace(year=date.year + years)
    except ValueError:
        return date.replace(year=date.year + years, day=28)


@transaction.atomic
def issue_documents(application: Application, officer=None) -> list[IssuedDocument]:
    from alokasi import documents

    application = Application.objects.select_for_update().get(pk=application.pk)
    _require(
        application.status == S.PAID,
        _("Dokumen hanya terbit setelah pembayaran lunas."),
    )
    issued = []
    today = timezone.localdate()
    if application.is_allocation:
        plot = LandPlot.objects.select_for_update().get(pk=application.plot_id)
        allocation = Allocation.objects.create(
            application=application,
            plot=plot,
            holder=application.applicant,
            kpt_number=_next_number("KPT"),
            ppt_number=_next_number("PPT"),
            issued_date=today,
            start_date=today,
            end_date=_add_years(today, plot.effective_term_years)
            - datetime.timedelta(days=1),
            area_m2=plot.area_m2,
            activity=application.activity,
        )
        plot.status = enums.PlotStatus.ALLOCATED
        plot.save(update_fields=["status", "modified_at"])
        issued.append(
            documents.issue(application, allocation, "kpt", allocation.kpt_number)
        )
        issued.append(
            documents.issue(application, allocation, "ppt", allocation.ppt_number)
        )
        body = _(
            "Keputusan Pengalokasian Tanah %(kpt)s dan Perjanjian Pemanfaatan Tanah %(ppt)s "
            "telah terbit. Unduh di %(url)s\n\nPemegang alokasi wajib melaporkan progres "
            "perizinan dan pembangunan secara berkala melalui portal."
        ) % {
            "kpt": allocation.kpt_number,
            "ppt": allocation.ppt_number,
            "url": portal_url(f"alokasi/{allocation.pk}/"),
        }
    elif application.is_transfer:
        allocation = Allocation.objects.select_for_update().get(
            pk=application.source_allocation_id
        )
        _require(
            allocation.status == enums.AllocationStatus.ACTIVE
            and allocation.holder_id == application.applicant_id,
            _("Alokasi tidak lagi dapat dialihkan."),
        )
        number = _next_number("IPH")
        previous_holder = allocation.holder
        allocation.holder = application.recipient
        allocation.save(update_fields=["holder", "modified_at"])
        issued.append(
            documents.issue(
                application, allocation, "iph", number, previous_holder=previous_holder
            )
        )
        body = _(
            "Surat Izin Persetujuan Peralihan Hak Atas Tanah %(number)s telah terbit. "
            "Alokasi %(kpt)s kini atas nama %(recipient)s. Unduh di %(url)s"
        ) % {
            "number": number,
            "kpt": allocation.kpt_number,
            "recipient": application.recipient.name,
            "url": portal_url(f"permohonan/{application.number}/"),
        }
        notify(
            application.recipient,
            _("Peralihan hak %s kepada Anda") % allocation.kpt_number,
            body,
        )
    elif application.is_extension:
        allocation = Allocation.objects.select_for_update().get(
            pk=application.source_allocation_id
        )
        _require_service_allocation(application, allocation)
        years = allocation.plot.effective_term_years
        is_renewal = application.service_type == enums.ServiceType.RENEWAL
        if is_renewal:
            # Pembaruan: periode baru dimulai hari ini.
            allocation.start_date = today
            new_end = _add_years(today, years) - datetime.timedelta(days=1)
        else:
            # Perpanjangan: sambung dari akhir jangka berjalan, kecuali sudah
            # lewat saat dokumen terbit.
            base = max(allocation.end_date, today)
            new_end = _add_years(base, years) - datetime.timedelta(days=1)
        allocation.end_date = new_end
        allocation.status = enums.AllocationStatus.ACTIVE
        allocation.save(
            update_fields=["start_date", "end_date", "status", "modified_at"]
        )
        number = _next_number("SPH")
        issued.append(documents.issue(application, allocation, "sph", number))
        body = _(
            "Surat %(service)s untuk alokasi KPT %(kpt)s telah terbit; jangka waktu "
            "kini berlaku sampai %(end)s. Unduh di %(url)s"
        ) % {
            "service": application.get_service_type_display(),
            "kpt": allocation.kpt_number,
            "end": allocation.end_date.strftime("%d-%m-%Y"),
            "url": portal_url(f"permohonan/{application.number}/"),
        }
    else:  # Pecah PL dan pengukuran ulang: surat persetujuan, tanpa ubah alokasi.
        allocation = Allocation.objects.select_for_update().get(
            pk=application.source_allocation_id
        )
        _require_service_allocation(application, allocation)
        number = _next_number("SPT")
        issued.append(documents.issue(application, allocation, "spt", number))
        body = _(
            "Surat persetujuan %(service)s untuk alokasi KPT %(kpt)s telah terbit. "
            "Unduh di %(url)s"
        ) % {
            "service": application.get_service_type_display(),
            "kpt": allocation.kpt_number,
            "url": portal_url(f"permohonan/{application.number}/"),
        }
    _set_status(application, S.ISSUED, actor=officer)
    notify(
        application.applicant,
        _("Dokumen permohonan %s terbit") % application.number,
        body,
    )
    return issued


@transaction.atomic
def revoke_allocation(allocation: Allocation, officer, reason: str) -> Allocation:
    allocation = Allocation.objects.select_for_update().get(pk=allocation.pk)
    _require(
        allocation.status == enums.AllocationStatus.ACTIVE, _("Alokasi tidak aktif.")
    )
    _require(bool(reason.strip()), _("Alasan pencabutan wajib diisi."))
    allocation.status = enums.AllocationStatus.REVOKED
    allocation.revoked_at = timezone.now()
    allocation.revoke_reason = reason
    allocation.save()
    # Permohonan peralihan/perpanjangan/layanan lain atas alokasi ini tidak
    # dapat diteruskan lagi: tolak dan batalkan tagihan yang belum lunas.
    note = _("Alokasi %(kpt)s dicabut: %(reason)s") % {
        "kpt": allocation.kpt_number,
        "reason": reason,
    }
    open_applications = allocation.transfer_applications.select_for_update().exclude(
        status__in=enums.FINAL_STATUSES
    )
    for application in open_applications:
        application.invoices.filter(
            status__in=(
                enums.InvoiceStatus.UNPAID,
                enums.InvoiceStatus.PROOF_UPLOADED,
            )
        ).update(status=enums.InvoiceStatus.CANCELLED)
        application.officer_note = note
        if application.status == S.DRAFT:
            _set_status(application, S.CANCELLED, actor=officer, note=note)
        else:
            application.decided_at = timezone.now()
            application.decided_by = officer
            _set_status(application, S.REJECTED, actor=officer, note=note)
        _notify_status(application, note)
    plot = allocation.plot
    plot.status = enums.PlotStatus.AVAILABLE
    plot.is_published = False
    plot.save(update_fields=["status", "is_published", "modified_at"])
    notify(
        allocation.holder,
        _("Alokasi %s dicabut") % allocation.kpt_number,
        _("Alokasi lahan %(kpt)s dicabut dengan alasan: %(reason)s")
        % {"kpt": allocation.kpt_number, "reason": reason},
    )
    return allocation
