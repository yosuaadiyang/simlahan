"""Validator OAuth2 server: grant yang melewati OTP petugas ditolak."""

from oauth2_provider.oauth2_validators import OAuth2Validator


class OfficerOAuth2Validator(OAuth2Validator):
    """Hanya grant yang tidak melewati OTP petugas.

    Grant *password* (ROPC) menukar nama akun + sandi langsung menjadi token,
    melewati OTP surel yang wajib bagi sesi dan login JWT petugas. Implicit
    mengirim token lewat URL. Keduanya ditolak walau aplikasi didaftarkan
    dengan grant tersebut; gunakan authorization code (+PKCE) atau client
    credentials.
    """

    BLOCKED_GRANT_TYPES = frozenset({"password"})
    BLOCKED_RESPONSE_TYPES = frozenset({"token", "id_token", "id_token token"})

    def validate_grant_type(
        self, client_id, grant_type, client, request, *args, **kwargs
    ):
        if grant_type in self.BLOCKED_GRANT_TYPES:
            return False
        return super().validate_grant_type(
            client_id, grant_type, client, request, *args, **kwargs
        )

    def validate_response_type(
        self, client_id, response_type, client, request, *args, **kwargs
    ):
        if response_type in self.BLOCKED_RESPONSE_TYPES:
            return False
        return super().validate_response_type(
            client_id, response_type, client, request, *args, **kwargs
        )
