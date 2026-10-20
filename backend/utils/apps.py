from django.apps import AppConfig


class UtilsConfig(AppConfig):
    name = "utils"

    def ready(self):
        from utils.admin_numbers import install

        install()
