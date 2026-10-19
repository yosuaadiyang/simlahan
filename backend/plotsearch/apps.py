from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PlotsearchConfig(AppConfig):
    name = "plotsearch"
    verbose_name = _("Plot search")

    def ready(self):
        import plotsearch.signals  # noqa: F401
