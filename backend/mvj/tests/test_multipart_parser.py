import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_multipart_upload_without_data_field_is_rejected_with_400(admin_client):
    response = admin_client.post(reverse("v1:collectionletter-list"), {"x": "1"})

    assert response.status_code == 400
    assert "data" in response.json()["detail"]


@pytest.mark.django_db
def test_unauthenticated_multipart_upload_is_rejected_with_401(client):
    response = client.post(reverse("v1:collectionletter-list"), {"x": "1"})

    assert response.status_code == 401
