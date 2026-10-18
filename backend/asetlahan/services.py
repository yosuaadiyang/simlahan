"""Notifikasi (surel & WhatsApp) dan tautan modul aset lahan."""

import logging
import re

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

LOG = logging.getLogger(__name__)


def app_url(path: str = "") -> str:
    base = (getattr(settings, "OFFICER_UI_URL", "") or "").rstrip("/")
    return f"{base}/{path.lstrip('/')}" if base else f"/{path.lstrip('/')}"


def admin_url(path: str = "") -> str:
    return app_url(f"admin/asetlahan/{path.lstrip('/')}")


def send_email(recipients, subject: str, body: str) -> bool:
    """Kirim surel; kegagalan SMTP dicatat dan tidak menggagalkan proses."""
    recipients = sorted({r.strip() for r in recipients if r and r.strip()})
    if not recipients:
        return False
    try:
        send_mail(
            subject=f"[{settings.ORGANIZATION_NAME}] {subject}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception:  # noqa: BLE001
        LOG.exception("Gagal mengirim surel ke %s", ", ".join(recipients))
        return False
    return True


def normalize_phone(phone: str) -> str:
    """Nomor Indonesia ke format internasional tanpa '+', mis. 0812… → 62812…."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("8"):
        digits = "62" + digits
    return digits if 9 <= len(digits) <= 15 else ""


def whatsapp_enabled() -> bool:
    return bool(settings.WHATSAPP_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID)


def send_whatsapp(phone: str, text: str) -> bool:
    """Kirim pesan teks lewat WhatsApp Cloud API bila dikonfigurasi.

    Catatan: di luar jendela 24 jam percakapan, Meta hanya mengizinkan pesan
    templat; pesan teks biasa akan ditolak dan kegagalan dicatat di log.
    """
    number = normalize_phone(phone)
    if not number or not whatsapp_enabled():
        return False
    url = (
        f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )
    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"},
            json={
                "messaging_product": "whatsapp",
                "to": number,
                "type": "text",
                "text": {"preview_url": False, "body": text[:4000]},
            },
            timeout=15,
        )
    except requests.RequestException:
        LOG.exception("Gagal mengirim WhatsApp ke %s", number)
        return False
    if response.status_code >= 400:
        LOG.warning(
            "WhatsApp ditolak (%s): %s", response.status_code, response.text[:300]
        )
        return False
    return True


def notify_contact(
    *, email: str = "", phone: str = "", subject: str, body: str
) -> bool:
    sent_email = send_email([email], subject, body) if email else False
    sent_wa = send_whatsapp(phone, f"{subject}\n\n{body}") if phone else False
    return sent_email or sent_wa


def group_emails(*group_ids) -> list[str]:
    User = get_user_model()
    return list(
        User.objects.filter(is_active=True, groups__id__in=group_ids)
        .exclude(email="")
        .values_list("email", flat=True)
        .distinct()
    )
