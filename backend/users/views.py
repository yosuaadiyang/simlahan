from django.contrib import auth
from django.contrib.auth.models import Permission
from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from leasing.serializers.service_unit import ServiceUnitSerializer

# Aplikasi petugas (SPA) memeriksa izin berdasarkan codename saja. Beberapa
# codename dipakai oleh lebih dari satu aplikasi (mis. "view_invoice" milik
# leasing dan alokasi); izin dari aplikasi lain tidak boleh membuka fitur sewa.
SPA_PRIMARY_APP_LABEL = "leasing"


def _without_shadowed_codenames(permissions):
    permissions = list(permissions)
    primary = Permission.objects.filter(
        content_type__app_label=SPA_PRIMARY_APP_LABEL,
        codename__in={p.codename for p in permissions},
    )
    primary_codenames = set(primary.values_list("codename", flat=True))
    primary_content_types = set(primary.values_list("content_type_id", flat=True))
    return [
        p
        for p in permissions
        if p.codename not in primary_codenames
        or p.content_type_id in primary_content_types
    ]


class UsersPermissions(APIView):
    permission_classes = (IsAuthenticated,)

    def get_view_name(self):
        return _("Users permissions")

    def get(self, request, format=None):
        if request.user.is_superuser:
            permissions = Permission.objects.all()
        else:
            permissions = set()
            for backend in auth.get_backends():
                if hasattr(backend, "get_all_permissions"):
                    permissions.update(backend._get_user_permissions(request.user))
                    permissions.update(backend._get_group_permissions(request.user))

        permissions = _without_shadowed_codenames(permissions)
        groups = [g.name for g in request.user.groups.all()]
        service_units = request.user.service_units.all()
        service_units_serializer = ServiceUnitSerializer(service_units, many=True)

        return Response(
            {
                "groups": groups,
                "service_units": service_units_serializer.data,
                "permissions": [
                    {"name": p.name, "codename": p.codename} for p in permissions
                ],
            }
        )
