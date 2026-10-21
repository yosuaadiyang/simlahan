"""Fungsi wilayah: Korwil di suatu titik, cek geofence absen, dan pemisahan data."""

from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from asetlahan import scope
from asetlahan.geo import utm_srid
from utils.group_permissions import UserGroup


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
# Pemisahan data
#
# Administrator, superuser, dan Petugas Aset Lahan mengawasi data per unit
# layanan (mengikuti modul aset lahan). Pengguna lain (Petugas Lapangan dan
# Koordinator Wilayah) hanya melihat Korwil tempat mereka menjadi anggota atau
# koordinator; data tanpa Korwil hanya terlihat oleh pembuatnya.
# --------------------------------------------------------------------------

# Field pembuat/pelapor per model: dasar data tanpa Korwil yang boleh dilihat.
OWNER_FIELDS = {
    "resident": "created_by",
    "activity": "reported_by",
    "activityphoto": "activity__reported_by",
    "soiltest": "sampled_by",
    "sosalert": "raised_by",
    "attendance": "user",
}
_AUTO = object()


def is_supervisor(user) -> bool:
    """Pengawas lintas Korwil: superuser, Administrator, dan Petugas Aset Lahan."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if scope.sees_all(user):
        return True
    return user.groups.filter(pk=UserGroup.PETUGAS_ASET).exists()


def korwil_q(user, prefix: str = "korwil", owner: str | None = None) -> Q:
    """Filter data yang boleh dilihat pengguna.

    ``prefix`` adalah jalur ke Korwil (kosong untuk model Korwil sendiri) dan
    ``owner`` jalur ke pembuat data, untuk data tanpa Korwil.
    """
    if is_supervisor(user):
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
    mine = user_korwils(user).values("pk")
    if not prefix:
        return Q(pk__in=mine)
    allowed = Q(**{f"{prefix}__in": mine})
    if owner and getattr(user, "is_authenticated", False):
        allowed |= Q(**{f"{prefix}__isnull": True, owner: user})
    return allowed


def scoped(queryset, user, prefix: str = "korwil", owner=_AUTO):
    if owner is _AUTO:
        owner = OWNER_FIELDS.get(queryset.model._meta.model_name)
    return queryset.filter(korwil_q(user, prefix, owner))


def visible_korwils(user):
    from operasi.models import Korwil

    return scoped(Korwil.objects.filter(is_active=True), user, prefix="")


OUT_OF_SCOPE_MESSAGE = _(
    "Lokasi berada di luar wilayah kerja Anda. Pilih Korwil Anda secara manual."
)


def korwil_for_write(user, point, *, strict: bool = True):
    """Korwil untuk data baru tanpa Korwil pilihan: dari lokasi, tetapi tidak
    pernah Korwil di luar wilayah kerja pengguna.

    Bila Korwil di lokasi tidak terlihat oleh pengguna, dipakai satu-satunya
    Korwil miliknya; bila tidak ada (atau lebih dari satu) data ditolak, atau
    tanpa Korwil bila ``strict`` mati (mis. SOS yang tidak boleh ditolak).
    """
    from django.core.exceptions import ValidationError

    found = korwil_for(point, user)
    if found is None:
        return None
    visible = visible_korwils(user)
    if visible.filter(pk=found.pk).exists():
        return found
    own = list(visible.filter(pk__in=user_korwils(user).values("pk"))[:2])
    if len(own) == 1:
        return own[0]
    if strict:
        raise ValidationError({"korwil": [OUT_OF_SCOPE_MESSAGE]})
    return None


def assign_korwil(obj, user, *, strict: bool = True) -> None:
    """Tetapkan Korwil data baru (bila belum dipilih) sesuai wilayah kerja pengguna."""
    if obj.korwil_id is None:
        obj.korwil = korwil_for_write(user, obj.location, strict=strict)
    # Jangan biarkan save() model menebak ulang Korwil dari lokasi.
    obj._korwil_resolved = True
