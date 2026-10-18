from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AlokasiConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "alokasi"
    verbose_name = _("Alokasi lahan")

    def ready(self):
        from alokasi import signals  # noqa: F401
