"""AI Satelit: analisis kotak area yang digambar di peta.

Citra satelit area diunduh dari server ubin (bawaan Esri World Imagery, dapat
diganti di pengaturan), dijahit menjadi satu gambar, lalu dianalisis Claude
(tutupan lahan, perkiraan jumlah bangunan, temuan) bila ``ANTHROPIC_API_KEY``
diisi. Tanpa kunci AI, hasil tetap berisi mosaik citra dan ringkasan data
SimLahan di dalam area (warga, lahan, kegiatan, uji tanah, bidang, aset).
"""

import base64
import io
import json
import logging
import math
from concurrent.futures import ThreadPoolExecutor

import requests
from django.conf import settings
from django.contrib.gis.geos import Polygon
from django.core.files.base import ContentFile
from django.db.models import Count, Q
from django.utils.translation import gettext as _

from asetlahan import ai
from asetlahan import enums as aset_enums
from asetlahan.geo import area_m2
from operasi import enums
from operasi.models import (
    RELEASED_PARCEL_STATUSES,
    Activity,
    AreaAnalysis,
    CommandSettings,
    Resident,
    SoilTest,
)

LOG = logging.getLogger(__name__)

TILE_SIZE = 256
MAX_TILES = 36
MAX_ZOOM = 18
MIN_ZOOM = 12
MAX_AREA_KM2 = 25
MAX_IMAGE_SIDE = 1568


class AnalysisError(Exception):
    pass


def parse_bbox(values) -> Polygon:
    """[selatan, barat, utara, timur] → Polygon EPSG:4326 yang sudah divalidasi."""
    try:
        south, west, north, east = (float(v) for v in values)
    except (TypeError, ValueError):
        raise AnalysisError(_("Kotak area tidak sah."))
    if not (-85 <= south < north <= 85 and -180 <= west < east <= 180):
        raise AnalysisError(_("Kotak area tidak sah."))
    polygon = Polygon.from_bbox((west, south, east, north))
    polygon.srid = 4326
    size_km2 = float(area_m2(polygon) or 0) / 1_000_000
    if size_km2 > MAX_AREA_KM2:
        raise AnalysisError(
            _("Area terlalu luas (%(size).1f km²). Maksimal %(max)s km².")
            % {"size": size_km2, "max": MAX_AREA_KM2}
        )
    if size_km2 < 0.0001:
        raise AnalysisError(_("Area terlalu kecil. Seret kotak yang lebih besar."))
    return polygon


def _tile_xy(lat, lng, zoom) -> tuple[float, float]:
    n = 2**zoom
    x = (lng + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return x, y


def choose_zoom(polygon: Polygon) -> int:
    west, south, east, north = polygon.extent
    for zoom in range(MAX_ZOOM, MIN_ZOOM - 1, -1):
        x0, y0 = _tile_xy(north, west, zoom)
        x1, y1 = _tile_xy(south, east, zoom)
        count = (int(x1) - int(x0) + 1) * (int(y1) - int(y0) + 1)
        if count <= MAX_TILES:
            return zoom
    return MIN_ZOOM


def _fetch_tile(url: str) -> bytes | None:
    try:
        response = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": f"{settings.APP_NAME} (AI Satelit)"},
        )
    except requests.RequestException:
        return None
    if response.status_code != 200 or not response.content:
        return None
    return response.content


def mosaic(polygon: Polygon, zoom: int, template: str) -> bytes:
    """Unduh & jahit ubin, potong tepat sesuai kotak, kembalikan PNG."""
    from PIL import Image

    west, south, east, north = polygon.extent
    fx0, fy0 = _tile_xy(north, west, zoom)
    fx1, fy1 = _tile_xy(south, east, zoom)
    tx0, ty0, tx1, ty1 = int(fx0), int(fy0), int(fx1), int(fy1)
    jobs = [
        (
            x,
            y,
            template.replace("{z}", str(zoom))
            .replace("{x}", str(x))
            .replace("{y}", str(y)),
        )
        for y in range(ty0, ty1 + 1)
        for x in range(tx0, tx1 + 1)
    ]
    with ThreadPoolExecutor(max_workers=6) as pool:
        tiles = list(pool.map(lambda job: _fetch_tile(job[2]), jobs))
    if not any(tiles):
        raise AnalysisError(_("Citra satelit tidak dapat diunduh dari server ubin."))
    canvas = Image.new(
        "RGB", ((tx1 - tx0 + 1) * TILE_SIZE, (ty1 - ty0 + 1) * TILE_SIZE), "#1f2328"
    )
    for (x, y, _url), data in zip(jobs, tiles):
        if not data:
            continue
        try:
            tile = Image.open(io.BytesIO(data)).convert("RGB")
        except Exception:  # noqa: BLE001 - ubin rusak dilewati
            continue
        if tile.size != (TILE_SIZE, TILE_SIZE):
            tile = tile.resize((TILE_SIZE, TILE_SIZE))
        canvas.paste(tile, ((x - tx0) * TILE_SIZE, (y - ty0) * TILE_SIZE))
    left = round((fx0 - tx0) * TILE_SIZE)
    top = round((fy0 - ty0) * TILE_SIZE)
    right = max(round((fx1 - tx0) * TILE_SIZE), left + 1)
    bottom = max(round((fy1 - ty0) * TILE_SIZE), top + 1)
    image = canvas.crop((left, top, right, bottom))
    if max(image.size) > MAX_IMAGE_SIDE:
        image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def data_summary(polygon: Polygon, user) -> dict:
    """Ringkasan data SimLahan di dalam area (mengikuti hak lihat pengguna)."""
    from operasi import geo
    from operasi.services import released_q

    summary = {"luas_ha": round(float(area_m2(polygon) or 0) / 10_000, 2)}
    if user.has_perm("operasi.view_resident"):
        residents = geo.scoped(Resident.objects.filter(location__within=polygon), user)
        summary["warga"] = residents.aggregate(
            total=Count("pk"),
            pro=Count("pk", filter=Q(stance=enums.Stance.SUPPORT)),
            menolak=Count("pk", filter=Q(stance=enums.Stance.OPPOSE)),
            lahan_sudah=Count("pk", filter=released_q()),
            rtrw_sesuai=Count("pk", filter=Q(rtrw_status=enums.RtrwStatus.CONFORM)),
        )
    if user.has_perm("operasi.view_activity"):
        summary["kegiatan"] = geo.scoped(
            Activity.objects.filter(location__within=polygon), user
        ).count()
    if user.has_perm("operasi.view_soiltest"):
        rows = (
            geo.scoped(SoilTest.objects.filter(location__within=polygon), user)
            .values("suitability")
            .annotate(n=Count("pk"))
        )
        labels = dict(enums.SoilSuitability.choices)
        summary["uji_tanah"] = {str(labels[r["suitability"]]): r["n"] for r in rows}
    if user.has_perm("pengadaan.view_acquisitionparcel"):
        from pengadaan.models import AcquisitionParcel

        parcels = AcquisitionParcel.objects.filter(geometry__intersects=polygon)
        summary["bidang_pengadaan"] = parcels.aggregate(
            total=Count("pk"),
            lepas=Count("pk", filter=Q(status__in=RELEASED_PARCEL_STATUSES)),
        )
    if user.has_perm("asetlahan.view_landasset"):
        from asetlahan import scope as aset_scope
        from asetlahan.models import EncroachmentCase, LandAsset

        summary["aset_lahan"] = aset_scope.scoped(
            LandAsset.objects.filter(geometry__intersects=polygon), user
        ).count()
        summary["okupasi_terbuka"] = aset_scope.scoped(
            EncroachmentCase.objects.filter(
                Q(location__within=polygon) | Q(area_geometry__intersects=polygon),
                status__in=aset_enums.OPEN_ENCROACHMENT_STATUSES,
            ),
            user,
        ).count()
    return summary


AI_SCHEMA = {
    "type": "object",
    "properties": {
        "tutupan_lahan": {
            "type": "object",
            "properties": {
                "vegetasi_pct": {"type": "number"},
                "bangunan_pct": {"type": "number"},
                "lahan_terbuka_pct": {"type": "number"},
                "air_pct": {"type": "number"},
                "jalan_pct": {"type": "number"},
            },
            "required": [
                "vegetasi_pct",
                "bangunan_pct",
                "lahan_terbuka_pct",
                "air_pct",
                "jalan_pct",
            ],
            "additionalProperties": False,
        },
        "perkiraan_jumlah_bangunan": {"type": "integer"},
        "temuan": {"type": "array", "items": {"type": "string"}},
        "rekomendasi": {"type": "array", "items": {"type": "string"}},
        "ringkasan": {"type": "string"},
    },
    "required": [
        "tutupan_lahan",
        "perkiraan_jumlah_bangunan",
        "temuan",
        "rekomendasi",
        "ringkasan",
    ],
    "additionalProperties": False,
}

AI_PROMPT = (
    "Ini citra satelit sebuah area di wilayah kerja pengadaan/pengelolaan lahan "
    "(utara di atas, luas {luas} ha). Data lapangan SimLahan di area ini: {data}. "
    "Perkirakan persentase tutupan lahan (jumlah 100), perkiraan jumlah bangunan "
    "yang terlihat, temuan penting (permukiman, pembukaan lahan baru, tambak, "
    "pantai/mangrove, akses jalan, potensi okupasi), dan rekomendasi tindak lanjut "
    "untuk tim lapangan. Jawab dalam bahasa Indonesia, ringkas, dan sebutkan bila "
    "citra kurang jelas. Jangan mengarang hal yang tidak terlihat."
)


def ai_analyze(image: bytes, summary: dict) -> dict:
    response = ai.create(
        max_tokens=3000,
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": AI_SCHEMA},
        },
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": base64.standard_b64encode(image).decode(),
                        },
                    },
                    {
                        "type": "text",
                        "text": AI_PROMPT.format(
                            luas=summary.get("luas_ha"),
                            data=json.dumps(summary, ensure_ascii=False),
                        ),
                    },
                ],
            }
        ],
    )
    try:
        return json.loads(ai.text_of(response))
    except json.JSONDecodeError:
        raise ai.AIError(_("Jawaban layanan AI tidak dapat dibaca."))


def analyze(bbox_values, user) -> AreaAnalysis:
    polygon = parse_bbox(bbox_values)
    config = CommandSettings.load()
    zoom = choose_zoom(polygon)
    analysis = AreaAnalysis(bbox=polygon, requested_by=user, zoom=zoom)
    analysis.data_summary = data_summary(polygon, user)
    image = b""
    try:
        image = mosaic(polygon, zoom, config.satellite_tile_url)
    except AnalysisError as error:
        analysis.error = str(error)
    if image:
        analysis.image.save("citra.png", ContentFile(image), save=False)
        if ai.enabled():
            try:
                analysis.ai_result = ai_analyze(image, analysis.data_summary)
                analysis.ai_model = ai.model()
            except ai.AIError as error:
                analysis.error = str(error)
    analysis.save()
    return analysis
