from django.utils.translation import gettext as _
from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication

from users import otp


class OfficerTokenAuthentication(TokenAuthentication):
    """Token statis DRF (``Authorization: Token <key>``) dengan aturan yang sama
    seperti pintu masuk API lain.

    - Akun pemohon hanya boleh masuk lewat /portal/.
    - Token statis tidak melewati OTP. Bila OTP petugas diwajibkan
      (OFFICER_OTP_REQUIRED), token ini ditolak; integrasi memakai aplikasi
      OAuth2 dengan akun layanan.
    """

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if hasattr(user, "pemohon"):
            raise exceptions.AuthenticationFailed(
                _("Applicant accounts can only sign in at /portal/.")
            )
        if otp.required_for(user):
            raise exceptions.AuthenticationFailed(
                _(
                    "Static API tokens are disabled while officer OTP is "
                    "required. Use an OAuth2 application instead."
                )
            )
        return user, token
