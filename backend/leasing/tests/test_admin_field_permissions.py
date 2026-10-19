import pytest
from django.contrib.auth.models import Permission

from leasing.models import Lease


@pytest.mark.django_db
def test_lease_admin_change_page_for_view_only_field_permissions(
    client, django_user_model, lease_test_data
):
    # Petugas yang hanya boleh MELIHAT kolom (termasuk relasi balik "related_to")
    # sebelumnya mendapat 500: relasi balik dijadikan readonly oleh admin.
    user = django_user_model.objects.create_user(
        username="lihat_saja", password="x", is_staff=True
    )
    user.user_permissions.set(
        Permission.objects.filter(
            content_type__app_label="leasing",
            codename__startswith="view_lease",
        )
    )
    assert user.has_perm("leasing.view_lease_related_to")
    assert not user.has_perm("leasing.change_lease_related_to")
    client.force_login(user)
    lease = lease_test_data["lease"]
    response = client.get(f"/admin/leasing/lease/{lease.pk}/change/")
    assert response.status_code == 200
    readonly = response.context["adminform"].readonly_fields
    assert "related_to" not in readonly
    assert Lease._meta.get_field("related_to").is_relation
