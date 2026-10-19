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
