"""Alamat IP klien di belakang reverse proxy tepercaya."""

from django.conf import settings


def client_ip(request) -> str:
    """Alamat klien untuk kuota dan catatan audit.

    Di belakang reverse proxy, REMOTE_ADDR selalu alamat proxy. Setiap proxy
    tepercaya menambahkan satu alamat di ujung X-Forwarded-For, jadi alamat
    klien ada di posisi ke-N dari belakang (N = TRUSTED_PROXY_COUNT). Entri di
    depannya dikirim klien sendiri dan bisa dipalsukan.
    """
    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        hops = max(getattr(settings, "TRUSTED_PROXY_COUNT", 1), 1)
        forwarded = [
            part.strip()
            for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
            if part.strip()
        ]
        if forwarded:
            return forwarded[-min(hops, len(forwarded))]
    return request.META.get("REMOTE_ADDR", "")
