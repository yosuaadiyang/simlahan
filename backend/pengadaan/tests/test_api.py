import datetime
import io
import json
import zipfile
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from pengadaan import enums
from pengadaan.models import (
    AcquisitionParcel,
    AcquisitionProject,
    Compensation,
    CompensationPayment,
)

D = datetime.date


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
def test_create_project_via_api(admin_client, seeded_rules, municipality_factory):
    municipality = municipality_factory(name="Kota Uji", identifier="9972")
    response = admin_client.post(
        reverse("v1:acquisitionproject-list"),
        data={
            "name": "Bendungan Uji",
            "requiring_agency": "BBWS",
            "municipality": municipality.id,
            "acquisition_type": enums.AcquisitionType.PUBLIC_INTEREST,
            "purpose_category": enums.PublicInterestCategory.WATER,
        },
        content_type="application/json",
    )
    assert response.status_code == 201, response.content
    project = AcquisitionProject.objects.get(pk=response.json()["id"])
    assert project.identifier.startswith("PT-")
    assert project.created_by is not None
    assert project.milestones.exists()


@pytest.mark.django_db
def test_small_scale_area_limit(admin_client, seeded_rules):
    response = admin_client.post(
        reverse("v1:acquisitionproject-list"),
        data={
            "name": "Skala kecil",
            "requiring_agency": "Pemda",
            "acquisition_type": enums.AcquisitionType.SMALL_SCALE,
            "estimated_area_m2": "60000",
        },
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "estimated_area_m2" in response.json()


@pytest.mark.django_db
def test_affected_area_cannot_exceed_measured(admin_client, project):
    response = admin_client.post(
        reverse("v1:acquisitionparcel-list"),
        data={
            "project": project.id,
            "parcel_number": "X-1",
            "measured_area_m2": "100",
            "affected_area_m2": "150",
        },
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "affected_area_m2" in response.json()


@pytest.mark.django_db
def test_sensitive_data_masked_without_permission(make_user, party):
    viewer = make_user("viewer", perms=["pengadaan.view_entitledparty"])
    url = reverse("v1:entitledparty-detail", kwargs={"pk": party.pk})

    data = _client(viewer).get(url).json()
    assert data["nik"] != "2171010101900001"
    assert data["nik"].startswith("2171") and "*" in data["nik"]
    assert "*" in data["bank_account_number"]

    officer = make_user(
        "officer",
        perms=[
            "pengadaan.view_entitledparty",
            "pengadaan.view_sensitive_personal_data",
        ],
    )
    data = _client(officer).get(url).json()
    assert data["nik"] == "2171010101900001"
    assert data["bank_account_number"] == "1234567890"


@pytest.mark.django_db
def test_masked_value_roundtrip_keeps_original(make_user, party):
    editor = make_user(
        "editor",
        perms=["pengadaan.view_entitledparty", "pengadaan.change_entitledparty"],
    )
    url = reverse("v1:entitledparty-detail", kwargs={"pk": party.pk})
    client = _client(editor)
    data = client.get(url).json()
    response = client.patch(url, {"nik": data["nik"], "name": "Budi S."}, format="json")
    assert response.status_code == 200, response.content
    party.refresh_from_db()
    assert party.nik == "2171010101900001"
    assert party.name == "Budi S."


@pytest.mark.django_db
def test_invalid_nik_rejected(admin_client, parcel):
    response = admin_client.post(
        reverse("v1:entitledparty-list"),
        data={"parcel": parcel.id, "name": "Ani", "nik": "12345"},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "nik" in response.json()


@pytest.mark.django_db
def test_share_total_cannot_exceed_100(admin_client, party):
    response = admin_client.post(
        reverse("v1:entitledparty-list"),
        data={"parcel": party.parcel_id, "name": "Ahli waris", "share_percentage": "1"},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "share_percentage" in response.json()


@pytest.mark.django_db
def test_permission_denied_without_model_permission(make_user, project):
    nobody = make_user("nobody")
    response = _client(nobody).get(reverse("v1:acquisitionproject-list"))
    assert response.status_code == 403
    response = _client(nobody).get(reverse("v1:pengadaan-dashboard"))
    assert response.status_code == 403


@pytest.mark.django_db
def test_compensation_validation_and_payment_rules(admin_client, parcel, party):
    compensation = Compensation.objects.create(
        parcel=parcel, party=party, amount=Decimal("1000000")
    )
    payment_url = reverse("v1:compensationpayment-list")
    payload = {
        "compensation": compensation.id,
        "paid_on": "2025-05-05",
        "amount": "1000000",
    }

    # Belum divalidasi Ketua Pelaksana → ditolak.
    response = admin_client.post(payment_url, payload, content_type="application/json")
    assert response.status_code == 400

    response = admin_client.post(
        reverse("v1:compensation-validate", kwargs={"pk": compensation.pk})
    )
    assert response.status_code == 200, response.content
    compensation.refresh_from_db()
    assert compensation.status == enums.CompensationStatus.VALIDATED
    assert compensation.validated_by is not None

    # Melebihi nilai ganti kerugian → ditolak.
    response = admin_client.post(
        payment_url, {**payload, "amount": "1000001"}, content_type="application/json"
    )
    assert response.status_code == 400

    response = admin_client.post(payment_url, payload, content_type="application/json")
    assert response.status_code == 201, response.content
    compensation.refresh_from_db()
    assert compensation.status == enums.CompensationStatus.PAID
    assert CompensationPayment.objects.filter(compensation=compensation).count() == 1
    parcel.refresh_from_db()
    assert parcel.status == enums.ParcelStatus.PAID


@pytest.mark.django_db
def test_rights_release_requires_payment(admin_client, parcel, party):
    url = reverse("v1:rightsrelease-list")
    payload = {"parcel": parcel.id, "party": party.id, "released_on": "2025-06-02"}
    response = admin_client.post(url, payload, content_type="application/json")
    assert response.status_code == 400

    compensation = Compensation.objects.create(
        parcel=parcel,
        party=party,
        amount=Decimal("500"),
        status=enums.CompensationStatus.VALIDATED,
    )
    CompensationPayment.objects.create(
        compensation=compensation, paid_on=D(2025, 6, 1), amount=Decimal("500")
    )
    response = admin_client.post(url, payload, content_type="application/json")
    assert response.status_code == 201, response.content


def _geojson_upload():
    collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"parcel_number": "A-1", "luas": 120.5},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [104.0, 1.0],
                            [104.001, 1.0],
                            [104.001, 1.001],
                            [104.0, 1.001],
                            [104.0, 1.0],
                        ]
                    ],
                },
            },
            {
                "type": "Feature",
                "properties": {"parcel_number": ""},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[104.0, 1.0], [104.1, 1.0], [104.1, 1.1], [104.0, 1.0]]
                    ],
                },
            },
        ],
    }
    return SimpleUploadedFile(
        "bidang.geojson",
        json.dumps(collection).encode(),
        content_type="application/geo+json",
    )


@pytest.mark.django_db
def test_import_parcels_from_geojson(admin_client, project):
    url = reverse("v1:acquisitionproject-import-parcels", kwargs={"pk": project.pk})
    response = admin_client.post(url, {"file": _geojson_upload(), "area_field": "luas"})
    assert response.status_code == 200, response.content
    result = response.json()
    assert result["created"] == 1
    assert result["skipped"] == 1
    parcel = AcquisitionParcel.objects.get(project=project, parcel_number="A-1")
    assert parcel.geometry is not None
    assert parcel.measured_area_m2 == Decimal("120.50")

    # Impor ulang memperbarui, bukan menggandakan.
    response = admin_client.post(url, {"file": _geojson_upload()})
    assert response.json()["updated"] == 1
    assert AcquisitionParcel.objects.filter(project=project).count() == 1

    geo = admin_client.get(
        reverse("v1:acquisitionproject-geojson", kwargs={"pk": project.pk})
    ).json()
    assert geo["type"] == "FeatureCollection"
    assert geo["features"][0]["properties"]["parcel_number"] == "A-1"


@pytest.mark.django_db
def test_import_rejects_zip_without_prj(admin_client, project):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("bidang.shp", b"")
        archive.writestr("bidang.dbf", b"")
        archive.writestr("bidang.shx", b"")
    upload = SimpleUploadedFile("bidang.zip", buffer.getvalue())
    url = reverse("v1:acquisitionproject-import-parcels", kwargs={"pk": project.pk})
    response = admin_client.post(url, {"file": upload})
    assert response.status_code == 400


@pytest.mark.django_db
def test_nominative_list_export(admin_client, project, parcel, party):
    response = admin_client.get(
        reverse("v1:acquisitionproject-nominative-list", kwargs={"pk": project.pk})
    )
    assert response.status_code == 200
    assert "daftar-nominatif" in response["Content-Disposition"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as workbook:
        text = workbook.read("xl/sharedStrings.xml").decode()
    assert "Budi Santoso" in text
    assert parcel.parcel_number in text


@pytest.mark.django_db
def test_summary_dashboard_choices_and_workdays(admin_client, project, parcel):
    summary = admin_client.get(
        reverse("v1:acquisitionproject-summary", kwargs={"pk": project.pk})
    ).json()
    assert summary["parcel_count"] == 1
    assert summary["milestones_total"] > 0

    dashboard = admin_client.get(reverse("v1:pengadaan-dashboard")).json()
    assert dashboard["parcels_by_status"][enums.ParcelStatus.IDENTIFIED] == 1

    choices = admin_client.get(
        reverse("v1:pengadaan-choices"), HTTP_ACCEPT_LANGUAGE="id"
    ).json()
    labels = {c["value"]: c["label"] for c in choices["LandRightType"]}
    assert labels["shm"] == "Hak Milik (SHM)"

    response = admin_client.get(
        reverse("v1:pengadaan-workdays"), {"start": "2025-08-15", "days": "1"}
    )
    assert response.status_code == 200
    assert response.json()["date"] == "2025-08-19"

    response = admin_client.get(reverse("v1:pengadaan-workdays"), {"start": "x"})
    assert response.status_code == 400


@pytest.mark.django_db
def test_deadlines_endpoint(admin_client, project, parcel):
    from pengadaan.models import Valuation

    Valuation.objects.create(
        parcel=parcel,
        status=enums.ValuationStatus.FINAL,
        submitted_on=datetime.date.today(),
    )
    data = admin_client.get(reverse("v1:pengadaan-deadlines")).json()
    assert any(item["kind"] == "deliberation" for item in data)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "basename",
    [
        "acquisitionproject",
        "acquisitionmilestone",
        "acquisitionparcel",
        "entitledparty",
        "parcelsurvey",
        "inventoryitem",
        "announcement",
        "valuation",
        "deliberation",
        "deliberationresult",
        "objection",
        "consignment",
        "compensation",
        "compensationpayment",
        "rightsrelease",
        "handover",
        "affectedhousehold",
        "acquisitiondocument",
        "holiday",
        "deadlinerule",
    ],
)
def test_options_metadata_for_all_endpoints(admin_client, basename):
    response = admin_client.options(reverse(f"v1:{basename}-list"))
    assert response.status_code == 200, response.content
    fields = response.json()["fields"]
    assert "id" in fields


@pytest.mark.django_db
def test_holiday_year_filter(admin_client, seeded_rules):
    data = admin_client.get(
        reverse("v1:holiday-list"), {"date__year": 2026, "limit": 500}
    ).json()
    dates = [item["date"] for item in data["results"]]
    assert dates and all(d.startswith("2026-") for d in dates)


@pytest.mark.django_db
def test_document_upload_and_download(admin_client, project):
    upload = SimpleUploadedFile(
        "penlok.pdf", b"%PDF-1.4 uji", content_type="application/pdf"
    )
    response = admin_client.post(
        reverse("v1:acquisitiondocument-list"),
        {
            "project": project.id,
            "document_type": enums.DocumentType.LOCATION_DECREE,
            "title": "SK Penlok",
            "file": upload,
        },
    )
    assert response.status_code == 201, response.content
    document_id = response.json()["id"]
    assert response.json()["uploaded_by_name"]
    download = admin_client.get(
        reverse("v1:acquisitiondocument-download", kwargs={"pk": document_id})
    )
    assert download.status_code == 200
    assert b"".join(download.streaming_content).startswith(b"%PDF")


@pytest.mark.django_db
def test_duplicate_parcel_number_is_a_field_error(admin_client, parcel):
    response = admin_client.post(
        reverse("v1:acquisitionparcel-list"),
        data={"project": parcel.project_id, "parcel_number": parcel.parcel_number},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "parcel_number" in response.json()


@pytest.mark.django_db
def test_compensation_validation_requires_validate_permission(make_user, parcel, party):
    compensation = Compensation.objects.create(
        parcel=parcel, party=party, amount=Decimal("1000000")
    )
    url = reverse("v1:compensation-validate", kwargs={"pk": compensation.pk})
    billing = make_user(
        "penagih",
        perms=("pengadaan.view_compensation", "pengadaan.change_compensation"),
    )
    assert _client(billing).post(url).status_code == 403

    chair = make_user(
        "ketua",
        perms=("pengadaan.view_compensation", "pengadaan.validate_compensation"),
    )
    response = _client(chair).post(url)
    assert response.status_code == 200, response.content
    compensation.refresh_from_db()
    assert compensation.validated_by == chair
