from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DokumenConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "dokumen"
    verbose_name = _("Dokumen & perizinan")

    def ready(self):
        from dokumen import signals  # noqa: F401
