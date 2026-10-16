"""Perhitungan hari kerja (Senin–Jumat, di luar libur nasional & cuti bersama).

Batas waktu dalam UU 2/2012 dan PP 19/2021 umumnya dinyatakan dalam "hari kerja".
Daftar libur dikelola lewat model ``Holiday`` (dapat diperbarui admin setiap tahun
sesuai SKB 3 Menteri).
"""

import datetime
from functools import lru_cache


def _holidays_between(start: datetime.date, end: datetime.date) -> set[datetime.date]:
    from pengadaan.models import Holiday

    return set(
        Holiday.objects.filter(date__gte=start, date__lte=end).values_list(
            "date", flat=True
        )
    )


def is_workday(day: datetime.date, holidays: set[datetime.date] | None = None) -> bool:
    if day.weekday() >= 5:
        return False
    if holidays is None:
        holidays = _holidays_between(day, day)
    return day not in holidays


def add_workdays(start: datetime.date, days: int) -> datetime.date:
    """Tanggal setelah ``days`` hari kerja terhitung sejak ``start`` (hari ``start`` tidak dihitung).

    Contoh: keberatan "paling lama 14 hari kerja setelah musyawarah" →
    ``add_workdays(tanggal_musyawarah, 14)`` adalah hari terakhir pengajuan.
    """
    if days <= 0:
        return start
    # Rentang pencarian libur yang cukup longgar (libur tidak mungkin > 2x hari kerja).
    window_end = start + datetime.timedelta(days=days * 3 + 30)
    holidays = _holidays_between(start, window_end)
    current = start
    counted = 0
    while counted < days:
        current += datetime.timedelta(days=1)
        if current > window_end:
            window_end = current + datetime.timedelta(days=days * 3 + 30)
            holidays |= _holidays_between(current, window_end)
        if is_workday(current, holidays):
            counted += 1
    return current


def workdays_between(start: datetime.date, end: datetime.date) -> int:
    """Jumlah hari kerja setelah ``start`` sampai dengan ``end`` (negatif bila end < start)."""
    if end == start:
        return 0
    sign = 1
    if end < start:
        start, end = end, start
        sign = -1
    holidays = _holidays_between(start, end)
    count = 0
    current = start
    while current < end:
        current += datetime.timedelta(days=1)
        if is_workday(current, holidays):
            count += 1
    return sign * count


def add_years(start: datetime.date, years: int) -> datetime.date:
    try:
        return start.replace(year=start.year + years)
    except ValueError:
        # 29 Februari → 28 Februari
        return start.replace(year=start.year + years, day=28)


@lru_cache(maxsize=1)
def unit_labels():
    from django.utils.translation import gettext_lazy as _

    return {"workdays": _("working days"), "days": _("days"), "years": _("years")}
