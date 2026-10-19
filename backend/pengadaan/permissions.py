"""Matriks hak akses modul pengadaan tanah per grup pengguna.

Diterapkan dengan ``python manage.py set_group_model_permissions``.
"""

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
from utils.group_permissions import UG, GroupModelPermissions

V = ("view",)
VA = ("view", "add")
VAC = ("view", "add", "change")
ALL = ("view", "add", "change", "delete")
SENSITIVE = "view_sensitive_personal_data"
VALIDATE = "validate_compensation"

# Grup yang hanya membaca seluruh modul.
READERS = (
    UG.SELAILIJA,
    UG.VALMISTELIJA,
    UG.SOPIMUSVALMISTELIJA,
    UG.SYOTTAJA,
)


def _perms(overrides=None):
    base = {group: V for group in READERS}
    base.update(
        {
            UG.PERINTALAKIMIES: V,
            UG.LASKUTTAJA: V,
            UG.PAAKAYTTAJA: ALL,
            UG.PELAKSANA_PENGADAAN: ALL,
            UG.SATGAS_PENGADAAN: V,
            UG.PENILAI: V,
            UG.INSTANSI_PEMOHON: None,
        }
    )
    base.update(overrides or {})
    return {"model": base, "fields": {}}


PENGADAAN_GROUP_MODEL_PERMISSIONS: GroupModelPermissions = {
    Holiday: _perms({UG.PELAKSANA_PENGADAAN: VAC, UG.INSTANSI_PEMOHON: V}),
    DeadlineRule: _perms(
        {UG.PELAKSANA_PENGADAAN: ("view", "change"), UG.INSTANSI_PEMOHON: V}
    ),
    AcquisitionProject: _perms({UG.INSTANSI_PEMOHON: V}),
    AcquisitionMilestone: _perms(
        {UG.SATGAS_PENGADAAN: ("view", "change"), UG.INSTANSI_PEMOHON: V}
    ),
    AcquisitionParcel: _perms({UG.SATGAS_PENGADAAN: VAC, UG.INSTANSI_PEMOHON: V}),
    EntitledParty: _perms(
        {
            UG.PAAKAYTTAJA: ALL + (SENSITIVE,),
            UG.PELAKSANA_PENGADAAN: ALL + (SENSITIVE,),
            UG.SATGAS_PENGADAAN: VAC + (SENSITIVE,),
            UG.PENILAI: V,
        }
    ),
    ParcelSurvey: _perms({UG.SATGAS_PENGADAAN: ALL}),
    InventoryItem: _perms({UG.SATGAS_PENGADAAN: ALL, UG.PENILAI: V}),
    Announcement: _perms({UG.SATGAS_PENGADAAN: VA, UG.INSTANSI_PEMOHON: V}),
    Valuation: _perms({UG.PENILAI: VAC}),
    Deliberation: _perms({UG.SATGAS_PENGADAAN: VA, UG.INSTANSI_PEMOHON: V}),
    DeliberationResult: _perms({UG.SATGAS_PENGADAAN: VAC}),
    Objection: _perms({UG.PERINTALAKIMIES: VAC}),
    Consignment: _perms({UG.PERINTALAKIMIES: VAC}),
    Compensation: _perms(
        {
            UG.PAAKAYTTAJA: ALL + (VALIDATE,),
            UG.PELAKSANA_PENGADAAN: ALL + (VALIDATE,),
            UG.LASKUTTAJA: ("view", "change"),
        }
    ),
    CompensationPayment: _perms({UG.LASKUTTAJA: VAC}),
    RightsRelease: _perms({UG.SATGAS_PENGADAAN: VAC}),
    Handover: _perms({UG.INSTANSI_PEMOHON: V}),
    AffectedHousehold: _perms({UG.SATGAS_PENGADAAN: VAC}),
    AcquisitionDocument: _perms(
        {
            UG.SATGAS_PENGADAAN: VA,
            UG.PENILAI: VA,
            UG.PERINTALAKIMIES: VA,
            UG.INSTANSI_PEMOHON: VA,
        }
    ),
}
