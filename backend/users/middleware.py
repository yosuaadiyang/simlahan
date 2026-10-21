"""Wajibkan OTP surel bagi petugas yang masuk lewat sesi (panel /admin/, aplikasi lapangan).

Login JWT aplikasi petugas memeriksa OTP di ``users.auth_views``; middleware
ini menangani sesi Django. Aktif hanya bila ``OFFICER_OTP_REQUIRED=True``.
"""

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.translation import gettext as _

from users import otp

EXEMPT_PREFIXES = (
    "/admin/otp/",
    "/admin/logout/",
    # Login/logout aplikasi petugas tidak memakai sesi; jangan diblokir oleh
    # sesi lama yang belum lolos OTP.
    "/v1/auth/login/",
    "/v1/auth/logout/",
    "/healthz",
    "/readiness",
)


class OfficerOTPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._needs_otp(request):
            if (
                request.path.startswith("/v1/")
                or request.headers.get("x-requested-with") == "XMLHttpRequest"
            ):
                return JsonResponse(
                    {"detail": "Verifikasi OTP diperlukan."}, status=403
                )
            return redirect(
                f"{reverse('officer-otp')}?{urlencode({'next': request.get_full_path()})}"
            )
        return self.get_response(request)

    @staticmethod
    def _needs_otp(request) -> bool:
        user = getattr(request, "user", None)
        if user is None or not otp.required_for(user):
            return False
        path = request.path
        if path.startswith(EXEMPT_PREFIXES) or path.startswith(
            (settings.STATIC_URL, settings.MEDIA_URL)
        ):
            return False
        return request.session.get(otp.SESSION_KEY) != user.pk


# Halaman login sesi (panel admin & API yang dapat dijelajah). Login JWT
# /v1/auth/login/ sudah dibatasi oleh ScopedRateThrottle DRF.
SESSION_LOGIN_PATHS = ("/admin/login/", "/auth/login/")


class LoginThrottleMiddleware:
    """Batasi percobaan login sesi per alamat IP agar sandi tidak bisa ditebak."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path in SESSION_LOGIN_PATHS:
            from alokasi.views import _throttled

            if _throttled(request, "login-sesi", limit=10, window=60):
                return HttpResponse(
                    _("Terlalu banyak percobaan masuk. Coba lagi dalam satu menit."),
                    status=429,
                    content_type="text/plain; charset=utf-8",
                )
        return self.get_response(request)
