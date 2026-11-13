"""Panel petugas modul dokumen & perizinan (/admin/dokumen/)."""

import datetime

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q, TextField
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.http import content_disposition_header
from django.utils.translation import gettext_lazy as _

from alokasi.templatetags.alokasi_tags import angka
from dokumen import access, downloads, enums, merge, pdf, services, signing
from dokumen.forms import (
    BulkSendForm,
    ContentBlockForm,
    DocumentTemplateForm,
    DownloadDecisionForm,
    FillFieldsForm,
    GenerateForm,
    HostedSignForm,
    OfficerNoteForm,
    OfficerUploadForm,
    OfficerVerifyForm,
    ReassignForm,
    RecipientForm,
    SigningCreateForm,
    SigningDocumentForm,
    TemplateImportForm,
    TemplatePreviewForm,
    recipient_user_queryset,
)
from dokumen.models import (
    Activity,
    ContentBlock,
    DocumentRecipient,
    DocumentSettings,
    DocumentTemplate,
    DownloadLog,
    DownloadRequest,
    LandUse,
    PermitRecord,
    PermitType,
    SavedSignature,
    SigningDocument,
    SigningField,
)

COLORS = {
    # dokumen perizinan
    "belum": "#9a6700",
    "proses": "#0a7ea4",
    "diajukan": "#1f6feb",
    "perbaikan": "#bf8700",
    "terverifikasi": "#1a7f37",
    "kedaluwarsa": "#cf222e",
    "tidak_wajib": "#6e7781",
    # tanda tangan
    "draf": "#6e7781",
    "menunggu_persetujuan": "#8250df",
    "disetujui": "#0a7ea4",
    "dikirim": "#1f6feb",
    "dilihat": "#0969da",
    "selesai": "#1a7f37",
    "ditolak": "#cf222e",
    "dibatalkan": "#6e7781",
    # unduhan & pemanfaatan
    "menunggu": "#bf8700",
    "aktif": "#1a7f37",
    "berakhir": "#8250df",
    "dicabut": "#cf222e",
}


def badge(status, label):
    return format_html(
        '<span class="dk-badge" style="color:#fff;background:{};padding:2px 8px;'
        'border-radius:999px;white-space:nowrap;font-size:.8em">{}</span>',
        COLORS.get(status, "#6e7781"),
        label,
    )


def size_label(size) -> str:
    if size >= 1024 * 1024:
        return f"{angka(size / (1024 * 1024), 1)} MB"
    return f"{angka(max(size, 1) / 1024, 0)} KB"


SECRET_PREVIEW_DENIED = _(
    "Dokumen rahasia hanya dapat dibuka lewat permintaan unduh yang disetujui "
    "pejabat berwenang."
)


def _redirect(request, url, error=None, success=None):
    if error:
        messages.error(request, error)
    if success:
        messages.success(request, success)
    return HttpResponseRedirect(url)


def _errors(error: ValidationError) -> str:
    return " ".join(error.messages)


def process_page(
    request,
    admin_obj,
    obj,
    *,
    title,
    form,
    back_url,
    submit_label,
    intro="",
    danger=False,
    multipart=False,
    extra=None,
):
    context = {
        **admin_obj.admin_site.each_context(request),
        "opts": admin_obj.model._meta,
        "original": obj,
        "title": title,
        "form": form,
        "back_url": back_url,
        "submit_label": submit_label,
        "intro": intro,
        "danger": danger,
        "multipart": multipart,
        "media": admin_obj.media + form.media,
        **(extra or {}),
    }
    return TemplateResponse(request, "admin/dokumen/process_form.html", context)


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    max_num = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ActivityInline(ReadOnlyInline):
    model = Activity
    fk_name = None
    fields = ("created_at", "actor_name", "action", "detail", "ip_address")
    readonly_fields = fields
    verbose_name_plural = _("Jejak aktivitas")
    ordering = ("-created_at", "-pk")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("actor")


# --------------------------------------------------------------------------
# Pengaturan, pustaka konten, templat
# --------------------------------------------------------------------------


@admin.register(DocumentSettings)
class DocumentSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            _("Unduhan"),
            {
                "fields": (
                    "download_valid_hours",
                    "download_max_count",
                    "applicant_needs_approval",
                    "allow_self_approval",
                    "watermark",
                )
            },
        ),
        (
            _("Tanda tangan elektronik"),
            {"fields": ("signing_expiry_days", "reminder_every_days")},
        ),
        (_("Masa berlaku izin"), {"fields": ("expiry_warning_days",)}),
    )

    def has_add_permission(self, request):
        return not DocumentSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        config = DocumentSettings.load()
        return HttpResponseRedirect(
            reverse("admin:dokumen_documentsettings_change", args=[config.pk])
        )


@admin.register(ContentBlock)
class ContentBlockAdmin(admin.ModelAdmin):
    form = ContentBlockForm
    list_display = ("name", "code_tag", "is_active", "modified_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "body")

    @admin.display(description=_("Isian"), ordering="code")
    def code_tag(self, obj):
        return format_html("<code>{{{{ blok.{} }}}}</code>", obj.code)


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    form = DocumentTemplateForm
    list_display = (
        "name",
        "category",
        "kind",
        "version",
        "confidentiality",
        "is_active",
        "usage",
        "modified_at",
    )
    list_filter = ("kind", "category", "confidentiality", "is_active")
    search_fields = ("name", "description", "body", "original_name")
    readonly_fields = (
        "version",
        "original_name",
        "fields_used",
        "created_by",
        "created_at",
        "modified_at",
    )
    change_form_template = "admin/dokumen/documenttemplate/change_form.html"
    change_list_template = "admin/dokumen/documenttemplate/change_list.html"
    fieldsets = (
        (None, {"fields": ("name", "category", "kind", "description", "is_active")}),
        (
            _("Isi templat"),
            {
                "fields": ("body", "file", "original_name", "fields_used"),
                "description": _(
                    "Dokumen isian: tulis isi di editor dan sisipkan isian otomatis. Word/formulir: "
                    "unggah berkas .docx (isian ditulis {{ pemohon.nama }} di dalam Word) atau format lain."
                ),
            },
        ),
        (
            _("Tanda tangan & akses"),
            {
                "fields": (
                    "signer_roles",
                    "needs_approval",
                    "expiry_days",
                    "confidentiality",
                )
            },
        ),
        (
            _("Riwayat"),
            {"fields": ("version", "created_by", "created_at", "modified_at")},
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_usage=Count("signing_documents", distinct=True))
        )

    @admin.display(description=_("Dipakai"), ordering="_usage")
    def usage(self, obj):
        return getattr(obj, "_usage", 0)

    @admin.display(description=_("Isian yang dipakai"))
    def fields_used(self, obj):
        if obj is None or not obj.pk:
            return "–"
        if obj.kind == enums.TemplateKind.HTML:
            text = obj.body
            found = sorted({f"{g}.{n}" for g, n in merge.FIELD_RE.findall(text)})
        elif obj.kind == enums.TemplateKind.DOCX and obj.file:
            try:
                found = merge.docx_fields(services.read_file(obj.file))
            except OSError:
                found = []
            text = " ".join(f"{{{{ {key} }}}}" for key in found)
        else:
            return _("Formulir siap unduh (tanpa isian).")
        unknown = merge.unknown_fields(text)
        if not found:
            return _("Tidak ada isian.")
        return format_html(
            "{}{}",
            ", ".join(found),
            (
                format_html(
                    '<br><strong style="color:#cf222e">{}</strong>',
                    _("Tidak dikenal: ") + ", ".join(unknown),
                )
                if unknown
                else ""
            ),
        )

    def save_model(self, request, obj, form, change):
        upload = form.cleaned_data.get("file")
        if upload and hasattr(upload, "name") and "file" in form.changed_data:
            obj.original_name = upload.name.rsplit("/", 1)[-1][:255]
        if change and ({"body", "file", "kind"} & set(form.changed_data)):
            obj.version += 1
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_urls(self):
        return [
            path(
                "impor/",
                self.admin_site.admin_view(self.import_view),
                name="dokumen_documenttemplate_import",
            ),
            path(
                "<int:pk>/pratinjau/",
                self.admin_site.admin_view(self.preview_view),
                name="dokumen_documenttemplate_preview",
            ),
            path(
                "<int:pk>/unduh/",
                self.admin_site.admin_view(self.download_view),
                name="dokumen_documenttemplate_download",
            ),
        ] + super().get_urls()

    def import_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        form = TemplateImportForm(request.POST or None, request.FILES or None)
        back = reverse("admin:dokumen_documenttemplate_changelist")
        if request.method == "POST" and form.is_valid():
            try:
                created, skipped = services.import_templates(
                    form.cleaned_data["files"],
                    user=request.user,
                    category=form.cleaned_data["category"],
                    docx_mode=form.cleaned_data["docx_mode"],
                )
            except ValidationError as error:
                form.add_error(None, _errors(error))
            else:
                text = _("%d templat diimpor.") % len(created)
                if skipped:
                    text += " " + _("Dilewati (format tidak didukung): %s") % ", ".join(
                        skipped[:20]
                    )
                if len(created) == 1:
                    return _redirect(
                        request,
                        reverse(
                            "admin:dokumen_documenttemplate_change",
                            args=[created[0].pk],
                        ),
                        success=text,
                    )
                return _redirect(request, back, success=text)
        return process_page(
            request,
            self,
            None,
            title=_("Impor templat dokumen"),
            form=form,
            back_url=back,
            submit_label=_("Impor"),
            intro=_(
                "Unggah format dokumen yang sudah ada. Isian otomatis ditulis {{ grup.nama }}, mis. {{ pemohon.nama }}."
            ),
            multipart=True,
            extra={"field_groups": merge.FIELD_GROUPS},
        )

    def preview_view(self, request, pk):
        template = get_object_or_404(DocumentTemplate, pk=pk)
        if not self.has_view_permission(request, template):
            raise PermissionDenied
        form = TemplatePreviewForm(request.GET or None)
        land_use = form.cleaned_data.get("land_use") if form.is_valid() else None
        if template.kind != enums.TemplateKind.HTML:
            return self.download_view(request, pk)
        context = (
            merge.build_context(land_use=land_use)
            if land_use
            else merge.sample_context()
        )
        body = merge.merge_html(template.body, context, highlight_missing=True)
        return TemplateResponse(
            request,
            "admin/dokumen/documenttemplate/preview.html",
            {
                **self.admin_site.each_context(request),
                "opts": self.model._meta,
                "original": template,
                "title": _("Pratinjau: %s") % template.name,
                "body": body,
                "form": form,
                "media": self.media + form.media,
                "custom": merge.custom_fields(template.body),
            },
        )

    def download_view(self, request, pk):
        from django.http import HttpResponse

        template = get_object_or_404(DocumentTemplate, pk=pk)
        if not self.has_view_permission(request, template):
            raise PermissionDenied
        land_use = None
        if request.GET.get("land_use"):
            land_use = LandUse.objects.filter(pk=request.GET["land_use"]).first()
        try:
            data, filename = services.render_template(
                template, land_use=land_use, extra=None
            )
        except merge.TemplateRenderError as error:
            return _redirect(
                request,
                reverse("admin:dokumen_documenttemplate_change", args=[pk]),
                error=str(error),
            )
        except OSError:
            return _redirect(
                request,
                reverse("admin:dokumen_documenttemplate_change", args=[pk]),
                error=_("Berkas templat tidak ditemukan."),
            )
        downloads.log_preview(
            request.user,
            template=template,
            filename=filename,
            data=data,
            request=request,
            preview=False,
        )
        response = HttpResponse(
            data,
            content_type=services.CONTENT_TYPES.get(
                filename.rsplit(".", 1)[-1], "application/octet-stream"
            ),
        )
        response["Content-Disposition"] = content_disposition_header(
            as_attachment=True, filename=filename
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response


# --------------------------------------------------------------------------
# Jenis dokumen
# --------------------------------------------------------------------------


@admin.register(PermitType)
class PermitTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "category",
        "is_required",
        "schemes",
        "validity_months",
        "confidentiality",
        "template",
        "is_active",
        "order",
    )
    list_editable = ("order",)
    list_filter = ("category", "is_required", "confidentiality", "is_active")
    search_fields = ("name", "code", "issuer", "description")
    filter_horizontal = ("sectors",)
    actions = ("apply_to_land_uses",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "code",
                    "category",
                    "issuer",
                    "description",
                    "is_required",
                    "is_active",
                    "order",
                )
            },
        ),
        (
            _("Berlaku untuk"),
            {
                "fields": (
                    "applies_allocation",
                    "applies_lease",
                    "applies_partnership",
                    "applies_other",
                    "sectors",
                )
            },
        ),
        (
            _("Masa berlaku, sifat & templat"),
            {"fields": ("validity_months", "confidentiality", "template")},
        ),
    )

    @admin.display(description=_("Skema"))
    def schemes(self, obj):
        labels = [
            str(label)
            for scheme, label in enums.Scheme.choices
            if getattr(obj, PermitType.SCHEME_FLAGS[scheme])
        ]
        return ", ".join(labels) or "–"

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        created = services.sync_permit_type(form.instance)
        if created:
            messages.info(
                request, _("Ditambahkan ke %d pemanfaatan lahan aktif.") % created
            )

    @admin.action(
        description=_("Terapkan ke pemanfaatan lahan aktif"), permissions=["change"]
    )
    def apply_to_land_uses(self, request, queryset):
        total = sum(services.sync_permit_type(item) for item in queryset)
        self.message_user(request, _("%d dokumen perizinan ditambahkan.") % total)


# --------------------------------------------------------------------------
# Pemanfaatan lahan
# --------------------------------------------------------------------------


class RecordInline(ReadOnlyInline):
    model = PermitRecord
    fields = (
        "permit_type",
        "required",
        "status_badge",
        "number",
        "expiry_date",
        "versions",
        "modified_at",
    )
    readonly_fields = fields
    show_change_link = True
    verbose_name_plural = _("Dokumen perizinan")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("permit_type")
            .annotate(_versions=Count("versions"))
        )

    @admin.display(description=_("Wajib"), boolean=True)
    def required(self, obj):
        return obj.permit_type.is_required

    @admin.display(description=_("Status"))
    def status_badge(self, obj):
        return badge(obj.status, obj.get_status_display())

    @admin.display(description=_("Versi"))
    def versions(self, obj):
        return getattr(obj, "_versions", 0)


class LandUseActivityInline(ActivityInline):
    fk_name = "land_use"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(record__isnull=True, signing__isnull=True, download__isnull=True)
        )


class ProgressFilter(admin.SimpleListFilter):
    title = _("Kelengkapan")
    parameter_name = "kelengkapan"

    def lookups(self, request, model_admin):
        return (
            ("menunggu", _("Ada yang menunggu verifikasi")),
            ("perbaikan", _("Ada yang perlu perbaikan")),
            ("kedaluwarsa", _("Ada yang kedaluwarsa")),
            ("belum_lengkap", _("Dokumen wajib belum lengkap")),
        )

    def queryset(self, request, queryset):
        value = self.value()
        RS = enums.RecordStatus
        if value == "menunggu":
            return queryset.filter(records__status=RS.SUBMITTED).distinct()
        if value == "perbaikan":
            return queryset.filter(records__status=RS.REVISION).distinct()
        if value == "kedaluwarsa":
            return queryset.filter(records__status=RS.EXPIRED).distinct()
        if value == "belum_lengkap":
            return queryset.filter(
                records__permit_type__is_required=True,
                records__status__in=[
                    s for s in RS.values if s not in enums.DONE_RECORD_STATUSES
                ],
            ).distinct()
        return queryset


@admin.register(LandUse)
class LandUseAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "holder_col",
        "scheme",
        "status_badge",
        "progress_col",
        "assigned_to",
        "created_at",
    )
    list_filter = ("status", "scheme", ProgressFilter, "sector")
    search_fields = (
        "number",
        "title",
        "holder_name",
        "holder__name",
        "reference",
        "plot__code",
        "plot__name",
    )
    list_select_related = ("holder", "assigned_to", "plot")
    autocomplete_fields = ("holder", "plot")
    inlines = (RecordInline, LandUseActivityInline)
    change_form_template = "admin/dokumen/landuse/change_form.html"
    actions = ("bulk_send_documents",)
    BULK_LIMIT = 200
    fieldsets = (
        (None, {"fields": ("number", "title", "scheme", "status", "assigned_to")}),
        (_("Pemegang hak"), {"fields": ("holder", "holder_name")}),
        (
            _("Lahan & dasar hak"),
            {
                "fields": (
                    "plot",
                    "sector",
                    "reference",
                    "area_m2",
                    "start_date",
                    "end_date",
                    "allocation",
                    "investment",
                )
            },
        ),
        (_("Catatan"), {"fields": ("note",)}),
    )
    SYNCED = (
        "scheme",
        "holder",
        "holder_name",
        "plot",
        "allocation",
        "investment",
        "start_date",
        "end_date",
        "area_m2",
        "status",
    )

    def get_queryset(self, request):
        RS = enums.RecordStatus
        return (
            super()
            .get_queryset(request)
            .annotate(
                _required=Count(
                    "records",
                    filter=Q(records__permit_type__is_required=True),
                    distinct=True,
                ),
                _done=Count(
                    "records",
                    filter=Q(
                        records__permit_type__is_required=True,
                        records__status__in=enums.DONE_RECORD_STATUSES,
                    ),
                    distinct=True,
                ),
                _waiting=Count(
                    "records", filter=Q(records__status=RS.SUBMITTED), distinct=True
                ),
            )
        )

    def get_readonly_fields(self, request, obj=None):
        fields = ["number", "allocation", "investment"]
        if obj is not None and (obj.allocation_id or obj.investment_id):
            # Disesuaikan otomatis dari alokasi/permintaan investasi.
            fields += [
                f
                for f in self.SYNCED
                if f not in fields and not (obj.investment_id and f == "status")
            ]
        return fields

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "assigned_to":
            from django.contrib.auth import get_user_model

            kwargs["queryset"] = get_user_model().objects.filter(
                is_active=True, is_staff=True
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description=_("Pemegang hak"), ordering="holder_name")
    def holder_col(self, obj):
        return obj.holder_display

    @admin.display(description=_("Status"), ordering="status")
    def status_badge(self, obj):
        return badge(obj.status, obj.get_status_display())

    @admin.display(description=_("Kelengkapan"))
    def progress_col(self, obj):
        required, done, waiting = (
            getattr(obj, "_required", 0),
            getattr(obj, "_done", 0),
            getattr(obj, "_waiting", 0),
        )
        percent = round(done * 100 / required) if required else 100
        extra = (
            format_html(
                ' · <strong style="color:#1f6feb">{} menunggu</strong>', waiting
            )
            if waiting
            else ""
        )
        return format_html(
            '<span style="display:inline-block;width:60px;height:6px;background:#e5e7eb;'
            'border-radius:3px;vertical-align:middle"><span style="display:block;height:6px;'
            'width:{}%;background:#1a7f37;border-radius:3px"></span></span> {}/{}{}',
            percent,
            done,
            required,
            extra,
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change:
            if form.changed_data:
                services.log(
                    enums.Action.UPDATED,
                    actor=request.user,
                    request=request,
                    land_use=obj,
                    detail=", ".join(form.changed_data),
                )
        else:
            services.log(
                enums.Action.CREATED, actor=request.user, request=request, land_use=obj
            )
            services.ensure_records(obj)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        extra = {}
        if obj is not None:
            extra = {
                "progress": obj.progress(),
                "signing_documents": obj.signing_documents.order_by("-created_at")[:20],
                "can_add_record": request.user.has_perm("dokumen.add_permitrecord")
                and obj.status == enums.LandUseStatus.ACTIVE,
                "can_sign": request.user.has_perm("dokumen.add_signingdocument"),
            }
        return super().change_view(
            request, object_id, form_url, {**(extra_context or {}), **extra}
        )

    def get_urls(self):
        return [
            path(
                "kirim-massal/",
                self.admin_site.admin_view(self.bulk_send_view),
                name="dokumen_landuse_bulk_send",
            ),
            path(
                "<int:pk>/tambah-dokumen/",
                self.admin_site.admin_view(self.add_record_view),
                name="dokumen_landuse_add_record",
            ),
        ] + super().get_urls()

    @admin.action(
        description=_("Kirim dokumen tanda tangan massal (satu per pemanfaatan)"),
        permissions=("bulk_send",),
    )
    def bulk_send_documents(self, request, queryset):
        ids = list(queryset.values_list("pk", flat=True)[: self.BULK_LIMIT + 1])
        if len(ids) > self.BULK_LIMIT:
            self.message_user(
                request,
                _("Maksimal %d pemanfaatan sekali kirim.") % self.BULK_LIMIT,
                messages.ERROR,
            )
            return None
        url = reverse("admin:dokumen_landuse_bulk_send")
        return HttpResponseRedirect(f"{url}?ids={','.join(str(i) for i in ids)}")

    def has_bulk_send_permission(self, request):
        return request.user.has_perm(
            "dokumen.add_signingdocument"
        ) and request.user.has_perm("dokumen.send_signingdocument")

    def bulk_send_view(self, request):
        if not self.has_bulk_send_permission(request):
            raise PermissionDenied
        back = reverse("admin:dokumen_landuse_changelist")
        try:
            ids = [int(i) for i in request.GET.get("ids", "").split(",") if i.strip()][
                : self.BULK_LIMIT
            ]
        except ValueError:
            ids = []
        land_uses = list(
            self.get_queryset(request)
            .filter(pk__in=ids)
            .select_related("holder", "holder__user", "plot")
            .order_by("number")
        )
        if not land_uses:
            return _redirect(request, back, error=_("Pilih pemanfaatan lahan dahulu."))
        form = BulkSendForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            data = form.cleaned_data
            extra = None
            if data["countersigner"] is not None:
                user = data["countersigner"]
                extra = {
                    "user": user,
                    "name": signing.display_name(user)[:255],
                    "email": user.email,
                    "role": data["countersigner_role"],
                    "order": 2,
                }
            results = signing.bulk_send(
                template=data["template"],
                land_uses=land_uses,
                user=request.user,
                title=data["title"],
                extra_recipient=extra,
                message=data["message"],
                request=request,
            )
            context = {
                **self.admin_site.each_context(request),
                "opts": self.model._meta,
                "title": _("Hasil kirim massal"),
                "results": results,
                "back_url": back,
                "sent": sum(1 for r in results if r["status"] == "dikirim"),
            }
            return TemplateResponse(
                request, "admin/dokumen/bulk_send_result.html", context
            )
        names = ", ".join(lu.number for lu in land_uses[:10])
        if len(land_uses) > 10:
            names += _(" dan %d lainnya") % (len(land_uses) - 10)
        return process_page(
            request,
            self,
            None,
            title=_("Kirim dokumen tanda tangan massal"),
            form=form,
            back_url=back,
            submit_label=_("Buat & kirim %d dokumen") % len(land_uses),
            intro=_(
                "Satu dokumen dibuat dari templat untuk tiap pemanfaatan lahan "
                "(%(count)d): %(names)s. Pemegang hak menjadi penanda tangan pertama. "
                "Dokumen yang perlu persetujuan internal diajukan dahulu; yang belum "
                "lengkap disimpan sebagai draf."
            )
            % {"count": len(land_uses), "names": names},
        )

    def add_record_view(self, request, pk):
        land_use = get_object_or_404(LandUse, pk=pk)
        if not request.user.has_perm("dokumen.add_permitrecord"):
            raise PermissionDenied
        back = reverse("admin:dokumen_landuse_change", args=[pk])
        existing = land_use.records.values_list("permit_type_id", flat=True)

        class AddRecordForm(forms.Form):
            permit_types = forms.ModelMultipleChoiceField(
                label=_("Jenis dokumen"),
                queryset=PermitType.objects.filter(is_active=True).exclude(
                    pk__in=existing
                ),
                widget=forms.CheckboxSelectMultiple,
            )

        form = AddRecordForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            for permit_type in form.cleaned_data["permit_types"]:
                record, created = PermitRecord.objects.get_or_create(
                    land_use=land_use, permit_type=permit_type
                )
                if created:
                    services.log(
                        enums.Action.CREATED,
                        actor=request.user,
                        request=request,
                        record=record,
                    )
            return _redirect(request, back, success=_("Dokumen ditambahkan ke daftar."))
        return process_page(
            request,
            self,
            land_use,
            title=_("Tambah dokumen ke daftar"),
            form=form,
            back_url=back,
            submit_label=_("Tambahkan"),
            intro=_("Pilih dokumen tambahan yang diminta untuk pemanfaatan lahan ini."),
        )


# --------------------------------------------------------------------------
# Dokumen perizinan
# --------------------------------------------------------------------------


class ExpiringFilter(admin.SimpleListFilter):
    title = _("Masa berlaku")
    parameter_name = "berlaku"

    def lookups(self, request, model_admin):
        return (
            ("30", _("Habis ≤ 30 hari")),
            ("90", _("Habis ≤ 90 hari")),
            ("lewat", _("Sudah lewat")),
        )

    def queryset(self, request, queryset):
        today = timezone.localdate()
        if self.value() in ("30", "90"):
            limit = today + datetime.timedelta(days=int(self.value()))
            return queryset.filter(expiry_date__gte=today, expiry_date__lte=limit)
        if self.value() == "lewat":
            return queryset.filter(expiry_date__lt=today)
        return queryset


class RecordActivityInline(ActivityInline):
    fk_name = "record"


@admin.register(PermitRecord)
class PermitRecordAdmin(admin.ModelAdmin):
    list_display = (
        "land_use",
        "holder_col",
        "permit_type",
        "status_badge",
        "number",
        "expiry_col",
        "versions",
        "modified_at",
    )
    list_filter = (
        "status",
        ExpiringFilter,
        "permit_type__category",
        "permit_type",
        "land_use__scheme",
    )
    search_fields = (
        "land_use__number",
        "land_use__title",
        "land_use__holder_name",
        "permit_type__name",
        "number",
    )
    list_select_related = ("land_use", "permit_type")
    change_form_template = "admin/dokumen/permitrecord/change_form.html"
    inlines = (RecordActivityInline,)
    fields = (
        "land_use",
        "permit_type",
        "status",
        "number",
        "issued_date",
        "expiry_date",
        "holder_note",
        "review_note",
        "verified_by",
        "verified_at",
    )
    readonly_fields = fields

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_versions=Count("versions"))

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        # Tidak ada kolom yang diubah lewat formulir; tindakan lewat tombol proses.
        return False

    @admin.display(description=_("Pemegang hak"), ordering="land_use__holder_name")
    def holder_col(self, obj):
        return obj.land_use.holder_display

    @admin.display(description=_("Status"), ordering="status")
    def status_badge(self, obj):
        return badge(obj.status, obj.get_status_display())

    @admin.display(description=_("Berlaku sampai"), ordering="expiry_date")
    def expiry_col(self, obj):
        if not obj.expiry_date:
            return "–"
        days = obj.days_to_expiry
        color = "#cf222e" if days < 0 else ("#bf8700" if days <= 60 else "inherit")
        return format_html(
            '<span style="color:{}">{}</span>',
            color,
            obj.expiry_date.strftime("%d-%m-%Y"),
        )

    @admin.display(description=_("Versi"))
    def versions(self, obj):
        return getattr(obj, "_versions", 0)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        extra = {}
        if obj is not None:
            RS = enums.RecordStatus
            can_verify = request.user.has_perm("dokumen.verify_permitrecord")
            versions = list(obj.versions.select_related("uploaded_by"))
            for version in versions:
                version.size_label = size_label(version.size)
                version.previewable = version.extension in ("pdf", "png", "jpg", "jpeg")
            extra = {
                "versions": versions,
                "can_verify": can_verify and obj.status != RS.VERIFIED,
                "can_revise": can_verify and obj.status not in (RS.WAIVED,),
                "can_waive": can_verify and obj.status != RS.WAIVED,
                "can_reopen": can_verify
                and obj.status in (RS.VERIFIED, RS.WAIVED, RS.EXPIRED),
                "can_upload": can_verify,
                "can_generate": can_verify
                and DocumentTemplate.objects.filter(is_active=True).exists(),
                "can_sign": request.user.has_perm("dokumen.add_signingdocument"),
                "can_preview": can_verify,
                "signing_documents": obj.signing_documents.order_by("-created_at"),
                "my_requests": DownloadRequest.objects.filter(
                    requester=request.user, version__record=obj
                ).select_related("version")[:20],
            }
        return super().change_view(
            request, object_id, form_url, {**(extra_context or {}), **extra}
        )

    def get_urls(self):
        return [
            path(
                "<int:pk>/proses/<str:action>/",
                self.admin_site.admin_view(self.process_view),
                name="dokumen_permitrecord_process",
            ),
            path(
                "<int:pk>/templat/",
                self.admin_site.admin_view(self.generate_view),
                name="dokumen_permitrecord_generate",
            ),
        ] + super().get_urls()

    PROCESS = {
        "verifikasi": (
            _("Verifikasi dokumen"),
            OfficerVerifyForm,
            _("Nyatakan terverifikasi"),
            False,
        ),
        "perbaikan": (
            _("Minta perbaikan"),
            OfficerNoteForm,
            _("Kirim permintaan perbaikan"),
            True,
        ),
        "tidak-wajib": (
            _("Nyatakan tidak wajib"),
            OfficerNoteForm,
            _("Nyatakan tidak wajib"),
            False,
        ),
        "buka": (_("Buka kembali"), OfficerNoteForm, _("Buka kembali"), True),
        "unggah": (_("Unggah versi baru"), OfficerUploadForm, _("Unggah"), False),
    }

    def _run(self, action, record, request, data):
        user = request.user
        if action == "verifikasi":
            services.verify(
                record,
                user,
                number=data.get("number") or record.number,
                issued_date=data.get("issued_date") or record.issued_date,
                expiry_date=data.get("expiry_date") or record.expiry_date,
                note=data.get("note", ""),
                request=request,
            )
            return _("Dokumen terverifikasi.")
        if action == "perbaikan":
            services.request_revision(record, user, data["note"], request=request)
            return _("Permintaan perbaikan dikirim ke pemegang hak.")
        if action == "tidak-wajib":
            services.waive(record, user, data["note"], request=request)
            return _("Dokumen dinyatakan tidak wajib.")
        if action == "buka":
            services.reopen(record, user, data["note"], request=request)
            return _("Dokumen dibuka kembali.")
        services.officer_upload(
            record,
            user,
            data["file"],
            note=data.get("note", ""),
            number=data.get("number") or None,
            issued_date=data.get("issued_date"),
            expiry_date=data.get("expiry_date"),
            verify_now=data.get("verify_now", False),
            request=request,
        )
        return _("Versi baru diunggah.")

    def process_view(self, request, pk, action):
        if action not in self.PROCESS:
            raise PermissionDenied
        record = get_object_or_404(
            PermitRecord.objects.select_related("land_use", "permit_type"), pk=pk
        )
        if not request.user.has_perm("dokumen.verify_permitrecord"):
            raise PermissionDenied
        title, form_class, submit, danger = self.PROCESS[action]
        back = reverse("admin:dokumen_permitrecord_change", args=[pk])
        initial = {
            "number": record.number,
            "issued_date": record.issued_date,
            "expiry_date": record.expiry_date,
        }
        form = form_class(request.POST or None, request.FILES or None, initial=initial)
        if request.method == "POST" and form.is_valid():
            try:
                message = self._run(action, record, request, form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, _errors(error))
            else:
                return _redirect(request, back, success=message)
        return process_page(
            request,
            self,
            record,
            title=title,
            form=form,
            back_url=back,
            submit_label=submit,
            danger=danger,
            multipart=action == "unggah",
            intro=f"{record.permit_type} – {record.land_use}",
        )

    def generate_view(self, request, pk):
        record = get_object_or_404(
            PermitRecord.objects.select_related("land_use", "permit_type"), pk=pk
        )
        if not request.user.has_perm("dokumen.verify_permitrecord"):
            raise PermissionDenied
        back = reverse("admin:dokumen_permitrecord_change", args=[pk])
        template_id = (
            request.POST.get("template")
            or request.GET.get("templat")
            or record.permit_type.template_id
        )
        template = (
            DocumentTemplate.objects.filter(pk=template_id, is_active=True).first()
            if template_id
            else None
        )
        keys = []
        if template is not None and template.kind == enums.TemplateKind.HTML:
            keys = merge.custom_fields(template.body)
        form = GenerateForm(
            request.POST or None, initial={"template": template}, custom_keys=keys
        )
        if request.method == "POST" and form.is_valid():
            chosen = form.cleaned_data["template"]
            if chosen.kind == enums.TemplateKind.HTML and set(
                merge.custom_fields(chosen.body)
            ) - set(form.custom_values()):
                return _redirect(
                    request,
                    reverse("admin:dokumen_permitrecord_generate", args=[pk])
                    + f"?templat={chosen.pk}",
                    error=_("Lengkapi isian templat yang dipilih."),
                )
            try:
                version = services.generate_version(
                    record,
                    request.user,
                    chosen,
                    extra=form.custom_values(),
                    note=form.cleaned_data["note"],
                    request=request,
                )
            except (ValidationError, OSError) as error:
                form.add_error(
                    None,
                    (
                        _errors(error)
                        if isinstance(error, ValidationError)
                        else _("Berkas templat tidak ditemukan.")
                    ),
                )
            else:
                return _redirect(
                    request,
                    back,
                    success=_("Versi %s dibuat dari templat.") % version.number,
                )
        return process_page(
            request,
            self,
            record,
            title=_("Buat dokumen dari templat"),
            form=form,
            back_url=back,
            submit_label=_("Buat versi baru"),
            intro=_(
                "Hasil disimpan sebagai versi baru dokumen ini (PDF untuk templat isian, .docx untuk templat Word)."
            ),
            extra={"reload_on_template": True},
        )


# --------------------------------------------------------------------------
# Dokumen tanda tangan
# --------------------------------------------------------------------------


class RecipientInline(admin.TabularInline):
    model = DocumentRecipient
    form = RecipientForm
    extra = 0
    fields = (
        "order",
        "role",
        "action",
        "user",
        "name",
        "email",
        "in_person",
        "access_code",
        "stamp_page",
        "stamp_x",
        "stamp_y",
        "stamp_width",
        "status_col",
        "views_col",
        "completed_at",
    )
    readonly_fields = ("status_col", "views_col", "completed_at")
    verbose_name_plural = _("Penerima (urutan tanda tangan)")

    @admin.display(description=_("Status"))
    def status_col(self, obj):
        if obj is None or not obj.pk:
            return "–"
        return badge(
            obj.status if obj.status != "selesai" else "selesai",
            obj.get_status_display(),
        )

    @admin.display(description=_("Dibuka"))
    def views_col(self, obj):
        if obj is None or not obj.pk or not obj.view_count:
            return "–"
        return f"{obj.view_count}× · {timezone.localtime(obj.last_viewed_at):%d-%m-%Y %H.%M}"

    def _editable(self, obj):
        return obj is not None and obj.is_editable

    def get_extra(self, request, obj=None, **kwargs):
        return 1 if self._editable(obj) and not obj.recipients.exists() else 0

    def has_add_permission(self, request, obj=None):
        return self._editable(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._editable(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._editable(obj) and super().has_delete_permission(request, obj)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        if "user" in formset.form.base_fields:
            formset.form.base_fields["user"].queryset = recipient_user_queryset(obj)
        return formset


class SigningFieldInline(admin.TabularInline):
    model = SigningField
    extra = 0
    fields = (
        "order",
        "key",
        "label",
        "kind",
        "options",
        "required",
        "recipient",
        "value_col",
    )
    readonly_fields = ("value_col",)
    verbose_name_plural = _(
        "Kolom isian penerima ({{ kolom.<kunci> }} di isi; PDF: tampil di lembar pengesahan)"
    )
    formfield_overrides = {
        TextField: {"widget": forms.Textarea(attrs={"rows": 2, "cols": 24})}
    }

    @admin.display(description=_("Isian"))
    def value_col(self, obj):
        if obj is None or not obj.pk or not obj.filled_at:
            return "–"
        if obj.kind == SigningField.Kind.FILE and obj.file:
            return format_html(
                '<a href="{}">{}</a>',
                reverse("admin:dokumen_signingdocument_field_file", args=[obj.pk]),
                obj.file_name,
            )
        return obj.display_value or "–"

    def _editable(self, obj):
        return obj is not None and obj.is_editable

    def has_add_permission(self, request, obj=None):
        return self._editable(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._editable(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._editable(obj) and super().has_delete_permission(request, obj)

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and (
            obj is None or obj.is_editable or obj.fields.exists()
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "recipient":
            object_id = (
                request.resolver_match.kwargs.get("object_id")
                if request.resolver_match
                else None
            )
            kwargs["queryset"] = (
                DocumentRecipient.objects.filter(document_id=object_id).exclude(
                    action=enums.RecipientAction.COPY
                )
                if object_id
                else DocumentRecipient.objects.none()
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class SigningActivityInline(ActivityInline):
    fk_name = "signing"


@admin.register(SigningDocument)
class SigningDocumentAdmin(admin.ModelAdmin):
    form = SigningDocumentForm
    list_display = (
        "number",
        "title",
        "status_badge",
        "progress_col",
        "land_use",
        "created_by",
        "sent_at",
        "expires_on",
    )
    list_filter = ("status", "source", "confidentiality", "needs_approval")
    search_fields = (
        "number",
        "title",
        "land_use__number",
        "land_use__holder_name",
        "recipients__name",
        "recipients__email",
    )
    list_select_related = ("land_use", "created_by")
    autocomplete_fields = ("land_use",)
    inlines = (RecipientInline, SigningFieldInline, SigningActivityInline)
    change_form_template = "admin/dokumen/signingdocument/change_form.html"
    date_hierarchy = "created_at"
    INFO = (
        "number",
        "status",
        "source",
        "template",
        "template_version",
        "source_name",
        "created_by",
        "approved_by",
        "approved_at",
        "sent_at",
        "completed_at",
        "content_sha256",
        "final_sha256",
        "closed_reason",
    )
    fieldsets = (
        (None, {"fields": ("number", "title", "status", "land_use", "record")}),
        (
            _("Isi"),
            {
                "fields": (
                    "source",
                    "template",
                    "template_version",
                    "source_name",
                    "body",
                )
            },
        ),
        (
            _("Pengiriman"),
            {
                "fields": (
                    "message",
                    "expires_on",
                    "reminder_every_days",
                    "needs_approval",
                    "confidentiality",
                )
            },
        ),
        (
            _("Riwayat"),
            {
                "fields": (
                    "created_by",
                    "approved_by",
                    "approved_at",
                    "sent_at",
                    "completed_at",
                    "content_sha256",
                    "final_sha256",
                    "closed_reason",
                )
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _acting=Count(
                    "recipients",
                    filter=~Q(recipients__action=enums.RecipientAction.COPY),
                    distinct=True,
                ),
                _done=Count(
                    "recipients",
                    filter=~Q(recipients__action=enums.RecipientAction.COPY)
                    & Q(recipients__status=enums.RecipientStatus.DONE),
                    distinct=True,
                ),
            )
        )

    def get_readonly_fields(self, request, obj=None):
        if (
            obj is None
            or not obj.is_editable
            or not self.has_change_permission(request, obj)
        ):
            return [f for fs in self.fieldsets for f in fs[1]["fields"]]
        fields = list(self.INFO)
        if obj.source == enums.SigningSource.PDF:
            fields.append("body")
        return fields

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj is not None and (
            obj.source == enums.SigningSource.PDF or not obj.is_editable
        ):
            # Isi dokumen yang terkunci ditampilkan rapi di ringkasan, bukan sebagai kode HTML.
            fieldsets = [
                (n, {**o, "fields": tuple(f for f in o["fields"] if f != "body")})
                for n, o in fieldsets
            ]
        return fieldsets

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "record":
            object_id = (
                request.resolver_match.kwargs.get("object_id")
                if request.resolver_match
                else None
            )
            document = (
                SigningDocument.objects.filter(pk=object_id).first()
                if object_id
                else None
            )
            queryset = PermitRecord.objects.select_related("permit_type", "land_use")
            kwargs["queryset"] = (
                queryset.filter(land_use=document.land_use)
                if document and document.land_use_id
                else queryset.none()
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (
            obj is None or obj.status == enums.SigningStatus.DRAFT
        )

    @admin.display(description=_("Status"), ordering="status")
    def status_badge(self, obj):
        return badge(obj.status, obj.get_status_display())

    @admin.display(description=_("Progres"))
    def progress_col(self, obj):
        return f"{getattr(obj, '_done', 0)}/{getattr(obj, '_acting', 0)}"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change and form.changed_data:
            services.log(
                enums.Action.UPDATED,
                actor=request.user,
                request=request,
                signing=obj,
                detail=", ".join(form.changed_data),
            )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Kolom {{ kolom.* }} baru di isi otomatis mendapat definisi bawaan.
        if signing.sync_fields(form.instance):
            messages.info(
                request,
                _(
                    "Kolom isian penerima baru ditambahkan dari isi dokumen; "
                    "tetapkan penerima dan jenisnya."
                ),
            )

    # --- pembuatan ---------------------------------------------------------

    def add_view(self, request, form_url="", extra_context=None):
        if not self.has_add_permission(request):
            raise PermissionDenied
        initial = {}
        record = None
        if request.GET.get("izin"):
            record = (
                PermitRecord.objects.filter(pk=request.GET["izin"])
                .select_related("permit_type", "land_use")
                .first()
            )
            if record is not None:
                initial = {
                    "record": record.pk,
                    "land_use": record.land_use_id,
                    "title": f"{record.permit_type.name} – {record.land_use.holder_display}"[
                        :255
                    ],
                    "template": (
                        record.permit_type.template_id
                        if record.permit_type.template
                        and record.permit_type.template.can_sign
                        else None
                    ),
                }
        elif request.GET.get("pemanfaatan"):
            initial = {"land_use": request.GET["pemanfaatan"]}
        elif request.GET.get("templat"):
            initial = {"template": request.GET["templat"]}
        form = SigningCreateForm(
            request.POST or None, request.FILES or None, initial=initial
        )
        back = reverse("admin:dokumen_signingdocument_changelist")
        if request.method == "POST" and form.is_valid():
            data = form.cleaned_data
            try:
                document = signing.create(
                    user=request.user,
                    title=data["title"],
                    template=data["template"],
                    land_use=data["land_use"],
                    record=data["record"],
                    upload=data["source_file"],
                    request=request,
                )
            except ValidationError as error:
                form.add_error(None, _errors(error))
            else:
                return _redirect(
                    request,
                    reverse("admin:dokumen_signingdocument_change", args=[document.pk]),
                    success=_("Draf dibuat. Periksa isi dan penerima, lalu kirim."),
                )
        return process_page(
            request,
            self,
            None,
            title=_("Buat dokumen tanda tangan"),
            form=form,
            back_url=back,
            submit_label=_("Buat draf"),
            multipart=True,
            intro=_(
                "Buat dari templat isian (isi dapat diedit) atau unggah PDF yang sudah jadi."
            ),
            extra={"record": record},
        )

    # --- halaman ubah & tindakan ------------------------------------------

    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        extra = {}
        if obj is not None:
            user = request.user
            S = enums.SigningStatus
            can_send = user.has_perm("dokumen.send_signingdocument")
            leftovers = merge.custom_fields(obj.body) if obj.is_editable else []
            comments = obj.comments.select_related("author")
            extra = {
                "problems": (
                    signing.problems(obj) if obj.status in (S.DRAFT, S.APPROVED) else []
                ),
                "can_submit_approval": can_send
                and obj.status == S.DRAFT
                and obj.needs_approval,
                "can_approve": obj.status == S.PENDING_APPROVAL
                and signing.can_approve(user, obj),
                "can_reject_approval": obj.status == S.PENDING_APPROVAL
                and user.has_perm("dokumen.approve_signingdocument"),
                "can_send": can_send
                and (
                    obj.status == S.APPROVED
                    or (obj.status == S.DRAFT and not obj.needs_approval)
                ),
                "can_remind": can_send and obj.is_open,
                "can_cancel": can_send and not obj.is_final,
                "can_duplicate": user.has_perm("dokumen.add_signingdocument"),
                "can_preview": user.has_perm("dokumen.view_signingdocument"),
                "can_request_download": obj.status == S.COMPLETED
                and bool(obj.final_file),
                "fill_form": FillFieldsForm(keys=leftovers) if leftovers else None,
                "comments": comments,
                "recipients": obj.recipients.order_by("order", "pk"),
                "current_order": obj.current_order(),
                "rendered_body": (
                    signing.render_body(obj)
                    if obj.source == enums.SigningSource.HTML
                    else ""
                ),
                "can_manage_recipients": can_send and (obj.is_open or obj.is_editable),
                "verify_url": reverse(
                    "dokumen_portal:verify_token", args=[obj.verify_token]
                ),
                "my_requests": DownloadRequest.objects.filter(
                    requester=user, signing=obj
                )[:10],
            }
            if not obj.is_editable:
                extra.update(
                    show_save=False,
                    show_save_and_continue=False,
                    show_save_and_add_another=False,
                )
        return super().change_view(
            request, object_id, form_url, {**(extra_context or {}), **extra}
        )

    def get_urls(self):
        return [
            path(
                "<int:pk>/proses/<str:action>/",
                self.admin_site.admin_view(self.process_view),
                name="dokumen_signingdocument_process",
            ),
            path(
                "<int:pk>/komentar/",
                self.admin_site.admin_view(self.comment_view),
                name="dokumen_signingdocument_comment",
            ),
            path(
                "<int:pk>/isian/",
                self.admin_site.admin_view(self.fill_view),
                name="dokumen_signingdocument_fill",
            ),
            path(
                "<int:pk>/pratinjau/",
                self.admin_site.admin_view(self.preview_view),
                name="dokumen_signingdocument_preview",
            ),
            path(
                "penerima/<int:rid>/kirim-ulang/",
                self.admin_site.admin_view(self.resend_view),
                name="dokumen_signingdocument_resend",
            ),
            path(
                "penerima/<int:rid>/ganti/",
                self.admin_site.admin_view(self.reassign_view),
                name="dokumen_signingdocument_reassign",
            ),
            path(
                "penerima/<int:rid>/ttd-langsung/",
                self.admin_site.admin_view(self.hosted_view),
                name="dokumen_signingdocument_hosted",
            ),
            path(
                "kolom/<int:fid>/berkas/",
                self.admin_site.admin_view(self.field_file_view),
                name="dokumen_signingdocument_field_file",
            ),
        ] + super().get_urls()

    NOTE_ACTIONS = {
        "tolak-persetujuan": (_("Tolak persetujuan"), _("Kembalikan ke draf"), True),
        "batal": (_("Batalkan dokumen"), _("Batalkan dokumen"), True),
        "setujui": (_("Setujui dokumen"), _("Setujui"), False),
    }
    NOTE_HANDLERS = {
        "tolak-persetujuan": (
            "dokumen.approve_signingdocument",
            signing.reject_approval,
        ),
        "batal": ("dokumen.send_signingdocument", signing.cancel),
        "setujui": ("dokumen.approve_signingdocument", signing.approve),
    }

    def process_view(self, request, pk, action):
        document = get_object_or_404(SigningDocument, pk=pk)
        back = reverse("admin:dokumen_signingdocument_change", args=[pk])
        user = request.user
        if action in ("ajukan", "kirim", "ingatkan", "salin"):
            if request.method != "POST":
                return HttpResponseRedirect(back)
            return self._quick_action(request, document, action, back)
        if action not in self.NOTE_ACTIONS:
            raise PermissionDenied
        permission, handler = self.NOTE_HANDLERS[action]
        if not user.has_perm(permission):
            raise PermissionDenied
        title, submit, danger = self.NOTE_ACTIONS[action]
        form = OfficerNoteForm(request.POST or None)
        if action == "setujui":
            form.fields["note"].required = False
        if request.method == "POST" and form.is_valid():
            note = form.cleaned_data["note"]
            try:
                handler(document, user, note, request=request)
            except ValidationError as error:
                form.add_error(None, _errors(error))
            else:
                return _redirect(request, back, success=_("Tersimpan."))
        return process_page(
            request,
            self,
            document,
            title=title,
            form=form,
            back_url=back,
            submit_label=submit,
            danger=danger,
            intro=str(document),
        )

    def _quick_action(self, request, document, action, back):
        user = request.user
        needed = (
            "dokumen.add_signingdocument"
            if action == "salin"
            else "dokumen.send_signingdocument"
        )
        if not user.has_perm(needed):
            raise PermissionDenied
        try:
            if action == "ajukan":
                signing.submit_for_approval(document, user, request=request)
                return _redirect(
                    request, back, success=_("Persetujuan internal diminta.")
                )
            if action == "kirim":
                signing.send(document, user, request=request)
                return _redirect(
                    request, back, success=_("Dokumen dikirim ke penerima.")
                )
            if action == "ingatkan":
                count = signing.remind(document, user, request=request)
                return _redirect(
                    request,
                    back,
                    success=_("Pengingat dikirim ke %d penerima.") % count,
                )
            copy = signing.duplicate(document, user, request=request)
            return _redirect(
                request,
                reverse("admin:dokumen_signingdocument_change", args=[copy.pk]),
                success=_("Salinan draf dibuat."),
            )
        except ValidationError as error:
            return _redirect(request, back, error=_errors(error))

    def comment_view(self, request, pk):
        document = get_object_or_404(SigningDocument, pk=pk)
        back = reverse("admin:dokumen_signingdocument_change", args=[pk]) + "#komentar"
        if request.method != "POST" or not self.has_view_permission(request, document):
            raise PermissionDenied
        try:
            signing.add_comment(
                document,
                request.user,
                request.POST.get("body", ""),
                internal=request.POST.get("internal") == "1",
                request=request,
            )
        except ValidationError as error:
            return _redirect(request, back, error=_errors(error))
        return _redirect(request, back, success=_("Komentar ditambahkan."))

    def fill_view(self, request, pk):
        document = get_object_or_404(SigningDocument, pk=pk)
        back = reverse("admin:dokumen_signingdocument_change", args=[pk])
        if request.method != "POST" or not self.has_change_permission(
            request, document
        ):
            raise PermissionDenied
        form = FillFieldsForm(request.POST, keys=merge.custom_fields(document.body))
        if not form.is_valid():
            return _redirect(request, back, error=_("Lengkapi semua isian."))
        try:
            signing.fill_fields(document, form.values(), request.user, request=request)
        except ValidationError as error:
            return _redirect(request, back, error=_errors(error))
        return _redirect(request, back, success=_("Isian diterapkan ke isi dokumen."))

    def _may_preview_content(self, request, document) -> bool:
        """Isi dokumen rahasia: penyusun (izin ubah) dan pejabat penyetuju
        unduhan rahasia; peran yang hanya melihat mengajukan permintaan unduh."""
        return self.has_change_permission(
            request, document
        ) or access.can_preview_confidential(request.user, document.confidentiality)

    def preview_view(self, request, pk):
        from django.http import HttpResponse

        from dokumen import pdf

        document = get_object_or_404(SigningDocument, pk=pk)
        if not self.has_view_permission(request, document):
            raise PermissionDenied
        back = reverse("admin:dokumen_signingdocument_change", args=[pk])
        if not self._may_preview_content(request, document):
            return _redirect(request, back, error=SECRET_PREVIEW_DENIED)
        try:
            if document.source == enums.SigningSource.PDF:
                data = services.read_file(document.source_file)
            else:
                data = pdf.template_pdf(
                    document.title,
                    signing.render_body(document, preview=True),
                    number=document.number,
                )
            data = pdf.watermark(
                data,
                [
                    _("PRATINJAU – BUKAN DOKUMEN SAH"),
                    f"{document.number} · {timezone.localtime():%d-%m-%Y %H.%M}",
                ],
            )
        except (OSError, pdf.PdfReadError):
            return _redirect(request, back, error=_("Pratinjau tidak dapat dibuat."))
        downloads.log_preview(
            request.user,
            signing=document,
            filename=f"pratinjau-{document.number}.pdf",
            data=data,
            request=request,
        )
        response = HttpResponse(data, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="pratinjau-{document.number}.pdf"'
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    def resend_view(self, request, rid):
        recipient = get_object_or_404(DocumentRecipient, pk=rid)
        back = reverse(
            "admin:dokumen_signingdocument_change", args=[recipient.document_id]
        )
        if request.method != "POST" or not request.user.has_perm(
            "dokumen.send_signingdocument"
        ):
            raise PermissionDenied
        try:
            signing.resend(recipient, request.user, request=request)
        except ValidationError as error:
            return _redirect(request, back, error=_errors(error))
        return _redirect(
            request, back, success=_("Tautan dikirim ulang ke %s.") % recipient.email
        )

    def _recipient_for(self, request, rid):
        recipient = get_object_or_404(
            DocumentRecipient.objects.select_related("document"), pk=rid
        )
        if not request.user.has_perm("dokumen.send_signingdocument"):
            raise PermissionDenied
        if not self.has_view_permission(request, recipient.document):
            raise PermissionDenied
        back = reverse(
            "admin:dokumen_signingdocument_change", args=[recipient.document_id]
        )
        return recipient, back

    def reassign_view(self, request, rid):
        recipient, back = self._recipient_for(request, rid)
        form = ReassignForm(request.POST or None, document=recipient.document)
        if request.method == "POST" and form.is_valid():
            data = form.cleaned_data
            try:
                signing.reassign(
                    recipient,
                    name=data["name"],
                    email=data["email"],
                    user=data["user"],
                    officer=request.user,
                    reason=data["reason"],
                    request=request,
                )
            except ValidationError as error:
                form.add_error(None, _errors(error))
            else:
                return _redirect(request, back, success=_("Penerima diganti."))
        return process_page(
            request,
            self,
            recipient.document,
            title=_("Ganti penerima"),
            form=form,
            back_url=back,
            submit_label=_("Ganti penerima"),
            intro=_(
                "Mengganti %(name)s (%(action)s). Tautan lama tidak berlaku lagi; "
                "penerima baru diberi tahu bila sudah gilirannya."
            )
            % {"name": recipient.name, "action": recipient.get_action_display()},
        )

    def hosted_view(self, request, rid):
        recipient, back = self._recipient_for(request, rid)
        form = HostedSignForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            try:
                signing.start_hosted(
                    recipient,
                    request.user,
                    form.cleaned_data["evidence"],
                    request=request,
                )
            except ValidationError as error:
                form.add_error(None, _errors(error))
            else:
                return HttpResponseRedirect(
                    reverse("dokumen_portal:sign", args=[recipient.token])
                )
        return process_page(
            request,
            self,
            recipient.document,
            title=_("Tanda tangan langsung"),
            form=form,
            back_url=back,
            submit_label=_("Buka halaman tanda tangan"),
            intro=_(
                "%(name)s menandatangani di perangkat ini, di hadapan Anda. Sesi "
                "berlaku 30 menit dan tercatat di jejak audit beserta bukti identitas."
            )
            % {"name": recipient.name},
        )

    def field_file_view(self, request, fid):
        from dokumen.views import file_response

        field = get_object_or_404(
            SigningField.objects.select_related("document"), pk=fid
        )
        if not self.has_view_permission(request, field.document) or not field.file:
            raise PermissionDenied
        if not self._may_preview_content(request, field.document):
            back = reverse(
                "admin:dokumen_signingdocument_change", args=[field.document_id]
            )
            return _redirect(request, back, error=SECRET_PREVIEW_DENIED)
        data = services.read_file(field.file)
        filename = field.file_name or "berkas"
        # Pratinjau (bukan unduhan penuh): PDF pindaian KTP penerima diberi
        # tanda air identitas petugas dan tercatat sebagai pratinjau, sama
        # seperti pratinjau versi izin — selaras kebijakan modul bahwa tidak
        # ada unduhan tanpa persetujuan.
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension == "pdf":
            try:
                stamp = timezone.localtime().strftime("%d-%m-%Y %H.%M")
                data = pdf.watermark(
                    data,
                    [_("PRATINJAU"), f"{request.user.get_username()} · {stamp}"],
                )
            except pdf.PdfReadError:
                pass
        downloads.log_preview(
            request.user,
            signing=field.document,
            filename=filename,
            data=data,
            request=request,
            preview=True,
        )
        import mimetypes

        return file_response(
            data,
            filename,
            mimetypes.guess_type(filename)[0] or "application/octet-stream",
        )


@admin.register(SavedSignature)
class SavedSignatureAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "updated_at")
    search_fields = ("user__username", "user__email", "name")
    readonly_fields = ("user", "name", "preview", "updated_at")
    fields = readonly_fields

    @admin.display(description=_("Tanda tangan"))
    def preview(self, obj):
        return format_html('<img src="{}" alt="" style="max-width:240px">', obj.image)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# --------------------------------------------------------------------------
# Permintaan unduhan & riwayat
# --------------------------------------------------------------------------


class DownloadLogInline(ReadOnlyInline):
    model = DownloadLog
    fields = (
        "created_at",
        "user_name",
        "filename",
        "watermarked",
        "ip_address",
        "sha256",
    )
    readonly_fields = fields
    verbose_name_plural = _("Riwayat unduh")


class PendingFilter(admin.SimpleListFilter):
    title = _("Tindakan saya")
    parameter_name = "saya"

    def lookups(self, request, model_admin):
        return (
            ("putuskan", _("Menunggu keputusan saya")),
            ("milik", _("Permintaan saya")),
        )

    def queryset(self, request, queryset):
        if self.value() == "putuskan":
            return queryset.filter(
                pk__in=downloads.pending_for(request.user).values("pk")
            )
        if self.value() == "milik":
            return queryset.filter(requester=request.user)
        return queryset


@admin.register(DownloadRequest)
class DownloadRequestAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "requester_col",
        "target_col",
        "confidentiality",
        "purpose",
        "state_badge",
        "usage",
        "created_at",
        "decided_by",
    )
    list_filter = (PendingFilter, "status", "confidentiality", "purpose")
    search_fields = (
        "number",
        "requester__email",
        "requester__first_name",
        "requester__last_name",
        "reason",
        "signing__number",
        "version__record__land_use__number",
    )
    list_select_related = (
        "requester",
        "decided_by",
        "signing",
        "version__record__permit_type",
        "version__record__land_use",
    )
    change_form_template = "admin/dokumen/downloadrequest/change_form.html"
    inlines = (DownloadLogInline,)
    fields = (
        "number",
        "requester",
        "target_col",
        "confidentiality",
        "purpose",
        "reason",
        "status",
        "created_at",
        "decided_by",
        "decided_at",
        "decision_note",
        "valid_until",
        "max_downloads",
        "download_count",
    )
    readonly_fields = fields

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        user = request.user
        if user.has_perm("dokumen.approve_confidential_download"):
            return queryset
        if user.has_perm("dokumen.approve_downloadrequest"):
            # Alasan & data permintaan dokumen rahasia hanya untuk pejabat
            # penyetuju rahasia (sama dengan downloads.pending_for).
            return queryset.exclude(
                Q(confidentiality=enums.Confidentiality.SECRET) & ~Q(requester=user)
            )
        return queryset.filter(requester=user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description=_("Pemohon unduhan"), ordering="requester__email")
    def requester_col(self, obj):
        from dokumen.access import display_name

        return display_name(obj.requester)

    @admin.display(description=_("Dokumen"))
    def target_col(self, obj):
        if obj.version_id:
            url = reverse(
                "admin:dokumen_permitrecord_change", args=[obj.version.record_id]
            )
        else:
            url = reverse("admin:dokumen_signingdocument_change", args=[obj.signing_id])
        return format_html('<a href="{}">{}</a>', url, obj.target_label)

    @admin.display(description=_("Status"), ordering="status")
    def state_badge(self, obj):
        state = obj.status
        if obj.status == enums.DownloadStatus.APPROVED and not obj.is_usable:
            state = "kedaluwarsa"
        return badge(state, obj.state_label)

    @admin.display(description=_("Unduh"))
    def usage(self, obj):
        if obj.status != enums.DownloadStatus.APPROVED:
            return "–"
        return f"{obj.download_count}/{obj.max_downloads}"

    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        extra = {}
        if obj is not None:
            can_decide = (
                obj.status == enums.DownloadStatus.PENDING
                and downloads.can_decide(request.user, obj)
            )
            extra = {
                "can_decide": can_decide,
                "decision_form": (
                    DownloadDecisionForm(form_id="dk-decide") if can_decide else None
                ),
                "is_mine": obj.requester_id == request.user.pk,
                "download_url": (
                    reverse("dokumen-staff-download", args=[obj.number])
                    if obj.requester_id == request.user.pk and obj.is_usable
                    else ""
                ),
                "self_blocked": obj.status == enums.DownloadStatus.PENDING
                and obj.requester_id == request.user.pk
                and not downloads.can_decide(request.user, obj),
                "history": DownloadRequest.objects.filter(requester=obj.requester)
                .exclude(pk=obj.pk)
                .order_by("-created_at")[:10],
            }
        return super().change_view(
            request, object_id, form_url, {**(extra_context or {}), **extra}
        )

    def get_urls(self):
        return [
            path(
                "<int:pk>/putuskan/",
                self.admin_site.admin_view(self.decide_view),
                name="dokumen_downloadrequest_decide",
            ),
            path(
                "<int:pk>/batal/",
                self.admin_site.admin_view(self.cancel_view),
                name="dokumen_downloadrequest_cancel",
            ),
        ] + super().get_urls()

    def decide_view(self, request, pk):
        dl = get_object_or_404(DownloadRequest, pk=pk)
        back = reverse("admin:dokumen_downloadrequest_change", args=[pk])
        if request.method != "POST":
            return HttpResponseRedirect(back)
        form = DownloadDecisionForm(request.POST)
        if not form.is_valid():
            return _redirect(
                request, back, error=" ".join(" ".join(e) for e in form.errors.values())
            )
        data = form.cleaned_data
        try:
            if request.POST.get("decision") == "setuju":
                downloads.approve(
                    dl,
                    request.user,
                    note=data["note"],
                    hours=data["hours"],
                    max_count=data["max_count"],
                    request=request,
                )
                text = _("Permintaan disetujui.")
            else:
                downloads.reject(dl, request.user, data["note"], request=request)
                text = _("Permintaan ditolak.")
        except ValidationError as error:
            return _redirect(request, back, error=_errors(error))
        return _redirect(
            request,
            reverse("admin:dokumen_downloadrequest_changelist") + "?saya=putuskan",
            success=text,
        )

    def cancel_view(self, request, pk):
        dl = get_object_or_404(DownloadRequest, pk=pk)
        back = reverse("admin:dokumen_downloadrequest_change", args=[pk])
        if request.method != "POST":
            return HttpResponseRedirect(back)
        try:
            downloads.cancel(dl, request.user, request=request)
        except ValidationError as error:
            return _redirect(request, back, error=_errors(error))
        return _redirect(request, back, success=_("Permintaan dibatalkan."))


@admin.register(DownloadLog)
class DownloadLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "user_name",
        "filename",
        "is_preview",
        "watermarked",
        "request",
        "ip_address",
    )
    list_filter = ("is_preview", "watermarked")
    search_fields = ("user_name", "filename", "request__number", "ip_address", "sha256")
    date_hierarchy = "created_at"
    list_select_related = ("request",)
    readonly_fields = [f.name for f in DownloadLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "actor_name",
        "action",
        "target",
        "detail_short",
        "ip_address",
    )
    list_filter = ("action",)
    search_fields = (
        "actor_name",
        "detail",
        "land_use__number",
        "signing__number",
        "download__number",
        "record__permit_type__name",
    )
    date_hierarchy = "created_at"
    list_select_related = ("land_use", "signing", "download", "record__permit_type")
    readonly_fields = [f.name for f in Activity._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description=_("Objek"))
    def target(self, obj):
        if obj.signing_id:
            return obj.signing.number
        if obj.download_id:
            return obj.download.number
        if obj.record_id:
            return f"{obj.land_use.number if obj.land_use_id else ''} {obj.record.permit_type.name}"
        if obj.land_use_id:
            return obj.land_use.number
        return "–"

    @admin.display(description=_("Keterangan"))
    def detail_short(self, obj):
        return (obj.detail[:120] + "…") if len(obj.detail) > 120 else obj.detail
