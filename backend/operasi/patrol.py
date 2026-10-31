"""Impor ekspor patroli SMART Mobile / CyberTracker (GeoJSON).

Satu berkas berisi titik jalur (tanpa ``sighting``) dan observasi (dengan
``sighting``: tipe, komentar, atribut, foto base64). Hasil baca dipakai untuk
mengisi otomatis laporan patroli Taman Buru dan disimpan sebagai
``PatrolSession`` beserta observasi dan fotonya.
"""

import base64
import binascii
import datetime
import json
import math
import re
import uuid

from django.contrib.gis.geos import LineString, Point
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _

from operasi import enums

MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_FEATURES = 20000
MAX_PHOTOS = 200
MAX_PHOTO_BYTES = 5 * 1024 * 1024
# Nilai kode SMART (mis. "a:xyz", "l:..."), bukan teks yang dapat dibaca.
_CODED = re.compile(r"^(l|t|e|pm|pt|ps|tt|c|i|d|u|a):", re.I)
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
_GRID = re.compile(r"\bTB\w*?\d+\b", re.I)
_ATTR = re.compile(r"^([^:]{2,40}?)\s*:\s*(.+?)\.?$")
_ILLEGAL_WORDS = re.compile(
    r"(KEBUN|LADANG|RAMBAH|PERAMBAHAN|TEBANG|PENEBANGAN|LOGGING|GERGAJI|GUBUK|"
    r"PONDOK|JERAT|PERBURUAN|\bBURU\b|SAWIT|ARANG|PEMBUKAAN LAHAN|PENJAGA|ILEGAL|"
    r"ILLEGAL|TAMBANG)"
)
_FAUNA_WORDS = re.compile(
    r"(BABI|KUBANGAN|JEJAK|TAPAK|KOTORAN|FESES|SARANG|HARIMAU|RUSA|KIJANG|BURUNG|"
    r"ULAR|BIAWAK|MONYET|BERUANG|SATWA|FAUNA|MAMALIA|REPTIL|TRENGGILING|RANGKONG|"
    r"KUKANG|LANDAK|TERNAK)"
)
_FLORA_WORDS = re.compile(
    r"(POHON|KAYU|TANAMAN|BUNGA|ANGGREK|FLORA|TEGAKAN|SEMAI|TUMBUHAN|MERANTI|"
    r"MIRANTI|BELIMBING|PAKIS|ROTAN|BAMBU)"
)
_FINDING_WORDS = re.compile(r"\bTEMUAN\b|\bDITEMUKAN\b|\bJUMPA\b|\bMELIHAT\b")
_NOTE_WORDS = re.compile(
    r"^(SELESAI|MULAI|MEMULAI|MENGAKHIRI|MELAKUKAN PATROLI|PATROLI BERSAMA|"
    r"PATROLI DI|PATROLI RUTIN|ISTIRAHAT|TIBA|BERANGKAT|MENUJU|KEMBALI|SAMPAI|"
    r"TITIK|BERHENTI|MELANJUTKAN)\b"
)
_PLACE_WORDS = re.compile(r"GRID|SUNGAI|DUSUN|DESA|KAMPUNG|RPG", re.I)
_JPEG = b"\xff\xd8\xff"
_PNG = b"\x89PNG\r\n\x1a\n"


def _readable(value) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    return not (
        len(text) < 2
        or _CODED.match(text)
        or text in ("True", "False")
        or _NUMBER.match(text)
    )


def _coded(value) -> bool:
    return isinstance(value, str) and bool(_CODED.match(value.strip()))


def haversine(a, b) -> float:
    radius = 6371000
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    d_lat = lat2 - lat1
    d_lng = math.radians(b[0] - a[0])
    h = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(h))


def _coord(geometry, props):
    coords = (geometry or {}).get("coordinates") or [
        props.get("longitude"),
        props.get("latitude"),
    ]
    try:
        lng, lat = float(coords[0]), float(coords[1])
    except (TypeError, ValueError, IndexError):
        return None
    if not (-180 <= lng <= 180 and -90 <= lat <= 90):
        return None
    return lng, lat


def _photo(value: str) -> bytes | None:
    try:
        data = base64.b64decode(value.split(",", 1)[-1], validate=False)
    except (binascii.Error, ValueError):
        return None
    if len(data) > MAX_PHOTO_BYTES or not data.startswith((_JPEG, _PNG)):
        return None
    return data


def _time(value) -> datetime.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    moment = parse_datetime(value.strip())
    if moment is None:
        return None
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment)
    return moment


META_KEYS = (
    "SMART_PatrolID",
    "SMART_Objective",
    "SMART_Comments",
    "SMART_Leader",
    "SMART_Team",
    "SMART_Station",
    "SMART_PatrolTransport",
)


def _features(raw: bytes) -> list:
    if len(raw) > MAX_FILE_BYTES:
        raise ValidationError(_("Berkas SMART maksimal 15 MB."))
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValidationError(_("Berkas SMART harus GeoJSON (.json) yang sah."))
    features = data.get("features") if isinstance(data, dict) else None
    if not isinstance(features, list) or len(features) > MAX_FEATURES:
        raise ValidationError(_("Berkas SMART tidak dikenali atau terlalu besar."))
    return features


def _images(sighting: dict, budget: int) -> list[bytes]:
    images = []
    for key, value in sighting.items():
        if len(images) >= budget:
            break
        if (
            str(key).startswith("SMART_Photo")
            and isinstance(value, str)
            and len(value) > 100
        ):
            image = _photo(value)
            if image:
                images.append(image)
    return images


def _leg(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _observation(sighting: dict, coord, when: str, budget: int) -> dict:
    values = [
        str(v).strip()
        for k, v in sighting.items()
        if str(k).startswith("a:") and _readable(v)
    ]
    main = max(values, key=len) if values else ""
    if not main:
        main = str(sighting.get("SMART_Comments") or "").strip()
    details = [v for v in values if v != main]
    return {
        "kind": str(sighting.get("SMART_ObservationType") or "Observation")[:64],
        "lng": coord[0],
        "lat": coord[1],
        "time": when,
        "comment": main[:5000],
        "details": [d[:500] for d in details[:20]],
        "photos": _images(sighting, budget),
        "leg": _leg(sighting.get("SMART_PatrolLegDistance")),
        "meta": {key: sighting.get(key) for key in META_KEYS},
    }


def _meta(track, observations, distance) -> dict:
    start = next((o for o in observations if o["kind"] == "NewPatrol"), None)
    head = (start or {}).get("meta") or {}
    times = sorted(
        t for t in [t[2] for t in track] + [o["time"] for o in observations] if t
    )

    def text(key, size):
        value = head.get(key)
        return str(value).strip()[:size] if isinstance(value, (str, int, float)) else ""

    return {
        "patrol_id": text("SMART_PatrolID", 128),
        "objective": text("SMART_Objective", 255),
        "comments": text("SMART_Comments", 5000),
        "leader": text("SMART_Leader", 255),
        "team": text("SMART_Team", 255),
        "station": text("SMART_Station", 255),
        "transport": text("SMART_PatrolTransport", 128),
        "started": times[0] if times else "",
        "ended": times[-1] if times else "",
        "distance_m": round(distance),
    }


def parse(raw: bytes) -> dict:
    """Baca berkas GeoJSON SMART; ValidationError bila tidak dikenali."""
    track, observations, photos = [], [], 0
    for item in _features(raw):
        props = item.get("properties") if isinstance(item, dict) else None
        if not isinstance(props, dict):
            continue
        coord = _coord(item.get("geometry"), props)
        if coord is None:
            continue
        when = props.get("dateTime") if isinstance(props.get("dateTime"), str) else ""
        sighting = props.get("sighting")
        if not isinstance(sighting, dict):
            track.append((coord[0], coord[1], when))
            continue
        observation = _observation(sighting, coord, when, MAX_PHOTOS - photos)
        photos += len(observation["photos"])
        observations.append(observation)
    if not track and not observations:
        raise ValidationError(_("Berkas SMART tidak berisi jalur atau observasi."))
    track.sort(key=lambda t: t[2])
    coords = [(t[0], t[1]) for t in track]
    distance = sum(haversine(coords[i - 1], coords[i]) for i in range(1, len(coords)))
    observations.sort(key=lambda o: o["time"])
    return {
        "meta": _meta(track, observations, distance),
        "coords": coords,
        "observations": observations,
    }


def _parse_finding(main: str, details: list[str]) -> dict:
    out = {"headline": "", "quantity": None, "forest_status": "", "extras": []}
    raw = re.sub(r"\.\s+(?=[A-Za-z][A-Za-z /]{1,30}:)", ".\n", main.replace("\r", ""))
    lines = [line.strip() for line in raw.split("\n") if line.strip()]
    out["headline"] = lines[0] if lines else raw.strip()
    has_attrs = False
    for line in lines[1:]:
        match = _ATTR.match(line)
        if not match:
            out["extras"].append(line)
            continue
        has_attrs = True
        label, value = match.group(1).strip(), match.group(2).strip()
        upper = label.upper()
        if re.search(r"JUM.{0,3}LAH|JML|JLH", upper):
            number = re.search(r"\d+", value)
            out["quantity"] = int(number.group()) if number else None
        elif "STATUS" in upper:
            out["forest_status"] = value[:128]
        else:
            out["extras"].append(f"{label}: {value}")
    for value in details:
        if value and value not in out["extras"]:
            out["extras"].append(value)
    out["has_attrs"] = has_attrs
    return out


def _category(text: str) -> str:
    upper = text.upper()
    if _ILLEGAL_WORDS.search(upper):
        return enums.FindingCategory.ILLEGAL
    if _FAUNA_WORDS.search(upper):
        return enums.FindingCategory.FAUNA
    if _FLORA_WORDS.search(upper):
        return enums.FindingCategory.FLORA
    return enums.FindingCategory.OTHER


def _is_note(headline: str, has_attrs: bool) -> bool:
    upper = headline.upper()
    if _FINDING_WORDS.search(upper) or has_attrs:
        return False
    return bool(_NOTE_WORDS.search(upper))


def _grids(observations) -> str:
    grids = []
    for obs in observations:
        for value in [obs["comment"], *obs["details"]]:
            for grid in _GRID.findall(value or ""):
                if grid.upper() not in grids:
                    grids.append(grid.upper())
    return ", ".join(grids)[:255]


def _place(meta, observations) -> str:
    match = re.search(r"WILAYAH\s+(.+?)[.\n]", meta["objective"], re.I)
    if match:
        return match.group(1).strip()[:255]
    for obs in observations:
        for detail in obs["details"]:
            if _PLACE_WORDS.search(detail) and len(detail) < 60:
                return detail.strip()
    return re.sub(r"^PATROLI\s+", "", meta["objective"], flags=re.I)[:60].strip()


def _start_point(parsed):
    observations = parsed["observations"]
    start = next((o for o in observations if o["kind"] == "NewPatrol"), None)
    start = start or (observations[0] if observations else None)
    if start:
        return start["lng"], start["lat"]
    if parsed["coords"]:
        return parsed["coords"][0]
    return None, None


def _findings_and_notes(observations):
    findings, notes = [], []
    for obs in observations:
        if obs["kind"] in ("NewPatrol", "StopPatrol"):
            if obs["comment"]:
                notes.append(obs["comment"])
            continue
        item = _parse_finding(obs["comment"], obs["details"])
        if _is_note(item["headline"], item["has_attrs"]):
            if item["headline"]:
                notes.append(item["headline"])
            continue
        findings.append(
            {
                "category": _category(
                    item["headline"] + " " + " ".join(item["extras"])
                ),
                "description": (item["headline"] or _("Observasi"))[:500],
                "quantity": item["quantity"],
                "forest_status": item["forest_status"],
                "note": " · ".join(item["extras"])[:500],
                "lat": obs["lat"],
                "lng": obs["lng"],
                "photos": len(obs["photos"]),
            }
        )
    return findings, notes


def _narrative(meta, notes) -> str:
    narrative = meta["objective"] or _("Patroli SMART")
    extra = []
    if meta["comments"] and meta["comments"] != meta["objective"]:
        extra.append(meta["comments"])
    for note in notes:
        if note not in extra:
            extra.append(note)
    if extra:
        narrative += " " + _("Catatan: %s.") % "; ".join(extra)
    return narrative[:10000]


def prefill(parsed: dict) -> dict:
    """Isian laporan Taman Buru dari hasil baca SMART (kode SMART tidak diisikan)."""
    meta = parsed["meta"]
    observations = parsed["observations"]
    lng, lat = _start_point(parsed)
    findings, notes = _findings_and_notes(observations)

    def clean(value):
        return "" if _coded(value) else value

    return {
        "location_name": _place(meta, observations),
        "grid": _grids(observations),
        "lat": lat,
        "lng": lng,
        "objective": meta["objective"],
        "team_leader": clean(meta["leader"]),
        "team": clean(meta["team"]),
        "station": clean(meta["station"]),
        "transport": clean(meta["transport"]),
        "started": meta["started"],
        "ended": meta["ended"],
        "distance_m": meta["distance_m"],
        "narrative": _narrative(meta, notes),
        "findings": findings[:50],
        "counts": {
            "observations": len(observations),
            "track": len(parsed["coords"]),
            "photos": sum(len(o["photos"]) for o in observations),
        },
    }


@transaction.atomic
def save_session(parsed: dict, user, activity=None, source_name: str = ""):
    """Simpan jejak, observasi, dan foto patroli sebagai satu PatrolSession."""
    from operasi.models import PatrolObservation, PatrolPhoto, PatrolSession

    meta = parsed["meta"]
    coords = parsed["coords"]
    session = PatrolSession(
        activity=activity,
        korwil=activity.korwil if activity is not None else None,
        smart_patrol_id=meta["patrol_id"],
        name=meta["objective"] or _("Patroli SMART"),
        started_at=_time(meta["started"]),
        ended_at=_time(meta["ended"]),
        leader=meta["leader"],
        team=meta["team"],
        station=meta["station"],
        transport=meta["transport"],
        comments=meta["comments"],
        distance_m=meta["distance_m"],
        track=LineString(coords, srid=4326) if len(coords) > 1 else None,
        source_name=source_name[:255],
        uploaded_by=user,
    )
    if activity is not None:
        session._korwil_resolved = True
    session.save()
    for seq, obs in enumerate(parsed["observations"]):
        observation = PatrolObservation.objects.create(
            session=session,
            seq=seq,
            kind=obs["kind"],
            location=Point(obs["lng"], obs["lat"], srid=4326),
            observed_at=_time(obs["time"]),
            comment=" — ".join(
                filter(None, [obs["comment"], " · ".join(obs["details"])])
            ),
            leg_distance_m=(
                round(obs["leg"], 1)
                if obs["leg"] is not None and 0 <= obs["leg"] < 1e8
                else None
            ),
        )
        for image in obs["photos"]:
            ext = "png" if image.startswith(_PNG) else "jpg"
            photo = PatrolPhoto(observation=observation)
            photo.photo.save(
                f"{uuid.uuid4().hex}.{ext}", ContentFile(image), save=False
            )
            photo.save()
    return session
