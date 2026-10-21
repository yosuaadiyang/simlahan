"""Pembatasan data pengadaan per proyek untuk peran eksternal.

Penilai Pertanahan (grup 10) dan Instansi Yang Memerlukan Tanah (grup 11)
adalah pihak luar: mereka hanya melihat proyek yang ditugaskan kepadanya
(``AcquisitionProject.assigned_users``). Pengguna yang juga berada di grup
internal (1–9, termasuk Administrator) serta superuser tetap melihat semua
proyek. Pengguna tanpa grup sama sekali (mis. izin diberikan langsung) tidak
dibatasi; hak modelnya tetap diperiksa seperti biasa.
"""

from django.db.models import QuerySet

from pengadaan import enums
from utils.group_permissions import UG

# Grup internal: melihat seluruh proyek.
FULL_ACCESS_GROUPS = frozenset(
    {
        UG.SELAILIJA,
        UG.VALMISTELIJA,
        UG.SOPIMUSVALMISTELIJA,
        UG.SYOTTAJA,
        UG.PERINTALAKIMIES,
        UG.LASKUTTAJA,
        UG.PAAKAYTTAJA,
        UG.PELAKSANA_PENGADAAN,
        UG.SATGAS_PENGADAAN,
    }
)
# Grup eksternal: hanya proyek yang ditugaskan.
PROJECT_SCOPED_GROUPS = frozenset({UG.PENILAI, UG.INSTANSI_PEMOHON})


# Jenis dokumen yang memuat data pribadi pihak yang berhak; bersama dokumen
# yang dikaitkan ke pihak tertentu hanya terlihat oleh pemegang izin
# ``pengadaan.view_sensitive_personal_data``.
SENSITIVE_DOCUMENT_TYPES = (
    enums.DocumentType.ID_CARD,
    enums.DocumentType.CERTIFICATE,
    enums.DocumentType.PAYMENT_PROOF,
)

# Jenis dokumen yang boleh diunggah pengguna yang hanya berperan sebagai
# Instansi Yang Memerlukan Tanah: dokumen perencanaan/permohonan dari instansi,
# berita acara serah terima yang ikut ditandatanganinya, foto dan lain-lain.
REQUESTING_AGENCY_DOCUMENT_TYPES = (
    enums.DocumentType.DPPT,
    enums.DocumentType.FEASIBILITY,
    enums.DocumentType.HANDOVER_MINUTES,
    enums.DocumentType.PHOTO,
    enums.DocumentType.OTHER,
)


def _group_ids(user) -> frozenset[int]:
    cached = getattr(user, "_pengadaan_group_ids", None)
    if cached is None:
        cached = frozenset(user.groups.values_list("id", flat=True))
        try:
            user._pengadaan_group_ids = cached
        except AttributeError:  # pragma: no cover - objek pengguna tanpa atribut
            pass
    return cached


def is_project_scoped(user) -> bool:
    """Benar bila pengguna hanya boleh melihat proyek yang ditugaskan."""
    if user is None or not user.is_authenticated or user.is_superuser:
        return False
    groups = _group_ids(user)
    if groups & FULL_ACCESS_GROUPS:
        return False
    return bool(groups & PROJECT_SCOPED_GROUPS)


def is_requesting_agency_only(user) -> bool:
    """Benar bila satu-satunya peran pengadaan pengguna adalah Instansi Pemohon."""
    if user is None or not user.is_authenticated or user.is_superuser:
        return False
    groups = _group_ids(user)
    return UG.INSTANSI_PEMOHON in groups and not (
        groups & (FULL_ACCESS_GROUPS | {UG.PENILAI})
    )


def visible_project_ids(user) -> QuerySet:
    """Subkueri id proyek yang ditugaskan kepada pengguna."""
    from pengadaan.models import AcquisitionProject

    return AcquisitionProject.objects.filter(assigned_users=user).values("pk")


def visible_projects(user) -> QuerySet:
    from pengadaan.models import AcquisitionProject

    projects = AcquisitionProject.objects.all()
    if is_project_scoped(user):
        projects = projects.filter(pk__in=visible_project_ids(user))
    return projects


def scope_queryset(queryset: QuerySet, user, lookup: str | None = None) -> QuerySet:
    """Batasi ``queryset`` ke proyek yang terlihat oleh ``user``.

    ``lookup`` adalah jalur ke proyek (mis. ``parcel__project``); bila kosong
    diambil dari ``PROJECT_LOOKUPS`` menurut model queryset.
    """
    if not is_project_scoped(user):
        return queryset
    if lookup is None:
        lookup = project_lookup_for(queryset.model)
        if lookup is None:
            return queryset
    return queryset.filter(**{f"{lookup}__in": visible_project_ids(user)})


def project_lookup_for(model) -> str | None:
    from pengadaan import models as m

    return {
        m.AcquisitionProject: "pk",
        m.AcquisitionMilestone: "project",
        m.AcquisitionParcel: "project",
        m.EntitledParty: "parcel__project",
        m.ParcelSurvey: "parcel__project",
        m.InventoryItem: "parcel__project",
        m.Announcement: "project",
        m.Valuation: "parcel__project",
        m.Deliberation: "project",
        m.DeliberationResult: "parcel__project",
        m.Objection: "project",
        m.Consignment: "parcel__project",
        m.Compensation: "parcel__project",
        m.CompensationPayment: "compensation__parcel__project",
        m.RightsRelease: "parcel__project",
        m.Handover: "project",
        m.AffectedHousehold: "project",
        m.AcquisitionDocument: "project",
    }.get(model)
