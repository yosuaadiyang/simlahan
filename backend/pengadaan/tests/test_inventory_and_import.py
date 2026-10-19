import json
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from pengadaan import enums
from pengadaan.models import AcquisitionParcel, EntitledParty, InventoryItem

pytestmark = pytest.mark.django_db

URL = "/v1/pengadaan/inventory_item/"


def test_inventory_item_crud_and_total(admin_client, parcel, party):
    response = admin_client.post(
        URL,
        {
            "parcel": parcel.pk,
            "party": party.pk,
            "item_type": enums.InventoryItemType.PLANT,
            "description": "Pohon kelapa produktif",
            "quantity": "12",
            "unit": "pohon",
            "unit_value": "1500000",
        },
        content_type="application/json",
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["party_name"] == "Budi Santoso"
    assert body["parcel_number"] == "001"
    assert Decimal(body["total_value"]) == Decimal("18000000")

    listing = admin_client.get(URL, {"parcel": parcel.pk}).json()
    assert listing["count"] == 1
    item_id = body["id"]
    response = admin_client.patch(
        f"{URL}{item_id}/", {"party": None}, content_type="application/json"
    )
    assert response.status_code == 200, response.content
    assert response.json()["party_name"] is None
    assert admin_client.delete(f"{URL}{item_id}/").status_code == 204
    assert not InventoryItem.objects.exists()


def test_inventory_owner_must_belong_to_parcel(admin_client, project, parcel):
    other_parcel = AcquisitionParcel.objects.create(
        project=project, parcel_number="002"
    )
    stranger = EntitledParty.objects.create(parcel=other_parcel, name="Orang lain")
    response = admin_client.post(
        URL,
        {
            "parcel": parcel.pk,
            "party": stranger.pk,
            "item_type": enums.InventoryItemType.BUILDING,
            "description": "Rumah permanen",
        },
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "party" in response.json()


def test_inventory_item_requires_permission(make_user, parcel):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(make_user("tamu"))
    assert client.get(URL).status_code == 403


def test_inventory_item_in_admin(admin_client, parcel, party):
    InventoryItem.objects.create(
        parcel=parcel,
        party=party,
        item_type=enums.InventoryItemType.WELL,
        description="Sumur bor",
    )
    changelist = admin_client.get(reverse("admin:pengadaan_inventoryitem_changelist"))
    assert changelist.status_code == 200
    assert "Sumur bor" in changelist.content.decode()
    change = admin_client.get(
        reverse("admin:pengadaan_acquisitionparcel_change", args=[parcel.pk])
    )
    assert change.status_code == 200
    assert "inventory_items" in change.content.decode()


def test_import_parcels_drops_z_coordinates(admin_client, project):
    collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"parcel_number": "Z-1"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [104.0, 1.0, 12.5],
                            [104.001, 1.0, 12.5],
                            [104.001, 1.001, 13.0],
                            [104.0, 1.001, 13.0],
                            [104.0, 1.0, 12.5],
                        ]
                    ],
                },
            }
        ],
    }
    upload = SimpleUploadedFile("bidang.geojson", json.dumps(collection).encode())
    url = reverse("v1:acquisitionproject-import-parcels", kwargs={"pk": project.pk})
    response = admin_client.post(url, {"file": upload})
    assert response.status_code == 200, response.content
    assert response.json()["created"] == 1
    parcel = AcquisitionParcel.objects.get(project=project, parcel_number="Z-1")
    assert not parcel.geometry.hasz
