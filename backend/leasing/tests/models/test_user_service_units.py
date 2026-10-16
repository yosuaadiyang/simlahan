import pytest
from django.urls import reverse

from leasing.models.service_unit import ServiceUnitGroupMapping


@pytest.mark.django_db
def test_jwt_login_updates_service_units(client, user_factory, service_unit, group):
    """Login through the JWT endpoint syncs service units from group mappings."""
    user = user_factory(username="jwt_user")
    user.set_password("a-Strong-pass-123")
    user.save()
    user.groups.add(group)
    ServiceUnitGroupMapping.objects.create(group=group, service_unit=service_unit)

    response = client.post(
        reverse("v1:auth-login"),
        data={"username": "jwt_user", "password": "a-Strong-pass-123"},
        content_type="application/json",
    )

    assert response.status_code == 200, response.data
    assert "access" in response.data and "refresh" in response.data
    assert user.service_units.count() == 1
    assert response.data["user"]["service_units"][0]["id"] == service_unit.id


@pytest.mark.django_db
def test_service_unit_update_on_login(client, user_factory, service_unit, group):
    """Test that the service units are updated when the user logs into the
    browsable REST API or into the Admin."""
    user = user_factory(username="test_user")
    user.set_password("test_password")
    user.save()

    ServiceUnitGroupMapping.objects.create(group=group, service_unit=service_unit)
    user.service_units.add(service_unit)

    client.login(username="test_user", password="test_password")

    assert user.service_units.count() == 0
