"""Matriks hak akses pusat komando per grup.

Diterapkan dengan ``python manage.py set_group_model_permissions`` (otomatis
lewat ``simlahan_bootstrap``). Kunci hidup sistem sengaja tidak diberikan ke
grup mana pun: hanya superuser yang dapat mengelolanya.
"""

from operasi.models import (
    Activity,
    ActivityPhoto,
    AreaAnalysis,
    Attendance,
    ChatMessage,
    CommandSettings,
    Korwil,
    OfficerPosition,
    Resident,
    SoilTest,
    SosAlert,
    StanceChange,
    SystemLock,
)
from utils.group_permissions import UG, GroupModelPermissions

V = ("view",)
VA = ("view", "add")
VC = ("view", "change")
VAC = ("view", "add", "change")
VD = ("view", "delete")
VAD = ("view", "add", "delete")
ALL = ("view", "add", "change", "delete")


def _perms(admin, coordinator=None, field=None, asset=None):
    groups = {
        UG.PAAKAYTTAJA: admin,
        UG.KOORDINATOR_WILAYAH: coordinator,
        UG.PETUGAS_LAPANGAN: field,
        UG.PETUGAS_ASET: asset,
    }
    return {"model": {k: v for k, v in groups.items() if v}, "fields": {}}


OPERASI_GROUP_MODEL_PERMISSIONS: GroupModelPermissions = {
    CommandSettings: _perms(VC),
    SystemLock: _perms(None),
    Korwil: _perms(ALL, V, V, V),
    Resident: _perms(ALL, VAC, VAC, V),
    StanceChange: _perms(V, V, V, V),
    Activity: _perms(ALL, VAC, VA, V),
    ActivityPhoto: _perms(ALL, VAC, VA, V),
    SoilTest: _perms(ALL, VAC, VA, V),
    Attendance: _perms(ALL, VA, VA, VA),
    ChatMessage: _perms(VAD, VA, VA, VA),
    SosAlert: _perms(ALL, VAC, VA, VA),
    OfficerPosition: _perms(VAD, VA, VA, VA),
    AreaAnalysis: _perms(VAD, VA, VA, VA),
}
