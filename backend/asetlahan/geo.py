"""Fungsi geospasial: luas, deteksi aset di titik, tumpang tindih, GeoJSON."""

import json
from decimal import ROUND_HALF_UP, Decimal

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon

from utils.geometry import force_2d


def utm_srid(geom) -> int:
    """EPSG zona UTM WGS84 dari titik tengah geometri (Indonesia: zona 46–54)."""
    point = (
        geom.centroid
        if geom.srid == 4326
        else geom.transform(4326, clone=True).centroid
    )
    zone = int((point.x + 180) // 6) + 1
    return (32600 if point.y >= 0 else 32700) + zone


def area_m2(geom) -> Decimal | None:
    if geom is None or geom.empty:
        return None
    projected = geom.transform(utm_srid(geom), clone=True)
    return Decimal(str(projected.area)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def as_multipolygon(geom) -> MultiPolygon | None:
    if geom is None:
        return None
    if isinstance(geom, Polygon):
        return MultiPolygon(geom, srid=geom.srid)
    if isinstance(geom, MultiPolygon):
        return geom
    polygons = (
        [g for g in geom if isinstance(g, Polygon)] if hasattr(geom, "__iter__") else []
    )
    return MultiPolygon(*polygons, srid=geom.srid) if polygons else None


def asset_at(point, user=None):
    """Aset terkecil yang memuat titik; bila ``user`` diberikan, hanya aset di unitnya."""
    from asetlahan import scope
    from asetlahan.models import LandAsset

    if point is None:
        return None
    queryset = LandAsset.objects.filter(geometry__intersects=point)
    if user is not None:
        queryset = scope.scoped(queryset, user)
    return queryset.order_by("area_m2").first()


def encroached_area(case) -> Decimal | None:
    """Luas area okupasi yang berada di dalam aset (atau seluruh area bila tanpa aset)."""
    geom = case.area_geometry
    if geom is None:
        return None
    asset_geom = case.asset.geometry if case.asset_id and case.asset.geometry else None
    if asset_geom is not None:
        inside = geom.intersection(asset_geom)
        if inside.empty:
            return Decimal("0.00")
        return area_m2(inside)
    return area_m2(geom)


def asset_overlaps(
    queryset=None, min_area_m2: Decimal = Decimal("1"), limit: int = 500
):
    """Pasangan aset yang batasnya tumpang tindih (indikasi klaim ganda / salah ukur)."""
    from asetlahan.models import LandAsset

    results = []
    queryset = LandAsset.objects.all() if queryset is None else queryset
    assets = queryset.exclude(geometry__isnull=True).only(
        "id", "code", "name", "geometry"
    )
    for asset in assets:
        if len(results) >= limit:
            break
        others = (
            queryset.filter(pk__gt=asset.pk, geometry__intersects=asset.geometry)
            .exclude(geometry__isnull=True)
            .only("id", "code", "name", "geometry")
        )
        for other in others:
            overlap = asset.geometry.intersection(other.geometry)
            size = area_m2(overlap) if not overlap.empty and overlap.dims == 2 else None
            if size is not None and size >= min_area_m2:
                results.append(
                    {"a": asset, "b": other, "area_m2": size, "geometry": overlap}
                )
    return results


def external_overlaps(asset, user=None):
    """Bidang pengadaan & lahan alokasi yang beririsan dengan aset.

    Bila ``user`` diberikan, bidang/lahan hanya dicari di modul yang boleh
    dilihat pengguna tersebut.
    """
    from alokasi.models import LandPlot
    from pengadaan.models import AcquisitionParcel

    show_parcels = user is None or user.has_perm("pengadaan.view_acquisitionparcel")
    show_plots = user is None or user.has_perm("alokasi.view_landplot")
    if asset.geometry is None:
        return {"parcels": [], "plots": []}
    parcels = AcquisitionParcel.objects.filter(
        geometry__intersects=asset.geometry
    ).select_related("project")
    plots = LandPlot.objects.filter(geometry__intersects=asset.geometry)
    if asset.pengadaan_parcel_id:
        parcels = parcels.exclude(pk=asset.pengadaan_parcel_id)
    if asset.alokasi_plot_id:
        plots = plots.exclude(pk=asset.alokasi_plot_id)
    return {
        "parcels": list(parcels[:50]) if show_parcels else [],
        "plots": list(plots[:50]) if show_plots else [],
    }


def feature(geom, properties: dict) -> dict | None:
    if geom is None:
        return None
    return {
        "type": "Feature",
        "geometry": json.loads(geom.geojson),
        "properties": properties,
    }


def collection(features) -> dict:
    return {"type": "FeatureCollection", "features": [f for f in features if f]}


def parse_geojson_geometry(text: str):
    """GeoJSON (Feature/FeatureCollection/geometri) → MultiPolygon EPSG:4326."""
    data = json.loads(text)
    if data.get("type") == "FeatureCollection":
        geoms = [
            GEOSGeometry(json.dumps(f["geometry"]))
            for f in data.get("features", [])
            if f.get("geometry")
        ]
    elif data.get("type") == "Feature":
        geoms = [GEOSGeometry(json.dumps(data["geometry"]))]
    else:
        geoms = [GEOSGeometry(json.dumps(data))]
    polygons = []
    for geom in geoms:
        geom = force_2d(geom)
        if geom.srid is None:
            geom.srid = 4326
        elif geom.srid != 4326:
            geom.transform(4326)
        multi = as_multipolygon(geom)
        if multi is not None:
            polygons.extend(list(multi))
    if not polygons:
        raise ValueError("Tidak ada poligon di dalam GeoJSON.")
    result = MultiPolygon(*polygons, srid=4326)
    if not result.valid:
        result = as_multipolygon(result.buffer(0))
    return result
