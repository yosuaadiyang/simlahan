import datetime
import io
from decimal import Decimal

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from asetlahan.models import (
    Advocate,
    CaseHearing,
    LegalCase,
    ModuleSettings,
    Task,
    TaxObligation,
)
from asetlahan.setup import ensure_reminder_job

pytestmark = pytest.mark.django_db


@pytest.fixture
def due_items(make_asset, officer, lawyer):
    asset = make_asset(
        responsible=officer,
        title_expiry=timezone.localdate() + datetime.timedelta(days=10),
    )
    TaxObligation.objects.create(
        asset=asset, amount=Decimal("100"), due_date=timezone.localdate()
    )
    case = LegalCase.objects.create(
        title="Gugatan", opposing_party="P", responsible=lawyer
    )
    case.advocates.add(
        Advocate.objects.create(name="Advokat", email="advokat@example.id")
    )
    hearing = CaseHearing.objects.create(
        case=case,
        agenda="Pembuktian",
        scheduled_at=timezone.now() + datetime.timedelta(days=2),
    )
    Task.objects.create(
        title="Terlambat",
        assignee=officer,
        due_date=timezone.localdate() - datetime.timedelta(days=1),
    )
    return hearing


def test_reminder_dry_run_lists_without_sending(due_items):
    out = io.StringIO()
    call_command("asetlahan_pengingat", stdout=out)
    text = out.getvalue()
    for tag in ("[HAK BERAKHIR]", "[PAJAK]", "[SIDANG]", "[TUGAS TERLAMBAT]"):
        assert tag in text
    assert mail.outbox == []
    due_items.refresh_from_db()
    assert due_items.reminder_sent_at is None


def test_reminder_sends_personal_summary_and_hearing_once(due_items, officer, lawyer):
    call_command("asetlahan_pengingat", "--email", stdout=io.StringIO())
    recipients = [tuple(m.to) for m in mail.outbox]
    assert (officer.email,) in recipients
    assert (lawyer.email,) in recipients
    assert ("advokat@example.id",) in recipients
    due_items.refresh_from_db()
    assert due_items.reminder_sent_at is not None
    mail.outbox.clear()
    call_command("asetlahan_pengingat", "--email", stdout=io.StringIO())
    assert ("advokat@example.id",) not in [tuple(m.to) for m in mail.outbox]


def test_reminder_respects_disabled_modules(due_items):
    config = ModuleSettings.load()
    config.enable_litigation = False
    config.enable_tasks = False
    config.save()
    out = io.StringIO()
    call_command("asetlahan_pengingat", stdout=out)
    assert (
        "[SIDANG]" not in out.getvalue() and "[TUGAS TERLAMBAT]" not in out.getvalue()
    )


def test_reminder_job_is_scheduled_once(seeded):
    assert ensure_reminder_job() is True
    assert ensure_reminder_job() is False


def test_api_lists_scoped_assets_as_geojson(officer, make_asset, units):
    make_asset(service_unit=units[0], code="AST-MILIK")
    make_asset(service_unit=units[1], code="AST-LAIN")
    api = APIClient()
    api.force_authenticate(officer)
    response = api.get("/v1/aset/asset/")
    assert response.status_code == 200
    codes = [row["code"] for row in response.json()["results"]]
    assert codes == ["AST-MILIK"]
    assert response.json()["results"][0]["geometry"]["type"] == "MultiPolygon"


def test_api_requires_view_permission_and_enabled_module(field_officer, officer):
    api = APIClient()
    api.force_authenticate(field_officer)
    assert api.get("/v1/aset/transaction/").status_code == 403
    api.force_authenticate(officer)
    assert api.get("/v1/aset/tender/").status_code == 200
    config = ModuleSettings.load()
    config.enable_tender = False
    config.save()
    assert api.get("/v1/aset/tender/").status_code == 404
    assert "access_code" not in str(api.get("/v1/aset/grievance/").json())


def test_api_rejects_anonymous(seeded):
    assert APIClient().get("/v1/aset/asset/").status_code == 401
