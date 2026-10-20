from django.contrib import admin

from pengadaan import access
from pengadaan import models as m

SENSITIVE_PERMISSION = "pengadaan.view_sensitive_personal_data"


class SensitiveFieldsAdminMixin:
    """Sembunyikan NIK/rekening/KK dari staf tanpa izin data pribadi."""

    sensitive_fields: tuple[str, ...] = ()

    def get_exclude(self, request, obj=None):
        exclude = list(super().get_exclude(request, obj) or ())
        if not request.user.has_perm(SENSITIVE_PERMISSION):
            exclude += [f for f in self.sensitive_fields if f not in exclude]
        return exclude


class ProjectScopedAdmin(admin.ModelAdmin):
    """Panel admin mengikuti pembatasan proyek yang sama dengan API."""

    def get_queryset(self, request):
        return access.scope_queryset(super().get_queryset(request), request.user)


@admin.register(m.Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("date", "name", "is_collective_leave")
    list_filter = ("is_collective_leave",)
    search_fields = ("name",)
    date_hierarchy = "date"


@admin.register(m.DeadlineRule)
class DeadlineRuleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "amount", "unit", "legal_basis")
    readonly_fields = ("code",)
    search_fields = ("code", "name", "legal_basis")

    def has_add_permission(self, request):
        # Kode aturan dipakai program; tambah aturan baru lewat migrasi.
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class MilestoneInline(admin.TabularInline):
    model = m.AcquisitionMilestone
    extra = 0
    fields = ("sequence", "stage", "title", "planned_date", "actual_date", "status")


@admin.register(m.AcquisitionProject)
class AcquisitionProjectAdmin(ProjectScopedAdmin):
    list_display = ("identifier", "name", "acquisition_type", "stage", "status")
    list_filter = ("acquisition_type", "stage", "status", "priority")
    search_fields = ("identifier", "name", "requiring_agency")
    readonly_fields = ("identifier",)
    raw_id_fields = ("executing_chair", "created_by", "municipality")
    filter_horizontal = ("assigned_users",)
    inlines = [MilestoneInline]


class PartyInline(SensitiveFieldsAdminMixin, admin.StackedInline):
    model = m.EntitledParty
    extra = 0
    exclude = ("deleted", "deleted_by_cascade")
    sensitive_fields = ("nik", "bank_account_number")


class InventoryItemInline(admin.TabularInline):
    model = m.InventoryItem
    extra = 0
    fields = (
        "item_type",
        "description",
        "quantity",
        "unit",
        "condition",
        "unit_value",
        "party",
        "note",
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Pemilik objek hanya dari pihak yang berhak pada bidang ini.
        if db_field.name == "party":
            parcel_id = request.resolver_match.kwargs.get("object_id")
            kwargs["queryset"] = (
                m.EntitledParty.objects.filter(parcel_id=parcel_id)
                if parcel_id and str(parcel_id).isdigit()
                else m.EntitledParty.objects.none()
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(m.AcquisitionParcel)
class AcquisitionParcelAdmin(ProjectScopedAdmin):
    list_display = ("parcel_number", "project", "right_type", "status", "is_disputed")
    list_filter = ("status", "right_type", "is_disputed", "project")
    search_fields = ("parcel_number", "nib", "village", "certificate_number")
    readonly_fields = ("status",)
    raw_id_fields = ("project", "district")
    inlines = [PartyInline, InventoryItemInline]


@admin.register(m.Compensation)
class CompensationAdmin(ProjectScopedAdmin):
    list_display = ("parcel", "party", "form", "amount", "status")
    list_filter = ("status", "form")
    # Status hanya berubah lewat validasi, pembayaran dan konsinyasi.
    readonly_fields = ("status", "validated_on", "validated_by")
    raw_id_fields = (
        "parcel",
        "party",
        "valuation",
        "deliberation_result",
        "court_decision",
    )


@admin.register(m.AffectedHousehold)
class AffectedHouseholdAdmin(SensitiveFieldsAdminMixin, ProjectScopedAdmin):
    list_display = ("head_name", "project", "displacement", "stage")
    list_filter = ("displacement", "stage")
    search_fields = ("head_name",)
    raw_id_fields = ("project", "parcel")
    sensitive_fields = ("nik", "family_card_number")


for model in (
    m.ParcelSurvey,
    m.InventoryItem,
    m.Announcement,
    m.Valuation,
    m.Deliberation,
    m.DeliberationResult,
    m.Objection,
    m.Consignment,
    m.CompensationPayment,
    m.RightsRelease,
    m.Handover,
):
    admin.site.register(model, ProjectScopedAdmin)


@admin.register(m.AcquisitionDocument)
class AcquisitionDocumentAdmin(ProjectScopedAdmin):
    list_display = ("title", "document_type", "project", "parcel")
    list_filter = ("document_type",)
    search_fields = ("title", "number")
    raw_id_fields = ("project", "parcel", "party")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Sama seperti API: pindaian KTP, sertipikat, bukti bayar dan dokumen
        # milik pihak tertentu hanya untuk pemegang izin data pribadi.
        if not request.user.has_perm(SENSITIVE_PERMISSION):
            qs = qs.exclude(document_type__in=access.SENSITIVE_DOCUMENT_TYPES).filter(
                party__isnull=True
            )
        return qs
