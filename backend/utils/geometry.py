"""Utilitas geometri bersama untuk semua impor peta."""


def force_2d(geom):
    """Buang koordinat Z (ketinggian) dari KML/GPS; kolom geometri basis data 2D."""
    if geom is None or not geom.hasz:
        return geom
    srid = geom.srid
    ogr = geom.ogr
    ogr.coord_dim = 2
    flat = ogr.geos
    flat.srid = srid
    return flat


# --------------------------------------------------------------------------
# KML / KMZ (Google Earth)
# --------------------------------------------------------------------------

KML_EXTENSIONS = (".kml", ".kmz")
MAX_KML_BYTES = 100 * 1024 * 1024


def ogr_feature_geometry(feature):
    """Geometri fitur OGR, atau None bila fitur tidak punya geometri.

    ``Feature.geom`` milik Django melempar GDALException untuk geometri kosong
    (mis. placemark KML tanpa koordinat) alih-alih mengembalikan None.
    """
    from django.contrib.gis.gdal.error import GDALException

    try:
        return feature.geom
    except GDALException:
        return None


class SpatialFileError(ValueError):
    """Berkas spasial tidak dapat dibaca; pesannya siap ditampilkan ke pengguna."""


def kml_from_kmz(data: bytes) -> bytes:
    """Ambil dokumen KML dari arsip KMZ (doc.kml, atau .kml pertama)."""
    import io
    import os
    import zipfile

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise SpatialFileError("Berkas KMZ rusak atau bukan arsip KMZ.")
    with archive:
        documents = [
            info
            for info in archive.infolist()
            if not info.is_dir()
            and info.filename.lower().endswith(".kml")
            and not info.filename.startswith("__MACOSX")
        ]
        if not documents:
            raise SpatialFileError("KMZ tidak berisi berkas .kml.")
        # Google Earth menyimpan dokumen utama sebagai doc.kml di akar arsip.
        documents.sort(
            key=lambda info: (
                os.path.basename(info.filename).lower() != "doc.kml",
                info.filename.count("/"),
            )
        )
        document = documents[0]
        if document.file_size > MAX_KML_BYTES:
            raise SpatialFileError("Isi KMZ terlalu besar (maksimal 100 MB).")
        return archive.read(document)


def read_kml_features(data: bytes, filename: str) -> list:
    """Fitur berkas KML/KMZ sebagai daftar (atribut, geometri WGS 84 2D).

    Semua folder/lapisan dibaca. Atribut berisi Name, Description, dan
    ExtendedData. Placemark tanpa geometri dilewati.
    """
    import os
    import tempfile

    from django.contrib.gis.gdal import DataSource
    from django.contrib.gis.gdal.error import GDALException
    from django.contrib.gis.geos import GEOSException

    if filename.lower().endswith(".kmz"):
        data = kml_from_kmz(data)
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "impor.kml")
        with open(path, "wb") as handle:
            handle.write(data)
        try:
            source = DataSource(path)
        except GDALException:
            raise SpatialFileError("Berkas KML tidak dapat dibaca.")
        for layer in source:
            for feature in layer:
                ogr_geom = ogr_feature_geometry(feature)
                if ogr_geom is None:
                    continue
                props = {name: feature.get(name) for name in feature.fields}
                try:
                    geom = ogr_geom.geos
                except (GDALException, GEOSException):
                    raise SpatialFileError(
                        f"Fitur ke-{len(rows) + 1}: geometri tidak dapat dibaca."
                    )
                if geom.srid is None:
                    geom.srid = 4326
                rows.append((props, force_2d(geom)))
    return rows
