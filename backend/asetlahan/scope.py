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
