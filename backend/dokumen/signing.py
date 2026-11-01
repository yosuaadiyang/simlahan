"""Alur dokumen tanda tangan elektronik (seperti PandaDoc).

Draf → (persetujuan internal) → dikirim → dilihat → ditandatangani/disetujui
penerima sesuai urutan → selesai (PDF final + sertifikat penyelesaian).
Penerima tanpa akun membuka tautan bertoken dan wajib memasukkan kode
verifikasi yang dikirim ke surelnya sebelum menandatangani.
"""

import base64
import binascii
import datetime
import hashlib
import hmac
import io
import secrets
import uuid

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from alokasi.services import portal_url
from dokumen import enums, merge, pdf, services
from dokumen.access import display_name, users_with_perm
from dokumen.models import (
    DocumentComment,
    DocumentRecipient,
    DocumentSettings,
    SavedSignature,
    SigningDocument,
    SigningField,
)
from dokumen.sanitizer import sanitize_html
from dokumen.services import (
    absolute,
    add_version,
    client_ip,
    log,
    on_commit_email,
    read_file,
    require,
    user_agent,
)

S = enums.SigningStatus
OTP_TTL = datetime.timedelta(minutes=10)
OTP_SESSION = datetime.timedelta(minutes=30)
OTP_MAX_ATTEMPTS = 5
OTP_SENDS_PER_HOUR = 5
MAX_SIGNATURE_BYTES = 300 * 1024
HOST_SESSION = datetime.timedelta(minutes=30)
MAX_FIELD_CHARS = 5000


def _lock(document: SigningDocument) -> SigningDocument:
    return SigningDocument.objects.select_for_update().get(pk=document.pk)


def sign_url(recipient: DocumentRecipient) -> str:
    return portal_url(f"dokumen/ttd/{recipient.token}/")


def admin_url(document: SigningDocument) -> str:
    return absolute(reverse("admin:dokumen_signingdocument_change", args=[document.pk]))


def _self_approval_allowed() -> bool:
    return DocumentSettings.load().allow_self_approval


# --------------------------------------------------------------------------
# Membuat & menyunting
# --------------------------------------------------------------------------


def _holder_recipient(document, land_use, role):
    holder = land_use.holder if land_use else None
    if holder is None or not holder.user_id or not holder.user.email:
        return None
    return DocumentRecipient(
        document=document,
        order=1,
        role=role or _("Pemegang hak"),
        action=enums.RecipientAction.SIGN,
        user=holder.user,
        name=holder.pic_name or holder.name,
        email=holder.user.email,
    )


@transaction.atomic
def create(
    *,
    user,
    title: str,
    template=None,
    land_use=None,
    record=None,
    upload=None,
    extra=None,
    request=None,
) -> SigningDocument:
    """Buat draf dari templat isian atau dari PDF unggahan."""
    require(bool((title or "").strip()), _("Isi judul dokumen."))
    require(
        template is not None or upload is not None, _("Pilih templat atau unggah PDF.")
    )
    if record is not None:
        land_use = land_use or record.land_use
        require(
            record.land_use_id == land_use.pk,
            _("Dokumen perizinan bukan milik pemanfaatan lahan ini."),
        )
    config = DocumentSettings.load()
    document = SigningDocument(
        title=title.strip()[:255],
        land_use=land_use,
        record=record,
        created_by=user,
        reminder_every_days=config.reminder_every_days,
        confidentiality=(
            record.permit_type.confidentiality
            if record is not None
            else enums.Confidentiality.NORMAL
        ),
    )
    roles = []
    if upload is not None:
        data = upload.read()
        upload.seek(0)
        try:
            pdf.page_count(data)
        except pdf.PdfReadError as error:
            raise ValidationError(
                _("PDF tidak dapat dibaca atau terkunci sandi.")
            ) from error
        document.source = enums.SigningSource.PDF
        document.source_name = (upload.name or "dokumen.pdf")[:255]
        document.source_file.save(document.source_name, upload, save=False)
        document.expires_on = timezone.localdate() + datetime.timedelta(
            days=config.signing_expiry_days
        )
    else:
        require(
            template.kind == enums.TemplateKind.HTML,
            _("Hanya templat isian yang dapat ditandatangani elektronik."),
        )
        document.template = template
        document.template_version = template.version
        document.needs_approval = template.needs_approval
        if template.confidentiality == enums.Confidentiality.SECRET:
            document.confidentiality = enums.Confidentiality.SECRET
        days = template.expiry_days or config.signing_expiry_days
        document.expires_on = timezone.localdate() + datetime.timedelta(days=days)
        roles = template.roles
    document.save()
    if template is not None:
        context = merge.build_context(
            land_use=land_use, record=record, document=document, extra=extra
        )
        document.body = merge.merge_html(template.body, context)
        document.save(update_fields=["body", "modified_at"])
    holder = _holder_recipient(document, land_use, roles[0] if roles else "")
    if holder is not None:
        holder.save()
    sync_fields(document, default_recipient=holder)
    log(
        enums.Action.CREATED,
        actor=user,
        request=request,
        signing=document,
        land_use=land_use,
        record=record,
        detail=str(template or document.source_name),
    )
    return document


def update_body(
    document: SigningDocument, body: str, user, request=None
) -> SigningDocument:
    require(document.is_editable, _("Isi hanya dapat diubah selama draf."))
    cleaned = sanitize_html(body)
    require(bool(cleaned), _("Isi dokumen tidak boleh kosong."))
    if cleaned != document.body:
        document.body = cleaned
        document.save(update_fields=["body", "modified_at"])
        log(
            enums.Action.UPDATED,
            actor=user,
            request=request,
            signing=document,
            detail=_("Isi dokumen diubah."),
        )
    return document


def fill_fields(
    document: SigningDocument, values: dict, user, request=None
) -> SigningDocument:
    """Isi ``{{ isian.<kunci> }}`` yang masih tersisa di isi draf."""
    require(document.is_editable, _("Isi hanya dapat diubah selama draf."))
    context = {
        f"isian.{key}": str(value)
        for key, value in values.items()
        if merge.CUSTOM_KEY_RE.match(key)
    }
    body = merge.merge_html(document.body, context)
    if body != document.body:
        document.body = body
        document.save(update_fields=["body", "modified_at"])
        log(
            enums.Action.UPDATED,
            actor=user,
            request=request,
            signing=document,
            detail=_("Isian diisi: %s") % ", ".join(sorted(values)),
        )
    return document


# --------------------------------------------------------------------------
# Kolom isian penerima ({{ kolom.<kunci> }})
# --------------------------------------------------------------------------


def field_keys(body: str) -> list[str]:
    keys = []
    for group, name in merge.FIELD_RE.findall(body or ""):
        if group == merge.RECIPIENT_FIELD_GROUP and name not in keys:
            keys.append(name)
    return keys


def sync_fields(document: SigningDocument, default_recipient=None) -> int:
    """Buat baris kolom untuk ``{{ kolom.* }}`` di isi yang belum punya definisi."""
    if document.source != enums.SigningSource.HTML or not document.is_editable:
        return 0
    existing = set(document.fields.values_list("key", flat=True))
    created = 0
    for order, key in enumerate(field_keys(document.body), 1):
        if key in existing:
            continue
        SigningField.objects.create(
            document=document,
            recipient=default_recipient,
            key=key,
            label=key.replace("_", " ").capitalize(),
            order=order,
        )
        created += 1
    return created


def render_body(document: SigningDocument, *, viewer=None, preview=False) -> str:
    """Isi dokumen dengan nilai kolom penerima.

    Kolom yang belum diisi tampil sebagai penanda ``[label]``: milik
    ``viewer`` diberi penanda khusus agar mudah ditemukan saat mengisi.
    """
    from html import escape

    fields = {f.key: f for f in document.fields.select_related("recipient")}

    def replace(match):
        group, name = match.groups()
        if group != merge.RECIPIENT_FIELD_GROUP:
            return match.group(0)
        field = fields.get(name)
        if field is None:
            return escape(match.group(0)) if preview else ""
        if field.filled_at and (
            field.display_value or field.kind == field.Kind.CHECKBOX
        ):
            return escape(field.display_value).replace("\n", "<br>")
        if document.status == S.COMPLETED:
            return ""
        owner = field.recipient.name if field.recipient_id else _("penerima")
        css = (
            "merge-field own-field"
            if viewer is not None and field.recipient_id == viewer.pk
            else "merge-field"
        )
        return f'<span class="{css}">[{escape(field.label)} · {escape(owner)}]</span>'

    return sanitize_html(merge.FIELD_RE.sub(replace, document.body or ""))


def _clean_number(field: SigningField, value: str) -> str:
    from decimal import Decimal, InvalidOperation

    try:
        number = Decimal(value.replace(" ", "").replace(",", "."))
    except InvalidOperation as error:
        raise ValidationError(_("Isi angka pada kolom %s.") % field.label) from error
    require(number.is_finite(), _("Isi angka pada kolom %s.") % field.label)
    return format(number.normalize(), "f")


def _clean_date(field: SigningField, value: str) -> str:
    try:
        return datetime.date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise ValidationError(
            _("Tanggal tidak valid pada kolom %s.") % field.label
        ) from error


def _clean_choice(field: SigningField, value: str) -> str:
    require(value in field.choices, _("Pilihan tidak dikenal: %s.") % field.label)
    return value


def _clean_initials(field: SigningField, value: str) -> str:
    require(len(value) <= 12, _("Paraf maksimal 12 karakter."))
    return value


def _clean_text(field: SigningField, value: str) -> str:
    return " ".join(value.split())[:500]


FIELD_CLEANERS = {
    SigningField.Kind.NUMBER: _clean_number,
    SigningField.Kind.DATE: _clean_date,
    SigningField.Kind.CHOICE: _clean_choice,
    SigningField.Kind.INITIALS: _clean_initials,
    SigningField.Kind.TEXT: _clean_text,
}


def _clean_field_value(field: SigningField, raw, upload=None) -> tuple[str, object]:
    """Validasi nilai satu kolom; mengembalikan (nilai, berkas)."""
    if field.kind == SigningField.Kind.FILE:
        if upload is None:
            require(not field.required, _("Lampirkan berkas: %s.") % field.label)
            return "", None
        services.validate_upload(upload)
        return "", upload
    value = (raw or "").strip() if isinstance(raw, str) else raw
    if field.kind == SigningField.Kind.CHECKBOX:
        checked = value in ("1", "on", "true", True)
        require(checked or not field.required, _("Centang: %s.") % field.label)
        return ("1" if checked else "0"), None
    if not value:
        require(not field.required, _("Isi kolom: %s.") % field.label)
        return "", None
    require(len(value) <= MAX_FIELD_CHARS, _("Isian %s terlalu panjang.") % field.label)
    cleaner = FIELD_CLEANERS.get(field.kind)
    return (cleaner(field, value) if cleaner else value), None


def save_fields(recipient: DocumentRecipient, values: dict, files: dict) -> list[str]:
    """Simpan isian kolom milik penerima; semua divalidasi dulu (atomik)."""
    fields = list(recipient.fields.select_for_update())
    cleaned = []
    errors = []
    for field in fields:
        try:
            cleaned.append(
                (field,)
                + _clean_field_value(
                    field, values.get(field.key, ""), files.get(field.key)
                )
            )
        except ValidationError as error:
            errors.extend(error.messages)
    if errors:
        raise ValidationError(errors)
    now = timezone.now()
    filled = []
    for field, value, upload in cleaned:
        if upload is not None:
            field.file_sha256, _size = services.file_digest(upload)
            field.file_name = (upload.name or "berkas")[:255]
            field.file.save(field.file_name, upload, save=False)
        field.value = value
        field.filled_at = now
        field.save()
        filled.append(field.label)
    return filled


def _field_problems(document: SigningDocument, recipients) -> list[str]:
    issues = []
    acting_ids = {r.pk for r in recipients if r.is_acting}
    fields = list(document.fields.all())
    defined = {f.key for f in fields}
    if document.source == enums.SigningSource.HTML:
        missing = [k for k in field_keys(document.body) if k not in defined]
        if missing:
            issues.append(
                _("Kolom penerima belum didefinisikan: %s")
                % ", ".join(f"{{{{ kolom.{k} }}}}" for k in missing)
            )
    for field in fields:
        if field.recipient_id not in acting_ids:
            issues.append(
                _("Kolom %s belum ditetapkan ke penanda tangan/penyetuju.")
                % field.label
            )
        if field.kind == SigningField.Kind.CHOICE and not field.choices:
            issues.append(_("Kolom pilihan %s belum punya pilihan.") % field.label)
    return issues


def problems(document: SigningDocument) -> list[str]:
    """Hal yang harus dibereskan sebelum dokumen dapat dikirim."""
    issues = []
    if (
        document.source == enums.SigningSource.HTML
        and not (document.body or "").strip()
    ):
        issues.append(_("Isi dokumen masih kosong."))
    if document.source == enums.SigningSource.PDF and not document.source_file:
        issues.append(_("Berkas PDF belum diunggah."))
    recipients = list(document.recipients.all())
    if not any(r.is_acting for r in recipients):
        issues.append(_("Tambahkan minimal satu penanda tangan atau penyetuju."))
    emails = [r.email.lower() for r in recipients if r.is_acting and r.email]
    if len(emails) != len(set(emails)):
        issues.append(_("Satu surel tidak boleh menjadi dua penerima yang bertindak."))
    for r in recipients:
        if not r.email and not (r.is_acting and r.in_person):
            issues.append(
                _("Surel %s wajib diisi (kecuali tanda tangan langsung).") % r.name
            )
    issues.extend(_field_problems(document, recipients))
    if document.expires_on and document.expires_on < timezone.localdate():
        issues.append(_("Batas tanda tangan sudah lewat; ubah tanggalnya."))
    leftovers = [
        (group, name)
        for group, name in (
            merge.FIELD_RE.findall(merge.sanitize_html(document.body or ""))
            if document.body
            else []
        )
        if group != merge.RECIPIENT_FIELD_GROUP
    ]
    if leftovers:
        issues.append(
            _("Masih ada isian yang belum terganti: %s")
            % ", ".join(sorted({f"{{{{ {g}.{n} }}}}" for g, n in leftovers}))
        )
    return issues


# --------------------------------------------------------------------------
# Persetujuan internal & pengiriman
# --------------------------------------------------------------------------


@transaction.atomic
def submit_for_approval(document, user, request=None):
    document = _lock(document)
    require(
        document.status == S.DRAFT, _("Hanya draf yang dapat diajukan persetujuan.")
    )
    issues = problems(document)
    require(not issues, " ".join(issues))
    document.status = S.PENDING_APPROVAL
    document.needs_approval = True
    document.save()
    log(enums.Action.APPROVAL_REQUESTED, actor=user, request=request, signing=document)
    approvers = users_with_perm("dokumen.approve_signingdocument").exclude(pk=user.pk)
    body = _(
        '%(user)s meminta persetujuan dokumen %(number)s "%(title)s" sebelum dikirim:\n%(url)s'
    ) % {
        "user": display_name(user),
        "number": document.number,
        "title": document.title,
        "url": admin_url(document),
    }
    on_commit_email(
        [u.email for u in approvers[:30]],
        _("Persetujuan dokumen %s") % document.number,
        body,
    )
    return document


def can_approve(user, document) -> bool:
    return user.has_perm("dokumen.approve_signingdocument") and (
        document.created_by_id != user.pk or _self_approval_allowed()
    )


@transaction.atomic
def approve(document, user, note="", request=None):
    document = _lock(document)
    require(
        document.status == S.PENDING_APPROVAL,
        _("Dokumen tidak sedang menunggu persetujuan."),
    )
    require(
        can_approve(user, document),
        _("Anda tidak dapat menyetujui dokumen yang Anda buat sendiri."),
    )
    document.status = S.APPROVED
    document.approved_by = user
    document.approved_at = timezone.now()
    document.save()
    log(
        enums.Action.APPROVED,
        actor=user,
        request=request,
        signing=document,
        detail=note,
    )
    if document.created_by and document.created_by.email:
        on_commit_email(
            [document.created_by.email],
            _("Dokumen %s disetujui") % document.number,
            _('Dokumen "%(title)s" disetujui %(user)s dan siap dikirim:\n%(url)s')
            % {
                "title": document.title,
                "user": display_name(user),
                "url": admin_url(document),
            },
        )
    return document


@transaction.atomic
def reject_approval(document, user, note: str, request=None):
    document = _lock(document)
    note = (note or "").strip()
    require(bool(note), _("Tuliskan alasan penolakan."))
    require(
        document.status == S.PENDING_APPROVAL,
        _("Dokumen tidak sedang menunggu persetujuan."),
    )
    require(
        user.has_perm("dokumen.approve_signingdocument"),
        _("Anda tidak berwenang menyetujui dokumen."),
    )
    document.status = S.DRAFT
    document.save()
    DocumentComment.objects.create(
        document=document,
        author=user,
        author_name=display_name(user),
        body=note,
        is_internal=True,
    )
    log(
        enums.Action.APPROVAL_REJECTED,
        actor=user,
        request=request,
        signing=document,
        detail=note,
    )
    if document.created_by and document.created_by.email:
        on_commit_email(
            [document.created_by.email],
            _("Dokumen %s perlu diperbaiki") % document.number,
            _('Persetujuan dokumen "%(title)s" ditolak: %(note)s\n%(url)s')
            % {"title": document.title, "note": note, "url": admin_url(document)},
        )
    return document


def _content_digest(document) -> str:
    if document.source == enums.SigningSource.PDF:
        return pdf.sha256(read_file(document.source_file))
    return hashlib.sha256((document.body or "").encode()).hexdigest()


def _notify_turn(document: SigningDocument, *, reminder=False) -> int:
    """Surel ke penerima yang mendapat giliran (atau pengingat bagi yang belum bertindak)."""
    order = document.current_order()
    if order is None:
        return 0
    recipients = (
        document.acting_recipients()
        .filter(order=order)
        .exclude(
            status__in=(enums.RecipientStatus.DONE, enums.RecipientStatus.DECLINED)
        )
    )
    if not reminder:
        recipients = recipients.filter(notified_at__isnull=True)
    count = 0
    org_message = (
        f"\n\n{_('Pesan pengirim')}:\n{document.message}" if document.message else ""
    )
    for recipient in recipients:
        verb = (
            _("menandatangani")
            if recipient.action == enums.RecipientAction.SIGN
            else _("menyetujui")
        )
        subject = (_("Pengingat: ") if reminder else "") + _(
            "Mohon %(verb)s %(title)s"
        ) % {"verb": verb, "title": document.title}
        body = _(
            'Yth. %(name)s,\n\nAnda diminta %(verb)s dokumen %(number)s "%(title)s" '
            "sebagai %(role)s.%(message)s\n\nBuka dokumen: %(url)s\n\nBatas waktu: %(until)s."
        ) % {
            "name": recipient.name,
            "verb": verb,
            "number": document.number,
            "title": document.title,
            "role": recipient.role or recipient.get_action_display().lower(),
            "message": org_message,
            "url": sign_url(recipient),
            "until": (
                document.expires_on.strftime("%d-%m-%Y") if document.expires_on else "-"
            ),
        }
        if not recipient.in_person:
            # Penerima tanda tangan langsung tidak diberi tautan lewat surel.
            on_commit_email([recipient.email], subject, body)
        recipient.notified_at = timezone.now()
        recipient.save(update_fields=["notified_at"])
        count += 1
    return count


@transaction.atomic
def send(document, user, request=None):
    document = _lock(document)
    allowed = (S.DRAFT, S.APPROVED)
    require(
        document.status in allowed,
        _("Dokumen ini tidak dapat dikirim pada status sekarang."),
    )
    require(
        not (document.needs_approval and document.status != S.APPROVED),
        _(
            "Dokumen ini wajib disetujui internal sebelum dikirim. Ajukan persetujuan terlebih dahulu."
        ),
    )
    issues = problems(document)
    require(not issues, " ".join(issues))
    if not document.expires_on:
        document.expires_on = timezone.localdate() + datetime.timedelta(
            days=DocumentSettings.load().signing_expiry_days
        )
    document.content_sha256 = _content_digest(document)
    document.status = S.SENT
    document.sent_at = timezone.now()
    document.save()
    log(
        enums.Action.SENT,
        actor=user,
        request=request,
        signing=document,
        detail=_("Sidik isi %s") % document.content_sha256[:16],
    )
    _notify_turn(document)
    return document


@transaction.atomic
def remind(document, user=None, request=None) -> int:
    document = _lock(document)
    require(document.is_open, _("Dokumen tidak sedang menunggu tanda tangan."))
    count = _notify_turn(document, reminder=True)
    document.last_reminder_at = timezone.now()
    document.save(update_fields=["last_reminder_at", "modified_at"])
    log(
        enums.Action.REMINDED,
        actor=user,
        request=request,
        signing=document,
        detail=_("%d penerima") % count,
    )
    return count


@transaction.atomic
def resend(recipient: DocumentRecipient, user, request=None):
    document = _lock(recipient.document)
    require(document.is_open, _("Dokumen tidak sedang menunggu tanda tangan."))
    recipient.refresh_from_db()
    require(
        recipient.is_acting
        and recipient.status
        not in (enums.RecipientStatus.DONE, enums.RecipientStatus.DECLINED),
        _("Penerima ini sudah bertindak."),
    )
    require(
        recipient.order == document.current_order(), _("Belum giliran penerima ini.")
    )
    recipient.notified_at = None
    recipient.save(update_fields=["notified_at"])
    _notify_turn(document)
    log(
        enums.Action.REMINDED,
        actor=user,
        request=request,
        signing=document,
        detail=recipient.name,
    )


@transaction.atomic
def cancel(document, user, reason: str, request=None):
    document = _lock(document)
    reason = (reason or "").strip()
    require(bool(reason), _("Tuliskan alasan pembatalan."))
    require(not document.is_final, _("Dokumen ini sudah ditutup."))
    was_sent = document.sent_at is not None
    document.status = S.CANCELLED
    document.closed_reason = reason[:5000]
    document.save()
    log(
        enums.Action.CANCELLED,
        actor=user,
        request=request,
        signing=document,
        detail=reason,
    )
    if was_sent:
        emails = list(
            document.recipients.filter(notified_at__isnull=False).values_list(
                "email", flat=True
            )
        )
        on_commit_email(
            emails,
            _("Dokumen %s dibatalkan") % document.number,
            _(
                'Dokumen "%(title)s" dibatalkan pengirim dan tidak perlu ditindaklanjuti.\nAlasan: %(reason)s'
            )
            % {"title": document.title, "reason": reason},
        )
    return document


@transaction.atomic
def duplicate(document, user, request=None) -> SigningDocument:
    copy = SigningDocument.objects.create(
        title=(_("Salinan %s") % document.title)[:255],
        source=document.source,
        template=document.template,
        template_version=document.template_version,
        land_use=document.land_use,
        record=document.record,
        body=document.body,
        source_name=document.source_name,
        confidentiality=document.confidentiality,
        needs_approval=document.needs_approval,
        message=document.message,
        reminder_every_days=document.reminder_every_days,
        expires_on=timezone.localdate()
        + datetime.timedelta(days=DocumentSettings.load().signing_expiry_days),
        created_by=user,
    )
    if document.source_file:
        copy.source_file.save(
            document.source_name or "dokumen.pdf",
            ContentFile(read_file(document.source_file)),
        )
    mapping = {}
    for recipient in document.recipients.all():
        mapping[recipient.pk] = DocumentRecipient.objects.create(
            document=copy,
            order=recipient.order,
            role=recipient.role,
            action=recipient.action,
            user=recipient.user,
            name=recipient.name,
            email=recipient.email,
            in_person=recipient.in_person,
            stamp_page=recipient.stamp_page,
            stamp_x=recipient.stamp_x,
            stamp_y=recipient.stamp_y,
            stamp_width=recipient.stamp_width,
        )
    for field in document.fields.all():
        SigningField.objects.create(
            document=copy,
            recipient=mapping.get(field.recipient_id),
            key=field.key,
            label=field.label,
            kind=field.kind,
            options=field.options,
            required=field.required,
            order=field.order,
        )
    log(
        enums.Action.CREATED,
        actor=user,
        request=request,
        signing=copy,
        detail=_("Disalin dari %s") % document.number,
    )
    return copy


def add_comment(
    document, user, body: str, *, internal=False, request=None, author_name=""
) -> DocumentComment:
    body = (body or "").strip()
    require(bool(body), _("Komentar tidak boleh kosong."))
    require(len(body) <= 5000, _("Komentar maksimal 5000 karakter."))
    comment = DocumentComment.objects.create(
        document=document,
        author=user if user is not None and user.is_authenticated else None,
        author_name=(author_name or display_name(user))[:255] or _("Penerima"),
        body=body,
        is_internal=internal,
    )
    log(
        enums.Action.COMMENTED,
        actor=user if user is not None and user.is_authenticated else None,
        actor_name=comment.author_name,
        request=request,
        signing=document,
        detail=body[:200],
    )
    if (
        not internal
        and document.created_by
        and document.created_by.email
        and document.created_by_id != getattr(user, "pk", None)
    ):
        on_commit_email(
            [document.created_by.email],
            _("Komentar baru pada %s") % document.number,
            _("%(name)s menulis:\n\n%(body)s\n\n%(url)s")
            % {"name": comment.author_name, "body": body, "url": admin_url(document)},
        )
    return comment


# --------------------------------------------------------------------------
# Penerima: lihat, kode verifikasi, tanda tangan, tolak
# --------------------------------------------------------------------------


def is_turn(recipient: DocumentRecipient) -> bool:
    document = recipient.document
    return (
        document.is_open
        and recipient.is_acting
        and recipient.status
        not in (enums.RecipientStatus.DONE, enums.RecipientStatus.DECLINED)
        and recipient.order == document.current_order()
    )


@transaction.atomic
def record_view(recipient: DocumentRecipient, request=None) -> None:
    document = _lock(recipient.document)
    recipient = DocumentRecipient.objects.select_for_update().get(pk=recipient.pk)
    if document.sent_at is not None:
        now = timezone.now()
        DocumentRecipient.objects.filter(pk=recipient.pk).update(
            view_count=recipient.view_count + 1, last_viewed_at=now
        )
    if recipient.viewed_at is None and document.sent_at is not None:
        recipient.viewed_at = timezone.now()
        if recipient.status == enums.RecipientStatus.WAITING:
            recipient.status = enums.RecipientStatus.VIEWED
        recipient.save(update_fields=["viewed_at", "status"])
        if document.status == S.SENT:
            document.status = S.VIEWED
            document.save(update_fields=["status", "modified_at"])
        log(
            enums.Action.VIEWED,
            actor_name=recipient.name,
            request=request,
            signing=document,
            detail=recipient.email,
        )


def _otp_digest(recipient, code: str) -> str:
    key = f"{settings.SECRET_KEY}:dokumen-otp:{recipient.token}".encode()
    return hmac.new(key, code.encode(), hashlib.sha256).hexdigest()


def send_otp(recipient: DocumentRecipient, request=None) -> None:
    recipient = DocumentRecipient.objects.select_related("document").get(
        pk=recipient.pk
    )
    require(
        is_turn(recipient), _("Dokumen belum atau tidak lagi menunggu tindakan Anda.")
    )
    require(
        not recipient.in_person and bool(recipient.email),
        _("Penerima ini menandatangani langsung di hadapan petugas."),
    )
    key = f"dokumen:otp:{recipient.pk}"
    try:
        sent = cache.get_or_set(key, 0, 3600)
        require(
            sent < OTP_SENDS_PER_HOUR,
            _("Terlalu sering meminta kode. Coba lagi dalam satu jam."),
        )
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, 3600)
    code = f"{secrets.randbelow(10**6):06d}"
    recipient.otp_hash = _otp_digest(recipient, code)
    recipient.otp_expires_at = timezone.now() + OTP_TTL
    recipient.otp_attempts = 0
    recipient.save(update_fields=["otp_hash", "otp_expires_at", "otp_attempts"])
    from alokasi.services import send_email

    send_email(
        [recipient.email],
        _("Kode verifikasi dokumen %s") % recipient.document.number,
        _(
            "Kode verifikasi Anda: %(code)s\n\nBerlaku 10 menit. Jangan berikan "
            "kode ini kepada siapa pun, termasuk petugas."
        )
        % {"code": code},
    )
    log(
        enums.Action.OTP_SENT,
        actor_name=recipient.name,
        request=request,
        signing=recipient.document,
        detail=recipient.email,
    )


def set_access_code(recipient: DocumentRecipient, code: str) -> None:
    """Simpan kode akses (dibagikan petugas di luar surel) dalam bentuk hash."""
    from django.contrib.auth.hashers import make_password

    code = (code or "").strip()
    recipient.access_code_hash = make_password(code) if code else ""


def check_otp(recipient: DocumentRecipient, code: str, access_code: str = "") -> bool:
    """Kode surel (dan kode akses bila diatur) harus cocok bersamaan."""
    from django.contrib.auth.hashers import check_password

    recipient = DocumentRecipient.objects.get(pk=recipient.pk)
    code = (code or "").strip()
    if (
        not recipient.otp_hash
        or recipient.otp_expires_at is None
        or recipient.otp_expires_at < timezone.now()
        or recipient.otp_attempts >= OTP_MAX_ATTEMPTS
    ):
        return False
    DocumentRecipient.objects.filter(pk=recipient.pk).update(
        otp_attempts=recipient.otp_attempts + 1
    )
    if not hmac.compare_digest(recipient.otp_hash, _otp_digest(recipient, code)):
        return False
    if recipient.access_code_hash and not check_password(
        (access_code or "").strip(), recipient.access_code_hash
    ):
        return False
    DocumentRecipient.objects.filter(pk=recipient.pk).update(
        otp_verified_at=timezone.now(), otp_hash="", otp_expires_at=None
    )
    return True


def otp_ok(recipient: DocumentRecipient) -> bool:
    if recipient.in_person:
        # Hanya lewat sesi tanda tangan langsung yang dipandu petugas.
        return False
    if not recipient.needs_otp:
        return True
    return bool(
        recipient.otp_verified_at
        and recipient.otp_verified_at > timezone.now() - OTP_SESSION
    )


def clean_signature(data_uri: str) -> str:
    """Validasi & normalkan gambar tanda tangan (PNG data URI) dari kanvas."""
    from PIL import Image, UnidentifiedImageError

    prefix = "data:image/png;base64,"
    data_uri = (data_uri or "").strip()
    if not data_uri:
        return ""
    require(data_uri.startswith(prefix), _("Format gambar tanda tangan tidak dikenal."))
    try:
        raw = base64.b64decode(data_uri[len(prefix) :], validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValidationError(_("Gambar tanda tangan rusak.")) from error
    require(len(raw) <= MAX_SIGNATURE_BYTES, _("Gambar tanda tangan terlalu besar."))
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError) as error:
        raise ValidationError(_("Gambar tanda tangan rusak.")) from error
    require(image.format == "PNG", _("Format gambar tanda tangan tidak dikenal."))
    require(
        image.width <= 2000 and image.height <= 1000,
        _("Gambar tanda tangan terlalu besar."),
    )
    image = image.convert("RGBA")
    require(
        image.getchannel("A").getbbox() is not None, _("Tanda tangan masih kosong.")
    )
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return prefix + base64.b64encode(output.getvalue()).decode()


def _require_verified(recipient: DocumentRecipient, host=None) -> str:
    """Pastikan penerima terverifikasi; kembalikan catatan cara verifikasinya."""
    if host is not None:
        require(
            recipient.hosted_for(host),
            _(
                "Sesi tanda tangan langsung sudah berakhir; buka ulang dari panel petugas."
            ),
        )
        return _("Langsung di hadapan petugas %(officer)s; identitas: %(evidence)s") % {
            "officer": display_name(host),
            "evidence": recipient.host_evidence,
        }
    require(
        otp_ok(recipient), _("Masukkan kode verifikasi yang dikirim ke surel Anda.")
    )
    notes = []
    if recipient.user_id:
        notes.append(_("Masuk dengan akun SimLahan"))
    if recipient.needs_otp:
        notes.append(_("Kode verifikasi surel"))
    if recipient.access_code_hash:
        notes.append(_("Kode akses"))
    return " + ".join(str(n) for n in notes)


@transaction.atomic
def act(
    recipient: DocumentRecipient,
    *,
    name: str,
    signature: str = "",
    request=None,
    field_values=None,
    field_files=None,
    host=None,
) -> SigningDocument:
    """Penerima menandatangani (atau menyetujui) dokumen.

    ``host`` diisi petugas yang memandu tanda tangan langsung.
    """
    document = _lock(recipient.document)
    recipient = DocumentRecipient.objects.select_for_update().get(pk=recipient.pk)
    recipient.document = document
    require(
        is_turn(recipient), _("Dokumen belum atau tidak lagi menunggu tindakan Anda.")
    )
    verification = _require_verified(recipient, host)
    name = (name or "").strip()
    require(len(name) >= 3, _("Tulis nama lengkap Anda."))
    image = clean_signature(signature)
    if recipient.action == enums.RecipientAction.SIGN:
        require(bool(image), _("Bubuhkan tanda tangan pada kotak yang tersedia."))
    filled = save_fields(recipient, field_values or {}, field_files or {})
    recipient.signature_name = name[:255]
    recipient.signature_image = image
    recipient.status = enums.RecipientStatus.DONE
    recipient.completed_at = timezone.now()
    recipient.viewed_at = recipient.viewed_at or recipient.completed_at
    recipient.ip_address = client_ip(request)
    recipient.user_agent = user_agent(request)
    recipient.verification_note = verification[:255]
    recipient.hosted_by = None
    recipient.hosted_until = None
    recipient.save()
    action = (
        enums.Action.SIGNED
        if recipient.action == enums.RecipientAction.SIGN
        else enums.Action.RECIPIENT_APPROVED
    )
    detail = f"{name} <{recipient.email or '-'}> · {verification}"
    if filled:
        detail += " · " + _("kolom diisi: %s") % ", ".join(filled)
    log(
        action,
        actor=host or recipient.user,
        actor_name=recipient.name,
        request=request,
        signing=document,
        detail=detail,
    )
    if document.current_order() is None:
        _complete(document)
    else:
        _notify_turn(document)
    return document


@transaction.atomic
def decline(
    recipient: DocumentRecipient, reason: str, request=None, host=None
) -> SigningDocument:
    document = _lock(recipient.document)
    recipient = DocumentRecipient.objects.select_for_update().get(pk=recipient.pk)
    recipient.document = document
    require(
        is_turn(recipient), _("Dokumen belum atau tidak lagi menunggu tindakan Anda.")
    )
    _require_verified(recipient, host)
    recipient.hosted_by = None
    recipient.hosted_until = None
    reason = (reason or "").strip()
    require(bool(reason), _("Tuliskan alasan menolak."))
    recipient.status = enums.RecipientStatus.DECLINED
    recipient.decline_reason = reason[:5000]
    recipient.completed_at = timezone.now()
    recipient.ip_address = client_ip(request)
    recipient.user_agent = user_agent(request)
    recipient.save()
    document.status = S.DECLINED
    document.closed_reason = _("%(name)s menolak: %(reason)s") % {
        "name": recipient.name,
        "reason": reason,
    }
    document.save()
    log(
        enums.Action.DECLINED,
        actor=recipient.user,
        actor_name=recipient.name,
        request=request,
        signing=document,
        detail=reason,
    )
    emails = [document.created_by.email if document.created_by else ""]
    emails += list(
        document.recipients.filter(status=enums.RecipientStatus.DONE).values_list(
            "email", flat=True
        )
    )
    on_commit_email(
        emails,
        _("Dokumen %s ditolak") % document.number,
        _('%(name)s menolak dokumen "%(title)s".\nAlasan: %(reason)s')
        % {"name": recipient.name, "title": document.title, "reason": reason},
    )
    return document


def _complete(document: SigningDocument) -> None:
    document.status = S.COMPLETED
    document.completed_at = timezone.now()
    document.save()
    log(enums.Action.COMPLETED, signing=document, actor_name=_("Sistem"))
    data = pdf.signing_pdf(document)
    document.final_sha256 = pdf.sha256(data)
    filename = f"{document.number}.pdf"
    document.final_file.save(filename, ContentFile(data), save=False)
    document.save(update_fields=["final_file", "final_sha256", "modified_at"])
    if document.record_id:
        _attach_to_record(document, data, filename)
    recipients = list(document.recipients.all())
    emails = [r.email for r in recipients]
    if document.created_by and document.created_by.email:
        emails.append(document.created_by.email)
    on_commit_email(
        sorted(set(emails)),
        _("Dokumen %s selesai ditandatangani") % document.number,
        _(
            'Dokumen "%(title)s" telah ditandatangani semua pihak.\n'
            "Periksa keaslian: %(verify)s\n\n"
            "Salinan PDF dapat diunduh setelah permintaan unduh disetujui petugas berwenang."
        )
        % {"title": document.title, "verify": pdf.verification_url(document)},
    )


def _attach_to_record(document, data, filename):
    from dokumen.services import _lock_record

    record = _lock_record(document.record)
    add_version(
        record,
        ContentFile(data, name=filename),
        user=document.created_by,
        source=enums.VersionSource.SIGNED,
        note=_("Ditandatangani elektronik: %s") % document.number,
    )
    record.status = enums.RecordStatus.VERIFIED
    record.verified_by = document.created_by
    record.verified_at = timezone.now()
    record.review_note = (
        _("Ditandatangani elektronik oleh semua pihak (%s).") % document.number
    )
    if not record.number:
        record.number = document.number
    if not record.issued_date:
        record.issued_date = timezone.localdate()
        record.expiry_date = record.expiry_date or record.default_expiry()
    record.save()
    log(
        enums.Action.VERIFIED,
        actor=document.created_by,
        record=record,
        detail=record.review_note,
    )


# --------------------------------------------------------------------------
# Tugas harian
# --------------------------------------------------------------------------


def expire_documents(today=None) -> list[SigningDocument]:
    today = today or timezone.localdate()
    expired = []
    for document in SigningDocument.objects.filter(
        status__in=enums.OPEN_SIGNING_STATUSES, expires_on__lt=today
    ):
        with transaction.atomic():
            document = _lock(document)
            if not document.is_open:
                continue
            document.status = S.EXPIRED
            document.closed_reason = _(
                "Batas tanda tangan %s terlewati."
            ) % document.expires_on.strftime("%d-%m-%Y")
            document.save()
            log(enums.Action.EXPIRED, signing=document, detail=document.closed_reason)
            if document.created_by and document.created_by.email:
                on_commit_email(
                    [document.created_by.email],
                    _("Dokumen %s kedaluwarsa") % document.number,
                    _(
                        'Dokumen "%(title)s" belum selesai ditandatangani sampai '
                        "batas waktu. Salin dokumen untuk mengirim ulang:\n%(url)s"
                    )
                    % {"title": document.title, "url": admin_url(document)},
                )
        expired.append(document)
    return expired


def send_due_reminders(now=None) -> int:
    now = now or timezone.now()
    count = 0
    for document in SigningDocument.objects.filter(
        status__in=enums.OPEN_SIGNING_STATUSES, reminder_every_days__gt=0
    ):
        last = document.last_reminder_at or document.sent_at
        if last is None or last > now - datetime.timedelta(
            days=document.reminder_every_days
        ):
            continue
        count += remind(document)
    return count


# --------------------------------------------------------------------------
# Ganti penerima, tanda tangan langsung, tanda tangan tersimpan, kirim massal
# --------------------------------------------------------------------------


@transaction.atomic
def reassign(
    recipient: DocumentRecipient,
    *,
    name: str,
    email: str,
    user,
    officer,
    reason: str,
    request=None,
) -> DocumentRecipient:
    """Ganti penerima yang belum bertindak (mis. pejabat berganti, surel salah).

    Tautan lama tidak berlaku lagi (token baru) dan kode verifikasi direset.
    """
    document = _lock(recipient.document)
    recipient = DocumentRecipient.objects.select_for_update().get(pk=recipient.pk)
    require(
        document.is_open or document.is_editable,
        _(
            "Penerima hanya dapat diganti selama dokumen draf atau menunggu tanda tangan."
        ),
    )
    require(
        recipient.status
        not in (enums.RecipientStatus.DONE, enums.RecipientStatus.DECLINED),
        _("Penerima ini sudah bertindak."),
    )
    name = (name or "").strip()
    email = (email or "").strip().lower()
    reason = (reason or "").strip()
    require(len(name) >= 3, _("Tulis nama penerima baru."))
    require(bool(reason), _("Tuliskan alasan penggantian."))
    require(
        bool(email) or recipient.in_person,
        _("Surel penerima baru wajib diisi."),
    )
    if user is not None:
        require(
            bool(user.email) and user.email.lower() == email,
            _("Surel harus sama dengan surel akun yang dipilih."),
        )
    clash = (
        document.recipients.exclude(pk=recipient.pk)
        .exclude(action=enums.RecipientAction.COPY)
        .filter(email__iexact=email)
        .exists()
    )
    require(
        not (email and recipient.is_acting and clash),
        _("Surel ini sudah menjadi penerima lain yang bertindak."),
    )
    old = f"{recipient.name} <{recipient.email or '-'}>"
    recipient.name = name[:255]
    recipient.email = email
    recipient.user = user
    recipient.token = uuid.uuid4()
    recipient.status = enums.RecipientStatus.WAITING
    recipient.notified_at = None
    recipient.viewed_at = None
    recipient.otp_hash = ""
    recipient.otp_expires_at = None
    recipient.otp_attempts = 0
    recipient.otp_verified_at = None
    recipient.hosted_by = None
    recipient.hosted_until = None
    recipient.save()
    log(
        enums.Action.REASSIGNED,
        actor=officer,
        request=request,
        signing=document,
        detail=_("%(old)s diganti %(new)s: %(reason)s")
        % {"old": old, "new": f"{name} <{email or '-'}>", "reason": reason},
    )
    if document.is_open:
        _notify_turn(document)
    return recipient


@transaction.atomic
def start_hosted(
    recipient: DocumentRecipient, officer, evidence: str, request=None
) -> DocumentRecipient:
    """Buka sesi tanda tangan langsung di perangkat petugas (30 menit)."""
    recipient = DocumentRecipient.objects.select_for_update().get(pk=recipient.pk)
    require(
        is_turn(recipient),
        _("Dokumen belum atau tidak lagi menunggu tindakan penerima ini."),
    )
    evidence = " ".join((evidence or "").split())
    require(len(evidence) >= 4, _("Catat bukti identitas yang diperiksa."))
    recipient.hosted_by = officer
    recipient.hosted_until = timezone.now() + HOST_SESSION
    recipient.host_evidence = evidence[:255]
    recipient.save(update_fields=["hosted_by", "hosted_until", "host_evidence"])
    log(
        enums.Action.HOSTED,
        actor=officer,
        request=request,
        signing=recipient.document,
        detail=_("%(name)s · identitas: %(evidence)s")
        % {"name": recipient.name, "evidence": recipient.host_evidence},
    )
    return recipient


def save_signature(user, name: str, signature: str) -> SavedSignature:
    """Simpan (atau ganti) tanda tangan tersimpan milik akun."""
    name = (name or "").strip()
    require(len(name) >= 3, _("Tulis nama lengkap Anda."))
    image = clean_signature(signature)
    require(bool(image), _("Bubuhkan tanda tangan pada kotak yang tersedia."))
    saved, _created = SavedSignature.objects.update_or_create(
        user=user, defaults={"name": name[:255], "image": image}
    )
    return saved


def bulk_send(
    *,
    template,
    land_uses,
    user,
    title: str = "",
    extra_recipient: dict | None = None,
    message: str = "",
    request=None,
) -> list[dict]:
    """Buat (dan kirim bila bisa) satu dokumen per pemanfaatan lahan.

    Setiap dokumen ditangani dalam transaksi sendiri sehingga kegagalan satu
    pemanfaatan lahan tidak membatalkan yang lain. Hasil per baris:
    ``{"land_use", "document", "status", "note"}``.
    """
    results = []
    for land_use in land_uses:
        row = {"land_use": land_use, "document": None, "status": "gagal", "note": ""}
        try:
            with transaction.atomic():
                holder = land_use.holder
                require(
                    holder is not None and holder.user_id and holder.user.email,
                    _("Pemegang hak belum punya akun portal bersurel."),
                )
                document = create(
                    user=user,
                    title=(title or template.name).replace("{nomor}", land_use.number),
                    template=template,
                    land_use=land_use,
                    request=request,
                )
                if message:
                    document.message = message[:5000]
                    document.save(update_fields=["message", "modified_at"])
                if extra_recipient:
                    DocumentRecipient.objects.create(
                        document=document,
                        order=extra_recipient.get("order") or 2,
                        role=extra_recipient.get("role", "")[:100],
                        action=extra_recipient.get("action")
                        or enums.RecipientAction.SIGN,
                        user=extra_recipient.get("user"),
                        name=extra_recipient["name"][:255],
                        email=extra_recipient["email"],
                    )
                log(
                    enums.Action.BULK_SENT,
                    actor=user,
                    request=request,
                    signing=document,
                    land_use=land_use,
                    detail=str(template),
                )
                row["document"] = document
                issues = problems(document)
                if issues:
                    row["status"] = "draf"
                    row["note"] = " ".join(str(i) for i in issues)
                elif document.needs_approval:
                    submit_for_approval(document, user, request=request)
                    row["status"] = "menunggu_persetujuan"
                else:
                    send(document, user, request=request)
                    row["status"] = "dikirim"
        except ValidationError as error:
            row["note"] = " ".join(error.messages)
            row["document"] = None
        results.append(row)
    return results
