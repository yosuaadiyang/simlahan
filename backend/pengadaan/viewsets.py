import datetime
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, parsers, serializers, status
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from file_operations.viewsets.mixins import FileDownloadMixin
from leasing.permissions import MvjDjangoModelPermissions
from leasing.viewsets.utils import AtomicTransactionModelViewSet
from pengadaan import enums
from pengadaan.access import (
    SENSITIVE_DOCUMENT_TYPES,
    is_project_scoped,
    scope_queryset,
    visible_projects,
)
from pengadaan.deadlines import collect_deadlines
from pengadaan.exports import nominative_list_xlsx
from pengadaan.importers import ImportError_, import_parcels
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
from pengadaan.serializers import (
    AcquisitionDocumentSerializer,
    AcquisitionMilestoneSerializer,
    AcquisitionParcelSerializer,
    AcquisitionProjectSerializer,
    AffectedHouseholdSerializer,
    AnnouncementSerializer,
    CompensationPaymentSerializer,
    CompensationSerializer,
    ConsignmentSerializer,
    DeadlineRuleSerializer,
    DeliberationResultSerializer,
    DeliberationSerializer,
    EntitledPartySerializer,
    HandoverSerializer,
    HolidaySerializer,
    InventoryItemSerializer,
    ObjectionSerializer,
    ParcelSurveySerializer,
    RightsReleaseSerializer,
    ValuationSerializer,
)
from pengadaan.workdays import add_workdays, workdays_between


class BaseViewSet(AtomicTransactionModelViewSet):
    permission_classes = (IsAuthenticated, MvjDjangoModelPermissions)
    filter_backends = (
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    )
    ordering_fields = "__all__"
    # Jalur ke proyek untuk membatasi data peran eksternal (pengadaan.access);
    # None = data umum (kalender, aturan tenggat).
    project_scope_lookup: str | None = None

    def get_queryset(self):
        qs = super().get_queryset()
        if self.project_scope_lookup:
            qs = scope_queryset(qs, self.request.user, self.project_scope_lookup)
        return qs


class ProjectScopedViewSet(BaseViewSet):
    """Viewset yang dapat difilter ?project=<id> (langsung atau via bidang)."""

    project_lookup = "project"

    @property
    def project_scope_lookup(self):
        return self.project_lookup

    def get_queryset(self):
        qs = super().get_queryset()
        project = self.request.query_params.get("project")
        if project and project.isdigit():
            qs = qs.filter(**{f"{self.project_lookup}_id": int(project)})
        return qs


class HolidayViewSet(BaseViewSet):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    filterset_fields = {
        "is_collective_leave": ["exact"],
        "date": ["exact", "year", "gte", "lte"],
    }
    search_fields = ("name",)


class DeadlineRuleViewSet(BaseViewSet):
    queryset = DeadlineRule.objects.all()
    serializer_class = DeadlineRuleSerializer
    http_method_names = ["get", "put", "patch", "head", "options"]
    search_fields = ("name", "code", "legal_basis")


class AcquisitionProjectViewSet(BaseViewSet):
    queryset = AcquisitionProject.objects.select_related(
        "executing_chair", "municipality"
    ).annotate(parcel_count=Count("parcels", filter=Q(parcels__deleted__isnull=True)))
    serializer_class = AcquisitionProjectSerializer
    project_scope_lookup = "pk"
    filterset_fields = (
        "stage",
        "status",
        "acquisition_type",
        "purpose_category",
        "priority",
        "municipality",
        "service_unit",
    )
    search_fields = ("identifier", "name", "requiring_agency", "location_description")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(methods=["get"], detail=True)
    def summary(self, request, pk=None):
        project = self.get_object()
        user = request.user
        parcels = AcquisitionParcel.objects.filter(project=project)
        by_status = dict(
            parcels.values_list("status")
            .annotate(n=Count("id"))
            .values_list("status", "n")
        )
        areas = parcels.exclude(is_excluded=True).aggregate(
            measured=Sum("measured_area_m2"), affected=Sum("affected_area_m2")
        )
        released_area = parcels.filter(
            status__in=[enums.ParcelStatus.RELEASED, enums.ParcelStatus.HANDED_OVER]
        ).aggregate(a=Sum("affected_area_m2"))["a"]
        milestones = project.milestones.all()
        data = {
            "parcel_count": parcels.count(),
            "parcels_by_status": by_status,
            "measured_area_m2": areas["measured"] or Decimal("0"),
            "affected_area_m2": areas["affected"] or Decimal("0"),
            "released_area_m2": released_area or Decimal("0"),
            "milestones_done": milestones.filter(
                status__in=[
                    enums.MilestoneStatus.DONE,
                    enums.MilestoneStatus.SKIPPED,
                ]
            ).count(),
            "milestones_total": milestones.count(),
            "deadlines": [
                d.as_dict()
                for d in collect_deadlines(
                    AcquisitionProject.objects.filter(pk=project.pk)
                )
            ],
        }
        # Angka pihak, nilai uang, keberatan dan rumah tangga hanya untuk peran
        # yang berhak melihat data sumbernya.
        if user.has_perm("pengadaan.view_entitledparty"):
            data["party_count"] = EntitledParty.objects.filter(
                parcel__project=project
            ).count()
        if user.has_perm("pengadaan.view_valuation"):
            data["valuation_total"] = Valuation.objects.filter(
                parcel__project=project, status=enums.ValuationStatus.FINAL
            ).aggregate(t=Sum("total_value"))["t"] or Decimal("0")
        if user.has_perm("pengadaan.view_compensation"):
            compensations = Compensation.objects.filter(
                parcel__project=project
            ).exclude(status=enums.CompensationStatus.CANCELLED)
            data["compensation_total"] = compensations.aggregate(t=Sum("amount"))[
                "t"
            ] or Decimal("0")
            data["paid_total"] = CompensationPayment.objects.filter(
                compensation__in=compensations
            ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        if user.has_perm("pengadaan.view_consignment"):
            data["consigned_total"] = Consignment.objects.filter(
                parcel__project=project,
                status__in=[
                    enums.ConsignmentStatus.DEPOSITED,
                    enums.ConsignmentStatus.COLLECTED,
                ],
            ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        if user.has_perm("pengadaan.view_objection"):
            data["open_objections"] = Objection.objects.filter(
                project=project,
                status__in=[
                    enums.ObjectionStatus.FILED,
                    enums.ObjectionStatus.IN_PROCESS,
                ],
            ).count()
        if user.has_perm("pengadaan.view_affectedhousehold"):
            data["households"] = project.households.count()
        return Response(data)

    @action(methods=["get"], detail=True)
    def geojson(self, request, pk=None):
        project = self.get_object()
        show_parties = request.user.has_perm("pengadaan.view_entitledparty")
        features = []
        if project.geometry:
            features.append(
                {
                    "type": "Feature",
                    "geometry": _geojson(project.geometry),
                    "properties": {"kind": "project", "name": project.name},
                }
            )
        parcels = AcquisitionParcel.objects.filter(
            project=project, geometry__isnull=False
        )
        if show_parties:
            parcels = parcels.prefetch_related("parties")
        for parcel in parcels:
            properties = {
                "kind": "parcel",
                "id": parcel.id,
                "parcel_number": parcel.parcel_number,
                "status": parcel.status,
                "status_display": str(parcel.get_status_display()),
                "right_type": str(parcel.get_right_type_display()),
                "affected_area_m2": (
                    str(parcel.affected_area_m2)
                    if parcel.affected_area_m2 is not None
                    else None
                ),
                "is_disputed": parcel.is_disputed,
            }
            if show_parties:
                properties["parties"] = ", ".join(p.name for p in parcel.parties.all())
            features.append(
                {
                    "type": "Feature",
                    "id": parcel.id,
                    "geometry": _geojson(parcel.geometry),
                    "properties": properties,
                }
            )
        return Response({"type": "FeatureCollection", "features": features})

    @action(methods=["get"], detail=True)
    def nominative_list(self, request, pk=None):
        project = self.get_object()
        # Daftar nominatif memuat nama pihak serta nilai penilaian dan ganti
        # kerugian: wajib berhak melihat ketiganya.
        if not all(
            request.user.has_perm(f"pengadaan.view_{model}")
            for model in ("entitledparty", "valuation", "compensation")
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)
        content = nominative_list_xlsx(project)
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="daftar-nominatif-{project.identifier}.xlsx"'
        )
        return response

    @action(
        methods=["post"],
        detail=True,
        parser_classes=(parsers.MultiPartParser, parsers.FormParser),
    )
    def import_parcels(self, request, pk=None):
        project = self.get_object()
        if not request.user.has_perm("pengadaan.add_acquisitionparcel"):
            return Response(status=status.HTTP_403_FORBIDDEN)
        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"file": [_("A file is required.")]}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            result = import_parcels(
                project,
                upload,
                number_field=request.data.get("number_field") or "parcel_number",
                area_field=request.data.get("area_field") or None,
                update_existing=str(request.data.get("update_existing", "true")).lower()
                in ("1", "true", "yes"),
            )
        except ImportError_ as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result.as_dict())


def _geojson(geometry):
    import json

    return json.loads(geometry.geojson)


class AcquisitionMilestoneViewSet(ProjectScopedViewSet):
    queryset = AcquisitionMilestone.objects.select_related("responsible")
    serializer_class = AcquisitionMilestoneSerializer
    filterset_fields = ("project", "stage", "status")
    search_fields = ("title", "note")


class AcquisitionParcelViewSet(ProjectScopedViewSet):
    queryset = AcquisitionParcel.objects.select_related(
        "project", "district"
    ).prefetch_related("parties")
    serializer_class = AcquisitionParcelSerializer
    filterset_fields = (
        "project",
        "status",
        "right_type",
        "land_use",
        "district",
        "is_disputed",
        "is_excluded",
    )
    base_search_fields = (
        "parcel_number",
        "nib",
        "village",
        "address",
        "certificate_number",
    )

    @property
    def search_fields(self):
        # Pencarian nama pihak hanya untuk yang boleh melihat pihak yang berhak.
        request = getattr(self, "request", None)
        if request is not None and request.user.has_perm(
            "pengadaan.view_entitledparty"
        ):
            return self.base_search_fields + ("parties__name",)
        return self.base_search_fields


class ParcelChildViewSet(ProjectScopedViewSet):
    project_lookup = "parcel__project"


class EntitledPartyViewSet(ParcelChildViewSet):
    queryset = EntitledParty.objects.select_related("parcel")
    serializer_class = EntitledPartySerializer
    filterset_fields = ("parcel", "party_type", "role")
    search_fields = ("name", "npwp", "address", "parcel__parcel_number")

    def get_queryset(self):
        qs = super().get_queryset()
        nik = self.request.query_params.get("nik")
        # Pencarian NIK persis hanya untuk yang berhak melihat NIK; selain itu
        # parameter diabaikan agar NIK tersamar tidak dapat ditebak.
        if nik and self.request.user.has_perm("pengadaan.view_sensitive_personal_data"):
            from pengadaan.crypto import fingerprint

            qs = qs.filter(nik_fingerprint=fingerprint(nik))
        return qs


class ParcelSurveyViewSet(ParcelChildViewSet):
    queryset = ParcelSurvey.objects.select_related("parcel", "surveyor")
    serializer_class = ParcelSurveySerializer
    filterset_fields = ("parcel", "survey_type", "status")


class InventoryItemViewSet(ParcelChildViewSet):
    queryset = InventoryItem.objects.select_related("parcel", "party")
    serializer_class = InventoryItemSerializer
    filterset_fields = ("parcel", "party", "item_type")
    search_fields = ("description", "parcel__parcel_number")


class AnnouncementViewSet(ProjectScopedViewSet):
    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer
    filterset_fields = ("project", "announcement_type")


class ValuationViewSet(ParcelChildViewSet):
    queryset = Valuation.objects.select_related("parcel")
    serializer_class = ValuationSerializer
    filterset_fields = ("parcel", "status")
    search_fields = ("report_number", "appraiser_firm", "parcel__parcel_number")


class DeliberationViewSet(ProjectScopedViewSet):
    queryset = Deliberation.objects.select_related("chaired_by")
    serializer_class = DeliberationSerializer
    filterset_fields = ("project",)


class DeliberationResultViewSet(ParcelChildViewSet):
    queryset = DeliberationResult.objects.select_related(
        "deliberation", "parcel", "party"
    )
    serializer_class = DeliberationResultSerializer
    filterset_fields = ("deliberation", "parcel", "outcome")


class ObjectionViewSet(ProjectScopedViewSet):
    queryset = Objection.objects.select_related("parcel", "party")
    serializer_class = ObjectionSerializer
    filterset_fields = ("project", "parcel", "objection_type", "status")
    search_fields = ("case_number", "court_name", "filed_by_name")


class ConsignmentViewSet(ParcelChildViewSet):
    queryset = Consignment.objects.select_related("parcel", "party")
    serializer_class = ConsignmentSerializer
    filterset_fields = ("parcel", "status", "reason")


class CanValidateCompensation(BasePermission):
    """Hanya Ketua Pelaksana (izin ``validate_compensation``) yang boleh memvalidasi."""

    def has_permission(self, request, view):
        return request.user.has_perm("pengadaan.validate_compensation")


class CanRecordPayment(BasePermission):
    """Peran yang boleh mencatat pembayaran ganti kerugian."""

    def has_permission(self, request, view):
        return request.user.has_perm("pengadaan.add_compensationpayment")


class CompensationViewSet(ParcelChildViewSet):
    queryset = Compensation.objects.select_related(
        "parcel", "party", "validated_by"
    ).prefetch_related("payments")
    serializer_class = CompensationSerializer
    filterset_fields = ("parcel", "party", "status", "form")

    @action(
        methods=["post"],
        detail=True,
        permission_classes=(IsAuthenticated, CanValidateCompensation),
    )
    def validate(self, request, pk=None):
        """Validasi oleh Ketua Pelaksana sebelum ganti kerugian dibayarkan."""
        compensation = self.get_object()
        if compensation.status not in (enums.CompensationStatus.DETERMINED,):
            raise serializers.ValidationError(
                _("Only determined compensation can be validated.")
            )
        if (
            compensation.form == enums.CompensationForm.MONEY
            and compensation.party is not None
            and not compensation.party.bank_account_number
        ):
            raise serializers.ValidationError(
                _("The entitled party has no bank account number.")
            )
        compensation.status = enums.CompensationStatus.VALIDATED
        compensation.validated_on = timezone.localdate()
        compensation.validated_by = request.user
        compensation.save()
        return Response(self.get_serializer(compensation).data)

    @action(
        methods=["post"],
        detail=True,
        permission_classes=(IsAuthenticated, CanValidateCompensation),
    )
    def cancel(self, request, pk=None):
        """Batalkan ganti kerugian yang belum dibayar (wewenang Ketua Pelaksana)."""
        compensation = self.get_object()
        if compensation.status not in (
            enums.CompensationStatus.DETERMINED,
            enums.CompensationStatus.VALIDATED,
        ):
            raise serializers.ValidationError(
                _("Only determined or validated compensation can be cancelled.")
            )
        if compensation.payments.exists():
            raise serializers.ValidationError(
                _("Compensation that already has payments cannot be cancelled.")
            )
        compensation.status = enums.CompensationStatus.CANCELLED
        compensation.save()
        return Response(self.get_serializer(compensation).data)

    @action(
        methods=["post"],
        detail=True,
        permission_classes=(IsAuthenticated, CanRecordPayment),
    )
    def deliver(self, request, pk=None):
        """Catat penyerahan ganti kerugian bukan uang (tanah pengganti, dsb.).

        Setara dengan pembayaran untuk bentuk uang: hanya setelah divalidasi
        Ketua Pelaksana dan oleh peran yang boleh mencatat pembayaran.
        """
        compensation = self.get_object()
        if compensation.form == enums.CompensationForm.MONEY:
            raise serializers.ValidationError(
                _("Monetary compensation is settled by recording payments.")
            )
        if compensation.status != enums.CompensationStatus.VALIDATED:
            raise serializers.ValidationError(
                _("Compensation must be validated before it can be paid.")
            )
        compensation.status = enums.CompensationStatus.PAID
        compensation.save()
        return Response(self.get_serializer(compensation).data)


class CompensationPaymentViewSet(BaseViewSet):
    queryset = CompensationPayment.objects.select_related("compensation")
    serializer_class = CompensationPaymentSerializer
    filterset_fields = ("compensation",)
    project_scope_lookup = "compensation__parcel__project"

    def get_queryset(self):
        qs = super().get_queryset()
        project = self.request.query_params.get("project")
        if project and project.isdigit():
            qs = qs.filter(compensation__parcel__project_id=int(project))
        return qs


class RightsReleaseViewSet(ParcelChildViewSet):
    queryset = RightsRelease.objects.select_related("parcel", "party")
    serializer_class = RightsReleaseSerializer
    filterset_fields = ("parcel",)


class HandoverViewSet(ProjectScopedViewSet):
    queryset = Handover.objects.prefetch_related("parcels")
    serializer_class = HandoverSerializer
    filterset_fields = ("project",)


class AffectedHouseholdViewSet(ProjectScopedViewSet):
    queryset = AffectedHousehold.objects.select_related("parcel")
    serializer_class = AffectedHouseholdSerializer
    filterset_fields = ("project", "parcel", "displacement", "stage")
    search_fields = ("head_name",)


class AcquisitionDocumentViewSet(FileDownloadMixin, ProjectScopedViewSet):
    queryset = AcquisitionDocument.objects.select_related("uploaded_by")
    serializer_class = AcquisitionDocumentSerializer
    parser_classes = (parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser)
    filterset_fields = ("project", "parcel", "party", "document_type")
    search_fields = ("title", "number", "note")

    def get_queryset(self):
        qs = super().get_queryset()
        # Pindaian KTP, sertipikat, bukti bayar dan semua dokumen milik pihak
        # tertentu adalah data pribadi: daftar, detail dan unduhan disembunyikan
        # dari yang tidak berhak melihat data pribadi.
        if not self.request.user.has_perm("pengadaan.view_sensitive_personal_data"):
            qs = qs.exclude(document_type__in=SENSITIVE_DOCUMENT_TYPES).filter(
                party__isnull=True
            )
        return qs

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    @action(methods=["get"], detail=True)
    def download(self, request, pk=None):
        return super().download(request, pk, file_field="file")


class DeadlinesView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_view_name(self):
        return _("Land acquisition deadlines")

    def get(self, request, format=None):
        if not request.user.has_perm("pengadaan.view_acquisitionproject"):
            return Response(status=status.HTTP_403_FORBIDDEN)
        projects = visible_projects(request.user).exclude(
            status__in=[enums.ProjectStatus.COMPLETED, enums.ProjectStatus.CANCELLED]
        )
        project = request.query_params.get("project")
        if project and project.isdigit():
            projects = projects.filter(pk=int(project))
        items = collect_deadlines(projects)
        state = request.query_params.get("state")
        if state:
            items = [i for i in items if i.state == state]
        return Response([i.as_dict() for i in items])


class DashboardView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_view_name(self):
        return _("Land acquisition dashboard")

    def get(self, request, format=None):
        if not request.user.has_perm("pengadaan.view_acquisitionproject"):
            return Response(status=status.HTTP_403_FORBIDDEN)
        user = request.user
        projects = visible_projects(user)
        parcels = AcquisitionParcel.objects.exclude(is_excluded=True)
        if is_project_scoped(user):
            parcels = parcels.filter(project__in=projects)
        deadlines = collect_deadlines(
            projects.exclude(
                status__in=[
                    enums.ProjectStatus.COMPLETED,
                    enums.ProjectStatus.CANCELLED,
                ]
            )
        )
        data = {
            "projects_by_stage": dict(
                projects.values_list("stage")
                .annotate(n=Count("id"))
                .values_list("stage", "n")
            ),
            "projects_by_status": dict(
                projects.values_list("status")
                .annotate(n=Count("id"))
                .values_list("status", "n")
            ),
            "parcels_by_status": dict(
                parcels.values_list("status")
                .annotate(n=Count("id"))
                .values_list("status", "n")
            ),
            "affected_area_m2": parcels.aggregate(a=Sum("affected_area_m2"))["a"]
            or Decimal("0"),
            "released_area_m2": parcels.filter(
                status__in=[
                    enums.ParcelStatus.RELEASED,
                    enums.ParcelStatus.HANDED_OVER,
                ]
            ).aggregate(a=Sum("affected_area_m2"))["a"]
            or Decimal("0"),
            "deadlines_overdue": sum(1 for d in deadlines if d.state == "overdue"),
            "deadlines_due_soon": sum(1 for d in deadlines if d.state == "due_soon"),
            "upcoming_deadlines": [d.as_dict() for d in deadlines[:10]],
        }
        # Nilai uang dan keberatan hanya untuk peran yang boleh melihatnya.
        if user.has_perm("pengadaan.view_compensation"):
            compensations = scope_queryset(
                Compensation.objects.exclude(status=enums.CompensationStatus.CANCELLED),
                user,
            )
            data["compensation_total"] = compensations.aggregate(t=Sum("amount"))[
                "t"
            ] or Decimal("0")
            data["paid_total"] = CompensationPayment.objects.filter(
                compensation__in=compensations
            ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        if user.has_perm("pengadaan.view_objection"):
            data["open_objections"] = scope_queryset(
                Objection.objects.filter(
                    status__in=[
                        enums.ObjectionStatus.FILED,
                        enums.ObjectionStatus.IN_PROCESS,
                    ]
                ),
                user,
            ).count()
        return Response(data)


class ChoicesView(APIView):
    """Label pilihan (choices) modul pengadaan, sesuai bahasa permintaan."""

    permission_classes = (IsAuthenticated,)

    def get_view_name(self):
        return _("Land acquisition choices")

    def get(self, request, format=None):
        result = {}
        for name in dir(enums):
            obj = getattr(enums, name)
            if isinstance(obj, type) and hasattr(obj, "choices") and name[0].isupper():
                try:
                    result[name] = [
                        {"value": value, "label": str(label)}
                        for value, label in obj.choices
                    ]
                except TypeError:
                    continue
        return Response(result)


class WorkdaysView(APIView):
    """Kalkulator hari kerja: ?start=YYYY-MM-DD&days=N atau ?start=..&end=.."""

    permission_classes = (IsAuthenticated,)

    def get_view_name(self):
        return _("Working day calculator")

    def get(self, request, format=None):
        try:
            start = datetime.date.fromisoformat(request.query_params["start"])
        except (KeyError, ValueError):
            return Response(
                {"start": [_("Use format YYYY-MM-DD.")]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if "days" in request.query_params:
            try:
                days = int(request.query_params["days"])
            except ValueError:
                return Response(
                    {"days": [_("Must be an integer.")]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not 0 <= days <= 3650:
                return Response(
                    {"days": [_("Must be between 0 and 3650.")]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"start": start, "days": days, "date": add_workdays(start, days)}
            )
        try:
            end = datetime.date.fromisoformat(request.query_params["end"])
        except (KeyError, ValueError):
            return Response(
                {"end": [_("Use format YYYY-MM-DD.")]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {"start": start, "end": end, "workdays": workdays_between(start, end)}
        )
