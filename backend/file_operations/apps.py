from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class FileOperationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "file_operations"
    verbose_name = _("File operations")
