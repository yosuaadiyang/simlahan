"""Data contoh pusat komando di Pulau Rempang (fiktif, untuk uji coba).

python manage.py operasi_contoh_rempang          # buat (dilewati bila sudah ada)
python manage.py operasi_contoh_rempang --hapus  # hapus seluruh data contoh

Membuat 11 Korwil (A–K) dengan batas wilayah, warga terdata (sikap, status
lahan, kesesuaian RTRW, pilihan penyelesaian), laporan kegiatan, uji tanah,
dan tugas wilayah. Semua nama fiktif; tidak ada NIK.
"""

import datetime
import random

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from asetlahan import enums as aset_enums
from asetlahan.models import Task
from operasi import enums
from operasi.models import Activity, Korwil, Resident, SoilTest, StanceChange

MARK = "[contoh]"

# (kode, nama wilayah, kampung, warna)
KORWILS = [
    ("A", "Pasir Panjang", "Pasir Panjang", "#10b981"),
    ("B", "Sembulang", "Sembulang, Tanjung Banun", "#3b82f6"),
    ("C", "Rempang Cate", "Rempang Cate", "#f59e0b"),
    ("D", "Monggak", "Monggak", "#ef4444"),
    ("E", "Sungai Raya", "Sungai Raya", "#8b5cf6"),
    ("F", "Pantai Melayu", "Pantai Melayu", "#ec4899"),
    ("G", "Blongkeng", "Blongkeng", "#14b8a6"),
    ("H", "Pasir Merah", "Pasir Merah", "#eab308"),
    ("I", "Tanjung Kertang", "Tanjung Kertang", "#f97316"),
    ("J", "Sijantung", "Sijantung", "#22c55e"),
    ("K", "Karas", "Karas", "#06b6d4"),
]

# Kisi 4 × 3 sel di atas Pulau Rempang (sel terakhir dilewati).
WEST, NORTH = 104.105, 0.915
CELL_W, CELL_H = 0.045, 0.04

FIRST_NAMES = [
    "Ahmad",
    "Rahman",
    "Yusuf",
    "Hasan",
    "Ismail",
    "Syamsul",
    "Zulkifli",
    "Jamal",
    "Rusli",
    "Abdul",
    "Muhammad",
    "Salim",
    "Kamal",
    "Hamid",
    "Nurdin",
    "Saleh",
]
LAST_NAMES = [
    "bin Daud",
    "bin Ali",
    "bin Umar",
    "bin Said",
    "bin Yahya",
    "bin Harun",
    "bin Usman",
    "bin Musa",
    "bin Jalil",
    "bin Taher",
]

STANCE_WEIGHTS = [
    (enums.Stance.SUPPORT, 45),
    (enums.Stance.NEUTRAL, 20),
    (enums.Stance.OPPOSE, 15),
    (enums.Stance.UNKNOWN, 20),
]

ACTIVITIES = [
    (enums.ActivityType.SOCIALIZATION, "Sosialisasi program di balai kampung"),
    (enums.ActivityType.CENSUS, "Pendataan kepala keluarga"),
    (enums.ActivityType.VISIT, "Kunjungan rumah warga"),
    (enums.ActivityType.MEASUREMENT, "Pengukuran batas bidang bersama warga"),
    (enums.ActivityType.MEETING, "Rapat koordinasi tokoh masyarakat"),
]


def _cell(index: int) -> MultiPolygon:
    row, col = divmod(index, 3)
    west = WEST + col * CELL_W
    north = NORTH - row * CELL_H
    ring = (
        (west, north),
        (west + CELL_W, north),
        (west + CELL_W, north - CELL_H),
        (west, north - CELL_H),
        (west, north),
    )
    return MultiPolygon(Polygon(ring), srid=4326)


def _random_point(rng: random.Random, geometry: MultiPolygon) -> Point:
    xmin, ymin, xmax, ymax = geometry.extent
    margin_x, margin_y = (xmax - xmin) * 0.1, (ymax - ymin) * 0.1
    return Point(
        rng.uniform(xmin + margin_x, xmax - margin_x),
        rng.uniform(ymin + margin_y, ymax - margin_y),
        srid=4326,
    )


def _pick(rng: random.Random, weighted):
    values, weights = zip(*weighted)
    return rng.choices(values, weights=weights, k=1)[0]


class Command(BaseCommand):
    help = "Buat atau hapus data contoh pusat komando di Pulau Rempang"

    def add_arguments(self, parser):
        parser.add_argument("--hapus", action="store_true", help="Hapus data contoh")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["hapus"]:
            self._delete()
            self.stdout.write(self.style.SUCCESS("Data contoh pusat komando dihapus."))
            return
        codes = [row[0] for row in KORWILS]
        if Korwil.objects.filter(code__in=codes).exists():
            self.stdout.write(
                "Korwil A–K sudah ada; data contoh dilewati (jalankan --hapus dahulu "
                "untuk membuat ulang data contoh)."
            )
            return
        self._create()
        self.stdout.write(self.style.SUCCESS("Data contoh pusat komando dibuat."))

    def _delete(self):
        korwils = Korwil.objects.filter(note__startswith=MARK)
        Task.objects.filter(title__startswith=MARK).delete()
        Activity.objects.filter(description__startswith=MARK).delete()
        SoilTest.objects.filter(note__startswith=MARK).delete()
        residents = Resident.objects.filter(note__startswith=MARK)
        StanceChange.objects.filter(resident__in=residents).delete()
        residents.delete()
        korwils.delete()

    def _create(self):
        rng = random.Random(20231001)
        user = get_user_model().objects.filter(is_superuser=True).order_by("pk").first()
        now = timezone.now()
        for index, (code, name, villages, color) in enumerate(KORWILS):
            korwil = Korwil.objects.create(
                code=code,
                name=name,
                color=color,
                geometry=_cell(index),
                villages=villages,
                target_households=40,
                note=f"{MARK} Wilayah contoh fiktif.",
            )
            residents = []
            for number in range(rng.randint(8, 14)):
                land = (
                    enums.LandStatus.RELEASED
                    if rng.random() < 0.35
                    else enums.LandStatus.PENDING
                )
                rtrw = _pick(
                    rng,
                    [
                        (enums.RtrwStatus.CONFORM, 55),
                        (enums.RtrwStatus.NONCONFORM, 20),
                        (enums.RtrwStatus.UNASSESSED, 25),
                    ],
                )
                choice = (
                    _pick(
                        rng,
                        [
                            (enums.RelocationChoice.RELOCATION, 50),
                            (enums.RelocationChoice.COMPENSATION, 30),
                            (enums.RelocationChoice.SHIFT, 20),
                        ],
                    )
                    if land == enums.LandStatus.RELEASED
                    else enums.RelocationChoice.UNDECIDED
                )
                residents.append(
                    Resident.objects.create(
                        korwil=korwil,
                        head_name=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                        member_count=rng.randint(2, 7),
                        village=villages.split(",")[0],
                        address=f"RT 0{number % 4 + 1} / RW 0{number % 2 + 1}",
                        location=_random_point(rng, korwil.geometry),
                        stance=_pick(rng, STANCE_WEIGHTS),
                        land_status=land,
                        rtrw_status=rtrw,
                        relocation_choice=choice,
                        created_by=user,
                        note=f"{MARK} Data warga fiktif.",
                    )
                )
            for day, (kind, title) in zip(
                rng.sample(range(1, 21), 3), rng.sample(ACTIVITIES, 3)
            ):
                activity = Activity.objects.create(
                    korwil=korwil,
                    activity_type=kind,
                    title=f"{title} – Korwil {code}",
                    description=f"{MARK} Laporan contoh.",
                    started_at=now
                    - datetime.timedelta(days=day, hours=rng.randint(0, 6)),
                    duration_minutes=rng.choice([60, 90, 120]),
                    location=_random_point(rng, korwil.geometry),
                    participants_count=rng.randint(3, 40),
                    outcome="Warga menerima penjelasan; tindak lanjut pada kunjungan berikutnya.",
                    reported_by=user,
                    verified=rng.random() < 0.6,
                    verified_by=user,
                )
                activity.residents.set(rng.sample(residents, min(3, len(residents))))
                activity.touch_residents()
            for _test in range(rng.randint(1, 2)):
                suitability = _pick(
                    rng,
                    [
                        (enums.SoilSuitability.SUITABLE, 50),
                        (enums.SoilSuitability.CONDITIONAL, 30),
                        (enums.SoilSuitability.UNSUITABLE, 20),
                    ],
                )
                SoilTest.objects.create(
                    korwil=korwil,
                    location=_random_point(rng, korwil.geometry),
                    sampled_at=now - datetime.timedelta(days=rng.randint(1, 30)),
                    sampled_by=user,
                    depth_cm=rng.choice([30, 50, 100]),
                    texture=rng.choice(enums.SoilTexture.values),
                    color=rng.choice(
                        ["Coklat kemerahan", "Kuning", "Abu-abu", "Coklat tua"]
                    ),
                    ph=round(rng.uniform(4.5, 7.2), 2),
                    moisture_pct=round(rng.uniform(10, 40), 2),
                    organic_c_pct=round(rng.uniform(0.5, 3.5), 2),
                    bearing_capacity_kpa=round(rng.uniform(80, 250), 2),
                    cbr_pct=round(rng.uniform(2, 15), 2),
                    suitability=suitability,
                    lab_name="Laboratorium contoh",
                    note=f"{MARK} Hasil uji fiktif.",
                )
            Task.objects.create(
                title=f"{MARK} Lengkapi pendataan warga Korwil {code}",
                description="Pastikan seluruh KK di wilayah terdata beserta sikap dan lokasi rumah.",
                priority=aset_enums.Priority.NORMAL,
                due_date=timezone.localdate()
                + datetime.timedelta(days=rng.randint(3, 21)),
                korwil=korwil,
                created_by=user,
            )
