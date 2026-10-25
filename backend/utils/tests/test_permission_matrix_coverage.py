"""Setiap model modul SimLahan yang tampil di panel admin harus ada di matriks
hak akses modulnya; bila terlewat, hanya superuser yang dapat membukanya."""

import pytest
from django.contrib import admin

from alokasi.permissions import ALOKASI_GROUP_MODEL_PERMISSIONS
from asetlahan.permissions import ASETLAHAN_GROUP_MODEL_PERMISSIONS
from operasi.permissions import OPERASI_GROUP_MODEL_PERMISSIONS
from pengadaan.permissions import PENGADAAN_GROUP_MODEL_PERMISSIONS

MATRICES = {
    "alokasi": ALOKASI_GROUP_MODEL_PERMISSIONS,
    "asetlahan": ASETLAHAN_GROUP_MODEL_PERMISSIONS,
    "operasi": OPERASI_GROUP_MODEL_PERMISSIONS,
    "pengadaan": PENGADAAN_GROUP_MODEL_PERMISSIONS,
}


@pytest.mark.parametrize("app_label", sorted(MATRICES))
def test_admin_models_are_in_permission_matrix(app_label):
    missing = [
        model.__name__
        for model in admin.site._registry
        if model._meta.app_label == app_label and model not in MATRICES[app_label]
    ]
    assert missing == []
