"""OTP surel untuk petugas (aplikasi petugas berbasis JWT dan panel /admin/).

Aktif bila ``OFFICER_OTP_REQUIRED=True``. Akun pemohon portal tidak terkena
OTP. Kode 6 digit berlaku ``OTP_TTL_MINUTES`` menit, maksimal
``MAX_ATTEMPTS`` kali salah, dan hanya hash-nya yang disimpan.
"""

import datetime
import hashlib
import hmac
import logging
import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.translation import gettext as _

from users.models import LoginOTP

LOG = logging.getLogger(__name__)

OTP_TTL_MINUTES = 10
MAX_ATTEMPTS = 5
RESEND_SECONDS = 60
SESSION_KEY = "otp_verified_user"


def required_for(user) -> bool:
    return bool(
        getattr(settings, "OFFICER_OTP_REQUIRED", False)
        and user.is_authenticated
        and not hasattr(user, "pemohon")
    )


def _hash(code: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(), code.encode(), hashlib.sha256
    ).hexdigest()


def mask_email(email: str) -> str:
    name, _sep, domain = (email or "").partition("@")
    if not domain:
        return ""
    return f"{name[:1]}{'*' * max(len(name) - 1, 2)}@{domain}"


class OTPError(Exception):
    pass


def issue(user, purpose: str) -> LoginOTP:
    """Buat & kirim kode baru. Kode lama untuk tujuan yang sama dibatalkan."""
    if not user.email:
        raise OTPError(
            _(
                "Akun ini belum memiliki alamat surel untuk menerima kode OTP. Hubungi administrator."
            )
        )
    recent = LoginOTP.objects.filter(
        user=user,
        purpose=purpose,
        used_at__isnull=True,
        created_at__gt=timezone.now() - datetime.timedelta(seconds=RESEND_SECONDS),
    ).first()
    if recent is not None:
        return recent
    LoginOTP.objects.filter(user=user, purpose=purpose, used_at__isnull=True).update(
        used_at=timezone.now()
    )
    code = f"{secrets.randbelow(1_000_000):06d}"
    otp = LoginOTP.objects.create(
        user=user,
        purpose=purpose,
        code_hash=_hash(code),
        expires_at=timezone.now() + datetime.timedelta(minutes=OTP_TTL_MINUTES),
    )
    try:
        # Kode sengaja tidak diletakkan di subjek: subjek surel tampil di daftar
        # notifikasi/preview klien surel dan bisa terbaca orang lain.
        send_mail(
            subject=_("Kode masuk %(app)s") % {"app": settings.ORGANIZATION_NAME},
            message=_(
                "Kode masuk Anda: %(code)s\n\nKode berlaku %(minutes)d menit. Abaikan surel ini bila Anda tidak "
                "sedang masuk, dan segera ganti kata sandi Anda."
            )
            % {"code": code, "minutes": OTP_TTL_MINUTES},
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )
    except Exception:  # noqa: BLE001
        LOG.exception("Gagal mengirim OTP ke pengguna %s", user.pk)
        otp.delete()
        raise OTPError(
            _("Kode OTP tidak dapat dikirim. Coba lagi atau hubungi administrator.")
        )
    return otp


def verify(otp: LoginOTP | None, code: str) -> bool:
    """Periksa kode; kode benar dipakai sekali."""
    if (
        otp is None
        or otp.used_at is not None
        or otp.expires_at <= timezone.now()
        or otp.attempts >= MAX_ATTEMPTS
    ):
        return False
    if hmac.compare_digest(otp.code_hash, _hash((code or "").strip())):
        otp.used_at = timezone.now()
        otp.save(update_fields=["used_at"])
        return True
    otp.attempts += 1
    otp.save(update_fields=["attempts"])
    return False
