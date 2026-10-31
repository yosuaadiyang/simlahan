"""Struktur atasan–bawahan pusat komando.

Atasan langsung diambil dari jabatan petugas (``OfficerProfile``). Tanpa
atasan yang diatur, atasan anggota Korwil adalah koordinator Korwil-nya.
Struktur ini menentukan ke mana laporan harian dikirim, siapa yang boleh
memberi tugas, dan siapa yang memverifikasi tugas.
"""

from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from operasi.models import Korwil, OfficerProfile

MAX_DEPTH = 12


def _explicit_supervisor(user):
    profile = (
        OfficerProfile.objects.filter(user=user, supervisor__is_active=True)
        .select_related("supervisor")
        .first()
    )
    return profile.supervisor if profile else None


def supervisor_of(user):
    """Atasan langsung yang aktif, atau None untuk pimpinan tertinggi."""
    if user is None:
        return None
    supervisor = _explicit_supervisor(user)
    if supervisor is not None:
        return supervisor
    korwil = (
        Korwil.objects.filter(
            members=user,
            is_active=True,
            coordinator__isnull=False,
            coordinator__is_active=True,
        )
        .exclude(coordinator=user)
        .select_related("coordinator")
        .order_by("code")
        .first()
    )
    return korwil.coordinator if korwil else None


def direct_subordinate_ids(user) -> set[int]:
    """Bawahan langsung: petugas yang atasan langsungnya (``supervisor_of``)
    adalah pengguna, baik diatur di jabatan maupun lewat Korwil yang dipimpin."""
    User = get_user_model()
    candidates = User.objects.filter(is_active=True).exclude(pk=user.pk)
    explicit = candidates.filter(komando_profile__supervisor=user)
    members = candidates.filter(
        operasi_korwil__coordinator=user, operasi_korwil__is_active=True
    )
    found = set()
    for candidate in (explicit | members).distinct():
        boss = supervisor_of(candidate)
        if boss is not None and boss.pk == user.pk:
            found.add(candidate.pk)
    return found


def descendant_ids(user) -> set[int]:
    """Semua bawahan (langsung dan tidak langsung), tanpa pengguna sendiri."""
    found: set[int] = set()
    frontier = {user.pk}
    for _depth in range(MAX_DEPTH):
        nxt: set[int] = set()
        for pk in frontier:
            node = get_user_model()(pk=pk)
            nxt |= direct_subordinate_ids(node)
        nxt -= found | {user.pk}
        if not nxt:
            break
        found |= nxt
        frontier = nxt
    return found


def is_ancestor(user, other) -> bool:
    """Pengguna berada di rantai atasan ``other``."""
    if user is None or other is None or user.pk == other.pk:
        return False
    current = other
    seen = {other.pk}
    for _depth in range(MAX_DEPTH):
        current = supervisor_of(current)
        if current is None or current.pk in seen:
            return False
        if current.pk == user.pk:
            return True
        seen.add(current.pk)
    return False


def position_of(user) -> str:
    """Jabatan untuk ditampilkan: dari profil, atau diturunkan dari Korwil."""
    profile = OfficerProfile.objects.filter(user=user).first()
    if profile and profile.position:
        return profile.position
    led = Korwil.objects.filter(coordinator=user, is_active=True).order_by("code")
    if led.exists():
        return _("Koordinator Korwil %(codes)s") % {
            "codes": ", ".join(led.values_list("code", flat=True))
        }
    if Korwil.objects.filter(members=user, is_active=True).exists():
        return _("Petugas lapangan")
    return ""
