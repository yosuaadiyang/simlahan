from django import forms
from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _

from pengadaan import access, enums
from pengadaan import models as m
from pengadaan.status import settlement_blockers

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


class SettlementGuardAdminMixin:
    """Sama dengan API: bidang/proyek yang masih memiliki ganti kerugian,
    pembayaran, konsinyasi atau pelepasan hak tidak dapat dihapus (soft delete
    tidak meneruskan ke data tersebut)."""

    def _parcels_of(self, obj):
        raise NotImplementedError

    def _blockers(self, obj):
        return settlement_blockers(self._parcels_of(obj))

    def has_delete_permission(self, request, obj=None):
        if obj is not None and self._blockers(obj):
            return False
        return super().has_delete_permission(request, obj)

    def delete_queryset(self, request, queryset):
        blocked = [obj.pk for obj in queryset if self._blockers(obj)]
        if blocked:
            self.message_user(
                request,
                _("%d data tidak dihapus karena masih memiliki ganti kerugian.")
                % len(blocked),
                level=messages.WARNING,
            )
            queryset = queryset.exclude(pk__in=blocked)
        super().delete_queryset(request, queryset)


class PartyInlineFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        for form in self.forms:
            if (
                self.can_delete
                and self._should_delete_form(form)
                and form.instance.pk
                and settlement_blockers(parties=[form.instance.pk])
            ):
                raise forms.ValidationError(
                    _(
                        "Pihak %(name)s masih memiliki ganti kerugian; batalkan "
                        "atau hapus datanya lebih dahulu."
                    )
                    % {"name": form.instance.name}
                )


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
class AcquisitionProjectAdmin(SettlementGuardAdminMixin, ProjectScopedAdmin):
    list_display = ("identifier", "name", "acquisition_type", "stage", "status")
    list_filter = ("acquisition_type", "stage", "status", "priority")
    search_fields = ("identifier", "name", "requiring_agency")
    readonly_fields = ("identifier",)
    raw_id_fields = ("executing_chair", "created_by", "municipality")
    filter_horizontal = ("assigned_users",)
    inlines = [MilestoneInline]

    def _parcels_of(self, obj):
        return m.AcquisitionParcel.all_objects.filter(project=obj).values("pk")


class PartyInline(SensitiveFieldsAdminMixin, admin.StackedInline):
    model = m.EntitledParty
    formset = PartyInlineFormSet
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
class AcquisitionParcelAdmin(SettlementGuardAdminMixin, ProjectScopedAdmin):
    list_display = ("parcel_number", "project", "right_type", "status", "is_disputed")
    list_filter = ("status", "right_type", "is_disputed", "project")
    search_fields = ("parcel_number", "nib", "village", "certificate_number")
    readonly_fields = ("status",)
    raw_id_fields = ("project", "district")
    inlines = [PartyInline, InventoryItemInline]

    def _parcels_of(self, obj):
        return [obj.pk]


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

    def save_model(self, request, obj, form, change):
        # Sama seperti API: perubahan apa pun selain catatan setelah validasi
        # mengembalikan status ke DETERMINED agar divalidasi ulang oleh Ketua
        # Pelaksana. Tanpa ini admin bisa diam-diam mengubah nilai tervalidasi.
        if change and obj.status == enums.CompensationStatus.VALIDATED:
            if [f for f in form.changed_data if f != "note"]:
                obj.status = enums.CompensationStatus.DETERMINED
                obj.validated_on = None
                obj.validated_by = None
        super().save_model(request, obj, form, change)


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
    m.RightsRelease,
):
    admin.site.register(model, ProjectScopedAdmin)


class ImmutableParentAdmin(ProjectScopedAdmin):
    """Induk catatan tidak boleh dipindah setelah dibuat (sama dengan API):
    signal status hanya menghitung ulang induk yang baru, sehingga induk lama
    tertinggal berstatus lunas/dikonsinyasi tanpa catatan pendukung."""

    immutable_fields: tuple[str, ...] = ()

    def get_readonly_fields(self, request, obj=None):
        fields = tuple(super().get_readonly_fields(request, obj))
        if obj is not None:
            fields += tuple(f for f in self.immutable_fields if f not in fields)
        return fields


@admin.register(m.Consignment)
class ConsignmentAdmin(ImmutableParentAdmin):
    immutable_fields = ("parcel",)


@admin.register(m.CompensationPayment)
class CompensationPaymentAdmin(ImmutableParentAdmin):
    immutable_fields = ("compensation",)


class HandoverAdminForm(forms.ModelForm):
    """Pintu yang sama dengan API: hanya bidang yang sudah dilepas haknya.

    Pemeriksaan dipasang di form (bukan model) karena relasi banyak-ke-banyak
    belum tersambung ke instance saat ``full_clean`` dijalankan.
    """

    def clean(self):
        cleaned_data = super().clean()
        project = cleaned_data.get("project")
        for parcel in cleaned_data.get("parcels") or []:
            if project and parcel.project_id != project.id:
                raise forms.ValidationError(
                    _("All parcels must belong to the selected project.")
                )
            if not parcel.rights_releases.exists():
                raise forms.ValidationError(
                    _("Parcel %(parcel)s has no rights release yet.")
                    % {"parcel": parcel.parcel_number}
                )
        return cleaned_data


@admin.register(m.Handover)
class HandoverAdmin(ProjectScopedAdmin):
    form = HandoverAdminForm


@admin.register(m.AcquisitionDocument)
class AcquisitionDocumentAdmin(ProjectScopedAdmin):
    list_display = ("title", "document_type", "project", "parcel")
    list_filter = ("document_type",)
    search_fields = ("title", "number")
    raw_id_fields = ("project", "parcel", "party")

    def get_queryset(self, request):
        # Sama seperti API: data pribadi pihak dan jenis dokumen yang model
        # sumbernya tidak boleh dilihat disembunyikan.
        return access.visible_documents(super().get_queryset(request), request.user)
