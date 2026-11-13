"""Pengerasan pengadaan: penghapusan bidang/proyek/pihak dijaga bila masih ada
ganti kerugian, data turunan bidang terhapus tersembunyi, nilai negatif,
validasi uang wajib pihak, samaran 4 digit, dan importir."""

import datetime
import io
import json
import zipfile
from decimal import Decimal

import pytest
from django.contrib.admin.sites import site as admin_site
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from pengadaan import enums
from pengadaan.crypto import mask
from pengadaan.importers import ImportError_, import_parcels
from pengadaan.models import AcquisitionParcel, Compensation

pytestmark = pytest.mark.django_db
D = datetime.date


def _compensation(parcel, party, **kwargs):
    return Compensation.objects.create(
        parcel=parcel, party=party, amount=Decimal("1000"), **kwargs
    )


def test_parcel_project_and_party_with_compensation_cannot_be_deleted(
    admin_client, project, parcel, party
):
    compensation = _compensation(parcel, party)
    for url in (
        reverse("v1:acquisitionparcel-detail", kwargs={"pk": parcel.pk}),
        reverse("v1:acquisitionproject-detail", kwargs={"pk": project.pk}),
        reverse("v1:entitledparty-detail", kwargs={"pk": party.pk}),
    ):
        response = admin_client.delete(url)
        assert response.status_code == 400, (url, response.content)
    assert AcquisitionParcel.objects.filter(pk=parcel.pk).exists()

    Compensation.objects.filter(pk=compensation.pk).update(
        status=enums.CompensationStatus.CANCELLED
    )
    response = admin_client.delete(
        reverse("v1:acquisitionparcel-detail", kwargs={"pk": parcel.pk})
    )
    assert response.status_code == 204


def test_admin_cannot_delete_parcel_with_compensation(rf, admin_user, parcel, party):
    _compensation(parcel, party)
    request = rf.get("/")
    request.user = admin_user
    model_admin = admin_site._registry[AcquisitionParcel]
    assert model_admin.has_delete_permission(request, parcel) is False


def test_children_of_deleted_parcel_are_hidden_and_unpayable(
    admin_client, parcel, party
):
    compensation = _compensation(
        parcel,
        party,
        status=enums.CompensationStatus.VALIDATED,
        validated_on=D(2026, 1, 5),
    )
    AcquisitionParcel.objects.filter(pk=parcel.pk).update(deleted=D(2026, 2, 1))
    listed = admin_client.get(reverse("v1:compensation-list")).json()
    rows = listed["results"] if isinstance(listed, dict) else listed
    assert compensation.pk not in {row["id"] for row in rows}
    response = admin_client.post(
        reverse("v1:compensationpayment-list"),
        {"compensation": compensation.pk, "paid_on": "2026-02-02", "amount": "10"},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_negative_in_kind_amount_rejected(admin_client, parcel, party):
    response = admin_client.post(
        reverse("v1:compensation-list"),
        {
            "parcel": parcel.pk,
            "party": party.pk,
            "form": enums.CompensationForm.REPLACEMENT_LAND,
            "amount": "-5",
        },
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "amount" in response.json()


def test_money_compensation_without_party_cannot_be_validated(admin_client, parcel):
    compensation = Compensation.objects.create(parcel=parcel, amount=Decimal("1000"))
    response = admin_client.post(
        reverse("v1:compensation-validate", kwargs={"pk": compensation.pk})
    )
    assert response.status_code == 400
    compensation.refresh_from_db()
    assert compensation.status == enums.CompensationStatus.DETERMINED


def test_mask_shows_only_last_four():
    assert mask("2171010101900001") == "*" * 12 + "0001"
    assert mask("1234567890") == "******7890"


def _feature_collection(number, area):
    return SimpleUploadedFile(
        "bidang.geojson",
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"parcel_number": number, "luas": area},
                        "geometry": None,
                    }
                ],
            }
        ).encode(),
    )


def test_importer_needs_change_permission_and_respects_affected_area(project, parcel):
    result = import_parcels(
        project, _feature_collection(parcel.parcel_number, 50), area_field="luas"
    )
    parcel.refresh_from_db()
    assert parcel.measured_area_m2 == Decimal("500")  # 50 < terkena 200: ditolak
    assert result.errors

    result = import_parcels(
        project,
        _feature_collection(parcel.parcel_number, 900),
        area_field="luas",
        can_update=False,
    )
    parcel.refresh_from_db()
    assert parcel.measured_area_m2 == Decimal("500")
    assert result.updated == 0 and result.errors


def test_zip_with_unwritable_member_is_a_clean_error(project):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("a" * 300 + ".shp", b"x")
    upload = SimpleUploadedFile("bidang.zip", buffer.getvalue())
    with pytest.raises(ImportError_):
        import_parcels(project, upload)
