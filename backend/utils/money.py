"""Pemeriksaan batas nilai desimal hasil hitungan sebelum disimpan.

Nilai seperti total penilaian (jumlah komponen) atau nilai tanah (harga/m² ×
luas) dihitung otomatis. Bila hasilnya melebihi kapasitas kolom basis data,
penyimpanan gagal dengan galat server; periksa lebih dulu dan beri pesan yang
jelas kepada pengguna (biasanya karena salah ketik angka).
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


def field_limit(model, field_name: str) -> Decimal:
    field = model._meta.get_field(field_name)
    return Decimal(10) ** (field.max_digits - field.decimal_places)


def fits(model, field_name: str, value) -> bool:
    return value is None or abs(Decimal(value)) < field_limit(model, field_name)


def _first_upper(text: str) -> str:
    return text[:1].upper() + text[1:]


def too_large_message(model, field_name: str) -> str:
    field = model._meta.get_field(field_name)
    return _(
        "%(field)s hasil perhitungan terlalu besar (maksimal %(digits)s digit "
        "sebelum koma). Periksa kembali angka yang diisi."
    ) % {
        "field": _first_upper(str(field.verbose_name)),
        "digits": field.max_digits - field.decimal_places,
    }


def check_fits(model, field_name: str, value, error_key=None) -> None:
    """ValidationError bila ``value`` tidak muat di kolom ``field_name``."""
    if not fits(model, field_name, value):
        message = too_large_message(model, field_name)
        raise ValidationError({error_key: message} if error_key else message)
