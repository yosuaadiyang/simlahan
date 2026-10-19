from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class LeasingConfig(AppConfig):
    name = "leasing"
    verbose_name = _("Leasing")
