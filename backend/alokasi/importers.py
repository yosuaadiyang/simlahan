"""Impor data lahan dari GeoJSON (admin "Impor lahan" dan perintah alokasi_impor_lahan)."""

import json
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.contrib.gis.gdal.error import GDALException
from django.contrib.gis.geos import GEOSException, GEOSGeometry, MultiPolygon
from django.db import transaction

from alokasi import enums
from alokasi.models import LandPlot

# UTM zona 48N mencakup Batam–Rempang–Galang; dipakai untuk menghitung luas m².
AREA_SRID = 32648


class PlotImportError(ValueError):
    pass


def _prop(props: dict, *names, default=""):
    lowered = {str(k).lower(): v for k, v in props.items()}
    for name in names:
        value = lowered.get(name)
        if value not in (None, ""):
            return value
    return default


def _decimal(value, label):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except InvalidOperation:
        raise PlotImportError(f"Nilai {label} tidak valid: {value}")


def _geometry(raw) -> MultiPolygon:
    try:
        geom = GEOSGeometry(json.dumps(raw))
    except (GEOSException, GDALException, ValueError, TypeError) as error:
        raise PlotImportError(f"Geometri tidak valid: {error}")
    if geom.srid is None:
        geom.srid = 4326
    elif geom.srid != 4326:
        geom.transform(4326)
    if geom.geom_type == "Polygon":
        geom = MultiPolygon(geom, srid=4326)
    if geom.geom_type != "MultiPolygon":
        raise PlotImportError(
            f"Tipe geometri {geom.geom_type} tidak didukung (harus Polygon/MultiPolygon)."
        )
    if not geom.valid:
        geom = geom.buffer(0)
        if geom.geom_type == "Polygon":
            geom = MultiPolygon(geom, srid=4326)
    return geom


def area_m2(geom) -> Decimal:
    projected = geom.transform(AREA_SRID, clone=True)
    return Decimal(str(projected.area)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def _load_features(data: bytes | str) -> list:
    try:
        payload = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise PlotImportError(f"Berkas bukan JSON yang valid: {error}")
    if isinstance(payload, dict) and payload.get("type") == "Feature":
        features = [payload]
    elif isinstance(payload, dict) and payload.get("type") == "FeatureCollection":
        features = payload.get("features") or []
    else:
        raise PlotImportError("Berkas harus GeoJSON Feature atau FeatureCollection.")
    if not features:
        raise PlotImportError("Tidak ada fitur di dalam berkas.")
    return features


def _feature_values(index: int, feature: dict) -> tuple[str, dict]:
    """Kode lahan dan nilai field dari satu fitur GeoJSON."""
    props = feature.get("properties") or {}
    if not feature.get("geometry"):
        raise PlotImportError(f"Fitur ke-{index} tidak memiliki geometri.")
    try:
        geom = _geometry(feature["geometry"])
    except PlotImportError as error:
        raise PlotImportError(f"Fitur ke-{index}: {error}")
    code = str(_prop(props, "kode", "code", "kode_lahan")).strip()[:32]
    area = _decimal(_prop(props, "luas_m2", "area_m2", "luas"), "luas")
    allocation_type = _prop(props, "jenis_alokasi", "allocation_type")
    if allocation_type and allocation_type not in enums.AllocationType.values:
        raise PlotImportError(
            f"Fitur ke-{index}: jenis_alokasi tidak dikenal: {allocation_type}"
        )
    name = _prop(props, "nama", "name", default=code or f"Lahan impor {index}")
    intended_use = _prop(props, "arahan", "intended_use", "pemanfaatan")
    values = {
        "name": str(name)[:255],
        "geometry": geom,
        "area_m2": area or area_m2(geom),
        "district": str(_prop(props, "kecamatan", "district"))[:128],
        "village": str(_prop(props, "kelurahan", "desa", "village"))[:128],
        "address": str(_prop(props, "alamat", "address"))[:255],
        "zoning": str(_prop(props, "peruntukan", "zoning"))[:255],
        "intended_use": str(intended_use)[:255],
    }
    if allocation_type:
        values["allocation_type"] = allocation_type
    rate = _decimal(_prop(props, "tarif_uwt", "uwt_rate"), "tarif UWT")
    if rate is not None:
        values["uwt_rate_per_m2_year"] = rate
    term = _prop(props, "jangka_tahun", "term_years")
    if term not in ("", None):
        try:
            values["term_years"] = int(term)
        except (TypeError, ValueError):
            raise PlotImportError(f"Fitur ke-{index}: jangka_tahun tidak valid: {term}")
    return code, values


@transaction.atomic
def import_plots(data: bytes | str, defaults: dict | None = None) -> tuple[int, int]:
    """Buat atau perbarui lahan (dicocokkan dengan kode). Semua atau tidak sama sekali."""
    defaults = defaults or {}
    created = updated = 0
    for index, feature in enumerate(_load_features(data), start=1):
        code, values = _feature_values(index, feature)
        plot = LandPlot.objects.filter(code=code).first() if code else None
        if plot is None:
            plot = LandPlot(
                code=code,
                is_published=bool(defaults.get("is_published", False)),
                allocation_type=defaults.get("allocation_type")
                or enums.AllocationType.REGULAR,
            )
            created += 1
        else:
            updated += 1
            if plot.status in (enums.PlotStatus.RESERVED, enums.PlotStatus.ALLOCATED):
                # Jangan ubah luas/tarif lahan yang sedang/telah dialokasikan.
                for locked in ("area_m2", "uwt_rate_per_m2_year", "term_years"):
                    values.pop(locked, None)
        for field, value in values.items():
            setattr(plot, field, value)
        plot.save()
    return created, updated
