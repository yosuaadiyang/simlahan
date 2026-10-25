"""Halaman admin tidak boleh menjalankan kueri sebanyak jumlah model atau baris."""

import pytest
from django.urls import reverse

from operasi.models import Korwil, Resident


@pytest.mark.django_db
def test_admin_pages_load_module_settings_once(
    admin_client, django_assert_max_num_queries
):
    admin_client.get(reverse("admin:index"))
    # Menu admin memeriksa saklar modul aset untuk setiap model; dulu 59 kueri.
    with django_assert_max_num_queries(20):
        assert admin_client.get(reverse("admin:index")).status_code == 200


@pytest.mark.django_db
def test_resident_list_does_not_query_per_row(
    admin_client, django_assert_max_num_queries
):
    korwils = [
        Korwil.objects.create(code=f"K{i}", name=f"Korwil {i}") for i in range(3)
    ]
    for i in range(30):
        Resident.objects.create(korwil=korwils[i % 3], head_name=f"Warga {i}")
    admin_client.get(reverse("admin:operasi_resident_changelist"))
    with django_assert_max_num_queries(20):
        response = admin_client.get(reverse("admin:operasi_resident_changelist"))
    assert response.status_code == 200
