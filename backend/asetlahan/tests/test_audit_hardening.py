"""Pengerasan aset lahan: API, berkas petugas, aplikasi lapangan, impor, OCR
dan asisten AI (catatan hardening audit keamanan run 1)."""

import io
import tempfile
import zipfile

import pytest
from django.contrib.auth.models import Permission
from django.urls import resolve, reverse
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from asetlahan.models import FieldReport
from asetlahan.tests.conftest import make_user
from utils.group_permissions import UserGroup

pytestmark = pytest.mark.django_db


def _sync(client, point, client_id, captured="2026-10-20T10:00:00+07:00"):
    return client.post(
        reverse("asetlahan-field-sync"),
        {
            "client_id": client_id,
            "lat": point.y,
            "lng": point.x,
            "captured_at": captured,
        },
    )


def test_api_hides_cross_module_links_and_hidden_ordering(officer, make_asset, units):
    make_asset(service_unit=units[0], code="AST-API")
    assert not officer.has_perm("pengadaan.view_acquisitionparcel")
    api = APIClient()
    api.force_authenticate(officer)
    row = api.get("/v1/aset/asset/").json()["results"][0]
    properties = row.get("properties", row)
    assert "pengadaan_parcel" not in properties
    assert "service_unit" in properties

    # Urutan hanya boleh berdasarkan kolom yang memang dikirim.
    view = resolve("/v1/aset/grievance/").func.cls()
    view.request = Request(APIRequestFactory().get("/v1/aset/grievance/"))
    view.request.user = officer
    view.format_kwarg = None
    view.action = "list"
    fields = view.ordering_fields
    assert "number" in fields
    assert not {"access_code", "complainant_name", "phone", "email"} & set(fields)


def test_officer_file_respects_module_switch(client, admin, seeded):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from asetlahan.models import Grievance

    grievance = Grievance.objects.create(
        subject="Uji",
        description="Uji",
        attachment=SimpleUploadedFile("bukti.pdf", b"%PDF-1.4 uji"),
    )
    client.force_login(admin)
    url = reverse("asetlahan-file", args=["pengaduan", grievance.pk])
    assert client.get(url).status_code == 200
    seeded.enable_grievance = False
    seeded.save()
    assert client.get(url).status_code == 404


def test_field_boundaries_need_view_permissions(client, seeded, units, make_asset):
    make_asset(service_unit=units[0], name="Aset Batas")
    user = make_user("hanya-lapor", units=[units[0]])
    user.user_permissions.add(Permission.objects.get(codename="add_fieldreport"))
    client.force_login(user)
    response = client.get(reverse("asetlahan-field-boundaries"))
    assert response.status_code == 200
    assert "Aset Batas" not in response.content.decode()


def test_field_report_without_unit_rejected_for_multi_unit_officer(
    client, seeded, units, make_asset
):
    user = make_user("dua-unit", UserGroup.PETUGAS_LAPANGAN, units=list(units))
    client.force_login(user)
    asset = make_asset(service_unit=units[0])
    outside = asset.geometry.centroid.clone()
    outside.x += 1  # jauh dari aset mana pun
    response = _sync(client, outside, "22222222-2222-2222-2222-222222222222")
    assert response.status_code == 400
    assert not FieldReport.objects.exists()


def test_field_report_impossible_date_is_not_a_crash(client, field_officer, make_asset):
    asset = make_asset(service_unit=field_officer.service_units.first())
    client.force_login(field_officer)
    response = _sync(
        client,
        asset.geometry.centroid,
        "33333333-3333-3333-3333-333333333333",
        captured="2026-13-40T10:00:00+07:00",
    )
    assert response.status_code == 201, response.content


def test_corrupt_archives_are_clean_import_errors():
    from asetlahan.importers import AssetImportError, _extract_shapefile
    from utils.geometry import SpatialFileError, kml_from_kmz

    def corrupt(name):
        # Data tak terkompresi (STORED) dengan satu bita isi diubah: header
        # dan direktori ZIP tetap sah, CRC isinya salah saat dibaca.
        payload = bytes(range(256)) * 16
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
            archive.writestr(name, payload)
        data = bytearray(buffer.getvalue())
        offset = data.index(payload[:64]) + 100
        data[offset] ^= 0xFF
        return bytes(data)

    with tempfile.TemporaryDirectory() as directory:
        with pytest.raises(AssetImportError):
            _extract_shapefile(corrupt("bidang.shp"), directory)
    with pytest.raises(SpatialFileError):
        kml_from_kmz(corrupt("doc.kml"))


@pytest.mark.parametrize(
    "value,expected",
    [("NaN", None), ("Infinity", None), ("1e20", None), ("250.5", "250.5")],
)
def test_ocr_area_must_be_finite_and_in_range(value, expected):
    from asetlahan.ocr import _asset_values

    area = _asset_values({"luas_m2": value}).get("area_m2")
    assert (str(area) if area is not None else None) == expected


def test_assistant_tool_coerces_non_text_filters(officer):
    from asetlahan.assistant import run_tool

    result = run_tool(officer, "aset", {"kelurahan": 5, "status": ["x"]})
    assert isinstance(result, dict)


def test_shared_map_dies_with_creator_access(client, officer, make_asset, units):
    import datetime

    from django.utils import timezone

    from asetlahan.models import MapShare

    asset = make_asset(service_unit=units[0])
    share = MapShare.objects.create(
        title="Peta publik", created_by=officer, service_unit=units[0]
    )
    share.assets.add(asset)
    url = reverse("asetlahan-share", args=[share.token])
    assert client.get(url).status_code == 200
    officer.is_active = False
    officer.save(update_fields=["is_active"])
    assert client.get(url).status_code == 404

    # Masa berlaku maksimal 90 hari saat dibuat/diubah lewat admin.
    from asetlahan.admin import MapShareForm

    officer.is_active = True
    officer.save(update_fields=["is_active"])
    form_class = type("F", (MapShareForm,), {"user": officer})
    form = form_class(
        data={
            "title": "Terlalu lama",
            "expires_at": (timezone.now() + datetime.timedelta(days=365)).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "is_active": "on",
            "service_unit": units[0].pk,
            "assets": [asset.pk],
        }
    )
    assert not form.is_valid()
    assert "expires_at" in form.errors


def test_shared_map_project_must_be_in_creator_scope(seeded, units):
    from asetlahan.admin import MapShareForm
    from asetlahan.tests.conftest import make_user
    from pengadaan.models import AcquisitionProject

    project = AcquisitionProject.objects.create(name="Proyek di luar penugasan")
    valuer = make_user("penilai-peta", UserGroup.PENILAI, UserGroup.PETUGAS_ASET)
    valuer.user_permissions.add(Permission.objects.get(codename="add_mapshare"))
    form_class = type("F", (MapShareForm,), {"user": valuer})
    form = form_class(
        data={
            "title": "Bocor",
            "is_active": "on",
            "pengadaan_project": project.pk,
            "expires_at": "2030-01-01 00:00:00",
        }
    )
    form.is_valid()
    assert "pengadaan_project" in form.errors
