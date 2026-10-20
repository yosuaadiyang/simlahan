"""Angka desimal di panel admin ditampilkan dengan pemisah ribuan.

Bawaan Django menampilkan kolom desimal tanpa pemisah ribuan
("987654321987654321,99"), sehingga nominal besar sulit dibaca. Pemisah
ribuan global (USE_THOUSAND_SEPARATOR) tidak dipakai karena juga mengubah
bilangan bulat seperti tahun ("2.026") dan id di templat.
"""

from django.contrib.admin import helpers
from django.contrib.admin import utils as admin_utils
from django.contrib.admin.templatetags import admin_list
from django.db import models
from django.utils import formats

_original_display_for_field = admin_utils.display_for_field


def display_for_field(value, field, empty_value_display, avoid_link=False):
    if (
        isinstance(field, models.DecimalField)
        and not getattr(field, "flatchoices", None)
        and value not in field.empty_values
    ):
        return formats.number_format(value, field.decimal_places, force_grouping=True)
    return _original_display_for_field(
        value, field, empty_value_display, avoid_link=avoid_link
    )


def install() -> None:
    for module in (admin_utils, admin_list, helpers):
        module.display_for_field = display_for_field
