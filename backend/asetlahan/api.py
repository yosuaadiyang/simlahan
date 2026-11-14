"""API baca-saja modul aset lahan (/v1/aset/…) untuk integrasi sistem lain (ERP, GIS, dasbor).

Autentikasi sama dengan API petugas lain (JWT, token, atau sesi) dan
mengikuti izin lihat per model serta pemisahan unit layanan. Bidang geometri
dikirim sebagai GeoJSON.
"""

from django.http import Http404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, routers, serializers, viewsets
from rest_framework.permissions import IsAuthenticated

from asetlahan import scope
from asetlahan.models import (
    EncroachmentCase,
    Grievance,
    LandAsset,
    LandTransaction,
    LegalCase,
    ModuleSettings,
    Task,
    TaxObligation,
    Tender,
)
from leasing.permissions import MvjDjangoModelPermissions

# (rute, model, kolom, kolom pencarian, filter, lookup unit layanan, saklar modul)
RESOURCES = (
    (
        "aset/asset",
        LandAsset,
        [
            "id",
            "code",
            "name",
            "category",
            "status",
            "district",
            "village",
            "address",
            "area_m2",
            "geometry",
            "title_type",
            "title_number",
            "nib",
            "title_date",
            "title_expiry",
            "registered_owner",
            "acquisition_method",
            "acquisition_date",
            "acquisition_cost",
            "njop_per_m2",
            "zoning",
            "land_use",
            "pengadaan_parcel",
            "alokasi_plot",
            "lease",
            "service_unit",
            "created_at",
            "modified_at",
        ],
        ["code", "name", "title_number", "nib", "registered_owner"],
        ["status", "category", "title_type", "service_unit"],
        "service_unit",
        "",
    ),
    (
        "aset/tax",
        TaxObligation,
        "__all__",
        ["asset__code", "reference"],
        ["asset", "tax_type", "period"],
        "asset__service_unit",
        "enable_valuation",
    ),
    (
        "aset/transaction",
        LandTransaction,
        "__all__",
        ["number", "asset__code", "description", "reference"],
        ["asset", "transaction_type"],
        "service_unit",
        "enable_valuation",
    ),
    (
        "aset/legal_case",
        LegalCase,
        [
            "id",
            "number",
            "court_case_number",
            "title",
            "case_type",
            "court",
            "court_name",
            "our_position",
            "opposing_party",
            "status",
            "outcome",
            "filed_date",
            "decision_date",
            "claim_value",
            "disputed_area_m2",
            "assets",
            "service_unit",
            "created_at",
            "modified_at",
        ],
        ["number", "court_case_number", "title", "opposing_party"],
        ["status", "case_type", "court"],
        "service_unit",
        "enable_litigation",
    ),
    (
        "aset/encroachment",
        EncroachmentCase,
        "__all__",
        ["number", "title"],
        ["status", "asset"],
        "service_unit",
        "enable_encroachment",
    ),
    (
        "aset/task",
        Task,
        "__all__",
        ["number", "title"],
        ["status", "priority", "assignee", "team"],
        "service_unit",
        "enable_tasks",
    ),
    (
        "aset/grievance",
        Grievance,
        [
            "id",
            "number",
            "channel",
            "category",
            "subject",
            "description",
            "location_text",
            "location",
            "asset",
            "status",
            "due_date",
            "resolved_on",
            "service_unit",
            "created_at",
            "modified_at",
        ],
        ["number", "subject"],
        ["status", "category", "channel"],
        "service_unit",
        "enable_grievance",
    ),
    (
        "aset/tender",
        Tender,
        [
            "id",
            "number",
            "title",
            "method",
            "asset",
            "alokasi_plot",
            "reserve_price",
            "open_at",
            "close_at",
            "status",
            "winner",
            "awarded_on",
            "service_unit",
            "created_at",
            "modified_at",
        ],
        ["number", "title"],
        ["status", "method"],
        "service_unit",
        "enable_tender",
    ),
)


# Data master lintas modul yang boleh tampil sebagai label bagi semua petugas
# (sama dengan ForeignFieldsMixin di admin).
SHARED_MODELS = {"users.user", "leasing.serviceunit", "leasing.municipality"}


class ApiSerializer(serializers.ModelSerializer):
    """Tautan ke modul lain (pengadaan, alokasi, sewa, operasi) hanya dikirim
    bila pengguna boleh melihat model tujuannya, sama dengan panel admin."""

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None:
            return fields
        for field in self.Meta.model._meta.get_fields():
            if field.name not in fields or not field.concrete:
                continue
            if not (field.many_to_one or field.many_to_many):
                continue
            meta = field.related_model._meta
            if meta.app_label == "asetlahan" or meta.label_lower in SHARED_MODELS:
                continue
            if not user.has_perm(f"{meta.app_label}.view_{meta.model_name}"):
                fields.pop(field.name)
        return fields


def _viewset(model, fields, search, filterset, lookup, flag):
    serializer = type(
        f"{model.__name__}ApiSerializer",
        (ApiSerializer,),
        {
            "Meta": type("Meta", (), {"model": model, "fields": fields}),
        },
    )

    class ViewSet(viewsets.ReadOnlyModelViewSet):
        queryset = model.objects.all().order_by("pk")
        serializer_class = serializer
        permission_classes = (IsAuthenticated, MvjDjangoModelPermissions)
        filter_backends = (
            DjangoFilterBackend,
            filters.SearchFilter,
            filters.OrderingFilter,
        )
        search_fields = search
        filterset_fields = filterset

        @property
        def ordering_fields(self):
            # Hanya kolom yang memang dikirim ke pengguna ini; "__all__" juga
            # mengizinkan urut berdasarkan kolom tersembunyi (mis. kode akses
            # dan data pelapor pengaduan) sehingga nilainya bisa ditebak.
            return [
                name
                for name, field in self.get_serializer().fields.items()
                if getattr(field, "source", name) != "*"
                and name != "geometry"
                and "." not in (field.source or name)
            ]

        def get_queryset(self):
            if flag and not getattr(ModuleSettings.load(), flag):
                raise Http404
            return scope.scoped(super().get_queryset(), self.request.user, lookup)

    ViewSet.__name__ = f"{model.__name__}ApiViewSet"
    return ViewSet


router = routers.SimpleRouter()
for _prefix, _model, _fields, _search, _filters, _lookup, _flag in RESOURCES:
    router.register(
        _prefix,
        _viewset(_model, _fields, _search, _filters, _lookup, _flag),
        basename=f"aset-{_model._meta.model_name}",
    )

urlpatterns = router.urls
