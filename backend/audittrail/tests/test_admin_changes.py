"""Tabel perubahan log audit di panel admin memakai nilai berbahasa Indonesia."""

import pytest
from auditlog.models import LogEntry
from django.urls import reverse

from operasi.models import CommandSettings


@pytest.mark.django_db
def test_change_table_shows_readable_values(admin_client):
    settings = CommandSettings.load()
    settings.enforce_geofence = not settings.enforce_geofence
    settings.save()
    entry = LogEntry.objects.get_for_object(settings).order_by("-pk").first()
    assert entry is not None

    page = admin_client.get(
        reverse("admin:auditlog_logentry_change", args=[entry.pk])
    ).content.decode()
    assert "<td>None</td>" not in page
    assert "<td>False</td>" not in page and "<td>True</td>" not in page

    listing = admin_client.get(reverse("admin:auditlog_logentry_changelist"))
    assert " perubahan: " in listing.content.decode()
    assert " change: " not in listing.content.decode()
