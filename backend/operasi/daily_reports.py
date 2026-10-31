"""Laporan harian berjenjang pusat komando.

Petugas menyusun laporan dari kegiatannya yang belum dilaporkan lalu
mengirimnya ke atasan langsung. Atasan merangkum laporan masuk (ditambah
kegiatannya sendiri) menjadi laporan baru untuk atasannya, sampai pimpinan
tertinggi menandainya selesai ditinjau. Penerima dapat mengembalikan laporan
untuk revisi; pemegang revisi dapat memperbaikinya sendiri atau meneruskannya
ke bawahan langsung, dan laporan kembali naik lewat jalur yang sama.
"""

import datetime
import logging
from collections import Counter

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

from asetlahan import scope as aset_scope
from operasi import enums, geo, hierarchy
from operasi.models import (
    Activity,
    DailyReport,
    DailyReportAttachment,
    DailyReportEvent,
)

LOG = logging.getLogger(__name__)

MAX_CONTENT = 20_000
MAX_ATTACHMENTS = 10
DEFAULT_DAYS = 7
MAX_DAYS = 31
MAX_SOURCES = 200

Status = enums.DailyReportStatus
Action = enums.DailyReportAction


def _name(user) -> str:
    if user is None:
        return "—"
    return user.get_full_name() or user.get_username()


# --------------------------------------------------------------------------
# Kumpulan data
# --------------------------------------------------------------------------


def visible_reports(user):
    """Laporan yang boleh dibuka: buatan sendiri, yang dikirim kepada atau
    menunggu revisi oleh pengguna, dan laporan para bawahan."""
    queryset = DailyReport.objects.select_related(
        "author", "recipient", "revision_owner", "korwil"
    )
    if aset_scope.sees_all(user):
        return queryset
    condition = Q(author=user) | Q(recipient=user) | Q(revision_owner=user)
    below = hierarchy.descendant_ids(user)
    if below:
        condition |= Q(author__in=below)
    return queryset.filter(condition)


def inbox(user):
    return DailyReport.objects.filter(
        recipient=user, status=Status.SENT, consolidated_into__isnull=True
    ).select_related("author", "korwil")


def revisions(user):
    return DailyReport.objects.filter(
        revision_owner=user, status=Status.RETURNED
    ).select_related("author", "returned_by", "korwil")


def pending_activities(user, days=DEFAULT_DAYS):
    since = timezone.now() - datetime.timedelta(days=days)
    return (
        Activity.objects.filter(
            reported_by=user, daily_report__isnull=True, started_at__gte=since
        )
        .select_related("korwil")
        .prefetch_related("photos", "residents")
        .order_by("started_at")
    )


def can_finish(user) -> bool:
    """Pimpinan tertinggi (tanpa atasan) dan Administrator menutup rantai."""
    return aset_scope.sees_all(user) or hierarchy.supervisor_of(user) is None


# --------------------------------------------------------------------------
# Penyusunan isi (AI bila tersedia, templat bila tidak)
# --------------------------------------------------------------------------


def _activity_line(activity) -> str:
    parts = [
        timezone.localtime(activity.started_at).strftime("%d-%m %H:%M"),
        activity.get_activity_type_display(),
        activity.title,
    ]
    if activity.korwil_id:
        parts.append(_("Korwil %(code)s") % {"code": activity.korwil.code})
    if activity.location_name:
        parts.append(activity.location_name)
    residents = len(activity.residents.all())
    if residents:
        parts.append(_("%(n)d warga") % {"n": residents})
    photos = len(activity.photos.all())
    if photos:
        parts.append(_("%(n)d foto") % {"n": photos})
    line = " · ".join(str(p) for p in parts if p)
    narrative = " ".join(
        t for t in ((activity.description or "").strip(), activity.outcome.strip()) if t
    )
    if narrative:
        line += "\n   " + narrative[:400]
    return line


def _report_block(report) -> str:
    head = _("Dari %(name)s%(position)s, %(korwil)s, tanggal %(date)s") % {
        "name": _name(report.author),
        "position": f" ({report.author_position})" if report.author_position else "",
        "korwil": (
            _("Korwil %(code)s") % {"code": report.korwil.code}
            if report.korwil_id
            else _("lintas Korwil")
        ),
        "date": report.report_date.strftime("%d-%m-%Y"),
    }
    return f"— {head}:\n{report.content.strip()}"


def materials(activities, reports) -> str:
    text = []
    if activities:
        text.append(_("KEGIATAN SAYA SENDIRI:"))
        text += [f"{i}. {_activity_line(a)}" for i, a in enumerate(activities, 1)]
    if reports:
        text.append(_("LAPORAN MASUK DARI BAWAHAN:"))
        text += [_report_block(r) for r in reports]
    return "\n".join(text)


def _summary(activities, reports) -> list[str]:
    lines = []
    if activities:
        per_type = Counter(a.get_activity_type_display() for a in activities)
        lines.append(
            _("Kegiatan sendiri: %(n)d (%(types)s)")
            % {
                "n": len(activities),
                "types": ", ".join(f"{k} {v}" for k, v in per_type.most_common()),
            }
        )
        flagged = [
            a
            for a in activities
            if a.activity_type == enums.ActivityType.ILLEGAL
            or a.needs_impact_confirmation
        ]
        if flagged:
            lines.append(
                _("Perlu perhatian: %(items)s")
                % {"items": "; ".join(f"{a.number} {a.title}" for a in flagged[:10])}
            )
    if reports:
        lines.append(_("Laporan bawahan dirangkum: %(n)d") % {"n": len(reports)})
    return lines


def template_text(user, activities, reports) -> str:
    position = hierarchy.position_of(user)
    head = f"*{_('Laporan harian')} – {_name(user)}"
    head += f" ({position})*" if position else "*"
    today = f"{timezone.localdate():%d-%m-%Y}"
    parts = [head, _("Tanggal: %(d)s") % {"d": today}]
    if activities:
        parts.append("")
        parts.append(f"*{_('Kegiatan saya')} ({len(activities)})*")
        parts += [f"{i}. {_activity_line(a)}" for i, a in enumerate(activities, 1)]
    if reports:
        parts.append("")
        parts.append(f"*{_('Laporan masuk')} ({len(reports)})*")
        parts += [_report_block(r) for r in reports]
    summary = _summary(activities, reports)
    if summary:
        parts.append("")
        parts.append(f"*{_('Ringkasan')}*")
        parts += [f"- {line}" for line in summary]
    if not activities and not reports:
        parts.append("")
        parts.append(_("Tidak ada kegiatan maupun laporan masuk pada periode ini."))
    return "\n".join(parts)


AI_PROMPT = (
    "Anda menyusun laporan harian berjenjang untuk atasan langsung di pusat "
    "komando pengelolaan lahan. Tulis dalam Bahasa Indonesia yang ringkas dan "
    "profesional, format WhatsApp (cetak tebal memakai *). Gunakan HANYA fakta "
    "dari materi; jangan mengarang angka, nama, atau kejadian. Bila materi "
    "memuat lebih dari satu Korwil, kelompokkan per Korwil; bila lebih dari "
    "satu tanggal, beri sub-judul per tanggal. Bedakan kegiatan pelapor sendiri "
    "dari laporan bawahan yang dirangkum. Akhiri dengan bagian *Temuan penting* "
    "dan *Tindak lanjut* yang konkret."
)


def compose(user, activities, reports) -> tuple[str, bool]:
    """Draf isi laporan; ``True`` bila disusun AI."""
    from asetlahan import ai

    fallback = template_text(user, activities, reports)
    if not ai.enabled() or (not activities and not reports):
        return fallback, False
    position = hierarchy.position_of(user) or _("petugas")
    prompt = (
        f"Pelapor: {_name(user)} ({position}). "
        f"Tanggal: {timezone.localdate():%d-%m-%Y}.\n\n"
        f"Materi:\n{materials(activities, reports)[:60_000]}"
    )
    try:
        response = ai.create(
            max_tokens=2000,
            system=AI_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = ai.text_of(response).strip()
    except ai.AIError as error:
        LOG.warning("Penyusunan laporan harian AI gagal: %s", error)
        return fallback, False
    return (text[:MAX_CONTENT], True) if text else (fallback, False)


# --------------------------------------------------------------------------
# Validasi masukan
# --------------------------------------------------------------------------


def _content(value) -> str:
    content = (value or "").strip()
    if not content:
        raise ValidationError({"isi": [_("Isi laporan wajib diisi.")]})
    if len(content) > MAX_CONTENT:
        raise ValidationError({"isi": [_("Isi laporan maksimal 20.000 karakter.")]})
    return content


def _note(value) -> str:
    note = (value or "").strip()
    if not note:
        raise ValidationError({"catatan": [_("Catatan wajib diisi.")]})
    if len(note) > 2000:
        raise ValidationError({"catatan": [_("Catatan maksimal 2000 karakter.")]})
    return note


def selected_activities(user, ids):
    ids = set(ids)
    if len(ids) > MAX_SOURCES:
        raise ValidationError({"kegiatan": [_("Terlalu banyak kegiatan dipilih.")]})
    found = list(
        Activity.objects.filter(pk__in=ids, reported_by=user, daily_report__isnull=True)
        .select_related("korwil")
        .prefetch_related("photos", "residents")
        .order_by("started_at")
    )
    if len(found) != len(ids):
        raise ValidationError(
            {
                "kegiatan": [
                    _("Ada kegiatan yang bukan milik Anda atau sudah dilaporkan.")
                ]
            }
        )
    return found


def selected_reports(user, ids, lock=False):
    ids = set(ids)
    if len(ids) > MAX_SOURCES:
        raise ValidationError({"laporan": [_("Terlalu banyak laporan dipilih.")]})
    queryset = inbox(user).filter(pk__in=ids).order_by("report_date", "pk")
    if lock:
        queryset = queryset.select_for_update(of=("self",))
    found = list(queryset)
    if len(found) != len(ids):
        raise ValidationError(
            {"laporan": [_("Ada laporan yang tidak lagi di kotak masuk Anda.")]}
        )
    return found


def _attachments(report, files, user):
    files = list(files or [])
    if report.attachments.count() + len(files) > MAX_ATTACHMENTS:
        raise ValidationError({"lampiran": [_("Lampiran maksimal 10 berkas.")]})
    for upload in files:
        attachment = DailyReportAttachment(
            report=report, file=upload, name=upload.name[:255], uploaded_by=user
        )
        try:
            attachment.full_clean(exclude=["report"])
        except ValidationError as error:
            raise ValidationError({"lampiran": error.messages})
        attachment.save()


def _event(report, action, actor, target=None, note=""):
    DailyReportEvent.objects.create(
        report=report, action=action, actor=actor, target=target, note=note
    )


# --------------------------------------------------------------------------
# Alur
# --------------------------------------------------------------------------


@transaction.atomic
def send(user, *, content, activity_ids, report_ids, files=(), ai_generated=False):
    """Kirim laporan ke atasan langsung, merangkum kegiatan & laporan masuk."""
    if not user.has_perm("operasi.add_dailyreport"):
        raise PermissionDenied
    recipient = hierarchy.supervisor_of(user)
    if recipient is None:
        raise ValidationError(
            _(
                "Anda belum punya atasan di struktur komando. Pimpinan tertinggi "
                "menandai laporan masuk selesai ditinjau; minta Administrator "
                "mengatur atasan Anda bila keliru."
            )
        )
    content = _content(content)
    activities = selected_activities(user, activity_ids)
    reports = selected_reports(user, report_ids, lock=True)
    korwils = {a.korwil_id for a in activities} | {r.korwil_id for r in reports}
    korwils.discard(None)
    if len(korwils) == 1:
        korwil_id = korwils.pop()
    elif korwils:
        korwil_id = None  # lintas Korwil
    else:
        own = geo.user_korwils(user).order_by("code").first()
        korwil_id = own.pk if own else None
    report = DailyReport.objects.create(
        author=user,
        author_position=hierarchy.position_of(user)[:128],
        recipient=recipient,
        korwil_id=korwil_id,
        content=content,
        ai_generated=bool(ai_generated),
    )
    _attachments(report, files, user)
    Activity.objects.filter(pk__in=[a.pk for a in activities]).update(
        daily_report=report
    )
    if reports:
        DailyReport.objects.filter(pk__in=[r.pk for r in reports]).update(
            consolidated_into=report, status=Status.FORWARDED
        )
        DailyReportEvent.objects.bulk_create(
            [
                DailyReportEvent(
                    report=r, action=Action.FORWARDED, actor=user, target=recipient
                )
                for r in reports
            ]
        )
    _event(report, Action.SENT, user, recipient)
    return report


@transaction.atomic
def mark_reviewed(user, report_ids) -> int:
    if not can_finish(user):
        raise ValidationError(
            _("Laporan masuk dirangkum lalu dikirim ke atasan Anda, bukan ditutup.")
        )
    reports = selected_reports(user, report_ids, lock=True)
    if not reports:
        raise ValidationError({"laporan": [_("Pilih laporan yang ditinjau.")]})
    now = timezone.now()
    DailyReport.objects.filter(pk__in=[r.pk for r in reports]).update(
        status=Status.REVIEWED, reviewed_by=user, reviewed_at=now
    )
    for report in reports:
        _event(report, Action.REVIEWED, user)
    return len(reports)


def _locked(report):
    return DailyReport.objects.select_for_update().get(pk=report.pk)


@transaction.atomic
def return_report(user, report, note):
    report = _locked(report)
    if report.recipient_id != user.pk or not report.in_inbox:
        raise ValidationError(_("Laporan ini tidak lagi di kotak masuk Anda."))
    report.status = Status.RETURNED
    report.revision_owner_id = report.author_id
    report.revision_stack = [user.pk]
    report.return_note = _note(note)
    report.returned_by = user
    report.returned_at = timezone.now()
    report.save()
    _event(report, Action.RETURNED, user, report.author, report.return_note)
    return report


def _owned_revision(user, report):
    report = _locked(report)
    if report.status != Status.RETURNED or report.revision_owner_id != user.pk:
        raise ValidationError(_("Laporan ini tidak menunggu revisi dari Anda."))
    return report


@transaction.atomic
def delegate(user, report, subordinate_id, note):
    """Teruskan perbaikan ke bawahan langsung; setelah diperbaiki laporan
    kembali ke pengguna untuk ditinjau sebelum naik lagi."""
    report = _owned_revision(user, report)
    if not str(subordinate_id).isdigit() or int(
        subordinate_id
    ) not in hierarchy.direct_subordinate_ids(user):
        raise ValidationError({"bawahan": [_("Pilih bawahan langsung Anda.")]})
    subordinate = get_user_model().objects.get(pk=subordinate_id)
    report.revision_stack = list(report.revision_stack) + [user.pk]
    report.revision_owner = subordinate
    report.return_note = _note(note)
    report.returned_by = user
    report.returned_at = timezone.now()
    report.save()
    _event(report, Action.DELEGATED, user, subordinate, report.return_note)
    return report


@transaction.atomic
def revise(user, report, content, files=()):
    """Simpan perbaikan lalu kirim naik satu langkah ke peminta revisi."""
    report = _owned_revision(user, report)
    report.content = _content(content)
    _attachments(report, files, user)
    stack = list(report.revision_stack)
    up_id = stack.pop() if stack else report.recipient_id
    up = get_user_model().objects.filter(pk=up_id).first()
    report.revision_stack = stack
    if not stack:
        # Sampai ke peminta revisi pertama: masuk lagi ke kotak masuknya.
        report.status = Status.SENT
        report.recipient = up
        report.revision_owner = None
        report.sent_at = timezone.now()
        report.save()
        _event(report, Action.RESUBMITTED, user, up)
    else:
        report.revision_owner = up
        report.return_note = _("Sudah diperbaiki oleh %(name)s.") % {
            "name": _name(user)
        }
        report.returned_by = user
        report.returned_at = timezone.now()
        report.save()
        _event(report, Action.REVISED, user, up)
    return report


@transaction.atomic
def close(user, report):
    """Pembuat menutup laporan yang dikembalikan; kegiatan & laporan sumbernya
    kembali ke daftar yang belum dilaporkan agar bisa dikirim ulang."""
    report = _owned_revision(user, report)
    if report.author_id != user.pk or len(report.revision_stack) > 1:
        raise ValidationError(
            _("Hanya pembuat laporan yang dapat menutupnya, setelah revisi kembali.")
        )
    report.status = Status.CLOSED
    report.revision_owner = None
    report.save()
    report.activities.update(daily_report=None)
    report.sources.update(consolidated_into=None, status=Status.SENT)
    _event(report, Action.CLOSED, user)
    return report


# --------------------------------------------------------------------------
# Pelacakan
# --------------------------------------------------------------------------


def chain(report):
    """Laporan ini lalu laporan-laporan atas yang merangkumnya, berurutan."""
    nodes = [report]
    seen = {report.pk}
    node = report
    while node.consolidated_into_id and node.consolidated_into_id not in seen:
        node = DailyReport.objects.select_related(
            "author", "recipient", "revision_owner", "reviewed_by"
        ).get(pk=node.consolidated_into_id)
        seen.add(node.pk)
        nodes.append(node)
    return nodes


def position_text(top) -> str:
    if top.status == Status.REVIEWED:
        return _("Selesai ditinjau oleh %(name)s") % {"name": _name(top.reviewed_by)}
    if top.status == Status.RETURNED:
        return _("Dikembalikan, menunggu revisi oleh %(name)s") % {
            "name": _name(top.revision_owner)
        }
    if top.status == Status.CLOSED:
        return _("Ditutup oleh pembuat")
    return _("Di kotak masuk %(name)s") % {"name": _name(top.recipient)}


def trace(user, days=14, limit=40) -> list[dict]:
    """Posisi laporan buatan pengguna dan bawahannya: sudah sampai siapa."""
    since = timezone.now() - datetime.timedelta(days=days)
    authors = {user.pk} | hierarchy.descendant_ids(user)
    reports = (
        DailyReport.objects.filter(author__in=authors, sent_at__gte=since)
        .exclude(status=Status.CLOSED)
        .select_related(
            "author", "recipient", "revision_owner", "reviewed_by", "korwil"
        )
        .order_by("-sent_at")[:limit]
    )
    rows = []
    for report in reports:
        path = chain(report)
        top = path[-1]
        steps = [_name(r.author) for r in path]
        if top.status in (Status.SENT, Status.REVIEWED) and top.recipient_id:
            steps.append(_name(top.recipient))
        rows.append(
            {
                "id": report.pk,
                "number": report.number,
                "date": report.report_date.isoformat(),
                "author": _name(report.author),
                "mine": report.author_id == user.pk,
                "korwil": report.korwil.code if report.korwil_id else "",
                "steps": steps,
                "position": position_text(top),
                "state": top.status,
                "done": top.status == Status.REVIEWED,
            }
        )
    return rows
