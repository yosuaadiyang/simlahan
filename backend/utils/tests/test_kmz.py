import io
import zipfile

import pytest

from utils.geometry import SpatialFileError, kml_from_kmz, read_kml_features

KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<Folder><name>Blok A</name><Placemark>
<name>KMZ-1</name>
<ExtendedData><Data name="kecamatan"><value>Galang</value></Data></ExtendedData>
<Polygon><outerBoundaryIs><LinearRing><coordinates>
104.10,0.80,12 104.101,0.80,12 104.101,0.801,13 104.10,0.801,13 104.10,0.80,12
</coordinates></LinearRing></outerBoundaryIs></Polygon>
</Placemark></Folder>
<Folder><name>Blok B</name><Placemark>
<name>KMZ-2</name>
<Polygon><outerBoundaryIs><LinearRing><coordinates>
104.11,0.80 104.111,0.80 104.111,0.801 104.11,0.801 104.11,0.80
</coordinates></LinearRing></outerBoundaryIs></Polygon>
</Placemark></Folder>
<Placemark><name>Tanpa geometri</name></Placemark>
</Document></kml>"""


def make_kmz(kml: str = KML, extra: dict | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in (extra or {}).items():
            archive.writestr(name, content)
        archive.writestr("doc.kml", kml)
        archive.writestr("files/ikon.png", b"\x89PNG\r\n\x1a\n")
    return buffer.getvalue()


def test_kmz_prefers_root_doc_kml():
    kmz = make_kmz(extra={"lapisan/lain.kml": "<kml/>"})
    assert kml_from_kmz(kmz) == KML.encode()


def test_kmz_rejects_non_zip():
    with pytest.raises(SpatialFileError, match="rusak"):
        kml_from_kmz(b"bukan zip")


def test_kmz_without_kml_is_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("foto.jpg", b"\xff\xd8\xff")
    with pytest.raises(SpatialFileError, match="tidak berisi"):
        kml_from_kmz(buffer.getvalue())


@pytest.mark.parametrize("filename", ["peta.kml", "peta.KMZ"])
def test_read_kml_features_reads_all_folders_in_2d(filename):
    data = KML.encode() if filename.endswith(".kml") else make_kmz()
    rows = read_kml_features(data, filename)

    assert [props["Name"] for props, _ in rows] == ["KMZ-1", "KMZ-2"]
    for _props, geom in rows:
        assert geom.srid == 4326 and not geom.hasz
        assert geom.geom_type == "Polygon"
    assert rows[0][0].get("kecamatan") == "Galang"


def test_read_kml_features_rejects_garbage():
    with pytest.raises(SpatialFileError):
        read_kml_features(b"bukan kml", "peta.kml")
