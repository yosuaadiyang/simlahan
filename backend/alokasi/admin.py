"""Panel petugas alokasi lahan di /admin/.

Perubahan status permohonan, tagihan, dan alokasi hanya lewat tombol proses
(alokasi.services) supaya riwayat, status lahan, dan notifikasi tetap konsisten.
"""

from django import forms
from django.contrib import admin, messages
from django.contrib.gis.admin import GISModelAdmin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Exists, OuterRef
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from alokasi import documents, enums, services
from alokasi.admin_views import file_link, file_url
from alokasi.forms import OfficerNoteForm, ScoreForm
from alokasi.importers import PlotImportError, import_plots
from alokasi.models import (
    Allocation,
    AllocationSettings,
    Applicant,
    Application,
    ApplicationDocument,
    ApplicationEvent,
    DevelopmentReport,
    InfoPage,
    Invoice,
    IssuedDocument,
    LandPlot,
    PermitReport,
    RequirementDocType,
    VerificationCriterion,
    VerificationScore,
)
from alokasi.monitoring import idle_queryset, overdue_report_allocations
from file_operations.private_files import PrivateFileField

S = enums.ApplicationStatus


# --------------------------------------------------------------------------
# Utilitas
# --------------------------------------------------------------------------


class _FileLink:
    def __init__(self, url, name):
        self.url = url
        self.name = name

    def __str__(self):
        return self.name


class PrivateClearableFileInput(forms.ClearableFileInput):
    """Tautan berkas lewat unduhan petugas, bukan /media/ (berkas privat)."""

    def __init__(self, kind, attrs=None):
        super().__init__(attrs)
        self.kind = kind

    def format_value(self, value):
        if value and getattr(value, "instance", None) is not None and value.instance.pk:
            return _FileLink(
                file_url(self.kind, value.instance), value.name.rsplit("/", 1)[-1]
            )
        return None


class PrivateFileAdminMixin:
    file_kind = ""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, PrivateFileField) and self.file_kind:
            kwargs["widget"] = PrivateClearableFileInput(self.file_kind)
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    max_num = 0
    can_delete = False
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


def _status_badge(status, label):
    colors = {
        S.DRAFT: "#777",
        S.SUBMITTED: "#1f6feb",
        S.VERIFYING: "#8250df",
        S.REVISION: "#bf8700",
        S.APPROVED: "#0a7ea4",
        S.PAID: "#1a7f37",
        S.ISSUED: "#1a7f37",
        S.REJECTED: "#cf222e",
        S.CANCELLED: "#777",
    }
    return format_html(
        '<span style="color:#fff;background:{};padding:2px 6px;border-radius:3px;white-space:nowrap">{}</span>',
        colors.get(status, "#777"),
        label,
    )


def _process_page(
    request, admin_obj, obj, *, title, intro, form, submit_label, danger=False
):
    context = {
        **admin_obj.admin_site.each_context(request),
        "opts": admin_obj.model._meta,
        "original": obj,
        "title": title,
        "intro": intro,
        "form": form,
        "submit_label": submit_label,
        "danger": danger,
        "back_url": reverse(
            f"admin:alokasi_{admin_obj.model._meta.model_name}_change", args=[obj.pk]
        ),
    }
    return TemplateResponse(request, "admin/alokasi/process_form.html", context)


def _run(request, func, success_message):
    try:
        func()
    except ValidationError as error:
        for message in error.messages:
            messages.error(request, message)
        return False
    messages.success(request, success_message)
    return True


# --------------------------------------------------------------------------
# Pengaturan & data master
# --------------------------------------------------------------------------


@admin.register(AllocationSettings)
class AllocationSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            _("Otoritas & penandatangan"),
            {
                "fields": (
                    "authority_name",
                    "authority_short_name",
                    "city",
                    "signatory_name",
                    "signatory_title",
                )
            },
        ),
        (
            _("Tarif & tagihan"),
            {
                "fields": (
                    "allocation_admin_fee",
                    "transfer_admin_fee",
                    "transfer_fee_per_m2",
                    "invoice_due_days",
                    "payment_instructions",
                )
            },
        ),
        (
            _("Ketentuan alokasi"),
            {
                "fields": (
                    "default_term_years",
                    "passing_score",
                    "idle_years",
                    "report_interval_months",
                )
            },
        ),
        (_("Portal"), {"fields": ("contact_info",)}),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = AllocationSettings.load()
        return HttpResponseRedirect(
            reverse("admin:alokasi_allocationsettings_change", args=[obj.pk])
        )


@admin.register(LandPlot)
class LandPlotAdmin(PrivateFileAdminMixin, GISModelAdmin):
    file_kind = "lahan"
    list_display = (
        "code",
        "name",
        "allocation_type",
        "status",
        "area_m2",
        "district",
        "village",
        "has_map",
        "is_published",
    )
    list_filter = ("status", "allocation_type", "is_published", "district")
    search_fields = ("code", "name", "village", "district", "intended_use")
    list_editable = ("is_published",)
    readonly_fields = ("uwt_preview",)
    actions = ("publish", "unpublish", "close_plots", "reopen_plots")
    change_list_template = "admin/alokasi/landplot/change_list.html"
    fieldsets = (
        (
            None,
            {"fields": ("code", "name", "allocation_type", "status", "is_published")},
        ),
        (_("Lokasi"), {"fields": ("district", "village", "address", "geometry")}),
        (
            _("Data teknis"),
            {
                "fields": (
                    "area_m2",
                    "zoning",
                    "intended_use",
                    "has_technical_documents",
                    "land_preparation_done",
                    "infrastructure",
                    "description",
                    "photo",
                )
            },
        ),
        (_("Tarif"), {"fields": ("uwt_rate_per_m2_year", "term_years", "uwt_preview")}),
    )

    @admin.display(boolean=True, description=_("Peta"))
    def has_map(self, obj):
        return obj.geometry is not None

    @admin.display(description=_("Perkiraan UWT total"))
    def uwt_preview(self, obj):
        if not obj.pk:
            return "–"
        from alokasi.templatetags.alokasi_tags import rupiah

        return f"{rupiah(obj.uwt_total)} ({obj.effective_term_years} tahun)"

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.status in (
            enums.PlotStatus.RESERVED,
            enums.PlotStatus.ALLOCATED,
        ):
            # Status dikelola alur permohonan; ukuran & tarif dikunci agar tagihan konsisten.
            fields += ["status", "area_m2", "uwt_rate_per_m2_year", "term_years"]
        return fields

    def save_model(self, request, obj, form, change):
        if obj.allocation_type == enums.AllocationType.OPEN and not (
            obj.has_technical_documents and obj.land_preparation_done
        ):
            messages.warning(
                request,
                _(
                    "Alokasi tanah terbuka mensyaratkan dokumen teknis tersedia dan "
                    "pematangan lahan selesai. Periksa kembali isian lahan ini."
                ),
            )
        super().save_model(request, obj, form, change)

    @admin.action(description=_("Tampilkan di portal"), permissions=["change"])
    def publish(self, request, queryset):
        queryset.update(is_published=True)

    @admin.action(description=_("Sembunyikan dari portal"), permissions=["change"])
    def unpublish(self, request, queryset):
        queryset.update(is_published=False)

    @admin.action(
        description=_("Tutup lahan (tidak menerima permohonan)"), permissions=["change"]
    )
    def close_plots(self, request, queryset):
        updated = queryset.filter(status=enums.PlotStatus.AVAILABLE).update(
            status=enums.PlotStatus.CLOSED
        )
        self.message_user(request, _("%d lahan ditutup.") % updated)

    @admin.action(
        description=_("Buka kembali lahan yang ditutup"), permissions=["change"]
    )
    def reopen_plots(self, request, queryset):
        updated = queryset.filter(status=enums.PlotStatus.CLOSED).update(
            status=enums.PlotStatus.AVAILABLE
        )
        self.message_user(request, _("%d lahan dibuka kembali.") % updated)

    def get_urls(self):
        return [
            path(
                "impor/",
                self.admin_site.admin_view(self.import_view),
                name="alokasi_landplot_import",
            ),
        ] + super().get_urls()

    def import_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        form = PlotImportForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            try:
                with transaction.atomic():
                    upload = form.cleaned_data["file"]
                    created, updated = import_plots(
                        upload.read(),
                        filename=upload.name,
                        defaults={
                            "allocation_type": form.cleaned_data["allocation_type"],
                            "is_published": form.cleaned_data["is_published"],
                        },
                    )
            except PlotImportError as error:
                form.add_error("file", str(error))
            else:
                messages.success(
                    request,
                    _("Impor selesai: %(c)d lahan baru, %(u)d diperbarui.")
                    % {"c": created, "u": updated},
                )
                return HttpResponseRedirect(
                    reverse("admin:alokasi_landplot_changelist")
                )
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": _("Impor lahan dari GeoJSON atau KML/KMZ"),
            "form": form,
        }
        return TemplateResponse(request, "admin/alokasi/landplot/import.html", context)


class PlotImportForm(forms.Form):
    file = forms.FileField(
        label=_("Berkas GeoJSON atau KML/KMZ"),
        help_text=_(
            "GeoJSON FeatureCollection atau KML/KMZ dari Google Earth, berisi Polygon/MultiPolygon "
            "(WGS84). Pada KML/KMZ, nama placemark dipakai sebagai kode bila tidak ada atribut "
            "kode. Properti yang dikenali: kode/code, "
            "nama/name, luas_m2/area_m2 (dihitung dari geometri bila kosong), kecamatan, kelurahan, "
            "alamat, peruntukan, arahan, tarif_uwt, jangka_tahun, jenis_alokasi."
        ),
    )
    allocation_type = forms.ChoiceField(
        label=_("Jenis alokasi bawaan"), choices=enums.AllocationType.choices
    )
    is_published = forms.BooleanField(
        label=_("Langsung tampil di portal"), required=False
    )


@admin.register(InfoPage)
class InfoPageAdmin(PrivateFileAdminMixin, admin.ModelAdmin):
    file_kind = "informasi"
    list_display = ("title", "category", "published_at", "order", "is_published")
    list_filter = ("category", "is_published")
    list_editable = ("order", "is_published")
    search_fields = ("title", "summary", "body")
    date_hierarchy = "published_at"

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "video_url":
            kwargs["assume_scheme"] = "https"
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    fields = (
        "category",
        "title",
        "slug",
        "summary",
        "body",
        "video_url",
        "attachment",
        "order",
        "published_at",
        "is_published",
    )


@admin.register(RequirementDocType)
class RequirementDocTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "service_type",
        "allocation_type",
        "is_required",
        "order",
        "is_active",
    )
    list_filter = ("service_type", "allocation_type", "is_required", "is_active")
    list_editable = ("order", "is_required", "is_active")
    search_fields = ("name",)


@admin.register(VerificationCriterion)
class VerificationCriterionAdmin(admin.ModelAdmin):
    list_display = ("name", "weight", "order", "is_active")
    list_editable = ("weight", "order", "is_active")
    list_filter = ("is_active",)

    def changelist_view(self, request, extra_context=None):
        total = sum(
            c.weight for c in VerificationCriterion.objects.filter(is_active=True)
        )
        if total and total != 100:
            messages.info(
                request,
                _(
                    "Total bobot kriteria aktif %s%%. Nilai akhir dinormalisasi terhadap total bobot."
                )
                % total,
            )
        return super().changelist_view(request, extra_context)


@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "applicant_type",
        "email_display",
        "phone",
        "nib",
        "account_active",
        "created_at",
    )
    list_filter = ("applicant_type", "user__is_active")
    search_fields = ("name", "nib", "npwp", "pic_name", "user__email", "phone")
    readonly_fields = (
        "user",
        "email_display",
        "account_active",
        "created_at",
        "modified_at",
    )
    actions = ("activate_accounts", "deactivate_accounts")
    fields = (
        "user",
        "email_display",
        "account_active",
        "applicant_type",
        "name",
        "nib",
        "npwp",
        "nik",
        "pic_name",
        "pic_position",
        "phone",
        "address",
        "city",
        "created_at",
        "modified_at",
    )

    def has_add_permission(self, request):
        return False  # Pemohon mendaftar sendiri di portal.

    def has_delete_permission(self, request, obj=None):
        return False

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "nik":
            kwargs["widget"] = forms.TextInput(attrs={"maxlength": 16})
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    @admin.display(description=_("Surel"), ordering="user__email")
    def email_display(self, obj):
        return obj.user.email

    @admin.display(
        boolean=True, description=_("Akun aktif"), ordering="user__is_active"
    )
    def account_active(self, obj):
        return obj.user.is_active

    @admin.action(description=_("Aktifkan akun"), permissions=["change"])
    def activate_accounts(self, request, queryset):
        from django.contrib.auth import get_user_model

        n = get_user_model().objects.filter(pemohon__in=queryset).update(is_active=True)
        self.message_user(request, _("%d akun diaktifkan.") % n)

    @admin.action(description=_("Nonaktifkan akun"), permissions=["change"])
    def deactivate_accounts(self, request, queryset):
        from django.contrib.auth import get_user_model

        n = (
            get_user_model()
            .objects.filter(pemohon__in=queryset)
            .update(is_active=False)
        )
        self.message_user(request, _("%d akun dinonaktifkan.") % n)


# --------------------------------------------------------------------------
# Permohonan
# --------------------------------------------------------------------------


class ApplicationDocumentInline(ReadOnlyInline):
    model = ApplicationDocument
    fields = ("doc_type", "download", "created_at")
    readonly_fields = fields
    verbose_name_plural = _("Dokumen persyaratan")

    @admin.display(description=_("Berkas"))
    def download(self, obj):
        return file_link("dokumen", obj, obj.original_name)


class ScoreInline(ReadOnlyInline):
    model = VerificationScore
    fields = ("criterion", "verifier", "score", "note", "modified_at")
    readonly_fields = fields
    verbose_name_plural = _("Nilai verifikasi teknis")


class InvoiceInline(ReadOnlyInline):
    model = Invoice
    fields = ("invoice_link", "kind", "amount", "due_date", "status", "proof")
    readonly_fields = fields
    verbose_name_plural = _("Tagihan")

    @admin.display(description=_("Nomor"))
    def invoice_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse("admin:alokasi_invoice_change", args=[obj.pk]),
            obj.number,
        )

    @admin.display(description=_("Bukti bayar"))
    def proof(self, obj):
        return file_link("bukti", obj)


class IssuedDocumentInline(ReadOnlyInline):
    model = IssuedDocument
    fields = ("kind", "number", "holder_name", "issued_at", "download")
    readonly_fields = fields
    verbose_name_plural = _("Dokumen terbit")

    @admin.display(description=_("PDF"))
    def download(self, obj):
        return file_link("terbit", obj, _("Unduh"))


class EventInline(ReadOnlyInline):
    model = ApplicationEvent
    fields = ("created_at", "status", "actor", "note")
    readonly_fields = fields
    verbose_name_plural = _("Riwayat")


class ScoredFilter(admin.SimpleListFilter):
    title = _("penilaian saya")
    parameter_name = "nilai_saya"

    def lookups(self, request, model_admin):
        return (("belum", _("Belum saya nilai")), ("sudah", _("Sudah saya nilai")))

    def queryset(self, request, queryset):
        mine = VerificationScore.objects.filter(
            application=OuterRef("pk"), verifier=request.user
        )
        if self.value() == "belum":
            return queryset.filter(status=S.VERIFYING).exclude(Exists(mine))
        if self.value() == "sudah":
            return queryset.filter(Exists(mine))
        return queryset


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "service_type",
        "applicant",
        "plot",
        "status_badge",
        "submitted_at",
        "score",
    )
    list_filter = ("status", "service_type", "plot__allocation_type", ScoredFilter)
    search_fields = (
        "number",
        "applicant__name",
        "plot__code",
        "plot__name",
        "recipient__name",
    )
    date_hierarchy = "created_at"
    list_select_related = ("applicant", "plot")
    inlines = (
        ApplicationDocumentInline,
        ScoreInline,
        InvoiceInline,
        IssuedDocumentInline,
        EventInline,
    )
    change_form_template = "admin/alokasi/application/change_form.html"
    change_list_template = "admin/alokasi/application/change_list.html"
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "number",
                    "service_type",
                    "status",
                    "applicant",
                    "submitted_at",
                    "officer_note",
                )
            },
        ),
        (
            _("Alokasi tanah"),
            {
                "fields": (
                    "plot",
                    "activity",
                    "investment_value",
                    "workforce",
                    "development_months",
                    "description",
                )
            },
        ),
        (
            _("Peralihan hak"),
            {"fields": ("source_allocation", "recipient", "transfer_reason")},
        ),
        (_("Keputusan"), {"fields": ("score", "decided_at", "decided_by")}),
    )

    def get_readonly_fields(self, request, obj=None):
        return [f for fieldset in self.fieldsets for f in fieldset[1]["fields"]]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description=_("Status"), ordering="status")
    def status_badge(self, obj):
        return _status_badge(obj.status, obj.get_status_display())

    def changelist_view(self, request, extra_context=None):
        counts = dict(Application.objects.values_list("status").annotate(n=Count("pk")))
        extra_context = {
            **(extra_context or {}),
            "status_counts": [
                (value, label, counts.get(value, 0)) for value, label in S.choices
            ],
        }
        return super().changelist_view(request, extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        extra = {}
        if obj is not None:
            user = request.user
            can_decide = user.has_perm("alokasi.decide_application")
            can_verify = user.has_perm("alokasi.verify_application")
            criteria = list(VerificationCriterion.objects.filter(is_active=True))
            scores = list(obj.scores.select_related("verifier"))
            verifiers = sorted({s.verifier for s in scores}, key=lambda u: u.pk)
            extra = {
                "can_start": can_decide and obj.status == S.SUBMITTED,
                "can_revise": can_decide and obj.status in (S.SUBMITTED, S.VERIFYING),
                "can_approve": can_decide and obj.status == S.VERIFYING,
                "can_reject": can_decide
                and obj.status in (S.SUBMITTED, S.VERIFYING, S.REVISION),
                "can_score": can_verify
                and obj.status == S.VERIFYING
                and obj.is_allocation,
                "missing_docs": obj.missing_required_documents(),
                "computed_score": obj.compute_score() if obj.is_allocation else None,
                "passing_score": AllocationSettings.load().passing_score,
                "criteria_count": len(criteria),
                "verifier_progress": [
                    (v, sum(1 for s in scores if s.verifier_id == v.pk))
                    for v in verifiers
                ],
            }
        return super().change_view(
            request, object_id, form_url, {**(extra_context or {}), **extra}
        )

    def get_urls(self):
        view = self.admin_site.admin_view
        return [
            path(
                "<int:pk>/proses/<str:action>/",
                view(self.process_view),
                name="alokasi_application_process",
            ),
            path(
                "<int:pk>/nilai/",
                view(self.score_view),
                name="alokasi_application_score",
            ),
        ] + super().get_urls()

    PROCESS_ACTIONS = {
        "verifikasi": (_("Mulai verifikasi teknis"), False, False),
        "perbaikan": (_("Minta perbaikan kepada pemohon"), True, False),
        "setujui": (_("Setujui permohonan dan terbitkan tagihan"), False, False),
        "tolak": (_("Tolak permohonan"), True, True),
    }

    def process_view(self, request, pk, action):
        if action not in self.PROCESS_ACTIONS:
            raise PermissionDenied
        if not request.user.has_perm("alokasi.decide_application"):
            raise PermissionDenied
        application = get_object_or_404(Application, pk=pk)
        title, note_required, danger = self.PROCESS_ACTIONS[action]
        form = OfficerNoteForm(request.POST or None, required=note_required)
        back = reverse("admin:alokasi_application_change", args=[pk])
        if request.method == "POST" and form.is_valid():
            note = form.cleaned_data["note"]
            user = request.user
            funcs = {
                "verifikasi": lambda: services.start_verification(application, user),
                "perbaikan": lambda: services.request_revision(application, user, note),
                "setujui": lambda: services.approve(application, user, note),
                "tolak": lambda: services.reject(application, user, note),
            }
            _run(
                request,
                funcs[action],
                _("Permohonan %(n)s: %(t)s berhasil.")
                % {"n": application.number, "t": title},
            )
            return HttpResponseRedirect(back)
        intro = {
            "verifikasi": _(
                "Permohonan diteruskan ke Tim Verifikasi Teknis untuk dinilai."
            ),
            "perbaikan": _(
                "Pemohon diberi tahu lewat surel dan dapat memperbaiki data serta dokumen."
            ),
            "setujui": _(
                "Tagihan UWT dan biaya administrasi dibuat otomatis. Setelah semua tagihan lunas, "
                "KPT dan PPT (atau izin peralihan hak) terbit otomatis."
            ),
            "tolak": _(
                "Permohonan ditolak dan lahan kembali tersedia. Alasan dikirim ke pemohon."
            ),
        }[action]
        return _process_page(
            request,
            self,
            application,
            title=title,
            intro=intro,
            form=form,
            submit_label=title,
            danger=danger,
        )

    def score_view(self, request, pk):
        if not request.user.has_perm("alokasi.verify_application"):
            raise PermissionDenied
        application = get_object_or_404(Application, pk=pk)
        back = reverse("admin:alokasi_application_change", args=[pk])
        if application.status != S.VERIFYING:
            messages.error(
                request, _("Penilaian hanya untuk permohonan dalam verifikasi teknis.")
            )
            return HttpResponseRedirect(back)
        form = ScoreForm(
            request.POST or None, application=application, verifier=request.user
        )
        if not form.criteria:
            messages.error(
                request,
                _(
                    "Belum ada kriteria verifikasi aktif. Tambahkan di menu Kriteria verifikasi teknis."
                ),
            )
            return HttpResponseRedirect(back)
        if request.method == "POST" and form.is_valid():
            with transaction.atomic():
                for criterion in form.criteria:
                    VerificationScore.objects.update_or_create(
                        application=application,
                        criterion=criterion,
                        verifier=request.user,
                        defaults={
                            "score": form.cleaned_data[f"score_{criterion.pk}"],
                            "note": form.cleaned_data[f"note_{criterion.pk}"],
                        },
                    )
                services.refresh_score(application)
            messages.success(request, _("Nilai verifikasi disimpan."))
            return HttpResponseRedirect(back)
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "original": application,
            "title": _("Penilaian verifikasi teknis %s") % application.number,
            "form": form,
            "back_url": back,
            "documents": application.documents.select_related("doc_type"),
        }
        return TemplateResponse(
            request, "admin/alokasi/application/score_form.html", context
        )


# --------------------------------------------------------------------------
# Tagihan
# --------------------------------------------------------------------------


@admin.register(Invoice)
class InvoiceAdmin(ReadOnlyAdmin):
    list_display = (
        "number",
        "application",
        "applicant_name",
        "kind",
        "amount",
        "due_date",
        "status",
        "overdue",
    )
    list_filter = ("status", "kind")
    search_fields = ("number", "application__number", "application__applicant__name")
    list_select_related = ("application", "application__applicant")
    date_hierarchy = "due_date"
    change_form_template = "admin/alokasi/invoice/change_form.html"
    actions = ("verify_selected",)
    fields = (
        "number",
        "application",
        "kind",
        "description",
        "amount",
        "due_date",
        "status",
        "proof",
        "proof_uploaded_at",
        "paid_at",
        "verified_by",
        "note",
    )
    readonly_fields = fields

    @admin.display(description=_("Pemohon"), ordering="application__applicant__name")
    def applicant_name(self, obj):
        return obj.application.applicant.name

    @admin.display(boolean=True, description=_("Lewat jatuh tempo"))
    def overdue(self, obj):
        return obj.is_overdue

    @admin.display(description=_("Bukti bayar"))
    def proof(self, obj):
        return file_link("bukti", obj)

    def has_verify_payment_permission(self, request):
        return request.user.has_perm("alokasi.verify_payment")

    @admin.action(
        description=_("Verifikasi lunas (bukti bayar sudah diunggah)"),
        permissions=["verify_payment"],
    )
    def verify_selected(self, request, queryset):
        done = 0
        for invoice in queryset.filter(status=enums.InvoiceStatus.PROOF_UPLOADED):
            if _run(
                request,
                lambda inv=invoice: services.verify_payment(inv, request.user),
                _("%s lunas.") % invoice.number,
            ):
                done += 1
        if not done:
            self.message_user(
                request,
                _("Tidak ada tagihan dengan bukti bayar yang menunggu verifikasi."),
                messages.WARNING,
            )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        extra = {}
        if obj is not None:
            can = request.user.has_perm("alokasi.verify_payment")
            extra = {
                "can_verify": can
                and obj.status
                in (enums.InvoiceStatus.UNPAID, enums.InvoiceStatus.PROOF_UPLOADED),
                "can_reject": can and obj.status == enums.InvoiceStatus.PROOF_UPLOADED,
            }
        return super().change_view(
            request, object_id, form_url, {**(extra_context or {}), **extra}
        )

    def get_urls(self):
        view = self.admin_site.admin_view
        return [
            path(
                "<int:pk>/verifikasi/",
                view(self.verify_view),
                name="alokasi_invoice_verify",
            ),
            path(
                "<int:pk>/tolak-bukti/",
                view(self.reject_view),
                name="alokasi_invoice_reject",
            ),
            path("<int:pk>/pdf/", view(self.pdf_view), name="alokasi_invoice_pdf"),
        ] + super().get_urls()

    def verify_view(self, request, pk):
        if not request.user.has_perm("alokasi.verify_payment"):
            raise PermissionDenied
        invoice = get_object_or_404(Invoice, pk=pk)
        form = OfficerNoteForm(request.POST or None, required=False)
        if request.method == "POST" and form.is_valid():
            _run(
                request,
                lambda: services.verify_payment(invoice, request.user),
                _("Tagihan %s dinyatakan lunas.") % invoice.number,
            )
            return HttpResponseRedirect(
                reverse("admin:alokasi_invoice_change", args=[pk])
            )
        intro = _(
            "Pastikan dana %(amount)s sudah diterima di rekening resmi. Bila semua tagihan permohonan "
            "%(app)s lunas, dokumen terbit otomatis."
        ) % {
            "amount": f"Rp{invoice.amount:,.0f}".replace(",", "."),
            "app": invoice.application.number,
        }
        return _process_page(
            request,
            self,
            invoice,
            title=_("Verifikasi pembayaran"),
            intro=intro,
            form=form,
            submit_label=_("Nyatakan lunas"),
        )

    def reject_view(self, request, pk):
        if not request.user.has_perm("alokasi.verify_payment"):
            raise PermissionDenied
        invoice = get_object_or_404(Invoice, pk=pk)
        form = OfficerNoteForm(request.POST or None, required=True)
        if request.method == "POST" and form.is_valid():
            _run(
                request,
                lambda: services.reject_payment(
                    invoice, request.user, form.cleaned_data["note"]
                ),
                _("Bukti bayar %s ditolak.") % invoice.number,
            )
            return HttpResponseRedirect(
                reverse("admin:alokasi_invoice_change", args=[pk])
            )
        return _process_page(
            request,
            self,
            invoice,
            title=_("Tolak bukti bayar"),
            intro=_("Pemohon diminta mengunggah ulang bukti bayar."),
            form=form,
            submit_label=_("Tolak bukti bayar"),
            danger=True,
        )

    def pdf_view(self, request, pk):
        if not self.has_view_permission(request):
            raise PermissionDenied
        invoice = get_object_or_404(Invoice, pk=pk)
        response = HttpResponse(
            documents.invoice_pdf(invoice), content_type="application/pdf"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="tagihan-{invoice.number}.pdf"'
        )
        return response


# --------------------------------------------------------------------------
# Alokasi & pemantauan
# --------------------------------------------------------------------------


class IdleFilter(admin.SimpleListFilter):
    title = _("lahan tidur")
    parameter_name = "lahan_tidur"

    def lookups(self, request, model_admin):
        return (("ya", _("Lahan tidur")), ("tidak", _("Bukan lahan tidur")))

    def queryset(self, request, queryset):
        if self.value() == "ya":
            return idle_queryset(queryset)
        if self.value() == "tidak":
            return queryset.exclude(pk__in=idle_queryset().values("pk"))
        return queryset


class ReportOverdueFilter(admin.SimpleListFilter):
    title = _("kepatuhan lapor")
    parameter_name = "lapor"

    def lookups(self, request, model_admin):
        return (("terlambat", _("Laporan terlambat")),)

    def queryset(self, request, queryset):
        if self.value() == "terlambat":
            return queryset.filter(pk__in=[a.pk for a in overdue_report_allocations()])
        return queryset


class PermitReportInline(ReadOnlyInline):
    model = PermitReport
    fields = (
        "permit_type",
        "status",
        "permit_number",
        "issued_date",
        "download",
        "note",
        "modified_at",
    )
    readonly_fields = fields
    verbose_name_plural = _("Progres perizinan")

    @admin.display(description=_("Dokumen"))
    def download(self, obj):
        return file_link("izin", obj)


class DevelopmentReportInline(ReadOnlyInline):
    model = DevelopmentReport
    fields = (
        "report_date",
        "stage",
        "progress_percent",
        "realized_investment",
        "workforce",
        "description",
        "download",
    )
    readonly_fields = fields
    verbose_name_plural = _("Progres pembangunan")

    @admin.display(description=_("Lampiran"))
    def download(self, obj):
        return file_link("progres", obj)


class AllocationIssuedInline(IssuedDocumentInline):
    fk_name = "allocation"


@admin.register(Allocation)
class AllocationAdmin(ReadOnlyAdmin):
    list_display = (
        "kpt_number",
        "holder",
        "plot",
        "area_m2",
        "issued_date",
        "end_date",
        "status",
        "idle",
        "progress",
        "last_report",
    )
    list_filter = ("status", IdleFilter, ReportOverdueFilter, "plot__allocation_type")
    search_fields = (
        "kpt_number",
        "ppt_number",
        "holder__name",
        "plot__code",
        "plot__name",
    )
    list_select_related = ("holder", "plot")
    date_hierarchy = "issued_date"
    inlines = (AllocationIssuedInline, PermitReportInline, DevelopmentReportInline)
    change_form_template = "admin/alokasi/allocation/change_form.html"
    fields = (
        "kpt_number",
        "ppt_number",
        "application",
        "holder",
        "plot",
        "area_m2",
        "activity",
        "issued_date",
        "start_date",
        "end_date",
        "idle_deadline",
        "status",
        "revoked_at",
        "revoke_reason",
    )
    readonly_fields = fields

    @admin.display(boolean=True, description=_("Lahan tidur"))
    def idle(self, obj):
        return obj.is_idle

    @admin.display(description=_("Progres"))
    def progress(self, obj):
        return f"{obj.latest_progress}%"

    @admin.display(description=_("Laporan terakhir"))
    def last_report(self, obj):
        return obj.last_report_date or "–"

    @admin.display(description=_("Batas mulai membangun"))
    def idle_deadline(self, obj):
        return obj.idle_deadline

    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        extra = {}
        if obj is not None:
            extra = {
                "can_revoke": request.user.has_perm("alokasi.revoke_allocation")
                and obj.status == enums.AllocationStatus.ACTIVE,
                "is_idle": obj.is_idle,
            }
        return super().change_view(
            request, object_id, form_url, {**(extra_context or {}), **extra}
        )

    def get_urls(self):
        return [
            path(
                "<int:pk>/cabut/",
                self.admin_site.admin_view(self.revoke_view),
                name="alokasi_allocation_revoke",
            ),
        ] + super().get_urls()

    def revoke_view(self, request, pk):
        if not request.user.has_perm("alokasi.revoke_allocation"):
            raise PermissionDenied
        allocation = get_object_or_404(Allocation, pk=pk)
        form = OfficerNoteForm(request.POST or None, required=True)
        if request.method == "POST" and form.is_valid():
            _run(
                request,
                lambda: services.revoke_allocation(
                    allocation, request.user, form.cleaned_data["note"]
                ),
                _("Alokasi %s dicabut.") % allocation.kpt_number,
            )
            return HttpResponseRedirect(
                reverse("admin:alokasi_allocation_change", args=[pk])
            )
        return _process_page(
            request,
            self,
            allocation,
            title=_("Cabut alokasi lahan"),
            intro=_(
                "Alokasi dinyatakan dicabut, lahan kembali berstatus tersedia namun disembunyikan dari "
                "portal sampai petugas menampilkannya lagi. Pemegang alokasi diberi tahu lewat surel."
            ),
            form=form,
            submit_label=_("Cabut alokasi"),
            danger=True,
        )


@admin.register(IssuedDocument)
class IssuedDocumentAdmin(ReadOnlyAdmin):
    list_display = ("number", "kind", "holder_name", "issued_at", "download", "verify")
    list_filter = ("kind",)
    search_fields = ("number", "holder_name", "token")
    date_hierarchy = "issued_at"
    fields = (
        "kind",
        "number",
        "application",
        "allocation",
        "holder_name",
        "issued_at",
        "token",
        "download",
    )
    readonly_fields = fields

    @admin.display(description=_("PDF"))
    def download(self, obj):
        return file_link("terbit", obj, _("Unduh"))

    @admin.display(description=_("Halaman verifikasi"))
    def verify(self, obj):
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>',
            reverse("portal:verify_token", args=[obj.token]),
            _("Buka"),
        )


@admin.register(PermitReport)
class PermitReportAdmin(ReadOnlyAdmin):
    list_display = (
        "allocation",
        "permit_type",
        "status",
        "permit_number",
        "issued_date",
        "modified_at",
    )
    list_filter = ("permit_type", "status")
    search_fields = (
        "allocation__kpt_number",
        "allocation__holder__name",
        "permit_number",
    )
    list_select_related = ("allocation", "allocation__holder")
    fields = (
        "allocation",
        "permit_type",
        "status",
        "permit_number",
        "issued_date",
        "download",
        "note",
        "modified_at",
    )
    readonly_fields = fields

    @admin.display(description=_("Dokumen"))
    def download(self, obj):
        return file_link("izin", obj)


@admin.register(DevelopmentReport)
class DevelopmentReportAdmin(ReadOnlyAdmin):
    list_display = (
        "allocation",
        "report_date",
        "stage",
        "progress_percent",
        "realized_investment",
        "workforce",
    )
    list_filter = ("stage",)
    search_fields = ("allocation__kpt_number", "allocation__holder__name")
    list_select_related = ("allocation", "allocation__holder")
    date_hierarchy = "report_date"
    fields = (
        "allocation",
        "report_date",
        "stage",
        "progress_percent",
        "realized_investment",
        "workforce",
        "description",
        "download",
        "reported_by",
    )
    readonly_fields = fields

    @admin.display(description=_("Lampiran"))
    def download(self, obj):
        return file_link("progres", obj)
