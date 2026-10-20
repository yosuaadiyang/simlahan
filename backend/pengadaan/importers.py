"""Impor peta bidang (GeoJSON, KML/KMZ, atau Shapefile dalam ZIP) ke daftar bidang proyek.

Peta bidang dari BPN umumnya tersedia sebagai SHP/DXF dalam sistem koordinat
TM-3 atau UTM. Shapefile wajib menyertakan berkas .prj agar dapat diproyeksikan
ulang otomatis ke WGS 84 (EPSG:4326). GeoJSON diasumsikan WGS 84 sesuai RFC 7946
kecuali menyertakan anggota "crs". KML/KMZ (Google Earth) selalu WGS 84; nomor
bidang biasanya ada di atribut "Name".
"""

import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.contrib.gis.gdal import DataSource, GDALException
from django.contrib.gis.geos import GEOSException, GEOSGeometry, MultiPolygon, Polygon
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from pengadaan.models import AcquisitionParcel
from utils.geometry import (
    KML_EXTENSIONS,
    SpatialFileError,
    force_2d,
    ogr_feature_geometry,
    read_kml_features,
)

MAX_FEATURES = 20000
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024


class ImportError_(Exception):
    pass


class InvalidGeometry:
    """Penanda geometri yang tidak dapat dibaca pada satu baris impor."""


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self):
        return {
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors[:100],
        }


def _to_multipolygon(geom: GEOSGeometry) -> MultiPolygon | None:
    geom = force_2d(geom)
    if geom.srid is None:
        geom.srid = 4326
    if geom.srid != 4326:
        geom.transform(4326)
    if isinstance(geom, MultiPolygon):
        return geom
    if isinstance(geom, Polygon):
        return MultiPolygon(geom, srid=4326)
    return None


def _max_length(field_name: str) -> int:
    return AcquisitionParcel._meta.get_field(field_name).max_length


def _decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", ".")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _load_geojson(raw: bytes) -> dict:
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except UnicodeDecodeError:
        raise ImportError_(
            _("Invalid GeoJSON file: %(error)s")
            % {"error": _("the file is not UTF-8 encoded text")}
        )
    except json.JSONDecodeError as e:
        raise ImportError_(
            _("Invalid GeoJSON file: %(error)s")
            % {
                "error": _("syntax error at line %(line)s, column %(column)s")
                % {"line": e.lineno, "column": e.colno}
            }
        )
    if not isinstance(data, dict):
        raise ImportError_(_("The file is not a GeoJSON Feature or FeatureCollection."))
    return data


def _geojson_srid(data: dict) -> int:
    crs = data.get("crs")
    properties = crs.get("properties") if isinstance(crs, dict) else None
    crs_name = properties.get("name") if isinstance(properties, dict) else None
    if isinstance(crs_name, str) and "EPSG" in crs_name.upper():
        try:
            return int(crs_name.upper().rsplit(":", 1)[-1].replace("EPSG", ""))
        except ValueError:
            pass
    return 4326


def _geojson_features(data: dict) -> list:
    if data.get("type") == "FeatureCollection":
        features = data.get("features") or []
    else:
        features = [data]
    if not isinstance(features, list) or not all(
        isinstance(feature, dict) for feature in features
    ):
        raise ImportError_(_("The file is not a GeoJSON Feature or FeatureCollection."))
    return features


def _iter_geojson(raw: bytes):
    data = _load_geojson(raw)
    srid = _geojson_srid(data)
    for feature in _geojson_features(data):
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            properties = {}
        geometry = feature.get("geometry")
        if not geometry:
            yield properties, None
            continue
        try:
            geom = GEOSGeometry(json.dumps(geometry), srid=srid)
        except (GEOSException, GDALException, ValueError, TypeError):
            # Dilaporkan per baris oleh _import_rows, tidak menggagalkan impor.
            yield properties, InvalidGeometry()
            continue
        yield properties, geom


def _extract_zip(path: str, target_dir: str) -> list[str]:
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise ImportError_(_("The archive is not a valid ZIP file."))
    with archive:
        total = sum(info.file_size for info in archive.infolist())
        if total > MAX_UNCOMPRESSED_BYTES:
            raise ImportError_(_("Archive is too large."))
        for info in archive.infolist():
            name = os.path.basename(info.filename)
            if not name or info.is_dir():
                continue
            # Cegah path traversal: hanya nama berkas yang diekstrak.
            with archive.open(info) as src, open(
                os.path.join(target_dir, name), "wb"
            ) as dst:
                shutil.copyfileobj(src, dst)
    return os.listdir(target_dir)


def _ogr_to_geos(ogr_geometry):
    try:
        ogr = ogr_geometry.clone()
        ogr.transform(4326)
        geom = ogr.geos
    except (GDALException, GEOSException):
        return InvalidGeometry()
    geom.srid = 4326
    return geom


def _iter_shapefile_zip(path: str):
    tmpdir = tempfile.mkdtemp(prefix="pengadaan-shp-")
    try:
        files = _extract_zip(path, tmpdir)
        shp_files = [f for f in files if f.lower().endswith(".shp")]
        if not shp_files:
            raise ImportError_(_("No .shp file found in the archive."))
        if not any(f.lower().endswith(".prj") for f in files):
            raise ImportError_(
                _("The .prj file (coordinate system) is required for shapefiles.")
            )
        try:
            source = DataSource(os.path.join(tmpdir, shp_files[0]))
            layer = source[0]
        except (GDALException, IndexError):
            raise ImportError_(_("The shapefile could not be read."))
        for feature in layer:
            props = {name: feature.get(name) for name in layer.fields}
            geom = None
            ogr_geom = ogr_feature_geometry(feature)
            if ogr_geom is not None:
                geom = _ogr_to_geos(ogr_geom)
            yield props, geom
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def import_parcels(
    project,
    uploaded_file,
    number_field: str = "parcel_number",
    area_field: str | None = None,
    update_existing: bool = True,
) -> ImportResult:
    name = uploaded_file.name.lower()

    if name.endswith(".zip"):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
        try:
            return _import_rows(
                project,
                _iter_shapefile_zip(tmp_path),
                number_field,
                area_field,
                update_existing,
            )
        finally:
            os.unlink(tmp_path)
    if name.endswith(KML_EXTENSIONS):
        try:
            rows = read_kml_features(uploaded_file.read(), name)
        except SpatialFileError as error:
            raise ImportError_(str(error))
        # Google Earth menyimpan label placemark di "Name"; pakai bila atribut
        # nomor bidang yang diminta tidak ada.
        rows = [
            (
                (
                    {**props, number_field: props["Name"]}
                    if props.get(number_field) in (None, "") and props.get("Name")
                    else props
                ),
                geom,
            )
            for props, geom in rows
        ]
        return _import_rows(project, rows, number_field, area_field, update_existing)
    if name.endswith((".geojson", ".json")):
        return _import_rows(
            project,
            _iter_geojson(uploaded_file.read()),
            number_field,
            area_field,
            update_existing,
        )
    raise ImportError_(
        _(
            "Supported formats: GeoJSON (.geojson/.json), KML/KMZ (.kml/.kmz) or "
            "zipped shapefile (.zip)."
        )
    )


def _import_rows(  # noqa: C901
    project, rows, number_field, area_field, update_existing
) -> ImportResult:
    result = ImportResult()
    with transaction.atomic():
        for index, (props, geom) in enumerate(rows, start=1):
            if index > MAX_FEATURES:
                result.errors.append(
                    _("Feature limit exceeded; remaining rows skipped.")
                )
                break
            number = props.get(number_field)
            if number in (None, ""):
                result.skipped += 1
                result.errors.append(
                    _("Row %(row)s: attribute '%(field)s' is empty.")
                    % {"row": index, "field": number_field}
                )
                continue
            number = str(number).strip()
            if len(number) > _max_length("parcel_number"):
                result.skipped += 1
                result.errors.append(
                    _("Row %(row)s: parcel number is longer than %(max)s characters.")
                    % {"row": index, "max": _max_length("parcel_number")}
                )
                continue
            multipolygon = None
            if isinstance(geom, InvalidGeometry):
                result.skipped += 1
                result.errors.append(
                    _("Row %(row)s: the geometry could not be read.") % {"row": index}
                )
                continue
            if geom is not None:
                try:
                    multipolygon = _to_multipolygon(geom)
                except Exception as e:  # noqa: BLE001 - laporkan baris yang gagal
                    result.errors.append(
                        _("Row %(row)s: invalid geometry (%(error)s).")
                        % {"row": index, "error": e}
                    )
                else:
                    if multipolygon is None:
                        result.errors.append(
                            _("Row %(row)s: the geometry is not a polygon.")
                            % {"row": index}
                        )
                if multipolygon is None:
                    result.skipped += 1
                    continue
                if not multipolygon.valid:
                    multipolygon = multipolygon.buffer(0)
                    if isinstance(multipolygon, Polygon):
                        multipolygon = MultiPolygon(multipolygon, srid=4326)

            area = _decimal(props.get(area_field)) if area_field else None
            if area is not None:
                try:
                    AcquisitionParcel._meta.get_field(
                        "measured_area_m2"
                    ).run_validators(area)
                except DjangoValidationError:
                    result.errors.append(
                        _("Row %(row)s: the area value is out of range.")
                        % {"row": index}
                    )
                    area = None
            parcel = AcquisitionParcel.objects.filter(
                project=project, parcel_number=number
            ).first()
            if parcel is not None and not update_existing:
                result.skipped += 1
                continue
            if parcel is None:
                parcel = AcquisitionParcel(project=project, parcel_number=number)
                result.created += 1
            else:
                result.updated += 1
            if multipolygon is not None:
                parcel.geometry = multipolygon
            if area is not None:
                parcel.measured_area_m2 = area
            for attr, keys in {
                "nib": ("nib", "NIB"),
                "village": ("desa", "kelurahan", "village", "DESA"),
                "certificate_number": ("no_hak", "sertifikat", "NO_HAK"),
            }.items():
                for key in keys:
                    if props.get(key) not in (None, ""):
                        setattr(parcel, attr, str(props[key])[: _max_length(attr)])
                        break
            parcel.save()
    return result
