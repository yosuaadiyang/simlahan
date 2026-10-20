"""Impor aset lahan dari berkas spasial: GeoJSON, KML, GeoPackage, atau Shapefile (ZIP).

Atribut yang dikenali (huruf besar/kecil bebas): kode/code, nama/name,
kecamatan, kelurahan/desa, alamat, nomor_hak, nib, pemegang_hak, peruntukan,
penggunaan, njop. Aset dengan kode yang sudah ada diperbarui, lainnya dibuat.
"""

import io
import json
import os
import tempfile
import zipfile
from decimal import Decimal, InvalidOperation

from django.contrib.gis.gdal import DataSource
from django.contrib.gis.gdal.error import GDALException
from django.contrib.gis.geos import GEOSException, GEOSGeometry
from django.db import transaction

from asetlahan import geo
from asetlahan.models import LandAsset, MapOverlayFeature, next_number
from utils.geometry import force_2d

MAX_FEATURES = 5000
MAX_OVERLAY_FEATURES = 20000
NAME_FIELDS = ("nama", "name", "namobj", "remark", "keterangan", "label", "wadmkd")

TEXT_FIELDS = {
    "name": ("nama", "name", "nama_aset", "lokasi"),
    "district": ("kecamatan", "district"),
    "village": ("kelurahan", "desa", "village"),
    "address": ("alamat", "address", "patokan"),
    "title_number": ("nomor_hak", "no_hak", "sertipikat", "sertifikat", "title_number"),
    "nib": ("nib",),
    "registered_owner": ("pemegang_hak", "pemilik", "owner"),
    "zoning": ("peruntukan", "zoning", "rtrw"),
    "land_use": ("penggunaan", "land_use"),
}


class AssetImportError(ValueError):
    pass


def _prop(props: dict, names) -> str:
    lowered = {str(k).lower(): v for k, v in props.items()}
    for name in names:
        value = lowered.get(name)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _decimal(value: str):
    if not value:
        return None
    try:
        return Decimal(value.replace(",", "."))
    except InvalidOperation:
        return None


def _geojson_items(data: bytes) -> list:
    try:
        payload = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        # Pesan bawaan Python berbahasa Inggris; sebutkan posisinya saja.
        where = (
            f"baris {error.lineno}, kolom {error.colno}"
            if isinstance(error, json.JSONDecodeError)
            else "teks bukan UTF-8"
        )
        raise AssetImportError(f"Berkas bukan GeoJSON yang valid ({where}).")
    kind = payload.get("type") if isinstance(payload, dict) else None
    if kind == "Feature":
        return [payload]
    if kind == "FeatureCollection":
        return payload.get("features") or []
    raise AssetImportError("Berkas harus GeoJSON Feature atau FeatureCollection.")


def _geojson_features(data: bytes):
    for index, item in enumerate(_geojson_items(data), start=1):
        geometry = item.get("geometry") if isinstance(item, dict) else None
        if not geometry:
            raise AssetImportError(f"Fitur ke-{index} tidak memiliki geometri.")
        try:
            geom = GEOSGeometry(json.dumps(geometry))
        except (GEOSException, GDALException, ValueError, TypeError) as error:
            raise AssetImportError(f"Fitur ke-{index}: geometri tidak valid ({error}).")
        if geom.srid is None:
            geom.srid = 4326
        yield item.get("properties") or {}, force_2d(geom)


def _ogr_features(path: str):
    try:
        source = DataSource(path)
    except GDALException as error:
        raise AssetImportError(f"Berkas tidak dapat dibaca: {error}")
    for layer in source:
        for feature in layer:
            if feature.geom is None:
                continue
            props = {name: feature.get(name) for name in feature.fields}
            geom = feature.geom.geos
            if geom.srid is None:
                geom.srid = 4326
            yield props, force_2d(geom)


def _extract_shapefile(data: bytes, directory: str) -> str:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise AssetImportError("Berkas ZIP rusak.")
    shapefiles = [
        n
        for n in archive.namelist()
        if n.lower().endswith(".shp") and not n.startswith("__MACOSX")
    ]
    if not shapefiles:
        raise AssetImportError("ZIP tidak berisi berkas .shp.")
    for name in archive.namelist():
        target = os.path.realpath(os.path.join(directory, name))
        if not target.startswith(os.path.realpath(directory) + os.sep):
            raise AssetImportError("Nama berkas di dalam ZIP tidak aman.")
    archive.extractall(directory)
    return os.path.join(directory, shapefiles[0])


def _read_features(data: bytes, filename: str) -> list:
    extension = os.path.splitext(filename.lower())[1]
    if extension in ("", ".json", ".geojson"):
        return list(_geojson_features(data))
    if extension not in (".zip", ".kml", ".gpkg"):
        raise AssetImportError(
            "Format tidak didukung. Gunakan GeoJSON, KML, GeoPackage, atau Shapefile (ZIP)."
        )
    with tempfile.TemporaryDirectory() as directory:
        if extension == ".zip":
            path = _extract_shapefile(data, directory)
        else:
            path = os.path.join(directory, f"impor{extension}")
            with open(path, "wb") as handle:
                handle.write(data)
        return list(_ogr_features(path))


def _polygon(index: int, geom):
    if geom.srid != 4326:
        geom = geom.transform(4326, clone=True)
    multi = geo.as_multipolygon(geom)
    if multi is None:
        raise AssetImportError(
            f"Fitur ke-{index}: tipe geometri {geom.geom_type} harus poligon."
        )
    if not multi.valid:
        multi = geo.as_multipolygon(multi.buffer(0))
    return multi


def read_overlay_features(data: bytes, filename: str) -> list:
    """Baca berkas lapisan referensi; semua tipe geometri (titik, garis, poligon) diterima."""
    features = _read_features(data, filename)
    if not features:
        raise AssetImportError("Tidak ada fitur di dalam berkas.")
    if len(features) > MAX_OVERLAY_FEATURES:
        raise AssetImportError(
            f"Maksimal {MAX_OVERLAY_FEATURES} fitur per lapisan; pecah berkasnya."
        )
    result = []
    for props, geom in features:
        if geom.srid != 4326:
            geom = geom.transform(4326, clone=True)
        if not geom.valid and geom.dims == 2:
            geom = geom.buffer(0)
        clean = {
            str(k)[:64]: (v if isinstance(v, (int, float, bool)) else str(v)[:255])
            for k, v in props.items()
            if v not in (None, "")
        }
        result.append((_prop(props, NAME_FIELDS)[:255], geom, clean))
    return result


def replace_overlay_features(overlay, features) -> int:
    with transaction.atomic():
        overlay.features.all().delete()
        MapOverlayFeature.objects.bulk_create(
            [
                MapOverlayFeature(
                    overlay=overlay, name=name, geometry=geom, properties=props
                )
                for name, geom, props in features
            ],
            batch_size=1000,
        )
    return len(features)


def import_assets(
    data: bytes,
    *,
    filename: str = "impor.geojson",
    category=None,
    status=None,
    service_unit=None,
) -> tuple[int, int]:
    features = _read_features(data, filename)
    if not features:
        raise AssetImportError("Tidak ada fitur di dalam berkas.")
    if len(features) > MAX_FEATURES:
        raise AssetImportError(f"Maksimal {MAX_FEATURES} fitur per impor.")
    created = updated = 0
    with transaction.atomic():
        for index, (props, geom) in enumerate(features, start=1):
            values = {
                field: _prop(props, names)[:255] for field, names in TEXT_FIELDS.items()
            }
            values = {k: v for k, v in values.items() if v}
            values["geometry"] = _polygon(index, geom)
            values["area_m2"] = geo.area_m2(values["geometry"])
            njop = _decimal(_prop(props, ("njop", "njop_m2", "njop_per_m2")))
            if njop is not None:
                values["njop_per_m2"] = njop
            code = _prop(props, ("kode", "code", "kode_aset"))[:32]
            asset = LandAsset.objects.filter(code=code).first() if code else None
            if asset is None:
                asset = LandAsset(
                    code=code or next_number("AST"),
                    category=category,
                    service_unit=service_unit,
                )
                asset.status = status or asset.status
                created += 1
            else:
                updated += 1
            for field, value in values.items():
                setattr(asset, field, value)
            if not asset.name:
                asset.name = asset.code
            asset.save()
    return created, updated
