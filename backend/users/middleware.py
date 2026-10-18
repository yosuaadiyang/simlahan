"""Wajibkan OTP surel bagi petugas yang masuk lewat sesi (panel /admin/, aplikasi lapangan).

Login JWT aplikasi petugas memeriksa OTP di ``users.auth_views``; middleware
ini menangani sesi Django. Aktif hanya bila ``OFFICER_OTP_REQUIRED=True``.
"""

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode

from users import otp

EXEMPT_PREFIXES = ("/admin/otp/", "/admin/logout/", "/healthz", "/readiness")


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
