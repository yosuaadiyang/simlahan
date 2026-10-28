"""Alur kerja permintaan investasi & penggunaan lahan (portal investasi).

Setiap perubahan status lewat fungsi di modul ini supaya riwayat
(InvestmentEvent), status lahan, dan notifikasi surel selalu konsisten.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from alokasi import enums, services
from alokasi.models import (
    Applicant,
    InvestmentEvent,
    InvestmentMessage,
    InvestmentRequest,
    LandPlot,
)
from utils.group_permissions import UserGroup
from utils.money import check_fits

S = enums.InvestmentStatus
Scheme = enums.InvestmentScheme

OPEN_STATUSES = (S.SUBMITTED, S.REVIEW, S.CONSULTATION)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _lock(investment: InvestmentRequest) -> InvestmentRequest:
    """Muat ulang dengan kunci baris agar dua petugas tidak memproses bersamaan."""
    return InvestmentRequest.objects.select_for_update().get(pk=investment.pk)


def _set_status(investment, status, actor=None, note: str = "") -> None:
    investment.status = status
    if status in enums.INVESTMENT_FINAL_STATUSES:
        investment.closed_at = timezone.now()
    investment.save()
    InvestmentEvent.objects.create(
        request=investment, status=status, note=note, actor=actor
    )


# --------------------------------------------------------------------------
# Notifikasi
# --------------------------------------------------------------------------


def request_url(investment: InvestmentRequest) -> str:
    return services.portal_url(f"investasi/permintaan/{investment.number}/")


def officer_recipients(investment: InvestmentRequest) -> list[str]:
    """Petugas penanggung jawab; bila belum ada, seluruh Petugas Alokasi Lahan
    (atau Administrator bila grup itu kosong)."""
    if investment.assigned_to_id and investment.assigned_to.is_active:
        return [investment.assigned_to.email]
    users = get_user_model().objects.filter(is_active=True).exclude(email="")
    for group in (UserGroup.PETUGAS_ALOKASI, UserGroup.PAAKAYTTAJA):
        emails = list(users.filter(groups__pk=group).values_list("email", flat=True))
        if emails:
            return sorted(set(emails))
    return []


def admin_url(investment: InvestmentRequest) -> str:
    base = (getattr(settings, "OFFICER_UI_URL", "") or "").rstrip("/")
    return base + reverse(
        "admin:alokasi_investmentrequest_change", args=[investment.pk]
    )


def _notify_officers(investment: InvestmentRequest, subject: str, lines: list[str]):
    body = "\n".join(
        lines
        + [
            "",
            _("Investor: %(name)s") % {"name": investment.applicant.name},
            _("Buka di panel petugas: %s") % admin_url(investment),
        ]
    )
    services.send_email(officer_recipients(investment), subject, body)


def _notify_investor(investment: InvestmentRequest, subject: str, lines: list[str]):
    body = "\n".join(
        [_("Yth. %(name)s,") % {"name": investment.applicant.name}, ""]
        + lines
        + ["", _("Lihat rincian: %s") % request_url(investment)]
    )
    services.notify(investment.applicant, subject, body)


def _notify_status(investment: InvestmentRequest, note: str = "") -> None:
    lines = [
        _("Status permintaan investasi %(number)s (%(project)s) kini: %(status)s.")
        % {
            "number": investment.number,
            "project": investment.project_name,
            "status": investment.get_status_display(),
        }
    ]
    if note:
        lines += ["", _("Catatan petugas:"), note]
    _notify_investor(
        investment,
        _("Permintaan investasi %(number)s: %(status)s")
        % {"number": investment.number, "status": investment.get_status_display()},
        lines,
    )


# --------------------------------------------------------------------------
# Investor
# --------------------------------------------------------------------------


@transaction.atomic
def submit_request(applicant: Applicant, form) -> InvestmentRequest:
    """Simpan permintaan dari formulir portal yang sudah valid."""
    investment = form.save(commit=False)
    investment.applicant = applicant
    upload = form.cleaned_data.get("attachment")
    if upload:
        investment.attachment_name = upload.name[:255]
    investment.save()
    form.save_m2m()
    InvestmentEvent.objects.create(
        request=investment, status=S.SUBMITTED, actor=applicant.user
    )
    _become_investor(applicant, investment)
    transaction.on_commit(lambda: _after_submit(investment.pk))
    return investment


def _become_investor(applicant: Applicant, investment: InvestmentRequest) -> None:
    """Pengajuan minat pertama menjadikan akun pemohon akun investor; profil
    investornya diisi dari permintaan itu."""
    if applicant.is_investor:
        return
    applicant.is_investor = True
    applicant.capital_origin = investment.capital_origin
    applicant.origin_country = investment.origin_country
    applicant.save(
        update_fields=["is_investor", "capital_origin", "origin_country", "modified_at"]
    )
    if investment.sector_id and not applicant.interest_sectors.exists():
        applicant.interest_sectors.add(investment.sector_id)


def _after_submit(pk: int) -> None:
    investment = InvestmentRequest.objects.select_related("applicant__user").get(pk=pk)
    plots = ", ".join(p.code for p in investment.plots.all()) or "–"
    _notify_investor(
        investment,
        _("Permintaan investasi %s diterima") % investment.number,
        [
            _(
                "Terima kasih. Permintaan investasi %(number)s (%(project)s) telah kami "
                "terima dan akan ditinjau petugas."
            )
            % {"number": investment.number, "project": investment.project_name},
        ],
    )
    _notify_officers(
        investment,
        _("Permintaan investasi baru %s") % investment.number,
        [
            _("Permintaan investasi baru: %(number)s – %(project)s.")
            % {"number": investment.number, "project": investment.project_name},
            _("Skema: %s") % investment.get_scheme_display(),
            _("Lahan: %s") % plots,
        ],
    )


def post_message(
    investment: InvestmentRequest, user, body: str, attachment=None, *, officer: bool
) -> InvestmentMessage:
    _require(
        not investment.is_final,
        _("Permintaan ini sudah ditutup; pesan baru tidak dapat dikirim."),
    )
    body = (body or "").strip()
    _require(bool(body), _("Pesan tidak boleh kosong."))
    message = InvestmentMessage(
        request=investment, author=user, from_officer=officer, body=body
    )
    if attachment:
        message.attachment = attachment
        message.attachment_name = attachment.name[:255]
    message.full_clean()
    message.save()
    snippet = body if len(body) <= 600 else body[:600] + "…"
    if officer:
        _notify_investor(
            investment,
            _("Pesan baru dari petugas untuk %s") % investment.number,
            [_("Petugas mengirim pesan:"), "", snippet],
        )
    else:
        _notify_officers(
            investment,
            _("Pesan baru dari investor untuk %s") % investment.number,
            [_("Investor mengirim pesan:"), "", snippet],
        )
    return message


@transaction.atomic
def accept_offer(investment: InvestmentRequest, user) -> InvestmentRequest:
    investment = _lock(investment)
    _require(
        investment.status == S.OFFERED,
        _("Tidak ada penawaran yang menunggu jawaban."),
    )
    _require(
        not investment.offer_expired,
        _("Masa berlaku penawaran sudah lewat. Minta penawaran baru lewat pesan."),
    )
    plot = investment.offer_plot
    if plot is not None:
        _require(
            plot.is_available,
            _("Lahan yang ditawarkan sudah tidak tersedia. Hubungi petugas."),
        )
    _set_status(investment, S.ACCEPTED, user)
    transaction.on_commit(
        lambda: _notify_officers(
            investment,
            _("Penawaran %s diterima investor") % investment.number,
            [
                _(
                    "Investor menerima penawaran untuk %(number)s. Lanjutkan dengan "
                    "tombol Selesaikan & teruskan di panel petugas."
                )
                % {"number": investment.number}
            ],
        )
    )
    return investment


@transaction.atomic
def decline_offer(
    investment: InvestmentRequest, user, reason: str
) -> InvestmentRequest:
    investment = _lock(investment)
    _require(
        investment.status == S.OFFERED,
        _("Tidak ada penawaran yang menunggu jawaban."),
    )
    reason = (reason or "").strip()
    _require(bool(reason), _("Sebutkan alasan atau penyesuaian yang diinginkan."))
    _set_status(
        investment,
        S.REVIEW,
        user,
        _("Penawaran ditolak investor: %s") % reason,
    )
    transaction.on_commit(
        lambda: _notify_officers(
            investment,
            _("Penawaran %s ditolak investor") % investment.number,
            [_("Alasan investor:"), "", reason],
        )
    )
    return investment


@transaction.atomic
def cancel(investment: InvestmentRequest, user, note: str = "") -> InvestmentRequest:
    investment = _lock(investment)
    _require(
        not investment.is_final and investment.status != S.ACCEPTED,
        _("Permintaan ini tidak dapat dibatalkan lagi."),
    )
    _set_status(investment, S.CANCELLED, user, note)
    transaction.on_commit(
        lambda: _notify_officers(
            investment,
            _("Permintaan investasi %s dibatalkan") % investment.number,
            [_("Investor membatalkan permintaan ini."), note],
        )
    )
    return investment


# --------------------------------------------------------------------------
# Petugas
# --------------------------------------------------------------------------


@transaction.atomic
def start_review(investment: InvestmentRequest, officer, note: str = ""):
    investment = _lock(investment)
    _require(
        investment.status == S.SUBMITTED,
        _("Hanya permintaan berstatus Diajukan yang dapat mulai ditinjau."),
    )
    if investment.assigned_to_id is None:
        investment.assigned_to = officer
    _set_status(investment, S.REVIEW, officer, note)
    transaction.on_commit(lambda: _notify_status(investment, note))
    return investment


@transaction.atomic
def schedule_consultation(
    investment: InvestmentRequest, officer, meeting_at, place: str, note: str = ""
):
    investment = _lock(investment)
    _require(
        investment.status in OPEN_STATUSES,
        _("Jadwal hanya dapat dibuat sebelum penawaran dikirim."),
    )
    _require(meeting_at is not None, _("Isi jadwal konsultasi."))
    _require(
        meeting_at > timezone.now(),
        _("Jadwal konsultasi harus di masa mendatang."),
    )
    place = (place or "").strip()
    _require(bool(place), _("Isi tempat atau tautan pertemuan."))
    investment.meeting_at = meeting_at
    investment.meeting_place = place
    if investment.assigned_to_id is None:
        investment.assigned_to = officer
    when = timezone.localtime(meeting_at).strftime("%d-%m-%Y %H:%M")
    full_note = _("Jadwal: %(when)s, %(place)s.") % {"when": when, "place": place}
    if note:
        full_note += "\n" + note
    _set_status(investment, S.CONSULTATION, officer, full_note)
    transaction.on_commit(lambda: _notify_status(investment, full_note))
    return investment


@transaction.atomic
def make_offer(  # noqa: C901
    investment: InvestmentRequest,
    officer,
    *,
    scheme: str,
    plot: LandPlot | None,
    area_m2,
    rate_per_m2_year,
    term_years: int,
    valid_until,
    note: str = "",
):
    investment = _lock(investment)
    _require(
        investment.status in OPEN_STATUSES + (S.OFFERED,),
        _("Penawaran hanya dapat dibuat untuk permintaan yang masih ditinjau."),
    )
    _require(scheme in enums.OFFER_SCHEMES, _("Pilih skema yang ditawarkan."))
    if scheme == Scheme.ALLOCATION:
        _require(
            plot is not None,
            _("Skema alokasi memerlukan lahan dari daftar lahan alokasi."),
        )
        _require(
            plot.offer_allocation,
            _("Lahan %s tidak ditawarkan dengan skema alokasi.") % plot.code,
        )
    if plot is not None:
        plot = LandPlot.objects.select_for_update().get(pk=plot.pk)
        _require(
            plot.is_available,
            _("Lahan %s tidak tersedia untuk ditawarkan.") % plot.code,
        )
        if area_m2 is None:
            area_m2 = plot.area_m2
        if rate_per_m2_year is None:
            rate_per_m2_year = (
                plot.uwt_rate_per_m2_year
                if scheme == Scheme.ALLOCATION
                else plot.lease_rate_per_m2_year
            )
        if term_years is None:
            term_years = (
                plot.effective_term_years
                if scheme == Scheme.ALLOCATION
                else investment.term_years or plot.lease_min_years
            )
    if area_m2 is None:
        area_m2 = investment.requested_area_m2
    if term_years is None:
        term_years = investment.term_years
    _require(area_m2 is not None and area_m2 > 0, _("Isi luas yang ditawarkan."))
    _require(rate_per_m2_year is not None, _("Isi tarif yang ditawarkan."))
    _require(bool(term_years), _("Isi jangka waktu yang ditawarkan."))
    _require(
        valid_until is not None and valid_until >= timezone.localdate(),
        _("Masa berlaku penawaran harus hari ini atau setelahnya."),
    )
    investment.offer_scheme = scheme
    investment.offer_plot = plot
    investment.offer_area_m2 = area_m2
    investment.offer_rate_per_m2_year = rate_per_m2_year
    investment.offer_term_years = term_years
    investment.offer_valid_until = valid_until
    investment.offer_note = (note or "").strip()
    investment.offered_at = timezone.now()
    check_fits(InvestmentRequest, "offer_rate_per_m2_year", investment.offer_total)
    if investment.assigned_to_id is None:
        investment.assigned_to = officer
    summary = _("Penawaran %(scheme)s%(plot)s, berlaku s.d. %(until)s.") % {
        "scheme": investment.get_offer_scheme_display().lower(),
        "plot": f" {plot.code}" if plot else "",
        "until": valid_until.strftime("%d-%m-%Y"),
    }
    _set_status(investment, S.OFFERED, officer, summary)
    transaction.on_commit(
        lambda: _notify_status(investment, "\n".join(filter(None, [summary, note])))
    )
    return investment


@transaction.atomic
def complete(
    investment: InvestmentRequest, officer, *, contract_number: str = "", note: str = ""
):
    """Teruskan penawaran yang diterima: skema alokasi menjadi draf permohonan
    alokasi; sewa/kerja sama dicatat nomor kontraknya dan lahannya ditandai."""
    investment = _lock(investment)
    _require(
        investment.status == S.ACCEPTED,
        _("Hanya penawaran yang sudah diterima investor yang dapat diselesaikan."),
    )
    contract_number = (contract_number or "").strip()
    plot = investment.offer_plot
    if investment.offer_scheme == Scheme.ALLOCATION:
        application = services.create_allocation_application(investment.applicant, plot)
        # Isi rencana usaha dari permintaan; investor tinggal melengkapi dokumen.
        application.activity = investment.project_name[:255] or application.activity
        application.investment_value = investment.investment_value
        application.workforce = investment.workforce
        application.description = investment.activity
        application.save()
        investment.application = application
        closing = _(
            "Diteruskan menjadi draf permohonan alokasi %(number)s. Lengkapi dokumen "
            "persyaratan lalu ajukan permohonan."
        ) % {"number": application.number}
    else:
        _require(
            bool(contract_number),
            _("Isi nomor kontrak sewa atau perjanjian kerja sama."),
        )
        investment.contract_number = contract_number
        if plot is not None:
            plot = LandPlot.objects.select_for_update().get(pk=plot.pk)
            _require(
                plot.is_available,
                _("Lahan %s sudah tidak tersedia.") % plot.code,
            )
            plot.status = enums.PlotStatus.LEASED
            plot.save(update_fields=["status", "modified_at"])
        closing = _("Kontrak/perjanjian %(number)s dicatat.") % {
            "number": contract_number
        }
    full_note = "\n".join(filter(None, [closing, (note or "").strip()]))
    _set_status(investment, S.COMPLETED, officer, full_note)
    transaction.on_commit(lambda: _notify_status(investment, full_note))
    return investment


@transaction.atomic
def reject(investment: InvestmentRequest, officer, note: str):
    investment = _lock(investment)
    _require(
        not investment.is_final,
        _("Permintaan ini sudah ditutup."),
    )
    note = (note or "").strip()
    _require(bool(note), _("Sebutkan alasan penolakan."))
    _set_status(investment, S.REJECTED, officer, note)
    transaction.on_commit(lambda: _notify_status(investment, note))
    return investment
