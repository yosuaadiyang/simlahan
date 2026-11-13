"""Impor admin yang memperbarui data lama (dicocokkan dengan kode) butuh izin
ubah, bukan hanya izin tambah."""

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _staff(django_user_model, perms):
    user = django_user_model.objects.create_user(
        username="pengimpor", password="RahasiaKuat123!", is_staff=True
    )
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label=perms[0], codename__in=perms[1]
        )
    )
    return user


@pytest.mark.parametrize(
    "url_name,app,model",
    [
        ("admin:alokasi_landplot_import", "alokasi", "landplot"),
        ("admin:operasi_korwil_import", "operasi", "korwil"),
    ],
)
def test_import_needs_change_permission(
    client, django_user_model, url_name, app, model
):
    user = _staff(django_user_model, (app, [f"add_{model}", f"view_{model}"]))
    client.force_login(user)
    url = reverse(url_name)
    assert client.get(url).status_code == 403

    user.user_permissions.add(
        Permission.objects.get(content_type__app_label=app, codename=f"change_{model}")
    )
    user = django_user_model.objects.get(pk=user.pk)  # buang cache izin
    client.force_login(user)
    assert client.get(url).status_code == 200
