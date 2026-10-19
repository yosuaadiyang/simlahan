from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AsetLahanConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "asetlahan"
    verbose_name = _("Manajemen aset lahan")
