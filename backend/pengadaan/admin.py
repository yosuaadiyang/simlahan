from django.contrib import admin

from pengadaan import models as m


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
class AcquisitionProjectAdmin(admin.ModelAdmin):
    list_display = ("identifier", "name", "acquisition_type", "stage", "status")
    list_filter = ("acquisition_type", "stage", "status", "priority")
    search_fields = ("identifier", "name", "requiring_agency")
    readonly_fields = ("identifier",)
    raw_id_fields = ("executing_chair", "created_by", "municipality")
    inlines = [MilestoneInline]


class PartyInline(admin.StackedInline):
    model = m.EntitledParty
    extra = 0
    exclude = ("deleted", "deleted_by_cascade")


@admin.register(m.AcquisitionParcel)
class AcquisitionParcelAdmin(admin.ModelAdmin):
    list_display = ("parcel_number", "project", "right_type", "status", "is_disputed")
    list_filter = ("status", "right_type", "is_disputed", "project")
    search_fields = ("parcel_number", "nib", "village", "certificate_number")
    readonly_fields = ("status",)
    raw_id_fields = ("project", "district")
    inlines = [PartyInline]


for model in (
    m.ParcelSurvey,
    m.Announcement,
    m.Valuation,
    m.Deliberation,
    m.DeliberationResult,
    m.Objection,
    m.Consignment,
    m.Compensation,
    m.CompensationPayment,
    m.RightsRelease,
    m.Handover,
    m.AffectedHousehold,
    m.AcquisitionDocument,
):
    admin.site.register(model)
