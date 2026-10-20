"""Panel petugas modul Manajemen Aset Lahan di /admin/asetlahan/.

Halaman alat (dasbor, peta tematik, Gantt, laporan, asisten, pencarian)
ada di asetlahan.admin_views dan ditautkan dari halaman indeks modul.
"""

from decimal import Decimal

from django import forms
from django.contrib import admin, messages
from django.contrib.gis.admin import GISModelAdmin
from django.db import transaction
from django.db.models import Count, Q
from django.forms.models import BaseInlineFormSet
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

from asetlahan import enums, geo, scope, services
from asetlahan.admin_views import file_link, file_url
from asetlahan.models import (
    Advocate,
    AssetCategory,
    AssetValuation,
    Bid,
    CaseHearing,
    Document,
    EncroachmentActionLog,
    EncroachmentCase,
    Facilitator,
    FieldReport,
    Grievance,
    GrievanceCategory,
    HeirMember,
    Heirship,
    LandAsset,
    LandTransaction,
    LegalCase,
    LiaisonActivity,
    MapOverlay,
    MapShare,
    ModuleSettings,
    OwnershipRecord,
    ResettlementSite,
    ResettlementUnit,
    SatelliteImage,
    Stakeholder,
    StakeholderEngagement,
    SurveyRequest,
    Task,
    TaxObligation,
    Team,
    Tender,
    ValuationItem,
)
from file_operations.private_files import PrivateFileField
from utils.group_permissions import UserGroup


def badge(color: str, label) -> str:
    return format_html(
        '<span style="color:#fff;background:{};padding:2px 6px;border-radius:3px;white-space:nowrap">{}</span>',
        color,
        label,
    )


def rupiah(value) -> str:
    from alokasi.templatetags.alokasi_tags import rupiah as fmt

    return fmt(value)


# --------------------------------------------------------------------------
# Mixin
# --------------------------------------------------------------------------


class _FileLink:
    def __init__(self, url, name):
        self.url = url
        self.name = name

    def __str__(self):
        return self.name


class PrivateFileWidget(forms.ClearableFileInput):
    """Tautan berkas privat lewat unduhan petugas, bukan /media/."""

    def __init__(self, kind, attrs=None):
        super().__init__(attrs)
        self.kind = kind

    def format_value(self, value):
        if value and getattr(value, "instance", None) is not None and value.instance.pk:
            return _FileLink(
                file_url(self.kind, value.instance), value.name.rsplit("/", 1)[-1]
            )
        return None


# Data master lintas modul yang boleh tampil sebagai label bagi semua petugas.
SHARED_MODELS = {"users.user", "leasing.serviceunit", "leasing.municipality"}


class ForeignFieldsMixin:
    """Tautan ke modul lain (pengadaan, alokasi, sewa, operasi) hanya tampil bila
    pengguna boleh melihat model tujuannya.

    Tanpa izin tersebut field disembunyikan dari formulir, daftar, filter, dan
    pencarian: label tidak bocor dan ID tidak dapat diisi lewat raw-id. Nilai
    yang sudah tersimpan tetap dipertahankan saat formulir disimpan.
    """

    def hidden_foreign_fields(self, request) -> set[str]:
        hidden = set()
        for field in self.model._meta.get_fields():
            if not field.concrete or not (field.many_to_one or field.many_to_many):
                continue
            meta = field.related_model._meta
            if meta.app_label == "asetlahan" or meta.label_lower in SHARED_MODELS:
                continue
            if not request.user.has_perm(f"{meta.app_label}.view_{meta.model_name}"):
                hidden.add(field.name)
        return hidden

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        hidden = self.hidden_foreign_fields(request)
        if not hidden:
            return fieldsets
        result = []
        for name, options in fieldsets:
            fields = [f for f in options.get("fields", ()) if f not in hidden]
            if fields:
                result.append((name, {**options, "fields": fields}))
        return result


def _strip_hidden(names, hidden):
    def visible(item):
        name = item[0] if isinstance(item, (list, tuple)) else item
        return not (
            isinstance(name, str) and name.split("__", 1)[0].lstrip("^=@") in hidden
        )

    return [item for item in names if visible(item)]


class AsetAdminMixin(ForeignFieldsMixin):
    """Pemisahan data per unit layanan, modul yang dapat dimatikan, berkas privat."""

    scope_lookup = "service_unit"
    module_flag = ""
    file_kind = ""

    def module_enabled(self) -> bool:
        return not self.module_flag or getattr(
            ModuleSettings.load(), self.module_flag, True
        )

    def has_module_permission(self, request):
        return self.module_enabled() and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return self.module_enabled() and super().has_view_permission(request, obj)

    def has_add_permission(self, request, *args):
        return self.module_enabled() and super().has_add_permission(request, *args)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if self.scope_lookup:
            queryset = scope.scoped(queryset, request.user, self.scope_lookup)
        return queryset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        related = db_field.related_model
        field_names = {f.name for f in related._meta.get_fields()}
        if (
            related.__module__.startswith("asetlahan")
            and "service_unit" in field_names
            and "queryset" not in kwargs
        ):
            kwargs["queryset"] = scope.scoped(
                related._default_manager.all(), request.user
            )
        if db_field.name == "service_unit" and not scope.sees_all(request.user):
            kwargs["queryset"] = request.user.service_units.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        related = db_field.related_model
        field_names = {f.name for f in related._meta.get_fields()}
        if related.__module__.startswith("asetlahan") and "service_unit" in field_names:
            # Pilihan & validasi hanya data unit layanan pengguna.
            kwargs["queryset"] = scope.scoped(
                related._default_manager.all(), request.user
            )
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def get_list_display(self, request):
        return _strip_hidden(
            super().get_list_display(request), self.hidden_foreign_fields(request)
        )

    def get_list_filter(self, request):
        return _strip_hidden(
            super().get_list_filter(request), self.hidden_foreign_fields(request)
        )

    def get_search_fields(self, request):
        return _strip_hidden(
            super().get_search_fields(request), self.hidden_foreign_fields(request)
        )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, PrivateFileField) and self.file_kind:
            kwargs["widget"] = PrivateFileWidget(self.file_kind)
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        field_names = {f.name for f in self.model._meta.get_fields()}
        if "service_unit" in field_names and "service_unit" not in initial:
            unit = scope.default_unit(request.user)
            if unit:
                initial["service_unit"] = unit.pk
        return initial

    def save_model(self, request, obj, form, change):
        if not change:
            for field in ("created_by", "uploaded_by", "requested_by"):
                if hasattr(obj, f"{field}_id") and getattr(obj, f"{field}_id") is None:
                    setattr(obj, field, request.user)
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        # Tautan M2M ke data unit lain tidak terlihat di formulir; pertahankan
        # agar tidak ikut terhapus saat petugas unit lain menyimpan.
        preserved = {}
        if change:
            for model_field in self.model._meta.many_to_many:
                name = model_field.name
                field = form.fields.get(name)
                if field is None or name not in form.cleaned_data:
                    continue
                preserved[name] = list(
                    getattr(form.instance, name)
                    .exclude(pk__in=field.queryset.values("pk"))
                    .values_list("pk", flat=True)
                )
        super().save_related(request, form, formsets, change)
        for name, pks in preserved.items():
            if pks:
                getattr(form.instance, name).add(*pks)


class AsetModelAdmin(AsetAdminMixin, admin.ModelAdmin):
    pass


class AsetGISAdmin(AsetAdminMixin, GISModelAdmin):
    pass


class ScopedInlineMixin(ForeignFieldsMixin):
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        related = db_field.related_model
        field_names = {f.name for f in related._meta.get_fields()}
        if (
            related.__module__.startswith("asetlahan")
            and "service_unit" in field_names
            and "queryset" not in kwargs
        ):
            kwargs["queryset"] = scope.scoped(
                related._default_manager.all(), request.user
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class DocumentInline(ScopedInlineMixin, admin.TabularInline):
    model = Document
    extra = 0
    fields = (
        "title",
        "doc_type",
        "number",
        "document_date",
        "phase",
        "file",
        "ocr_status",
    )
    readonly_fields = ("ocr_status",)
    show_change_link = True

    def get_queryset(self, request):
        # Dokumen yang juga ditautkan ke perkara/lelang/dll. yang tidak boleh
        # dilihat pengguna tidak ikut tampil di halaman objek lain.
        return scope.documents(request.user, super().get_queryset(request))

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, PrivateFileField):
            kwargs["widget"] = PrivateFileWidget("dokumen")
        return super().formfield_for_dbfield(db_field, request, **kwargs)


def related_links(items, admin_name: str) -> str:
    if not items:
        return "–"
    return format_html_join(
        format_html("<br>"),
        '<a href="{}">{}</a>',
        (
            (reverse(f"admin:asetlahan_{admin_name}_change", args=[i.pk]), str(i))
            for i in items
        ),
    )


# --------------------------------------------------------------------------
# Pengaturan & data master
# --------------------------------------------------------------------------


@admin.register(ModuleSettings)
class ModuleSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            _("Modul aktif"),
            {
                "fields": (
                    "enable_ownership",
                    "enable_valuation",
                    "enable_litigation",
                    "enable_encroachment",
                    "enable_resettlement",
                    "enable_survey",
                    "enable_tasks",
                    "enable_grievance",
                    "enable_tender",
                ),
                "description": _(
                    "Modul yang dimatikan disembunyikan dari panel dan dasbor; datanya tetap tersimpan."
                ),
            },
        ),
        (
            _("Pengingat & batas waktu"),
            {
                "fields": (
                    "lease_alert_days",
                    "title_alert_days",
                    "tax_alert_days",
                    "hearing_alert_days",
                    "grievance_sla_days",
                    "encroachment_followup_days",
                    "monitoring_interval_days",
                )
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = ModuleSettings.load()
        return HttpResponseRedirect(
            reverse("admin:asetlahan_modulesettings_change", args=[obj.pk])
        )


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "color_swatch", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)

    @admin.display(description=_("Warna"))
    def color_swatch(self, obj):
        return badge(obj.color, obj.color)


@admin.register(GrievanceCategory)
class GrievanceCategoryAdmin(AsetModelAdmin):
    module_flag = "enable_grievance"
    scope_lookup = ""
    list_display = ("name", "sla_days", "is_active")
    list_filter = ("is_active",)


@admin.register(Team)
class TeamAdmin(AsetModelAdmin):
    module_flag = "enable_tasks"
    list_display = ("name", "leader", "member_count", "open_tasks", "service_unit")
    search_fields = ("name", "description")
    filter_horizontal = ("members",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _members=Count("members", distinct=True),
                _open=Count(
                    "tasks",
                    filter=Q(tasks__status__in=enums.OPEN_TASK_STATUSES),
                    distinct=True,
                ),
            )
        )

    @admin.display(description=_("Anggota"), ordering="_members")
    def member_count(self, obj):
        return obj._members

    @admin.display(description=_("Tugas terbuka"), ordering="_open")
    def open_tasks(self, obj):
        return obj._open


# --------------------------------------------------------------------------
# Bank tanah & kepemilikan
# --------------------------------------------------------------------------


class OwnershipInline(admin.TabularInline):
    model = OwnershipRecord
    extra = 0
    fields = (
        "owner_name",
        "owner_type",
        "start_date",
        "end_date",
        "basis",
        "share_percentage",
    )


class TaxInline(admin.TabularInline):
    model = TaxObligation
    extra = 0
    fields = ("tax_type", "period", "amount", "due_date", "paid_date", "reference")
    show_change_link = True


class AssetImportForm(forms.Form):
    file = forms.FileField(
        label=_("Berkas spasial"),
        help_text=_(
            "GeoJSON, KML/KMZ (Google Earth), GeoPackage (.gpkg), atau Shapefile dalam ZIP. Maksimal 5.000 poligon."
        ),
    )
    category = forms.ModelChoiceField(
        AssetCategory.objects.filter(is_active=True),
        label=_("Kategori"),
        required=False,
    )
    status = forms.ChoiceField(
        label=_("Status"),
        choices=enums.AssetStatus.choices,
        initial=enums.AssetStatus.CONTROLLED,
    )


@admin.register(LandAsset)
class LandAssetAdmin(AsetGISAdmin):
    list_display = (
        "code",
        "name",
        "category",
        "status_badge",
        "area_m2",
        "title_type",
        "title_expiry",
        "village",
        "service_unit",
        "has_map",
    )
    list_filter = (
        "status",
        "category",
        "title_type",
        "acquisition_method",
        "service_unit",
        "municipality",
    )
    search_fields = (
        "code",
        "name",
        "title_number",
        "nib",
        "registered_owner",
        "village",
        "district",
        "address",
    )
    autocomplete_fields = ("pengadaan_parcel", "lease")
    raw_id_fields = ("alokasi_plot",)
    readonly_fields = (
        "valuation_summary",
        "related_records",
        "overlap_summary",
        "monitoring_due",
    )
    inlines = (OwnershipInline, TaxInline, DocumentInline)
    actions = ("export_xlsx",)
    change_list_template = "admin/asetlahan/landasset/change_list.html"
    change_form_template = "admin/asetlahan/landasset/change_form.html"
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "code",
                    "name",
                    "category",
                    "status",
                    "service_unit",
                    "responsible",
                )
            },
        ),
        (
            _("Pemantauan lapangan"),
            {
                "fields": (
                    "monitoring_interval_days",
                    "last_monitored_on",
                    "monitoring_due",
                )
            },
        ),
        (
            _("Lokasi & batas"),
            {
                "fields": (
                    "municipality",
                    "district",
                    "village",
                    "address",
                    "geometry",
                    "area_m2",
                )
            },
        ),
        (
            _("Alas hak"),
            {
                "fields": (
                    "title_type",
                    "title_number",
                    "nib",
                    "title_date",
                    "title_expiry",
                    "registered_owner",
                )
            },
        ),
        (
            _("Perolehan & nilai"),
            {
                "fields": (
                    "acquisition_method",
                    "acquisition_date",
                    "acquisition_cost",
                    "njop_per_m2",
                    "valuation_summary",
                )
            },
        ),
        (
            _("Pemanfaatan"),
            {
                "fields": (
                    "zoning",
                    "land_use",
                    "pengadaan_parcel",
                    "alokasi_plot",
                    "lease",
                    "note",
                )
            },
        ),
        (_("Terkait"), {"fields": ("related_records", "overlap_summary")}),
    )

    @admin.display(description=_("Status"), ordering="status")
    def status_badge(self, obj):
        return badge(obj.status_color, obj.get_status_display())

    @admin.display(boolean=True, description=_("Peta"))
    def has_map(self, obj):
        return obj.geometry is not None

    @admin.display(description=_("Jadwal pemantauan berikutnya"))
    def monitoring_due(self, obj):
        if not obj.pk:
            return "–"
        due = obj.monitoring_due_on()
        if due is None:
            return _("Tidak dijadwalkan")
        if due < timezone.localdate():
            return format_html(
                '<strong style="color:#cf222e">{} ({})</strong>',
                due.strftime("%d-%m-%Y"),
                _("terlambat"),
            )
        return due.strftime("%d-%m-%Y")

    def get_object(self, request, object_id, from_field=None):
        obj = super().get_object(request, object_id, from_field)
        if obj is not None:
            # Ringkasan baca-saja di bawah bergantung pada izin penampil.
            obj._viewer = request.user
        return obj

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.has_perm("asetlahan.view_assetvaluation"):
            return fieldsets
        return [
            (
                name,
                {
                    **options,
                    "fields": [
                        f for f in options["fields"] if f != "valuation_summary"
                    ],
                },
            )
            for name, options in fieldsets
        ]

    @admin.display(description=_("Penilaian terakhir"))
    def valuation_summary(self, obj):
        viewer = getattr(obj, "_viewer", None)
        if viewer is None or not viewer.has_perm("asetlahan.view_assetvaluation"):
            return "–"
        valuation = obj.latest_valuation if obj.pk else None
        if not valuation:
            return "–"
        return format_html(
            '<a href="{}">{}</a> – {} ({})',
            reverse("admin:asetlahan_assetvaluation_change", args=[valuation.pk]),
            rupiah(valuation.total_value),
            valuation.get_method_display(),
            valuation.valuation_date,
        )

    @admin.display(description=_("Perkara, okupasi, tugas, survei"))
    def related_records(self, obj):
        viewer = getattr(obj, "_viewer", None)
        if not obj.pk or viewer is None:
            return "–"
        rows = [
            (label, related_links(list(scope.scoped(manager.all(), viewer)[:10]), name))
            for label, manager, name in (
                (_("Perkara"), obj.legal_cases, "legalcase"),
                (_("Okupasi"), obj.encroachments, "encroachmentcase"),
                (_("Tugas"), obj.tasks, "task"),
                (_("Survei"), obj.surveys, "surveyrequest"),
            )
            if viewer.has_perm(f"asetlahan.view_{name}")
        ]
        if not rows:
            return "–"
        return format_html_join("", "<p><b>{}</b><br>{}</p>", rows)

    @admin.display(description=_("Irisan dengan bidang lain"))
    def overlap_summary(self, obj):
        viewer = getattr(obj, "_viewer", None)
        if not obj.pk or obj.geometry is None or viewer is None:
            return "–"
        if not (
            viewer.has_perm("pengadaan.view_acquisitionparcel")
            or viewer.has_perm("alokasi.view_landplot")
        ):
            return "–"
        found = geo.external_overlaps(obj, viewer)
        if not found["parcels"] and not found["plots"]:
            return _("Tidak ada irisan dengan bidang pengadaan atau lahan alokasi.")
        parcels = format_html_join(", ", "{}", ((str(p),) for p in found["parcels"]))
        plots = format_html_join(", ", "{}", ((str(p),) for p in found["plots"]))
        return format_html(
            "<b>{}</b> {}<br><b>{}</b> {}",
            _("Bidang pengadaan:"),
            parcels or "–",
            _("Lahan alokasi:"),
            plots or "–",
        )

    @admin.action(description=_("Ekspor ke Excel"), permissions=["view"])
    def export_xlsx(self, request, queryset):
        from asetlahan import reports

        return reports.export_response(reports.dataset("aset"), queryset, "xlsx")

    def get_urls(self):
        return [
            path(
                "impor/",
                self.admin_site.admin_view(self.import_view),
                name="asetlahan_landasset_import",
            ),
        ] + super().get_urls()

    def import_view(self, request):
        if not self.has_add_permission(request):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        form = AssetImportForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            from asetlahan.importers import AssetImportError, import_assets

            try:
                upload = form.cleaned_data["file"]
                created, updated = import_assets(
                    upload.read(),
                    filename=upload.name,
                    category=form.cleaned_data["category"],
                    status=form.cleaned_data["status"],
                    service_unit=scope.default_unit(request.user),
                    user=request.user,
                )
            except AssetImportError as error:
                messages.error(request, str(error))
            else:
                messages.success(
                    request,
                    _("%(c)d aset dibuat, %(u)d diperbarui.")
                    % {"c": created, "u": updated},
                )
                return HttpResponseRedirect(
                    reverse("admin:asetlahan_landasset_changelist")
                )
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "form": form,
            "title": _("Impor aset dari berkas spasial"),
        }
        return TemplateResponse(
            request, "admin/asetlahan/landasset/import.html", context
        )


class HeirMemberInline(ForeignFieldsMixin, admin.TabularInline):
    model = HeirMember
    extra = 1
    fields = (
        "name",
        "relation",
        "parent",
        "is_alive",
        "share_percentage",
        "entitled_party",
        "note",
    )
    raw_id_fields = ("entitled_party",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "parent":
            heirship_id = request.resolver_match.kwargs.get("object_id")
            kwargs["queryset"] = (
                HeirMember.objects.filter(heirship_id=heirship_id)
                if heirship_id
                else HeirMember.objects.none()
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Heirship)
class HeirshipAdmin(AsetModelAdmin):
    module_flag = "enable_ownership"
    scope_lookup = "asset__service_unit"
    list_display = (
        "decedent_name",
        "asset",
        "pengadaan_parcel",
        "date_of_death",
        "member_count",
    )
    search_fields = ("decedent_name", "members__name", "certificate_number")
    autocomplete_fields = ("asset", "pengadaan_parcel")
    readonly_fields = ("family_tree",)
    inlines = (HeirMemberInline,)

    class Media:
        css = {"all": ("asetlahan/admin.css",)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_members=Count("members"))

    @admin.display(description=_("Ahli waris"), ordering="_members")
    def member_count(self, obj):
        return obj._members

    @admin.display(description=_("Silsilah"))
    def family_tree(self, obj):
        if not obj.pk:
            return _("Simpan dahulu untuk melihat silsilah.")
        from django.template.loader import render_to_string

        return render_to_string("admin/asetlahan/heirship/tree.html", {"heirship": obj})


class EngagementInline(admin.TabularInline):
    model = StakeholderEngagement
    extra = 0
    fields = ("date", "method", "summary", "follow_up", "follow_up_date", "officer")


@admin.register(Stakeholder)
class StakeholderAdmin(AsetModelAdmin):
    module_flag = "enable_ownership"
    list_display = (
        "name",
        "stakeholder_type",
        "organization",
        "influence",
        "interest",
        "stance",
        "phone",
    )
    list_filter = (
        "stakeholder_type",
        "influence",
        "interest",
        "stance",
        "service_unit",
    )
    search_fields = ("name", "organization", "position", "phone", "email")
    filter_horizontal = ("assets",)
    autocomplete_fields = ("pengadaan_project",)
    inlines = (EngagementInline,)
    change_list_template = "admin/asetlahan/stakeholder/change_list.html"


# --------------------------------------------------------------------------
# Penilaian, pajak, keuangan
# --------------------------------------------------------------------------


class ValuationItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        from utils.money import check_fits

        structures = Decimal(0)
        for form in self.forms:
            data = getattr(form, "cleaned_data", None) or {}
            if not data or data.get("DELETE"):
                continue
            structures += Decimal(data.get("quantity") or 0) * Decimal(
                data.get("unit_value") or 0
            )
        check_fits(AssetValuation, "structures_value", structures)
        land = self.instance.compute_land_value()
        check_fits(AssetValuation, "total_value", land + structures)


class ValuationItemInline(admin.TabularInline):
    model = ValuationItem
    formset = ValuationItemFormSet
    extra = 1
    fields = (
        "item_type",
        "description",
        "quantity",
        "unit",
        "unit_value",
        "item_total",
    )
    readonly_fields = ("item_total",)

    @admin.display(description=_("Jumlah"))
    def item_total(self, obj):
        return rupiah(obj.total) if obj.pk else "–"


@admin.register(AssetValuation)
class AssetValuationAdmin(AsetModelAdmin):
    module_flag = "enable_valuation"
    scope_lookup = "asset__service_unit"
    list_display = (
        "asset",
        "valuation_date",
        "method",
        "land_value_fmt",
        "structures_value_fmt",
        "total_value_fmt",
    )
    list_filter = ("method",)
    search_fields = ("asset__code", "asset__name", "report_number", "appraiser")
    autocomplete_fields = ("asset",)
    readonly_fields = ("land_value", "structures_value", "total_value")
    inlines = (ValuationItemInline,)
    date_hierarchy = "valuation_date"

    @admin.display(description=_("Nilai tanah"), ordering="land_value")
    def land_value_fmt(self, obj):
        return rupiah(obj.land_value)

    @admin.display(description=_("Bangunan & benda"), ordering="structures_value")
    def structures_value_fmt(self, obj):
        return rupiah(obj.structures_value)

    @admin.display(description=_("Total"), ordering="total_value")
    def total_value_fmt(self, obj):
        return rupiah(obj.total_value)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.recompute()


@admin.register(TaxObligation)
class TaxObligationAdmin(AsetModelAdmin):
    module_flag = "enable_valuation"
    scope_lookup = "asset__service_unit"
    list_display = (
        "asset",
        "tax_type",
        "period",
        "amount_fmt",
        "due_date",
        "payment_state",
        "reference",
    )
    list_filter = ("tax_type", "period", ("paid_date", admin.EmptyFieldListFilter))
    search_fields = ("asset__code", "asset__name", "reference")
    autocomplete_fields = ("asset",)
    date_hierarchy = "due_date"
    actions = ("mark_paid",)

    @admin.display(description=_("Jumlah"), ordering="amount")
    def amount_fmt(self, obj):
        return rupiah(obj.amount)

    @admin.display(description=_("Status bayar"))
    def payment_state(self, obj):
        if obj.is_paid:
            return badge("#1a7f37", _("Lunas"))
        if obj.is_overdue:
            return badge("#cf222e", _("Terlambat"))
        return badge("#bf8700", _("Belum bayar"))

    @admin.action(
        description=_("Tandai lunas hari ini & catat transaksi"), permissions=["change"]
    )
    def mark_paid(self, request, queryset):
        count = 0
        today = timezone.localdate()
        with transaction.atomic():
            for tax in queryset.filter(paid_date__isnull=True).select_related("asset"):
                tax.paid_date = today
                tax.paid_amount = tax.amount or 0
                tax.save(update_fields=["paid_date", "paid_amount"])
                LandTransaction.objects.create(
                    transaction_type=enums.TransactionType.TAX,
                    date=today,
                    amount=tax.paid_amount,
                    asset=tax.asset,
                    tax=tax,
                    reference=tax.reference,
                    service_unit=tax.asset.service_unit,
                    description=str(tax),
                    created_by=request.user,
                )
                count += 1
        self.message_user(request, _("%d kewajiban ditandai lunas.") % count)


@admin.register(LandTransaction)
class LandTransactionAdmin(AsetModelAdmin):
    module_flag = "enable_valuation"
    list_display = (
        "number",
        "date",
        "transaction_type",
        "direction",
        "amount_fmt",
        "asset",
        "counterparty",
        "account_code",
        "reference",
    )
    list_filter = ("transaction_type", "service_unit")
    search_fields = (
        "number",
        "reference",
        "counterparty",
        "description",
        "asset__code",
        "account_code",
    )
    autocomplete_fields = ("asset", "pengadaan_project", "legal_case")
    raw_id_fields = ("tax", "household")
    readonly_fields = ("number", "created_by")
    date_hierarchy = "date"
    actions = ("export_erp_csv", "export_erp_xlsx")
    change_list_template = "admin/asetlahan/landtransaction/change_list.html"

    @admin.display(description=_("Arah"))
    def direction(self, obj):
        return (
            badge("#1a7f37", _("Masuk"))
            if obj.is_income
            else badge("#57606a", _("Keluar"))
        )

    @admin.display(description=_("Jumlah"), ordering="amount")
    def amount_fmt(self, obj):
        return rupiah(obj.amount)

    @admin.action(description=_("Ekspor jurnal ERP (CSV)"), permissions=["view"])
    def export_erp_csv(self, request, queryset):
        from asetlahan import finance

        return finance.erp_export(finance.journal_rows(queryset), "csv")

    @admin.action(description=_("Ekspor jurnal ERP (Excel)"), permissions=["view"])
    def export_erp_xlsx(self, request, queryset):
        from asetlahan import finance

        return finance.erp_export(finance.journal_rows(queryset), "xlsx")


# --------------------------------------------------------------------------
# Permukiman kembali
# --------------------------------------------------------------------------


class ResettlementUnitInline(ForeignFieldsMixin, admin.TabularInline):
    model = ResettlementUnit
    extra = 0
    fields = (
        "unit_number",
        "house_type",
        "area_m2",
        "status",
        "household",
        "occupied_since",
        "note",
    )
    raw_id_fields = ("household",)
    show_change_link = True


@admin.register(ResettlementSite)
class ResettlementSiteAdmin(AsetGISAdmin):
    module_flag = "enable_resettlement"
    list_display = (
        "name",
        "pengadaan_project",
        "unit_total",
        "occupied",
        "vacant",
        "map_link",
    )
    search_fields = ("name", "address")
    autocomplete_fields = ("pengadaan_project", "asset")
    inlines = (ResettlementUnitInline,)

    def get_queryset(self, request):
        S = enums.ResettlementUnitStatus
        return (
            super()
            .get_queryset(request)
            .annotate(
                _total=Count("units"),
                _occupied=Count("units", filter=Q(units__status=S.OCCUPIED)),
                _vacant=Count("units", filter=Q(units__status=S.VACANT)),
            )
        )

    @admin.display(description=_("Unit"), ordering="_total")
    def unit_total(self, obj):
        return obj._total

    @admin.display(description=_("Dihuni"), ordering="_occupied")
    def occupied(self, obj):
        return obj._occupied

    @admin.display(description=_("Kosong"), ordering="_vacant")
    def vacant(self, obj):
        return obj._vacant

    @admin.display(description=_("Peta"))
    def map_link(self, obj):
        return format_html(
            '<a href="{}?permukiman={}">{}</a>',
            reverse("asetlahan-map"),
            obj.pk,
            _("Peta hunian"),
        )


@admin.register(ResettlementUnit)
class ResettlementUnitAdmin(AsetGISAdmin):
    module_flag = "enable_resettlement"
    scope_lookup = "site__service_unit"
    list_display = (
        "unit_number",
        "site",
        "house_type",
        "area_m2",
        "status",
        "household",
        "occupied_since",
    )
    list_filter = ("status", "site")
    search_fields = ("unit_number", "site__name", "household__head_name")
    raw_id_fields = ("household",)


# --------------------------------------------------------------------------
# Perkara & advokat
# --------------------------------------------------------------------------


@admin.register(Advocate)
class AdvocateAdmin(AsetModelAdmin):
    module_flag = "enable_litigation"
    scope_lookup = ""
    list_display = (
        "name",
        "firm",
        "license_number",
        "is_internal",
        "phone",
        "email",
        "open_cases",
        "is_active",
    )
    list_filter = ("is_internal", "is_active")
    search_fields = ("name", "firm", "license_number", "email")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _open=Count(
                    "cases",
                    filter=Q(cases__status__in=enums.OPEN_CASE_STATUSES),
                    distinct=True,
                )
            )
        )

    @admin.display(description=_("Perkara aktif"), ordering="_open")
    def open_cases(self, obj):
        return obj._open


class HearingInline(admin.TabularInline):
    model = CaseHearing
    extra = 0
    fields = ("scheduled_at", "agenda", "location", "attended_by", "result")


@admin.register(LegalCase)
class LegalCaseAdmin(AsetModelAdmin):
    module_flag = "enable_litigation"
    list_display = (
        "number",
        "title",
        "court_case_number",
        "court",
        "our_position",
        "status",
        "outcome",
        "next_hearing_at",
        "responsible",
    )
    list_filter = ("status", "case_type", "court", "outcome", "service_unit")
    search_fields = (
        "number",
        "court_case_number",
        "title",
        "opposing_party",
        "court_name",
    )
    filter_horizontal = ("assets", "advocates")
    raw_id_fields = ("pengadaan_objection",)
    readonly_fields = ("number", "linked_encroachments")
    inlines = (HearingInline, DocumentInline)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "number",
                    "title",
                    "case_type",
                    "court",
                    "court_name",
                    "court_case_number",
                    "service_unit",
                    "responsible",
                )
            },
        ),
        (_("Para pihak"), {"fields": ("our_position", "opposing_party", "advocates")}),
        (
            _("Objek"),
            {
                "fields": (
                    "assets",
                    "disputed_area_m2",
                    "claim_value",
                    "pengadaan_objection",
                    "linked_encroachments",
                )
            },
        ),
        (
            _("Perkembangan"),
            {
                "fields": (
                    "status",
                    "filed_date",
                    "decision_date",
                    "outcome",
                    "decision_summary",
                    "note",
                )
            },
        ),
    )

    @admin.display(description=_("Sidang berikutnya"))
    def next_hearing_at(self, obj):
        hearing = obj.next_hearing
        if not hearing:
            return "–"
        local = timezone.localtime(hearing.scheduled_at)
        return f"{local:%d-%m-%Y %H:%M} – {hearing.agenda}"

    @admin.display(description=_("Kasus okupasi terkait"))
    def linked_encroachments(self, obj):
        return (
            related_links(list(obj.encroachments.all()), "encroachmentcase")
            if obj.pk
            else "–"
        )


# --------------------------------------------------------------------------
# Citra satelit & okupasi
# --------------------------------------------------------------------------


@admin.register(SatelliteImage)
class SatelliteImageAdmin(AsetGISAdmin):
    module_flag = "enable_encroachment"
    scope_lookup = ""
    file_kind = "citra"
    list_display = (
        "title",
        "provider",
        "platform",
        "data_type",
        "acquired_on",
        "resolution_m",
        "cloud_cover",
        "status",
        "cost_fmt",
        "viewable",
    )
    list_filter = ("status", "platform", "data_type", "provider")
    search_fields = ("title", "provider", "sensor")
    date_hierarchy = "requested_on"

    @admin.display(description=_("Biaya"), ordering="cost")
    def cost_fmt(self, obj):
        return rupiah(obj.cost)

    @admin.display(boolean=True, description=_("Tampil di peta"))
    def viewable(self, obj):
        return obj.is_viewable


class ActionInline(admin.TabularInline):
    model = EncroachmentActionLog
    extra = 0
    fields = ("date", "action", "letter_number", "description", "officer")


@admin.register(EncroachmentCase)
class EncroachmentCaseAdmin(AsetGISAdmin):
    module_flag = "enable_encroachment"
    list_display = (
        "number",
        "title",
        "asset",
        "detected_on",
        "detection_method",
        "encroached_area_m2",
        "status_badge",
        "stale",
        "responsible",
    )
    list_filter = (
        "status",
        "detection_method",
        "structure_type",
        "severity",
        "service_unit",
    )
    search_fields = ("number", "title", "encroacher_name", "asset__code", "asset__name")
    autocomplete_fields = ("asset", "legal_case")
    readonly_fields = ("number", "compare_link")
    inlines = (ActionInline, DocumentInline)
    actions = ("create_legal_case",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "number",
                    "title",
                    "asset",
                    "status",
                    "severity",
                    "service_unit",
                    "responsible",
                )
            },
        ),
        (
            _("Temuan"),
            {
                "fields": (
                    "detected_on",
                    "detection_method",
                    "structure_type",
                    "encroacher_name",
                    "occupant_count",
                    "description",
                )
            },
        ),
        (_("Lokasi"), {"fields": ("location", "area_geometry", "encroached_area_m2")}),
        (_("Bukti citra"), {"fields": ("before_image", "after_image", "compare_link")}),
        (_("Penyelesaian"), {"fields": ("legal_case", "resolved_on")}),
    )

    @admin.display(description=_("Status"), ordering="status")
    def status_badge(self, obj):
        color = (
            "#1a7f37"
            if obj.status == enums.EncroachmentStatus.RESOLVED
            else (
                "#57606a"
                if obj.status == enums.EncroachmentStatus.REJECTED
                else "#cf222e"
            )
        )
        return badge(color, obj.get_status_display())

    @admin.display(boolean=True, description=_("Tanpa tindak lanjut"))
    def stale(self, obj):
        if not obj.is_open:
            return False
        from asetlahan.monitoring import last_activity

        days = ModuleSettings.load().encroachment_followup_days
        return (timezone.localdate() - last_activity(obj)).days > days

    @admin.display(description=_("Bandingkan citra"))
    def compare_link(self, obj):
        if not obj.pk:
            return "–"
        url = reverse("asetlahan-imagery-compare") + f"?okupasi={obj.pk}"
        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            url,
            _("Buka pembanding citra sebelum/sesudah"),
        )

    def save_model(self, request, obj, form, change):
        if "area_geometry" in form.changed_data and not form.cleaned_data.get(
            "encroached_area_m2"
        ):
            obj.encroached_area_m2 = None
        super().save_model(request, obj, form, change)

    def has_create_legal_case_permission(self, request):
        return self.has_change_permission(request) and request.user.has_perm(
            "asetlahan.add_legalcase"
        )

    @admin.action(
        description=_("Limpahkan ke perkara baru"), permissions=["create_legal_case"]
    )
    def create_legal_case(self, request, queryset):
        created = 0
        for case in queryset.filter(legal_case__isnull=True):
            legal = LegalCase.objects.create(
                title=_("Penyerobotan lahan: %s") % case.title,
                case_type=enums.CaseType.CRIMINAL,
                court=enums.Court.POLICE,
                our_position=enums.CasePosition.PLAINTIFF,
                opposing_party=case.encroacher_name or _("Belum diketahui"),
                service_unit=case.service_unit,
                disputed_area_m2=case.encroached_area_m2,
                responsible=request.user,
            )
            if case.asset_id:
                legal.assets.add(case.asset)
            case.legal_case = legal
            case.status = enums.EncroachmentStatus.LITIGATION
            case.save(update_fields=["legal_case", "status"])
            created += 1
        self.message_user(request, _("%d perkara dibuat.") % created)


# --------------------------------------------------------------------------
# Survei, fasilitator, urusan instansi
# --------------------------------------------------------------------------


@admin.register(SurveyRequest)
class SurveyRequestAdmin(AsetGISAdmin):
    module_flag = "enable_survey"
    list_display = (
        "number",
        "survey_type",
        "asset",
        "status",
        "scheduled_date",
        "assigned_to",
        "vendor",
        "result_area_m2",
    )
    list_filter = ("status", "survey_type", "service_unit")
    search_fields = ("number", "purpose", "vendor", "asset__code", "asset__name")
    autocomplete_fields = ("asset", "pengadaan_project")
    readonly_fields = ("number", "requested_by")
    inlines = (DocumentInline,)
    actions = ("apply_result",)

    def has_apply_result_permission(self, request):
        # Mengubah batas aset: perlu izin ubah aset, bukan hanya izin ubah survei.
        return self.has_change_permission(request) and request.user.has_perm(
            "asetlahan.change_landasset"
        )

    @admin.action(
        description=_("Terapkan batas hasil ukur ke aset"),
        permissions=["apply_result"],
    )
    def apply_result(self, request, queryset):
        applied = 0
        assets = scope.scoped(LandAsset.objects.all(), request.user)
        for survey in queryset.filter(
            status=enums.SurveyStatus.DONE,
            result_geometry__isnull=False,
            asset__in=assets,
        ).select_related("asset"):
            asset = survey.asset
            asset.geometry = survey.result_geometry
            asset.area_m2 = survey.result_area_m2 or geo.area_m2(survey.result_geometry)
            asset.save(update_fields=["geometry", "area_m2", "modified_at"])
            applied += 1
        if applied:
            self.message_user(
                request, _("Batas %d aset diperbarui dari hasil ukur.") % applied
            )
        else:
            self.message_user(
                request,
                _(
                    "Hanya survei selesai dengan aset & hasil ukur yang dapat diterapkan."
                ),
                messages.WARNING,
            )


@admin.register(Facilitator)
class FacilitatorAdmin(AsetModelAdmin):
    module_flag = "enable_survey"
    scope_lookup = ""
    list_display = (
        "name",
        "facilitator_type",
        "organization",
        "area",
        "phone",
        "is_active",
    )
    list_filter = ("facilitator_type", "is_active")
    search_fields = ("name", "organization", "area")


@admin.register(LiaisonActivity)
class LiaisonActivityAdmin(AsetModelAdmin):
    module_flag = "enable_survey"
    list_display = (
        "subject",
        "activity_type",
        "agency",
        "status",
        "submitted_on",
        "next_follow_up",
        "officer",
        "asset",
    )
    list_filter = ("activity_type", "status", "agency", "service_unit")
    search_fields = ("subject", "agency", "reference_number", "asset__code")
    autocomplete_fields = ("asset", "pengadaan_project", "facilitator")
    inlines = (DocumentInline,)


# --------------------------------------------------------------------------
# Tugas
# --------------------------------------------------------------------------


class MineFilter(admin.SimpleListFilter):
    title = _("penugasan")
    parameter_name = "milik"

    def lookups(self, request, model_admin):
        return (
            ("saya", _("Tugas saya")),
            ("tim", _("Tugas tim saya")),
            ("terlambat", _("Lewat tenggat")),
        )

    def queryset(self, request, queryset):
        if self.value() == "saya":
            return queryset.filter(assignee=request.user)
        if self.value() == "tim":
            return queryset.filter(team__members=request.user).distinct()
        if self.value() == "terlambat":
            return queryset.filter(
                status__in=enums.OPEN_TASK_STATUSES, due_date__lt=timezone.localdate()
            )
        return queryset


@admin.register(Task)
class TaskAdmin(AsetModelAdmin):
    module_flag = "enable_tasks"
    list_display = (
        "number",
        "title",
        "task_type",
        "priority",
        "status",
        "assignee",
        "team",
        "due_date",
        "progress",
        "overdue",
    )
    list_filter = (
        MineFilter,
        "status",
        "priority",
        "task_type",
        "team",
        "korwil",
        "service_unit",
    )
    search_fields = ("number", "title", "description")
    autocomplete_fields = (
        "korwil",
        "asset",
        "legal_case",
        "encroachment",
        "pengadaan_project",
        "depends_on",
    )
    readonly_fields = ("number", "created_by", "completed_date")
    list_editable = ("status", "progress")
    change_list_template = "admin/asetlahan/task/change_list.html"
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "number",
                    "title",
                    "description",
                    "task_type",
                    "priority",
                    "status",
                    "progress",
                )
            },
        ),
        (
            _("Penugasan"),
            {"fields": ("assignee", "team", "korwil", "service_unit", "created_by")},
        ),
        (
            _("Jadwal"),
            {"fields": ("start_date", "due_date", "completed_date", "depends_on")},
        ),
        (
            _("Terkait"),
            {"fields": ("asset", "legal_case", "encroachment", "pengadaan_project")},
        ),
    )

    # Petugas lapangan hanya memperbarui kemajuan tugasnya sendiri.
    FIELD_EDITABLE = ("status", "progress")

    @admin.display(boolean=True, description=_("Terlambat"))
    def overdue(self, obj):
        return obj.is_overdue

    @staticmethod
    def task_role(request) -> str:
        """``full`` (Administrator, Petugas Aset/Hukum), ``korwil``, atau ``field``."""
        role = getattr(request, "_asetlahan_task_role", None)
        if role is None:
            user = request.user
            groups = set(user.groups.values_list("pk", flat=True))
            full = {
                UserGroup.PAAKAYTTAJA,
                UserGroup.PETUGAS_ASET,
                UserGroup.PETUGAS_HUKUM,
            }
            if user.is_superuser or groups & full:
                role = "full"
            elif UserGroup.KOORDINATOR_WILAYAH in groups:
                role = "korwil"
            elif UserGroup.PETUGAS_LAPANGAN in groups:
                role = "field"
            else:
                role = "full"
            request._asetlahan_task_role = role
        return role

    @staticmethod
    def _user_korwils(user):
        from operasi.geo import user_korwils

        return user_korwils(user)

    def editable_q(self, request) -> Q:
        """Tugas yang boleh diubah pengguna (di dalam unit layanannya)."""
        user = request.user
        role = self.task_role(request)
        if role == "full":
            return Q()
        mine = Q(assignee=user) | Q(assignee__isnull=True, team__members=user)
        if role == "korwil":
            mine |= Q(korwil__in=self._user_korwils(user))
        return Q(pk__in=Task.objects.filter(mine).values("pk"))

    def has_change_permission(self, request, obj=None):
        allowed = super().has_change_permission(request, obj)
        if not allowed or obj is None or self.task_role(request) == "full":
            return allowed
        return Task.objects.filter(pk=obj.pk).filter(self.editable_q(request)).exists()

    def _get_list_editable_queryset(self, request, prefix):
        queryset = super()._get_list_editable_queryset(request, prefix)
        return queryset.filter(self.editable_q(request))

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is None or self.task_role(request) != "field":
            return readonly
        names = [f for _name, options in self.fieldsets for f in options["fields"]]
        return readonly + [
            f for f in names if f not in self.FIELD_EDITABLE and f not in readonly
        ]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "korwil" and self.task_role(request) == "korwil":
            kwargs["queryset"] = self._user_korwils(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        notify = obj.assignee_id and (not change or "assignee" in form.changed_data)
        super().save_model(request, obj, form, change)
        if notify and obj.assignee.email and obj.assignee_id != request.user.pk:
            services.send_email(
                [obj.assignee.email],
                _("Tugas baru: %s") % obj.title,
                _("Anda ditugaskan: %(t)s\nTenggat: %(d)s\n\n%(u)s")
                % {
                    "t": f"{obj.number} {obj.title}",
                    "d": obj.due_date or "-",
                    "u": services.admin_url(f"task/{obj.pk}/change/"),
                },
            )


# --------------------------------------------------------------------------
# Pengaduan
# --------------------------------------------------------------------------


@admin.register(Grievance)
class GrievanceAdmin(AsetModelAdmin):
    module_flag = "enable_grievance"
    file_kind = "pengaduan"
    list_display = (
        "number",
        "subject",
        "complainant_name",
        "channel",
        "category",
        "status",
        "due_date",
        "overdue",
        "assigned_to",
    )
    list_filter = ("status", "channel", "category", "service_unit")
    search_fields = (
        "number",
        "subject",
        "complainant_name",
        "phone",
        "email",
        "description",
    )
    autocomplete_fields = ("asset", "pengadaan_project", "encroachment")
    readonly_fields = ("number", "access_code", "resolved_on", "created_at")
    actions = ("create_encroachment",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "number",
                    "access_code",
                    "created_at",
                    "channel",
                    "category",
                    "status",
                    "assigned_to",
                    "due_date",
                    "service_unit",
                )
            },
        ),
        (_("Pelapor"), {"fields": ("complainant_name", "phone", "email")}),
        (
            _("Pengaduan"),
            {
                "fields": (
                    "subject",
                    "description",
                    "location_text",
                    "location",
                    "attachment",
                )
            },
        ),
        (_("Terkait"), {"fields": ("asset", "pengadaan_project", "encroachment")}),
        (_("Tindak lanjut"), {"fields": ("response", "internal_note", "resolved_on")}),
    )

    @admin.display(boolean=True, description=_("Lewat batas"))
    def overdue(self, obj):
        return obj.is_overdue

    def save_model(self, request, obj, form, change):
        changed = change and ({"status", "response"} & set(form.changed_data))
        super().save_model(request, obj, form, change)
        if changed:
            from asetlahan.portal_views import notify_grievance_update

            notify_grievance_update(obj)

    def has_create_encroachment_permission(self, request):
        return self.has_change_permission(request) and request.user.has_perm(
            "asetlahan.add_encroachmentcase"
        )

    @admin.action(
        description=_("Jadikan kasus okupasi"), permissions=["create_encroachment"]
    )
    def create_encroachment(self, request, queryset):
        created = 0
        for grievance in queryset.filter(encroachment__isnull=True):
            case = EncroachmentCase.objects.create(
                title=grievance.subject,
                asset=grievance.asset,
                detection_method=enums.DetectionMethod.REPORT,
                location=grievance.location,
                description=grievance.description,
                service_unit=grievance.service_unit,
                responsible=request.user,
            )
            grievance.encroachment = case
            grievance.save(update_fields=["encroachment"])
            created += 1
        self.message_user(request, _("%d kasus okupasi dibuat.") % created)


# --------------------------------------------------------------------------
# Lelang
# --------------------------------------------------------------------------


class BidInline(admin.TabularInline):
    model = Bid
    extra = 0
    fields = (
        "bidder_name",
        "email",
        "amount",
        "proposal_link",
        "technical_score",
        "status",
        "evaluation_note",
    )
    readonly_fields = ("bidder_name", "email", "amount", "proposal_link")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description=_("Dokumen"))
    def proposal_link(self, obj):
        return file_link("penawaran", obj)


@admin.register(Tender)
class TenderAdmin(AsetModelAdmin):
    module_flag = "enable_tender"
    list_display = (
        "number",
        "title",
        "method",
        "location",
        "reserve_price_fmt",
        "open_at",
        "close_at",
        "status",
        "bid_count",
        "winner",
    )
    list_filter = ("status", "method", "service_unit")
    search_fields = ("number", "title", "description")
    autocomplete_fields = ("asset",)
    raw_id_fields = ("alokasi_plot",)
    readonly_fields = ("number", "winner", "awarded_on")
    inlines = (BidInline, DocumentInline)
    actions = ("announce", "close", "award_highest")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_bids=Count("bids"))

    @admin.display(description=_("Objek"))
    def location(self, obj):
        return obj.location_name

    @admin.display(description=_("Nilai limit"), ordering="reserve_price")
    def reserve_price_fmt(self, obj):
        return rupiah(obj.reserve_price)

    @admin.display(description=_("Penawaran"), ordering="_bids")
    def bid_count(self, obj):
        return obj._bids

    @admin.action(description=_("Umumkan di portal"), permissions=["change"])
    def announce(self, request, queryset):
        updated = queryset.filter(status=enums.TenderStatus.DRAFT).update(
            status=enums.TenderStatus.ANNOUNCED
        )
        self.message_user(request, _("%d lelang diumumkan.") % updated)

    @admin.action(description=_("Tutup penerimaan penawaran"), permissions=["change"])
    def close(self, request, queryset):
        updated = queryset.filter(status=enums.TenderStatus.ANNOUNCED).update(
            status=enums.TenderStatus.CLOSED
        )
        self.message_user(request, _("%d lelang ditutup.") % updated)

    @admin.action(
        description=_("Tetapkan pemenang (penawaran lolos tertinggi)"),
        permissions=["change"],
    )
    def award_highest(self, request, queryset):
        from asetlahan.tenders import TenderError, award

        for tender in queryset:
            try:
                bid = award(tender)
            except TenderError as error:
                self.message_user(request, f"{tender.number}: {error}", messages.ERROR)
            else:
                self.message_user(
                    request,
                    _("%(t)s dimenangkan %(b)s.")
                    % {"t": tender.number, "b": bid.bidder_name},
                )


@admin.register(Bid)
class BidAdmin(AsetModelAdmin):
    module_flag = "enable_tender"
    scope_lookup = "tender__service_unit"
    file_kind = "penawaran"
    list_display = (
        "tender",
        "bidder_name",
        "amount_fmt",
        "technical_score",
        "status",
        "created_at",
    )
    list_filter = ("status", "tender")
    search_fields = ("bidder_name", "email", "tender__number")
    readonly_fields = (
        "tender",
        "applicant",
        "bidder_name",
        "email",
        "phone",
        "amount",
        "proposal",
    )

    def has_add_permission(self, request, *args):
        return False

    @admin.display(description=_("Nilai penawaran"), ordering="amount")
    def amount_fmt(self, obj):
        return rupiah(obj.amount)


# --------------------------------------------------------------------------
# Dokumen, peta berbagi, laporan lapangan
# --------------------------------------------------------------------------


@admin.register(Document)
class DocumentAdmin(AsetModelAdmin):
    file_kind = "dokumen"
    list_display = (
        "title",
        "doc_type",
        "number",
        "document_date",
        "linked_to",
        "ocr_status",
        "uploaded_by",
        "created_at",
    )
    list_filter = ("doc_type", "ocr_status", "service_unit")
    search_fields = ("title", "number", "extracted_text", "note")
    autocomplete_fields = (
        "asset",
        "legal_case",
        "encroachment",
        "survey",
        "liaison",
        "tender",
    )
    readonly_fields = (
        "uploaded_by",
        "ocr_status",
        "extracted_fields_table",
        "extracted_text",
    )
    actions = ("run_ocr",)
    change_form_template = "admin/asetlahan/document/change_form.html"
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "doc_type",
                    "number",
                    "document_date",
                    "file",
                    "phase",
                    "service_unit",
                    "note",
                )
            },
        ),
        (
            _("Terkait dengan"),
            {
                "fields": (
                    "asset",
                    "legal_case",
                    "encroachment",
                    "survey",
                    "liaison",
                    "tender",
                )
            },
        ),
        (
            _("Hasil OCR"),
            {
                "fields": ("ocr_status", "extracted_fields_table", "extracted_text"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        # Dokumen perkara, lelang, dsb. hanya untuk yang boleh melihat objeknya.
        return scope.documents(request.user, super().get_queryset(request))

    def has_change_permission(self, request, obj=None):
        allowed = super().has_change_permission(request, obj)
        if obj is None or not allowed:
            return allowed
        return scope.document_allows(request.user, obj, "change")

    def has_delete_permission(self, request, obj=None):
        allowed = super().has_delete_permission(request, obj)
        if obj is None or not allowed:
            return allowed
        return scope.document_allows(request.user, obj, "delete")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        links = dict(scope.DOCUMENT_LINKS)
        if db_field.name in links and not request.user.has_perm(
            f"asetlahan.change_{links[db_field.name]}"
        ):
            # Menautkan dokumen = mengubah berkas objek tersebut.
            kwargs["queryset"] = db_field.related_model._default_manager.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description=_("Terkait"))
    def linked_to(self, obj):
        for related in (
            obj.asset,
            obj.legal_case,
            obj.encroachment,
            obj.survey,
            obj.liaison,
            obj.tender,
        ):
            if related is not None:
                return str(related)
        return "–"

    @admin.display(description=_("Data terbaca"))
    def extracted_fields_table(self, obj):
        from asetlahan.ocr import FIELD_LABELS

        if not obj.extracted_fields:
            return "–"
        rows = (
            (FIELD_LABELS.get(k, k), v) for k, v in obj.extracted_fields.items() if v
        )
        return format_html(
            "<table>{}</table>",
            format_html_join("", "<tr><th>{}</th><td>{}</td></tr>", rows),
        )

    @admin.action(description=_("Baca teks dokumen (OCR)"), permissions=["change"])
    def run_ocr(self, request, queryset):
        from asetlahan.ocr import process_document

        done = sum(
            1
            for doc in queryset[:50]
            if scope.document_allows(request.user, doc, "change")
            and process_document(doc)
        )
        self.message_user(request, _("%d dokumen berhasil dibaca.") % done)

    def get_urls(self):
        return [
            path(
                "<int:pk>/terapkan/",
                self.admin_site.admin_view(self.apply_view),
                name="asetlahan_document_apply",
            ),
        ] + super().get_urls()

    def apply_view(self, request, pk):
        from django.core.exceptions import PermissionDenied

        from asetlahan.ocr import apply_to_asset

        document = get_object_or_404(self.get_queryset(request), pk=pk)
        if request.method != "POST" or not request.user.has_perm(
            "asetlahan.change_landasset"
        ):
            raise PermissionDenied
        if not document.asset_id:
            messages.error(request, _("Hubungkan dokumen dengan aset terlebih dahulu."))
        else:
            changed = apply_to_asset(document)
            if changed:
                messages.success(
                    request,
                    _("Aset diperbarui: %s.") % ", ".join(str(c) for c in changed),
                )
            else:
                messages.info(
                    request,
                    _(
                        "Tidak ada isian kosong pada aset yang dapat diisi dari dokumen ini."
                    ),
                )
        return HttpResponseRedirect(
            reverse("admin:asetlahan_document_change", args=[pk])
        )


# Sumber data peta berbagi: (field, izin untuk membagikan, izin nama pemilik).
SHARE_SOURCES = (
    ("assets", (), ("asetlahan.view_ownershiprecord",)),
    (
        "pengadaan_project",
        ("pengadaan.view_acquisitionproject", "pengadaan.view_acquisitionparcel"),
        ("pengadaan.view_entitledparty",),
    ),
    (
        "resettlement_site",
        ("asetlahan.view_resettlementunit",),
        ("pengadaan.view_affectedhousehold",),
    ),
)


class MapShareForm(forms.ModelForm):
    """Tautan publik hanya boleh memuat data yang boleh dilihat pembuatnya."""

    user = None  # diisi MapShareAdmin.get_form

    class Meta:
        model = MapShare
        fields = "__all__"

    def _value(self, name):
        if name in self.cleaned_data:
            return self.cleaned_data[name]
        if not self.instance.pk:
            return None
        value = getattr(self.instance, name)
        return value.all() if name == "assets" else value

    def _changed(self, name) -> bool:
        return not self.instance.pk or name in self.changed_data

    def clean(self):
        cleaned = super().clean()
        user = self.user
        if user is None:
            return cleaned
        owners_changed = self._changed("show_owner_names")
        show_owners = self._value("show_owner_names")
        missing_owner_perm = []
        for name, share_perms, owner_perms in SHARE_SOURCES:
            value = self._value(name)
            present = value.exists() if hasattr(value, "exists") else bool(value)
            if not present or not (owners_changed or self._changed(name)):
                continue
            if self._changed(name) and not user.has_perms(share_perms):
                self.add_error(
                    name if name in self.fields else None,
                    _("Anda tidak berhak membagikan data ini."),
                )
            if show_owners and not user.has_perms(owner_perms):
                missing_owner_perm.append(
                    str(MapShare._meta.get_field(name).verbose_name)
                )
        if missing_owner_perm and "show_owner_names" in self.fields:
            self.add_error(
                "show_owner_names",
                _("Anda tidak berhak menampilkan nama pemegang hak untuk: %s.")
                % ", ".join(missing_owner_perm),
            )
        elif missing_owner_perm:
            raise forms.ValidationError(
                _("Anda tidak berhak menampilkan nama pemegang hak untuk: %s.")
                % ", ".join(missing_owner_perm)
            )
        return cleaned


@admin.register(MapShare)
class MapShareAdmin(AsetModelAdmin):
    # Tanpa scope_lookup bawaan: tautan dibatasi per unit atau pembuat (get_queryset).
    scope_lookup = ""
    form = MapShareForm
    list_display = (
        "title",
        "public_link",
        "expires_at",
        "is_active",
        "view_count",
        "service_unit",
        "created_by",
    )
    list_filter = ("is_active", "service_unit")
    filter_horizontal = ("assets",)
    autocomplete_fields = ("pengadaan_project",)
    readonly_fields = ("public_link", "view_count", "created_by")

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        user = request.user
        if scope.sees_all(user):
            return queryset
        # Tautan berisi token publik: tanpa unit hanya terlihat oleh pembuatnya.
        return queryset.filter(
            Q(created_by=user) | Q(service_unit__in=scope.unit_ids(user))
        )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        return type(form.__name__, (form,), {"user": request.user})

    def save_model(self, request, obj, form, change):
        if obj.service_unit_id is None and not scope.sees_all(request.user):
            obj.service_unit = scope.default_unit(request.user)
        super().save_model(request, obj, form, change)

    @admin.display(description=_("Tautan publik"))
    def public_link(self, obj):
        if not obj.pk:
            return _("Tersedia setelah disimpan.")
        url = services.app_url(reverse("asetlahan-share", args=[obj.token]))
        return format_html('<a href="{0}" target="_blank" rel="noopener">{0}</a>', url)


class MapOverlayForm(forms.ModelForm):
    import_file = forms.FileField(
        label=_("Impor objek dari berkas"),
        required=False,
        help_text=_(
            "GeoJSON, KML/KMZ, GeoPackage, atau Shapefile (ZIP). Titik, garis, dan poligon "
            "diterima. Objek lama di lapisan ini diganti isi berkas."
        ),
    )

    class Meta:
        model = MapOverlay
        fields = "__all__"

    def clean_import_file(self):
        upload = self.cleaned_data.get("import_file")
        if not upload:
            return None
        if upload.size > 50 * 1024 * 1024:
            raise forms.ValidationError(_("Berkas maksimal 50 MB."))
        from asetlahan.importers import AssetImportError, read_overlay_features

        try:
            return read_overlay_features(upload.read(), upload.name)
        except AssetImportError as error:
            raise forms.ValidationError(str(error))

    def clean(self):
        cleaned = super().clean()
        if (
            not self.instance.pk
            and not cleaned.get("import_file")
            and "import_file" not in self.errors
        ):
            self.add_error("import_file", _("Unggah berkas peta untuk lapisan baru."))
        return cleaned


@admin.register(MapOverlay)
class MapOverlayAdmin(AsetModelAdmin):
    scope_lookup = ""
    form = MapOverlayForm
    list_display = (
        "name",
        "kind",
        "color_swatch",
        "feature_count",
        "is_active",
        "show_by_default",
        "modified_at",
    )
    list_filter = ("kind", "is_active")
    search_fields = ("name", "source", "note")
    readonly_fields = ("feature_count",)
    fields = (
        "name",
        "kind",
        "color",
        "source",
        "is_active",
        "show_by_default",
        "import_file",
        "feature_count",
        "note",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_features=Count("features"))

    @admin.display(description=_("Jumlah objek"), ordering="_features")
    def feature_count(self, obj):
        if not obj.pk:
            return "–"
        from alokasi.templatetags.alokasi_tags import angka

        count = getattr(obj, "_features", None)
        return angka(obj.features.count() if count is None else count)

    @admin.display(description=_("Warna"))
    def color_swatch(self, obj):
        return badge(obj.display_color, obj.display_color)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        features = form.cleaned_data.get("import_file")
        if features:
            from asetlahan.importers import replace_overlay_features

            count = replace_overlay_features(obj, features)
            self.message_user(
                request, _("%(count)s objek diimpor ke lapisan.") % {"count": count}
            )


@admin.register(FieldReport)
class FieldReportAdmin(AsetGISAdmin):
    file_kind = "lapangan"
    list_display = (
        "captured_at",
        "report_type",
        "asset",
        "reported_by",
        "accuracy_m",
        "has_photo",
        "encroachment",
    )
    list_filter = ("report_type", "service_unit")
    search_fields = ("note", "asset__code", "asset__name")
    readonly_fields = ("client_id", "captured_at", "reported_by", "accuracy_m")
    autocomplete_fields = ("asset", "encroachment")
    date_hierarchy = "captured_at"
    actions = ("to_encroachment",)

    def has_add_permission(self, request, *args):
        return False

    @admin.display(boolean=True, description=_("Foto"))
    def has_photo(self, obj):
        return bool(obj.photo)

    def has_to_encroachment_permission(self, request):
        return self.has_change_permission(request) and request.user.has_perm(
            "asetlahan.add_encroachmentcase"
        )

    @admin.action(
        description=_("Jadikan kasus okupasi"), permissions=["to_encroachment"]
    )
    def to_encroachment(self, request, queryset):
        created = 0
        for report in queryset.filter(encroachment__isnull=True):
            case = EncroachmentCase.objects.create(
                title=_("Temuan lapangan %s")
                % timezone.localtime(report.captured_at).strftime("%d-%m-%Y"),
                asset=report.asset,
                detection_method=enums.DetectionMethod.PATROL,
                location=report.location,
                detected_on=timezone.localtime(report.captured_at).date(),
                description=report.note,
                service_unit=report.service_unit,
                responsible=request.user,
            )
            if report.photo:
                Document.objects.create(
                    title=_("Foto temuan lapangan"),
                    doc_type=enums.DocumentType.PHOTO,
                    file=report.photo.name,
                    phase=enums.PhotoPhase.BEFORE,
                    encroachment=case,
                    uploaded_by=report.reported_by,
                )
            report.encroachment = case
            report.save(update_fields=["encroachment"])
            created += 1
        self.message_user(request, _("%d kasus okupasi dibuat.") % created)
