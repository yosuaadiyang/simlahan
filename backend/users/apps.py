from django.apps import AppConfig
from django.contrib.auth import user_logged_in
from django.utils.translation import gettext_lazy as _


class UsersConfig(AppConfig):
    name = "users"
    verbose_name = _("Users")

    def ready(self):
        from . import branding, signals

        branding.apply()

        user_logged_in.connect(
            signals.user_logged_in, dispatch_uid="users_signals_user_logged_in"
        )
