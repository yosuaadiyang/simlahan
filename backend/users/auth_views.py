"""Autentikasi lokal berbasis JWT (pengganti SSO Helsinki/Tunnistamo).

Alur:
  POST /v1/auth/login/     {username, password}       -> {access, refresh, user}
                                                         atau {otp_required, otp_token, email}
                                                         bila OFFICER_OTP_REQUIRED aktif
  POST /v1/auth/login/otp/ {otp_token, code}          -> {access, refresh, user}
  POST /v1/auth/refresh/   {refresh}                  -> {access, refresh}
  POST /v1/auth/logout/    {refresh}                  -> 204 (refresh token di-blacklist)
  GET  /v1/auth/me/                                   -> profil pengguna aktif
  POST /v1/auth/password/  {old_password, new_password} -> 204
"""

from django.contrib.auth import authenticate, password_validation, user_logged_in
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView

from leasing.serializers.service_unit import ServiceUnitSerializer
from users import otp
from users.models import LoginOTP


def serialize_user(user) -> dict:
    return {
        "id": user.id,
        "uuid": str(user.uuid),
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "name": user.get_display_name(),
        "email": user.email,
        "is_superuser": user.is_superuser,
        "is_staff": user.is_staff,
        "groups": [g.name for g in user.groups.all()],
        "service_units": ServiceUnitSerializer(
            user.service_units.all(), many=True
        ).data,
    }


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class LoginView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "login"

    def get_view_name(self):
        return _("Login")

    def post(self, request, format=None):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if user is None or not user.is_active:
            return Response(
                {"detail": _("Username or password is incorrect.")},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if hasattr(user, "pemohon"):
            # Akun pemohon portal alokasi lahan tidak boleh memakai aplikasi petugas.
            return Response(
                {"detail": _("Applicant accounts can only sign in at /portal/.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        if otp.required_for(user):
            try:
                challenge = otp.issue(user, LoginOTP.PURPOSE_API)
            except otp.OTPError as error:
                return Response(
                    {"detail": str(error)}, status=status.HTTP_403_FORBIDDEN
                )
            return Response(
                {
                    "otp_required": True,
                    "otp_token": str(challenge.token),
                    "email": otp.mask_email(user.email),
                }
            )
        return token_response(request, user)


def token_response(request, user) -> Response:
    # Sinkronkan unit layanan dari pemetaan grup, sama seperti login sesi.
    user_logged_in.send(sender=user.__class__, request=request, user=user)

    refresh = RefreshToken.for_user(user)
    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": serialize_user(user),
        }
    )


class LoginOTPSerializer(serializers.Serializer):
    otp_token = serializers.UUIDField()
    code = serializers.CharField(max_length=12)


class LoginOTPView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "login"

    def get_view_name(self):
        return _("Login OTP")

    def post(self, request, format=None):
        serializer = LoginOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        challenge = (
            LoginOTP.objects.select_related("user")
            .filter(
                token=serializer.validated_data["otp_token"],
                purpose=LoginOTP.PURPOSE_API,
            )
            .first()
        )
        if not otp.verify(challenge, serializer.validated_data["code"]):
            return Response(
                {"detail": _("OTP code is invalid or has expired.")},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not challenge.user.is_active:
            return Response(
                {"detail": _("Username or password is incorrect.")},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return token_response(request, challenge.user)


class TokenRefreshView(BaseTokenRefreshView):
    permission_classes = (AllowAny,)
    authentication_classes = ()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class LogoutView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get_view_name(self):
        return _("Logout")

    def post(self, request, format=None):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            # Token sudah kedaluwarsa/tidak valid: tetap anggap logout berhasil.
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_view_name(self):
        return _("Current user")

    def get(self, request, format=None):
        return Response(serialize_user(request.user))


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError(_("Old password is incorrect."))
        return value

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.context["request"].user)
        return value


class PasswordChangeView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "login"

    def get_view_name(self):
        return _("Change password")

    def post(self, request, format=None):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response(status=status.HTTP_204_NO_CONTENT)
