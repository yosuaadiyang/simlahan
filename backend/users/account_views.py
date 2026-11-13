"""Halaman akun petugas berbasis sesi: panduan peran dan ganti sandi.

Dibuka dari aplikasi petugas, panel admin, dan pusat komando (sesi peramban
dibuat saat login). Pemohon portal punya halaman sendiri di /portal/.
"""

import functools

from django.contrib import admin
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from users import role_guide
from utils import ratelimit

# Batas salah sandi lama per akun, agar sesi yang tertinggal terbuka tidak
# bisa dipakai menebak sandi.
MAX_FAILED_ATTEMPTS = 10
FAILED_WINDOW_SECONDS = 3600


def officer_page(view):
    @functools.wraps(view)
    @never_cache
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect("/")
        if hasattr(user, "pemohon"):
            return redirect("portal:dashboard")
        return view(request, *args, **kwargs)

    return wrapper


def _context(request, title: str, **extra) -> dict:
    return {
        "title": title,
        "site_header": admin.site.site_header,
        "site_title": admin.site.site_title,
        # Bilah atas panel admin (tanpa menu modul) juga untuk petugas non-staf.
        "has_permission": True,
        "is_nav_sidebar_enabled": False,
        **extra,
    }


@officer_page
def guide(request):
    user = request.user
    return render(
        request,
        "users/panduan.html",
        _context(
            request,
            "Panduan peran",
            guides=role_guide.guides_for(user),
            sees_all=role_guide.sees_all(user),
            general_steps=role_guide.GENERAL_STEPS,
            admin_steps=role_guide.ADMIN_STEPS,
            groups=list(user.groups.values_list("name", flat=True)),
        ),
    )


@officer_page
def change_password(request):
    user = request.user
    key = f"akun-sandi-gagal:{user.pk}"
    # Setiap percobaan memesan satu jatah secara atomik di basis data sebelum
    # sandi lama diperiksa (get+set cache bisa dilewati permintaan serentak);
    # jatah dikembalikan bila galatnya bukan sandi lama.
    blocked = ratelimit.failures(key) >= MAX_FAILED_ATTEMPTS
    form = PasswordChangeForm(user, request.POST or None)
    done = False
    if request.method == "POST":
        blocked = ratelimit.throttled(key, MAX_FAILED_ATTEMPTS, FAILED_WINDOW_SECONDS)
    if request.method == "POST" and not blocked:
        if form.is_valid():
            form.save()
            # Kredensial API lama dicabut oleh sinyal ganti sandi
            # (users.signals); sesi peramban ini dipertahankan.
            update_session_auth_hash(request, user)
            ratelimit.reset(key)
            done = True
            form = None
        elif "old_password" in form.errors:
            blocked = ratelimit.failures(key) >= MAX_FAILED_ATTEMPTS
        else:
            ratelimit.refund(key)
    return render(
        request,
        "users/sandi.html",
        _context(request, "Ganti sandi", form=form, done=done, blocked=blocked),
        status=429 if blocked and request.method == "POST" else 200,
    )
