"""Alamat pada catatan audit tidak bisa dipalsukan lewat X-Forwarded-For."""

import datetime

import pytest
from auditlog.models import LogEntry
from django.http import HttpResponse
from django.test import RequestFactory

from utils.middleware import CustomAuditlogMiddleware

FORGED = "203.0.113.9"


def _request(xff=None, remote="10.0.0.2"):
    extra = {"REMOTE_ADDR": remote}
    if xff is not None:
        extra["HTTP_X_FORWARDED_FOR"] = xff
    return RequestFactory().get("/", **extra)


def test_without_trusted_proxy_uses_peer_address(settings):
    settings.TRUST_PROXY_HEADERS = False
    request = _request(xff=f"{FORGED}, 198.51.100.7")
    assert CustomAuditlogMiddleware._get_remote_addr(request) == "10.0.0.2"


def test_behind_trusted_proxy_uses_proxy_appended_hop(settings):
    settings.TRUST_PROXY_HEADERS = True
    settings.TRUSTED_PROXY_COUNT = 1
    # Klien mengirim XFF palsu; nginx menambahkan alamat klien sebenarnya.
    request = _request(xff=f"{FORGED}, 198.51.100.7")
    assert CustomAuditlogMiddleware._get_remote_addr(request) == "198.51.100.7"
    assert CustomAuditlogMiddleware._get_remote_addr(_request()) == "10.0.0.2"


def test_disabled_remote_addr_setting_is_respected(settings):
    settings.AUDITLOG_DISABLE_REMOTE_ADDR = True
    assert CustomAuditlogMiddleware._get_remote_addr(_request(xff=FORGED)) is None


@pytest.mark.django_db
def test_log_entry_records_trusted_address(settings, admin_user):
    from pengadaan.models import Holiday

    settings.TRUST_PROXY_HEADERS = True
    settings.TRUSTED_PROXY_COUNT = 1

    def view(request):
        Holiday.objects.create(date=datetime.date(2026, 12, 31), name="Uji")
        return HttpResponse()

    request = _request(xff=f"{FORGED}, 198.51.100.7")
    request.user = admin_user
    CustomAuditlogMiddleware(view)(request)
    entry = LogEntry.objects.get(object_repr__contains="Uji")
    assert entry.remote_addr == "198.51.100.7"
