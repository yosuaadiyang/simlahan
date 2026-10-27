"""Portal dokumen & perizinan (/portal/dokumen/): pemegang hak, penanda tangan
dokumen elektronik, unduhan lewat persetujuan, dan verifikasi keaslian publik."""

import hashlib

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from alokasi.views import _throttled, _too_many, applicant_required
from dokumen import access, downloads, enums, merge, services, signing
from dokumen.forms import (
    CommentForm,
    DeclineForm,
    DownloadRequestForm,
    HashCheckForm,
    HolderRecordForm,
    OtpForm,
    SignForm,
)
from dokumen.models import (
    DocumentRecipient,
    DocumentVersion,
    DownloadLog,
    DownloadRequest,
    LandUse,
    PermitRecord,
    SigningDocument,
)
from file_operations.errors import FileScanError, FileScanPendingError, FileUnsafeError


def _errors(error: ValidationError) -> str:
    return " ".join(error.messages)


def file_response(
    data: bytes, filename: str, content_type: str, *, inline=False
) -> HttpResponse:
    response = HttpResponse(data, content_type=content_type)
    response["Content-Disposition"] = content_disposition_header(not inline, filename)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


def serve_download(request, dl: DownloadRequest, fallback: str) -> HttpResponse:
    """Unduh berkas lewat permintaan yang disetujui (dipakai portal & panel)."""
    try:
        data, filename, content_type, _marked = downloads.consume(
            dl, request.user, request=request
        )
    except ValidationError as error:
        messages.error(request, _errors(error))
        return redirect(fallback)
    except FileNotFoundError:
        messages.error(
            request, _("Berkas tidak ditemukan di penyimpanan. Hubungi petugas.")
        )
        return redirect(fallback)
    except FileScanPendingError:
        messages.error(request, _("Berkas masih menunggu pemindaian virus."))
        return redirect(fallback)
    except (FileUnsafeError, FileScanError):
        messages.error(request, _("Berkas tidak aman untuk diunduh."))
        return redirect(fallback)
    return file_response(data, filename, content_type)


# --------------------------------------------------------------------------
# Pemegang hak
# --------------------------------------------------------------------------


def _my_signing_tasks(user):
    tasks = []
    for recipient in DocumentRecipient.objects.filter(
        user=user, document__status__in=enums.OPEN_SIGNING_STATUSES
    ).select_related("document"):
        if signing.is_turn(recipient):
            tasks.append(recipient)
    return tasks


def portal_summary(applicant, user) -> dict:
    """Ringkasan untuk kartu "Dokumen & perizinan" di halaman Akun Saya."""
    records = PermitRecord.objects.filter(
        land_use__holder=applicant, land_use__status=enums.LandUseStatus.ACTIVE
    )
    return {
        "land_uses": LandUse.objects.filter(holder=applicant).count(),
        "revision": records.filter(status=enums.RecordStatus.REVISION).count(),
        "expired": records.filter(status=enums.RecordStatus.EXPIRED).count(),
        "missing": records.filter(
            permit_type__is_required=True,
            status__in=(enums.RecordStatus.NOT_STARTED, enums.RecordStatus.IN_PROGRESS),
        ).count(),
        "tasks": len(_my_signing_tasks(user)),
        "downloads_ready": sum(
            1
            for dl in DownloadRequest.objects.filter(
                requester=user, status=enums.DownloadStatus.APPROVED
            )
            if dl.is_usable
        ),
    }


@applicant_required
def index(request):
    land_uses = list(
        LandUse.objects.filter(holder=request.applicant)
        .select_related("plot")
        .order_by("status", "-created_at")
    )
    for land_use in land_uses:
        land_use.summary = land_use.progress()
    documents = (
        SigningDocument.objects.filter(
            Q(land_use__holder=request.applicant) | Q(recipients__user=request.user)
        )
        .exclude(
            status__in=(
                enums.SigningStatus.DRAFT,
                enums.SigningStatus.PENDING_APPROVAL,
                enums.SigningStatus.APPROVED,
            )
        )
        .distinct()
        .order_by("-created_at")[:30]
    )
    context = {
        "land_uses": land_uses,
        "tasks": _my_signing_tasks(request.user),
        "documents": documents,
        "requests": DownloadRequest.objects.filter(requester=request.user)
        .select_related(
            "version__record__permit_type", "version__record__land_use", "signing"
        )
        .order_by("-created_at")[:10],
    }
    return render(request, "dokumen/portal/index.html", context)


def _own_land_use(request, number) -> LandUse:
    return get_object_or_404(
        LandUse.objects.select_related("plot", "holder", "sector"),
        number=number,
        holder=request.applicant,
    )


def _render_land_use(request, land_use, *, failed=None, failed_form=None):
    records = list(
        land_use.records.select_related(
            "permit_type", "permit_type__template"
        ).prefetch_related("versions")
    )
    is_active = land_use.status == enums.LandUseStatus.ACTIVE
    for record in records:
        record.form = (
            (
                failed_form
                if failed is not None and failed.pk == record.pk
                else HolderRecordForm(
                    prefix=f"r{record.pk}",
                    initial={
                        "number": record.number,
                        "issued_date": record.issued_date,
                        "expiry_date": record.expiry_date,
                    },
                )
            )
            if is_active
            else None
        )
        record.version_list = sorted(record.versions.all(), key=lambda v: -v.number)
    # Hanya riwayat dokumen perizinan; aktivitas internal dokumen tanda tangan & unduhan tidak ditampilkan.
    activities = (
        land_use.activities.filter(download__isnull=True, signing__isnull=True)
        .exclude(action__in=(enums.Action.PREVIEWED, enums.Action.DOWNLOADED))
        .select_related("record__permit_type")[:30]
    )
    context = {
        "land_use": land_use,
        "records": records,
        "summary": land_use.progress(),
        "is_active": is_active,
        "documents": land_use.signing_documents.exclude(
            status__in=(
                enums.SigningStatus.DRAFT,
                enums.SigningStatus.PENDING_APPROVAL,
                enums.SigningStatus.APPROVED,
            )
        ).order_by("-created_at"),
        "activities": activities,
        "download_form": DownloadRequestForm(),
        "my_requests": {
            r.version_id: r
            for r in DownloadRequest.objects.filter(
                requester=request.user, version__record__land_use=land_use
            ).order_by("created_at")
        },
    }
    return render(
        request,
        "dokumen/portal/land_use.html",
        context,
        status=400 if failed_form else 200,
    )


@applicant_required
def land_use_detail(request, number):
    return _render_land_use(request, _own_land_use(request, number))


def _own_record(request, pk) -> PermitRecord:
    return get_object_or_404(
        PermitRecord.objects.select_related("land_use", "permit_type"),
        pk=pk,
        land_use__holder=request.applicant,
    )


@applicant_required
@require_POST
def record_update(request, pk):
    record = _own_record(request, pk)
    land_use = record.land_use
    form = HolderRecordForm(request.POST, request.FILES, prefix=f"r{record.pk}")
    if form.is_valid():
        data = form.cleaned_data
        try:
            services.holder_update(
                record,
                request.user,
                upload=data["file"],
                status=data["status"],
                number=data["number"],
                issued_date=data["issued_date"],
                expiry_date=data["expiry_date"],
                note=data["note"],
                request=request,
            )
        except ValidationError as error:
            form.add_error(None, _errors(error))
        else:
            messages.success(
                request,
                (
                    _("Dokumen diunggah dan menunggu verifikasi petugas.")
                    if data["file"]
                    else _("Status dokumen diperbarui.")
                ),
            )
            return redirect(
                f"{reverse('dokumen_portal:land_use', args=[land_use.number])}#izin-{record.pk}"
            )
    return _render_land_use(request, land_use, failed=record, failed_form=form)


@applicant_required
def template_download(request, pk):
    """Unduh format/templat dokumen (terisi data sendiri) — tidak perlu persetujuan."""
    record = _own_record(request, pk)
    template = record.permit_type.template
    if template is None or not template.is_active:
        raise Http404
    try:
        data, filename = services.render_template(template, record=record)
    except (merge.TemplateRenderError, OSError):
        messages.error(
            request, _("Format dokumen belum dapat dibuat. Hubungi petugas.")
        )
        return redirect("dokumen_portal:land_use", number=record.land_use.number)
    downloads.log_preview(
        request.user,
        template=template,
        filename=filename,
        data=data,
        request=request,
        preview=False,
    )
    content_type = services.CONTENT_TYPES.get(
        filename.rsplit(".", 1)[-1], "application/octet-stream"
    )
    return file_response(data, filename, content_type)


def _create_request(request, *, version=None, signing_doc=None, fallback):
    form = DownloadRequestForm(request.POST)
    if not form.is_valid():
        messages.error(
            request, _("Lengkapi keperluan dan alasan unduhan (minimal 5 karakter).")
        )
        return redirect(fallback)
    try:
        dl = downloads.request_download(
            request.user,
            version=version,
            signing=signing_doc,
            purpose=form.cleaned_data["purpose"],
            reason=form.cleaned_data["reason"],
            request=request,
        )
    except ValidationError as error:
        messages.error(request, _errors(error))
        return redirect(fallback)
    if dl.is_usable:
        messages.success(request, _("Unduhan %s siap. Klik Unduh.") % dl.number)
    else:
        messages.success(
            request,
            _("Permintaan unduh %s dikirim dan menunggu persetujuan petugas berwenang.")
            % dl.number,
        )
    return redirect("dokumen_portal:downloads")


@applicant_required
@require_POST
def request_version_download(request, pk):
    version = get_object_or_404(
        DocumentVersion.objects.select_related(
            "record__land_use", "record__permit_type"
        ),
        pk=pk,
        record__land_use__holder=request.applicant,
    )
    fallback = reverse("dokumen_portal:land_use", args=[version.record.land_use.number])
    return _create_request(request, version=version, fallback=fallback)


@applicant_required
def downloads_list(request):
    requests = DownloadRequest.objects.filter(requester=request.user).select_related(
        "version__record__permit_type", "version__record__land_use", "signing"
    )
    return render(
        request, "dokumen/portal/downloads.html", {"requests": requests[:100]}
    )


@applicant_required
@require_POST
def download_cancel(request, number):
    dl = get_object_or_404(DownloadRequest, number=number, requester=request.user)
    try:
        downloads.cancel(dl, request.user, request=request)
    except ValidationError as error:
        messages.error(request, _errors(error))
    else:
        messages.success(request, _("Permintaan %s dibatalkan.") % dl.number)
    return redirect("dokumen_portal:downloads")


@applicant_required
def download(request, number):
    dl = get_object_or_404(DownloadRequest, number=number, requester=request.user)
    return serve_download(request, dl, reverse("dokumen_portal:downloads"))


# --------------------------------------------------------------------------
# Dokumen tanda tangan (pemegang hak / penerima ber-akun)
# --------------------------------------------------------------------------


def _visible_document(request, number) -> SigningDocument:
    if not request.user.is_authenticated:
        raise PermissionDenied
    document = get_object_or_404(
        SigningDocument.objects.select_related("land_use"), number=number
    )
    if not access.can_view_signing(request.user, document):
        raise Http404
    return document


@applicant_required
def signing_detail(request, number):
    document = _visible_document(request, number)
    mine = document.recipients.filter(user=request.user).first()
    context = {
        "document": document,
        "recipients": document.recipients.order_by("order", "pk"),
        "comments": document.comments.filter(is_internal=False).order_by("created_at"),
        "comment_form": CommentForm(),
        "download_form": DownloadRequestForm(),
        "my_recipient": mine,
        "my_turn": mine is not None and signing.is_turn(mine),
        "can_request": access.can_request_download(request.user, signing=document),
        "my_requests": DownloadRequest.objects.filter(
            requester=request.user, signing=document
        ).order_by("-created_at")[:5],
    }
    return render(request, "dokumen/portal/signing_detail.html", context)


@applicant_required
@require_POST
def signing_comment(request, number):
    document = _visible_document(request, number)
    form = CommentForm(request.POST)
    if form.is_valid():
        try:
            signing.add_comment(
                document, request.user, form.cleaned_data["body"], request=request
            )
        except ValidationError as error:
            messages.error(request, _errors(error))
        else:
            messages.success(request, _("Komentar terkirim."))
    else:
        messages.error(request, _("Komentar tidak boleh kosong."))
    return redirect(
        f"{reverse('dokumen_portal:signing_detail', args=[number])}#komentar"
    )


@applicant_required
@require_POST
def request_signing_download(request, number):
    document = _visible_document(request, number)
    fallback = reverse("dokumen_portal:signing_detail", args=[number])
    return _create_request(request, signing_doc=document, fallback=fallback)


# --------------------------------------------------------------------------
# Halaman tanda tangan bertoken (penerima ber-akun maupun tanpa akun)
# --------------------------------------------------------------------------


def _recipient(token) -> DocumentRecipient:
    return get_object_or_404(
        DocumentRecipient.objects.select_related(
            "document", "document__land_use", "user"
        ),
        token=token,
    )


def _gate(request, recipient):
    """Penerima ber-akun wajib masuk dengan akun tersebut."""
    if recipient.user_id is None:
        return None
    if not request.user.is_authenticated:
        login = (
            reverse("admin:login")
            if recipient.user.is_staff
            else reverse("portal:login")
        )
        return redirect(f"{login}?next={request.get_full_path()}")
    if request.user.pk != recipient.user_id:
        return render(
            request,
            "dokumen/portal/wrong_account.html",
            {"recipient": recipient},
            status=403,
        )
    return None


def _mask_email(email: str) -> str:
    name, _at, domain = email.partition("@")
    return f"{name[:2]}{'*' * max(len(name) - 2, 1)}@{domain}"


def _sign_context(request, recipient, **extra):
    document = recipient.document
    verified = signing.otp_ok(recipient)
    return {
        "recipient": recipient,
        "document": document,
        "recipients": document.recipients.order_by("order", "pk"),
        "verified": verified,
        "my_turn": signing.is_turn(recipient),
        "masked_email": _mask_email(recipient.email),
        "otp_form": extra.pop("otp_form", OtpForm()),
        "sign_form": extra.pop(
            "sign_form",
            SignForm(initial={"name": recipient.signature_name or recipient.name}),
        ),
        "decline_form": extra.pop("decline_form", DeclineForm()),
        "comment_form": extra.pop("comment_form", CommentForm()),
        "comments": document.comments.filter(is_internal=False).order_by("created_at"),
        "show_content": verified
        and document.status not in (enums.SigningStatus.CANCELLED,),
        **extra,
    }


def _sign_send_code(request, recipient):
    signing.send_otp(recipient, request=request)
    messages.success(
        request, _("Kode verifikasi dikirim ke %s.") % _mask_email(recipient.email)
    )
    return None


def _sign_check_code(request, recipient):
    form = OtpForm(request.POST)
    if form.is_valid() and signing.check_otp(recipient, form.cleaned_data["code"]):
        messages.success(request, _("Kode cocok. Silakan tinjau dokumen."))
        return None
    form.add_error(None, _("Kode salah atau kedaluwarsa. Minta kode baru bila perlu."))
    return {"otp_form": form}


def _sign_comment(request, recipient):
    form = CommentForm(request.POST)
    if not form.is_valid():
        return {"comment_form": form}
    signing.add_comment(
        recipient.document,
        request.user,
        form.cleaned_data["body"],
        request=request,
        author_name=recipient.name,
    )
    messages.success(request, _("Komentar terkirim."))
    return None


def _sign_decline(request, recipient):
    form = DeclineForm(request.POST)
    if not form.is_valid():
        return {"decline_form": form, "open_decline": True}
    signing.decline(recipient, form.cleaned_data["reason"], request=request)
    messages.success(request, _("Penolakan Anda tercatat dan pengirim diberi tahu."))
    return None


def _sign_act(request, recipient):
    form = SignForm(request.POST)
    if not form.is_valid():
        return {"sign_form": form}
    signing.act(
        recipient,
        name=form.cleaned_data["name"],
        signature=form.cleaned_data["signature"],
        request=request,
    )
    messages.success(
        request,
        (
            _("Terima kasih, tanda tangan Anda tercatat.")
            if recipient.action == enums.RecipientAction.SIGN
            else _("Terima kasih, persetujuan Anda tercatat.")
        ),
    )
    return None


# Aksi yang tidak memerlukan kode OTP lebih dahulu.
SIGN_OTP_ACTIONS = {"kirim_kode": _sign_send_code, "cek_kode": _sign_check_code}
SIGN_ACTIONS = {
    "tanda_tangan": _sign_act,
    "tolak": _sign_decline,
    "komentar": _sign_comment,
}


def _sign_post(request, recipient):
    action = request.POST.get("aksi", "")
    if action in SIGN_OTP_ACTIONS:
        return SIGN_OTP_ACTIONS[action](request, recipient)
    if action not in SIGN_ACTIONS:
        raise PermissionDenied
    if not signing.otp_ok(recipient):
        raise ValidationError(_("Masukkan kode verifikasi yang dikirim ke surel Anda."))
    return SIGN_ACTIONS[action](request, recipient)


@require_http_methods(["GET", "POST"])
def sign(request, token):
    recipient = _recipient(token)
    gate = _gate(request, recipient)
    if gate is not None:
        return gate
    if recipient.document.status in (
        enums.SigningStatus.DRAFT,
        enums.SigningStatus.PENDING_APPROVAL,
        enums.SigningStatus.APPROVED,
    ):
        raise Http404
    extra = {}
    if request.method == "POST":
        if _throttled(request, "dokumen-ttd", limit=30, window=300):
            return _too_many(request)
        try:
            failed = _sign_post(request, recipient)
        except ValidationError as error:
            messages.error(request, _errors(error))
            failed = None
        if failed is None:
            return redirect("dokumen_portal:sign", token=token)
        extra = failed
        recipient.refresh_from_db()
    elif signing.otp_ok(recipient):
        signing.record_view(recipient, request=request)
        recipient.refresh_from_db()
    return render(
        request, "dokumen/portal/sign.html", _sign_context(request, recipient, **extra)
    )


def sign_pdf(request, token):
    """Tampilkan PDF yang ditandatangani (sebelum selesai) bagi penerimanya."""
    from dokumen import pdf

    recipient = _recipient(token)
    gate = _gate(request, recipient)
    if gate is not None:
        return gate
    document = recipient.document
    if (
        document.source != enums.SigningSource.PDF
        or not document.source_file
        or not signing.otp_ok(recipient)
        or document.status not in enums.OPEN_SIGNING_STATUSES
    ):
        raise Http404
    try:
        data = pdf.watermark(
            services.read_file(document.source_file),
            [_("Untuk ditinjau: %s") % recipient.name, document.number],
        )
    except (OSError, pdf.PdfReadError):
        raise Http404
    services.log(
        enums.Action.VIEWED,
        actor_name=recipient.name,
        request=request,
        signing=document,
        detail=_("PDF dibuka"),
    )
    return file_response(data, f"{document.number}.pdf", "application/pdf", inline=True)


# --------------------------------------------------------------------------
# Verifikasi keaslian (publik)
# --------------------------------------------------------------------------


def _mask_name(name: str) -> str:
    parts = name.split()
    if not parts:
        return "-"
    return " ".join([parts[0]] + [f"{p[0]}." for p in parts[1:]])


def _match_copy(document, sha) -> dict | bool:
    """Cocokkan sidik berkas dengan dokumen final atau salinan resmi bertanda air."""
    if not document.final_sha256:
        return False
    if sha == document.final_sha256:
        return {"kind": "asli"}
    log = (
        DownloadLog.objects.filter(signing=document, sha256=sha, is_preview=False)
        .order_by("created_at")
        .first()
    )
    if log is None:
        return False
    return {"kind": "salinan", "at": log.created_at, "name": _mask_name(log.user_name)}


def _verify_lookup(request):
    code = request.GET.get("kode", "").strip()
    if code:
        try:
            document = SigningDocument.objects.filter(verify_token=code).first()
        except ValidationError:
            document = None
        if document is not None:
            return redirect("dokumen_portal:verify_token", token=document.verify_token)
        messages.error(request, _("Kode verifikasi tidak ditemukan."))
    return render(request, "dokumen/portal/verify.html", {"document": None})


def _sha256(upload) -> str:
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    return digest.hexdigest()


@require_http_methods(["GET", "POST"])
def verify(request, token=None):
    if token is None:
        return _verify_lookup(request)
    document = (
        SigningDocument.objects.filter(verify_token=token)
        .exclude(status=enums.SigningStatus.DRAFT)
        .first()
    )
    if document is None:
        return render(
            request,
            "dokumen/portal/verify.html",
            {"document": None, "not_found": True},
            status=404,
        )
    form = HashCheckForm(request.POST or None, request.FILES or None)
    match = None
    if request.method == "POST":
        if _throttled(request, "dokumen-verifikasi", limit=20, window=300):
            return _too_many(request)
        if form.is_valid():
            match = _match_copy(document, _sha256(form.cleaned_data["file"]))
    signers = [
        {
            "name": _mask_name(r.signature_name or r.name),
            "role": r.role,
            "action": r.get_action_display(),
            "at": r.completed_at,
            "status": r.get_status_display(),
        }
        for r in document.recipients.exclude(
            action=enums.RecipientAction.COPY
        ).order_by("order", "pk")
    ]
    return render(
        request,
        "dokumen/portal/verify.html",
        {"document": document, "signers": signers, "form": form, "match": match},
    )
