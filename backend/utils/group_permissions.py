from enum import IntEnum
from typing import NotRequired, TypeAlias, TypedDict

from django.db.models import Model


class UserGroup(IntEnum):
    SELAILIJA = 1
    VALMISTELIJA = 2
    SOPIMUSVALMISTELIJA = 3
    SYOTTAJA = 4
    PERINTALAKIMIES = 5
    LASKUTTAJA = 6
    PAAKAYTTAJA = 7
    # Peran modul pengadaan tanah
    PELAKSANA_PENGADAAN = 8
    SATGAS_PENGADAAN = 9
    PENILAI = 10
    INSTANSI_PEMOHON = 11
    # Peran modul alokasi lahan
    PETUGAS_ALOKASI = 12
    TIM_VERIFIKASI = 13
    # Peran modul manajemen aset lahan
    PETUGAS_ASET = 14
    PETUGAS_HUKUM = 15
    PETUGAS_LAPANGAN = 16
    # Peran pusat komando operasi lapangan
    KOORDINATOR_WILAYAH = 17


UG = UserGroup

# Grup yang bekerja di panel /admin/ (alokasi & aset lahan): anggotanya
# otomatis berstatus staf.
ADMIN_PANEL_GROUPS = {
    UserGroup.PETUGAS_ALOKASI,
    UserGroup.TIM_VERIFIKASI,
    UserGroup.PETUGAS_ASET,
    UserGroup.PETUGAS_HUKUM,
    UserGroup.PETUGAS_LAPANGAN,
    UserGroup.KOORDINATOR_WILAYAH,
}

MANAGED_USER_GROUP_ID_RANGE = [
    group.value for group in UserGroup
]  # These groups have their permissions managed with permissions management commands.


PermissionNames: TypeAlias = tuple[str, ...] | None
ModelGroupPermissions: TypeAlias = dict[UserGroup, PermissionNames]
FieldGroupPermissions: TypeAlias = dict[UserGroup, str | None]
FieldPermissions: TypeAlias = dict[str, FieldGroupPermissions]


class ModelPermissionConfiguration(TypedDict):
    """Configured model- and field-level permissions for one Django model."""

    model: ModelGroupPermissions  # Standard django model permissions
    fields: NotRequired[
        FieldPermissions
    ]  # Custom field_permissions app definitions for fine-grained control


GroupModelPermissions: TypeAlias = dict[type[Model], ModelPermissionConfiguration]
