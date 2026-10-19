from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BatchrunConfig(AppConfig):
    name = "batchrun"
    verbose_name = _("Batch jobs")
