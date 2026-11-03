import pytest
from django.utils import translation


@pytest.mark.django_db
def test_admin_javascript_texts_are_proper_indonesian(admin_client):
    with translation.override("id"):
        catalog = admin_client.get("/admin/jsi18n/").content.decode()
    # Kotak pilih ganda (filter_horizontal): bawaan Django berisi
    # "Pindahkan%s" tanpa spasi dan nama tombol bahasa Inggris.
    assert "Tandai %s lalu klik tombol panah kanan untuk memilihnya." in catalog
    assert "Tandai %s lalu klik tombol panah kiri untuk mengeluarkannya." in catalog
    assert "Pindahkan%s" not in catalog
    assert "Minggu" in catalog


def test_admin_action_button_label():
    with translation.override("id"):
        assert translation.gettext("Go") == "Jalankan"
