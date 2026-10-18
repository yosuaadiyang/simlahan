import datetime
from types import SimpleNamespace

import pytest
from django.urls import reverse
from django.utils import timezone

from asetlahan import ai, assistant, enums
from asetlahan.models import EncroachmentCase, Grievance

pytestmark = pytest.mark.django_db


@pytest.fixture
def overdue_grievance(seeded):
    grievance = Grievance.objects.create(
        complainant_name="A", subject="Pagar liar", description="D"
    )
    Grievance.objects.filter(pk=grievance.pk).update(
        due_date=timezone.localdate() - datetime.timedelta(days=1)
    )
    return grievance


def test_rules_answer_without_api_key(admin, overdue_grievance, settings):
    settings.ANTHROPIC_API_KEY = ""
    result = assistant.answer(admin, "pengaduan yang lewat batas?")
    assert result["source"] == "aturan"
    assert overdue_grievance.number in str(result["tables"])


def test_rules_parse_periods():
    assert assistant._days("dalam 2 bulan", 7) == 60
    assert assistant._days("minggu depan", 1) == 7
    assert assistant._days("tanpa periode", 30) == 30


def test_rules_respect_permissions(field_officer, seeded, settings):
    settings.ANTHROPIC_API_KEY = ""
    result = assistant.answer(field_officer, "keuangan tahun ini")
    assert "tidak memiliki akses" in str(result["tables"])


def test_unmatched_question_searches(admin, make_asset, settings):
    settings.ANTHROPIC_API_KEY = ""
    asset = make_asset(name="Lahan Sembulang Hulu")
    result = assistant.answer(admin, "tolong cari sembulang")
    assert asset.code in str(result["tables"])


def _block(**kwargs):
    return SimpleNamespace(**kwargs)


def test_ai_tool_loop(monkeypatch, admin, make_asset, settings):
    settings.ANTHROPIC_API_KEY = "uji"
    asset = make_asset()
    EncroachmentCase.objects.create(
        title="Pagar", asset=asset, status=enums.EncroachmentStatus.VERIFIED
    )
    calls = []
    responses = [
        _block(
            stop_reason="tool_use",
            content=[
                _block(
                    type="tool_use",
                    id="tu_1",
                    name="okupasi",
                    input={"tanpa_tindak_lanjut_hari": 0},
                )
            ],
        ),
        _block(
            stop_reason="end_turn",
            content=[_block(type="text", text="Ada 1 kasus okupasi terbuka.")],
        ),
    ]

    def fake_create(**params):
        calls.append(params)
        return responses[len(calls) - 1]

    monkeypatch.setattr(ai, "create", fake_create)
    result = assistant.answer(
        admin, "Berapa okupasi terbuka?", history=[{"q": "halo", "answer": "hai"}]
    )
    assert result["source"] == "ai"
    assert result["answer"] == "Ada 1 kasus okupasi terbuka."
    assert result["tables"] and result["tables"][0]["rows"]
    assert calls[0]["messages"][0] == {"role": "user", "content": "halo"}
    tool_result = calls[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and tool_result["tool_use_id"] == "tu_1"
    assert {t["name"] for t in calls[0]["tools"]} >= {"okupasi", "aset", "cari"}


def test_ai_error_falls_back_to_rules(monkeypatch, admin, overdue_grievance, settings):
    settings.ANTHROPIC_API_KEY = "uji"

    def broken(**params):
        raise ai.AIError("Layanan AI sedang sibuk.")

    monkeypatch.setattr(ai, "create", broken)
    result = assistant.answer(admin, "pengaduan lewat batas")
    assert result["source"] == "aturan"
    assert "sibuk" in result["error"]


def test_ai_create_uses_fallback_beta(monkeypatch, settings):
    settings.ANTHROPIC_API_KEY = "uji"
    settings.ANTHROPIC_MODEL = ""
    captured = {}

    class Messages:
        def create(self, **params):
            captured.update(params)
            return _block(stop_reason="end_turn", content=[])

    fake = SimpleNamespace(
        beta=SimpleNamespace(messages=Messages()), messages=Messages()
    )
    monkeypatch.setattr(ai, "_client", lambda: fake)
    ai.create(max_tokens=10, messages=[])
    assert captured["model"] == "claude-opus-5-5"
    assert (
        captured["betas"] == [ai.FALLBACK_BETA] and captured["fallbacks"] == "default"
    )


def test_ai_refusal_raises(monkeypatch, settings):
    settings.ANTHROPIC_API_KEY = "uji"
    settings.ANTHROPIC_MODEL = "model-lain"

    class Messages:
        def create(self, **params):
            assert "betas" not in params
            return _block(stop_reason="refusal", content=[])

    monkeypatch.setattr(ai, "_client", lambda: SimpleNamespace(messages=Messages()))
    with pytest.raises(ai.AIError):
        ai.create(max_tokens=10, messages=[])


def test_assistant_page_keeps_history(client, admin, overdue_grievance, settings):
    settings.ANTHROPIC_API_KEY = ""
    client.force_login(admin)
    url = reverse("asetlahan-assistant")
    assert client.post(url, {"q": "pengaduan lewat batas"}).status_code == 302
    page = client.get(url).content.decode()
    assert overdue_grievance.number in page
    client.post(url, {"reset": "1"})
    assert overdue_grievance.number not in client.get(url).content.decode()
