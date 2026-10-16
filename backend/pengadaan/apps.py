from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PengadaanConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "pengadaan"
    verbose_name = _("Land acquisition")

    def ready(self):
        from pengadaan import signals  # noqa: F401
