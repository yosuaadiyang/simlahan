import json
from decimal import Decimal

import pytest

from asetlahan import importers, ocr
from asetlahan.models import Document, LandAsset

pytestmark = pytest.mark.django_db

CERTIFICATE = """
BUKU TANAH
HAK GUNA BANGUNAN No. 00145
NIB : 32.01.02.03.00145
Desa/Kelurahan : Sembulang
Kecamatan : Galang
Luas : 1.250 m2
Pemegang Hak : PT Contoh Sejahtera
Diterbitkan tanggal 12 Maret 2010
Berakhirnya hak tanggal 11-03-2040
NOP : 21.71.010.001.002-0003.0
Perkara 12/Pdt.G/2026/PN Btm
"""


def test_parse_fields_from_certificate_text():
    fields = ocr.parse_fields(CERTIFICATE)
    assert fields["jenis_hak"] == "hgb"
    assert fields["nomor_hak"] == "00145"
    assert fields["nib"] == "3201020300145"
    assert fields["kelurahan"] == "Sembulang"
    assert fields["kecamatan"] == "Galang"
    assert fields["luas_m2"] == "1250.00"
    assert fields["pemegang_hak"] == "PT Contoh Sejahtera"
    assert fields["tanggal_terbit"] == "2010-03-12"
    assert fields["tanggal_berakhir"] == "2040-03-11"
    assert fields["nomor_perkara"].startswith("12/Pdt.G/2026/PN")
    assert fields["nop"].startswith("21.71.010")


@pytest.mark.parametrize(
    "number,unit,expected",
    [
        ("1.250", "m2", "1250.00"),
        ("1.250,5", "m²", "1250.50"),
        ("2,5", "ha", "25000.00"),
        ("75", "m2", "75.00"),
    ],
)
def test_area_parsing(number, unit, expected):
    assert ocr._area(number, unit) == expected


def test_parse_date_rejects_invalid():
    assert ocr.parse_date("31-02-2020") == ""
    assert ocr.parse_date("5 Mei 2021") == "2021-05-05"


def test_apply_to_asset_fills_only_empty_fields(make_asset):
    asset = make_asset(registered_owner="Sudah diisi")
    document = Document(title="Sertipikat", asset=asset)
    document.extracted_fields = ocr.parse_fields(CERTIFICATE)
    changed = ocr.apply_to_asset(document)
    asset.refresh_from_db()
    assert asset.title_type == "hgb" and asset.title_number == "00145"
    assert asset.registered_owner == "Sudah diisi"
    assert str(asset.title_expiry) == "2040-03-11"
    assert changed


def _feature(code, x, name="Bidang"):
    return {
        "type": "Feature",
        "properties": {
            "kode": code,
            "nama": name,
            "luas": "1.000",
            "sertipikat": "SHM 1",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[x, 0.8], [x + 0.001, 0.8], [x + 0.001, 0.801], [x, 0.801], [x, 0.8]]
            ],
        },
    }


def test_geojson_import_creates_then_updates(seeded):
    data = json.dumps(
        {
            "type": "FeatureCollection",
            "features": [_feature("A-1", 104.1), _feature("", 104.2)],
        }
    )
    created, updated = importers.import_assets(data.encode(), filename="bidang.geojson")
    assert (created, updated) == (2, 0)
    assert LandAsset.objects.filter(code="A-1").exists()
    data = json.dumps({"type": "Feature", **_feature("A-1", 104.1, "Bidang baru")})
    assert importers.import_assets(data.encode(), filename="bidang.json") == (0, 1)
    assert LandAsset.objects.get(code="A-1").name == "Bidang baru"
    assert LandAsset.objects.get(code="A-1").area_m2 > Decimal("0")


@pytest.mark.parametrize(
    "payload,filename",
    [
        (b"bukan json", "a.geojson"),
        (b'{"type": "Point"}', "a.geojson"),
        (b"PK", "a.zip"),
        (b"x", "a.txt"),
    ],
)
def test_import_rejects_bad_files(seeded, payload, filename):
    with pytest.raises(importers.AssetImportError):
        importers.import_assets(payload, filename=filename)


def test_import_json_error_message_is_indonesian(seeded):
    # Pesan json.JSONDecodeError ("Expecting value ...") tidak boleh tampil.
    with pytest.raises(importers.AssetImportError) as excinfo:
        importers.import_assets(b"bukan json", filename="a.geojson")
    assert str(excinfo.value) == "Berkas bukan GeoJSON yang valid (baris 1, kolom 1)."
