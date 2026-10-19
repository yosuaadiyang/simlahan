"""OAuth2 untuk integrasi aplikasi lain (ERP, GIS, dasbor) lewat API /v1/.

Aplikasi didaftarkan admin di /admin/oauth2_provider/application/. Untuk grant
*client credentials*, setiap aplikasi wajib dikaitkan dengan akun layanan
(field "User"): izin grup dan unit layanan akun itulah yang berlaku. Token
dengan scope ``read`` saja hanya boleh membaca; mengubah data perlu ``write``.
"""

from django.utils.translation import gettext as _
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework import exceptions
from rest_framework.permissions import SAFE_METHODS


class OAuth2ServiceAuthentication(OAuth2Authentication):
    def authenticate(self, request):
        # Hanya token di header Authorization yang diterima. Tanpa itu jangan
        # memeriksa apa pun: oauthlib membaca isi permintaan, sehingga unggahan
        # tanpa autentikasi akan diurai (dan bisa gagal) sebelum ditolak 401.
        if not request.META.get("HTTP_AUTHORIZATION", "").lower().startswith(
            "bearer "
        ):
            return None
        result = super().authenticate(request)
        if result is None:
            return None
        user, token = result
        if user is None:
            # Token client credentials: bertindak sebagai akun layanan aplikasi.
            user = token.application.user if token.application_id else None
        if user is None or not user.is_active:
            raise exceptions.AuthenticationFailed(
                _("OAuth application has no active service account.")
            )
        if hasattr(user, "pemohon"):
            raise exceptions.AuthenticationFailed(
                _("Applicant accounts can only sign in at /portal/.")
            )
        if request.method not in SAFE_METHODS and not token.allow_scopes(["write"]):
            raise exceptions.PermissionDenied(
                _("This token is read-only (scope 'write' is required).")
            )
        return user, token
