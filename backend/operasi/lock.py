"""Kunci hidup sistem (deadman switch).

Saat kunci aktif dan waktunya tiba, semua permintaan dijawab halaman
"sistem dihentikan" (HTTP 503) kecuali untuk superuser yang masuk lewat
panel, halaman masuk, berkas statis, dan pemeriksaan kesehatan kontainer.
Superuser menonaktifkan kunci di pusat komando atau di panel admin dengan
kode rahasia.
"""

import datetime

from django.conf import settings
from django.db import DatabaseError
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from operasi.models import SystemLock

EXEMPT_PREFIXES = (
    "/healthz",
    "/readiness",
    "/admin/login/",
    "/admin/logout/",
    "/admin/otp/",
    "/admin/jsi18n/",
    # Masuk (termasuk OTP), perpanjang token, dan keluar aplikasi petugas agar
    # superuser tetap dapat masuk. Profil (/me/) dan ganti sandi ikut terkunci;
    # superuser melewatinya dengan token JWT-nya.
    "/v1/auth/login/",
    "/v1/auth/refresh/",
    "/v1/auth/logout/",
)


class SystemLockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not self._blocked(request):
            return self.get_response(request)
        try:
            state = SystemLock.state()
        except DatabaseError:
            # Tabel belum dimigrasi / basis data sibuk: jangan kunci aplikasi.
            return self.get_response(request)
        if SystemLock.is_locked_state(state):
            message = state.get("message") or ""
            if request.path.startswith(
                "/v1/"
            ) or "application/json" in request.headers.get("accept", ""):
                return JsonResponse({"detail": message, "locked": True}, status=503)
            response = render(
                request, "operasi/locked.html", {"message": message}, status=503
            )
            response["Retry-After"] = "3600"
            return response
        return self.get_response(request)

    @staticmethod
    def _blocked(request) -> bool:
        path = request.path
        if path.startswith(EXEMPT_PREFIXES) or path.startswith(settings.STATIC_URL):
            return False
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            return not user.is_superuser
        return not _api_superuser(request)


def _api_superuser(request) -> bool:
    """Superuser aplikasi petugas memakai token JWT yang baru dibaca DRF di view."""
    if not request.path.startswith("/v1/") or not request.headers.get(
        "authorization", ""
    ).startswith("Bearer "):
        return False
    from rest_framework_simplejwt.authentication import JWTAuthentication

    try:
        result = JWTAuthentication().authenticate(request)
    except (
        Exception
    ):  # token kedaluwarsa / tidak sah: perlakukan sebagai pengguna biasa
        return False
    return bool(result and result[0].is_superuser)


def system_lock(request):
    """Context processor: hitung mundur kunci untuk banner panel petugas."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or not user.is_staff:
        return {}
    try:
        state = SystemLock.state()
    except DatabaseError:
        return {}
    if not state.get("armed"):
        return {}
    shutdown = datetime.datetime.fromisoformat(state["shutdown_at"])
    return {
        "system_lock": {
            **state,
            "shutdown_label": timezone.localtime(shutdown).strftime("%d-%m-%Y %H:%M"),
            "passed": SystemLock.is_locked_state(state),
        }
    }
