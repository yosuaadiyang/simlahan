"""Analisis spasial pusat komando.

Penguasaan lahan (skor prioritas, impor & pencocokan berkas peta), tumpang
tindih lapisan, audit kepatuhan RTRW, anomali, peta panas, dan jejak GPS.
Semua data dibatasi lingkup Korwil pengguna (:mod:`operasi.geo`); lapisan
referensi yang ditandai "Tampil di pusat komando" terbuka untuk semua petugas.
"""

import csv
import datetime
import io
import json
import math
from collections import Counter, defaultdict
from decimal import Decimal

from django.contrib.gis.db.models.functions import SnapToGrid
from django.contrib.gis.geos import GEOSGeometry, LineString, MultiPolygon, Point
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext as _

from asetlahan import enums as aset_enums
from asetlahan import geo as aset_geo
from asetlahan.importers import AssetImportError, read_overlay_features
from asetlahan.models import MapOverlay, MapOverlayFeature
from operasi import enums, geo, services
from operasi.models import (
    Activity,
    Attendance,
    LandPlot,
    LandPlotChange,
    OfficerPosition,
    OfficerTrackPoint,
    Resident,
    SosAlert,
    ThreatZone,
)
from utils.spreadsheet import neutralize_formula

Stance = enums.Stance
ControlStatus = enums.ControlStatus
PlotZone = enums.PlotZone
RtrwZone = enums.RtrwZone

# Skor prioritas bidang = poin/ha × luas efektif × bobot zona × bobot urgensi.
# Luas di atas ambang dihitung akar agar bidang raksasa tidak mendominasi.
POINTS_PER_HA = 10
AREA_THRESHOLD_HA = 5
ZONE_WEIGHT = {PlotZone.CORE: 1.5, PlotZone.BUFFER: 1.2, PlotZone.OUTSIDE: 1.0}
URGENCY_WEIGHT = {
    enums.PlotUrgency.LOW: 1.0,
    enums.PlotUrgency.MEDIUM: 1.3,
    enums.PlotUrgency.HIGH: 1.6,
    enums.PlotUrgency.URGENT: 2.0,
}
# Pencocokan berkas penguasaan dengan bidang yang sudah ada.
MATCH_DISTANCE_M = 200
AREA_TOLERANCE = 0.35
MAX_IMPORT_FEATURES = 2000
MAX_OVERLAP_ROWS = 5000
MAX_AUDIT_ROWS = 5000
# Lapisan yang dipakai audit RTRW dan zona bidang.
ZONE_OVERLAY_KINDS = (
    aset_enums.OverlayKind.SPATIAL_PLAN,
    aset_enums.OverlayKind.FOREST,
    aset_enums.OverlayKind.PROJECT,
)
# Urutan prioritas zona bila satu titik masuk beberapa zona sekaligus.
ZONE_PRIORITY = (RtrwZone.SPECIAL, RtrwZone.PROTECTED, RtrwZone.CULTIVATION)
ZONE_WORDS = (
    ("khusus", RtrwZone.SPECIAL),
    ("lindung", RtrwZone.PROTECTED),
    ("budi", RtrwZone.CULTIVATION),
)
# Anomali
CONTRA_HIGH_PCT = 40
CONTRA_CRITICAL_PCT = 60
CONTRA_MIN_KNOWN = 5
SOS_OPEN_MINUTES = 30
TASK_OVERDUE_DAYS = 3
REPORT_PENDING_DAYS = 2
OUTSIDE_TOLERANCE_M = 100
# Jejak GPS
TRACK_MIN_SECONDS = 60
TRACK_MIN_METERS = 25
TRACK_KEEP_DAYS = 60
MAX_TRACK_POINTS = 5000
# Peta panas: sel ±250 m.
HEAT_CELL_DEG = 0.00225
HEAT_SOURCES = ("kegiatan", "posisi", "warga")


# --------------------------------------------------------------------------
# Lapisan referensi pusat komando
# --------------------------------------------------------------------------


def command_overlays():
    return MapOverlay.objects.filter(is_active=True, show_in_command=True)


def feature_zone(kind: str, name: str, properties: dict) -> str:
    """Zona RTRW dari nama/atribut objek lapisan; hutan = lindung, proyek = khusus."""
    values = [name or ""] + [str(v) for v in (properties or {}).values()]
    text = " ".join(values).lower()
    for word, zone in ZONE_WORDS:
        if word in text:
            return zone
    if kind == aset_enums.OverlayKind.FOREST:
        return RtrwZone.PROTECTED
    if kind == aset_enums.OverlayKind.PROJECT:
        return RtrwZone.SPECIAL
    return ""


def _best_zone(zones) -> str:
    for zone in ZONE_PRIORITY:
        if zone in zones:
            return zone
    return ""


def plot_tier(zones, kinds=()) -> str:
    """Kelas zona bidang: inti (proyek/khusus), penyangga (hutan, lindung, budi daya)."""
    if RtrwZone.SPECIAL in zones or aset_enums.OverlayKind.PROJECT in kinds:
        return PlotZone.CORE
    if (
        RtrwZone.PROTECTED in zones
        or RtrwZone.CULTIVATION in zones
        or aset_enums.OverlayKind.FOREST in kinds
    ):
        return PlotZone.BUFFER
    return PlotZone.OUTSIDE


def priority_score(area_ha, zone: str, urgency: str) -> float:
    area = max(float(area_ha or 0), 0.0)
    effective = min(area, AREA_THRESHOLD_HA) + math.sqrt(
        max(0.0, area - AREA_THRESHOLD_HA)
    )
    score = (
        POINTS_PER_HA
        * effective
        * ZONE_WEIGHT.get(zone, 1.0)
        * URGENCY_WEIGHT.get(urgency, 1.0)
    )
    return round(score, 1)


def _sql(queryset) -> tuple[str, tuple]:
    sql, params = queryset.values("pk").query.sql_with_params()
    return sql, tuple(params)


def _zone_features(overlay_ids) -> dict[int, dict]:
    return {
        row["pk"]: row
        for row in MapOverlayFeature.objects.filter(overlay_id__in=overlay_ids).values(
            "pk", "name", "properties", "overlay__kind", "overlay__name"
        )
    }


def _hits(table: str, column: str, condition: str, params, overlay_ids):
    """Pasangan (id objek, id fitur lapisan) yang saling bersinggungan.

    ``condition`` menyaring tabel objek (alias ``t``)."""
    if not overlay_ids:
        return []
    feature_table = MapOverlayFeature._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT t.id, f.id FROM {table} t JOIN {feature_table} f "
            f"ON ST_Intersects(f.geometry, t.{column}) "
            f"WHERE {condition} AND f.overlay_id = ANY(%s)",
            (*params, list(overlay_ids)),
        )
        return cursor.fetchall()


def plot_zones(plots) -> dict[int, dict]:
    """Zona tiap bidang (dalam satu kueri) dari lapisan referensi pusat komando."""
    plots = list(plots)
    result = {
        plot.pk: {"tier": PlotZone.OUTSIDE, "layers": [], "zones": []} for plot in plots
    }
    overlay_ids = list(
        command_overlays()
        .filter(kind__in=ZONE_OVERLAY_KINDS)
        .values_list("pk", flat=True)
    )
    if not plots or not overlay_ids:
        return result
    ids = [plot.pk for plot in plots]
    rows = _hits(
        LandPlot._meta.db_table, "geometry", "t.id = ANY(%s)", (ids,), overlay_ids
    )
    features = _zone_features(overlay_ids)
    found = defaultdict(lambda: {"zones": set(), "kinds": set(), "layers": set()})
    for plot_id, feature_id in rows:
        data = features.get(feature_id)
        if not data:
            continue
        kind = data["overlay__kind"]
        zone = feature_zone(kind, data["name"], data["properties"])
        entry = found[plot_id]
        entry["kinds"].add(kind)
        entry["layers"].add(data["overlay__name"])
        if zone:
            entry["zones"].add(zone)
    for plot_id, entry in found.items():
        result[plot_id] = {
            "tier": plot_tier(entry["zones"], entry["kinds"]),
            "layers": sorted(entry["layers"]),
            "zones": [z for z in ZONE_PRIORITY if z in entry["zones"]],
        }
    return result


def plot_overlaps(plot) -> list[dict]:
    """Persentase luas bidang yang masuk tiap lapisan referensi pusat komando."""
    overlays = list(command_overlays().values("pk", "name", "kind"))
    if not overlays or plot.geometry is None:
        return []
    feature_table = MapOverlayFeature._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT f.overlay_id, ST_Area(ST_Union(ST_CollectionExtract("
            "ST_Intersection(ST_MakeValid(f.geometry), ST_MakeValid(p.geometry)), 3)"
            ")::geography) "
            f"FROM {LandPlot._meta.db_table} p JOIN {feature_table} f "
            "ON ST_Intersects(f.geometry, p.geometry) "
            "WHERE p.id = %s AND f.overlay_id = ANY(%s) GROUP BY f.overlay_id",
            (plot.pk, [o["pk"] for o in overlays]),
        )
        areas = dict(cursor.fetchall())
    total = aset_geo.area_m2(plot.geometry) or Decimal("0")
    rows = []
    for overlay in overlays:
        area = areas.get(overlay["pk"]) or 0
        if area <= 0.01:
            continue
        rows.append(
            {
                "layer": overlay["name"],
                "kind": str(aset_enums.OverlayKind(overlay["kind"]).label),
                "area_ha": round(area / 10000, 4),
                "pct": min(round(area * 100 / float(total), 1), 100.0) if total else 0,
            }
        )
    return sorted(rows, key=lambda r: -r["pct"])


# --------------------------------------------------------------------------
# Bidang penguasaan
# --------------------------------------------------------------------------


def visible_plots(user):
    return geo.scoped(LandPlot.objects.all(), user)


def plot_row(plot, zone: dict) -> dict:
    return {
        "id": plot.pk,
        "number": plot.number,
        "name": plot.name,
        "owner": plot.owner_name,
        "guard": plot.guard_name,
        "korwil": plot.korwil.code if plot.korwil_id else "",
        "korwil_id": plot.korwil_id,
        "status": plot.control_status,
        "status_label": plot.get_control_status_display(),
        "color": enums.CONTROL_COLORS.get(plot.control_status, "#57606a"),
        "urgency": plot.urgency,
        "urgency_label": plot.get_urgency_display(),
        "area_ha": float(plot.area_ha),
        "zone": zone["tier"],
        "zone_label": str(PlotZone(zone["tier"]).label),
        "layers": zone["layers"],
        "score": priority_score(plot.area_ha, zone["tier"], plot.urgency),
        "controlled_on": (plot.controlled_on.isoformat() if plot.controlled_on else ""),
        "team": plot.control_team,
        "resident": plot.resident.head_name if plot.resident_id else "",
        "resident_id": plot.resident_id,
        "note": plot.note,
        "center": (
            [plot.geometry.point_on_surface.y, plot.geometry.point_on_surface.x]
            if plot.geometry is not None and not plot.geometry.empty
            else None
        ),
    }


def plot_rows(plots) -> list[dict]:
    plots = list(plots)
    zones = plot_zones(plots)
    return [plot_row(plot, zones[plot.pk]) for plot in plots]


def plot_summary(rows) -> dict:
    controlled = [r for r in rows if r["status"] == ControlStatus.CONTROLLED]
    pending = [r for r in rows if r["status"] == ControlStatus.PENDING]
    total_area = sum(r["area_ha"] for r in rows)
    controlled_area = sum(r["area_ha"] for r in controlled)
    return {
        "total": len(rows),
        "controlled": len(controlled),
        "pending": len(pending),
        "area_ha": round(total_area, 4),
        "controlled_ha": round(controlled_area, 4),
        "pending_ha": round(total_area - controlled_area, 4),
        "controlled_pct": services.pct(len(controlled), len(rows)),
        "score_pending": round(sum(r["score"] for r in pending), 1),
    }


@transaction.atomic
def set_control_status(
    plot, user, status: str, *, note="", controlled_on=None, team=None
) -> LandPlot:
    if status not in ControlStatus.values:
        raise ValidationError({"status": [_("Status penguasaan tidak dikenal.")]})
    old = plot.control_status
    fields = ["modified_at"]
    if team is not None:
        plot.control_team = team[:255]
        fields.append("control_team")
    if status == ControlStatus.CONTROLLED:
        plot.controlled_on = controlled_on or plot.controlled_on or timezone.localdate()
    else:
        plot.controlled_on = None
    fields += ["control_status", "controlled_on"]
    plot.control_status = status
    plot.save(update_fields=fields)
    if old != status:
        LandPlotChange.objects.create(
            plot=plot,
            old_status=old,
            new_status=status,
            changed_by=user,
            note=(note or "")[:255],
        )
    return plot


# --------------------------------------------------------------------------
# Impor berkas penguasaan (KML/KMZ/GeoJSON/GPKG/SHP)
# --------------------------------------------------------------------------

OWNER_KEYS = ("pemilik", "owner", "nama_pemilik", "pemilik_lahan")
GUARD_KEYS = ("penjaga", "penjaga_lahan", "guard")
AREA_KEYS = ("luas", "luas_ha", "area_ha", "luas (ha)")


def _value(props: dict, keys) -> str:
    lowered = {str(k).lower(): v for k, v in (props or {}).items()}
    for key in keys:
        value = lowered.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _area_value(props: dict):
    text = _value(props, AREA_KEYS).replace(",", ".")
    try:
        value = Decimal(text)
    except Exception:  # noqa: BLE001 - nilai atribut bebas dari berkas
        return None
    return value if value.is_finite() and value > 0 else None


def read_plot_file(data: bytes, filename: str) -> list[dict]:
    """Poligon dari berkas peta; objek non-poligon dilewati."""
    try:
        features = read_overlay_features(data, filename)
    except AssetImportError as error:
        raise ValidationError({"berkas": [str(error)]})
    if len(features) > MAX_IMPORT_FEATURES:
        raise ValidationError(
            {
                "berkas": [
                    _("Maksimal %(n)s objek per impor; pecah berkasnya.")
                    % {"n": MAX_IMPORT_FEATURES}
                ]
            }
        )
    items = []
    for index, (name, geom, props) in enumerate(features):
        multi = aset_geo.as_multipolygon(geom)
        if multi is not None and not multi.valid:
            multi = aset_geo.as_multipolygon(multi.buffer(0))
        if multi is None or multi.empty:
            continue
        area = aset_geo.area_m2(multi) or Decimal("0")
        items.append(
            {
                "index": index,
                "name": (name or "")[:255],
                "owner": _value(props, OWNER_KEYS)[:255],
                "guard": _value(props, GUARD_KEYS)[:255],
                "official_ha": _area_value(props),
                "measured_ha": (area / Decimal("10000")).quantize(Decimal("0.0001")),
                "geometry": multi,
            }
        )
    if not items:
        raise ValidationError({"berkas": [_("Berkas tidak memuat poligon bidang.")]})
    return items


def _same_owner(a: str, b: str) -> bool:
    a, b = a.strip().lower(), b.strip().lower()
    return bool(a) and a == b


def _classify(item: dict, user) -> dict:
    center = item["geometry"].point_on_surface
    srid = aset_geo.utm_srid(item["geometry"])
    candidates = visible_plots(user).filter(
        geometry__dwithin=(center, MATCH_DISTANCE_M / 111_320)
    )
    best, best_distance = None, None
    projected = center.transform(srid, clone=True)
    for plot in candidates[:50]:
        distance = plot.geometry.point_on_surface.transform(srid, clone=True).distance(
            projected
        )
        if distance <= MATCH_DISTANCE_M and (
            best_distance is None or distance < best_distance
        ):
            best, best_distance = plot, distance
    result = {
        "index": item["index"],
        "name": item["name"],
        "owner": item["owner"],
        "area_ha": float(item["official_ha"] or item["measured_ha"]),
        "center": [center.y, center.x],
        "plot": None,
    }
    if best is None:
        result["match"] = "nomatch"
        return result
    file_area = float(item["measured_ha"])
    plot_area = float(best.measured_area_ha or best.area_ha or 0)
    diff = abs(file_area - plot_area) / max(file_area, plot_area, 1e-9)
    result["plot"] = {
        "id": best.pk,
        "number": best.number,
        "name": best.name or best.owner_name,
        "status": best.control_status,
        "distance_m": round(best_distance),
        "area_diff_pct": round(diff * 100),
    }
    if best.control_status == ControlStatus.CONTROLLED:
        result["match"] = "already"
    elif diff <= AREA_TOLERANCE or _same_owner(item["owner"], best.owner_name):
        result["match"] = "match"
    else:
        result["match"] = "weak"
    return result


MATCH_LABELS = {
    "match": _("Cocok"),
    "weak": _("Cocok lemah (luas berbeda)"),
    "already": _("Sudah dikuasai"),
    "nomatch": _("Tidak ada bidang terdekat"),
    "new": _("Bidang baru"),
    "duplicate": _("Mirip bidang yang sudah ada"),
}


def preview_import(user, items, mode: str) -> dict:
    rows = [_classify(item, user) for item in items]
    if mode != "penguasaan":
        # Mode bidang baru: tandai objek yang mirip bidang yang sudah tercatat.
        for row in rows:
            row["match"] = (
                "duplicate" if row["match"] in ("match", "already") else "new"
            )
    for row in rows:
        row["match_label"] = str(MATCH_LABELS[row["match"]])
    counts = Counter(row["match"] for row in rows)
    return {"mode": mode, "rows": rows, "counts": dict(counts)}


def _new_plot(item, user, korwil, status, *, controlled_on, team, urgency, source):
    if korwil is None:
        korwil = geo.korwil_for_write(user, item["geometry"].point_on_surface)
    plot = LandPlot(
        name=item["name"],
        owner_name=item["owner"],
        guard_name=item["guard"],
        korwil=korwil,
        geometry=item["geometry"],
        official_area_ha=item["official_ha"],
        control_status=status,
        controlled_on=controlled_on if status == ControlStatus.CONTROLLED else None,
        control_team=team,
        urgency=urgency,
        source=source[:255],
        created_by=user,
    )
    plot.full_clean(exclude=["number", "korwil"])
    plot.save()
    LandPlotChange.objects.create(
        plot=plot,
        old_status="",
        new_status=status,
        changed_by=user,
        note=_("Impor %(source)s") % {"source": source[:200]},
    )
    return plot


@transaction.atomic
def apply_import(
    user,
    items,
    mode: str,
    selected,
    *,
    korwil=None,
    controlled_on=None,
    team="",
    urgency=enums.PlotUrgency.LOW,
    source="",
) -> dict:
    """Terapkan impor untuk objek terpilih; mode ``penguasaan`` menandai bidang
    cocok menjadi "sudah dikuasai" dan membuat bidang baru untuk yang tak cocok."""
    selected = set(selected)
    created = updated = skipped = 0
    for item in items:
        if item["index"] not in selected:
            continue
        if mode != "penguasaan":
            _new_plot(
                item,
                user,
                korwil,
                ControlStatus.PENDING,
                controlled_on=None,
                team=team,
                urgency=urgency,
                source=source,
            )
            created += 1
            continue
        row = _classify(item, user)
        if row["match"] == "already":
            skipped += 1
        elif row["match"] in ("match", "weak"):
            plot = LandPlot.objects.select_for_update().get(pk=row["plot"]["id"])
            set_control_status(
                plot,
                user,
                ControlStatus.CONTROLLED,
                note=_("Impor penguasaan %(source)s") % {"source": source[:180]},
                controlled_on=controlled_on,
                team=team or None,
            )
            updated += 1
        else:
            _new_plot(
                item,
                user,
                korwil,
                ControlStatus.CONTROLLED,
                controlled_on=controlled_on or timezone.localdate(),
                team=team,
                urgency=urgency,
                source=source,
            )
            created += 1
    return {"created": created, "updated": updated, "skipped": skipped}


# --------------------------------------------------------------------------
# Tumpang tindih lapisan
# --------------------------------------------------------------------------


def overlap_sources(user) -> list[dict]:
    sources = []
    if user.has_perm("operasi.view_landplot"):
        sources.append({"key": "bidang", "name": _("Bidang penguasaan")})
    for overlay in command_overlays():
        sources.append(
            {
                "key": f"ref-{overlay.pk}",
                "name": f"{overlay.name} ({overlay.get_kind_display()})",
            }
        )
    return sources


def _source(key: str, user, alias: str):
    """(FROM, WHERE, parameter, ekspresi label, nama) untuk satu sumber analisis."""
    if key == "bidang":
        if not user.has_perm("operasi.view_landplot"):
            raise ValidationError({"sumber": [_("Sumber tidak tersedia.")]})
        sql, params = _sql(visible_plots(user))
        return (
            f"{LandPlot._meta.db_table} {alias}",
            f"{alias}.id IN ({sql})",
            params,
            f"{alias}.number || CASE WHEN {alias}.name <> '' "
            f"THEN ' – ' || {alias}.name ELSE '' END",
            str(_("Bidang penguasaan")),
        )
    if key.startswith("ref-") and key[4:].isdigit():
        overlay = command_overlays().filter(pk=int(key[4:])).first()
        if overlay is not None:
            return (
                f"{MapOverlayFeature._meta.db_table} {alias}",
                f"{alias}.overlay_id = %s",
                (overlay.pk,),
                f"COALESCE(NULLIF({alias}.name, ''), '#' || {alias}.id)",
                overlay.name,
            )
    raise ValidationError({"sumber": [_("Sumber tidak tersedia.")]})


def _polygon_area_ha(from_sql, where_sql, params) -> float:
    alias = from_sql.split()[-1]
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT COALESCE(SUM(ST_Area(ST_CollectionExtract(ST_MakeValid("
            f"{alias}.geometry), 3)::geography)), 0) FROM {from_sql} WHERE {where_sql}",
            params,
        )
        return float(cursor.fetchone()[0] or 0) / 10000


def overlap(user, key_a: str, key_b: str) -> dict:
    from_a, where_a, params_a, label_a, name_a = _source(key_a, user, "a")
    from_b, where_b, params_b, label_b, name_b = _source(key_b, user, "b")
    same = key_a == key_b
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT a.id, {label_a}, b.id, {label_b}, ST_AsGeoJSON(x.g, 7), "
            "ST_Area(x.g::geography) "
            f"FROM {from_a} JOIN {from_b} ON ST_Intersects(a.geometry, b.geometry) "
            "CROSS JOIN LATERAL (SELECT ST_CollectionExtract(ST_Intersection("
            "ST_MakeValid(a.geometry), ST_MakeValid(b.geometry)), 3) AS g) x "
            f"WHERE {where_a} AND {where_b}"
            + (" AND a.id < b.id" if same else "")
            + " AND NOT ST_IsEmpty(x.g) ORDER BY 6 DESC LIMIT %s",
            (*params_a, *params_b, MAX_OVERLAP_ROWS + 1),
        )
        raw = cursor.fetchall()
    truncated = len(raw) > MAX_OVERLAP_ROWS
    raw = raw[:MAX_OVERLAP_ROWS]
    pairs, shapes = [], []
    for a_id, a_label, b_id, b_label, geojson, area in raw:
        if not area or area < 1:
            continue
        geom = GEOSGeometry(geojson, srid=4326)
        shapes.extend(geom if isinstance(geom, MultiPolygon) else [geom])
        pairs.append(
            {
                "a": a_label,
                "b": b_label,
                "a_id": a_id,
                "b_id": b_id,
                "area_ha": round(area / 10000, 4),
                "geometry": json.loads(geojson),
            }
        )
    union_ha = 0.0
    if shapes:
        union = MultiPolygon(*shapes, srid=4326).unary_union
        union_ha = float(aset_geo.area_m2(union) or 0) / 10000
    total_a = _polygon_area_ha(from_a, where_a, params_a)
    total_b = _polygon_area_ha(from_b, where_b, params_b)
    return {
        "a": {"key": key_a, "name": name_a, "area_ha": round(total_a, 4)},
        "b": {"key": key_b, "name": name_b, "area_ha": round(total_b, 4)},
        "overlap_ha": round(union_ha, 4),
        "pct_a": round(union_ha * 100 / total_a, 1) if total_a else None,
        "pct_b": round(union_ha * 100 / total_b, 1) if total_b else None,
        "pairs": pairs,
        "truncated": truncated,
    }


def overlap_csv(data: dict) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [data["a"]["name"], data["b"]["name"], _("Luas tumpang tindih (ha)")]
    )
    for row in data["pairs"]:
        writer.writerow(
            [
                neutralize_formula(row["a"]),
                neutralize_formula(row["b"]),
                neutralize_formula(row["area_ha"]),
            ]
        )
    writer.writerow([])
    writer.writerow([_("Total tumpang tindih (ha)"), data["overlap_ha"]])
    return buffer.getvalue()


# --------------------------------------------------------------------------
# Audit kepatuhan RTRW (titik warga vs lapisan tata ruang)
# --------------------------------------------------------------------------

AUDIT_LABELS = {
    "sesuai": _("Sesuai"),
    "beda": _("Tidak sesuai dengan zona tercatat"),
    "belum_dinilai": _("Terdeteksi, belum dinilai"),
    "tak_dikenali": _("Di lapisan, zona tak dikenali"),
    "di_luar": _("Di luar lapisan tata ruang"),
    "tanpa_lokasi": _("Tanpa lokasi"),
}


def _audit_category(resident, entry, recorded: str, detected: str) -> str:
    if resident.location is None:
        return "tanpa_lokasi"
    if entry is None:
        return "di_luar"
    if not detected:
        return "tak_dikenali"
    if recorded == RtrwZone.UNASSESSED:
        return "belum_dinilai"
    return "sesuai" if recorded == detected else "beda"


def rtrw_audit(user, korwil=None) -> dict:
    residents = geo.scoped(Resident.objects.all(), user).select_related("korwil")
    if korwil is not None:
        residents = residents.filter(korwil=korwil)
    overlays = list(command_overlays().filter(kind__in=ZONE_OVERLAY_KINDS))
    overlay_ids = [o.pk for o in overlays]
    sql, params = _sql(residents.exclude(location__isnull=True))
    hits = _hits(
        Resident._meta.db_table, "location", f"t.id IN ({sql})", params, overlay_ids
    )
    features = _zone_features(overlay_ids)
    by_resident = defaultdict(lambda: {"zones": set(), "layers": set()})
    for resident_id, feature_id in hits:
        data = features.get(feature_id)
        if not data:
            continue
        entry = by_resident[resident_id]
        entry["layers"].add(data["overlay__name"])
        zone = feature_zone(data["overlay__kind"], data["name"], data["properties"])
        if zone:
            entry["zones"].add(zone)
    zone_labels = dict(RtrwZone.choices)
    rows, counts = [], Counter()
    per_korwil = defaultdict(Counter)
    for resident in residents.order_by("korwil__code", "number")[:MAX_AUDIT_ROWS]:
        recorded = resident.rtrw_zone or RtrwZone.UNASSESSED
        entry = by_resident.get(resident.pk)
        detected = _best_zone(entry["zones"]) if entry else ""
        category = _audit_category(resident, entry, recorded, detected)
        counts[category] += 1
        code = resident.korwil.code if resident.korwil_id else "-"
        per_korwil[code][category] += 1
        rows.append(
            {
                "id": resident.pk,
                "number": resident.number,
                "name": resident.head_name,
                "korwil": code,
                "recorded": str(zone_labels.get(recorded, recorded)),
                "detected": str(zone_labels.get(detected, "")) if detected else "",
                "layers": sorted(entry["layers"]) if entry else [],
                "category": category,
                "category_label": str(AUDIT_LABELS[category]),
                "center": (
                    [resident.location.y, resident.location.x]
                    if resident.location
                    else None
                ),
            }
        )
    assessed = counts["sesuai"] + counts["beda"]
    return {
        "layers": [o.name for o in overlays],
        "counts": {key: counts[key] for key in AUDIT_LABELS},
        "labels": {key: str(label) for key, label in AUDIT_LABELS.items()},
        "conform_pct": services.pct(counts["sesuai"], assessed),
        "korwils": [
            {"code": code, **{key: c[key] for key in AUDIT_LABELS}}
            for code, c in sorted(per_korwil.items())
        ],
        "rows": rows,
        "truncated": residents.count() > MAX_AUDIT_ROWS,
    }


def audit_csv(data: dict) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            _("Nomor"),
            _("Kepala keluarga"),
            _("Korwil"),
            _("Zona tercatat"),
            _("Zona terdeteksi"),
            _("Lapisan"),
            _("Hasil audit"),
            _("Lintang"),
            _("Bujur"),
        ]
    )
    for row in data["rows"]:
        center = row["center"] or ["", ""]
        writer.writerow(
            [
                neutralize_formula(row["number"]),
                neutralize_formula(row["name"]),
                neutralize_formula(row["korwil"]),
                neutralize_formula(row["recorded"]),
                neutralize_formula(row["detected"]),
                neutralize_formula("; ".join(row["layers"])),
                neutralize_formula(row["category_label"]),
                neutralize_formula(center[0]),
                neutralize_formula(center[1]),
            ]
        )
    return buffer.getvalue()


# --------------------------------------------------------------------------
# Anomali & skor risiko Korwil
# --------------------------------------------------------------------------

LEVEL_ORDER = {"kritis": 0, "tinggi": 1, "sedang": 2, "rendah": 3}


def risk_level(contra_pct) -> str:
    if contra_pct is None:
        return ""
    if contra_pct >= CONTRA_CRITICAL_PCT:
        return "kritis"
    if contra_pct >= CONTRA_HIGH_PCT:
        return "tinggi"
    if contra_pct >= 20:
        return "sedang"
    return "rendah"


def korwil_risks(user) -> list[dict]:
    residents = geo.scoped(Resident.objects.exclude(korwil=None), user)
    stances = defaultdict(Counter)
    for korwil_id, stance, n in (
        residents.order_by()
        .values_list("korwil", "stance")
        .annotate(n=Count("pk", distinct=True))
    ):
        stances[korwil_id][stance] += n
    rows = []
    for korwil in services.visible_korwils(user).order_by("code"):
        counter = stances.get(korwil.pk, Counter())
        known = sum(counter.values()) - counter[Stance.UNKNOWN]
        contra_pct = (
            round(counter[Stance.OPPOSE] * 100 / known)
            if known >= CONTRA_MIN_KNOWN
            else None
        )
        rows.append(
            {
                "id": korwil.pk,
                "code": korwil.code,
                "name": korwil.name,
                "known": known,
                "contra": counter[Stance.OPPOSE],
                "contra_pct": contra_pct,
                "level": risk_level(contra_pct),
                "center": (
                    [
                        korwil.geometry.point_on_surface.y,
                        korwil.geometry.point_on_surface.x,
                    ]
                    if korwil.geometry is not None and not korwil.geometry.empty
                    else None
                ),
            }
        )
    return rows


def _point(location):
    return [location.y, location.x] if location is not None else None


def _name(user) -> str:
    if user is None:
        return "-"
    return user.get_full_name() or user.get_username()


def _contra_anomaly(risks):
    items = [
        {
            "label": f"{r['code']} {r['name']}",
            "detail": _("%(pct)s%% kontra dari %(n)s warga bersikap")
            % {"pct": r["contra_pct"], "n": r["known"]},
            "center": r["center"],
            "level": r["level"],
        }
        for r in risks
        if r["contra_pct"] is not None and r["contra_pct"] > CONTRA_HIGH_PCT
    ]
    if not items:
        return None
    critical = any(i["level"] == "kritis" for i in items)
    return {
        "kind": "kontra",
        "level": "kritis" if critical else "tinggi",
        "title": _("Korwil dengan warga kontra di atas %(pct)s%%")
        % {"pct": CONTRA_HIGH_PCT},
        "items": items,
    }


def _sos_anomaly(user, now):
    if not user.has_perm("operasi.view_sosalert"):
        return None
    alerts = geo.scoped(
        SosAlert.objects.filter(
            status__in=enums.OPEN_SOS_STATUSES,
            created_at__lt=now - datetime.timedelta(minutes=SOS_OPEN_MINUTES),
        ),
        user,
    ).select_related("raised_by")
    items = [
        {
            "label": f"{alert.number} · {_name(alert.raised_by)}",
            "detail": _("Terbuka sejak %(time)s")
            % {"time": timezone.localtime(alert.created_at).strftime("%d-%m %H:%M")},
            "center": _point(alert.location),
        }
        for alert in alerts[:20]
    ]
    if not items:
        return None
    return {
        "kind": "sos",
        "level": "kritis",
        "title": _("SOS belum selesai lebih dari %(n)s menit")
        % {"n": SOS_OPEN_MINUTES},
        "items": items,
    }


def _position_anomalies(user, now):
    from operasi.models import CommandSettings, Korwil

    if not user.has_perm("operasi.view_officerposition"):
        return []
    since = now - datetime.timedelta(minutes=CommandSettings.load().online_minutes)
    positions = list(
        OfficerPosition.objects.filter(
            updated_at__gte=since, user__in=services.visible_officers(user)
        ).select_related("user")
    )
    outside, threatened = [], []
    zones = list(
        geo.scoped(
            ThreatZone.objects.filter(
                is_active=True,
                level__in=[enums.ThreatLevel.HIGH, enums.ThreatLevel.CRITICAL],
            ),
            user,
        )
    )
    for position in positions:
        korwils = list(
            Korwil.objects.filter(
                Q(members=position.user) | Q(coordinator=position.user),
                is_active=True,
            )
            .exclude(geometry__isnull=True)
            .distinct()
        )
        if korwils and not any(
            geo.in_area(k, position.location, OUTSIDE_TOLERANCE_M) for k in korwils
        ):
            outside.append(
                {
                    "label": _name(position.user),
                    "detail": _("Di luar %(korwil)s")
                    % {"korwil": ", ".join(k.code for k in korwils)},
                    "center": _point(position.location),
                }
            )
        for zone in zones:
            if zone.geometry.intersects(position.location):
                threatened.append(
                    {
                        "label": _name(position.user),
                        "detail": _("Di zona %(zone)s (%(level)s)")
                        % {"zone": zone.name, "level": zone.get_level_display()},
                        "center": _point(position.location),
                    }
                )
                break
    result = []
    if threatened:
        result.append(
            {
                "kind": "zona",
                "level": "kritis",
                "title": _("Petugas berada di zona ancaman tinggi/kritis"),
                "items": threatened,
            }
        )
    if outside:
        result.append(
            {
                "kind": "luar",
                "level": "sedang",
                "title": _("Posisi Live di luar Korwil sendiri"),
                "items": outside,
            }
        )
    return result


def _checkin_anomaly(user, today):
    if not user.has_perm("operasi.view_attendance"):
        return None
    records = Attendance.objects.filter(
        date=today,
        check_in_in_area=False,
        user__in=services.team_users(user),
    ).select_related("user", "korwil")
    items = [
        {
            "label": _name(record.user),
            "detail": _("Absen masuk %(time)s di luar %(korwil)s")
            % {
                "time": (
                    timezone.localtime(record.check_in_at).strftime("%H:%M")
                    if record.check_in_at
                    else "-"
                ),
                "korwil": record.korwil.code if record.korwil_id else _("wilayah"),
            },
            "center": _point(record.check_in_location),
        }
        for record in records[:30]
    ]
    if not items:
        return None
    return {
        "kind": "absen",
        "level": "sedang",
        "title": _("Absen masuk di luar wilayah hari ini"),
        "items": items,
    }


def _task_anomaly(user, today):
    from operasi import task_flow

    if not user.has_perm("asetlahan.view_task"):
        return None
    tasks = (
        task_flow.visible_tasks(user)
        .filter(
            status__in=aset_enums.OPEN_TASK_STATUSES,
            due_date__lt=today - datetime.timedelta(days=TASK_OVERDUE_DAYS),
        )
        .select_related("assignee")
        .order_by("due_date")
    )
    total = tasks.count()
    if not total:
        return None
    return {
        "kind": "tugas",
        "level": "tinggi" if total >= 5 else "sedang",
        "title": _("Tugas lewat tenggat lebih dari %(n)s hari (%(total)s)")
        % {"n": TASK_OVERDUE_DAYS, "total": total},
        "items": [
            {
                "label": task.title,
                "detail": _("%(who)s · tenggat %(date)s")
                % {
                    "who": _name(task.assignee) if task.assignee_id else "-",
                    "date": task.due_date.strftime("%d-%m-%Y"),
                },
                "center": None,
            }
            for task in tasks[:10]
        ],
    }


def _report_anomaly(user, now):
    from operasi import daily_reports

    if not user.has_perm("operasi.view_dailyreport"):
        return None
    reports = (
        daily_reports.visible_reports(user)
        .filter(
            status=enums.DailyReportStatus.SENT,
            sent_at__lt=now - datetime.timedelta(days=REPORT_PENDING_DAYS),
        )
        .order_by("sent_at")
    )
    total = reports.count()
    if not total:
        return None
    return {
        "kind": "laporan",
        "level": "sedang",
        "title": _("Laporan harian belum ditinjau lebih dari %(n)s hari (%(total)s)")
        % {"n": REPORT_PENDING_DAYS, "total": total},
        "items": [
            {
                "label": f"{report.number} · {_name(report.author)}",
                "detail": _("Menunggu %(who)s sejak %(date)s")
                % {
                    "who": _name(report.recipient) if report.recipient_id else "-",
                    "date": timezone.localtime(report.sent_at).strftime("%d-%m-%Y"),
                },
                "center": None,
            }
            for report in reports[:10]
        ],
    }


def anomalies(user) -> dict:
    now = timezone.now()
    today = timezone.localdate()
    risks = korwil_risks(user)
    found = [
        _contra_anomaly(risks),
        _sos_anomaly(user, now),
        *_position_anomalies(user, now),
        _checkin_anomaly(user, today),
        _task_anomaly(user, today),
        _report_anomaly(user, now),
    ]
    items = sorted(
        (str_title(a) for a in found if a), key=lambda a: LEVEL_ORDER[a["level"]]
    )
    return {"anomalies": items, "risks": risks, "checked_at": now.isoformat()}


def str_title(anomaly: dict) -> dict:
    anomaly["title"] = str(anomaly["title"])
    for item in anomaly["items"]:
        item["label"] = str(item["label"])
        item["detail"] = str(item["detail"])
    return anomaly


# --------------------------------------------------------------------------
# Peta panas & jejak GPS
# --------------------------------------------------------------------------


def heat_cells(user, source: str, start, end) -> dict:
    if source == "kegiatan":
        if not user.has_perm("operasi.view_activity"):
            raise ValidationError({"sumber": [_("Sumber tidak tersedia.")]})
        queryset = geo.scoped(
            Activity.objects.filter(
                started_at__date__gte=start, started_at__date__lte=end
            ),
            user,
        )
    elif source == "posisi":
        if not user.has_perm("operasi.view_officertrackpoint"):
            raise ValidationError({"sumber": [_("Sumber tidak tersedia.")]})
        queryset = OfficerTrackPoint.objects.filter(
            recorded_at__date__gte=start,
            recorded_at__date__lte=end,
            user__in=services.visible_officers(user),
        )
    elif source == "warga":
        if not user.has_perm("operasi.view_resident"):
            raise ValidationError({"sumber": [_("Sumber tidak tersedia.")]})
        queryset = geo.scoped(Resident.objects.all(), user)
    else:
        raise ValidationError({"sumber": [_("Sumber tidak tersedia.")]})
    rows = (
        queryset.exclude(location__isnull=True)
        .annotate(cell=SnapToGrid("location", HEAT_CELL_DEG))
        .order_by()
        .values("cell")
        .annotate(n=Count("pk"))
    )
    cells = [
        [round(row["cell"].y, 6), round(row["cell"].x, 6), row["n"]]
        for row in rows
        if row["cell"] is not None
    ]
    return {
        "source": source,
        "size": HEAT_CELL_DEG,
        "cells": cells,
        "max": max((c[2] for c in cells), default=0),
        "total": sum(c[2] for c in cells),
        "start": start.isoformat(),
        "end": end.isoformat(),
    }


def record_track(user, location, accuracy, moment=None) -> bool:
    """Simpan titik jejak bila sudah cukup jauh atau cukup lama dari titik terakhir."""
    moment = moment or timezone.now()
    last = (
        OfficerTrackPoint.objects.filter(user=user)
        .order_by("-recorded_at")
        .only("location", "recorded_at")
        .first()
    )
    if last is not None:
        elapsed = (moment - last.recorded_at).total_seconds()
        srid = aset_geo.utm_srid(location)
        moved = last.location.transform(srid, clone=True).distance(
            location.transform(srid, clone=True)
        )
        if elapsed < TRACK_MIN_SECONDS and moved < TRACK_MIN_METERS:
            return False
    OfficerTrackPoint.objects.create(
        user=user, location=location, accuracy_m=accuracy, recorded_at=moment
    )
    return True


def prune_tracks() -> int:
    cutoff = timezone.now() - datetime.timedelta(days=TRACK_KEEP_DAYS)
    deleted, _rows = OfficerTrackPoint.objects.filter(recorded_at__lt=cutoff).delete()
    return deleted


def track(officer, day) -> dict:
    points = list(
        OfficerTrackPoint.objects.filter(user=officer, recorded_at__date=day).order_by(
            "recorded_at"
        )[:MAX_TRACK_POINTS]
    )
    distance = 0.0
    if len(points) > 1:
        line = LineString([p.location.coords for p in points], srid=4326)
        distance = float(line.transform(aset_geo.utm_srid(line), clone=True).length)
    return {
        "officer": {"id": officer.pk, "name": _name(officer)},
        "date": day.isoformat(),
        "points": [
            {
                "lat": round(p.location.y, 7),
                "lng": round(p.location.x, 7),
                "time": timezone.localtime(p.recorded_at).strftime("%H:%M:%S"),
                "accuracy": float(p.accuracy_m) if p.accuracy_m is not None else None,
            }
            for p in points
        ],
        "distance_km": round(distance / 1000, 2),
        "start": (
            timezone.localtime(points[0].recorded_at).strftime("%H:%M")
            if points
            else ""
        ),
        "end": (
            timezone.localtime(points[-1].recorded_at).strftime("%H:%M")
            if points
            else ""
        ),
    }


# --------------------------------------------------------------------------
# Zona ancaman
# --------------------------------------------------------------------------

MAX_THREAT_RADIUS_M = 20_000


def circle(lat: float, lng: float, radius_m: float) -> MultiPolygon:
    center = Point(lng, lat, srid=4326)
    srid = aset_geo.utm_srid(center)
    projected = center.transform(srid, clone=True).buffer(radius_m, quadsegs=16)
    projected.srid = srid
    return aset_geo.as_multipolygon(projected.transform(4326, clone=True))


def threat_geometry(data) -> MultiPolygon:
    """Area zona dari GeoJSON poligon atau titik pusat + radius (meter)."""
    text = (data.get("geometry") or "").strip()
    if text:
        try:
            geom = GEOSGeometry(text, srid=4326)
        except Exception:  # noqa: BLE001 - masukan GeoJSON bebas
            raise ValidationError({"geometry": [_("Geometri zona tidak sah.")]})
        multi = aset_geo.as_multipolygon(geom)
        if multi is not None and not multi.valid:
            multi = aset_geo.as_multipolygon(multi.buffer(0))
        if multi is None or multi.empty:
            raise ValidationError({"geometry": [_("Zona harus berupa poligon.")]})
        return multi
    try:
        lat = float(data.get("lat"))
        lng = float(data.get("lng"))
        radius = float(data.get("radius"))
    except (TypeError, ValueError):
        raise ValidationError(
            {"geometry": [_("Tentukan titik pusat dan radius, atau gambar poligon.")]}
        )
    if not (-90 <= lat <= 90 and -180 <= lng <= 180) or not (
        10 <= radius <= MAX_THREAT_RADIUS_M
    ):
        raise ValidationError(
            {
                "radius": [
                    _("Radius 10–%(max)s m dengan titik pusat yang sah.")
                    % {"max": MAX_THREAT_RADIUS_M}
                ]
            }
        )
    return circle(lat, lng, radius)
