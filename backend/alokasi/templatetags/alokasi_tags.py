"""Filter templat: format rupiah, luas, dan tanggal Bahasa Indonesia."""

import datetime
from decimal import Decimal, InvalidOperation

from django import template
from django.utils import timezone

register = template.Library()

MONTHS = (
    "Januari",
    "Februari",
    "Maret",
    "April",
    "Mei",
    "Juni",
    "Juli",
    "Agustus",
    "September",
    "Oktober",
    "November",
    "Desember",
)


def _group(value: Decimal, decimals: int) -> str:
    text = f"{value:,.{decimals}f}"
    # 1,234,567.89 → 1.234.567,89
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


@register.filter
def rupiah(value) -> str:
    if value in (None, ""):
        return "-"
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    return "Rp" + _group(amount, 0)


@register.filter
def angka(value, decimals=0) -> str:
    if value in (None, ""):
        return "-"
    try:
        return _group(Decimal(value), int(decimals))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)


@register.filter
def hektare(value) -> str:
    """Luas m² sebagai hektare, contoh 125000 → '12,5 ha'."""
    if value in (None, ""):
        return "-"
    try:
        ha = Decimal(value) / Decimal(10000)
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    text = _group(ha, 2).rstrip("0").rstrip(",")
    return f"{text} ha"


@register.filter
def tanggal(value) -> str:
    if not value:
        return "-"
    if isinstance(value, datetime.datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        value = value.date()
    return f"{value.day} {MONTHS[value.month - 1]} {value.year}"


@register.filter
def bulan_ke_tahun(months) -> str:
    """Contoh: 30 → '2 tahun 6 bulan'."""
    if months in (None, ""):
        return "-"
    months = int(months)
    years, rest = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} tahun")
    if rest or not parts:
        parts.append(f"{rest} bulan")
    return " ".join(parts)
