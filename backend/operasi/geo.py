"""Fungsi wilayah: Korwil di suatu titik, cek geofence absen, dan pemisahan data."""

from django.db.models import Q

from asetlahan import scope
from asetlahan.geo import utm_srid


def korwil_at(point):
    """Korwil aktif yang batasnya memuat titik (wilayah terkecil bila bertumpuk)."""
    from django.contrib.gis.db.models.functions import Area

    from operasi.models import Korwil

    if point is None:
        return None
    return (
        Korwil.objects.filter(is_active=True, geometry__intersects=point)
        .annotate(size=Area("geometry"))
        .order_by("size")
        .first()
    )


def user_korwils(user):
    from operasi.models import Korwil

    if user is None or not getattr(user, "is_authenticated", False):
        return Korwil.objects.none()
    return Korwil.objects.filter(
        Q(members=user) | Q(coordinator=user), is_active=True
    ).distinct()


def korwil_for(point, user=None):
    """Korwil dari lokasi; bila tanpa lokasi, Korwil tunggal tempat petugas bertugas."""
    found = korwil_at(point)
    if found is not None or user is None:
        return found
    korwils = list(user_korwils(user)[:2])
    return korwils[0] if len(korwils) == 1 else None


def distance_m(korwil, point) -> float | None:
    """Jarak titik ke batas Korwil dalam meter (0 bila di dalam)."""
    if korwil is None or korwil.geometry is None or point is None:
        return None
    if korwil.geometry.intersects(point):
        return 0.0
    srid = utm_srid(korwil.geometry)
    return korwil.geometry.transform(srid, clone=True).distance(
        point.transform(srid, clone=True)
    )


def in_area(korwil, point, tolerance_m: float = 0) -> bool | None:
    distance = distance_m(korwil, point)
    if distance is None:
        return None
    return distance <= tolerance_m


# --------------------------------------------------------------------------
# Pemisahan data per unit layanan (mengikuti modul aset lahan)
# --------------------------------------------------------------------------


def korwil_q(user, prefix: str = "korwil") -> Q:
    """Data tanpa Korwil, Korwil tanpa unit layanan, atau Korwil di unit milik pengguna."""
    if scope.sees_all(user):
        return Q()
    units = scope.unit_ids(user)
    if not prefix:
        return Q(service_unit__isnull=True) | Q(service_unit__in=units)
    return (
        Q(**{f"{prefix}__isnull": True})
        | Q(**{f"{prefix}__service_unit__isnull": True})
        | Q(**{f"{prefix}__service_unit__in": units})
    )


def scoped(queryset, user, prefix: str = "korwil"):
    return queryset.filter(korwil_q(user, prefix))
