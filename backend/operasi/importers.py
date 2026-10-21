"""Impor batas Korwil (berkas spasial) dan data warga (CSV atau titik spasial).

Batas Korwil: GeoJSON, KML/KMZ, GeoPackage, atau Shapefile (ZIP) berpoligon dengan
atribut ``kode`` (wajib) dan ``nama``/``warna`` (opsional). Korwil dengan kode
yang sama diperbarui.

Warga: CSV (pemisah koma atau titik koma, baris pertama judul kolom) atau
berkas spasial bertitik. Kolom yang dikenali: nama, nik, kk, jiwa, telepon,
kampung, alamat, korwil (kode), lat, lng, sikap, status_lahan, rtrw,
pilihan, catatan. Warga dengan NIK yang sudah terdata di wilayah kerja pengimpor
diperbarui (perlu hak ubah warga; catatan ditambahkan, tidak ditimpa). Baris
dengan NIK yang terdata di luar wilayah kerjanya dilewati tanpa menyebut
keberadaannya.
"""

import csv
import io
import os

from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from asetlahan.importers import AssetImportError
from asetlahan.importers import _polygon as polygon_of
from asetlahan.importers import _prop, _read_features
from operasi import enums, geo
from operasi.models import Korwil, Resident
from pengadaan.crypto import fingerprint

MAX_ROWS = 20000
NIK_REJECTED = "NIK tidak dapat dipakai; baris dilewati."
NO_CHANGE_PERMISSION = (
    "warga dengan NIK ini sudah terdata dan Anda tidak berhak mengubahnya; "
    "baris dilewati."
)
OUT_OF_AREA = "lokasi berada di luar wilayah kerja Anda; baris dilewati."


class RowSkipped(Exception):
    """Baris dilewati (bukan galat berkas): impor baris lain tetap berjalan."""


NAME = ("nama", "nama_kk", "kepala_keluarga", "nama_kepala_keluarga", "name")
NIK = ("nik", "no_nik")
KK = ("kk", "no_kk", "nomor_kk")
MEMBERS = ("jiwa", "jumlah_jiwa", "anggota", "jumlah_anggota")
PHONE = ("telepon", "hp", "wa", "whatsapp", "phone")
VILLAGE = ("kampung", "desa", "kelurahan", "village")
ADDRESS = ("alamat", "address")
KORWIL = ("korwil", "kode_korwil")
LAT = ("lat", "latitude", "lintang", "y")
LNG = ("lng", "lon", "long", "longitude", "bujur", "x")
STANCE = ("sikap", "stance", "dukungan")
LAND = ("status_lahan", "lahan")
RTRW = ("rtrw", "kesesuaian_rtrw")
CHOICE = ("pilihan", "pilihan_penyelesaian")
NOTE = ("catatan", "keterangan", "note")

STANCE_WORDS = {
    "pro": enums.Stance.SUPPORT,
    "mendukung": enums.Stance.SUPPORT,
    "setuju": enums.Stance.SUPPORT,
    "dukung": enums.Stance.SUPPORT,
    "netral": enums.Stance.NEUTRAL,
    "ragu": enums.Stance.NEUTRAL,
    "ragu-ragu": enums.Stance.NEUTRAL,
    "kontra": enums.Stance.OPPOSE,
    "menolak": enums.Stance.OPPOSE,
    "tolak": enums.Stance.OPPOSE,
    "belum": enums.Stance.UNKNOWN,
}
LAND_WORDS = {
    "sudah": enums.LandStatus.RELEASED,
    "bebas": enums.LandStatus.RELEASED,
    "dibebaskan": enums.LandStatus.RELEASED,
    "belum": enums.LandStatus.PENDING,
}
RTRW_WORDS = {
    "sesuai": enums.RtrwStatus.CONFORM,
    "ya": enums.RtrwStatus.CONFORM,
    "tidak": enums.RtrwStatus.NONCONFORM,
    "tidak sesuai": enums.RtrwStatus.NONCONFORM,
    "belum": enums.RtrwStatus.UNASSESSED,
}
CHOICE_WORDS = {
    "relokasi": enums.RelocationChoice.RELOCATION,
    "hunian": enums.RelocationChoice.RELOCATION,
    "uang": enums.RelocationChoice.COMPENSATION,
    "kompensasi": enums.RelocationChoice.COMPENSATION,
    "ganti rugi": enums.RelocationChoice.COMPENSATION,
    "ganti kerugian": enums.RelocationChoice.COMPENSATION,
    "geser": enums.RelocationChoice.SHIFT,
    "lainnya": enums.RelocationChoice.OTHER,
    "belum": enums.RelocationChoice.UNDECIDED,
}


def _word(value: str, table: dict, default):
    value = (value or "").strip().lower()
    if not value:
        return default
    if value in table:
        return table[value]
    for choice in table.values():
        if value == str(choice):
            return choice
    raise AssetImportError(f"Nilai '{value}' tidak dikenal.")


# --------------------------------------------------------------------------
# Korwil
# --------------------------------------------------------------------------


def import_korwils(data: bytes, filename: str) -> tuple[int, int]:
    features = _read_features(data, filename)
    if not features:
        raise AssetImportError("Tidak ada fitur di dalam berkas.")
    rows = []
    for index, (props, geom) in enumerate(features, start=1):
        code = _prop(props, ("kode", "code", "korwil")).upper()[:8]
        if not code:
            raise AssetImportError(f"Fitur ke-{index} tidak memiliki atribut 'kode'.")
        name = _prop(props, ("nama", "name", "wilayah"))[:128] or f"Korwil {code}"
        color = _prop(props, ("warna", "color"))
        rows.append((code, name, color, polygon_of(index, geom)))
    created = updated = 0
    with transaction.atomic():
        for code, name, color, geometry in rows:
            korwil = Korwil.objects.filter(code__iexact=code).first()
            if korwil is None:
                korwil = Korwil(code=code)
                created += 1
            else:
                updated += 1
            korwil.name = name
            korwil.geometry = geometry
            if len(color) == 7 and color.startswith("#"):
                korwil.color = color
            korwil.save()
    return created, updated


# --------------------------------------------------------------------------
# Warga
# --------------------------------------------------------------------------


def _csv_rows(data: bytes) -> list[tuple[dict, Point | None]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = []
    for props in reader:
        props = {
            str(k).strip().lower(): (v or "").strip() for k, v in props.items() if k
        }
        lat, lng = _prop(props, LAT), _prop(props, LNG)
        point = None
        if lat and lng:
            try:
                lat_f, lng_f = float(lat.replace(",", ".")), float(
                    lng.replace(",", ".")
                )
            except ValueError:
                raise AssetImportError(f"Koordinat tidak sah: {lat}, {lng}")
            if not (-90 <= lat_f <= 90 and -180 <= lng_f <= 180):
                raise AssetImportError(f"Koordinat di luar jangkauan: {lat}, {lng}")
            point = Point(lng_f, lat_f, srid=4326)
        rows.append((props, point))
    return rows


def _spatial_rows(data: bytes, filename: str) -> list[tuple[dict, Point | None]]:
    rows = []
    for index, (props, geom) in enumerate(_read_features(data, filename), start=1):
        if geom.srid != 4326:
            geom = geom.transform(4326, clone=True)
        point = geom if geom.geom_type == "Point" else geom.point_on_surface
        point.srid = 4326
        rows.append(({str(k).lower(): v for k, v in props.items()}, point))
    return rows


def _resident_for_row(props: dict, user, residents):
    """Warga yang diperbarui (NIK sama di wilayah kerja) atau warga baru.

    Mengembalikan (warga, baru). ``residents`` adalah warga yang terlihat oleh
    pengimpor; NIK yang hanya terdata di luar itu ditolak dengan pesan umum.
    """
    name = _prop(props, NAME)[:255]
    if not name:
        raise AssetImportError("kolom 'nama' kosong.")
    nik = "".join(ch for ch in _prop(props, NIK) if ch.isdigit())
    if nik and len(nik) != 16:
        raise AssetImportError(f"NIK '{nik}' harus 16 digit.")
    resident = None
    if nik:
        key = fingerprint(nik)
        resident = residents.filter(nik_fingerprint=key).first()
        if resident is None and Resident.objects.filter(nik_fingerprint=key).exists():
            raise RowSkipped(NIK_REJECTED)
        if (
            resident is not None
            and user is not None
            and not user.has_perm("operasi.change_resident")
        ):
            raise RowSkipped(NO_CHANGE_PERMISSION)
    is_new = resident is None
    if is_new:
        resident = Resident(created_by=user)
    resident.head_name = name
    if nik:
        resident.nik = nik
    return resident, is_new


def _append_note(resident, text: str, user) -> None:
    """Catatan impor ditambahkan di bawah catatan lama, tidak menimpanya."""
    if not resident.pk or not resident.note:
        resident.note = text
        return
    who = ""
    if user is not None:
        who = " " + (user.get_full_name() or user.get_username())
    stamp = timezone.localtime().strftime("%d-%m-%Y %H:%M")
    resident.note = f"{resident.note}\n[{stamp} impor{who}] {text}"


def _apply_korwil(resident, props: dict, korwils: dict, korwil) -> None:
    code = _prop(props, KORWIL).upper().removeprefix("KORWIL ").strip()
    if code:
        if code not in korwils:
            raise AssetImportError(f"Korwil '{code}' belum terdaftar.")
        resident.korwil = korwils[code]
    elif korwil is not None and resident.korwil_id is None:
        resident.korwil = korwil


def _apply_row(resident, props: dict, point, korwils: dict, korwil, user=None) -> None:
    for field, names, size in (
        ("family_card_number", KK, 32),
        ("phone", PHONE, 32),
        ("village", VILLAGE, 128),
        ("address", ADDRESS, 255),
    ):
        value = _prop(props, names)
        if value:
            setattr(resident, field, value[:size])
    note = _prop(props, NOTE)[:5000]
    if note:
        _append_note(resident, note, user)
    members = _prop(props, MEMBERS)
    if members:
        if not members.isdigit():
            raise AssetImportError(f"jumlah jiwa '{members}' bukan angka.")
        resident.member_count = int(members)
    _apply_korwil(resident, props, korwils, korwil)
    if point is not None:
        resident.location = point
    for field, names, words in (
        ("stance", STANCE, STANCE_WORDS),
        ("land_status", LAND, LAND_WORDS),
        ("rtrw_status", RTRW, RTRW_WORDS),
        ("relocation_choice", CHOICE, CHOICE_WORDS),
    ):
        setattr(
            resident, field, _word(_prop(props, names), words, getattr(resident, field))
        )


def _import_row(props, point, user, residents, korwils, korwil) -> bool:
    """Simpan satu baris; mengembalikan True bila warga baru."""
    resident, is_new = _resident_for_row(props, user, residents)
    _apply_row(resident, props, point, korwils, korwil, user)
    if user is not None:
        try:
            geo.assign_korwil(resident, user)
        except ValidationError:
            raise RowSkipped(OUT_OF_AREA)
    resident._changed_by = user
    resident.save()
    return is_new


def import_residents(data: bytes, filename: str, *, user=None, korwil=None) -> dict:
    extension = os.path.splitext(filename.lower())[1]
    rows = (
        _csv_rows(data)
        if extension in (".csv", ".txt")
        else _spatial_rows(data, filename)
    )
    if not rows:
        raise AssetImportError("Tidak ada baris data di dalam berkas.")
    if len(rows) > MAX_ROWS:
        raise AssetImportError(f"Maksimal {MAX_ROWS} baris per impor; pecah berkasnya.")
    if user is not None:
        korwils = {k.code.upper(): k for k in geo.visible_korwils(user)}
        residents = geo.scoped(Resident.objects.all(), user)
    else:
        korwils = {k.code.upper(): k for k in Korwil.objects.all()}
        residents = Resident.objects.all()
    created = updated = 0
    errors = []
    with transaction.atomic():
        for line, (props, point) in enumerate(rows, start=2):
            try:
                is_new = _import_row(props, point, user, residents, korwils, korwil)
            except AssetImportError as error:
                raise AssetImportError(f"Baris {line}: {error}")
            except RowSkipped as skipped:
                errors.append(f"Baris {line}: {skipped}")
                continue
            if is_new:
                created += 1
            else:
                updated += 1
    return {
        "created": created,
        "updated": updated,
        "skipped": len(errors),
        "errors": errors,
    }
