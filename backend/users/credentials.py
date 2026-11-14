"""Mencabut kredensial API milik pengguna.

Dipanggil setiap kali sandi pengguna berubah (lewat sinyal di
``users.signals``), dari jalur mana pun: API ganti sandi, halaman /akun/sandi/,
admin Django, atau lupa sandi portal. Kredensial yang mungkin sudah dicuri
tidak boleh tetap berlaku setelah pemiliknya mengganti sandi.
"""

from oauth2_provider.models import AccessToken
from oauth2_provider.models import RefreshToken as OAuthRefreshToken
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)


def revoke_api_credentials(user) -> None:
    # JWT: access token ditolak lewat CHECK_REVOKE_TOKEN, refresh token masuk
    # daftar hitam.
    for token in OutstandingToken.objects.filter(
        user=user, blacklistedtoken__isnull=True
    ):
        BlacklistedToken.objects.get_or_create(token=token)
    # Token statis DRF.
    Token.objects.filter(user=user).delete()
    # OAuth2 atas nama pengguna ini (authorization code). Token client
    # credentials tidak terikat ke pengguna (user kosong) sehingga tidak
    # terpengaruh.
    for refresh in OAuthRefreshToken.objects.filter(user=user, revoked__isnull=True):
        refresh.revoke()
    AccessToken.objects.filter(user=user).delete()
