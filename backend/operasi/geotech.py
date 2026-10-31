"""Uji tanah PLTS: progres titik penyelidikan tanah, rekomendasi, ekspor & impor Excel.

Titik dicocokkan lewat kode kanonik (huruf & angka saja) sehingga "PV-BH 01",
"PV BH01", dan "pvbh01" dianggap titik yang sama. Impor dua langkah: pratinjau
memperlihatkan perubahan per titik, lalu hanya baris terpilih yang disimpan.
"""

import re
from collections import Counter

from django.contrib.gis.geos import Point
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from operasi import enums, geo, spatial, tabular
from operasi.models import GeotechChange, GeotechPoint, geotech_key

W = enums.GeotechWorkStatus
MAX_IMPORT_ROWS = 5000
MAX_PHOTOS = 6
REKOM_HEADER = "rekomendasi sistem"

# Kolom ekspor = kolom impor, agar berkas hasil ekspor dapat diedit lalu diimpor.
COLUMNS = [
    ("code", "Kode titik"),
    ("method", "Metode"),
    ("segment", "Bagian proyek"),
    ("area_name", "Area / paket"),
    ("zone_name", "Zona"),
    ("batch", "Batch"),
    ("korwil", "Korwil"),
    ("survey_status", "Status survei"),
    ("social_condition", "Kondisi sosial"),
    ("landowner", "Pemilik lahan"),
    ("work_status", "Status pekerjaan"),
    ("progress_pct", "Progres %"),
    ("obstacle", "Kendala"),
    ("survey_note", "Catatan survei"),
    ("work_note", "Catatan pekerjaan"),
    ("recommendation", "Rekomendasi tindak lanjut"),
    ("system", "Rekomendasi sistem"),
    ("access", "Akses lokasi"),
    ("started_on", "Tanggal mulai"),
    ("finished_on", "Tanggal selesai"),
    ("lat", "Lintang"),
    ("lng", "Bujur"),
]

HEADER_ALIASES = {
    "code": ("kode titik", "kode", "id titik", "titik", "id", "kode uji"),
    "method": ("metode", "jenis", "jenis uji", "metode uji"),
    "segment": ("bagian proyek", "bagian", "tipe", "segmen"),
    "area_name": ("area paket", "area", "paket"),
    "zone_name": ("zona",),
    "batch": ("batch", "tahap"),
    "korwil": ("korwil", "kode korwil"),
    "survey_status": ("status survei", "survei", "survey", "status survey"),
    "social_condition": ("kondisi sosial", "sosial"),
    "landowner": ("pemilik lahan", "pemilik", "pemilik penggarap lahan"),
    "work_status": (
        "status pekerjaan",
        "status kerja",
        "status",
        "status pekerjaan uji",
    ),
    "progress_pct": ("progres", "progress", "progres persen", "persen"),
    "obstacle": ("kendala", "hambatan"),
    "survey_note": ("catatan survei", "catatan survey"),
    "work_note": ("catatan pekerjaan", "catatan kerja", "catatan", "remark"),
    "recommendation": ("rekomendasi tindak lanjut", "rekomendasi"),
    "access": ("akses lokasi", "akses"),
    "started_on": ("tanggal mulai", "tgl mulai", "mulai"),
    "finished_on": ("tanggal selesai", "tgl selesai", "selesai"),
    "lat": ("lintang", "lat", "latitude", "y"),
    "lng": ("bujur", "lon", "lng", "long", "longitude", "x"),
}

CHOICE_WORDS = {
    "method": [
        (("sondir", "cpt"), enums.GeotechMethod.SONDIR),
        (("termal", "thermal"), enums.GeotechMethod.THERMAL),
        (("resistiv", "ert", "geolistrik"), enums.GeotechMethod.RESISTIVITY),
        (
            ("test pit", "trial pit", "sumur uji", "testpit"),
            enums.GeotechMethod.TEST_PIT,
        ),
        (("bor", "boring", "borehole"), enums.GeotechMethod.BOREHOLE),
        (("lain",), enums.GeotechMethod.OTHER),
    ],
    "segment": [
        (("joint bay", "tjb"), enums.GeotechSegment.JOINT_BAY),
        (("transmisi", "transmission", "tl"), enums.GeotechSegment.TRANSMISSION),
        (
            ("substation", "gardu", "pooling", "ss", "gi"),
            enums.GeotechSegment.SUBSTATION,
        ),
        (("pv", "panel", "surya"), enums.GeotechSegment.PV),
        (("lain",), enums.GeotechSegment.OTHER),
    ],
    "survey_status": [
        (("belum",), enums.SurveyStatus.PENDING),
        (("selesai", "sudah", "done"), enums.SurveyStatus.DONE),
    ],
    "social_condition": [
        (("belum kondusif", "tidak kondusif"), enums.SocialCondition.NOT_CONDUCIVE),
        (("belum dicek", "belum cek"), enums.SocialCondition.UNCHECKED),
        (("bermasalah", "masalah", "konflik"), enums.SocialCondition.PROBLEM),
        (("kondusif", "aman"), enums.SocialCondition.CONDUCIVE),
    ],
    "work_status": [
        (("belum", "not started"), W.NOT_STARTED),
        (("terhenti", "stop", "hold", "tunda"), W.STOPPED),
        (("proses", "progress", "berjalan"), W.IN_PROGRESS),
        (("selesai", "done", "complete", "rampung"), W.DONE),
    ],
}

TRACKED = {
    "work_status": _("Status pekerjaan"),
    "progress_pct": _("Progres"),
    "survey_status": _("Status survei"),
    "social_condition": _("Kondisi sosial"),
    "obstacle": _("Kendala"),
}

QUICK_ACTIONS = ("selesai", "proses", "terhenti", "survei", "kondusif")


def _normal(text) -> str:
    return " ".join(re.sub(r"[^0-9a-z]+", " ", str(text or "").lower()).split())


def visible_points(user):
    return geo.scoped(GeotechPoint.objects.all(), user)


def can_change(user, point=None) -> bool:
    return user.has_perm("operasi.change_geotechpoint")


# --------------------------------------------------------------------------
# Rekomendasi sistem
# --------------------------------------------------------------------------


def protected_ids(points) -> set[int]:
    """Titik yang jatuh di zona lindung/hutan pada lapisan pusat komando."""
    ids = [p.pk for p in points if p.location is not None]
    overlay_ids = list(
        spatial.command_overlays()
        .filter(kind__in=spatial.ZONE_OVERLAY_KINDS)
        .values_list("pk", flat=True)
    )
    if not ids or not overlay_ids:
        return set()
    rows = spatial._hits(
        GeotechPoint._meta.db_table, "location", "t.id = ANY(%s)", (ids,), overlay_ids
    )
    features = spatial._zone_features(overlay_ids)
    found = set()
    for point_id, feature_id in rows:
        data = features.get(feature_id)
        if data and (
            spatial.feature_zone(
                data["overlay__kind"], data["name"], data["properties"]
            )
            == spatial.RtrwZone.PROTECTED
        ):
            found.add(point_id)
    return found


def system_recommendations(point, protected: bool = False) -> list[str]:
    tips = []
    if point.location is None:
        tips.append(_("Lengkapi koordinat titik agar dapat dipetakan."))
    if protected:
        tips.append(
            _(
                "Titik berada di kawasan lindung/hutan: ajukan persetujuan atau "
                "geser titik ke luar kawasan."
            )
        )
    if point.social_condition in (
        enums.SocialCondition.PROBLEM,
        enums.SocialCondition.NOT_CONDUCIVE,
    ):
        tips.append(
            _(
                "Survei lokasi, identifikasi pemilik lahan, dan koordinasi sosial "
                "sebelum pekerjaan."
            )
        )
    elif (
        point.social_condition == enums.SocialCondition.UNCHECKED
        and point.work_status == W.NOT_STARTED
    ):
        tips.append(_("Cek kondisi sosial di lokasi sebelum mobilisasi alat."))
    if point.work_status == W.STOPPED:
        tips.append(
            _("Selesaikan kendala (%(k)s) lalu lanjutkan pekerjaan.")
            % {"k": point.obstacle or _("belum dicatat")}
        )
    if (
        point.survey_status == enums.SurveyStatus.PENDING
        and point.work_status == W.NOT_STARTED
    ):
        tips.append(_("Jadwalkan survei lokasi."))
    return tips


# --------------------------------------------------------------------------
# Baris & ringkasan
# --------------------------------------------------------------------------


def point_row(point, protected: bool = False) -> dict:
    lat = lng = None
    if point.location is not None:
        lng, lat = point.location.x, point.location.y
    return {
        "id": point.pk,
        "code": point.code,
        "method": point.method,
        "method_label": point.get_method_display(),
        "segment": point.segment,
        "segment_label": point.get_segment_display(),
        "area": point.area_name,
        "zone": point.zone_name,
        "batch": point.batch,
        "korwil": point.korwil.code if point.korwil_id else "",
        "korwil_id": point.korwil_id,
        "survey": point.survey_status,
        "survey_label": point.get_survey_status_display(),
        "social": point.social_condition,
        "social_label": point.get_social_condition_display(),
        "landowner": point.landowner,
        "status": point.work_status,
        "status_label": point.get_work_status_display(),
        "color": enums.GEOTECH_COLORS.get(point.work_status, "#57606a"),
        "progress": point.progress_pct,
        "obstacle": point.obstacle,
        "survey_note": point.survey_note,
        "work_note": point.work_note,
        "recommendation": point.recommendation,
        "system": system_recommendations(point, protected),
        "protected": protected,
        "access": point.access,
        "started_on": point.started_on.isoformat() if point.started_on else "",
        "finished_on": point.finished_on.isoformat() if point.finished_on else "",
        "lat": lat,
        "lng": lng,
        "soil_test": point.soil_test.number if point.soil_test_id else "",
        "modified_at": timezone.localtime(point.modified_at).isoformat(),
    }


def point_rows(points) -> list[dict]:
    if hasattr(points, "select_related"):
        points = points.select_related("korwil", "soil_test")
    points = list(points)
    protected = protected_ids(points)
    return [point_row(p, p.pk in protected) for p in points]


def summary(rows) -> dict:
    total = len(rows)
    status = Counter(r["status"] for r in rows)
    done = status.get(W.DONE, 0)
    return {
        "total": total,
        "status": [
            {
                "value": str(value),
                "label": str(label),
                "count": status.get(value, 0),
                "color": enums.GEOTECH_COLORS[value],
            }
            for value, label in W.choices
        ],
        "done_pct": round(done * 100 / total) if total else 0,
        "avg_progress": (
            round(sum(r["progress"] for r in rows) / total, 1) if total else 0
        ),
        "surveyed": sum(1 for r in rows if r["survey"] == enums.SurveyStatus.DONE),
        "social_issue": sum(
            1
            for r in rows
            if r["social"]
            in (enums.SocialCondition.PROBLEM, enums.SocialCondition.NOT_CONDUCIVE)
        ),
        "no_location": sum(1 for r in rows if r["lat"] is None),
        "batches": [
            {
                "batch": b,
                "total": n,
                "done": sum(
                    1 for r in rows if r["batch"] == b and r["status"] == W.DONE
                ),
            }
            for b, n in sorted(Counter(r["batch"] for r in rows).items())
        ],
        "segments": [
            {
                "value": str(value),
                "label": str(label),
                "total": sum(1 for r in rows if r["segment"] == value),
                "done": sum(
                    1 for r in rows if r["segment"] == value and r["status"] == W.DONE
                ),
            }
            for value, label in enums.GeotechSegment.choices
            if any(r["segment"] == value for r in rows)
        ],
    }


# --------------------------------------------------------------------------
# Perubahan & aksi cepat
# --------------------------------------------------------------------------


def _display(point, field) -> str:
    if field == "progress_pct":
        return f"{point.progress_pct}%"
    getter = getattr(point, f"get_{field}_display", None)
    return str(getter()) if getter else str(getattr(point, field) or "")


def save_with_history(point, user, *, note: str = "", source: str = "", before=None):
    """Simpan titik dan catat perubahan kolom penting ke riwayat."""
    point.updated_by = user
    point.full_clean()
    point.save()
    if before is None:
        return []
    point.refresh_from_db()
    logged = []
    for field, label in TRACKED.items():
        old, new = before.get(field, ""), _display(point, field)
        if old != new:
            logged.append(
                GeotechChange(
                    point=point,
                    field=str(label),
                    old_value=old[:255],
                    new_value=new[:255],
                    note=note[:255],
                    source=source[:64],
                    changed_by=user,
                )
            )
    GeotechChange.objects.bulk_create(logged)
    return logged


def snapshot(point) -> dict:
    return {field: _display(point, field) for field in TRACKED}


def quick_action(point, user, action: str, note: str = ""):
    if action not in QUICK_ACTIONS:
        raise ValidationError({"aksi": [_("Aksi tidak dikenal.")]})
    before = snapshot(point)
    today = timezone.localdate()
    if action == "selesai":
        point.work_status = W.DONE
        point.finished_on = point.finished_on or today
        point.obstacle = ""
        if point.social_condition != enums.SocialCondition.PROBLEM:
            point.social_condition = enums.SocialCondition.CONDUCIVE
    elif action == "proses":
        point.work_status = W.IN_PROGRESS
        point.progress_pct = max(point.progress_pct or 0, 50)
        point.obstacle = ""
    elif action == "terhenti":
        obstacle = (note or point.obstacle).strip()
        if not obstacle:
            raise ValidationError({"catatan": [_("Isi kendala penyebab terhenti.")]})
        point.work_status = W.STOPPED
        point.obstacle = obstacle[:255]
        point.progress_pct = point.progress_pct or 1
    elif action == "survei":
        point.survey_status = enums.SurveyStatus.DONE
    elif action == "kondusif":
        point.social_condition = enums.SocialCondition.CONDUCIVE
    if note and action != "terhenti":
        stamp = f"{today:%d-%m-%Y}: {note.strip()}"
        point.work_note = f"{point.work_note}\n{stamp}".strip()[:5000]
    save_with_history(point, user, note=note, source=_("Aksi cepat"), before=before)
    return point


# --------------------------------------------------------------------------
# Ekspor Excel
# --------------------------------------------------------------------------


def export_rows(points):
    for row in point_rows(points):
        yield [
            row["code"],
            row["method_label"],
            row["segment_label"],
            row["area"],
            row["zone"],
            row["batch"],
            row["korwil"],
            row["survey_label"],
            row["social_label"],
            row["landowner"],
            row["status_label"],
            row["progress"],
            row["obstacle"],
            row["survey_note"],
            row["work_note"],
            row["recommendation"],
            " ".join(row["system"]),
            row["access"],
            row["started_on"],
            row["finished_on"],
            row["lat"],
            row["lng"],
        ]


def add_sheet(book, points, name: str = "Uji tanah PLTS"):
    widths = {0: 16, 3: 22, 9: 22, 12: 24, 13: 30, 14: 30, 15: 30, 16: 40}
    book.table(name, [label for _key, label in COLUMNS], export_rows(points), widths)


def workbook(points) -> bytes:
    from operasi.recap import _Book

    book = _Book()
    add_sheet(book, points)
    return book.close()


# --------------------------------------------------------------------------
# Impor Excel/CSV
# --------------------------------------------------------------------------


def _choice(field: str, value) -> str | None:
    text = _normal(value)
    if not text:
        return None
    model_field = GeotechPoint._meta.get_field(field)
    for key, label in model_field.choices:
        if text in (_normal(key), _normal(label)):
            return key
    for words, key in CHOICE_WORDS.get(field, []):
        for word in words:
            if re.search(rf"(^| ){re.escape(word)}( |$)", text) or (
                len(word) > 3 and word in text
            ):
                return key
    return ""


def _header_map(row) -> dict[int, str]:
    found = {}
    for index, cell in enumerate(row):
        text = _normal(cell)
        if not text or text == REKOM_HEADER:
            continue
        for field, aliases in HEADER_ALIASES.items():
            if field in found.values():
                continue
            if text in aliases:
                found[index] = field
                break
    return found


def read_rows(name: str, data: bytes) -> list[dict]:
    """Baris impor: deteksi baris judul (≤ 15 baris pertama) yang memuat kolom kode."""
    _sheet, table = tabular.read_table(name, data)
    header_index, mapping = None, {}
    for index, row in enumerate(table[:15]):
        candidate = _header_map(row)
        if "code" in candidate.values():
            header_index, mapping = index, candidate
            break
    if header_index is None:
        raise ValidationError(
            {"berkas": [_('Kolom "Kode titik" tidak ditemukan di 15 baris pertama.')]}
        )
    rows = []
    for number, row in enumerate(table[header_index + 1 :], start=header_index + 2):
        values = {
            field: row[index] if index < len(row) else ""
            for index, field in mapping.items()
        }
        if not tabular.cell_text(values.get("code")):
            continue
        values["_row"] = number
        rows.append(values)
        if len(rows) > MAX_IMPORT_ROWS:
            raise ValidationError(
                {
                    "berkas": [
                        _("Maksimal %(n)s titik per impor.") % {"n": MAX_IMPORT_ROWS}
                    ]
                }
            )
    if not rows:
        raise ValidationError({"berkas": [_("Tidak ada baris titik di berkas.")]})
    return rows


TEXT_LIMITS = {
    "area_name": 128,
    "zone_name": 128,
    "landowner": 255,
    "obstacle": 255,
    "access": 255,
    "survey_note": 5000,
    "work_note": 5000,
    "recommendation": 5000,
}
CHOICE_FIELDS = (
    "method",
    "segment",
    "survey_status",
    "social_condition",
    "work_status",
)


def _parse_choices(values: dict, data: dict, errors: list):
    for field in CHOICE_FIELDS:
        if field not in values:
            continue
        choice = _choice(field, values[field])
        if choice == "":
            errors.append(
                _('%(f)s "%(v)s" tidak dikenal.')
                % {
                    "f": GeotechPoint._meta.get_field(field).verbose_name,
                    "v": tabular.cell_text(values[field])[:40],
                }
            )
        elif choice:
            data[field] = choice


def _parse_numbers(values: dict, data: dict, errors: list):
    if tabular.cell_text(values.get("batch")):
        match = re.search(r"\d+", tabular.cell_text(values["batch"]))
        if match and 1 <= int(match[0]) <= 99:
            data["batch"] = int(match[0])
        else:
            errors.append(_("Batch harus angka 1–99."))
    if tabular.cell_text(values.get("progress_pct")):
        raw = values["progress_pct"]
        number = tabular.number(raw)
        if isinstance(raw, float) and number is not None and 0 < number < 1:
            number *= 100  # sel berformat persen di Excel (0,5 = 50%)
        if number is None or not 0 <= number <= 100:
            errors.append(_("Progres harus 0–100."))
        else:
            data["progress_pct"] = int(round(number))
    for field in ("started_on", "finished_on"):
        if tabular.cell_text(values.get(field)):
            date = tabular.excel_date(values[field])
            if date is None:
                errors.append(
                    _('Tanggal "%(v)s" tidak sah.')
                    % {"v": tabular.cell_text(values[field])[:20]}
                )
            else:
                data[field] = date


def _parse_place(values: dict, korwils: dict, data: dict, errors: list):
    code = tabular.cell_text(values.get("korwil")).upper()
    if code:
        if code in korwils:
            data["korwil"] = korwils[code]
        else:
            errors.append(
                _('Korwil "%(v)s" tidak dikenal atau di luar cakupan.')
                % {"v": code[:20]}
            )
    lat, lng = tabular.number(values.get("lat")), tabular.number(values.get("lng"))
    if not lat and not lng:
        return  # kosong atau 0,0 = koordinat belum ada
    if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
        errors.append(_("Koordinat tidak sah."))
    else:
        data["location"] = Point(lng, lat, srid=4326)


def _parse(values: dict, korwils: dict) -> tuple[dict, list[str]]:
    """Nilai model dari satu baris; sel kosong = tidak diubah."""
    data, errors = {}, []
    for field, limit in TEXT_LIMITS.items():
        text = tabular.cell_text(values.get(field))
        if text:
            data[field] = text[:limit]
    _parse_choices(values, data, errors)
    _parse_numbers(values, data, errors)
    _parse_place(values, korwils, data, errors)
    return data, errors


def _changes(point, data: dict) -> list[str]:
    out = []
    for field, value in data.items():
        if field == "location":
            old = point.location
            if old is None or old.distance(value) > 1e-7:
                out.append(_("Koordinat diperbarui"))
            continue
        old = getattr(point, field)
        if old == value:
            continue
        model_field = GeotechPoint._meta.get_field(field)
        if field == "korwil":
            label_old, label_new = (old.code if old else "-"), value.code
        elif model_field.choices:
            choices = dict(model_field.choices)
            label_old, label_new = choices.get(old, old or "-"), choices.get(
                value, value
            )
        else:
            label_old, label_new = old if old not in (None, "") else "-", value
        out.append(f"{model_field.verbose_name}: {label_old} → {label_new}")
    return out


def _context(user):
    korwils = {k.code.upper(): k for k in geo.visible_korwils(user)}
    existing = {p.code_key: p for p in GeotechPoint.objects.select_related("korwil")}
    visible = set(visible_points(user).values_list("pk", flat=True))
    return korwils, existing, visible


def preview_import(user, rows, mode: str) -> dict:
    korwils, existing, visible = _context(user)
    can_add = mode == "lengkap" and user.has_perm("operasi.add_geotechpoint")
    items, seen = [], set()
    for index, values in enumerate(rows):
        code = tabular.cell_text(values.get("code"))[:64]
        key = geotech_key(code)
        data, errors = _parse(values, korwils)
        item = {
            "index": index,
            "row": values["_row"],
            "code": code,
            "changes": [],
            "errors": errors,
        }
        point = existing.get(key)
        if not key:
            item["action"], item["errors"] = "galat", [_("Kode titik kosong.")]
        elif key in seen:
            item["action"], item["errors"] = "galat", [_("Kode ganda di berkas.")]
        elif point is not None and point.pk not in visible:
            item["action"] = "luar"
        elif errors:
            item["action"] = "galat"
        elif point is not None:
            item["changes"] = _changes(point, data)
            item["action"] = "ubah" if item["changes"] else "sama"
        elif can_add:
            item["action"] = "baru"
        else:
            item["action"] = "tak_dikenal"
        seen.add(key)
        items.append(item)
    counts = Counter(i["action"] for i in items)
    return {
        "items": items,
        "counts": dict(counts),
        "labels": IMPORT_LABELS,
        "can_add": can_add,
    }


IMPORT_LABELS = {
    "ubah": _("Diperbarui"),
    "sama": _("Tidak berubah"),
    "baru": _("Titik baru"),
    "tak_dikenal": _("Kode belum terdaftar (lewati)"),
    "luar": _("Di luar cakupan Anda"),
    "galat": _("Galat"),
}


def _apply_item(user, item, values, korwils, existing, source) -> str:
    data, _errors = _parse(values, korwils)
    if item["action"] == "ubah":
        point = existing[geotech_key(item["code"])]
        before = snapshot(point)
    else:
        point = GeotechPoint(code=item["code"], created_by=user)
        before = None
    for field, value in data.items():
        setattr(point, field, value)
    if before is None and point.korwil_id is None:
        point.korwil = geo.korwil_for_write(user, point.location)
    with transaction.atomic():
        save_with_history(point, user, source=source, before=before)
        if before is None:
            GeotechChange.objects.create(
                point=point,
                field=str(_("Titik")),
                new_value=str(_("Dibuat dari impor")),
                source=source[:64],
                changed_by=user,
            )
    return "created" if before is None else "updated"


@transaction.atomic
def apply_import(user, rows, mode: str, selected: list[int], source: str) -> dict:
    if not user.has_perm("operasi.change_geotechpoint"):
        raise PermissionDenied
    preview = preview_import(user, rows, mode)
    korwils, existing, _visible = _context(user)
    result = {"updated": 0, "created": 0, "errors": []}
    chosen = set(selected)
    for item in preview["items"]:
        if item["index"] not in chosen or item["action"] not in ("ubah", "baru"):
            continue
        try:
            outcome = _apply_item(
                user, item, rows[item["index"]], korwils, existing, source
            )
        except ValidationError as error:
            result["errors"].append(
                {
                    "row": item["row"],
                    "code": item["code"],
                    "errors": [str(m) for m in error.messages],
                }
            )
            continue
        result[outcome] += 1
    return result


def history(point) -> list[dict]:
    return [
        {
            "field": c.field,
            "old": c.old_value,
            "new": c.new_value,
            "note": c.note,
            "source": c.source,
            "by": (
                (c.changed_by.get_full_name() or c.changed_by.get_username())
                if c.changed_by_id
                else ""
            ),
            "at": timezone.localtime(c.created_at).isoformat(),
        }
        for c in point.changes.select_related("changed_by")[:50]
    ]
