"""Matriks hak akses modul aset lahan per grup.

Diterapkan dengan ``python manage.py set_group_model_permissions`` (otomatis
lewat ``simlahan_bootstrap``). Hanya grup yang bekerja di panel /admin/ yang
diberi izin, karena anggota grup lain bukan staf.
"""

from asetlahan.models import (
    Advocate,
    AssetCategory,
    AssetValuation,
    Bid,
    CaseHearing,
    Document,
    EncroachmentActionLog,
    EncroachmentCase,
    Facilitator,
    FieldReport,
    Grievance,
    GrievanceCategory,
    HeirMember,
    Heirship,
    LandAsset,
    LandTransaction,
    LegalCase,
    LiaisonActivity,
    MapShare,
    ModuleSettings,
    OwnershipRecord,
    ResettlementSite,
    ResettlementUnit,
    SatelliteImage,
    Stakeholder,
    StakeholderEngagement,
    SurveyRequest,
    Task,
    TaxObligation,
    Team,
    Tender,
    ValuationItem,
)
from utils.group_permissions import UG, GroupModelPermissions

V = ("view",)
VC = ("view", "change")
VA = ("view", "add")
VAC = ("view", "add", "change")
ALL = ("view", "add", "change", "delete")


def _perms(admin, asset, legal=None, field=None):
    groups = {UG.PAAKAYTTAJA: admin, UG.PETUGAS_ASET: asset}
    if legal:
        groups[UG.PETUGAS_HUKUM] = legal
    if field:
        groups[UG.PETUGAS_LAPANGAN] = field
    return {"model": groups, "fields": {}}


ASETLAHAN_GROUP_MODEL_PERMISSIONS: GroupModelPermissions = {
    ModuleSettings: _perms(VC, V),
    AssetCategory: _perms(ALL, ALL, V, V),
    GrievanceCategory: _perms(ALL, ALL),
    Team: _perms(ALL, ALL, V, V),
    LandAsset: _perms(ALL, ALL, V, V),
    OwnershipRecord: _perms(ALL, ALL, V),
    Heirship: _perms(ALL, ALL, V),
    HeirMember: _perms(ALL, ALL, V),
    Stakeholder: _perms(ALL, ALL, V),
    StakeholderEngagement: _perms(ALL, ALL, V),
    AssetValuation: _perms(ALL, ALL, V),
    ValuationItem: _perms(ALL, ALL, V),
    TaxObligation: _perms(ALL, ALL, V),
    LandTransaction: _perms(ALL, VAC, V),
    ResettlementSite: _perms(ALL, ALL, None, V),
    ResettlementUnit: _perms(ALL, ALL, None, V),
    Advocate: _perms(ALL, V, ALL),
    LegalCase: _perms(ALL, V, ALL),
    CaseHearing: _perms(ALL, V, ALL),
    SatelliteImage: _perms(ALL, ALL, None, V),
    EncroachmentCase: _perms(ALL, ALL, VC, VAC),
    EncroachmentActionLog: _perms(ALL, ALL, V, VA),
    SurveyRequest: _perms(ALL, ALL, V, VC),
    Facilitator: _perms(ALL, ALL, V),
    LiaisonActivity: _perms(ALL, ALL, VAC),
    Task: _perms(ALL, ALL, VAC, VC),
    Grievance: _perms(ALL, ALL, VC, VC),
    Tender: _perms(ALL, ALL),
    Bid: _perms(VC, VC),
    Document: _perms(ALL, ALL, ALL, VA),
    MapShare: _perms(ALL, ALL, VA),
    FieldReport: _perms(ALL, VAC, V, VA),
}
