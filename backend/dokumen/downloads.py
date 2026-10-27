"""Unduhan berkas dokumen lewat persetujuan.

Setiap unduhan (petugas maupun pemegang hak) wajib punya permintaan yang
disetujui pejabat berizin, berlaku terbatas waktu dan jumlah unduhnya, serta
dicatat lengkap (siapa, kapan, dari mana, sidik berkas). PDF diberi tanda air
identitas pengunduh agar salinan yang beredar dapat ditelusuri.
"""

import datetime
import mimetypes

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from alokasi.services import portal_url
from dokumen import access, enums, pdf
from dokumen.models import DocumentSettings, DownloadLog, DownloadRequest
from dokumen.services import (
    absolute,
    client_ip,
    log,
    on_commit_email,
    read_file,
    require,
    user_agent,
)

D = enums.DownloadStatus


def _target_land_use(dl: DownloadRequest):
    if dl.version_id:
        return dl.version.record.land_use
    return dl.signing.land_use


def _targets(dl: DownloadRequest) -> dict:
    targets = {"download": dl}
    if dl.version_id:
        targets["record"] = dl.version.record
    else:
        targets["signing"] = dl.signing
        if dl.signing.land_use_id:
            targets["land_use"] = dl.signing.land_use
    return targets


def download_url(dl: DownloadRequest, *, for_staff: bool) -> str:
    if for_staff:
        return absolute(reverse("dokumen-staff-download", args=[dl.number]))
    return portal_url(f"dokumen/unduh/{dl.number}/")


def _is_staff_user(user) -> bool:
    return bool(user.is_staff and access.applicant_of(user) is None)


def can_decide(user, dl: DownloadRequest) -> bool:
    if not user.has_perm(access.approver_permission(dl.confidentiality)):
        return False
    return dl.requester_id != user.pk or DocumentSettings.load().allow_self_approval


@transaction.atomic
def request_download(user, *, version=None, signing=None, purpose: str, reason: str, request=None) -> DownloadRequest:
    require(
        access.can_request_download(user, version=version, signing=signing),
        _("Anda tidak berhak meminta unduhan dokumen ini."),
    )
    reason = (reason or "").strip()
    require(len(reason) >= 5, _("Jelaskan alasan unduhan (minimal 5 karakter)."))
    require(purpose in enums.DownloadPurpose.values, _("Pilih keperluan unduhan."))
    open_requests = DownloadRequest.objects.filter(requester=user, version=version, signing=signing)
    for existing in open_requests.filter(status__in=(D.PENDING, D.APPROVED)):
        if existing.status == D.PENDING or existing.is_usable:
            return existing
    confidentiality = (
        version.record.permit_type.confidentiality if version is not None else signing.confidentiality
    )
    dl = DownloadRequest.objects.create(
        requester=user,
        version=version,
        signing=signing,
        confidentiality=confidentiality,
        purpose=purpose,
        reason=reason[:2000],
    )
    log(enums.Action.DOWNLOAD_REQUESTED, actor=user, request=request, detail=f"{dl.number}: {reason[:200]}", **_targets(dl))
    config = DocumentSettings.load()
    land_use = _target_land_use(dl)
    auto = (
        not config.applicant_needs_approval
        and confidentiality == enums.Confidentiality.NORMAL
        and access.is_holder(user, land_use)
    )
    if auto:
        _approve(dl, None, _("Disetujui otomatis sesuai pengaturan (dokumen milik sendiri)."), request=request)
        return dl
    approvers = access.users_with_perm(access.approver_permission(confidentiality))
    if not config.allow_self_approval:
        approvers = approvers.exclude(pk=user.pk)
    url = absolute(reverse("admin:dokumen_downloadrequest_change", args=[dl.pk]))
    on_commit_email(
        [u.email for u in approvers[:30]],
        _("Permintaan unduhan %s menunggu persetujuan") % dl.number,
        _(
            "%(user)s meminta mengunduh %(target)s.\nKeperluan: %(purpose)s\nAlasan: %(reason)s\n"
            "Sifat dokumen: %(level)s\n\nTinjau: %(url)s"
        )
        % {
            "user": access.display_name(user),
            "target": dl.target_label,
            "purpose": dl.get_purpose_display(),
            "reason": reason,
            "level": dl.get_confidentiality_display(),
            "url": url,
        },
    )
    return dl


def _approve(dl, approver, note, *, hours=None, max_count=None, request=None):
    config = DocumentSettings.load()
    hours = hours or config.download_valid_hours
    dl.status = D.APPROVED
    dl.decided_by = approver
    dl.decided_at = timezone.now()
    dl.decision_note = (note or "").strip()[:2000]
    dl.valid_until = dl.decided_at + datetime.timedelta(hours=hours)
    dl.max_downloads = max_count or config.download_max_count
    dl.save()
    log(enums.Action.DOWNLOAD_APPROVED, actor=approver, request=request, detail=f"{dl.number}: {dl.decision_note}", **_targets(dl))
    if dl.requester.email:
        on_commit_email(
            [dl.requester.email],
            _("Unduhan %s disetujui") % dl.number,
            _(
                "Permintaan unduh %(target)s disetujui. Berlaku sampai %(until)s WIB untuk %(count)s kali unduh.\n"
                "Unduh: %(url)s"
            )
            % {
                "target": dl.target_label,
                "until": timezone.localtime(dl.valid_until).strftime("%d-%m-%Y %H.%M"),
                "count": dl.max_downloads,
                "url": download_url(dl, for_staff=_is_staff_user(dl.requester)),
            },
        )


def _lock(dl: DownloadRequest) -> DownloadRequest:
    return DownloadRequest.objects.select_for_update().get(pk=dl.pk)


@transaction.atomic
def approve(dl, approver, *, note="", hours=None, max_count=None, request=None) -> DownloadRequest:
    dl = _lock(dl)
    require(dl.status == D.PENDING, _("Permintaan ini sudah diputuskan."))
    require(can_decide(approver, dl), _("Anda tidak berwenang menyetujui permintaan ini."))
    if hours is not None:
        require(1 <= hours <= 720, _("Masa berlaku 1–720 jam."))
    if max_count is not None:
        require(1 <= max_count <= 20, _("Batas unduh 1–20 kali."))
    _approve(dl, approver, note, hours=hours, max_count=max_count, request=request)
    return dl


@transaction.atomic
def reject(dl, approver, note: str, request=None) -> DownloadRequest:
    dl = _lock(dl)
    note = (note or "").strip()
    require(dl.status == D.PENDING, _("Permintaan ini sudah diputuskan."))
    require(can_decide(approver, dl), _("Anda tidak berwenang memutuskan permintaan ini."))
    require(bool(note), _("Tuliskan alasan penolakan."))
    dl.status = D.REJECTED
    dl.decided_by = approver
    dl.decided_at = timezone.now()
    dl.decision_note = note[:2000]
    dl.save()
    log(enums.Action.DOWNLOAD_REJECTED, actor=approver, request=request, detail=f"{dl.number}: {note}", **_targets(dl))
    if dl.requester.email:
        on_commit_email(
            [dl.requester.email],
            _("Unduhan %s ditolak") % dl.number,
            _("Permintaan unduh %(target)s ditolak.\nAlasan: %(note)s") % {"target": dl.target_label, "note": note},
        )
    return dl


@transaction.atomic
def cancel(dl, user, request=None) -> DownloadRequest:
    dl = _lock(dl)
    require(dl.requester_id == user.pk, _("Hanya pemohon yang dapat membatalkan."))
    require(dl.status in (D.PENDING, D.APPROVED), _("Permintaan ini sudah ditutup."))
    dl.status = D.CANCELLED
    dl.save()
    log(enums.Action.DOWNLOAD_CANCELLED, actor=user, request=request, detail=dl.number, **_targets(dl))
    return dl


def _source(dl):
    if dl.version_id:
        return dl.version.file, dl.version.original_name
    return dl.signing.final_file, f"{dl.signing.number}.pdf"


def _watermark_lines(user, dl) -> list[str]:
    stamp = timezone.localtime().strftime("%d-%m-%Y %H.%M")
    return [
        _("Diunduh %(name)s") % {"name": access.display_name(user)},
        f"{stamp} WIB · {dl.number}",
        _("Salinan terkendali – dilarang disebarluaskan tanpa izin"),
    ]


def consume(dl: DownloadRequest, user, request=None) -> tuple[bytes, str, str, bool]:
    """Periksa izin lalu kurangi kuota; kembalikan (isi, nama, tipe, bertanda air)."""
    with transaction.atomic():
        dl = DownloadRequest.objects.select_for_update().select_related(
            "version__record__land_use", "signing__land_use"
        ).get(pk=dl.pk)
        if dl.requester_id != user.pk:
            raise PermissionDenied
        require(dl.status == D.APPROVED, _("Permintaan unduh belum disetujui."))
        require(not dl.is_expired, _("Izin unduh sudah kedaluwarsa. Ajukan permintaan baru."))
        require(dl.remaining > 0, _("Kuota unduh sudah habis. Ajukan permintaan baru."))
        version, signing = dl.version, dl.signing
        require(
            access.can_request_download(user, version=version, signing=signing),
            _("Anda tidak lagi berhak atas dokumen ini."),
        )
        fieldfile, filename = _source(dl)
        data = read_file(fieldfile)
        watermarked = False
        if DocumentSettings.load().watermark and filename.lower().endswith(".pdf"):
            try:
                data = pdf.watermark(data, _watermark_lines(user, dl))
                watermarked = True
            except pdf.PdfReadError:
                watermarked = False
        dl.download_count += 1
        dl.save(update_fields=["download_count"])
        DownloadLog.objects.create(
            user=user,
            user_name=access.display_name(user)[:255],
            request=dl,
            version=version,
            signing=signing,
            filename=filename[:255],
            sha256=pdf.sha256(data),
            watermarked=watermarked,
            ip_address=client_ip(request),
            user_agent=user_agent(request),
        )
        log(enums.Action.DOWNLOADED, actor=user, request=request, detail=f"{dl.number} ({dl.download_count}/{dl.max_downloads}) {filename}", **_targets(dl))
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return data, filename, content_type, watermarked


def log_preview(user, *, version=None, signing=None, template=None, filename="", data=b"", request=None, preview=True):
    DownloadLog.objects.create(
        user=user,
        user_name=access.display_name(user)[:255],
        version=version,
        signing=signing,
        template=template,
        is_preview=preview,
        filename=(filename or "-")[:255],
        sha256=pdf.sha256(data) if data else "",
        ip_address=client_ip(request),
        user_agent=user_agent(request),
    )
    targets = {}
    if version is not None:
        targets["record"] = version.record
    if signing is not None:
        targets["signing"] = signing
    if targets:
        log(enums.Action.PREVIEWED if preview else enums.Action.DOWNLOADED, actor=user, request=request, detail=filename, **targets)


def pending_for(user):
    """Permintaan menunggu yang dapat diputuskan pengguna ini."""
    queryset = DownloadRequest.objects.filter(status=D.PENDING)
    if not user.has_perm("dokumen.approve_confidential_download"):
        queryset = queryset.exclude(confidentiality=enums.Confidentiality.SECRET)
    if not user.has_perm("dokumen.approve_downloadrequest"):
        queryset = queryset.filter(confidentiality=enums.Confidentiality.SECRET)
    if not DocumentSettings.load().allow_self_approval:
        queryset = queryset.exclude(requester=user)
    return queryset
