"""Pemisahan data per unit layanan (lokasi).

Petugas hanya melihat data yang unit layanannya termasuk unit layanan mereka
atau yang belum diberi unit layanan. Superuser dan grup Administrator melihat
seluruh data (agregat lintas lokasi).
"""

from django.db.models import Q

from utils.group_permissions import UserGroup


def sees_all(user) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(pk=UserGroup.PAAKAYTTAJA).exists()


def unit_ids(user) -> list[int]:
    return list(user.service_units.values_list("pk", flat=True))


def scope_q(user, lookup: str = "service_unit") -> Q:
    """Filter Q untuk model dengan field unit layanan pada ``lookup``."""
    if sees_all(user):
        return Q()
    return Q(**{f"{lookup}__isnull": True}) | Q(**{f"{lookup}__in": unit_ids(user)})


def scoped(queryset, user, lookup: str = "service_unit"):
    return queryset.filter(scope_q(user, lookup))


def default_unit(user):
    """Unit layanan bawaan untuk data baru: satu-satunya unit milik pengguna."""
    if not user.is_authenticated:
        return None
    units = list(user.service_units.all()[:2])
    return units[0] if len(units) == 1 else None


def in_scope(user, service_unit_id) -> bool:
    """Apakah data dengan unit layanan ``service_unit_id`` terlihat oleh pengguna."""
    return (
        service_unit_id is None or sees_all(user) or service_unit_id in unit_ids(user)
    )


# --------------------------------------------------------------------------
# Dokumen: terlihat hanya bila objek yang ditautkan juga boleh dilihat
# --------------------------------------------------------------------------

# (field tautan di Document, nama model untuk kode izin)
DOCUMENT_LINKS = (
    ("asset", "landasset"),
    ("legal_case", "legalcase"),
    ("encroachment", "encroachmentcase"),
    ("survey", "surveyrequest"),
    ("liaison", "liaisonactivity"),
    ("tender", "tender"),
)


def document_q(user, prefix: str = "") -> Q:
    """Dokumen yang setiap objek tautannya boleh dilihat pengguna (izin & unit)."""
    condition = scope_q(user, f"{prefix}service_unit")
    everything = sees_all(user)
    for field, model_name in DOCUMENT_LINKS:
        empty = Q(**{f"{prefix}{field}__isnull": True})
        if not user.has_perm(f"asetlahan.view_{model_name}"):
            condition &= empty
        elif not everything:
            # Catatan: Q() kosong tidak boleh di-OR-kan (hasilnya hanya ``empty``).
            condition &= empty | scope_q(user, f"{prefix}{field}__service_unit")
    return condition


def documents(user, queryset=None):
    """Dokumen yang boleh dilihat, dicari, dan diunduh pengguna."""
    from asetlahan.models import Document

    queryset = Document.objects.all() if queryset is None else queryset
    if not user.has_perm("asetlahan.view_document"):
        return queryset.none()
    return queryset.filter(document_q(user))


def document_allows(user, document, action: str) -> bool:
    """Ubah/hapus dokumen juga memerlukan izin yang sama atas objek tautannya."""
    for field, model_name in DOCUMENT_LINKS:
        if getattr(document, f"{field}_id") is not None and not user.has_perm(
            f"asetlahan.{action}_{model_name}"
        ):
            return False
    return True
