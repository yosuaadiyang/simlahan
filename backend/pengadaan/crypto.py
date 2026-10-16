"""Enkripsi data pribadi (NIK, nomor rekening) sesuai prinsip UU No. 27/2022 (PDP).

Nilai disimpan terenkripsi (Fernet / AES-128-CBC + HMAC-SHA256). Untuk pencarian
NIK disimpan pula sidik jari HMAC-SHA256 (tidak bisa dibalik).

Kunci diambil dari setting FIELD_ENCRYPTION_KEY (base64 urlsafe 32 byte, buat
dengan ``python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"``).
Jika kosong (hanya untuk pengembangan), kunci diturunkan dari SECRET_KEY.
"""

import base64
import hashlib
import hmac
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

PREFIX = "enc$"


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or ""
    if not key:
        digest = hashlib.sha256(
            ("field-encryption:" + settings.SECRET_KEY).encode()
        ).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(value: str | None) -> str | None:
    if value in (None, ""):
        return value
    if isinstance(value, str) and value.startswith(PREFIX):
        return value
    token = _fernet().encrypt(str(value).encode()).decode()
    return PREFIX + token


def decrypt(value: str | None) -> str | None:
    if value in (None, ""):
        return value
    if not value.startswith(PREFIX):
        # Data lama/tidak terenkripsi dikembalikan apa adanya.
        return value
    try:
        return _fernet().decrypt(value[len(PREFIX) :].encode()).decode()
    except InvalidToken:
        return None


def fingerprint(value: str | None) -> str | None:
    """HMAC-SHA256 dari nilai yang dinormalisasi; untuk pencarian persis."""
    if not value:
        return None
    normalized = "".join(ch for ch in str(value) if ch.isalnum()).upper()
    secret = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or settings.SECRET_KEY
    key = (secret + ":fingerprint").encode()
    return hmac.new(key, normalized.encode(), hashlib.sha256).hexdigest()


def mask(value: str | None, visible_start: int = 4, visible_end: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= visible_start + visible_end:
        return "*" * len(value)
    return (
        value[:visible_start]
        + "*" * (len(value) - visible_start - visible_end)
        + value[-visible_end:]
    )


class EncryptedCharField(models.TextField):
    """TextField yang menyimpan nilai terenkripsi dan mengembalikan teks asli."""

    description = "Encrypted text"

    def from_db_value(self, value, expression, connection):
        return decrypt(value)

    def to_python(self, value):
        if isinstance(value, str) and value.startswith(PREFIX):
            return decrypt(value)
        return value

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return encrypt(value)
