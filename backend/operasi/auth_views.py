"""Pintu masuk tersendiri pusat komando (/komando/masuk/ dan /komando/keluar/).

Pusat komando tidak lagi menumpang halaman masuk panel admin: petugas
lapangan dan koordinator wilayah masuk langsung di sini, seperti pemohon di
portal. Sesi yang dibuat tetap sesi peramban yang sama, jadi panel admin,
aplikasi lapangan, dan aplikasi utama (lewat /v1/auth/session/) tidak meminta
login kedua kali.
"""

import functools

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

# Halaman awal aplikasi petugas (SPA) per izin, sama dengan HOME_ROUTES di
# frontend/apps/leasing/src/root/homeRoute.ts. Pengguna tanpa satu pun izin ini
# tidak punya halaman di sana, jadi "aplikasi utama" baginya adalah panel admin.
SPA_HOME_PERMISSIONS = (
    "leasing.view_lease",
    "pengadaan.view_acquisitionproject",
    "leasing.view_contact",
    "leasing.view_areanote",
    "leasing.view_basisofrent",
    "plotsearch.view_areasearch",
)


def has_command_access(user) -> bool:
    return bool(
        user.is_authenticated
        and user.is_active
        and user.is_staff
        and user.has_perm("operasi.view_korwil")
    )


def main_app_url(user) -> str:
    """Tujuan tombol "Utama" di pusat komando."""
    if any(user.has_perm(permission) for permission in SPA_HOME_PERMISSIONS):
        return "/"
    return reverse("admin:index")


def command_login_required(view):
    """Belum masuk -> halaman masuk pusat komando; bukan petugas -> 403."""

    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path(), reverse("operasi-login"))
        if not user.is_active or not user.is_staff:
            return forbidden(request)
        return view(request, *args, **kwargs)

    return wrapper


def forbidden(request):
    return render(
        request,
        "operasi/forbidden.html",
        {"main_url": main_app_url(request.user)},
        status=403,
    )


class CommandLoginForm(AuthenticationForm):
    username = forms.CharField(
        label=_("Nama pengguna"),
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "autofocus": True,
                "autocomplete": "username",
                "autocapitalize": "none",
                "spellcheck": "false",
            }
        ),
    )
    password = forms.CharField(
        label=_("Kata sandi"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": _(
            "Nama pengguna atau kata sandi salah. Perhatikan huruf besar/kecil."
        ),
        "no_access": _(
            "Akun ini belum diberi akses pusat komando. Minta administrator "
            "menambahkan Anda ke grup Petugas Lapangan, Koordinator Wilayah, "
            "atau Petugas Aset."
        ),
        "applicant": _(
            "Akun pemohon hanya bisa masuk di portal, bukan di pusat komando."
        ),
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if hasattr(user, "pemohon"):
            raise forms.ValidationError(
                self.error_messages["applicant"], code="applicant"
            )
        if not has_command_access(user):
            raise forms.ValidationError(
                self.error_messages["no_access"], code="no_access"
            )


class CommandLoginView(auth_views.LoginView):
    """Batas percobaan masuk ditangani users.middleware.LoginThrottleMiddleware."""

    template_name = "operasi/login.html"
    authentication_form = CommandLoginForm

    def get(self, request, *args, **kwargs):
        if has_command_access(request.user):
            return redirect(self.get_success_url())
        return super().get(request, *args, **kwargs)

    def get_default_redirect_url(self):
        return reverse("operasi-command")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["app_name"] = settings.APP_NAME
        # Sudah masuk dengan akun lain (mis. pemohon portal): tampilkan siapa.
        user = self.request.user
        context["current_user"] = user if user.is_authenticated else None
        return context


@never_cache
def command_logout(request):
    """Keluar hanya lewat formulir (CSRF). Juga mencabut token aplikasi utama
    yang tersimpan di perangkat ini (dikirim oleh tombol Keluar pusat komando)."""
    if request.method != "POST":
        return redirect("operasi-command")
    refresh = request.POST.get("refresh", "")
    if refresh:
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            pass
    logout(request)
    messages.info(request, _("Anda sudah keluar dari pusat komando."))
    return redirect("operasi-login")
