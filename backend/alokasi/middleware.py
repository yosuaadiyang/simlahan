"""Pisahkan akun pemohon dari aplikasi petugas.

Pemohon masuk lewat sesi di /portal/. Sesi yang sama tidak boleh dipakai untuk
API petugas (/v1/), admin Django, atau API yang dapat dijelajah (/auth/).
Login JWT pemohon ditolak di users.auth_views.LoginView.
"""

from django.http import JsonResponse
from django.shortcuts import redirect

OFFICER_PREFIXES = ("/v1/", "/admin/", "/auth/", "/docs", "/redoc", "/swagger")


class ApplicantIsolationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and request.path.startswith(OFFICER_PREFIXES)
            and hasattr(user, "pemohon")
        ):
            if request.path.startswith("/v1/"):
                return JsonResponse(
                    {"detail": "Akun pemohon hanya dapat dipakai di portal."},
                    status=403,
                )
            return redirect("portal:dashboard")
        return self.get_response(request)
