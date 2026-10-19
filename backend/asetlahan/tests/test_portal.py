import datetime
from decimal import Decimal

import pytest
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from alokasi.models import Applicant
from asetlahan import enums
from asetlahan.models import Bid, Grievance, ModuleSettings, Tender
from users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_throttle():
    cache.clear()
    yield
    cache.clear()


def _grievance_payload(**extra):
    payload = {
        "complainant_name": "Warga Rempang",
        "phone": "081234567890",
        "email": "warga@example.id",
        "subject": "Pemagaran liar",
        "description": "Ada pagar baru di tanah cadangan.",
        "location_text": "Rempang Cate",
        "website": "",
    }
    payload.update(extra)
    return payload


def test_grievance_submit_and_check(
    client, make_asset, officer, django_capture_on_commit_callbacks
):
    asset = make_asset()
    centroid = asset.geometry.centroid
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            reverse("aset_portal:grievance_create"),
            _grievance_payload(latitude=centroid.y, longitude=centroid.x),
        )
    assert response.status_code == 302
    grievance = Grievance.objects.get()
    assert grievance.channel == enums.GrievanceChannel.PORTAL
    assert grievance.asset == asset
    done = client.get(response["Location"])
    assert grievance.access_code in done.content.decode()
    # surel ke pelapor + petugas (setelah commit)
    recipients = {r for message in mail.outbox for r in message.to}
    assert "warga@example.id" in recipients
    assert officer.email in recipients

    check = client.get(
        reverse("aset_portal:grievance_check"),
        {
            "number": grievance.number.lower(),
            "access_code": grievance.access_code.lower(),
        },
    )
    assert grievance.subject in check.content.decode()
    wrong = client.get(
        reverse("aset_portal:grievance_check"),
        {"number": grievance.number, "access_code": "SALAH"},
    )
    assert "tidak ditemukan" in wrong.content.decode()


def test_grievance_map_center_not_localized(client, seeded, settings):
    # data-lat="0,87" dibaca parseFloat sebagai 0 sehingga peta pemilih lokasi
    # terbuka jauh dari wilayah kerja.
    settings.MAP_CENTER_LAT = 0.87
    settings.MAP_CENTER_LNG = 104.15
    html = client.get(reverse("aset_portal:grievance_create")).content.decode()
    assert 'data-lat="0.87"' in html and 'data-lng="104.15"' in html


def test_grievance_rejects_bots_and_missing_contact(client, seeded):
    response = client.post(
        reverse("aset_portal:grievance_create"),
        _grievance_payload(website="http://spam"),
    )
    assert response.status_code == 200
    response = client.post(
        reverse("aset_portal:grievance_create"), _grievance_payload(phone="", email="")
    )
    assert response.status_code == 200
    assert not Grievance.objects.exists()


def test_grievance_attachment_type_is_validated(client, seeded):
    bad = SimpleUploadedFile(
        "skrip.exe", b"MZ", content_type="application/octet-stream"
    )
    response = client.post(
        reverse("aset_portal:grievance_create"),
        {**_grievance_payload(), "attachment": bad},
    )
    assert response.status_code == 200
    assert not Grievance.objects.exists()


def test_grievance_update_notifies_complainant(seeded):
    from asetlahan.portal_views import notify_grievance_update

    grievance = Grievance.objects.create(
        complainant_name="A", email="a@example.id", subject="S", description="D"
    )
    grievance.status = enums.GrievanceStatus.RESOLVED
    grievance.response = "Pagar sudah dibongkar."
    grievance.save()
    assert notify_grievance_update(grievance) is True
    assert "Pagar sudah dibongkar." in mail.outbox[-1].body
    assert mail.outbox[-1].to == ["a@example.id"]


def test_portal_pages_follow_module_flags(client, seeded):
    assert client.get(reverse("aset_portal:tender_list")).status_code == 200
    home = client.get(reverse("portal:home")).content.decode()
    assert reverse("aset_portal:grievance_create") in home
    config = ModuleSettings.load()
    config.enable_grievance = False
    config.enable_tender = False
    config.save()
    assert client.get(reverse("aset_portal:grievance_create")).status_code == 404
    assert client.get(reverse("aset_portal:tender_list")).status_code == 404
    home = client.get(reverse("portal:home")).content.decode()
    assert reverse("aset_portal:grievance_create") not in home


@pytest.fixture
def open_tender(make_asset):
    now = timezone.now()
    return Tender.objects.create(
        title="Dermaga nelayan",
        description="Pemanfaatan dermaga",
        asset=make_asset(),
        reserve_price=Decimal("1000000"),
        open_at=now - datetime.timedelta(hours=1),
        close_at=now + datetime.timedelta(days=3),
        status=enums.TenderStatus.ANNOUNCED,
    )


@pytest.fixture
def applicant_client(client, seeded):
    user = User.objects.create_user(
        username="pemohon@example.id",
        email="pemohon@example.id",
        password="RahasiaKuat123!",
    )
    Applicant.objects.create(
        user=user, name="PT Contoh", pic_name="Budi", phone="0812", address="Batam"
    )
    client.force_login(user)
    return client


def test_draft_tender_is_hidden(client, open_tender):
    open_tender.status = enums.TenderStatus.DRAFT
    open_tender.save()
    assert (
        client.get(
            reverse("aset_portal:tender_detail", args=[open_tender.number])
        ).status_code
        == 404
    )
    assert (
        open_tender.number
        not in client.get(reverse("aset_portal:tender_list")).content.decode()
    )


def test_bid_requires_applicant_login(client, open_tender):
    response = client.get(reverse("aset_portal:bid_submit", args=[open_tender.number]))
    assert response.status_code == 302 and "/portal/masuk/" in response["Location"]


def test_applicant_submits_and_updates_bid(applicant_client, open_tender):
    url = reverse("aset_portal:bid_submit", args=[open_tender.number])
    form = applicant_client.get(url)
    assert form.status_code == 200
    payload = {
        "bidder_name": "PT Contoh",
        "email": "pemohon@example.id",
        "phone": "0812",
        "amount": "900000",
    }
    response = applicant_client.post(url, payload)
    assert response.status_code == 200  # di bawah nilai limit
    assert not Bid.objects.exists()
    response = applicant_client.post(url, {**payload, "amount": "1500000"})
    assert response.status_code == 302
    response = applicant_client.post(url, {**payload, "amount": "1750000"})
    assert response.status_code == 302
    bid = Bid.objects.get()
    assert bid.amount == Decimal("1750000") and bid.applicant.name == "PT Contoh"


def test_bid_rejected_after_close(applicant_client, open_tender):
    open_tender.close_at = timezone.now() - datetime.timedelta(minutes=1)
    open_tender.save()
    url = reverse("aset_portal:bid_submit", args=[open_tender.number])
    response = applicant_client.post(url, {"bidder_name": "X", "amount": "2000000"})
    assert response.status_code == 302
    assert not Bid.objects.exists()


def test_awarded_tender_shows_winner(client, open_tender):
    bid = Bid.objects.create(
        tender=open_tender, bidder_name="PT Pemenang", amount=Decimal("2000000")
    )
    open_tender.status = enums.TenderStatus.AWARDED
    open_tender.winner = bid
    open_tender.awarded_on = timezone.localdate()
    open_tender.save()
    page = client.get(
        reverse("aset_portal:tender_detail", args=[open_tender.number])
    ).content.decode()
    assert "PT Pemenang" in page
