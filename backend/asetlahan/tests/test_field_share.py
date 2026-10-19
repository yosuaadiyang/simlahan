import datetime
import io
import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from asetlahan.models import FieldReport, MapShare

pytestmark = pytest.mark.django_db


def _photo():
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), "green").save(buffer, "JPEG")
    return SimpleUploadedFile("foto.jpg", buffer.getvalue(), content_type="image/jpeg")


def _report(asset, **extra):
    point = asset.geometry.centroid
    payload = {
        "client_id": str(uuid.uuid4()),
        "report_type": "okupasi",
        "lat": str(point.y),
        "lng": str(point.x),
        "accuracy": "14.23",
        "captured_at": timezone.now().isoformat(),
        "note": "Pagar baru",
    }
    payload.update(extra)
    return payload


def test_field_app_pages(client, field_officer, make_asset):
    make_asset()
    client.force_login(field_officer)
    page = client.get(reverse("asetlahan-field"))
    assert page.status_code == 200 and b"field-config" in page.content
    manifest = client.get(reverse("asetlahan-field-manifest")).json()
    assert manifest["start_url"] == reverse("asetlahan-field")
    worker = client.get(reverse("asetlahan-field-sw"))
    assert worker["Content-Type"].startswith("application/javascript")
    assert b"lapangan-shell-" in worker.content
    boundaries = client.get(reverse("asetlahan-field-boundaries")).json()
    assert len(boundaries["features"]) == 1


def test_field_app_requires_permission(client, lawyer):
    client.force_login(lawyer)
    assert client.get(reverse("asetlahan-field")).status_code == 403
    assert client.post(reverse("asetlahan-field-sync"), {}).status_code == 403


def test_field_app_requires_login(client, seeded):
    response = client.get(reverse("asetlahan-field"))
    assert response.status_code == 302 and "/admin/login/" in response["Location"]


def test_sync_is_idempotent_and_links_asset(client, field_officer, make_asset, units):
    asset = make_asset(service_unit=units[0])
    client.force_login(field_officer)
    payload = _report(asset)
    first = client.post(reverse("asetlahan-field-sync"), {**payload, "photo": _photo()})
    assert first.status_code == 201, first.content
    again = client.post(reverse("asetlahan-field-sync"), payload)
    assert again.status_code == 200 and again.json()["duplicate"] is True
    report = FieldReport.objects.get()
    assert report.asset == asset and report.service_unit == units[0]
    assert report.reported_by == field_officer
    assert report.photo and str(report.accuracy_m) == "14.2"


def test_sync_validates_payload(client, field_officer, make_asset):
    client.force_login(field_officer)
    asset = make_asset()
    bad = _report(asset, client_id="x", lat="200", report_type="lain")
    response = client.post(reverse("asetlahan-field-sync"), bad)
    assert response.status_code == 400
    assert set(response.json()["errors"]) == {"client_id", "location", "report_type"}
    future = _report(
        asset, captured_at=(timezone.now() + datetime.timedelta(days=3)).isoformat()
    )
    assert client.post(reverse("asetlahan-field-sync"), future).status_code == 201
    assert FieldReport.objects.get().captured_at <= timezone.now() + datetime.timedelta(
        minutes=11
    )


def test_shared_map_hides_owner_names_unless_allowed(client, make_asset):
    asset = make_asset(registered_owner="Budi Pemilik")
    share = MapShare.objects.create(title="Rapat")
    share.assets.add(asset)
    page = client.get(reverse("asetlahan-share", args=[share.token]))
    assert page.status_code == 200 and page["X-Robots-Tag"] == "noindex, nofollow"
    data = client.get(reverse("asetlahan-share-data", args=[share.token])).json()
    assert "Budi Pemilik" not in str(data)
    MapShare.objects.filter(pk=share.pk).update(show_owner_names=True)
    data = client.get(reverse("asetlahan-share-data", args=[share.token])).json()
    assert "Budi Pemilik" in str(data)
    share.refresh_from_db()
    assert share.view_count == 1


def test_expired_or_inactive_share_is_gone(client, make_asset):
    share = MapShare.objects.create(
        title="Lama", expires_at=timezone.now() - datetime.timedelta(minutes=1)
    )
    assert client.get(reverse("asetlahan-share", args=[share.token])).status_code == 404
    share.expires_at = timezone.now() + datetime.timedelta(days=1)
    share.is_active = False
    share.save()
    assert (
        client.get(reverse("asetlahan-share-data", args=[share.token])).status_code
        == 404
    )
