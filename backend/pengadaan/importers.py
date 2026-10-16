"""Impor peta bidang (GeoJSON atau Shapefile dalam ZIP) ke daftar bidang proyek.

Peta bidang dari BPN umumnya tersedia sebagai SHP/DXF dalam sistem koordinat
TM-3 atau UTM. Shapefile wajib menyertakan berkas .prj agar dapat diproyeksikan
ulang otomatis ke WGS 84 (EPSG:4326). GeoJSON diasumsikan WGS 84 sesuai RFC 7946
kecuali menyertakan anggota "crs".
"""

import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from django.db import transaction
from django.utils.translation import gettext as _

from pengadaan.models import AcquisitionParcel

MAX_FEATURES = 20000
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024


class ImportError_(Exception):
    pass


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
    if geom.srid is None:
        geom.srid = 4326
    if geom.srid != 4326:
        geom.transform(4326)
    if isinstance(geom, MultiPolygon):
        return geom
    if isinstance(geom, Polygon):
        return MultiPolygon(geom, srid=4326)
    return None


def _decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", ".")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _iter_geojson(raw: bytes):
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ImportError_(_("Invalid GeoJSON file: %(error)s") % {"error": e})
    srid = 4326
    crs_name = (data.get("crs") or {}).get("properties", {}).get("name", "")
    if "EPSG" in crs_name.upper():
        try:
            srid = int(crs_name.upper().rsplit(":", 1)[-1].replace("EPSG", ""))
        except ValueError:
            srid = 4326
    features = (
        data.get("features") if data.get("type") == "FeatureCollection" else [data]
    )
    for feature in features or []:
        geometry = feature.get("geometry")
        if not geometry:
            yield feature.get("properties") or {}, None
            continue
        geom = GEOSGeometry(json.dumps(geometry), srid=srid)
        yield feature.get("properties") or {}, geom


def _iter_shapefile_zip(path: str):
    tmpdir = tempfile.mkdtemp(prefix="pengadaan-shp-")
    try:
        with zipfile.ZipFile(path) as archive:
            total = sum(info.file_size for info in archive.infolist())
            if total > MAX_UNCOMPRESSED_BYTES:
                raise ImportError_(_("Archive is too large."))
            for info in archive.infolist():
                name = os.path.basename(info.filename)
                if not name or info.is_dir():
                    continue
                # Cegah path traversal: hanya nama berkas yang diekstrak.
                with archive.open(info) as src, open(
                    os.path.join(tmpdir, name), "wb"
                ) as dst:
                    shutil.copyfileobj(src, dst)
        files = os.listdir(tmpdir)
        shp_files = [f for f in files if f.lower().endswith(".shp")]
        if not shp_files:
            raise ImportError_(_("No .shp file found in the archive."))
        if not any(f.lower().endswith(".prj") for f in files):
            raise ImportError_(
                _("The .prj file (coordinate system) is required for shapefiles.")
            )
        source = DataSource(os.path.join(tmpdir, shp_files[0]))
        layer = source[0]
        for feature in layer:
            props = {name: feature.get(name) for name in layer.fields}
            geom = None
            if feature.geom is not None:
                ogr = feature.geom.clone()
                ogr.transform(4326)
                geom = ogr.geos
                geom.srid = 4326
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
    if name.endswith((".geojson", ".json")):
        return _import_rows(
            project,
            _iter_geojson(uploaded_file.read()),
            number_field,
            area_field,
            update_existing,
        )
    raise ImportError_(
        _("Supported formats: GeoJSON (.geojson/.json) or zipped shapefile (.zip).")
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
            multipolygon = None
            if geom is not None:
                try:
                    multipolygon = _to_multipolygon(geom)
                except Exception as e:  # noqa: BLE001 - laporkan baris yang gagal
                    result.errors.append(
                        _("Row %(row)s: invalid geometry (%(error)s).")
                        % {"row": index, "error": e}
                    )
                if multipolygon is None:
                    result.skipped += 1
                    continue
                if not multipolygon.valid:
                    multipolygon = multipolygon.buffer(0)
                    if isinstance(multipolygon, Polygon):
                        multipolygon = MultiPolygon(multipolygon, srid=4326)

            area = _decimal(props.get(area_field)) if area_field else None
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
                        setattr(parcel, attr, str(props[key])[:255])
                        break
            parcel.save()
    return result
