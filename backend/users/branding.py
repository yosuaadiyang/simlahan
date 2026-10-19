"""Merek SimLahan pada panel admin: judul situs dan nama aplikasi pustaka pihak ketiga."""

from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

# Nama bawaan pustaka yang tampil sebagai judul kelompok di panel admin.
APP_LABELS = {
    "oauth2_provider": _("OAuth2 integration"),
    "django_q": _("Background tasks"),
    "rest_framework": _("REST API"),
    "django_filters": _("Data filters"),
    "django_countries": _("Countries"),
    "corsheaders": _("CORS"),
}

# Model pustaka yang tidak memberi verbose_name sendiri (nama otomatis berbahasa Inggris).
MODEL_LABELS = {
    "oauth2_provider.Application": (
        _("OAuth2 application"),
        _("OAuth2 applications"),
    ),
    "oauth2_provider.AccessToken": (_("access token"), _("access tokens")),
    "oauth2_provider.RefreshToken": (_("refresh token"), _("refresh tokens")),
    "oauth2_provider.IDToken": (_("ID token"), _("ID tokens")),
    "oauth2_provider.Grant": (_("authorization grant"), _("authorization grants")),
}


def apply():
    admin.site.site_header = format_lazy(
        _("{app} administration"), app=settings.APP_NAME
    )
    admin.site.site_title = format_lazy(_("{app} site admin"), app=settings.APP_NAME)
    for label, verbose_name in APP_LABELS.items():
        try:
            apps.get_app_config(label).verbose_name = verbose_name
        except LookupError:
            continue
    for model_label, (singular, plural) in MODEL_LABELS.items():
        try:
            options = apps.get_model(model_label)._meta
        except LookupError:
            continue
        # Hanya tampilan; original_attrs (dasar makemigrations) tidak berubah.
        options.verbose_name = singular
        options.verbose_name_plural = plural
