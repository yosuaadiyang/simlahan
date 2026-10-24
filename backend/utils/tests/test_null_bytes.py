"""Karakter NUL pada permintaan ditolak 400, bukan galat 500 dari PostgreSQL."""

import json

import pytest


@pytest.mark.django_db
def test_null_byte_in_query_string_is_rejected(client):
    response = client.get("/portal/lahan/", {"q": "a\x00b"})
    assert response.status_code == 400


@pytest.mark.django_db
def test_null_byte_in_form_post_is_rejected(client):
    response = client.post("/portal/lacak/", {"number": "x\x00", "pin": "1"})
    assert response.status_code == 400


@pytest.mark.django_db
def test_null_byte_in_json_body_is_rejected(admin_client):
    response = admin_client.post(
        "/komando/api/ai-satelit/",
        json.dumps({"bbox": "\x00"}),
        content_type="application/json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_normal_requests_pass(client):
    assert client.get("/portal/lahan/", {"q": "Rempang"}).status_code == 200
