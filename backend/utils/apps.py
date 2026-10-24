from django.apps import AppConfig, apps


def _freeze_constraint_fields():
    """django-modeltranslation menambah UniqueConstraint per bahasa dengan
    ``fields`` berupa list; DRF memakai ``constraint.fields`` sebagai kunci
    dict sehingga setiap POST ke serializer model tersebut gagal 500
    (``unhashable type: 'list'``). Samakan dengan Django (tuple)."""
    for model in apps.get_models():
        for constraint in model._meta.constraints:
            fields = getattr(constraint, "fields", None)
            if isinstance(fields, list):
                constraint.fields = tuple(fields)


class UtilsConfig(AppConfig):
    name = "utils"

    def ready(self):
        from utils.admin_numbers import install

        install()
        _freeze_constraint_fields()
