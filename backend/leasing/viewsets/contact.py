from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.permissions import IsAuthenticated

from field_permissions.viewsets import FieldPermissionsViewsetMixin
from leasing.filters import CoalesceOrderingFilter, ContactFilter
from leasing.models import Contact
from leasing.permissions import IsMemberOfSameServiceUnit, MvjDjangoModelPermissions
from leasing.serializers.contact import (
    ContactCreateUpdateSerializer,
    ContactSerializerWithActiveLeases,
)

from .utils import AtomicTransactionModelViewSet


class ContactViewSet(FieldPermissionsViewsetMixin, AtomicTransactionModelViewSet):
    queryset = Contact.objects.all()
    # Baca lintas unit boleh; ubah/hapus hanya oleh anggota unit layanan kontak.
    permission_classes = [
        IsAuthenticated,
        MvjDjangoModelPermissions,
        IsMemberOfSameServiceUnit,
    ]
    serializer_class = ContactSerializerWithActiveLeases
    filterset_class = ContactFilter
    filter_backends = (
        DjangoFilterBackend,
        filters.SearchFilter,
        CoalesceOrderingFilter,
    )
    search_fields = (
        "id",
        "first_name",
        "last_name",
        "name",
        "business_id",
        "sap_customer_number",
        "care_of",
    )
    ordering_fields = (
        "names",
        "first_name",
        "last_name",
        "name",
        "business_id",
        "type",
        "care_of",
    )
    coalesce_ordering = {"names": ("name", "last_name")}
    ordering = ("names", "first_name")

    def get_queryset(self):
        return Contact.objects.select_related("service_unit").prefetch_related(
            # Required for `contacts_active_leases` serializer method field
            "tenants__lease__identifier",
            # Improve performance of contact list filters.
            "tenantcontact_set",
        )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update", "metadata"):
            return ContactCreateUpdateSerializer

        return ContactSerializerWithActiveLeases
