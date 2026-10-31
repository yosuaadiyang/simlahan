"""Matriks hak akses pusat komando per grup.

Diterapkan dengan ``python manage.py set_group_model_permissions`` (otomatis
lewat ``simlahan_bootstrap``). Kunci hidup sistem sengaja tidak diberikan ke
grup mana pun: hanya superuser yang dapat mengelolanya.
"""

from operasi.models import (
    Activity,
    ActivityPhoto,
    ActivityWeight,
    AreaAnalysis,
    Attendance,
    ChatMessage,
    CommandSettings,
    DailyReport,
    DailyReportAttachment,
    DailyReportEvent,
    HuntingParkFinding,
    HuntingParkPatrol,
    IllegalFinding,
    IllegalFindingVisit,
    Korwil,
    LandAreaChange,
    LandPlot,
    LandPlotChange,
    OfficerPosition,
    OfficerProfile,
    OfficerTrackPoint,
    PatrolObservation,
    PatrolPhoto,
    PatrolSession,
    Resident,
    Seedling,
    SitePhoto360,
    SoilTest,
    SosAlert,
    StanceChange,
    SystemLock,
    TaskEvent,
    TaskPoint,
    ThreatZone,
)
from utils.group_permissions import UG, GroupModelPermissions

V = ("view",)
VA = ("view", "add")
VC = ("view", "change")
VAC = ("view", "add", "change")
VD = ("view", "delete")
VAD = ("view", "add", "delete")
ALL = ("view", "add", "change", "delete")
# NIK & nomor KK warga hanya untuk Administrator.
NIK = "view_resident_nik"


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
    Resident: _perms(ALL + (NIK,), VAC, VAC, V),
    StanceChange: _perms(V, V, V, V),
    LandAreaChange: _perms(V, V, V, V),
    Activity: _perms(ALL, VAC, VA, V),
    ActivityPhoto: _perms(ALL, VAC, VA, V),
    ActivityWeight: _perms(VC),
    # Temuan ilegal: kunjungan berulang boleh memperbarui profil temuan.
    IllegalFinding: _perms(ALL, VAC, VAC, V),
    IllegalFindingVisit: _perms(ALL, VAC, VA, V),
    HuntingParkPatrol: _perms(ALL, VAC, VA, V),
    HuntingParkFinding: _perms(ALL, VAC, VA, V),
    Seedling: _perms(ALL, VAC, VA, V),
    PatrolSession: _perms(ALL, VAC, VA, V),
    PatrolObservation: _perms(ALL, VAC, VA, V),
    PatrolPhoto: _perms(ALL, VAC, VA, V),
    SoilTest: _perms(ALL, VAC, VA, V),
    Attendance: _perms(ALL, VA, VA, VA),
    ChatMessage: _perms(VAD, VA, VA, VA),
    SosAlert: _perms(ALL, VAC, VA, VA),
    OfficerPosition: _perms(VAD, VA, VA, VA),
    AreaAnalysis: _perms(VAD, VA, VA, VA),
    # Atasan langsung diatur Administrator; semua petugas boleh melihat strukturnya.
    OfficerProfile: _perms(ALL, V, V, V),
    TaskEvent: _perms(ALL, VA, VA, VA),
    TaskPoint: _perms(ALL, V, V, V),
    # Laporan harian berjenjang: semua tingkat menyusun, mengirim, dan merevisi.
    DailyReport: _perms(ALL, VAC, VAC, VAC),
    DailyReportEvent: _perms(ALL, VA, VA, VA),
    DailyReportAttachment: _perms(ALL, VA, VA, VA),
    # Peta & spasial: penguasaan lahan dicatat petugas lapangan dan koordinator.
    LandPlot: _perms(ALL, VAC, VAC, V),
    LandPlotChange: _perms(V, V, V, V),
    ThreatZone: _perms(ALL, VAC, V, VAC),
    # Jejak GPS hanya untuk pimpinan; cakupan dibatasi ``visible_officers``.
    OfficerTrackPoint: _perms(V, V),
    SitePhoto360: _perms(ALL, VAD, VA, V),
}
