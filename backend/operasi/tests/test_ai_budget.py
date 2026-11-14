"""Setiap jalur AI berbayar atas nama pengguna mengambil jatah AI per jam
(asetlahan.ai.take_budget) yang dihitung atomik di basis data."""

from types import SimpleNamespace

import pytest
from django.urls import reverse

from asetlahan import ai
from operasi import daily_reports, enums, services
from operasi.tests.conftest import login


@pytest.fixture
def ai_enabled(settings, monkeypatch):
    settings.ANTHROPIC_API_KEY = "uji"
    calls = []

    def fake_create(**params):
        calls.append(params)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="Draf AI")])

    monkeypatch.setattr(ai, "create", fake_create)
    return calls


def test_daily_report_compose_falls_back_when_budget_spent(
    field, ai_enabled, monkeypatch
):
    monkeypatch.setitem(ai.BUDGETS, "laporan-harian", 1)
    monkeypatch.setattr(daily_reports, "template_text", lambda *a: "Templat")
    monkeypatch.setattr(daily_reports, "materials", lambda *a: "materi")
    monkeypatch.setattr(ai, "text_of", lambda response: "Draf AI")
    first = daily_reports.compose(field, ["kegiatan"], [])
    second = daily_reports.compose(field, ["kegiatan"], [])
    assert first == ("Draf AI", True)
    assert second == ("Templat", False)
    assert len(ai_enabled) == 1


def test_komsos_stance_not_scheduled_when_budget_spent(field, ai_enabled, monkeypatch):
    scheduled = []
    monkeypatch.setattr(
        services.transaction, "on_commit", lambda fn: scheduled.append(fn)
    )
    monkeypatch.setitem(ai.BUDGETS, "sikap-komsos", 1)
    activity = SimpleNamespace(
        pk=1,
        activity_type=enums.ActivityType.KOMSOS,
        description="Warga menyampaikan dukungan penuh",
    )
    services.schedule_ai_stance(activity, field)
    services.schedule_ai_stance(activity, field)
    assert len(scheduled) == 1


def test_ai_chat_budget_is_counted_in_database(coordinator, ai_enabled):
    client = login(coordinator)
    for _ in range(20):
        ai.take_budget(coordinator, "tanya-ai", 20)
    response = client.post(reverse("operasi-ai-chat"), {"tanya": "Berapa warga?"})
    assert response.status_code == 429
    assert ai_enabled == []
