"""Asisten AI dan aksi OCR admin mengambil jatah AI per jam pengguna."""

from types import SimpleNamespace

import pytest
from django.contrib.admin.sites import site as admin_site
from django.urls import reverse

from asetlahan import ai
from asetlahan import assistant as engine
from asetlahan.models import Document

pytestmark = pytest.mark.django_db


@pytest.fixture
def ai_enabled(settings):
    settings.ANTHROPIC_API_KEY = "uji"


def test_assistant_question_needs_ai_budget(
    admin_client, admin_user, ai_enabled, monkeypatch
):
    asked = []

    def fake_answer(user, question, history):
        asked.append(question)
        return {"answer": "ok"}

    monkeypatch.setattr(engine, "answer", fake_answer)
    monkeypatch.setitem(ai.BUDGETS, "asisten", 1)
    url = reverse("asetlahan-assistant")
    assert admin_client.post(url, {"q": "Berapa aset?"}).status_code == 302
    assert admin_client.post(url, {"q": "Lagi?"}).status_code == 302
    assert asked == ["Berapa aset?"]


def test_admin_ocr_reads_without_ai_once_budget_spent(
    rf, admin_user, ai_enabled, monkeypatch
):
    from asetlahan import ocr, scope

    seen = []
    monkeypatch.setattr(
        ocr, "process_document", lambda doc, use_ai=True: seen.append(use_ai) or True
    )
    monkeypatch.setattr(scope, "document_allows", lambda *a: True)
    monkeypatch.setitem(ai.BUDGETS, "ocr-admin", 2)
    model_admin = admin_site._registry[Document]
    notes = []
    monkeypatch.setattr(
        model_admin, "message_user", lambda request, msg, **kw: notes.append(msg)
    )
    request = rf.post("/")
    request.user = admin_user
    docs = [SimpleNamespace(pk=i) for i in range(4)]
    model_admin.run_ocr(request, docs)
    assert seen == [True, True, False, False]
    assert any("tanpa AI" in str(note) for note in notes)
