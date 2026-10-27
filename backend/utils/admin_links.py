"""Tautan ke objek terkait di kolom baca-saja panel admin hanya bagi yang berhak.

Django menautkan setiap ForeignKey baca-saja ke halaman ubah objeknya tanpa
memeriksa izin, sehingga peran yang tidak boleh melihat objek itu mendapat
tautan yang berujung 403 (mis. Petugas Alokasi pada akun pemohon). Bila
pengguna tidak boleh melihat objek terkait, tampilkan namanya saja.
"""

from contextvars import ContextVar

from django.contrib.admin import helpers

current_request = ContextVar("simlahan_current_request", default=None)

_original_get_admin_url = helpers.AdminReadonlyField.get_admin_url


def get_admin_url(self, remote_field, remote_obj):
    request = current_request.get()
    if request is not None:
        related_admin = self.model_admin.admin_site._registry.get(remote_field.model)
        if related_admin is None or not related_admin.has_view_or_change_permission(
            request, remote_obj
        ):
            return str(remote_obj)
    return _original_get_admin_url(self, remote_field, remote_obj)


class CurrentRequestMiddleware:
    """Simpan permintaan aktif selama view dan templatnya dirender."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = current_request.set(request)
        try:
            return self.get_response(request)
        finally:
            current_request.reset(token)


def install() -> None:
    helpers.AdminReadonlyField.get_admin_url = get_admin_url
