"""Pindahkan data sistem pusat komando lama (cadangan Supabase) ke SimLahan.

Dijalankan lewat ``python manage.py impor_komando``. Setiap baris sumber yang
dipindahkan dicatat di :class:`~operasi.models.ImportedRecord`, jadi impor
boleh diulang tanpa membuat data ganda. Isi cadangan diperlakukan sebagai
masukan tak tepercaya: teks dipotong sesuai panjang kolom, koordinat dan foto
diperiksa, dan tidak ada perintah SQL dari berkas yang dijalankan.

Pemetaan utama (tabel lama → SimLahan):

* ``korwil`` → Korwil; ``personel`` → akun petugas, grup peran, keanggotaan
  Korwil, jabatan & atasan;
* ``warga`` → warga terdata; ``komsos_history`` → kegiatan Komsos;
  ``komsos_perubahan_dukungan_raw``/``komsos_perubahan_luas`` → riwayat sikap
  dan luas lahan;
* ``kegiatan`` → laporan kegiatan (+ foto, patroli Taman Buru);
  ``tasks`` (+ penerima, poin, riwayat) → tugas komando;
  ``laporan_harian`` → laporan harian berjenjang;
* ``land_polygons`` → bidang penguasaan; ``soil_test`` → titik uji tanah PLTS;
  ``patrol_sessions``/``patrol_observations`` → jejak patroli SMART;
  ``gps_tracking`` → jejak GPS petugas;
* ``rtrw_zones``, ``rempang_geo_layers``, ``user_geo_layers``, ``lahan`` →
  lapisan peta referensi pusat komando.

Tabel lain (log masuk, sesi, PIN, cadangan lama, kunci sistem, dll.) sengaja
tidak dipindahkan; alasannya tercantum di laporan.
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import json
import os
import re
import secrets
import string
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from auditlog.context import disable_auditlog
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import GEOSException, GEOSGeometry, LineString, Point
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from asetlahan import enums as aset_enums
from asetlahan import geo as aset_geo
from asetlahan.models import MapOverlay, MapOverlayFeature, Task
from leasing.models import ServiceUnit
from operasi import enums, patrol
from operasi.models import (
    MAX_LAND_AREA_M2,
    Activity,
    ActivityPhoto,
    DailyReport,
    DailyReportEvent,
    GeotechPoint,
    HuntingParkFinding,
    HuntingParkPatrol,
    ImportedRecord,
    Korwil,
    LandAreaChange,
    LandPlot,
    LandPlotChange,
    OfficerProfile,
    OfficerTrackPoint,
    PatrolObservation,
    PatrolPhoto,
    PatrolSession,
    Resident,
    Seedling,
    StanceChange,
    TaskEvent,
    TaskPoint,
    geotech_key,
)
from operasi.pgdump import Dump
from operasi.spatial import TRACK_KEEP_DAYS
from utils.group_permissions import UserGroup

NO_KORWIL = {"", "-", "NK", "ALL", "LINTAS", "TL"}
FIELD_ROLES = {"Anggota", "PHL"}
COORDINATOR_ROLES = {"Ka Korwil", "Ka Tim Lahan"}
JUNK_TEXT = {"", "-", "_", "*", "?", "#error!", "tidak ada", "tidak ada hp", "null"}
# Nama instansi yang tidak boleh muncul di SimLahan diganti kata netral.
_AUTHORITY = re.compile(r"\bB\s*P\.?\s*Batam\b", re.IGNORECASE)
AUTHORITY_REPLACEMENT = "pihak berwenang"

STANCES = {
    "pro": enums.Stance.SUPPORT,
    "kontra": enums.Stance.OPPOSE,
    "netral": enums.Stance.NEUTRAL,
}
GENDERS = {"laki-laki": enums.Gender.MALE, "perempuan": enums.Gender.FEMALE}
RESIDENCY = {
    "tempatan": enums.ResidencyStatus.NATIVE,
    "pendatang": enums.ResidencyStatus.NEWCOMER,
}
ACTIVITY_TYPES = {
    "komsos": enums.ActivityType.KOMSOS,
    "patroli tb": enums.ActivityType.HUNTING_PARK,
    "taman buru": enums.ActivityType.HUNTING_PARK,
    "topografi": enums.ActivityType.TOPOGRAPHY,
    "pemetaan": enums.ActivityType.MAPPING,
    "penguasaan lahan": enums.ActivityType.MAPPING,
    "temuan ilegal": enums.ActivityType.ILLEGAL,
}
TASK_STATUS = {
    "pending": aset_enums.TaskStatus.NEW,
    "overdue": aset_enums.TaskStatus.NEW,
    "in_progress": aset_enums.TaskStatus.IN_PROGRESS,
    "done": aset_enums.TaskStatus.DONE,
    "cancelled": aset_enums.TaskStatus.CANCELLED,
}
TASK_PRIORITY = {
    "low": aset_enums.Priority.LOW,
    "medium": aset_enums.Priority.NORMAL,
    "high": aset_enums.Priority.HIGH,
    "urgent": aset_enums.Priority.URGENT,
}
TASK_EVENTS = {
    "started": enums.TaskEventKind.STARTED,
    "submitted": enums.TaskEventKind.SUBMITTED,
    "verified": enums.TaskEventKind.VERIFIED,
    "blocked": enums.TaskEventKind.BLOCKED,
    "resumed": enums.TaskEventKind.RESUMED,
    "rejected": enums.TaskEventKind.REJECTED,
    "cancelled": enums.TaskEventKind.CANCELLED,
}
FINDING_CATEGORIES = {
    "flora": enums.FindingCategory.FLORA,
    "fauna": enums.FindingCategory.FAUNA,
    "aktivitas ilegal": enums.FindingCategory.ILLEGAL,
}
GEO_LAYER_KINDS = {
    "PLTS": (aset_enums.OverlayKind.PROJECT, "Kawasan proyek PLTS"),
    "HL": (aset_enums.OverlayKind.FOREST, "Hutan lindung (HL)"),
    "TJB": (aset_enums.OverlayKind.UTILITY, "Transition joint bay (TJB)"),
    "RTRW": (aset_enums.OverlayKind.SPATIAL_PLAN, "Zona RTRW"),
    "JALAN": (aset_enums.OverlayKind.ROAD, "Jalan"),
    "INFRASTRUKTUR": (aset_enums.OverlayKind.UTILITY, "Infrastruktur"),
    "KORWIL": (aset_enums.OverlayKind.ADMINISTRATIVE, "Batas Korwil"),
    "LAHAN": (aset_enums.OverlayKind.CADASTRE, "Lahan"),
    "OTHER": (aset_enums.OverlayKind.OTHER, "Lainnya"),
}
RTRW_SOURCES = {
    "rencana_ruang": "Rencana tata ruang (RTRW)",
    "usulan_tata_ruang": "Usulan tata ruang",
}
OVERLAY_SOURCE = "Sistem pusat komando lama"
# Penanda data contoh (operasi_contoh_rempang); data asli tidak boleh tercampur.
SAMPLE_MARK = "[contoh]"

# Tabel yang sengaja tidak dipindahkan beserta alasannya.
NOT_IMPORTED = {
    "activity_log": "log aktivitas & masuk sistem lama (SimLahan mencatat log sendiri)",
    "audit_log": "log audit sistem lama",
    "approvals": "persetujuan otomatis sistem lama (sudah tercermin di kegiatan)",
    "app_sessions": "sesi masuk sistem lama",
    "personel_auth": "PIN masuk sistem lama (tidak dipakai; sandi baru dibuat)",
    "push_subscriptions": "langganan notifikasi peramban sistem lama",
    "ai_query_log": "log pertanyaan AI sistem lama",
    "rcc_deadman": "kunci sistem lama (tidak dibawa; kunci SimLahan tetap mati)",
    "rcc_master_lock": "kunci sistem lama (tidak dibawa; kunci SimLahan tetap mati)",
    "users": "akun admin sistem lama (bukan petugas)",
    "map_geotag": "tabel bantu pencocokan nama sistem lama",
    "pemetaan_uploads": "catatan unggahan berkas (berkasnya tidak ada di cadangan)",
    "kegiatan_review_state": "status tinjauan sistem lama",
    "kpi_scores": "skor KPI dihitung ulang oleh SimLahan",
}
LEGACY_BACKUP = re.compile(r"^(bak_|backup_|arsip_)|_backup_\d|_premig$")


# --------------------------------------------------------------------------
# Laporan
# --------------------------------------------------------------------------


@dataclass
class Report:
    counts: dict = field(default_factory=lambda: defaultdict(Counter))
    reasons: dict = field(default_factory=lambda: defaultdict(Counter))
    warnings: list = field(default_factory=list)
    not_imported: list = field(default_factory=list)
    passwords: list = field(default_factory=list)

    def add(self, table: str, key: str, amount: int = 1):
        self.counts[table][key] += amount

    def skip(self, table: str, reason: str, amount: int = 1):
        self.counts[table]["dilewati"] += amount
        self.reasons[table][reason] += amount

    def warn(self, message: str):
        self.warnings.append(message)


# --------------------------------------------------------------------------
# Pembersih nilai
# --------------------------------------------------------------------------


def clean_text(value, limit: int | None = None) -> str:
    text = str(value or "").replace("\x00", "").strip()
    text = _AUTHORITY.sub(AUTHORITY_REPLACEMENT, text)
    if limit is not None:
        text = text[:limit].strip()
    return text


def meaningful(value) -> str:
    text = clean_text(value)
    return "" if text.lower() in JUNK_TEXT else text


def to_bool(value) -> bool:
    return str(value or "").lower() in ("t", "true", "1")


def to_int(value) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def to_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def to_datetime(value):
    if not value:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value).strip()):
        return at_noon(to_date(value))
    try:
        moment = parse_datetime(str(value).strip().replace(" ", "T", 1))
    except ValueError:
        moment = None
    if moment is None:
        day = parse_date(str(value).strip()[:10])
        return at_noon(day) if day else None
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment)
    return moment


def to_date(value):
    if not value:
        return None
    try:
        return parse_date(str(value).strip()[:10])
    except ValueError:
        return None


def at_noon(day):
    """Tanggal tanpa jam → pukul 12.00 waktu setempat (tidak bergeser hari)."""
    if day is None:
        return None
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time(12)))


def to_point(lat, lon) -> Point | None:
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if lat_f == 0 and lon_f == 0:
        return None
    if not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180):
        return None
    return Point(lon_f, lat_f, srid=4326)


def to_json(value, default):
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def parse_pg_array(value) -> list[str]:
    """Larik teks PostgreSQL satu dimensi (``{"a","b"}``) menjadi list."""
    text = str(value or "").strip()
    if not (text.startswith("{") and text.endswith("}")):
        return []
    items, i, inner = [], 0, text[1:-1]
    while i < len(inner):
        if inner[i] == '"':
            i += 1
            buf = []
            while i < len(inner) and inner[i] != '"':
                if inner[i] == "\\" and i + 1 < len(inner):
                    i += 1
                buf.append(inner[i])
                i += 1
            items.append("".join(buf))
            i += 2  # tanda kutip penutup dan koma
        else:
            end = inner.find(",", i)
            end = len(inner) if end == -1 else end
            token = inner[i:end].strip()
            if token.upper() != "NULL":
                items.append(token)
            i = end + 1
    return items


_NUMBER = r"(\d+(?:[.,]\d+)?|\d+/\d+)"


def _number(text: str) -> Decimal | None:
    if "/" in text:
        top, bottom = text.split("/", 1)
        try:
            return Decimal(top) / Decimal(bottom) if Decimal(bottom) else None
        except InvalidOperation:
            return None
    if re.fullmatch(r"\d{1,3}\.\d{3}", text):  # 1.250 = seribu dua ratus lima puluh
        text = text.replace(".", "")
    return to_decimal(text.replace(",", "."))


def parse_area_m2(value) -> Decimal | None:
    """Luas lahan teks bebas (``± 2 ha``, ``10 x 12 m``, ``500m``) → m²."""
    text = clean_text(value).lower()
    text = text.replace("±", "").replace("×", "x").replace("²", "2").strip(" .\"'")
    match = re.fullmatch(_NUMBER + r"\s*(ha|hektar|hektare)", text)
    if match:
        number = _number(match.group(1))
        area = number * 10000 if number is not None else None
    else:
        match = re.fullmatch(_NUMBER + r"\s*x\s*" + _NUMBER + r"\s*(m2|m|meter)?", text)
        if match:
            a, b = _number(match.group(1)), _number(match.group(2))
            area = a * b if a is not None and b is not None else None
        else:
            match = re.fullmatch(_NUMBER + r"\s*(m2|m|meter)", text)
            area = _number(match.group(1)) if match else None
    if area is None or area <= 0 or area > MAX_LAND_AREA_M2:
        return None
    return area.quantize(Decimal("0.01"))


def parse_years(value, unit=("tahun", "thn", "th")) -> int | None:
    text = clean_text(value).lower().replace("±", "").strip()
    match = re.fullmatch(r"(\d{1,3})\s*(%s)\.?" % "|".join(unit), text)
    if match:
        number = int(match.group(1))
        return number if 0 <= number < 130 else None
    if re.fullmatch(r"\d{1,2}\s*bulan", text):
        return 0
    return None


def _read_geometry(value):
    if isinstance(value, dict):
        return GEOSGeometry(json.dumps(value), srid=4326)
    text = str(value).strip()
    if not text.startswith(("{", "[")):
        return GEOSGeometry(text)  # EWKB heks dari kolom PostGIS
    data = json.loads(text)
    if isinstance(data, list):  # hanya koordinat cincin poligon
        data = {"type": "Polygon", "coordinates": data}
    return GEOSGeometry(json.dumps(data), srid=4326)


def _scalar_props(data: dict) -> dict:
    """Atribut teks/angka sebuah objek peta (nilai bersarang diabaikan)."""
    return {
        str(k)[:64]: clean_text(v, 255)
        for k, v in data.items()
        if isinstance(v, (str, int, float)) and str(v).strip()
    }


def person_key(name) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(name or "").lower()).split())


def name_tokens(name: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", (name or "").lower()) if len(t) > 1}


# --------------------------------------------------------------------------
# Pengimpor
# --------------------------------------------------------------------------


class LegacyImporter:
    def __init__(
        self,
        dump: Dump,
        *,
        update: bool = False,
        include_test: bool = False,
        dry_run: bool = False,
        password_file: str | None = None,
        log=None,
    ):
        self.dump = dump
        self.update = update
        self.include_test = include_test
        self.dry_run = dry_run
        self.password_file = password_file
        self.log = log or (lambda message: None)
        self.report = Report()
        self.saved_files: list = []
        self.cache: dict[str, list[dict]] = {}
        self.korwils: dict[str, Korwil] = {}
        self.users: dict[str, object] = {}
        self.test_people: set[str] = set()
        self.residents: dict[str, Resident] = {}
        self.resident_names: dict = defaultdict(list)
        self.activities: dict[str, Activity] = {}
        self.tasks: dict[str, Task] = {}
        self.plots: dict[str, LandPlot] = {}
        self._content_types: dict = {}

    # ------------------------------------------------------------------
    # Kerangka
    # ------------------------------------------------------------------

    def rows(self, table: str) -> list[dict]:
        name = table if "." in table else f"public.{table}"
        if name not in self.cache:
            self.cache[name] = self.dump.rows(name) if self.dump.has(name) else []
        return self.cache[name]

    def run(self) -> Report:
        try:
            with disable_auditlog(), transaction.atomic():
                self._load_links()
                steps = [
                    ("Korwil", self.import_korwils),
                    ("Petugas", self.import_people),
                    ("Warga", self.import_residents),
                    ("Riwayat Komsos", self.import_komsos_history),
                    ("Riwayat sikap & luas", self.import_resident_changes),
                    ("Kegiatan", self.import_activities),
                    ("Tugas", self.import_tasks),
                    ("Laporan harian", self.import_daily_reports),
                    ("Bidang penguasaan", self.import_land_plots),
                    ("Uji tanah PLTS", self.import_geotech),
                    ("Patroli SMART", self.import_patrols),
                    ("Jejak GPS", self.import_tracks),
                    ("Lapisan peta", self.import_overlays),
                ]
                for label, step in steps:
                    self.log(f"… {label}")
                    step()
                self._passwords()
                self._list_not_imported()
                if self.dry_run:
                    transaction.set_rollback(True)
        except BaseException:
            self._delete_saved_files()
            raise
        if self.dry_run:
            self._delete_saved_files()
        elif self.password_file and self.report.passwords:
            self._write_passwords()
        return self.report

    def _delete_saved_files(self):
        for storage, name in self.saved_files:
            try:
                storage.delete(name)
            except OSError:
                pass
        self.saved_files = []

    def _ct(self, model):
        if model not in self._content_types:
            self._content_types[model] = ContentType.objects.get_for_model(model)
        return self._content_types[model]

    def _load_links(self):
        self.links = {
            (r.source_table, r.source_id): r
            for r in ImportedRecord.objects.select_related("content_type")
        }

    def linked(self, table: str, source_id: str):
        """(sudah pernah diimpor?, objeknya atau None bila sudah dihapus)."""
        link = self.links.get((table, str(source_id)))
        if link is None:
            return False, None
        model = link.content_type.model_class()
        return True, model._default_manager.filter(pk=link.object_id).first()

    def link(self, table: str, source_id: str, obj):
        record = ImportedRecord.objects.create(
            source_table=table,
            source_id=str(source_id),
            content_type=self._ct(type(obj)),
            object_id=obj.pk,
        )
        self.links[(table, str(source_id))] = record

    def save(self, table, source_id, model, values, *, flags=None, created_at=None):
        """Buat objek baru atau pakai yang sudah diimpor (diperbarui bila --perbarui).

        Mengembalikan (objek atau None, baru?). Objek yang sudah dihapus di
        SimLahan setelah impor sebelumnya tidak dibuat ulang.
        """
        seen, obj = self.linked(table, source_id)
        if seen and obj is None:
            self.report.skip(table, "sudah dihapus di SimLahan, tidak dibuat ulang")
            return None, False
        if obj is not None:
            if not self.update:
                self.report.add(table, "sudah ada")
                return obj, False
            for name, value in values.items():
                setattr(obj, name, value)
            for name, value in (flags or {}).items():
                setattr(obj, name, value)
            obj.save()
            self.report.add(table, "diperbarui")
            return obj, False
        obj = model(**values)
        for name, value in (flags or {}).items():
            setattr(obj, name, value)
        obj.save()
        if created_at is not None and hasattr(obj, "created_at"):
            model._default_manager.filter(pk=obj.pk).update(created_at=created_at)
            obj.created_at = created_at
        self.link(table, source_id, obj)
        self.report.add(table, "dibuat")
        return obj, True

    def save_photo(self, field_file, data: bytes):
        ext = "png" if data.startswith(b"\x89PNG") else "jpg"
        field_file.save(f"{uuid.uuid4().hex}.{ext}", ContentFile(data), save=False)
        self.saved_files.append((field_file.storage, field_file.name))

    def photos_from(self, values) -> list[bytes]:
        """Foto JPEG/PNG dari daftar data URL (tanpa duplikat)."""
        result, seen = [], set()
        for value in values:
            if not isinstance(value, str) or not value.startswith("data:image"):
                continue
            data = patrol._photo(value)
            if data is None:
                self.report.warn("Satu foto dilewati (bukan JPEG/PNG atau > 5 MB).")
                continue
            digest = hashlib.sha256(data).hexdigest()
            if digest not in seen:
                seen.add(digest)
                result.append(data)
        return result

    def is_test(self, person_id) -> bool:
        return bool(person_id) and person_id in self.test_people

    def user(self, person_id):
        return self.users.get(person_id) if person_id else None

    def korwil(self, code):
        return self.korwils.get(str(code or "").strip().upper())

    # ------------------------------------------------------------------
    # Korwil
    # ------------------------------------------------------------------

    def import_korwils(self):
        table = "korwil"
        rows = self.rows(table)
        self.report.add(table, "dibaca", len(rows))
        for row in rows:
            code = clean_text(row["id"]).upper()
            if code in NO_KORWIL:
                self.report.skip(table, "bukan wilayah (Non-Korwil)")
                continue
            if len(code) > 8:
                self.report.skip(table, "kode Korwil lebih dari 8 huruf")
                continue
            existing = Korwil.objects.filter(code__iexact=code).first()
            seen, _obj = self.linked(table, code)
            if existing is not None and not seen:
                if existing.note.lower().startswith(SAMPLE_MARK):
                    raise ValidationError(
                        f"Korwil {code} masih berisi data contoh. Jalankan dahulu: "
                        "python manage.py hapus_data_contoh"
                    )
                # Korwil yang sudah dibuat manual di SimLahan dipakai apa adanya.
                self.link(table, code, existing)
                self.report.add(table, "sudah ada")
                self.korwils[code] = existing
                if self.update:
                    self._fill_korwil(existing, row)
                    existing.save()
                continue
            values = self._korwil_values(row, code)
            korwil, _new = self.save(
                table, code, Korwil, values, created_at=to_datetime(row["created_at"])
            )
            if korwil is not None:
                self.korwils[code] = korwil

    def _korwil_values(self, row, code):
        korwil = Korwil(code=code)
        self._fill_korwil(korwil, row)
        return {
            name: getattr(korwil, name)
            for name in ("code", "name", "color", "geometry", "note")
        }

    def _fill_korwil(self, korwil, row):
        korwil.name = clean_text(row["area_name"] or row["name"], 128) or (
            f"Korwil {korwil.code}"
        )
        color = clean_text(row["color"])
        if re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
            korwil.color = color
        geometry = self.geometry(row["boundary_geojson"])
        multi = aset_geo.as_multipolygon(geometry) if geometry else None
        if multi is not None:
            korwil.geometry = multi
        project = clean_text(row["project"])
        if project and f"Proyek: {project}" not in korwil.note:
            korwil.note = "\n".join(filter(None, [korwil.note, f"Proyek: {project}"]))

    def geometry(self, value):
        """GeoJSON (teks/dict/larik koordinat poligon) atau EWKB heks →
        GEOSGeometry SRID 4326 yang sah, atau None."""
        if value in (None, ""):
            return None
        try:
            geom = _read_geometry(value)
        except (GEOSException, ValueError, TypeError):
            return None
        if geom.srid is None:
            geom.srid = 4326
        elif geom.srid != 4326:
            geom.transform(4326)
        if geom.empty:
            return None
        if not geom.valid:
            try:
                geom = geom.make_valid()
            except GEOSException:
                return None
        return geom

    # ------------------------------------------------------------------
    # Petugas
    # ------------------------------------------------------------------

    def import_people(self):
        table = "personel"
        rows = self.rows(table)
        self.report.add(table, "dibaca", len(rows))
        groups = Group.objects.in_bulk(
            [UserGroup.PETUGAS_LAPANGAN, UserGroup.KOORDINATOR_WILAYAH]
        )
        if len(groups) < 2:
            raise ValidationError(
                "Grup peran belum lengkap. Jalankan dahulu: "
                "python manage.py simlahan_bootstrap"
            )
        units = list(ServiceUnit.objects.order_by("pk"))
        people = {}
        for row in rows:
            person = row["id"]
            name = clean_text(row["nama"])
            if not self.include_test and (
                name.upper().startswith("UJI ")
                or clean_text(row["nama_login"]).lower().startswith("uji")
            ):
                self.test_people.add(person)
                self.report.skip(table, "akun uji coba sistem lama (UJI …)")
                continue
            people[person] = row
            values = {
                "first_name": name[:150],
                "last_name": "",
                "email": self._email(row["email"]),
                "department_name": clean_text(row["perusahaan"], 255),
                "is_active": to_bool(row["is_active"]),
                "is_staff": True,
            }
            seen, user = self.linked(table, person)
            if seen and user is None:
                self.report.skip(table, "sudah dihapus di SimLahan, tidak dibuat ulang")
                continue
            if user is None:
                user = self._new_user(row, values, groups, units)
            elif self.update:
                for key, value in values.items():
                    setattr(user, key, value)
                user.save()
                self.report.add(table, "diperbarui")
            else:
                self.report.add(table, "sudah ada")
            self.users[person] = user
        self._profiles(people)
        self._coordinators(people)

    def _new_user(self, row, values, groups, units):
        """Akun petugas baru tanpa sandi, dengan satu grup peran dan Korwil-nya."""
        User = get_user_model()
        name = values["first_name"]
        user = User(username=self._username(row["nama_login"], name), **values)
        user.set_unusable_password()
        user.save()
        self.link("personel", row["id"], user)
        self.report.add("personel", "dibuat")
        is_coordinator = clean_text(row["role"]) not in FIELD_ROLES
        group = (
            UserGroup.KOORDINATOR_WILAYAH
            if is_coordinator
            else UserGroup.PETUGAS_LAPANGAN
        )
        user.groups.add(groups[group])
        user.service_units.add(*units)
        own = self.korwil(row["korwil"])
        if own is not None:
            own.members.add(user)
        elif is_coordinator:
            # Pimpinan/staf lintas wilayah memantau semua Korwil.
            for korwil in self.korwils.values():
                if korwil.is_active:
                    korwil.members.add(user)
        else:
            self.report.warn(
                f"Petugas {name} tanpa Korwil yang dikenal "
                f"({row['korwil'] or '-'}); atur Korwil-nya di admin."
            )
        return user

    def _email(self, value) -> str:
        email = clean_text(value, 254).lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            return ""
        User = get_user_model()
        return "" if User.objects.filter(email__iexact=email).exists() else email

    def _username(self, login, name) -> str:
        User = get_user_model()
        base = re.sub(r"[^a-z0-9._-]+", "", clean_text(login).lower())[:120]
        if not base:
            base = (
                re.sub(r"[^a-z0-9]+", ".", name.lower()).strip(".")[:120] or "petugas"
            )
        candidates = [base, f"komando.{base}"] + [
            f"komando.{base}{n}" for n in range(2, 100)
        ]
        for candidate in candidates:
            if not User.objects.filter(username__iexact=candidate).exists():
                if candidate != base:
                    self.report.warn(
                        f"Nama pengguna '{base}' sudah dipakai; {name} memakai "
                        f"'{candidate}'."
                    )
                return candidate
        raise ValidationError(f"Tidak ada nama pengguna bebas untuk {name}.")

    def _profiles(self, people):
        for person, row in people.items():
            user = self.users.get(person)
            if user is None:
                continue
            supervisor = self.user(row["atasan_id"])
            if supervisor is not None and supervisor.pk == user.pk:
                supervisor = None
            position = clean_text(row["jabatan"] or row["role"], 128)
            profile = OfficerProfile.objects.filter(user=user).first()
            if profile is None:
                OfficerProfile.objects.create(
                    user=user, position=position, supervisor=supervisor
                )
            elif self.update or not profile.position:
                profile.position = position or profile.position
                profile.supervisor = supervisor or profile.supervisor
                profile.save()
        self._break_supervisor_cycles()

    def _break_supervisor_cycles(self):
        ids = [u.pk for u in self.users.values()]
        chain = dict(
            OfficerProfile.objects.filter(user_id__in=ids).values_list(
                "user_id", "supervisor_id"
            )
        )
        for start in ids:
            seen, current = set(), start
            while current and current not in seen:
                seen.add(current)
                current = chain.get(current)
            if current:  # kembali ke petugas yang sudah dilewati: melingkar
                OfficerProfile.objects.filter(user_id=current).update(supervisor=None)
                chain[current] = None
                self.report.warn(
                    "Rantai atasan melingkar di data lama diputus; periksa "
                    "atasan langsung di admin."
                )

    def _coordinators(self, people):
        for person, row in people.items():
            user = self.users.get(person)
            korwil = self.korwil(row["korwil"])
            if (
                user is None
                or korwil is None
                or clean_text(row["role"]) not in COORDINATOR_ROLES
                or not user.is_active
            ):
                continue
            if korwil.coordinator_id is None:
                korwil.coordinator = user
                korwil.save(update_fields=["coordinator", "modified_at"])

    # ------------------------------------------------------------------
    # Warga
    # ------------------------------------------------------------------

    def import_residents(self):
        table = "warga"
        rows = self.rows(table)
        self.report.add(table, "dibaca", len(rows))
        latest_komsos = {}
        for row in sorted(
            self.rows("komsos_history"), key=lambda r: (r["tanggal"] or "", r["id"])
        ):
            latest_komsos[row["warga_id"]] = row
        for row in rows:
            name = clean_text(row["nama"], 255)
            if not name:
                self.report.skip(table, "nama kosong")
                continue
            values = self._resident_values(row, name, latest_komsos.get(row["id"]))
            created = to_datetime(row["tanggal_input"]) or to_datetime(
                row["created_at"]
            )
            resident, _new = self.save(
                table,
                row["id"],
                Resident,
                values,
                flags={"_korwil_resolved": True},
                created_at=created,
            )
            if resident is not None:
                self.residents[row["id"]] = resident
                key = (clean_text(row["korwil"]).upper(), person_key(row["nama"]))
                self.resident_names[key].append(resident)

    def resident_for(self, row):
        """Warga untuk baris riwayat: ID warga, atau nama + Korwil yang unik.

        Riwayat perubahan di data lama memakai ID warga sebelum data warga
        dibangun ulang, jadi dicocokkan lewat nama di Korwil yang sama dan
        hanya bila tepat satu warga yang cocok.
        """
        resident = self.residents.get(row["warga_id"])
        if resident is not None:
            return resident, False
        key = (clean_text(row["korwil"]).upper(), person_key(row["nama_warga"]))
        found = self.resident_names.get(key) or []
        return (found[0], True) if len(found) == 1 else (None, False)

    def _resident_values(self, row, name, komsos):
        notes, area, age, years = self._resident_notes(row, komsos)
        return {
            "korwil": self.korwil(row["korwil"]),
            "head_name": name,
            "gender": GENDERS.get(clean_text(row["jenis_kelamin"]).lower(), ""),
            "age": age,
            "occupation": meaningful(row["pekerjaan"])[:128],
            "origin": meaningful(row["asal_daerah"])[:128],
            "years_living": years,
            "residency_status": RESIDENCY.get(
                clean_text(row["status_tempatan"]).lower(), ""
            ),
            "phone": self._phone(row["no_hp"]),
            "address": meaningful(row["alamat"])[:255],
            "location": to_point(row["lat"], row["lon"]),
            "stance": STANCES.get(
                clean_text(row["status_dukungan"]).lower(), enums.Stance.UNKNOWN
            ),
            "relocation_choice": self._relocation(meaningful(row["status_relokasi"])),
            "land_area_m2": area,
            "land_condition": meaningful(row["status_lahan"]),
            "note": "\n".join(notes),
        }

    def _resident_notes(self, row, komsos):
        """Catatan warga (isian lama yang tidak punya kolom sendiri), luas, umur,
        dan lama menetap hasil baca teks bebas."""
        area_text = meaningful(row["luas_lahan"])
        area = parse_area_m2(area_text) if area_text else None
        if area is None and komsos and to_decimal(komsos["luas_ha"]):
            area = parse_area_m2(f"{komsos['luas_ha']} ha")
        age = parse_years(row["umur"])
        living_text = meaningful(row["lama_menetap"])
        years = parse_years(living_text)
        if years is None and living_text.lower() == "sejak lahir":
            years = age
        tokoh = meaningful(row["status_tokoh"])
        farming = meaningful(komsos["status_penggarapan"]) if komsos else ""
        entries = [
            ("Status tokoh", "" if tokoh.lower() == "bukan" else tokoh),
            ("Status relokasi (data lama)", meaningful(row["status_relokasi"])),
            ("Luas lahan (data lama)", area_text),
            ("Pemilik lahan", meaningful(row["pemilik_lahan"])),
            ("Status penggarapan (data lama)", farming),
            ("Umur (data lama)", "" if age is not None else meaningful(row["umur"])),
            ("Lama menetap (data lama)", "" if years is not None else living_text),
            ("Jenis tanaman", meaningful(row["jenis_tanaman"])),
            ("Catatan", meaningful(row["catatan"])),
        ]
        notes = [f"ID warga sistem lama: {clean_text(row['warga_id_asli'])}"]
        notes += [f"{label}: {value}" for label, value in entries if value]
        return notes, area, age, years

    @staticmethod
    def _phone(value) -> str:
        text = clean_text(value)
        digits = re.sub(r"\D", "", text)
        if not 8 <= len(digits) <= 15:
            return ""
        return ("+" if text.startswith("+") else "") + digits

    @staticmethod
    def _relocation(text: str) -> str:
        lowered = text.lower()
        positive = ("sudah relokasi", "sudah pindah", "sudah daftar", "mau daftar")
        if any(word in lowered for word in positive):
            return enums.RelocationChoice.RELOCATION
        return enums.RelocationChoice.UNDECIDED

    # ------------------------------------------------------------------
    # Riwayat Komsos → kegiatan
    # ------------------------------------------------------------------

    def _match_officer(self, names: str):
        """Petugas dari nama di data lama, hanya bila cocok tepat satu orang."""
        first = re.split(r"[|,/&]", names or "", maxsplit=1)[0]
        wanted = name_tokens(first)
        if not wanted:
            return None
        if not hasattr(self, "_officer_tokens"):
            self._officer_tokens = [
                (name_tokens(u.first_name), u) for u in self.users.values()
            ]
        found = [u for tokens, u in self._officer_tokens if wanted <= tokens]
        active = [u for u in found if u.is_active]
        if len(found) == 1:
            return found[0]
        if len(active) == 1:
            return active[0]
        return None

    def import_komsos_history(self):
        table = "komsos_history"
        rows = self.rows(table)
        self.report.add(table, "dibaca", len(rows))
        matched = 0
        for row in rows:
            resident = self.residents.get(row["warga_id"])
            if resident is None:
                self.report.skip(table, "warga tidak ditemukan")
                continue
            day = to_date(row["tanggal"]) or to_date(row["bulan"])
            started = at_noon(day) if day else to_datetime(row["created_at"])
            officer = self._match_officer(row["personil_kanonik"])
            matched += officer is not None
            number = to_int(row["komsos_ke"]) or 1
            outcome = [
                (
                    f"Sikap saat itu: {clean_text(row['status_dukungan_asli'])}"
                    if meaningful(row["status_dukungan_asli"])
                    else ""
                ),
                (
                    f"Catatan pro/kontra: {meaningful(row['catatan_prokontra'])}"
                    if meaningful(row["catatan_prokontra"])
                    else ""
                ),
                (
                    f"Tindak lanjut: {meaningful(row['tindak_lanjut'])}"
                    if meaningful(row["tindak_lanjut"])
                    else ""
                ),
                (
                    f"Status relokasi saat itu: {meaningful(row['status_relokasi'])}"
                    if meaningful(row["status_relokasi"])
                    else ""
                ),
                "" if day else "Tanggal kunjungan tidak tercatat di data lama.",
                (
                    f"Sumber: {clean_text(row['sumber_file'])}"
                    if meaningful(row["sumber_file"])
                    else ""
                ),
            ]
            values = {
                "korwil": self.korwil(row["korwil"]) or resident.korwil,
                "activity_type": enums.ActivityType.KOMSOS,
                "title": clean_text(f"Komsos ke-{number} – {resident.head_name}", 255),
                "description": meaningful(row["ringkasan_hasil"]),
                "companion": meaningful(row["personil_kanonik"])[:255],
                "location_name": meaningful(row["alamat_saat_itu"])[:255],
                "started_at": started,
                "outcome": "\n".join(filter(None, outcome)),
                "reported_by": officer,
                "verified": True,
            }
            activity, new = self.save(
                table,
                row["id"],
                Activity,
                values,
                flags={"_korwil_resolved": True},
                created_at=to_datetime(row["created_at"]),
            )
            if activity is None:
                continue
            self.activities[f"komsos:{row['id']}"] = activity
            if new:
                activity.residents.add(resident)
                activity.refresh_effort()
                if number == 1 and resident.registered_activity_id is None:
                    Resident.objects.filter(pk=resident.pk).update(
                        registered_activity=activity
                    )
                    resident.registered_activity = activity
        if rows:
            self.report.add(table, "petugas dikenali", matched)
        self._touch_residents()

    def _touch_residents(self):
        latest = defaultdict(lambda: None)
        through = Activity.residents.through
        pairs = through.objects.filter(
            resident_id__in=[r.pk for r in self.residents.values()]
        ).values_list("resident_id", "activity__started_at")
        for resident_id, started in pairs:
            day = timezone.localtime(started).date()
            if latest[resident_id] is None or day > latest[resident_id]:
                latest[resident_id] = day
        for resident in self.residents.values():
            day = latest[resident.pk]
            if day and (
                resident.last_visited_on is None or resident.last_visited_on < day
            ):
                Resident.objects.filter(pk=resident.pk).update(last_visited_on=day)

    # ------------------------------------------------------------------
    # Riwayat sikap & luas lahan
    # ------------------------------------------------------------------

    def import_resident_changes(self):
        self._stance_changes()
        self._history_stances()
        self._area_changes()

    def _stance_changes(self):
        table = "komsos_perubahan_dukungan_raw"
        rows = self.rows(table)
        self.report.add(table, "dibaca", len(rows))
        for row in rows:
            resident, by_name = self.resident_for(row)
            old = STANCES.get(clean_text(row["dari_kategori"]).lower())
            new = STANCES.get(clean_text(row["ke_kategori"]).lower())
            if resident is None:
                self.report.skip(table, "warga tidak ada di data warga terbaru")
                continue
            if old is None or new is None:
                self.report.skip(table, "sikap tidak dikenali")
                continue
            if old == new:
                self.report.skip(table, "sikap tidak berubah (hanya beda tulisan)")
                continue
            moment = at_noon(to_date(row["tanggal"])) or to_datetime(row["created_at"])
            change, new_row = self.save(
                table,
                row["id"],
                StanceChange,
                {"resident": resident, "old_stance": old, "new_stance": new},
            )
            if new_row and moment:
                StanceChange.objects.filter(pk=change.pk).update(changed_at=moment)
            if new_row and by_name:
                self.report.add(table, "dicocokkan lewat nama + Korwil")

    def _history_stances(self):
        history = [
            r
            for r in self.rows("status_history")
            if r["entity_type"] == "warga" and r["field_changed"] == "status_dukungan"
        ]
        for row in history:
            resident = self.residents.get(row["entity_id"])
            old = STANCES.get(clean_text(row["old_value"]).lower())
            new = STANCES.get(clean_text(row["new_value"]).lower())
            if resident is None or old is None or new is None or old == new:
                self.report.skip(
                    "status_history", "perubahan sikap warga yang sudah tidak ada"
                )
                continue
            change, new_row = self.save(
                "status_history",
                row["id"],
                StanceChange,
                {
                    "resident": resident,
                    "old_stance": old,
                    "new_stance": new,
                    "changed_by": self.user(row["changed_by_id"]),
                },
            )
            if new_row:
                StanceChange.objects.filter(pk=change.pk).update(
                    changed_at=to_datetime(row["created_at"])
                )

    def _area_changes(self):
        table = "komsos_perubahan_luas"
        rows = self.rows(table)
        self.report.add(table, "dibaca", len(rows))
        for row in rows:
            resident, by_name = self.resident_for(row)
            before = to_decimal(row["luas_sebelum"])
            after = to_decimal(row["luas_sesudah"])
            if resident is None:
                self.report.skip(table, "warga tidak ada di data warga terbaru")
                continue
            if after is None:
                self.report.skip(table, "luas tidak dikenali")
                continue
            old = parse_area_m2(f"{before} ha") if before is not None else None
            new_area = parse_area_m2(f"{after} ha")
            change, new_row = self.save(
                table,
                row["id"],
                LandAreaChange,
                {"resident": resident, "old_area_m2": old, "new_area_m2": new_area},
            )
            moment = at_noon(to_date(row["tanggal"])) or to_datetime(row["created_at"])
            if new_row and moment:
                LandAreaChange.objects.filter(pk=change.pk).update(changed_at=moment)
            if new_row and by_name:
                self.report.add(table, "dicocokkan lewat nama + Korwil")

    # ------------------------------------------------------------------
    # Kegiatan
    # ------------------------------------------------------------------

    def import_activities(self):
        table = "kegiatan"
        rows = self.rows(table)
        self.report.add(table, "dibaca", len(rows))
        for row in rows:
            if self.is_test(row["personel_id"]) or self.is_test(row["created_by"]):
                self.report.skip(table, "dibuat akun uji coba")
                continue
            kind = ACTIVITY_TYPES.get(
                clean_text(row["jenis_kegiatan"]).lower(), enums.ActivityType.OTHER
            )
            extra = to_json(row["supplementary_data"], {})
            extra = extra if isinstance(extra, dict) else {}
            reporter = self.user(row["personel_id"]) or self.user(row["created_by"])
            location = to_point(row["lat"], row["lon"])
            subject = meaningful(row["nama_warga"]) or meaningful(
                row["lokasi_kegiatan"]
            )
            title = clean_text(row["jenis_kegiatan"]) or "Kegiatan"
            if subject:
                title = f"{title} – {subject}"
            companions = [
                meaningful(row[f"personil_{n}"])
                for n in (2, 3, 4)
                if meaningful(row[f"personil_{n}"])
            ]
            values = {
                "korwil": self.korwil(row["korwil"]),
                "activity_type": kind,
                "title": title[:255],
                "description": meaningful(row["narasi"]),
                "companion": ", ".join(companions)[:255],
                "location_name": meaningful(row["lokasi_kegiatan"])[:255],
                "started_at": at_noon(to_date(row["tanggal"]))
                or to_datetime(row["created_at"]),
                "location": location,
                "outcome": self._activity_outcome(row, extra),
                "reported_by": reporter,
                "verified": True,
                "distance_m": self._distance(extra.get("jarak_tempuh")),
                "task": None,
            }
            if kind == enums.ActivityType.OTHER:
                # Rubrik dampak tidak ada di data lama: nilai terendah, perlu dinilai ulang.
                values.update(impact_scope=1, impact_risk=1, impact_result=1)
            activity, new = self.save(
                table,
                row["id"],
                Activity,
                values,
                flags={"_korwil_resolved": True},
                created_at=to_datetime(row["created_at"]),
            )
            if activity is None:
                continue
            self.activities[row["id"]] = activity
            if not new:
                continue
            photos = self.photos_from(
                parse_pg_array(row["foto_urls"]) + [row["foto"] or ""]
            )
            for data in photos:
                photo = ActivityPhoto(activity=activity, location=location)
                self.save_photo(photo.photo, data)
                photo.save()
            self.report.add(table, "foto", len(photos))
            if kind == enums.ActivityType.HUNTING_PARK and location is not None:
                self._hunting_patrol(activity, extra)
            activity.refresh_effort()

    def _activity_outcome(self, row, extra) -> str:
        lines = []
        for key, label in (("hasil", "Hasil"), ("rekomendasi", "Rekomendasi")):
            if meaningful(row[key]):
                lines.append(f"{label}: {meaningful(row[key])}")
        if meaningful(row["status_komsos"]):
            lines.append(f"Status komsos: {meaningful(row['status_komsos'])}")
        labels = {
            "mode": "Mode",
            "penguasaan": "Bidang dikuasai",
            "lahan_baru": "Lahan baru",
            "total_luas_ha": "Total luas (ha)",
            "poin_bidang": "Poin bidang",
            "luas_lahan": "Luas lahan",
            "kondisi_lahan": "Kondisi lahan",
            "status_penggarapan": "Status penggarapan",
            "nama_pasangan": "Nama pasangan",
            "pekerjaan_pasangan": "Pekerjaan pasangan",
            "jumlah_anak": "Jumlah anak",
            "data_anak": "Data anak",
        }
        for key, label in labels.items():
            value = extra.get(key)
            if value not in (None, "", [], {}):
                lines.append(f"{label}: {clean_text(value)}")
        return "\n".join(lines)

    @staticmethod
    def _distance(value) -> int | None:
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(km|m)\b", str(value or "").lower())
        if not match:
            return None
        number = Decimal(match.group(1).replace(",", "."))
        meters = number * 1000 if match.group(2) == "km" else number
        return int(meters) if 0 <= meters < 10**7 else None

    def _hunting_patrol(self, activity, extra):
        def moment(key):
            return to_datetime(extra.get(key)) if extra.get(key) else None

        report = HuntingParkPatrol.objects.create(
            activity=activity,
            grid=clean_text(extra.get("grid"), 255),
            objective=clean_text(extra.get("objektif"), 255),
            patrol_started_at=moment("waktu_mulai"),
            patrol_ended_at=moment("waktu_selesai"),
        )
        for item in extra.get("temuan") or []:
            if not isinstance(item, dict) or not clean_text(item.get("deskripsi")):
                continue
            HuntingParkFinding.objects.create(
                patrol=report,
                category=FINDING_CATEGORIES.get(
                    clean_text(item.get("kategori")).lower(),
                    enums.FindingCategory.OTHER,
                ),
                description=clean_text(item.get("deskripsi"), 500),
                quantity=to_int(item.get("jumlah")),
                forest_status=clean_text(item.get("status_hutan"), 128),
                note=clean_text(item.get("keterangan"), 500),
            )
        for key, kind in (
            ("dirawat", enums.SeedlingKind.TENDED),
            ("diproduksi", enums.SeedlingKind.PRODUCED),
        ):
            for item in extra.get(key) or []:
                if not isinstance(item, dict):
                    continue
                species = clean_text(
                    item.get("jenis") or item.get("nama") or item.get("species"), 128
                )
                quantity = to_int(item.get("jumlah"))
                if species and quantity and quantity > 0:
                    Seedling.objects.create(
                        patrol=report, kind=kind, species=species, quantity=quantity
                    )

    # ------------------------------------------------------------------
    # Tugas
    # ------------------------------------------------------------------

    def import_tasks(self):
        table = "tasks"
        rows = self.rows(table)
        self.report.add(table, "dibaca", len(rows))
        helpers, givers, history = self._task_related()
        for row in rows:
            if self.is_test(row["assigned_to"]) or self.is_test(row["assigned_by"]):
                self.report.skip(table, "melibatkan akun uji coba")
                continue
            task, new = self.save(
                table,
                row["id"],
                Task,
                self._task_values(row),
                created_at=to_datetime(row["created_at"]),
            )
            if task is None:
                continue
            self.tasks[row["id"]] = task
            if new:
                self._task_people(task, row, helpers[row["id"]], givers[row["id"]])
                self._task_events(task, row, history[row["id"]])
        self._link_activity_tasks()

    def _task_related(self):
        helpers = defaultdict(list)
        for row in self.rows("task_assignees"):
            helpers[row["task_id"]].append(row)
        givers = defaultdict(list)
        for row in self.rows("task_giver_points"):
            givers[row["task_id"]].append(row)
        history = defaultdict(list)
        for row in self.rows("status_history"):
            if row["entity_type"] == "task" and row["field_changed"] == "lifecycle":
                history[row["entity_id"]].append(row)
        return helpers, givers, history

    def _task_values(self, row):
        points = to_int(row["poin_nilai"]) or 0
        if points > enums.MAX_TASK_POINTS:
            self.report.warn(
                f"Tugas '{clean_text(row['title'])}': nilai poin {points} "
                f"dipangkas jadi {enums.MAX_TASK_POINTS} (batas SimLahan); poin yang "
                "sudah diterima petugas tetap seperti data lama."
            )
        notes = meaningful(row["completion_notes"])
        description = meaningful(row["description"])
        if notes:
            description = f"{description}\n\nCatatan penyelesaian: {notes}".strip()
        status = TASK_STATUS.get(row["status"], aset_enums.TaskStatus.NEW)
        values = {
            "title": clean_text(row["title"], 255) or "Tugas",
            "description": description,
            "task_type": aset_enums.TaskType.OTHER,
            "priority": TASK_PRIORITY.get(row["priority"], aset_enums.Priority.NORMAL),
            "status": status,
            "assignee": self.user(row["assigned_to"]),
            "start_date": to_date(row["created_at"]),
            "due_date": to_date(row["due_date"]),
            "completed_date": to_date(row["completed_at"]),
            "progress": 100 if status == aset_enums.TaskStatus.DONE else 0,
            "korwil": self.korwil(row["korwil"]),
            "activity_type": ACTIVITY_TYPES.get(
                clean_text(row["jenis_kegiatan"]).lower(),
                enums.ActivityType.OTHER if row["jenis_kegiatan"] else "",
            ),
            "point_value": min(points, enums.MAX_TASK_POINTS),
            "created_by": self.user(row["assigned_by"]),
        }
        if (
            values["start_date"]
            and values["due_date"]
            and values["due_date"] < values["start_date"]
        ):
            values["start_date"] = values["due_date"]
        return values

    def _link_activity_tasks(self):
        for row in self.rows("kegiatan"):
            activity = self.activities.get(row["id"])
            task = self.tasks.get(row["task_id"])
            if activity is not None and task is not None and activity.task_id is None:
                Activity.objects.filter(pk=activity.pk).update(task=task)

    def _task_people(self, task, row, helpers, givers):
        for helper in helpers:
            user = self.user(helper["personel_id"])
            if user is None:
                continue
            if user.pk != task.assignee_id:
                task.contributors.add(user)
            earned = to_int(helper["poin_earned"]) or 0
            if to_bool(helper["poin_given"]) and earned > 0:
                role = (
                    enums.TaskPointRole.ASSIGNEE
                    if user.pk == task.assignee_id
                    else enums.TaskPointRole.CONTRIBUTOR
                )
                self._task_point(task, user, role, earned, task.completed_date)
        for giver in givers:
            user = self.user(giver["personel_id"])
            points = to_int(giver["poin"]) or 0
            if user is not None and points > 0:
                self._task_point(
                    task,
                    user,
                    enums.TaskPointRole.GIVER,
                    points,
                    to_datetime(giver["given_at"]),
                )

    def _task_point(self, task, user, role, points, when):
        if TaskPoint.objects.filter(task=task, user=user).exists():
            return
        moment = when if isinstance(when, datetime.datetime) else at_noon(when)
        TaskPoint.objects.create(
            task=task,
            user=user,
            role=role,
            points=points,
            awarded_at=moment or timezone.now(),
        )
        self.report.add("tasks", "poin KPI")

    def _task_events(self, task, row, history):
        TaskEvent.objects.create(
            task=task,
            kind=enums.TaskEventKind.CREATED,
            actor=task.created_by,
            note=f"Untuk {task.assignee.get_full_name()}" if task.assignee else "",
            created_at=to_datetime(row["created_at"]) or timezone.now(),
        )
        attachment = to_json(row["attachments"], [])
        photo = None
        if isinstance(attachment, dict):
            photos = self.photos_from([attachment.get("foto")])
            photo = photos[0] if photos else None
        submitted = None
        for item in sorted(history, key=lambda r: r["created_at"] or ""):
            kind = TASK_EVENTS.get(item["new_value"])
            if kind is None:
                continue
            event = TaskEvent.objects.create(
                task=task,
                kind=kind,
                actor=self.user(item["changed_by_id"]),
                note=meaningful(item["notes"]),
                created_at=to_datetime(item["created_at"]) or timezone.now(),
            )
            if kind == enums.TaskEventKind.SUBMITTED:
                submitted = event
        if photo is not None:
            if submitted is None:
                submitted = TaskEvent(
                    task=task,
                    kind=enums.TaskEventKind.SUBMITTED,
                    actor=task.assignee,
                    note=meaningful(row["completion_notes"]),
                    created_at=to_datetime(row["completed_at"])
                    or to_datetime(row["updated_at"])
                    or timezone.now(),
                )
            submitted.location = to_point(attachment.get("lat"), attachment.get("lon"))
            self.save_photo(submitted.photo, photo)
            submitted.save()
            self.report.add("tasks", "foto")

    # ------------------------------------------------------------------
    # Laporan harian
    # ------------------------------------------------------------------

    def import_daily_reports(self):
        table = "laporan_harian"
        rows = sorted(self.rows(table), key=lambda r: to_int(r["id"]) or 0)
        self.report.add(table, "dibaca", len(rows))
        imported = {}
        for row in rows:
            author = self.user(row["dibuat_oleh_id"])
            if self.is_test(row["dibuat_oleh_id"]):
                self.report.skip(table, "dibuat akun uji coba")
                continue
            if author is None or not clean_text(row["isi"]):
                self.report.skip(table, "pembuat atau isi tidak dikenali")
                continue
            values = self._daily_report_values(row, author)
            report, new = self.save(
                table, row["id"], DailyReport, values, created_at=values["sent_at"]
            )
            if report is None:
                continue
            imported[row["id"]] = (report, row)
            if new:
                self._daily_report_events(report)
        self._link_report_sources(imported)

    def _daily_report_values(self, row, author):
        stack = to_json(row["revisi_stack"], [])
        stack = [s for s in stack if isinstance(s, dict)]
        history = to_json(row["revisi_history"], [])
        history = [h for h in history if isinstance(h, dict)]
        profile = OfficerProfile.objects.filter(user=author).first()
        recipient = (self.user(stack[0].get("id")) if stack else None) or (
            profile.supervisor if profile else None
        )
        sent_at = to_datetime(row["terkirim_pada"]) or to_datetime(row["created_at"])
        values = {
            "report_date": to_date(row["tanggal"]) or timezone.localdate(),
            "author": author,
            "author_position": profile.position if profile else "",
            "recipient": recipient,
            "korwil": self.korwil(row["korwil"]),
            "content": clean_text(row["isi"]),
            "status": enums.DailyReportStatus.SENT,
            "sent_at": sent_at or timezone.now(),
        }
        if row["status"] == "dikembalikan":
            back = [h for h in history if h.get("aksi") == "kembalikan"]
            returner = self.user(back[-1].get("dari_id")) if back else recipient
            values.update(
                status=enums.DailyReportStatus.RETURNED,
                revision_owner=author,
                revision_stack=[returner.pk] if returner else [],
                return_note=meaningful(row["return_note"]),
                returned_by=returner,
                returned_at=to_datetime(row["returned_at"]),
            )
        return values

    @staticmethod
    def _daily_report_events(report):
        DailyReportEvent.objects.create(
            report=report,
            action=enums.DailyReportAction.SENT,
            actor=report.author,
            target=report.recipient,
            created_at=report.sent_at,
        )
        if report.status == enums.DailyReportStatus.RETURNED:
            DailyReportEvent.objects.create(
                report=report,
                action=enums.DailyReportAction.RETURNED,
                actor=report.returned_by,
                target=report.author,
                note=report.return_note,
                created_at=report.returned_at or timezone.now(),
            )

    def _link_report_sources(self, imported):
        """Kegiatan dan laporan bawahan yang dirangkum sebuah laporan."""
        for report, row in imported.values():
            sources = to_json(row["sumber_ids"], {})
            sources = sources if isinstance(sources, dict) else {}
            for activity_id in sources.get("kegiatan") or []:
                activity = self.activities.get(str(activity_id))
                if activity is not None and activity.daily_report_id is None:
                    Activity.objects.filter(pk=activity.pk).update(daily_report=report)
            children = (imported.get(str(i)) for i in sources.get("laporan") or [])
            for child, _row in filter(None, children):
                if child.consolidated_into_id is None:
                    DailyReport.objects.filter(pk=child.pk).update(
                        consolidated_into=report,
                        status=enums.DailyReportStatus.FORWARDED,
                    )

    # ------------------------------------------------------------------
    # Bidang penguasaan
    # ------------------------------------------------------------------

    def import_land_plots(self):
        table = "land_polygons"
        rows = self.rows(table)
        self.report.add(table, "dibaca", len(rows))
        for row in rows:
            geometry = self.geometry(row["polygon_geojson"])
            multi = aset_geo.as_multipolygon(geometry) if geometry else None
            if multi is None or multi.empty:
                self.report.skip(table, "batas bidang tidak sah")
                continue
            plot, _new = self.save(
                table,
                row["id"],
                LandPlot,
                self._land_plot_values(row, multi),
                created_at=to_datetime(row["created_at"]),
            )
            if plot is not None:
                self.plots[row["id"]] = plot
        self._land_plot_history()

    def _land_plot_values(self, row, multi):
        controlled = clean_text(row["status_penguasaan"]) == "sudah"
        lahan = meaningful(row["lahan"])
        notes = [meaningful(row["keterangan"])]
        if lahan and lahan != meaningful(row["nama_pemilik"]):
            notes.append(f"Lahan: {lahan}")
        if meaningful(row["no_berkas"]):
            notes.append(f"No. berkas: {meaningful(row['no_berkas'])}")
        if meaningful(row["kategori_priority"]):
            notes.append(f"Kategori: {meaningful(row['kategori_priority'])}")
        values = {
            "name": clean_text(row["titik"], 255),
            "owner_name": meaningful(row["nama_pemilik"])[:255],
            "korwil": self.korwil(row["korwil"]),
            "geometry": multi,
            "official_area_ha": self._area_ha(row["luas_ha"]),
            "control_status": (
                enums.ControlStatus.CONTROLLED
                if controlled
                else enums.ControlStatus.PENDING
            ),
            "controlled_on": (to_date(row["tanggal_dikuasai"]) if controlled else None),
            "control_team": (
                meaningful(row["tim_penguasaan"])[:255] if controlled else ""
            ),
            "source": clean_text(row["source"], 255),
            "note": "\n".join(filter(None, notes)),
        }
        return values

    def _land_plot_history(self):
        for row in self.rows("status_history"):
            if row["entity_type"] != "land_polygon":
                continue
            plot = self.plots.get(row["entity_id"])
            new = clean_text(row["new_value"])
            if plot is None or new not in enums.ControlStatus.values:
                self.report.skip("status_history", "riwayat bidang yang tidak ada")
                continue
            old = clean_text(row["old_value"])
            change, created = self.save(
                "status_history",
                row["id"],
                LandPlotChange,
                {
                    "plot": plot,
                    "old_status": old if old in enums.ControlStatus.values else "",
                    "new_status": new,
                    "changed_by": self.user(row["changed_by_id"]),
                    "note": meaningful(row["notes"])[:255],
                },
            )
            if created:
                LandPlotChange.objects.filter(pk=change.pk).update(
                    changed_at=to_datetime(row["created_at"])
                )

    @staticmethod
    def _area_ha(value) -> Decimal | None:
        number = to_decimal(value)
        if number is None or number < 0 or number >= 10**8:
            return None
        return number.quantize(Decimal("0.0001"))

    # ------------------------------------------------------------------
    # Uji tanah PLTS
    # ------------------------------------------------------------------

    def import_geotech(self):
        table = "soil_test"
        rows = self.rows(table)
        self.report.add(table, "dibaca", len(rows))
        statuses = {
            "completed": enums.GeotechWorkStatus.DONE,
            "in progress": enums.GeotechWorkStatus.IN_PROGRESS,
            "issue": enums.GeotechWorkStatus.STOPPED,
            "pending": enums.GeotechWorkStatus.NOT_STARTED,
        }
        for row in rows:
            code = " ".join(clean_text(row["point_id"]).split())[:64]
            key = geotech_key(code)
            if not key:
                self.report.skip(table, "kode titik kosong")
                continue
            status = clean_text(row["status"]).lower()
            notes = [
                f"{label}: {meaningful(row[col])}"
                for col, label in (
                    ("notes", "Catatan"),
                    ("assigned_to", "Petugas"),
                    ("last_operator", "Operator terakhir"),
                    ("jenis_test", "Jenis uji"),
                )
                if meaningful(row[col])
            ]
            values = {
                "code": code,
                "method": self._geotech_method(key),
                "area_name": clean_text(row["project"], 128),
                "zone_name": meaningful(row["wilayah"])[:128],
                "location": to_point(row["lat"], row["lon"]),
                "work_status": statuses.get(
                    status, enums.GeotechWorkStatus.NOT_STARTED
                ),
                "obstacle": "Bermasalah (data lama)" if status == "issue" else "",
                "access": meaningful(row["akses_medan"])[:255],
                "survey_note": meaningful(row["catatan_survey"]),
                "work_note": "\n".join(notes),
                "finished_on": to_date(row["completed_at"]),
                "social_condition": self._social(row["kondisi_sosial"]),
            }
            existing = GeotechPoint.objects.filter(code_key=key).first()
            seen, _obj = self.linked(table, row["id"])
            if existing is not None and not seen:
                self.link(table, row["id"], existing)
                self.report.add(table, "sudah ada (kode sama)")
                continue
            self.save(
                table,
                row["id"],
                GeotechPoint,
                values,
                created_at=to_datetime(row["created_at"]),
            )

    @staticmethod
    def _geotech_method(key: str) -> str:
        for word, method in (
            ("CPT", enums.GeotechMethod.SONDIR),
            ("ERT", enums.GeotechMethod.RESISTIVITY),
            ("TP", enums.GeotechMethod.TEST_PIT),
            ("BH", enums.GeotechMethod.BOREHOLE),
        ):
            if word in key:
                return method
        return enums.GeotechMethod.OTHER

    @staticmethod
    def _social(value) -> str:
        text = clean_text(value).lower()
        if not text:
            return enums.SocialCondition.UNCHECKED
        if "belum" in text or "tidak" in text:
            return enums.SocialCondition.NOT_CONDUCIVE
        if "masalah" in text:
            return enums.SocialCondition.PROBLEM
        if "kondusif" in text or "aman" in text:
            return enums.SocialCondition.CONDUCIVE
        return enums.SocialCondition.UNCHECKED

    # ------------------------------------------------------------------
    # Patroli SMART
    # ------------------------------------------------------------------

    def import_patrols(self):
        table = "patrol_sessions"
        rows = self.rows(table)
        self.report.add(table, "dibaca", len(rows))
        observations = defaultdict(list)
        for row in self.rows("patrol_observations"):
            observations[row["session_id"]].append(row)
        groups = defaultdict(list)
        for row in rows:
            groups[clean_text(row["patrol_id"]) or row["id"]].append(row)
        for _patrol_id, items in groups.items():
            items.sort(
                key=lambda r: (bool(r["kegiatan_id"]), r["created_at"] or ""),
                reverse=True,
            )
            chosen, duplicates = items[0], items[1:]
            if duplicates:
                self.report.skip(
                    table, "unggahan ganda patroli yang sama", len(duplicates)
                )
            self._patrol(chosen, observations[chosen["id"]])

    def _patrol(self, row, observations):
        table = "patrol_sessions"
        coords = to_json(row["track_geojson"], [])
        points = []
        for item in coords if isinstance(coords, list) else []:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                point = to_point(item[1], item[0])
                if point is not None:
                    points.append((point.x, point.y))
        activity = self.activities.get(row["kegiatan_id"])

        def opaque(value):
            # ID internal SMART (mis. "e:3602…") tidak bermakna bagi pembaca.
            text = clean_text(value, 255)
            return "" if re.fullmatch(r"[a-z]{1,3}:[0-9a-f]{16,}", text) else text

        values = {
            "activity": activity,
            "korwil": activity.korwil if activity else None,
            "smart_patrol_id": clean_text(row["patrol_id"], 128),
            "name": clean_text(row["objektif"] or row["nama"], 255) or "Patroli SMART",
            "started_at": to_datetime(row["waktu_mulai"]),
            "ended_at": to_datetime(row["waktu_selesai"]),
            "leader": opaque(row["leader"]),
            "team": opaque(row["team"]),
            "station": opaque(row["station"]),
            "transport": opaque(row["transport"])[:128],
            "comments": clean_text(row["nama"]),
            "distance_m": max(0, min(int(to_decimal(row["jarak_m"]) or 0), 2**31 - 1)),
            "track": LineString(points, srid=4326) if len(points) > 1 else None,
            "source_name": clean_text(row["source"], 255),
        }
        session, new = self.save(
            table,
            row["id"],
            PatrolSession,
            values,
            flags={"_korwil_resolved": activity is not None},
            created_at=to_datetime(row["created_at"]),
        )
        if session is None or not new:
            return
        observations.sort(key=lambda r: (to_int(r["seq"]) or 0, r["waktu"] or ""))
        for row_obs in observations:
            point = to_point(row_obs["lat"], row_obs["lon"])
            if point is None:
                self.report.skip("patrol_observations", "tanpa koordinat")
                continue
            leg = to_decimal(row_obs["leg_distance"])
            observation = PatrolObservation.objects.create(
                session=session,
                seq=max(0, to_int(row_obs["seq"]) or 0),
                kind=clean_text(row_obs["tipe"], 64) or "Observation",
                location=point,
                observed_at=to_datetime(row_obs["waktu"]),
                comment=meaningful(row_obs["komentar"]),
                leg_distance_m=(
                    leg.quantize(Decimal("0.1"))
                    if leg is not None and 0 <= leg < 10**8
                    else None
                ),
            )
            self.link("patrol_observations", row_obs["id"], observation)
            self.report.add("patrol_observations", "dibuat")
            photos = self.photos_from(to_json(row_obs["foto"], []) or [])
            for data in photos:
                photo = PatrolPhoto(observation=observation)
                self.save_photo(photo.photo, data)
                photo.save()
            self.report.add("patrol_observations", "foto", len(photos))
        if activity is not None:
            activity.refresh_effort()

    # ------------------------------------------------------------------
    # Jejak GPS
    # ------------------------------------------------------------------

    def import_tracks(self):
        table = "gps_tracking"
        rows = self.rows(table)
        self.report.add(table, "dibaca", len(rows))
        cutoff = timezone.now() - datetime.timedelta(days=TRACK_KEEP_DAYS)
        for row in rows:
            user = self.user(row["personel_id"])
            moment = to_datetime(row["created_at"])
            point = to_point(row["lat"], row["lon"])
            accuracy = to_decimal(row["accuracy"])
            if self.is_test(row["personel_id"]):
                self.report.skip(table, "akun uji coba")
            elif user is None:
                self.report.skip(table, "petugas tidak dikenali")
            elif point is None:
                self.report.skip(table, "koordinat kosong/0,0")
            elif moment is None or moment < cutoff:
                self.report.skip(
                    table, f"lebih lama dari {TRACK_KEEP_DAYS} hari (masa simpan jejak)"
                )
            elif accuracy is not None and accuracy > 1000:
                self.report.skip(table, "akurasi GPS lebih buruk dari 1 km")
            else:
                self.save(
                    table,
                    row["id"],
                    OfficerTrackPoint,
                    {
                        "user": user,
                        "location": point,
                        "accuracy_m": (
                            accuracy.quantize(Decimal("0.1"))
                            if accuracy is not None
                            else None
                        ),
                        "recorded_at": moment,
                    },
                )

    # ------------------------------------------------------------------
    # Lapisan peta referensi
    # ------------------------------------------------------------------

    def import_overlays(self):
        self._rtrw_overlays()
        self._geo_layer_overlays()
        self._user_overlays()
        self._lahan_overlay()

    def _rtrw_overlays(self):
        zones = defaultdict(list)
        for row in self.rows("rtrw_zones"):
            zones[clean_text(row["source_file"]) or "rtrw"].append(row)
        self.report.add("rtrw_zones", "dibaca", len(self.rows("rtrw_zones")))
        for source, rows in sorted(zones.items()):
            features = []
            for row in rows:
                tier = clean_text(row["zone_tier"])
                props = {
                    "zona": tier,
                    "sub_kategori": clean_text(row["sub_category"], 255),
                    "kode_lapisan": clean_text(row["layer_code"], 255),
                    "pulau": clean_text(row["nampul"], 255),
                    "luas_ha": clean_text(row["area_ha"], 32),
                }
                features.append(
                    (
                        clean_text(row["zone_name"], 255),
                        self.geometry(row["geom"]),
                        {k: v for k, v in props.items() if v},
                    )
                )
            self._overlay(
                "rtrw_zones",
                source,
                name=RTRW_SOURCES.get(source, f"Tata ruang ({source})"),
                kind=aset_enums.OverlayKind.SPATIAL_PLAN,
                features=features,
                in_command=True,
            )

    def _geo_layer_overlays(self):
        rows = self.rows("rempang_geo_layers")
        self.report.add("rempang_geo_layers", "dibaca", len(rows))
        layers = defaultdict(list)
        for row in rows:
            if not to_bool(row["is_active"]):
                self.report.skip(
                    "rempang_geo_layers", "objek dinonaktifkan di data lama"
                )
                continue
            layers[clean_text(row["category"]).upper() or "OTHER"].append(row)
        for category, items in sorted(layers.items()):
            kind, label = GEO_LAYER_KINDS.get(category, GEO_LAYER_KINDS["OTHER"])
            features = []
            for row in items:
                meta = to_json(row["meta"], {})
                props = {
                    "kategori": category,
                    "sub_kategori": clean_text(row["subcategory"], 255),
                    "luas_ha": clean_text(row["area_ha"], 32),
                }
                if isinstance(meta, dict):
                    props.update(_scalar_props(meta))
                features.append(
                    (
                        clean_text(row["name"], 255),
                        self.geometry(row["geometry"]),
                        {k: v for k, v in props.items() if v},
                    )
                )
            self._overlay(
                "rempang_geo_layers",
                category,
                name=label,
                kind=kind,
                features=features,
                in_command=True,
            )

    def _user_overlays(self):
        rows = self.rows("user_geo_layers")
        self.report.add("user_geo_layers", "dibaca", len(rows))
        for row in rows:
            data = to_json(row["geojson"], {})
            features = []
            for item in (data.get("features") or []) if isinstance(data, dict) else []:
                if not isinstance(item, dict):
                    continue
                props = (
                    item.get("properties")
                    if isinstance(item.get("properties"), dict)
                    else {}
                )
                features.append(
                    (
                        clean_text(props.get("name") or props.get("nama"), 255),
                        self.geometry(item.get("geometry")),
                        _scalar_props(props),
                    )
                )
            color = clean_text(row["warna"])
            self._overlay(
                "user_geo_layers",
                row["id"],
                name=clean_text(row["nama"], 255) or "Lapisan unggahan",
                kind=aset_enums.OverlayKind.OTHER,
                features=features,
                in_command=True,
                active=to_bool(row["is_active"]),
                color=color if re.fullmatch(r"#[0-9A-Fa-f]{6}", color) else "",
                note=(
                    f"Diunggah oleh {clean_text(row['diunggah_oleh'])}"
                    if meaningful(row["diunggah_oleh"])
                    else ""
                ),
            )

    def _lahan_overlay(self):
        rows = self.rows("lahan")
        self.report.add("lahan", "dibaca", len(rows))
        if rows:
            features = []
            for row in rows:
                props = {
                    "korwil": clean_text(row["korwil"]),
                    "luas_ha": clean_text(row["luas_ha"], 32),
                    "jenis_usaha": clean_text(row["jenis_usaha"], 255),
                    "status_lahan": clean_text(row["status_lahan"], 255),
                    "catatan": clean_text(row["catatan"], 255),
                }
                geometry = self.geometry(row["polygon_geojson"]) or to_point(
                    row["lat"], row["lon"]
                )
                features.append(
                    (
                        meaningful(row["nama_pemilik"])[:255],
                        geometry,
                        {k: v for k, v in props.items() if v},
                    )
                )
            self._overlay(
                "lahan",
                "titik-lahan",
                name="Titik lahan warga (sistem lama)",
                kind=aset_enums.OverlayKind.CADASTRE,
                features=features,
                in_command=True,
            )

    def _overlay(
        self,
        table,
        key,
        *,
        name,
        kind,
        features,
        in_command,
        active=True,
        color="",
        note="",
    ):
        valid = [(n, g, p) for n, g, p in features if g is not None]
        if len(valid) < len(features):
            self.report.skip(table, "geometri tidak sah", len(features) - len(valid))
        if not valid:
            return
        values = {
            "name": name[:255],
            "kind": kind,
            "color": color,
            "source": OVERLAY_SOURCE,
            "is_active": active,
            "show_in_command": in_command,
            "note": note,
        }
        overlay, new = self.save(table, f"lapisan:{key}", MapOverlay, values)
        if overlay is None:
            return
        if not new and not self.update:
            return
        if not new:
            overlay.features.all().delete()
        MapOverlayFeature.objects.bulk_create(
            [
                MapOverlayFeature(overlay=overlay, name=n, geometry=g, properties=p)
                for n, g, p in valid
            ],
            batch_size=500,
        )
        self.report.add(table, "objek peta", len(valid))

    # ------------------------------------------------------------------
    # Sandi awal & tabel yang tidak dipindah
    # ------------------------------------------------------------------

    def _passwords(self):
        if not self.password_file:
            return
        for user in self.users.values():
            if user.has_usable_password() or not user.is_active:
                continue
            password = generate_password()
            password_validation.validate_password(password, user)
            user.set_password(password)
            user.save(update_fields=["password"])
            self.report.passwords.append((user.username, user.first_name, password))

    def _write_passwords(self):
        path = self.password_file
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["nama_pengguna", "nama", "sandi_awal"])
            writer.writerows(self.report.passwords)

    def _list_not_imported(self):
        handled = {
            "korwil",
            "personel",
            "warga",
            "komsos_history",
            "komsos_perubahan_dukungan_raw",
            "komsos_perubahan_luas",
            "kegiatan",
            "tasks",
            "task_assignees",
            "task_giver_points",
            "laporan_harian",
            "land_polygons",
            "soil_test",
            "patrol_sessions",
            "patrol_observations",
            "gps_tracking",
            "rtrw_zones",
            "rempang_geo_layers",
            "user_geo_layers",
            "lahan",
            "status_history",
        }
        for name in self.dump.table_names():
            schema, table = name.split(".", 1)
            if schema != "public":
                continue
            if table in handled:
                continue
            count = len(self.rows(name))
            if not count:
                continue
            if table in NOT_IMPORTED:
                reason = NOT_IMPORTED[table]
            elif LEGACY_BACKUP.search(table):
                reason = "salinan cadangan lama di sistem lama (bukan data aktif)"
            else:
                reason = "belum ada padanannya di SimLahan"
            self.report.not_imported.append((table, count, reason))
        files = len(self.rows("storage.objects"))
        if files:
            self.report.not_imported.append(
                (
                    "storage.objects",
                    files,
                    "berkas lampiran tersimpan di luar cadangan basis data",
                )
            )
        removed = sum(
            1
            for r in self.rows("status_history")
            if r["field_changed"] == "(baris dihapus)"
        )
        if removed:
            self.report.not_imported.append(
                ("status_history", removed, "jejak baris yang dihapus di sistem lama")
            )


def generate_password() -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        password = "".join(secrets.choice(alphabet) for _i in range(14))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
        ):
            return password
