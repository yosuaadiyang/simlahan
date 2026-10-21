from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.relations import ManyRelatedField, PrimaryKeyRelatedField
from rest_framework_gis.fields import GeometryField

from leasing.validators import (
    validate_business_id,
    validate_national_identification_number,
)
from pengadaan import enums
from pengadaan.access import (
    REQUESTING_AGENCY_DOCUMENT_TYPES,
    is_project_scoped,
    is_requesting_agency_only,
    project_lookup_for,
    scope_queryset,
)
from pengadaan.crypto import mask
from pengadaan.models import (
    AcquisitionDocument,
    AcquisitionMilestone,
    AcquisitionParcel,
    AcquisitionProject,
    AffectedHousehold,
    Announcement,
    Compensation,
    CompensationPayment,
    Consignment,
    DeadlineRule,
    Deliberation,
    DeliberationResult,
    EntitledParty,
    Handover,
    Holiday,
    InventoryItem,
    Objection,
    ParcelSurvey,
    RightsRelease,
    Valuation,
)
from pengadaan.status import is_parcel_settled
from utils.money import fits, too_large_message


def _request_user(serializer):
    request = serializer.context.get("request")
    return getattr(request, "user", None)


def _has_perm(serializer, perm: str) -> bool:
    user = _request_user(serializer)
    return bool(user and user.is_authenticated and user.has_perm(perm))


def _changed_fields(instance, attrs, fields=None) -> list[str]:
    """Nama bidang di ``attrs`` yang nilainya berbeda dari ``instance``."""
    if instance is None:
        return []
    names = attrs.keys() if fields is None else [f for f in fields if f in attrs]
    return [name for name in names if attrs[name] != getattr(instance, name)]


def _reject_changes(instance, attrs, fields, message):
    """Tolak perubahan bidang yang hanya boleh diisi saat data dibuat."""
    changed = _changed_fields(instance, attrs, fields)
    if changed:
        raise serializers.ValidationError({name: message for name in changed})


class PengadaanModelSerializer(serializers.ModelSerializer):
    """Dasar serializer pengadaan.

    Bagi peran eksternal yang dibatasi per proyek (pengadaan.access), pilihan
    relasi (proyek, bidang, pihak, dst.) dibatasi ke proyek yang ditugaskan,
    sehingga data proyek lain tidak dapat dirujuk.
    """

    def get_fields(self):
        fields = super().get_fields()
        user = _request_user(self)
        if user is None or not is_project_scoped(user):
            return fields
        for field in fields.values():
            relation = (
                field.child_relation if isinstance(field, ManyRelatedField) else field
            )
            if (
                isinstance(relation, PrimaryKeyRelatedField)
                and not relation.read_only
                and relation.queryset is not None
                and project_lookup_for(relation.queryset.model)
            ):
                relation.queryset = scope_queryset(relation.queryset, user)
        return fields


class NoticeMixin:
    """Sertakan pemberitahuan (``notice``) pada respons setelah penyimpanan."""

    notice = None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self.notice:
            data["notice"] = str(self.notice)
        return data


class UserNameField(serializers.Field):
    """Nama tampilan pengguna dari atribut FK (hanya-baca)."""

    def __init__(self, attr, **kwargs):
        kwargs["source"] = "*"
        kwargs["read_only"] = True
        super().__init__(**kwargs)
        self.attr = attr

    def to_representation(self, instance):
        user = getattr(instance, self.attr, None)
        return user.get_display_name() if user is not None else None


class HolidaySerializer(PengadaanModelSerializer):
    class Meta:
        model = Holiday
        fields = ("id", "date", "name", "is_collective_leave")


class DeadlineRuleSerializer(PengadaanModelSerializer):
    class Meta:
        model = DeadlineRule
        fields = ("id", "code", "name", "amount", "unit", "legal_basis", "description")
        read_only_fields = ("code",)


class AcquisitionMilestoneSerializer(PengadaanModelSerializer):
    responsible_name = UserNameField("responsible")

    class Meta:
        model = AcquisitionMilestone
        fields = (
            "id",
            "project",
            "stage",
            "code",
            "sequence",
            "title",
            "legal_basis",
            "planned_date",
            "actual_date",
            "status",
            "responsible",
            "responsible_name",
            "note",
        )

    # Tonggak yang menjadi tanggung jawab Satgas Pengadaan Tanah. Pengguna yang
    # boleh mengubah tetapi tidak boleh menambah tonggak (grup Satgas) hanya
    # dapat memperbarui status, tanggal realisasi dan catatan tonggak ini;
    # rencana, penanggung jawab dan tonggak lain dikelola Pelaksana.
    TASK_FORCE_CODES = frozenset(
        {
            "inventory",
            "inventory_announcement",
            "inventory_verification",
            "deliberation",
            "release",
        }
    )
    TASK_FORCE_FIELDS = frozenset({"status", "actual_date", "note"})

    def validate(self, attrs):
        instance = self.instance
        _reject_changes(
            instance,
            attrs,
            ("project", "stage", "code"),
            _("This cannot be changed after the milestone has been created."),
        )
        if instance is not None and not _has_perm(
            self, "pengadaan.add_acquisitionmilestone"
        ):
            if instance.code not in self.TASK_FORCE_CODES:
                raise PermissionDenied(
                    _("This milestone is managed by the implementing team.")
                )
            changed = [
                name
                for name in _changed_fields(instance, attrs)
                if name not in self.TASK_FORCE_FIELDS
            ]
            if changed:
                raise serializers.ValidationError(
                    {
                        name: _(
                            "Only the status, actual date and note of this "
                            "milestone can be changed."
                        )
                        for name in changed
                    }
                )
        return attrs


class AcquisitionProjectSerializer(PengadaanModelSerializer):
    executing_chair_name = UserNameField("executing_chair")
    municipality_name = serializers.CharField(
        source="municipality.name", read_only=True, default=None
    )
    location_decree_expires_on = serializers.DateField(read_only=True)
    ptun_filing_deadline = serializers.DateField(read_only=True)
    parcel_count = serializers.IntegerField(read_only=True, required=False)
    geometry = GeometryField(required=False, allow_null=True)
    assigned_users = serializers.PrimaryKeyRelatedField(
        many=True,
        required=False,
        queryset=get_user_model().objects.all(),
        label=_("Assigned users"),
        help_text=_(
            "Land appraisers and users of the agency requiring the land only see "
            "the projects they are assigned to."
        ),
    )

    class Meta:
        model = AcquisitionProject
        fields = (
            "id",
            "identifier",
            "name",
            "description",
            "acquisition_type",
            "purpose_category",
            "priority",
            "funding_source",
            "requiring_agency",
            "requiring_agency_contact",
            "executing_office",
            "executing_chair",
            "executing_chair_name",
            "service_unit",
            "municipality",
            "municipality_name",
            "location_description",
            "estimated_area_m2",
            "estimated_budget",
            "stage",
            "status",
            "planning_document_number",
            "planning_document_date",
            "notification_date",
            "public_consultation_date",
            "location_decree_number",
            "location_decree_date",
            "location_decree_extended",
            "location_decree_expires_on",
            "location_announcement_date",
            "ptun_filing_deadline",
            "start_date",
            "target_completion_date",
            "geometry",
            "parcel_count",
            "assigned_users",
            "created_at",
            "modified_at",
        )
        read_only_fields = ("identifier", "created_at", "modified_at")

    def get_fields(self):
        fields = super().get_fields()
        user = _request_user(self)
        # Peran eksternal tidak perlu tahu siapa saja yang ditugaskan.
        if user is not None and is_project_scoped(user):
            fields.pop("assigned_users", None)
        return fields

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        target = attrs.get(
            "target_completion_date",
            getattr(self.instance, "target_completion_date", None),
        )
        if start and target and target < start:
            raise serializers.ValidationError(
                {
                    "target_completion_date": _(
                        "Target completion date cannot be before the start date."
                    )
                }
            )
        if attrs.get("acquisition_type") == enums.AcquisitionType.SMALL_SCALE:
            area = attrs.get("estimated_area_m2")
            if area is not None and area > 50000:
                raise serializers.ValidationError(
                    {
                        "estimated_area_m2": _(
                            "Small scale acquisition is limited to 5 hectares (50,000 m²)."
                        )
                    }
                )
        return attrs


class AcquisitionParcelSerializer(PengadaanModelSerializer):
    district_name = serializers.CharField(
        source="district.name", read_only=True, default=None
    )
    project_identifier = serializers.CharField(
        source="project.identifier", read_only=True
    )
    remaining_area_m2 = serializers.DecimalField(
        max_digits=None, decimal_places=2, read_only=True
    )
    party_names = serializers.SerializerMethodField()
    geometry = GeometryField(required=False, allow_null=True)

    class Meta:
        model = AcquisitionParcel
        fields = (
            "id",
            "project",
            "project_identifier",
            "parcel_number",
            "nib",
            "district",
            "district_name",
            "village",
            "address",
            "right_type",
            "certificate_number",
            "measured_area_m2",
            "affected_area_m2",
            "remaining_area_m2",
            "land_use",
            "building_description",
            "building_area_m2",
            "plants_description",
            "other_objects_description",
            "status",
            "is_excluded",
            "is_disputed",
            "geometry",
            "party_names",
            "note",
            "created_at",
            "modified_at",
        )
        read_only_fields = ("status", "created_at", "modified_at")

    def get_fields(self):
        fields = super().get_fields()
        # Nama pihak hanya untuk peran yang boleh melihat pihak yang berhak.
        if not _has_perm(self, "pengadaan.view_entitledparty"):
            fields.pop("party_names", None)
        return fields

    def get_party_names(self, obj):
        return ", ".join(p.name for p in obj.parties.all())

    def validate(self, attrs):
        measured = attrs.get(
            "measured_area_m2", getattr(self.instance, "measured_area_m2", None)
        )
        affected = attrs.get(
            "affected_area_m2", getattr(self.instance, "affected_area_m2", None)
        )
        if measured is not None and affected is not None and affected > measured:
            raise serializers.ValidationError(
                {
                    "affected_area_m2": _(
                        "Affected area cannot exceed the measured area."
                    )
                }
            )
        district = attrs.get("district")
        project = attrs.get("project", getattr(self.instance, "project", None))
        if (
            district is not None
            and project is not None
            and project.municipality_id
            and district.municipality_id != project.municipality_id
        ):
            raise serializers.ValidationError(
                {"district": _("Sub-district must be in the project's regency/city.")}
            )
        parcel_number = attrs.get(
            "parcel_number", getattr(self.instance, "parcel_number", None)
        )
        if project is not None and parcel_number:
            duplicates = AcquisitionParcel.objects.filter(
                project=project, parcel_number=parcel_number
            )
            if self.instance is not None:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise serializers.ValidationError(
                    {
                        "parcel_number": _(
                            "This parcel number already exists in the project."
                        )
                    }
                )
        return attrs


def reset_validation(compensations) -> int:
    """Kembalikan ganti kerugian tervalidasi ke status ditetapkan.

    Disimpan satu per satu agar perubahan tercatat di log audit.
    """
    count = 0
    for compensation in compensations:
        compensation.status = enums.CompensationStatus.DETERMINED
        compensation.validated_on = None
        compensation.validated_by = None
        compensation.save(
            update_fields=["status", "validated_on", "validated_by", "modified_at"]
        )
        count += 1
    return count


class SensitiveDataMixin:
    """Menyamarkan NIK/rekening kecuali pengguna berhak melihat data pribadi."""

    sensitive_fields: tuple[str, ...] = ()

    def _can_view_sensitive(self) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and user.has_perm("pengadaan.view_sensitive_personal_data")
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self._can_view_sensitive():
            for field in self.sensitive_fields:
                if data.get(field):
                    data[field] = mask(data[field])
        return data


class EntitledPartySerializer(
    NoticeMixin, SensitiveDataMixin, PengadaanModelSerializer
):
    sensitive_fields = ("nik", "bank_account_number")
    BANK_FIELDS = ("bank_name", "bank_account_number", "bank_account_holder")
    parcel_number = serializers.CharField(source="parcel.parcel_number", read_only=True)
    project = serializers.IntegerField(source="parcel.project_id", read_only=True)

    class Meta:
        model = EntitledParty
        fields = (
            "id",
            "parcel",
            "parcel_number",
            "project",
            "party_type",
            "role",
            "name",
            "nik",
            "npwp",
            "address",
            "phone",
            "email",
            "share_percentage",
            "bank_name",
            "bank_account_number",
            "bank_account_holder",
            "contact",
            "note",
        )

    def validate_nik(self, value):
        if value and "*" in value and self.instance is not None:
            # Nilai tersamar dikirim balik oleh UI: pertahankan nilai lama.
            return self.instance.nik
        if value:
            validate_national_identification_number(value)
        return value

    def validate_bank_account_number(self, value):
        if value and "*" in value and self.instance is not None:
            return self.instance.bank_account_number
        if value and not value.replace("-", "").replace(" ", "").isdigit():
            raise serializers.ValidationError(_("Bank account number must be numeric."))
        return value

    def validate_npwp(self, value):
        if value:
            validate_business_id(value)
        return value

    def validate(self, attrs):
        parcel = attrs.get("parcel", getattr(self.instance, "parcel", None))
        share = attrs.get("share_percentage")
        if parcel is not None and share is not None:
            others = parcel.parties.exclude(pk=getattr(self.instance, "pk", None))
            total = sum((p.share_percentage or 0 for p in others), 0) + share
            if total > 100:
                raise serializers.ValidationError(
                    {
                        "share_percentage": _(
                            "Total shares of the parcel's parties exceed 100%."
                        )
                    }
                )
        return attrs

    def update(self, instance, validated_data):
        bank_changed = bool(_changed_fields(instance, validated_data, self.BANK_FIELDS))
        instance = super().update(instance, validated_data)
        if bank_changed:
            # Validasi Ketua Pelaksana mencakup rekening tujuan pembayaran:
            # rekening berubah berarti validasi harus diulang.
            count = reset_validation(
                instance.compensations.filter(status=enums.CompensationStatus.VALIDATED)
            )
            if count:
                self.notice = _(
                    "Bank details changed: %(count)d validated compensation(s) of "
                    "this party were returned to determined and must be validated "
                    "again by the executing chair."
                ) % {"count": count}
        return instance


class ParcelSurveySerializer(PengadaanModelSerializer):
    surveyor_name = UserNameField("surveyor")
    parcel_number = serializers.CharField(source="parcel.parcel_number", read_only=True)

    class Meta:
        model = ParcelSurvey
        fields = (
            "id",
            "parcel",
            "parcel_number",
            "survey_type",
            "status",
            "survey_date",
            "team_name",
            "surveyor",
            "surveyor_name",
            "latitude",
            "longitude",
            "findings",
        )


class InventoryItemSerializer(PengadaanModelSerializer):
    parcel_number = serializers.CharField(source="parcel.parcel_number", read_only=True)
    # Pemilik boleh kosong; field metode agar tetap ada juga pada respons PATCH.
    party_name = serializers.SerializerMethodField()
    total_value = serializers.DecimalField(
        max_digits=None, decimal_places=2, read_only=True
    )

    class Meta:
        model = InventoryItem
        fields = (
            "id",
            "parcel",
            "parcel_number",
            "party",
            "party_name",
            "item_type",
            "description",
            "quantity",
            "unit",
            "condition",
            "unit_value",
            "total_value",
            "note",
        )

    def get_party_name(self, obj) -> str | None:
        return obj.party.name if obj.party_id else None

    def validate(self, attrs):
        parcel = attrs.get("parcel") or getattr(self.instance, "parcel", None)
        party = attrs.get("party", getattr(self.instance, "party", None))
        if party is not None and parcel is not None and party.parcel_id != parcel.pk:
            raise serializers.ValidationError(
                {"party": _("The owner must be an entitled party of this parcel.")}
            )
        return attrs


class AnnouncementSerializer(PengadaanModelSerializer):
    period_ends_on = serializers.DateField(read_only=True)
    objection_deadline = serializers.DateField(read_only=True)

    class Meta:
        model = Announcement
        fields = (
            "id",
            "project",
            "announcement_type",
            "announced_on",
            "location",
            "document_number",
            "period_ends_on",
            "objection_deadline",
            "note",
        )


class ValuationSerializer(PengadaanModelSerializer):
    parcel_number = serializers.CharField(source="parcel.parcel_number", read_only=True)
    deliberation_deadline = serializers.DateField(read_only=True)

    class Meta:
        model = Valuation
        fields = (
            "id",
            "parcel",
            "parcel_number",
            "status",
            "appraiser_firm",
            "appraiser_name",
            "appraiser_license",
            "report_number",
            "valuation_date",
            "submitted_on",
            "value_land",
            "value_space",
            "value_building",
            "value_plants",
            "value_other_objects",
            "value_non_physical",
            "total_value",
            "deliberation_deadline",
            "note",
        )
        read_only_fields = ("total_value",)

    def _check_locked(self, attrs):
        """Penilaian final tidak dapat diubah; revisi dicatat sebagai penilaian baru.

        Satu-satunya perubahan yang diizinkan adalah menandai penilaian final
        sebagai direvisi (beserta catatannya) setelah penilaian pengganti dibuat.
        """
        instance = self.instance
        if instance is None or instance.status not in (
            enums.ValuationStatus.FINAL,
            enums.ValuationStatus.REVISED,
        ):
            return
        changed = set(_changed_fields(instance, attrs))
        marking_revised = (
            instance.status == enums.ValuationStatus.FINAL
            and attrs.get("status") == enums.ValuationStatus.REVISED
        )
        allowed = {"status", "note"} if marking_revised else set()
        if changed - allowed:
            raise serializers.ValidationError(
                _(
                    "A final valuation cannot be changed. Record a new valuation to "
                    "revise it."
                )
            )

    def validate(self, attrs):
        self._check_locked(attrs)
        for field in (
            "value_land",
            "value_space",
            "value_building",
            "value_plants",
            "value_other_objects",
            "value_non_physical",
        ):
            if attrs.get(field) is not None and attrs[field] < 0:
                raise serializers.ValidationError(
                    {field: _("Value cannot be negative.")}
                )
        values = {
            name: attrs.get(name, getattr(self.instance, name, None))
            for name in Valuation.VALUE_FIELDS
        }
        if not fits(Valuation, "total_value", Valuation.compute_total(values)):
            raise serializers.ValidationError(
                too_large_message(Valuation, "total_value")
            )
        return attrs


class DeliberationResultSerializer(PengadaanModelSerializer):
    parcel_number = serializers.CharField(source="parcel.parcel_number", read_only=True)
    party_name = serializers.CharField(
        source="party.name", read_only=True, default=None
    )
    objection_deadline = serializers.DateField(read_only=True)
    held_on = serializers.DateField(source="deliberation.held_on", read_only=True)

    class Meta:
        model = DeliberationResult
        fields = (
            "id",
            "deliberation",
            "held_on",
            "parcel",
            "parcel_number",
            "party",
            "party_name",
            "outcome",
            "compensation_form",
            "agreed_amount",
            "signed_on",
            "objection_deadline",
            "note",
        )

    def validate(self, attrs):
        deliberation = attrs.get(
            "deliberation", getattr(self.instance, "deliberation", None)
        )
        parcel = attrs.get("parcel", getattr(self.instance, "parcel", None))
        party = attrs.get("party", getattr(self.instance, "party", None))
        if deliberation and parcel and deliberation.project_id != parcel.project_id:
            raise serializers.ValidationError(
                {"parcel": _("Parcel does not belong to the deliberation's project.")}
            )
        if party and parcel and party.parcel_id != parcel.id:
            raise serializers.ValidationError(
                {"party": _("Party does not belong to the selected parcel.")}
            )
        return attrs


class DeliberationSerializer(PengadaanModelSerializer):
    chaired_by_name = UserNameField("chaired_by")
    result_count = serializers.SerializerMethodField()

    class Meta:
        model = Deliberation
        fields = (
            "id",
            "project",
            "held_on",
            "location",
            "minutes_number",
            "chaired_by",
            "chaired_by_name",
            "result_count",
            "note",
        )

    def get_result_count(self, obj):
        return obj.results.count()


class ObjectionSerializer(PengadaanModelSerializer):
    parcel_number = serializers.CharField(
        source="parcel.parcel_number", read_only=True, default=None
    )
    party_name = serializers.CharField(
        source="party.name", read_only=True, default=None
    )
    decision_deadline = serializers.DateField(read_only=True)
    appeal_deadline = serializers.DateField(read_only=True)

    class Meta:
        model = Objection
        fields = (
            "id",
            "project",
            "parcel",
            "parcel_number",
            "party",
            "party_name",
            "parent",
            "objection_type",
            "status",
            "filed_by_name",
            "court_name",
            "case_number",
            "filed_on",
            "received_on",
            "decision_deadline",
            "decided_on",
            "decision_summary",
            "decided_amount",
            "appeal_deadline",
            "note",
        )

    def validate(self, attrs):
        project = attrs.get("project", getattr(self.instance, "project", None))
        parcel = attrs.get("parcel", getattr(self.instance, "parcel", None))
        if project and parcel and parcel.project_id != project.id:
            raise serializers.ValidationError(
                {"parcel": _("Parcel does not belong to the selected project.")}
            )
        filed = attrs.get("filed_on", getattr(self.instance, "filed_on", None))
        decided = attrs.get("decided_on", getattr(self.instance, "decided_on", None))
        if filed and decided and decided < filed:
            raise serializers.ValidationError(
                {"decided_on": _("Decision date cannot be before the filing date.")}
            )
        return attrs


class ConsignmentSerializer(PengadaanModelSerializer):
    parcel_number = serializers.CharField(source="parcel.parcel_number", read_only=True)
    party_name = serializers.CharField(
        source="party.name", read_only=True, default=None
    )
    acceptance_deadline = serializers.DateField(read_only=True)

    class Meta:
        model = Consignment
        fields = (
            "id",
            "parcel",
            "parcel_number",
            "party",
            "party_name",
            "reason",
            "status",
            "court_name",
            "application_date",
            "acceptance_deadline",
            "decree_number",
            "decree_date",
            "deposited_on",
            "amount",
            "collected_on",
            "note",
        )

    def validate(self, attrs):
        parcel = attrs.get("parcel", getattr(self.instance, "parcel", None))
        party = attrs.get("party", getattr(self.instance, "party", None))
        if party and parcel and party.parcel_id != parcel.id:
            raise serializers.ValidationError(
                {"party": _("Party does not belong to the selected parcel.")}
            )
        return attrs


class CompensationPaymentSerializer(PengadaanModelSerializer):
    class Meta:
        model = CompensationPayment
        fields = (
            "id",
            "compensation",
            "paid_on",
            "amount",
            "method",
            "bank_reference",
            "recipient_name",
            "note",
        )

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(_("Amount must be greater than zero."))
        return value

    def validate(self, attrs):
        compensation = attrs.get(
            "compensation", getattr(self.instance, "compensation", None)
        )
        amount = attrs.get("amount", getattr(self.instance, "amount", None))
        if compensation and amount is not None:
            if compensation.status not in (
                enums.CompensationStatus.VALIDATED,
                enums.CompensationStatus.PAID,
            ):
                raise serializers.ValidationError(
                    _("Compensation must be validated before it can be paid.")
                )
            already = sum(
                (
                    p.amount
                    for p in compensation.payments.exclude(
                        pk=getattr(self.instance, "pk", None)
                    )
                ),
                0,
            )
            if already + amount > compensation.amount:
                raise serializers.ValidationError(
                    {"amount": _("Payments exceed the compensation amount.")}
                )
        return attrs


class CompensationSerializer(NoticeMixin, PengadaanModelSerializer):
    parcel_number = serializers.CharField(source="parcel.parcel_number", read_only=True)
    party_name = serializers.CharField(
        source="party.name", read_only=True, default=None
    )
    validated_by_name = UserNameField("validated_by")
    paid_amount = serializers.DecimalField(
        max_digits=None, decimal_places=2, read_only=True
    )
    outstanding_amount = serializers.DecimalField(
        max_digits=None, decimal_places=2, read_only=True
    )
    payments = CompensationPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Compensation
        fields = (
            "id",
            "parcel",
            "parcel_number",
            "party",
            "party_name",
            "form",
            "amount",
            "description",
            "status",
            "valuation",
            "deliberation_result",
            "court_decision",
            "validated_on",
            "validated_by",
            "validated_by_name",
            "paid_amount",
            "outstanding_amount",
            "payments",
            "note",
        )
        # Status hanya berubah lewat aksi (validate, cancel, deliver) serta
        # pencatatan pembayaran/konsinyasi; ganti kerugian baru selalu
        # berstatus "ditetapkan".
        read_only_fields = ("status", "validated_on", "validated_by")

    LOCKED_STATUSES = (
        enums.CompensationStatus.PAID,
        enums.CompensationStatus.CONSIGNED,
        enums.CompensationStatus.CANCELLED,
    )

    def validate(self, attrs):  # noqa: C901
        instance = self.instance
        if instance is not None and instance.status in self.LOCKED_STATUSES:
            if [f for f in _changed_fields(instance, attrs) if f != "note"]:
                raise serializers.ValidationError(
                    _(
                        "Paid, consigned or cancelled compensation cannot be "
                        "changed; only the note can be edited."
                    )
                )
        parcel = attrs.get("parcel", getattr(instance, "parcel", None))
        party = attrs.get("party", getattr(instance, "party", None))
        if party and parcel and party.parcel_id != parcel.id:
            raise serializers.ValidationError(
                {"party": _("Party does not belong to the selected parcel.")}
            )
        valuation = attrs.get("valuation", getattr(instance, "valuation", None))
        if valuation and parcel and valuation.parcel_id != parcel.id:
            raise serializers.ValidationError(
                {"valuation": _("Valuation does not belong to the selected parcel.")}
            )
        result = attrs.get(
            "deliberation_result", getattr(instance, "deliberation_result", None)
        )
        if result and parcel and result.parcel_id != parcel.id:
            raise serializers.ValidationError(
                {
                    "deliberation_result": _(
                        "Deliberation result does not belong to the selected parcel."
                    )
                }
            )
        decision = attrs.get(
            "court_decision", getattr(instance, "court_decision", None)
        )
        if (
            decision
            and parcel
            and (
                decision.project_id != parcel.project_id
                or (decision.parcel_id and decision.parcel_id != parcel.id)
            )
        ):
            raise serializers.ValidationError(
                {
                    "court_decision": _(
                        "Court decision does not concern the selected parcel."
                    )
                }
            )
        amount = attrs.get("amount", getattr(instance, "amount", None))
        form = attrs.get("form", getattr(instance, "form", None))
        if form == enums.CompensationForm.MONEY and (amount is None or amount <= 0):
            raise serializers.ValidationError(
                {"amount": _("Monetary compensation must be greater than zero.")}
            )
        if instance is not None and amount is not None:
            if amount < instance.paid_amount:
                raise serializers.ValidationError(
                    {"amount": _("Amount cannot be less than what has been paid.")}
                )
        return attrs

    def update(self, instance, validated_data):
        if instance.status == enums.CompensationStatus.VALIDATED and [
            f for f in _changed_fields(instance, validated_data) if f != "note"
        ]:
            # Validasi berlaku untuk nilai, pihak dan bentuk yang divalidasi:
            # setiap perubahan mengharuskan validasi ulang oleh Ketua Pelaksana.
            validated_data.update(
                status=enums.CompensationStatus.DETERMINED,
                validated_on=None,
                validated_by=None,
            )
            self.notice = _(
                "The compensation was changed after validation and was returned "
                "to determined; it must be validated again by the executing chair."
            )
        return super().update(instance, validated_data)


class RightsReleaseSerializer(PengadaanModelSerializer):
    parcel_number = serializers.CharField(source="parcel.parcel_number", read_only=True)
    party_name = serializers.CharField(
        source="party.name", read_only=True, default=None
    )
    handover_deadline = serializers.DateField(read_only=True)

    class Meta:
        model = RightsRelease
        fields = (
            "id",
            "parcel",
            "parcel_number",
            "party",
            "party_name",
            "minutes_number",
            "released_on",
            "certificate_surrendered",
            "handover_deadline",
            "note",
        )

    def validate(self, attrs):
        # Bidang tidak dapat dipindah: syarat pelunasan diperiksa untuk bidang
        # saat pelepasan hak dicatat.
        _reject_changes(
            self.instance,
            attrs,
            ("parcel",),
            _("The parcel of a rights release cannot be changed."),
        )
        parcel = attrs.get("parcel", getattr(self.instance, "parcel", None))
        party = attrs.get("party", getattr(self.instance, "party", None))
        if party and parcel and party.parcel_id != parcel.id:
            raise serializers.ValidationError(
                {"party": _("Party does not belong to the selected parcel.")}
            )
        if parcel is not None and self.instance is None:
            if not is_parcel_settled(parcel):
                raise serializers.ValidationError(
                    _(
                        "Rights can only be released after all compensation of the "
                        "parcel has been paid or consigned to the court."
                    )
                )
        return attrs


class HandoverSerializer(PengadaanModelSerializer):
    registration_deadline = serializers.DateField(read_only=True)

    class Meta:
        model = Handover
        fields = (
            "id",
            "project",
            "minutes_number",
            "handed_over_on",
            "recipient",
            "parcels",
            "registration_applied_on",
            "registration_deadline",
            "registration_number",
            "note",
        )

    def validate(self, attrs):
        project = attrs.get("project", getattr(self.instance, "project", None))
        for parcel in attrs.get("parcels", []):
            if project and parcel.project_id != project.id:
                raise serializers.ValidationError(
                    {"parcels": _("All parcels must belong to the selected project.")}
                )
            if not parcel.rights_releases.exists():
                raise serializers.ValidationError(
                    {
                        "parcels": _("Parcel %(parcel)s has no rights release yet.")
                        % {"parcel": parcel.parcel_number}
                    }
                )
        return attrs


class AffectedHouseholdSerializer(SensitiveDataMixin, PengadaanModelSerializer):
    sensitive_fields = ("nik", "family_card_number")
    parcel_number = serializers.CharField(
        source="parcel.parcel_number", read_only=True, default=None
    )

    class Meta:
        model = AffectedHousehold
        fields = (
            "id",
            "project",
            "parcel",
            "parcel_number",
            "head_name",
            "nik",
            "family_card_number",
            "member_count",
            "displacement",
            "stage",
            "assistance_description",
            "monetary_assistance_amount",
            "progress_percentage",
            "note",
        )

    def validate_nik(self, value):
        if value and "*" in value and self.instance is not None:
            return self.instance.nik
        if value:
            validate_national_identification_number(value)
        return value

    def validate_family_card_number(self, value):
        if value and "*" in value and self.instance is not None:
            return self.instance.family_card_number
        if value and (not value.isdigit() or len(value) != 16):
            raise serializers.ValidationError(
                _("Family card number must be 16 digits.")
            )
        return value


class AcquisitionDocumentSerializer(PengadaanModelSerializer):
    uploaded_by_name = UserNameField("uploaded_by")
    file_name = serializers.SerializerMethodField()

    class Meta:
        model = AcquisitionDocument
        fields = (
            "id",
            "project",
            "parcel",
            "party",
            "document_type",
            "title",
            "number",
            "document_date",
            "file",
            "file_name",
            "uploaded_by",
            "uploaded_by_name",
            "note",
            "created_at",
        )
        read_only_fields = ("uploaded_by", "created_at")
        extra_kwargs = {"file": {"write_only": True}}

    def get_file_name(self, obj):
        return obj.file.name.rsplit("/", 1)[-1] if obj.file else None

    def validate(self, attrs):
        instance = self.instance
        project = attrs.get("project", getattr(instance, "project", None))
        parcel = attrs.get("parcel", getattr(instance, "parcel", None))
        party = attrs.get("party", getattr(instance, "party", None))
        if parcel and project and parcel.project_id != project.id:
            raise serializers.ValidationError(
                {"parcel": _("Parcel does not belong to the selected project.")}
            )
        if party and parcel and party.parcel_id != parcel.id:
            raise serializers.ValidationError(
                {"party": _("Party does not belong to the selected parcel.")}
            )
        if party and project and party.parcel.project_id != project.id:
            raise serializers.ValidationError(
                {"party": _("Party does not belong to the selected project.")}
            )
        user = _request_user(self)
        if user is not None and is_requesting_agency_only(user):
            # Instansi pemohon hanya mengunggah dokumen dari pihaknya sendiri
            # (lihat REQUESTING_AGENCY_DOCUMENT_TYPES), tanpa data pribadi pihak.
            document_type = attrs.get(
                "document_type", getattr(instance, "document_type", None)
            )
            if document_type not in REQUESTING_AGENCY_DOCUMENT_TYPES:
                raise serializers.ValidationError(
                    {
                        "document_type": _(
                            "Your role cannot upload this type of document."
                        )
                    }
                )
            if party is not None:
                raise serializers.ValidationError(
                    {"party": _("Your role cannot attach documents to a party.")}
                )
        return attrs

    def validate_file(self, value):
        from file_operations.viewsets.mixins import MAX_FILE_SIZE_BYTES

        allowed = {
            "pdf",
            "jpg",
            "jpeg",
            "png",
            "tif",
            "tiff",
            "doc",
            "docx",
            "xls",
            "xlsx",
            "odt",
            "ods",
            "csv",
            "txt",
            "zip",
            "geojson",
            "json",
            "kml",
            "kmz",
            "dxf",
            "dwg",
            "shp",
        }
        extension = value.name.rsplit(".", 1)[-1].lower() if "." in value.name else ""
        if extension not in allowed:
            raise serializers.ValidationError(_("File type is not allowed."))
        if value.size > MAX_FILE_SIZE_BYTES:
            raise serializers.ValidationError(_("File is too large."))
        return value
