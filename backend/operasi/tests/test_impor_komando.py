"""Impor data sistem pusat komando lama (``impor_komando``)."""

import io
import json
import os
import stat
import struct
import zlib
from decimal import Decimal

import pytest
from django.contrib.gis.geos import Polygon
from django.core.management import CommandError, call_command

from asetlahan.models import MapOverlay, Task
from operasi import enums
from operasi.legacy_import import (
    clean_text,
    parse_area_m2,
    parse_pg_array,
    parse_years,
)
from operasi.models import (
    Activity,
    ActivityPhoto,
    GeotechPoint,
    ImportedRecord,
    Korwil,
    LandAreaChange,
    LandPlot,
    OfficerProfile,
    Resident,
    StanceChange,
    TaskPoint,
)
from operasi.pgdump import Dump, DumpError
from users.models import User
from utils.group_permissions import UserGroup

# Nama instansi yang dilarang tampil di SimLahan dirakit saat tes berjalan agar
# kode sumber sendiri tetap bersih (lihat asetlahan/tests/test_branding.py).
AGENCY = " ".join(("BP", "Batam"))
AGENCY_DOT = ".".join(("BP", "Batam"))
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 60
JPEG_URL = "data:image/jpeg;base64," + __import__("base64").b64encode(JPEG).decode()
BOX_A = [
    [[104.10, 0.80], [104.20, 0.80], [104.20, 0.90], [104.10, 0.90], [104.10, 0.80]]
]
LEADER = "a2000000-0000-0000-0000-000000000001"
COORD = "c0000000-0000-0000-0000-000000000001"
FIELD = "f0000000-0000-0000-0000-000000000001"
TESTER = "70000000-0000-0000-0000-000000000001"
W1 = "11111111-0000-0000-0000-000000000001"
W2 = "11111111-0000-0000-0000-000000000002"
OLD_W = "99999999-0000-0000-0000-000000000009"
TASK = "7a500000-0000-0000-0000-000000000001"
KGT = "4e600000-0000-0000-0000-000000000001"
KGT_TEST = "4e600000-0000-0000-0000-000000000002"


def _copy(table, columns, rows):
    def value(v):
        if v is None:
            return r"\N"
        text = str(v)
        return (
            text.replace("\\", "\\\\")
            .replace("\t", "\\t")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )

    lines = [f"COPY public.{table} ({', '.join(columns)}) FROM stdin;"]
    lines += ["\t".join(value(row.get(c)) for c in columns) for row in rows]
    lines.append("\\.")
    return "\n".join(lines) + "\n\n"


def sample_tables():
    polygon = Polygon(*[tuple(map(tuple, ring)) for ring in BOX_A], srid=4326)
    return {
        "korwil": [
            {
                "id": "A",
                "name": "Korwil A",
                "area_name": "Sembulang",
                "project": "PLTS",
                "boundary_geojson": json.dumps(
                    {"type": "Polygon", "coordinates": BOX_A}
                ),
                "color": "#FF6B6B",
                "created_at": "2026-03-12 09:06:33+00",
            },
            {"id": "NK", "name": "Non-Korwil", "color": "#AEB6BF"},
        ],
        "personel": [
            {
                "id": LEADER,
                "nama": "Steven Pimpinan",
                "nama_login": "steven",
                "role": "Asisten Manager",
                "korwil": "ALL",
                "jabatan": "Asisten Manager",
                "is_active": "t",
                "perusahaan": "SGA",
                "email": "steven@example.org",
            },
            {
                "id": COORD,
                "nama": "M JULDI SETIAWAN",
                "nama_login": "juldi",
                "role": "Ka Korwil",
                "korwil": "A",
                "jabatan": "KA KORWIL",
                "is_active": "t",
                "atasan_id": LEADER,
            },
            {
                "id": FIELD,
                "nama": "Angga Lapangan",
                "nama_login": "angga",
                "role": "PHL",
                "korwil": "A",
                "jabatan": "PHL",
                "is_active": "t",
                "atasan_id": COORD,
            },
            {
                "id": TESTER,
                "nama": "UJI Anggota A",
                "nama_login": "uji_anggota",
                "role": "Anggota",
                "korwil": "A",
                "is_active": "t",
            },
        ],
        "warga": [
            {
                "id": W1,
                "korwil": "A",
                "nama": "Agus",
                "jenis_kelamin": "Laki-laki",
                "pekerjaan": "Nelayan",
                "status_tokoh": "Tomas",
                "umur": "40 Tahun",
                "no_hp": "0812-3456-7890",
                "alamat": "Sembulang",
                "asal_daerah": "Melayu",
                "status_tempatan": "Tempatan",
                "status_dukungan": "Pro",
                "status_relokasi": f"Belum ada kejelasan dari {AGENCY}",
                "luas_lahan": "± 2 ha",
                "status_lahan": "Bangunan Rumah",
                "lat": "0.85",
                "lon": "104.15",
                "catatan": "Mendukung\tprogram",
                "created_at": "2026-09-03 19:17:05+00",
                "tanggal_input": "2024-11-19",
                "lama_menetap": "Sejak lahir",
                "warga_id_asli": "A-W0001",
            },
            {
                "id": W2,
                "korwil": "A",
                "nama": "Siti",
                "jenis_kelamin": "Perempuan",
                "umur": "± 35 Tahun",
                "no_hp": "#ERROR!",
                "status_tempatan": "Pendatang",
                "status_dukungan": "Kontra",
                "status_relokasi": "Sudah Daftar",
                "luas_lahan": "10 x 12 m",
                "created_at": "2026-09-03 19:17:05+00",
                "lama_menetap": "8 Bulan",
                "warga_id_asli": "A-W0002",
            },
        ],
        "komsos_history": [
            {
                "id": "17106",
                "korwil": "A",
                "warga_id": W1,
                "nama_warga": "Agus",
                "tanggal": "2024-11-19",
                "personil_kanonik": "Juldi | Angga",
                "komsos_ke": "1",
                "status_dukungan_asli": "Pro",
                "ringkasan_hasil": "Mendukung program pemerintah",
                "alamat_saat_itu": "Sembulang",
                "sumber_file": "Master.xlsx",
                "created_at": "2026-09-03 19:17:05+00",
            },
            {
                "id": "17107",
                "korwil": "A",
                "warga_id": W2,
                "nama_warga": "Siti",
                "komsos_ke": "2",
                "created_at": "2026-09-03 19:17:05+00",
            },
        ],
        "komsos_perubahan_dukungan_raw": [
            {
                "id": "1",
                "korwil": "A",
                "warga_id": OLD_W,
                "nama_warga": "Siti",
                "tanggal": "2025-06-02",
                "dari_kategori": "Netral",
                "ke_kategori": "Kontra",
                "created_at": "2026-05-30 17:29:49+00",
            },
            {
                "id": "2",
                "korwil": "A",
                "warga_id": OLD_W,
                "nama_warga": "Orang Lain",
                "dari_kategori": "Netral",
                "ke_kategori": "Pro",
            },
        ],
        "komsos_perubahan_luas": [
            {
                "id": "1",
                "korwil": "A",
                "warga_id": OLD_W,
                "nama_warga": "Agus",
                "tanggal": "2025-07-06",
                "luas_sebelum": "1",
                "luas_sesudah": "2",
            }
        ],
        "kegiatan": [
            {
                "id": KGT,
                "korwil": "A",
                "tanggal": "2026-07-21",
                "personil_1": "Angga Lapangan",
                "jenis_kegiatan": "Komsos",
                "nama_warga": "Abdul",
                "narasi": "Mendukung dan mau direlokasi",
                "foto_urls": "{" + f'"{JPEG_URL}","{JPEG_URL}"' + "}",
                "foto": JPEG_URL,
                "lat": "0.85",
                "lon": "104.15",
                "personel_id": FIELD,
                "created_at": "2026-07-21 10:28:25+00",
                "supplementary_data": json.dumps({"nama_pasangan": "Abdullah"}),
                "task_id": TASK,
            },
            {
                "id": KGT_TEST,
                "korwil": "A",
                "tanggal": "2026-07-21",
                "jenis_kegiatan": "Komsos",
                "personel_id": TESTER,
                "supplementary_data": "{}",
            },
        ],
        "tasks": [
            {
                "id": TASK,
                "title": "Lahan PLTS 96 Ha",
                "description": "Penguasaan lahan",
                "assigned_to": FIELD,
                "assigned_by": COORD,
                "korwil": "A",
                "jenis_kegiatan": "Pemetaan",
                "priority": "high",
                "status": "done",
                "due_date": "2026-09-25",
                "completed_at": "2026-09-04 10:46:45+00",
                "completion_notes": "Selesai",
                "attachments": json.dumps(
                    {"lat": 0.85, "lon": 104.15, "foto": JPEG_URL}
                ),
                "created_at": "2026-09-04 09:46:04+00",
                "updated_at": "2026-09-04 09:46:04+00",
                "poin_nilai": "250000",
            }
        ],
        "task_assignees": [
            {
                "id": "x1",
                "task_id": TASK,
                "personel_id": FIELD,
                "poin_earned": "250000",
                "poin_given": "t",
            },
            {
                "id": "x2",
                "task_id": TASK,
                "personel_id": LEADER,
                "poin_earned": "0",
                "poin_given": "f",
            },
        ],
        "task_giver_points": [
            {"id": "g1", "task_id": TASK, "personel_id": COORD, "poin": "10"}
        ],
        "status_history": [
            {
                "id": "s1",
                "entity_type": "task",
                "entity_id": TASK,
                "field_changed": "lifecycle",
                "old_value": "pending",
                "new_value": "started",
                "changed_by_id": FIELD,
                "created_at": "2026-09-04 09:47:00+00",
            },
            {
                "id": "s2",
                "entity_type": "warga",
                "entity_id": "gone",
                "field_changed": "(baris dihapus)",
                "old_value": "Adi",
                "created_at": "2026-09-03 19:17:05+00",
            },
        ],
        "land_polygons": [
            {
                "id": "p1",
                "titik": "IBU NORY 1 HA",
                "lahan": "Nory",
                "luas_ha": "1.1170",
                "korwil": "A",
                "polygon_geojson": json.dumps(
                    [
                        [
                            [104.15, 0.85],
                            [104.151, 0.85],
                            [104.151, 0.851],
                            [104.15, 0.85],
                        ]
                    ]
                ),
                "source": "KMZ-2026-06-02",
                "status_penguasaan": "sudah",
                "tanggal_dikuasai": "2026-06-02",
                "tim_penguasaan": "Diserahkan",
                "nama_pemilik": "Nory",
                "created_at": "2026-06-07 19:28:58+00",
            },
            {"id": "p2", "titik": "Rusak", "polygon_geojson": "bukan json"},
        ],
        "soil_test": [
            {
                "id": "t1",
                "project": "PLTS PT RES",
                "point_id": "TL-BH-1",
                "status": "Completed",
                "lat": "0.85",
                "lon": "104.15",
                "created_at": "2026-03-16 06:24:44+00",
            }
        ],
        "rtrw_zones": [
            {
                "id": "z1",
                "source_file": "rencana_ruang",
                "zone_name": "Zona Perumahan",
                "zone_tier": "Budi Daya",
                "sub_category": "Perumahan",
                "nampul": "Pulau Rempang",
                "geom": polygon.hexewkb.decode(),
                "area_ha": "265.1",
            }
        ],
        "activity_log": [{"id": "l1", "user_name": "x", "action": "login"}],
        "backup_warga_20260903": [{"id": "b1", "nama": "Lama"}],
    }


COLUMNS = {
    "korwil": ["id", "name", "area_name", "project", "boundary_geojson", "color"]
    + ["created_at"],
    "personel": [
        "id",
        "nama",
        "nama_login",
        "role",
        "korwil",
        "email",
        "jabatan",
        "is_active",
        "perusahaan",
        "atasan_id",
    ],
    "warga": [
        "id",
        "korwil",
        "nama",
        "jenis_kelamin",
        "pekerjaan",
        "status_tokoh",
        "umur",
        "no_hp",
        "alamat",
        "asal_daerah",
        "status_tempatan",
        "status_dukungan",
        "status_relokasi",
        "luas_lahan",
        "status_lahan",
        "pemilik_lahan",
        "jenis_tanaman",
        "lat",
        "lon",
        "catatan",
        "created_at",
        "tanggal_input",
        "lama_menetap",
        "warga_id_asli",
    ],
    "komsos_history": [
        "id",
        "korwil",
        "warga_id",
        "nama_warga",
        "tanggal",
        "personil_kanonik",
        "komsos_ke",
        "status_dukungan_asli",
        "luas_ha",
        "status_penggarapan",
        "status_relokasi",
        "alamat_saat_itu",
        "ringkasan_hasil",
        "catatan_prokontra",
        "tindak_lanjut",
        "bulan",
        "sumber_file",
        "created_at",
    ],
    "komsos_perubahan_dukungan_raw": [
        "id",
        "korwil",
        "warga_id",
        "nama_warga",
        "tanggal",
        "dari_kategori",
        "ke_kategori",
        "created_at",
    ],
    "komsos_perubahan_luas": [
        "id",
        "korwil",
        "warga_id",
        "nama_warga",
        "tanggal",
        "luas_sebelum",
        "luas_sesudah",
        "created_at",
    ],
    "kegiatan": [
        "id",
        "korwil",
        "tanggal",
        "personil_1",
        "personil_2",
        "personil_3",
        "personil_4",
        "jenis_kegiatan",
        "status_komsos",
        "nama_warga",
        "narasi",
        "hasil",
        "rekomendasi",
        "lokasi_kegiatan",
        "foto_urls",
        "lat",
        "lon",
        "created_by",
        "created_at",
        "foto",
        "personel_id",
        "task_id",
        "supplementary_data",
    ],
    "tasks": [
        "id",
        "title",
        "description",
        "assigned_to",
        "assigned_by",
        "korwil",
        "jenis_kegiatan",
        "priority",
        "status",
        "due_date",
        "completed_at",
        "completion_notes",
        "attachments",
        "created_at",
        "updated_at",
        "poin_nilai",
    ],
    "task_assignees": ["id", "task_id", "personel_id", "poin_earned", "poin_given"],
    "task_giver_points": ["id", "task_id", "personel_id", "poin", "given_at"],
    "status_history": [
        "id",
        "entity_type",
        "entity_id",
        "field_changed",
        "old_value",
        "new_value",
        "changed_by_id",
        "notes",
        "created_at",
    ],
    "land_polygons": [
        "id",
        "titik",
        "lahan",
        "luas_ha",
        "keterangan",
        "korwil",
        "polygon_geojson",
        "source",
        "created_at",
        "status_penguasaan",
        "tanggal_dikuasai",
        "tim_penguasaan",
        "no_berkas",
        "nama_pemilik",
        "kategori_priority",
    ],
    "soil_test": [
        "id",
        "project",
        "point_id",
        "status",
        "lat",
        "lon",
        "assigned_to",
        "notes",
        "completed_at",
        "created_at",
        "wilayah",
        "kondisi_sosial",
        "akses_medan",
        "catatan_survey",
        "last_operator",
        "jenis_test",
    ],
    "rtrw_zones": [
        "id",
        "source_file",
        "zone_name",
        "zone_tier",
        "sub_category",
        "layer_code",
        "nampul",
        "geom",
        "area_ha",
    ],
    "activity_log": ["id", "user_name", "action"],
    "backup_warga_20260903": ["id", "nama"],
}


def write_sql(path, tables=None):
    tables = tables or sample_tables()
    text = "-- PostgreSQL database dump\n\n" + "".join(
        _copy(name, COLUMNS[name], rows) for name, rows in tables.items()
    )
    path.write_text(text, encoding="utf-8")
    return str(path)


@pytest.fixture
def dump_file(tmp_path):
    return write_sql(tmp_path / "komando.sql")


@pytest.fixture
def importable(seeded, units):
    return units


def run(path, *args):
    out = io.StringIO()
    call_command("impor_komando", path, *args, stdout=out)
    return out.getvalue()


# --------------------------------------------------------------------------
# Pembersih nilai
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2 ha", Decimal("20000.00")),
        ("± 2,8 ha", Decimal("28000.00")),
        ("± 1/2 ha", Decimal("5000.00")),
        ("10 x 12 m", Decimal("120.00")),
        ("50 × 30 m", Decimal("1500.00")),
        ("8 x 10", Decimal("80.00")),
        ('500m"', Decimal("500.00")),
        ("42m2", Decimal("42.00")),
        ("1.250 m", Decimal("1250.00")),
        ("Tidak ada lahan", None),
        ("10 hektar yg di garap 1 hektar", None),
        ("", None),
    ],
)
def test_parse_area_m2(text, expected):
    assert parse_area_m2(text) == expected


def test_parse_years_and_array():
    assert parse_years("40 Tahun") == 40
    assert parse_years("55thn") == 55
    assert parse_years("± 35 Tahun") == 35
    assert parse_years("8 Bulan") == 0
    assert parse_years("Abdullah = ? Santi = 60 tahun") is None
    assert parse_pg_array('{"data:a,b","x\\"y",NULL,plain}') == [
        "data:a,b",
        'x"y',
        "plain",
    ]
    assert parse_pg_array("") == []


def test_clean_text_replaces_authority_name():
    assert clean_text(f"oleh {AGENCY_DOT} terkait") == "oleh pihak berwenang terkait"
    assert clean_text(f"DARI {AGENCY.upper()}") == "DARI pihak berwenang"
    assert clean_text("BPN Batam") == "BPN Batam"


# --------------------------------------------------------------------------
# Pembaca cadangan
# --------------------------------------------------------------------------


def _int(value):
    return bytes([1 if value < 0 else 0]) + struct.pack("<I", abs(value))


def _str(value):
    if value is None:
        return _int(-1)
    data = value.encode()
    return _int(len(data)) + data


def write_custom(path, version, compress):
    """Arsip pg_dump format kustom minimal: satu tabel berisi dua baris."""
    copy = "COPY public.korwil (id, name) FROM stdin;\n"
    payload = "A\tKorwil A\nB\tKorwil \\\\B\\tx\n\\.\n\n".encode()
    head = b"PGDMP" + bytes([1, version, 0, 4, 8, 1])
    head += (
        bytes([1 if compress else 0]) if version >= 15 else _int(-1 if compress else 0)
    )
    head += b"".join(_int(0) for _i in range(7))
    head += _str("postgres") + _str("17.6") + _str("17.11")
    entry = _int(7) + _int(1) + _str("0") + _str("0") + _str("korwil")
    entry += _str("TABLE DATA") + _int(3) + _str("") + _str("") + _str(copy)
    entry += _str("public") + _str("") + _str("")
    if version >= 16:
        entry += _int(0)
    entry += _str("postgres") + _str("false") + _str("1") + _str(None)
    toc = _int(1)
    offset_pos = len(head) + len(toc) + len(entry)
    data = zlib.compress(payload) if compress else payload
    block = b"\x01" + _int(7) + _int(len(data)) + data + _int(0)
    data_at = offset_pos + 9
    offset = b"\x02" + struct.pack("<Q", data_at)
    path.write_bytes(head + toc + entry + offset + block)
    return str(path)


@pytest.mark.parametrize("version,compress", [(16, True), (16, False), (14, True)])
def test_custom_format_reader(tmp_path, version, compress):
    path = write_custom(tmp_path / "x.dump", version, compress)
    with Dump(path) as dump:
        assert dump.table_names() == ["public.korwil"]
        assert dump.rows("public.korwil") == [
            {"id": "A", "name": "Korwil A"},
            {"id": "B", "name": "Korwil \\B\tx"},
        ]


def test_reader_rejects_garbage(tmp_path):
    path = tmp_path / "x.dump"
    path.write_bytes(b"PGDMP" + bytes([9, 9, 0]))
    with pytest.raises(DumpError):
        Dump(str(path))
    other = tmp_path / "x.sql"
    other.write_text("SELECT 1;\n")
    with pytest.raises(DumpError):
        Dump(str(other))


# --------------------------------------------------------------------------
# Impor
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_dry_run_changes_nothing(importable, dump_file, private_storage):
    output = run(dump_file, "--coba")
    assert "UJI COBA" in output
    assert "warga: dibaca 2, dibuat 2" in output
    assert not Resident.objects.exists()
    assert not ImportedRecord.objects.exists()
    assert not User.objects.filter(username="juldi").exists()
    stored = [f for _root, _dirs, files in os.walk(private_storage) for f in files]
    assert stored == ["komando.sql"]


@pytest.mark.django_db
def test_full_import_and_rerun(importable, dump_file, tmp_path):
    secrets_file = tmp_path / "sandi.csv"
    output = run(dump_file, "--sandi-awal", str(secrets_file))
    assert "Impor selesai." in output

    korwil = Korwil.objects.get(code="A")
    assert korwil.name == "Sembulang"
    assert korwil.geometry is not None
    assert not Korwil.objects.filter(code="NK").exists()

    leader = User.objects.get(username="steven")
    coordinator = User.objects.get(username="juldi")
    officer = User.objects.get(username="angga")
    assert not User.objects.filter(username__startswith="uji").exists()
    assert korwil.coordinator == coordinator
    assert officer.groups.filter(pk=UserGroup.PETUGAS_LAPANGAN).exists()
    assert leader.groups.filter(pk=UserGroup.KOORDINATOR_WILAYAH).exists()
    assert leader in korwil.members.all() and officer in korwil.members.all()
    assert OfficerProfile.objects.get(user=officer).supervisor == coordinator
    assert OfficerProfile.objects.get(user=coordinator).supervisor == leader
    assert leader.email == "steven@example.org"

    agus = Resident.objects.get(head_name="Agus")
    assert agus.korwil == korwil
    assert agus.stance == enums.Stance.SUPPORT
    assert agus.gender == enums.Gender.MALE
    assert agus.age == 40 and agus.years_living == 40
    assert agus.phone == "081234567890"
    assert agus.land_area_m2 == Decimal("20000.00")
    assert agus.residency_status == enums.ResidencyStatus.NATIVE
    assert "A-W0001" in agus.note and "Tomas" in agus.note
    assert "pihak berwenang" in agus.note and "Batam" not in agus.note
    assert agus.last_visited_on.isoformat() == "2024-11-19"
    assert agus.created_at.date().isoformat() == "2024-11-19"
    siti = Resident.objects.get(head_name="Siti")
    assert siti.phone == ""
    assert siti.relocation_choice == enums.RelocationChoice.RELOCATION
    assert siti.land_area_m2 == Decimal("120.00")

    komsos = Activity.objects.get(residents=agus)
    assert komsos.activity_type == enums.ActivityType.KOMSOS
    assert komsos.reported_by == coordinator  # "Juldi" cocok satu petugas
    assert komsos.verified
    assert agus.registered_activity == komsos
    assert Activity.objects.get(residents=siti).reported_by is None

    # Riwayat lama dicocokkan lewat nama + Korwil; nama tanpa pasangan dilewati.
    change = StanceChange.objects.get()
    assert (change.resident, change.old_stance, change.new_stance) == (
        siti,
        enums.Stance.NEUTRAL,
        enums.Stance.OPPOSE,
    )
    assert change.changed_at.date().isoformat() == "2025-06-02"
    area = LandAreaChange.objects.get()
    assert (area.old_area_m2, area.new_area_m2) == (Decimal("10000"), Decimal("20000"))

    report = Activity.objects.get(title__startswith="Komsos – Abdul")
    assert report.reported_by == officer
    assert (
        ActivityPhoto.objects.filter(activity=report).count() == 1
    )  # duplikat dibuang
    assert "Abdullah" in report.outcome
    assert report.effort_points > 0
    assert Activity.objects.count() == 3  # 2 komsos + 1 kegiatan (uji dilewati)

    task = Task.objects.get()
    assert report.task == task
    assert task.point_value == 250_000  # ratusan ribu poin tidak dipangkas
    assert task.assignee == officer and task.created_by == coordinator
    assert list(task.contributors.all()) == [leader]
    points = {(p.user, p.role, p.points) for p in TaskPoint.objects.all()}
    assert points == {
        (officer, enums.TaskPointRole.ASSIGNEE, 250_000),
        (coordinator, enums.TaskPointRole.GIVER, 10),
    }
    kinds = list(
        task.komando_events.order_by("created_at").values_list("kind", flat=True)
    )
    assert kinds == [
        enums.TaskEventKind.CREATED,
        enums.TaskEventKind.STARTED,
        enums.TaskEventKind.SUBMITTED,
    ]
    assert task.komando_events.get(kind=enums.TaskEventKind.SUBMITTED).photo

    plot = LandPlot.objects.get()
    assert plot.control_status == enums.ControlStatus.CONTROLLED
    assert plot.official_area_ha == Decimal("1.1170")
    assert GeotechPoint.objects.get().work_status == enums.GeotechWorkStatus.DONE
    overlay = MapOverlay.objects.get()
    assert overlay.show_in_command and overlay.features.count() == 1

    assert "land_polygons: dibaca 2, dibuat 1, dilewati 1" in output
    assert "activity_log (1 baris)" in output
    assert "backup_warga_20260903 (1 baris)" in output
    assert "dipangkas" not in output

    assert stat.S_IMODE(os.stat(secrets_file).st_mode) == 0o600
    rows = secrets_file.read_text().splitlines()
    assert rows[0] == "nama_pengguna,nama,sandi_awal" and len(rows) == 4
    username, _name, password = rows[2].split(",")
    assert User.objects.get(username=username).check_password(password)

    counts = {
        model: model.objects.count()
        for model in (User, Resident, Activity, StanceChange, Task, LandPlot)
    }
    links = ImportedRecord.objects.count()
    again = run(dump_file)
    assert "warga: dibaca 2, sudah ada 2" in again
    assert counts == {model: model.objects.count() for model in counts}
    assert ImportedRecord.objects.count() == links


@pytest.mark.django_db
def test_task_points_above_limit_are_capped(importable, tmp_path):
    tables = sample_tables()
    tables["tasks"][0]["poin_nilai"] = str(enums.MAX_TASK_POINTS + 1)
    out = io.StringIO()
    call_command("impor_komando", write_sql(tmp_path / "besar.sql", tables), stdout=out)
    assert Task.objects.get().point_value == enums.MAX_TASK_POINTS
    assert "nilai poin 1000001 dipangkas jadi 1000000" in out.getvalue()


def test_update_and_deleted_records(importable, dump_file):
    run(dump_file)
    agus = Resident.objects.get(head_name="Agus")
    agus.occupation = "Diubah petugas"
    agus.save()
    Resident.objects.get(head_name="Siti").delete()

    output = run(dump_file)
    assert "sudah dihapus di SimLahan" in output
    assert not Resident.objects.filter(head_name="Siti").exists()
    assert Resident.objects.get(head_name="Agus").occupation == "Diubah petugas"

    run(dump_file, "--perbarui")
    assert Resident.objects.get(head_name="Agus").occupation == "Nelayan"


@pytest.mark.django_db
def test_existing_korwil_and_username_are_kept(importable, dump_file):
    korwil = Korwil.objects.create(code="A", name="Wilayah Manual")
    User.objects.create_user(username="angga", email="lain@example.org")
    output = run(dump_file)
    korwil.refresh_from_db()
    assert korwil.name == "Wilayah Manual"
    assert Resident.objects.filter(korwil=korwil).count() == 2
    assert User.objects.filter(username="komando.angga").exists()
    assert "memakai 'komando.angga'" in output


@pytest.mark.django_db
def test_include_test_accounts(importable, dump_file):
    run(dump_file, "--sertakan-uji")
    assert User.objects.filter(username="uji_anggota").exists()
    assert Activity.objects.count() == 4


@pytest.mark.django_db
def test_refuses_sample_korwil(importable, dump_file):
    Korwil.objects.create(code="A", name="Contoh", note="[contoh] fiktif")
    with pytest.raises(CommandError, match="hapus_data_contoh"):
        run(dump_file)
    assert not Resident.objects.exists()


@pytest.mark.django_db
def test_requires_groups(db, dump_file):
    with pytest.raises(CommandError, match="simlahan_bootstrap"):
        run(dump_file)


def test_password_file_must_not_exist(tmp_path, dump_file):
    existing = tmp_path / "ada.csv"
    existing.write_text("x")
    with pytest.raises(CommandError, match="sudah ada"):
        run(dump_file, "--sandi-awal", str(existing))
    with pytest.raises(CommandError, match="tidak ditemukan"):
        run(str(tmp_path / "tidak-ada.dump"))
