"""Halaman verifikasi OTP untuk sesi petugas (/admin/otp/)."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache

from users import otp
from users.models import LoginOTP
from utils import ratelimit

SESSION_TOKEN = "otp_session_token"
# Batas tebakan per akun lintas kode (kirim ulang membuat kode baru dengan
# jatah MAX_ATTEMPTS sendiri).
OTP_POSTS_PER_WINDOW = 10
OTP_WINDOW = 900


def _next_url(request) -> str:
    target = request.POST.get("next") or request.GET.get("next") or "/admin/"
    if url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return "/admin/"


def _challenge(request):
    token = request.session.get(SESSION_TOKEN)
    if not token:
        return None
    return LoginOTP.objects.filter(
        token=token, user=request.user, purpose=LoginOTP.PURPOSE_SESSION
    ).first()


def _send(request) -> str:
    try:
        challenge = otp.issue(request.user, LoginOTP.PURPOSE_SESSION)
    except otp.OTPError as error:
        return str(error)
    request.session[SESSION_TOKEN] = str(challenge.token)
    return ""


@never_cache
@login_required(login_url="/admin/login/")
def officer_otp(request):
    next_url = _next_url(request)
    if (
        not otp.required_for(request.user)
        or request.session.get(otp.SESSION_KEY) == request.user.pk
    ):
        return redirect(next_url)
    error = ""
    challenge = _challenge(request)
    if request.method == "POST" and request.POST.get("action") == "resend":
        error = _send(request)
    elif request.method == "POST":
        if ratelimit.throttled(
            f"users:otp-sesi:{request.user.pk}", OTP_POSTS_PER_WINDOW, OTP_WINDOW
        ):
            error = _("Terlalu banyak percobaan. Coba lagi beberapa menit lagi.")
        elif otp.verify(challenge, request.POST.get("code", "")):
            request.session[otp.SESSION_KEY] = request.user.pk
            request.session.pop(SESSION_TOKEN, None)
            return redirect(next_url)
        else:
            error = _("Kode OTP salah atau sudah kedaluwarsa.")
    elif (
        challenge is None
        or challenge.used_at is not None
        or challenge.expires_at <= timezone.now()
    ):
        error = _send(request)
    return TemplateResponse(
        request,
        "users/otp.html",
        {
            "title": _("Verifikasi OTP"),
            "email": otp.mask_email(request.user.email),
            "error": error,
            "next": next_url,
            "site_header": _("Panel petugas"),
        },
    )
