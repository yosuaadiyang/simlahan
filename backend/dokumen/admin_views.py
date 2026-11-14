"""Halaman petugas di /admin/dokumen/…: dasbor, unduhan lewat persetujuan,
pratinjau verifikasi, dan formulir permintaan unduh."""

import datetime
import functools

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Avg, Count, F, Q
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from asetlahan.admin_views import bars
from dokumen import access, downloads, enums, pdf, services
from dokumen.forms import DownloadRequestForm
from dokumen.models import (
    Activity,
    DocumentVersion,
    DownloadLog,
    DownloadRequest,
    LandUse,
    PermitRecord,
    SigningDocument,
)
from dokumen.views import file_response, serve_download
from file_operations.errors import FileScanError, FileScanPendingError, FileUnsafeError

TOOLS = (
    ("dokumen-dashboard", _("Dasbor"), "dokumen.view_landuse"),
    (
        "admin:dokumen_landuse_changelist",
        _("Pemanfaatan lahan"),
        "dokumen.view_landuse",
    ),
    (
        "admin:dokumen_permitrecord_changelist",
        _("Dokumen perizinan"),
        "dokumen.view_permitrecord",
    ),
    (
        "admin:dokumen_signingdocument_changelist",
        _("Tanda tangan elektronik"),
        "dokumen.view_signingdocument",
    ),
    (
        "admin:dokumen_documenttemplate_changelist",
        _("Templat"),
        "dokumen.view_documenttemplate",
    ),
    (
        "admin:dokumen_downloadrequest_changelist",
        _("Permintaan unduh"),
        "dokumen.view_downloadrequest",
    ),
    (
        "admin:dokumen_activity_changelist",
        _("Jejak aktivitas"),
        "dokumen.view_activity",
    ),
)


def tools(user) -> list[dict]:
    return [
        {"url": reverse(name), "label": label, "name": name}
        for name, label, perm in TOOLS
        if user.has_perm(perm)
    ]


def officer_view(*perms):
    def decorator(view):
        @staff_member_required
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            if perms and not any(request.user.has_perm(p) for p in perms):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def render(request, template, title, context=None):
    return TemplateResponse(
        request,
        template,
        {
            **admin.site.each_context(request),
            "title": title,
            "tools": tools(request.user),
            "current": (
                request.resolver_match.url_name if request.resolver_match else ""
            ),
            **(context or {}),
        },
    )


COLOR = {
    "belum": "#9a6700",
    "proses": "#0a7ea4",
    "diajukan": "#1f6feb",
    "perbaikan": "#bf8700",
    "terverifikasi": "#1a7f37",
    "kedaluwarsa": "#cf222e",
    "tidak_wajib": "#6e7781",
    "draf": "#6e7781",
    "menunggu_persetujuan": "#8250df",
    "disetujui": "#0a7ea4",
    "dikirim": "#1f6feb",
    "dilihat": "#0969da",
    "selesai": "#1a7f37",
    "ditolak": "#cf222e",
    "dibatalkan": "#6e7781",
}


def _records_section():
    today = timezone.localdate()
    RS = enums.RecordStatus
    active = PermitRecord.objects.filter(land_use__status=enums.LandUseStatus.ACTIVE)
    counts = dict(active.values_list("status").annotate(n=Count("pk")))
    expiring = active.filter(status=RS.VERIFIED, expiry_date__gte=today)
    return {
        "bars": bars([(k, label, counts.get(k, 0)) for k, label in RS.choices], COLOR),
        "waiting": counts.get(RS.SUBMITTED, 0),
        "revision": counts.get(RS.REVISION, 0),
        "expired": counts.get(RS.EXPIRED, 0),
        "expiring_30": expiring.filter(
            expiry_date__lte=today + datetime.timedelta(days=30)
        ).count(),
        "expiring_90": expiring.filter(
            expiry_date__lte=today + datetime.timedelta(days=90)
        ).count(),
        "soon": list(
            expiring.filter(expiry_date__lte=today + datetime.timedelta(days=60))
            .select_related("land_use", "permit_type")
            .order_by("expiry_date")[:8]
        ),
        "queue": list(
            active.filter(status=RS.SUBMITTED)
            .select_related("land_use", "permit_type")
            .order_by("modified_at")[:8]
        ),
    }


def _land_use_section():
    active = LandUse.objects.filter(status=enums.LandUseStatus.ACTIVE)
    incomplete = active.filter(
        records__permit_type__is_required=True,
        records__status__in=[
            s for s in enums.RecordStatus.values if s not in enums.DONE_RECORD_STATUSES
        ],
    ).distinct()
    schemes = dict(active.values_list("scheme").annotate(n=Count("pk")))
    return {
        "active": active.count(),
        "incomplete": incomplete.count(),
        "bars": bars(
            [(k, label, schemes.get(k, 0)) for k, label in enums.Scheme.choices]
        ),
    }


def _signing_section():
    S = enums.SigningStatus
    counts = dict(SigningDocument.objects.values_list("status").annotate(n=Count("pk")))
    month_start = timezone.localdate().replace(day=1)
    done = SigningDocument.objects.filter(
        status=S.COMPLETED, sent_at__isnull=False, completed_at__isnull=False
    )
    duration = done.aggregate(avg=Avg(F("completed_at") - F("sent_at")))["avg"]
    return {
        "bars": bars([(k, label, counts.get(k, 0)) for k, label in S.choices], COLOR),
        "open": counts.get(S.SENT, 0) + counts.get(S.VIEWED, 0),
        "approval": counts.get(S.PENDING_APPROVAL, 0),
        "completed_month": done.filter(completed_at__date__gte=month_start).count(),
        "avg_days": round(duration.total_seconds() / 86400, 1) if duration else None,
    }


def _download_section(user):
    since = timezone.now() - datetime.timedelta(days=30)
    return {
        "pending_mine": (
            downloads.pending_for(user).count()
            if user.has_perm("dokumen.approve_downloadrequest")
            or user.has_perm("dokumen.approve_confidential_download")
            else None
        ),
        "pending": DownloadRequest.objects.filter(
            status=enums.DownloadStatus.PENDING
        ).count(),
        "approved_30": DownloadRequest.objects.filter(
            status=enums.DownloadStatus.APPROVED, decided_at__gte=since
        ).count(),
        "rejected_30": DownloadRequest.objects.filter(
            status=enums.DownloadStatus.REJECTED, decided_at__gte=since
        ).count(),
        "downloads_30": DownloadLog.objects.filter(
            is_preview=False, created_at__gte=since
        ).count(),
    }


@officer_view(
    "dokumen.view_landuse",
    "dokumen.view_signingdocument",
    "dokumen.view_downloadrequest",
)
def dashboard(request):
    user = request.user
    context = {
        "records": (
            _records_section() if user.has_perm("dokumen.view_permitrecord") else None
        ),
        "land_uses": (
            _land_use_section() if user.has_perm("dokumen.view_landuse") else None
        ),
        "signing": (
            _signing_section()
            if user.has_perm("dokumen.view_signingdocument")
            else None
        ),
        "downloads": (
            _download_section(user)
            if user.has_perm("dokumen.view_downloadrequest")
            else None
        ),
        "activities": (
            Activity.objects.select_related(
                "land_use", "signing", "record__permit_type"
            )[:15]
            if user.has_perm("dokumen.view_activity")
            else []
        ),
        "my_tasks": _staff_tasks(user),
    }
    return render(
        request,
        "admin/dokumen/dashboard.html",
        _("Dasbor dokumen & perizinan"),
        context,
    )


def _staff_tasks(user):
    from dokumen import signing

    tasks = []
    for recipient in user.signing_tasks.filter(
        document__status__in=enums.OPEN_SIGNING_STATUSES
    ).select_related("document"):
        if signing.is_turn(recipient):
            tasks.append(recipient)
    return tasks


@staff_member_required
def staff_download(request, number):
    dl = get_object_or_404(DownloadRequest, number=number, requester=request.user)
    return serve_download(
        request, dl, reverse("admin:dokumen_downloadrequest_change", args=[dl.pk])
    )


@officer_view("dokumen.verify_permitrecord")
def version_preview(request, pk):
    """Pratinjau berkas untuk verifikasi (PDF bertanda air / gambar), tercatat."""
    version = get_object_or_404(
        DocumentVersion.objects.select_related(
            "record__land_use", "record__permit_type"
        ),
        pk=pk,
    )
    back = reverse("admin:dokumen_permitrecord_change", args=[version.record_id])
    if not access.can_view_record(request.user, version.record):
        raise PermissionDenied
    if not access.can_preview_confidential(
        request.user, version.record.permit_type.confidentiality
    ):
        messages.error(
            request,
            _(
                "Dokumen rahasia hanya dapat dibuka lewat permintaan unduh yang "
                "disetujui pejabat berwenang."
            ),
        )
        return redirect(back)
    extension = version.extension
    if extension not in ("pdf", "png", "jpg", "jpeg"):
        messages.error(
            request,
            _(
                "Pratinjau hanya untuk PDF dan gambar. Ajukan permintaan unduh untuk berkas ini."
            ),
        )
        return redirect(back)
    try:
        data = services.read_file(version.file)
        if extension == "pdf":
            stamp = timezone.localtime().strftime("%d-%m-%Y %H.%M")
            data = pdf.watermark(
                data,
                [_("PRATINJAU VERIFIKASI"), f"{request.user.get_username()} · {stamp}"],
            )
    except FileNotFoundError:
        messages.error(request, _("Berkas tidak ditemukan di penyimpanan."))
        return redirect(back)
    except (FileScanPendingError, FileUnsafeError, FileScanError):
        messages.error(request, _("Berkas belum lolos pemindaian virus."))
        return redirect(back)
    except pdf.PdfReadError:
        messages.error(
            request,
            _(
                "PDF tidak dapat dibuka (rusak atau terkunci sandi). Ajukan permintaan unduh."
            ),
        )
        return redirect(back)
    downloads.log_preview(
        request.user,
        version=version,
        filename=version.original_name,
        data=data,
        request=request,
    )
    content_type = services.CONTENT_TYPES.get(extension, "application/octet-stream")
    return file_response(data, version.original_name, content_type, inline=True)


@staff_member_required
def staff_request_download(request, kind, pk):
    if kind == "versi":
        version = get_object_or_404(
            DocumentVersion.objects.select_related(
                "record__land_use", "record__permit_type"
            ),
            pk=pk,
        )
        target = {"version": version}
        back = reverse("admin:dokumen_permitrecord_change", args=[version.record_id])
        label = f"{version.record.permit_type} v{version.number} – {version.record.land_use}"
        level = version.record.permit_type.get_confidentiality_display()
    elif kind == "dokumen":
        document = get_object_or_404(SigningDocument, pk=pk)
        target = {"signing": document}
        back = reverse("admin:dokumen_signingdocument_change", args=[pk])
        label = str(document)
        level = document.get_confidentiality_display()
    else:
        raise PermissionDenied
    form = DownloadRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            dl = downloads.request_download(
                request.user,
                purpose=form.cleaned_data["purpose"],
                reason=form.cleaned_data["reason"],
                request=request,
                **target,
            )
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
        else:
            messages.success(
                request,
                (
                    _("Permintaan %s dikirim ke pemberi persetujuan.") % dl.number
                    if not dl.is_usable
                    else _("Unduhan %s siap.") % dl.number
                ),
            )
            return redirect("admin:dokumen_downloadrequest_change", dl.pk)
    return render(
        request,
        "admin/dokumen/request_download.html",
        _("Minta izin unduh"),
        {"form": form, "back_url": back, "label": label, "level": level},
    )


def other_counts(user) -> dict:
    """Ringkasan kecil untuk halaman indeks aplikasi."""
    result = {}
    if user.has_perm("dokumen.verify_permitrecord"):
        result["waiting"] = PermitRecord.objects.filter(
            status=enums.RecordStatus.SUBMITTED
        ).count()
    if user.has_perm("dokumen.approve_downloadrequest") or user.has_perm(
        "dokumen.approve_confidential_download"
    ):
        result["downloads"] = downloads.pending_for(user).count()
    if user.has_perm("dokumen.approve_signingdocument"):
        result["approvals"] = (
            SigningDocument.objects.filter(status=enums.SigningStatus.PENDING_APPROVAL)
            .exclude(Q(created_by=user))
            .count()
        )
    return result
