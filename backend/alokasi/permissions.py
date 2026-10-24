"""Matriks hak akses modul alokasi lahan per grup pengguna.

Diterapkan dengan ``python manage.py set_group_model_permissions`` (otomatis
lewat ``simlahan_bootstrap``). Pemohon tidak masuk grup mana pun; mereka
memakai portal /portal/ yang memeriksa kepemilikan data sendiri.
"""

from alokasi.models import (
    Allocation,
    AllocationSettings,
    Applicant,
    Application,
    ApplicationDocument,
    ApplicationEvent,
    DevelopmentReport,
    InfoPage,
    Invoice,
    IssuedDocument,
    LandPlot,
    PermitReport,
    RequirementDocType,
    ServiceCatalog,
    VerificationCriterion,
    VerificationScore,
)
from utils.group_permissions import UG, GroupModelPermissions

V = ("view",)
VC = ("view", "change")
ALL = ("view", "add", "change", "delete")


# Hanya grup yang bekerja di panel /admin/alokasi/. Grup lain tidak diberi izin
# karena anggotanya bukan staf dan tidak dapat membuka panel tersebut.
def _staff(admin, officer, verifier):
    return {
        "model": {
            UG.PAAKAYTTAJA: admin,
            UG.PETUGAS_ALOKASI: officer,
            UG.TIM_VERIFIKASI: verifier,
        },
        "fields": {},
    }


ALOKASI_GROUP_MODEL_PERMISSIONS: GroupModelPermissions = {
    # Bobot kriteria & nilai minimum menentukan hasil verifikasi teknis, jadi
    # hanya Administrator yang boleh mengubahnya (petugas yang memutuskan
    # permohonan tidak boleh mengubah aturan penilaiannya sendiri).
    AllocationSettings: _staff(VC, V, V),
    LandPlot: _staff(ALL, ALL, V),
    InfoPage: _staff(ALL, ALL, None),
    Applicant: _staff(VC, VC, V),
    RequirementDocType: _staff(ALL, ALL, V),
    ServiceCatalog: _staff(ALL, ALL, V),
    VerificationCriterion: _staff(ALL, V, V),
    Application: _staff(
        VC + ("verify_application", "decide_application"),
        VC + ("decide_application",),
        V + ("verify_application",),
    ),
    ApplicationDocument: _staff(V, V, V),
    VerificationScore: _staff(V, V, V),
    ApplicationEvent: _staff(V, V, V),
    Invoice: _staff(VC + ("verify_payment",), VC + ("verify_payment",), V),
    Allocation: _staff(VC + ("revoke_allocation",), VC + ("revoke_allocation",), V),
    IssuedDocument: _staff(V, V, V),
    PermitReport: _staff(V, V, V),
    DevelopmentReport: _staff(V, V, V),
}
