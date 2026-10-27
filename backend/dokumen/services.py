"""Logika inti modul dokumen: pemanfaatan lahan, dokumen perizinan, versi,
templat, dan jejak aktivitas. Semua perubahan status lewat fungsi di sini."""

import datetime
import hashlib
import io
import logging
import os
import zipfile

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from alokasi.services import send_email
from dokumen import enums, merge
from dokumen.access import display_name
from dokumen.models import (
    DOCUMENT_EXTENSIONS,
    MAX_UPLOAD_BYTES,
    Activity,
    DocumentTemplate,
    DocumentVersion,
    LandUse,
    PermitRecord,
    PermitType,
)
from dokumen.sanitizer import sanitize_html

LOG = logging.getLogger(__name__)
RS = enums.RecordStatus


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def client_ip(request) -> str | None:
    if request is None:
        return None
    from alokasi.views import _client_ip

    return _client_ip(request) or None


def user_agent(request) -> str:
    if request is None:
        return ""
    return (request.META.get("HTTP_USER_AGENT") or "")[:255]


def log(action, *, actor=None, request=None, detail="", **targets) -> Activity:
    if actor is None and request is not None and request.user.is_authenticated:
        actor = request.user
    record = targets.get("record")
    if record is not None and "land_use" not in targets:
        targets["land_use"] = record.land_use
    return Activity.objects.create(
        action=action,
        actor=actor if actor is not None and actor.pk else None,
        actor_name=targets.pop("actor_name", "") or display_name(actor) or _("Sistem"),
        detail=(detail or "")[:5000],
        ip_address=client_ip(request),
        **targets,
    )


def absolute(path: str) -> str:
    base = (getattr(settings, "OFFICER_UI_URL", "") or "").rstrip("/")
    return f"{base}{path}"


def email_users(users, subject: str, body: str) -> None:
    for user in users:
        if user is not None and user.email:
            send_email([user.email], subject, body)


def on_commit_email(recipients, subject: str, body: str) -> None:
    """Kirim surel setelah transaksi berhasil (gagal kirim tidak membatalkan proses)."""
    emails = [e for e in recipients if e]
    if emails:
        transaction.on_commit(lambda: send_email(emails, subject, body))


def file_digest(fieldfile_or_upload) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    handle = fieldfile_or_upload
    handle.seek(0)
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
        size += len(chunk)
    handle.seek(0)
    return digest.hexdigest(), size


def read_file(fieldfile) -> bytes:
    with fieldfile.open("rb") as handle:
        return handle.read()


# --------------------------------------------------------------------------
# Pemanfaatan lahan
# --------------------------------------------------------------------------

ALLOCATION_STATUS = {
    "aktif": enums.LandUseStatus.ACTIVE,
    "dialihkan": enums.LandUseStatus.ENDED,
    "berakhir": enums.LandUseStatus.ENDED,
    "dicabut": enums.LandUseStatus.REVOKED,
}


def ensure_records(land_use: LandUse) -> int:
    """Buat baris dokumen perizinan untuk setiap jenis yang berlaku tetapi belum ada."""
    existing = set(land_use.records.values_list("permit_type_id", flat=True))
    missing = [
        PermitRecord(land_use=land_use, permit_type=permit_type)
        for permit_type in PermitType.applicable(land_use.scheme, land_use.sector_id)
        if permit_type.pk not in existing
    ]
    PermitRecord.objects.bulk_create(missing, ignore_conflicts=True)
    return len(missing)


def sync_permit_type(permit_type: PermitType) -> int:
    """Terapkan jenis dokumen ke semua pemanfaatan aktif yang memenuhi syarat."""
    if not permit_type.is_active:
        return 0
    schemes = [
        scheme
        for scheme, flag in PermitType.SCHEME_FLAGS.items()
        if getattr(permit_type, flag)
    ]
    land_uses = LandUse.objects.filter(
        status=enums.LandUseStatus.ACTIVE, scheme__in=schemes
    ).exclude(records__permit_type=permit_type)
    sector_ids = list(permit_type.sectors.values_list("pk", flat=True))
    if sector_ids:
        land_uses = land_uses.filter(sector_id__in=sector_ids)
    records = [
        PermitRecord(land_use_id=pk, permit_type=permit_type)
        for pk in land_uses.values_list("pk", flat=True)
    ]
    PermitRecord.objects.bulk_create(records, ignore_conflicts=True)
    return len(records)


def sync_from_allocation(allocation) -> LandUse:
    plot = allocation.plot
    land_use = LandUse.objects.filter(allocation=allocation).first()
    status = ALLOCATION_STATUS.get(allocation.status, enums.LandUseStatus.ACTIVE)
    if land_use is None:
        land_use = LandUse.objects.create(
            title=allocation.activity or plot.name,
            scheme=enums.Scheme.ALLOCATION,
            status=status,
            holder=allocation.holder,
            holder_name=allocation.holder.name,
            plot=plot,
            allocation=allocation,
            sector=plot.sector,
            reference=allocation.kpt_number,
            area_m2=allocation.area_m2,
            start_date=allocation.start_date,
            end_date=allocation.end_date,
        )
        log(
            enums.Action.CREATED,
            land_use=land_use,
            detail=_("Dari alokasi %s") % allocation.kpt_number,
        )
        ensure_records(land_use)
        return land_use
    changed = []
    for field, value in (
        ("status", status),
        ("holder_id", allocation.holder_id),
        ("holder_name", allocation.holder.name),
        ("end_date", allocation.end_date),
        ("start_date", allocation.start_date),
        ("area_m2", allocation.area_m2),
    ):
        if getattr(land_use, field) != value:
            setattr(land_use, field, value)
            changed.append(field)
    if changed:
        land_use.save()
        log(
            enums.Action.UPDATED,
            land_use=land_use,
            detail=_("Disesuaikan dengan alokasi %(kpt)s (%(fields)s).")
            % {"kpt": allocation.kpt_number, "fields": ", ".join(changed)},
        )
    return land_use


def sync_from_investment(investment) -> LandUse | None:
    from alokasi.enums import InvestmentScheme, InvestmentStatus

    if (
        investment.status != InvestmentStatus.COMPLETED
        or investment.offer_scheme
        not in (
            InvestmentScheme.LEASE,
            InvestmentScheme.PARTNERSHIP,
        )
    ):
        return None
    existing = LandUse.objects.filter(investment=investment).first()
    if existing is not None:
        return existing
    scheme = (
        enums.Scheme.LEASE
        if investment.offer_scheme == InvestmentScheme.LEASE
        else enums.Scheme.PARTNERSHIP
    )
    start = timezone.localdate()
    end = None
    if investment.offer_term_years:
        from alokasi.services import _add_years

        end = _add_years(start, investment.offer_term_years) - datetime.timedelta(
            days=1
        )
    plot = investment.offer_plot
    land_use = LandUse.objects.create(
        title=investment.project_name,
        scheme=scheme,
        holder=investment.applicant,
        holder_name=investment.applicant.name,
        plot=plot,
        investment=investment,
        sector=investment.sector or (plot.sector if plot else None),
        reference=investment.contract_number,
        area_m2=investment.offer_area_m2 or investment.requested_area_m2,
        start_date=start,
        end_date=end,
        assigned_to=investment.assigned_to,
    )
    log(
        enums.Action.CREATED,
        land_use=land_use,
        detail=_("Dari permintaan investasi %s") % investment.number,
    )
    ensure_records(land_use)
    return land_use


def end_land_uses_for_plots(plot_ids, actor=None) -> int:
    """Sewa diakhiri dari data lahan: pemanfaatan sewa/kerja sama ikut berakhir."""
    land_uses = LandUse.objects.filter(
        plot_id__in=plot_ids,
        status=enums.LandUseStatus.ACTIVE,
        scheme__in=(enums.Scheme.LEASE, enums.Scheme.PARTNERSHIP),
    )
    count = 0
    for land_use in land_uses:
        land_use.status = enums.LandUseStatus.ENDED
        land_use.end_date = min(
            land_use.end_date or timezone.localdate(), timezone.localdate()
        )
        land_use.save(update_fields=["status", "end_date", "modified_at"])
        log(
            enums.Action.STATUS,
            actor=actor,
            land_use=land_use,
            detail=_("Sewa diakhiri."),
        )
        count += 1
    return count


# --------------------------------------------------------------------------
# Dokumen perizinan & versi
# --------------------------------------------------------------------------


def _lock_record(record: PermitRecord) -> PermitRecord:
    return (
        PermitRecord.objects.select_for_update(of=("self",))
        .select_related("land_use", "permit_type")
        .get(pk=record.pk)
    )


def validate_upload(upload) -> None:
    require(upload is not None, _("Pilih berkas."))
    extension = os.path.splitext(upload.name or "")[1].lower().lstrip(".")
    require(
        extension in DOCUMENT_EXTENSIONS,
        _("Format berkas harus salah satu dari: %s.") % ", ".join(DOCUMENT_EXTENSIONS),
    )
    require(upload.size <= MAX_UPLOAD_BYTES, _("Ukuran berkas maksimal 20 MB."))
    from file_operations.validators import validate_file_signature

    validate_file_signature(upload)


def add_version(
    record: PermitRecord,
    upload,
    *,
    user,
    source: str,
    note: str = "",
    request=None,
    original_name: str = "",
) -> DocumentVersion:
    """Simpan berkas sebagai versi berikutnya. ``upload`` = UploadedFile atau ContentFile."""
    last = record.versions.order_by("-number").values_list("number", flat=True).first()
    name = os.path.basename(original_name or getattr(upload, "name", "") or "dokumen")[
        :200
    ]
    digest, size = file_digest(upload)
    version = DocumentVersion(
        record=record,
        number=(last or 0) + 1,
        original_name=name,
        size=size,
        sha256=digest,
        source=source,
        note=(note or "")[:2000],
        uploaded_by=user if user is not None and user.pk else None,
    )
    version.file.save(name, upload, save=False)
    version.save()
    log(
        enums.Action.UPLOADED,
        actor=user,
        request=request,
        record=record,
        detail=_("Versi %(n)s: %(name)s (%(source)s)")
        % {"n": version.number, "name": name, "source": version.get_source_display()},
    )
    return version


def _apply_dates(record, number, issued_date, expiry_date):
    if number is not None:
        record.number = (number or "").strip()[:128]
    if issued_date is not None:
        record.issued_date = issued_date or None
    if expiry_date is not None:
        record.expiry_date = expiry_date or None
    if record.issued_date and not record.expiry_date:
        record.expiry_date = record.default_expiry()
    require(
        not (
            record.issued_date
            and record.expiry_date
            and record.expiry_date < record.issued_date
        ),
        _("Masa berlaku berakhir sebelum tanggal terbit."),
    )
    if record.expiry_date != record.expiry_warned_for:
        record.expiry_warned_for = None


def _staff_recipients(record) -> list:
    land_use = record.land_use
    if land_use.assigned_to_id and land_use.assigned_to.email:
        return [land_use.assigned_to]
    from dokumen.access import users_with_perm

    return list(
        users_with_perm("dokumen.verify_permitrecord").exclude(is_superuser=True)[:20]
    )


def _notify_holder(record, subject, lines):
    holder = record.land_use.holder
    if holder is None or not holder.user_id:
        return
    from alokasi.services import portal_url

    body = "\n".join(
        [
            _("Yth. %s,") % holder.name,
            "",
            *lines,
            "",
            _("Lihat rincian: %s")
            % portal_url(f"dokumen/pemanfaatan/{record.land_use.number}/"),
        ]
    )
    on_commit_email([holder.user.email], subject, body)


@transaction.atomic
def holder_update(
    record: PermitRecord,
    user,
    *,
    upload=None,
    status: str = "",
    number=None,
    issued_date=None,
    expiry_date=None,
    note: str = "",
    request=None,
) -> PermitRecord:
    """Pemegang hak memperbarui status/nomor atau mengunggah versi baru."""
    record = _lock_record(record)
    require(
        record.land_use.status == enums.LandUseStatus.ACTIVE,
        _("Pemanfaatan lahan ini tidak aktif; dokumen tidak dapat diubah."),
    )
    _apply_dates(record, number, issued_date, expiry_date)
    record.holder_note = (note or "").strip()[:5000] or record.holder_note
    if upload is not None:
        validate_upload(upload)
        add_version(
            record,
            upload,
            user=user,
            source=enums.VersionSource.HOLDER,
            note=note,
            request=request,
        )
        record.status = RS.SUBMITTED
        record.save()
        log(
            enums.Action.STATUS,
            actor=user,
            request=request,
            record=record,
            detail=record.get_status_display(),
        )
        transaction.on_commit(lambda: _notify_staff_submitted(record))
        return record
    require(status in enums.HOLDER_RECORD_STATUSES, _("Pilih status yang valid."))
    require(
        record.status in (RS.NOT_STARTED, RS.IN_PROGRESS, RS.REVISION, RS.EXPIRED),
        _("Status dokumen ini diatur petugas. Unggah versi baru untuk memperbaruinya."),
    )
    previous = record.status
    record.status = status
    record.save()
    if previous != status:
        log(
            enums.Action.STATUS,
            actor=user,
            request=request,
            record=record,
            detail=record.get_status_display(),
        )
    return record


def _notify_staff_submitted(record):
    from django.urls import reverse

    url = absolute(reverse("admin:dokumen_permitrecord_change", args=[record.pk]))
    body = _(
        "%(holder)s mengunggah %(type)s untuk %(number)s (%(title)s). Mohon diverifikasi:\n%(url)s"
    ) % {
        "holder": record.land_use.holder_display,
        "type": record.permit_type.name,
        "number": record.land_use.number,
        "title": record.land_use.title,
        "url": url,
    }
    email_users(
        _staff_recipients(record),
        _("Dokumen menunggu verifikasi: %s") % record.permit_type.name,
        body,
    )


@transaction.atomic
def officer_upload(
    record,
    user,
    upload,
    *,
    note="",
    number=None,
    issued_date=None,
    expiry_date=None,
    verify_now=False,
    request=None,
) -> DocumentVersion:
    record = _lock_record(record)
    validate_upload(upload)
    _apply_dates(record, number, issued_date, expiry_date)
    version = add_version(
        record,
        upload,
        user=user,
        source=enums.VersionSource.OFFICER,
        note=note,
        request=request,
    )
    if verify_now:
        _set_verified(record, user, note, request)
    elif record.status in (RS.NOT_STARTED, RS.IN_PROGRESS, RS.REVISION, RS.EXPIRED):
        record.status = RS.SUBMITTED
        record.save()
        log(
            enums.Action.STATUS,
            actor=user,
            request=request,
            record=record,
            detail=record.get_status_display(),
        )
    else:
        record.save()
    return version


def _set_verified(record, user, note, request):
    record.status = RS.VERIFIED
    record.verified_by = user
    record.verified_at = timezone.now()
    if note:
        record.review_note = note[:5000]
    if record.expiry_date and record.expiry_date < timezone.localdate():
        record.status = RS.EXPIRED
    record.save()
    log(enums.Action.VERIFIED, actor=user, request=request, record=record, detail=note)
    _notify_holder(
        record,
        _("%s terverifikasi") % record.permit_type.name,
        [
            _("Dokumen %(type)s untuk %(number)s telah diverifikasi petugas.")
            % {"type": record.permit_type.name, "number": record.land_use.number}
        ]
        + ([_("Catatan: %s") % note] if note else []),
    )


@transaction.atomic
def verify(
    record,
    user,
    *,
    number=None,
    issued_date=None,
    expiry_date=None,
    note="",
    request=None,
):
    record = _lock_record(record)
    require(record.status != RS.VERIFIED, _("Dokumen ini sudah terverifikasi."))
    require(
        record.versions.exists() or bool((note or "").strip()),
        _(
            "Belum ada berkas. Tulis catatan dasar verifikasi (mis. diperiksa di sistem OSS)."
        ),
    )
    _apply_dates(record, number, issued_date, expiry_date)
    _set_verified(record, user, (note or "").strip(), request)
    return record


@transaction.atomic
def request_revision(record, user, note: str, request=None):
    record = _lock_record(record)
    note = (note or "").strip()
    require(bool(note), _("Tuliskan bagian yang perlu diperbaiki."))
    require(record.status != RS.WAIVED, _("Dokumen ini dinyatakan tidak wajib."))
    record.status = RS.REVISION
    record.review_note = note[:5000]
    record.save()
    log(enums.Action.REVISION, actor=user, request=request, record=record, detail=note)
    _notify_holder(
        record,
        _("%s perlu diperbaiki") % record.permit_type.name,
        [
            _("Petugas meminta perbaikan dokumen %(type)s untuk %(number)s:")
            % {"type": record.permit_type.name, "number": record.land_use.number},
            note,
        ],
    )
    return record


@transaction.atomic
def waive(record, user, note: str, request=None):
    record = _lock_record(record)
    note = (note or "").strip()
    require(bool(note), _("Tuliskan dasar dokumen ini tidak wajib."))
    record.status = RS.WAIVED
    record.review_note = note[:5000]
    record.verified_by = user
    record.verified_at = timezone.now()
    record.save()
    log(enums.Action.WAIVED, actor=user, request=request, record=record, detail=note)
    return record


@transaction.atomic
def reopen(record, user, note: str, request=None):
    record = _lock_record(record)
    note = (note or "").strip()
    require(bool(note), _("Tuliskan alasan membuka kembali."))
    require(
        record.status in (RS.VERIFIED, RS.WAIVED, RS.EXPIRED),
        _("Dokumen ini masih terbuka."),
    )
    record.status = RS.SUBMITTED if record.versions.exists() else RS.NOT_STARTED
    record.review_note = note[:5000]
    record.verified_by = None
    record.verified_at = None
    record.save()
    log(enums.Action.REOPENED, actor=user, request=request, record=record, detail=note)
    return record


def expire_records(today=None) -> list[PermitRecord]:
    today = today or timezone.localdate()
    expired = []
    for record in PermitRecord.objects.select_related("land_use", "permit_type").filter(
        status=RS.VERIFIED,
        expiry_date__lt=today,
        land_use__status=enums.LandUseStatus.ACTIVE,
    ):
        with transaction.atomic():
            record.status = RS.EXPIRED
            record.save(update_fields=["status", "modified_at"])
            log(
                enums.Action.EXPIRED,
                record=record,
                detail=_("Masa berlaku berakhir %s") % record.expiry_date,
            )
            _notify_holder(
                record,
                _("%s kedaluwarsa") % record.permit_type.name,
                [
                    _(
                        "Masa berlaku %(type)s untuk %(number)s telah berakhir. Unggah dokumen yang diperbarui."
                    )
                    % {
                        "type": record.permit_type.name,
                        "number": record.land_use.number,
                    }
                ],
            )
        expired.append(record)
    return expired


def warn_expiring(today=None, days=60) -> list[PermitRecord]:
    today = today or timezone.localdate()
    limit = today + datetime.timedelta(days=days)
    warned = []
    records = PermitRecord.objects.select_related(
        "land_use", "permit_type", "land_use__holder__user"
    ).filter(
        status=RS.VERIFIED,
        expiry_date__gte=today,
        expiry_date__lte=limit,
        land_use__status=enums.LandUseStatus.ACTIVE,
    )
    for record in records:
        if record.expiry_warned_for == record.expiry_date:
            continue
        with transaction.atomic():
            record.expiry_warned_for = record.expiry_date
            record.save(update_fields=["expiry_warned_for", "modified_at"])
            _notify_holder(
                record,
                _("%s akan kedaluwarsa") % record.permit_type.name,
                [
                    _(
                        "Masa berlaku %(type)s untuk %(number)s berakhir %(date)s "
                        "(%(days)s hari lagi). Segera perpanjang lalu unggah dokumen "
                        "terbaru."
                    )
                    % {
                        "type": record.permit_type.name,
                        "number": record.land_use.number,
                        "date": record.expiry_date.strftime("%d-%m-%Y"),
                        "days": (record.expiry_date - today).days,
                    }
                ],
            )
        warned.append(record)
    return warned


# --------------------------------------------------------------------------
# Templat
# --------------------------------------------------------------------------

CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


def safe_filename(text: str, extension: str) -> str:
    from django.utils.text import slugify

    stem = slugify(text)[:80] or "dokumen"
    return f"{stem}.{extension}"


def render_template(
    template: DocumentTemplate, *, land_use=None, record=None, extra=None, title=""
) -> tuple[bytes, str]:
    """Hasilkan berkas dari templat: (isi, nama berkas)."""
    from dokumen import pdf

    title = title or template.name
    context = merge.build_context(land_use=land_use, record=record, extra=extra)
    if template.kind == enums.TemplateKind.HTML:
        body = merge.merge_html(template.body, context)
        return pdf.template_pdf(title, body), safe_filename(title, "pdf")
    data = read_file(template.file)
    if template.kind == enums.TemplateKind.DOCX:
        return merge.render_docx(data, context), safe_filename(title, "docx")
    extension = (
        (template.original_name or template.file.name).rsplit(".", 1)[-1].lower()
    )
    return data, safe_filename(title, extension)


@transaction.atomic
def generate_version(
    record, user, template, *, extra=None, note="", request=None
) -> DocumentVersion:
    record = _lock_record(record)
    try:
        data, filename = render_template(
            template,
            record=record,
            extra=extra,
            title=f"{record.permit_type.name} {record.land_use.number}",
        )
    except merge.TemplateRenderError as error:
        raise ValidationError(str(error)) from error
    version = add_version(
        record,
        ContentFile(data, name=filename),
        user=user,
        source=enums.VersionSource.TEMPLATE,
        note=note or _("Dari templat %s") % template,
        request=request,
    )
    log(
        enums.Action.GENERATED,
        actor=user,
        request=request,
        record=record,
        detail=str(template),
    )
    return version


MAX_IMPORT_FILES = 50
MAX_IMPORT_TOTAL = 100 * 1024 * 1024
IMPORT_FILE_EXTENSIONS = {"pdf", "xlsx", "png", "jpg", "jpeg"}


def _stem(name: str) -> str:
    base = os.path.basename(name)
    stem = os.path.splitext(base)[0].replace("_", " ").replace("-", " ").strip()
    return (stem[:1].upper() + stem[1:])[:255] or _("Templat tanpa nama")


def _text_to_html(data: bytes, extension: str) -> str:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    if extension == "txt":
        from html import escape

        text = "".join(
            f"<p>{escape(line)}</p>" for line in text.splitlines() if line.strip()
        )
    return sanitize_html(text)


def _docx_html(name: str, data: bytes) -> str:
    try:
        return merge.docx_to_html(data)
    except merge.TemplateRenderError as error:
        raise ValidationError(f"{name}: {error}") from error


def _check_import_file(name: str, extension: str, data: bytes) -> None:
    from file_operations.validators import SIGNATURE_CHECKS

    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationError(_("%s lebih dari 20 MB.") % name)
    check = SIGNATURE_CHECKS.get(extension)
    if check is not None and not check(data[:1024]):
        raise ValidationError(_("Isi %s tidak sesuai dengan jenisnya.") % name)


def _import_one(
    name: str, data: bytes, *, user, category, docx_mode: str
) -> DocumentTemplate | None:
    extension = os.path.splitext(name)[1].lower().lstrip(".")
    _check_import_file(name, extension, data)
    template = DocumentTemplate(name=_stem(name), category=category, created_by=user)
    if extension in ("html", "htm", "txt") or (
        extension == "docx" and docx_mode == "html"
    ):
        if extension == "docx":
            template.body = _docx_html(name, data)
        else:
            template.body = _text_to_html(data, extension)
        require(bool(template.body), _("%s kosong setelah dibersihkan.") % name)
        template.kind = enums.TemplateKind.HTML
        template.save()
        return template
    if extension == "docx":
        _docx_html(name, data)  # validasi: berkas harus dapat dibaca
        template.kind = enums.TemplateKind.DOCX
    elif extension in IMPORT_FILE_EXTENSIONS:
        template.kind = enums.TemplateKind.FILE
    else:
        return None
    template.original_name = os.path.basename(name)[:255]
    template.file.save(template.original_name, ContentFile(data), save=False)
    template.save()
    return template


def _zip_entries(data: bytes):
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise ValidationError(_("Berkas ZIP rusak.")) from error
    entries = [
        info
        for info in archive.infolist()
        if not info.is_dir()
        and not os.path.basename(info.filename).startswith((".", "~$"))
        and "__MACOSX" not in info.filename
    ]
    require(
        len(entries) <= MAX_IMPORT_FILES,
        _("ZIP berisi lebih dari %d berkas.") % MAX_IMPORT_FILES,
    )
    require(
        sum(info.file_size for info in entries) <= MAX_IMPORT_TOTAL,
        _("Isi ZIP lebih dari 100 MB setelah diekstrak."),
    )
    for info in entries:
        require(
            info.file_size <= MAX_UPLOAD_BYTES,
            _("%s lebih dari 20 MB.") % info.filename,
        )
        yield info.filename, archive.read(info)


@transaction.atomic
def import_templates(
    uploads, *, user, category, docx_mode="docx"
) -> tuple[list, list[str]]:
    """Impor satu/banyak berkas (atau ZIP) menjadi templat. Kembalikan (templat, dilewati)."""
    created, skipped = [], []
    for upload in uploads:
        data = upload.read()
        name = upload.name or "templat"
        if name.lower().endswith(".zip"):
            entries = list(_zip_entries(data))
        else:
            entries = [(name, data)]
        for entry_name, entry_data in entries:
            template = _import_one(
                entry_name,
                entry_data,
                user=user,
                category=category,
                docx_mode=docx_mode,
            )
            if template is None:
                skipped.append(os.path.basename(entry_name))
            else:
                created.append(template)
    require(
        bool(created),
        _(
            "Tidak ada berkas yang dapat diimpor (format didukung: DOCX, HTML, TXT, "
            "PDF, XLSX, JPG, PNG, atau ZIP berisi berkas tersebut)."
        ),
    )
    return created, skipped
