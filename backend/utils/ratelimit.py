"""Kuota atomik berbasis baris basis data.

``consume(key, limit, seconds)`` mengambil satu jatah dari jendela waktu
tetap: pembaruan bersyarat ``UPDATE ... WHERE count < limit`` dijalankan
basis data secara atomik, sehingga permintaan serentak tidak bisa melewati
batas (berbeda dengan ``cache.get`` lalu ``cache.set``).

Catatan: penghitung ikut transaksi pemanggil. Panggil di luar blok
``transaction.atomic`` yang bisa dibatalkan setelah pemanggilan berbayar, atau
terima bahwa jatah dikembalikan bila transaksi dibatalkan.
"""

import datetime
import hashlib
import random

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from utils.models import RateCounter

_CLEANUP_PROBABILITY = 0.01


MAX_KEY_LENGTH = 200


def _key(key: str) -> str:
    if len(key) <= MAX_KEY_LENGTH:
        return key
    digest = hashlib.sha256(key.encode()).hexdigest()
    return f"{key[: MAX_KEY_LENGTH - 65]}:{digest}"


def throttled(key: str, limit: int, seconds: int) -> bool:
    """``True`` bila batas percobaan ``key`` di jendela ini sudah tercapai;
    bila belum, satu percobaan dicatat (atomik)."""
    return not consume(key, limit, seconds)


def consume(key: str, limit: int, seconds: int) -> bool:
    """Ambil satu jatah; ``False`` bila jatah jendela ini sudah habis."""
    if limit <= 0:
        return False
    key = _key(key)
    now = timezone.now()
    expires = now + datetime.timedelta(seconds=seconds)
    with transaction.atomic():
        counter = _get_or_create(key, expires)
        # Jendela kedaluwarsa: mulai lagi. Baris yang sedang diperbarui
        # transaksi lain dikunci, lalu syaratnya dievaluasi ulang.
        RateCounter.objects.filter(pk=counter.pk, expires_at__lte=now).update(
            count=0, expires_at=expires
        )
        taken = RateCounter.objects.filter(pk=counter.pk, count__lt=limit).update(
            count=F("count") + 1
        )
    if random.random() < _CLEANUP_PROBABILITY:  # noqa: S311 - bukan kriptografi
        RateCounter.objects.filter(
            expires_at__lt=now - datetime.timedelta(days=1)
        ).delete()
    return taken == 1


def failures(key: str) -> int:
    """Jumlah jatah terpakai di jendela yang masih berlaku (tanpa mencatat)."""
    counter = RateCounter.objects.filter(
        key=_key(key), expires_at__gt=timezone.now()
    ).first()
    return counter.count if counter else 0


def refund(key: str) -> None:
    """Kembalikan satu jatah yang dipesan tetapi tidak dipakai."""
    RateCounter.objects.filter(
        key=_key(key), count__gt=0, expires_at__gt=timezone.now()
    ).update(count=F("count") - 1)


def reset(key: str) -> None:
    RateCounter.objects.filter(key=_key(key)).delete()


def _get_or_create(key: str, expires) -> RateCounter:
    try:
        with transaction.atomic():
            return RateCounter.objects.get_or_create(
                key=key, defaults={"count": 0, "expires_at": expires}
            )[0]
    except IntegrityError:
        return RateCounter.objects.get(key=key)
