"""Data contoh pusat komando di Pulau Rempang (fiktif, untuk uji coba).

python manage.py operasi_contoh_rempang          # buat (dilewati bila sudah ada)
python manage.py operasi_contoh_rempang --hapus  # hapus seluruh data contoh

Membuat 11 Korwil (A–K) dengan batas wilayah, warga terdata (sikap, status
lahan, kesesuaian RTRW, pilihan penyelesaian), laporan kegiatan, uji tanah,
tugas wilayah, Komsos, temuan ilegal, patroli Taman Buru (temuan & bibit),
kegiatan lainnya dengan penilaian dampak, bidang penguasaan lahan, zona
ancaman, lapisan RTRW contoh, titik uji tanah PLTS, dan tiket masukan untuk
pusat komando, foto kegiatan, riwayat sikap & luas lahan warga, sesi patroli
SMART (jalur, observasi, foto), foto 360°, serta foto & riwayat titik PLTS.
Semua nama dan kode fiktif; tidak ada NIK. Bila data contoh lama sudah ada,
bagian yang baru dilengkapi.

Rantai komando contoh (tugas berpoin, laporan harian berjenjang & lampirannya,
absensi, obrolan Korwil, SOS yang sudah selesai, posisi & jejak GPS petugas,
analisis citra area) dibuat oleh ``pengguna_contoh`` lewat :func:`komando_demo`
karena memerlukan akun contoh.
"""

import datetime
import random

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import LineString, MultiPolygon, Point, Polygon
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from asetlahan import enums as aset_enums
from asetlahan.models import MapOverlay, MapOverlayFeature, Task
from operasi import enums, geotech, spatial, task_flow, tools
from operasi.models import (
    Activity,
    ActivityPhoto,
    AreaAnalysis,
    Attendance,
    ChatMessage,
    DailyReport,
    DailyReportAttachment,
    DailyReportEvent,
    GeotechChange,
    GeotechPhoto,
    GeotechPoint,
    HuntingParkFinding,
    HuntingParkPatrol,
    IllegalFinding,
    IllegalFindingVisit,
    Korwil,
    LandAreaChange,
    LandPlot,
    LandPlotChange,
    OfficerPosition,
    OfficerProfile,
    OfficerTrackPoint,
    PatrolObservation,
    PatrolPhoto,
    PatrolSession,
    Resident,
    Seedling,
    SitePhoto360,
    SoilTest,
    SosAlert,
    StanceChange,
    TaskEvent,
    ThreatZone,
    Ticket,
)
from utils.sample_files import delete_files, jpeg_upload, pdf_upload, png_upload

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

# Korwil yang diberi contoh temuan ilegal / patroli Taman Buru.
ILLEGAL_KORWILS = {
    "B": (enums.IllegalActivityKind.LOGGING, "Hutan Pos 500"),
    "D": (enums.IllegalActivityKind.CLEARING, "Bukit Monggak"),
    "H": (enums.IllegalActivityKind.MINING, "Bekas galian Pasir Merah"),
}
PATROL_KORWILS = {"C": "Seranggong", "G": "Hutan Blongkeng"}


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
            added = (
                self._extras()
                if Korwil.objects.filter(note__startswith=MARK).exists()
                else 0
            )
            self.stdout.write(
                "Korwil A–K sudah ada; data contoh dilewati"
                + (f" ({added} bagian baru dilengkapi)." if added else ".")
                + " Jalankan --hapus dahulu untuk membuat ulang data contoh."
            )
            return
        self._create()
        self._extras()
        self.stdout.write(self.style.SUCCESS("Data contoh pusat komando dibuat."))

    def _delete(self):
        korwils = Korwil.objects.filter(note__startswith=MARK)
        delete_komando_demo()
        sessions = PatrolSession.objects.filter(name__startswith=MARK)
        delete_files(
            *(
                photo.photo
                for photo in PatrolPhoto.objects.filter(
                    observation__session__in=sessions
                )
            )
        )
        sessions.delete()
        photos360 = SitePhoto360.objects.filter(title__startswith=MARK)
        delete_files(*(p.image for p in photos360))
        photos360.delete()
        delete_files(
            *(
                p.photo
                for p in ActivityPhoto.objects.filter(
                    activity__description__startswith=MARK
                )
            ),
            *(
                p.image
                for p in GeotechPhoto.objects.filter(
                    point__survey_note__startswith=MARK
                )
            ),
        )
        GeotechPoint.objects.filter(survey_note__startswith=MARK).delete()
        Ticket.objects.filter(title__startswith=MARK).delete()
        LandPlot.objects.filter(note__startswith=MARK).delete()
        ThreatZone.objects.filter(note__startswith=MARK).delete()
        MapOverlay.objects.filter(note__startswith=MARK).delete()
        Task.objects.filter(title__startswith=MARK).delete()
        Activity.objects.filter(description__startswith=MARK).delete()
        IllegalFinding.objects.filter(note__startswith=MARK).delete()
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
                activity.refresh_effort()
            self._komsos(rng, korwil, residents, user, now)
            if code in ILLEGAL_KORWILS:
                self._illegal(rng, korwil, user, now, *ILLEGAL_KORWILS[code])
            if code in PATROL_KORWILS:
                self._patrol(rng, korwil, user, now, PATROL_KORWILS[code])
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
        self._spatial(user)
        self._tools(user)

    def _extras(self) -> int:  # noqa: C901
        """Bagian yang ditambahkan belakangan (idempoten)."""
        user = get_user_model().objects.filter(is_superuser=True).order_by("pk").first()
        rng = random.Random(20261102)
        now = timezone.now()
        added = 0
        activities = Activity.objects.filter(description__startswith=MARK)
        if not ActivityPhoto.objects.filter(activity__in=activities).exists():
            for activity in activities.order_by("pk")[:6]:
                ActivityPhoto.objects.create(
                    activity=activity,
                    photo=jpeg_upload(f"Foto kegiatan {activity.pk}"),
                    caption=f"{MARK} Dokumentasi {activity.title}",
                    location=activity.location,
                )
            added += 1
        residents = Resident.objects.filter(note__startswith=MARK).order_by("pk")
        if not StanceChange.objects.filter(resident__in=residents).exists():
            for resident in residents[:4]:
                old = (
                    enums.Stance.NEUTRAL
                    if resident.stance != enums.Stance.NEUTRAL
                    else enums.Stance.UNKNOWN
                )
                StanceChange.objects.create(
                    resident=resident,
                    old_stance=old,
                    new_stance=resident.stance,
                    changed_by=user,
                )
            for resident in residents[4:7]:
                new_area = resident.land_area_m2 or 600
                LandAreaChange.objects.create(
                    resident=resident,
                    old_area_m2=None,
                    new_area_m2=new_area,
                    changed_by=user,
                )
                if resident.land_area_m2 is None:
                    Resident.objects.filter(pk=resident.pk).update(
                        land_area_m2=new_area
                    )
            added += 1
        if not PatrolSession.objects.filter(name__startswith=MARK).exists():
            patrol = (
                Activity.objects.filter(
                    description__startswith=MARK,
                    activity_type=enums.ActivityType.HUNTING_PARK,
                )
                .select_related("korwil")
                .first()
            )
            if patrol is not None:
                self._patrol_session(rng, patrol, user, now)
                added += 1
        if not SitePhoto360.objects.filter(title__startswith=MARK).exists():
            for code in ("A", "E"):
                korwil = Korwil.objects.filter(code=code, note__startswith=MARK).first()
                if korwil is None:
                    continue
                SitePhoto360.objects.create(
                    title=f"{MARK} Panorama 360° Korwil {code}",
                    korwil=korwil,
                    location=korwil.geometry.centroid,
                    captured_on=timezone.localdate() - datetime.timedelta(days=4),
                    image=jpeg_upload(
                        f"Panorama 360 Korwil {code}", size=(1024, 512), color="#2e7d5b"
                    ),
                    uploaded_by=user,
                    note="Foto panorama fiktif.",
                )
            added += 1
        points = GeotechPoint.objects.filter(survey_note__startswith=MARK).order_by(
            "pk"
        )
        if not GeotechPhoto.objects.filter(point__in=points).exists():
            for point in points[:3]:
                GeotechPhoto.objects.create(
                    point=point,
                    image=jpeg_upload(f"Uji tanah {point.code}", color="#8d6e63"),
                    caption=f"{MARK} Lubang uji {point.code}",
                    uploaded_by=user,
                )
                GeotechChange.objects.create(
                    point=point,
                    field="Status pekerjaan",
                    old_value="Belum dikerjakan",
                    new_value=str(point.get_work_status_display()),
                    note=f"{MARK} Pembaruan contoh",
                    source="Panel admin",
                    changed_by=user,
                )
            added += 1
        return added

    def _patrol_session(self, rng, activity, user, now):
        start = activity.location
        coords = [
            (start.x + i * 0.0012, start.y + (0.0008 if i % 2 else 0) - i * 0.0004)
            for i in range(6)
        ]
        session = PatrolSession.objects.create(
            activity=activity,
            korwil=activity.korwil,
            smart_patrol_id=f"SMART-CONTOH-{activity.korwil.code}",
            name=f"{MARK} Patroli SMART kawasan Taman Buru",
            started_at=now - datetime.timedelta(days=2, hours=5),
            ended_at=now - datetime.timedelta(days=2, hours=1),
            leader="Ketua Regu Contoh",
            team="Regu A",
            station="Pos Contoh",
            transport="Jalan kaki",
            comments="Jalur aman; jejak satwa di dua titik.",
            distance_m=3200,
            track=LineString(coords, srid=4326),
            source_name="patroli-contoh.xml",
            uploaded_by=user,
        )
        for seq, (x, y) in enumerate(coords[1:5], 1):
            observation = PatrolObservation.objects.create(
                session=session,
                seq=seq,
                kind="Observation" if seq % 2 else "Waypoint",
                location=Point(x, y, srid=4326),
                observed_at=session.started_at + datetime.timedelta(minutes=40 * seq),
                comment=f"{MARK} Titik pengamatan {seq}",
                leg_distance_m=rng.randint(300, 900),
            )
            if seq == 1:
                PatrolPhoto.objects.create(
                    observation=observation,
                    photo=jpeg_upload("Jejak satwa", color="#5d7a3a"),
                )

    def _tools(self, user):
        """Titik uji tanah PLTS dan tiket masukan (fiktif)."""
        rng = random.Random(20261101)
        today = timezone.localdate()
        W = enums.GeotechWorkStatus
        plan = (
            ("A", "PV", "Blok surya contoh 1", 9),
            ("E", "PV", "Blok surya contoh 2", 7),
            ("E", "TL", "Jalur transmisi contoh", 5),
            ("G", "GI", "Gardu contoh", 3),
        )
        methods = (
            enums.GeotechMethod.BOREHOLE,
            enums.GeotechMethod.TEST_PIT,
            enums.GeotechMethod.RESISTIVITY,
            enums.GeotechMethod.SONDIR,
            enums.GeotechMethod.THERMAL,
        )
        statuses = (
            (W.DONE, 4),
            (W.IN_PROGRESS, 3),
            (W.NOT_STARTED, 3),
            (W.STOPPED, 1),
        )
        korwils = {k.code: k for k in Korwil.objects.filter(note__startswith=MARK)}
        for code, prefix, area, count in plan:
            korwil = korwils.get(code)
            if korwil is None:
                continue
            for number in range(1, count + 1):
                status = _pick(rng, statuses)
                method = methods[number % len(methods)]
                started = today - datetime.timedelta(days=rng.randint(5, 40))
                point = GeotechPoint(
                    code=f"{prefix}-CTH{code}-{number:02d}",
                    method=method,
                    area_name=area,
                    zone_name=f"Zona {1 + number % 3}",
                    batch=1 + (number - 1) // 4,
                    korwil=korwil,
                    location=_random_point(rng, korwil.geometry),
                    landowner=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                    work_status=status,
                    progress_pct=rng.randint(20, 80),
                    social_condition=(
                        enums.SocialCondition.NOT_CONDUCIVE
                        if status == W.STOPPED
                        else enums.SocialCondition.CONDUCIVE
                    ),
                    survey_status=(
                        enums.SurveyStatus.DONE
                        if status != W.NOT_STARTED or rng.random() < 0.4
                        else enums.SurveyStatus.PENDING
                    ),
                    obstacle=(
                        "Pemilik lahan belum mengizinkan akses (contoh)"
                        if status == W.STOPPED
                        else ""
                    ),
                    started_on=started if status != W.NOT_STARTED else None,
                    finished_on=(
                        started + datetime.timedelta(days=rng.randint(1, 4))
                        if status == W.DONE
                        else None
                    ),
                    survey_note=f"{MARK} Titik uji fiktif.",
                    created_by=user,
                    updated_by=user,
                )
                point._korwil_resolved = True
                geotech.save_with_history(point, user)
        if user is None:
            return
        now = timezone.now()
        samples = (
            (
                enums.TicketCategory.BUG,
                enums.TicketPriority.HIGH,
                "Foto laporan tidak muncul di riwayat",
                enums.TicketStatus.NEW,
            ),
            (
                enums.TicketCategory.OUTAGE,
                enums.TicketPriority.CRITICAL,
                "Peta lambat dimuat saat sinyal lemah",
                enums.TicketStatus.IN_PROGRESS,
            ),
            (
                enums.TicketCategory.SUGGESTION,
                enums.TicketPriority.NORMAL,
                "Tambah filter tanggal di daftar warga",
                enums.TicketStatus.DONE,
            ),
        )
        for index, (category, priority, title, status) in enumerate(samples):
            ticket = Ticket.objects.create(
                category=category,
                priority=priority,
                title=f"{MARK} {title}",
                description="Tiket contoh untuk uji coba alur masukan.",
                created_by=user,
            )
            if status != enums.TicketStatus.NEW:
                Ticket.objects.filter(pk=ticket.pk).update(
                    created_at=now - datetime.timedelta(hours=30 + index * 10)
                )
                ticket.refresh_from_db()
                tools.set_ticket_status(ticket, user, status, note="Contoh tanggapan.")

    def _spatial(self, user):
        """Lapisan RTRW contoh, bidang penguasaan, dan zona ancaman (fiktif)."""
        rng = random.Random(20261031)
        today = timezone.localdate()
        overlay = MapOverlay.objects.create(
            name="RTRW contoh Rempang (fiktif)",
            kind=aset_enums.OverlayKind.SPATIAL_PLAN,
            show_in_command=True,
            source="Data contoh",
            note=f"{MARK} Lapisan fiktif untuk uji coba pusat komando.",
        )
        zones = ("Zona Khusus", "Zona Budi Daya", "Zona Lindung")
        korwils = Korwil.objects.filter(note__startswith=MARK).order_by("code")
        for index, korwil in enumerate(korwils):
            xmin, ymin, xmax, ymax = korwil.geometry.extent
            zone = zones[index % len(zones)]
            MapOverlayFeature.objects.create(
                overlay=overlay,
                name=zone,
                geometry=Polygon.from_bbox((xmin, ymin, (xmin + xmax) / 2, ymax)),
                properties={"zona": zone},
            )
            for number in range(1, 4):
                center = _random_point(rng, korwil.geometry)
                half = rng.uniform(0.0004, 0.0015)
                controlled = rng.random() < 0.4
                plot = LandPlot.objects.create(
                    name=f"Bidang {korwil.code}-{number}",
                    owner_name=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                    korwil=korwil,
                    geometry=MultiPolygon(
                        Polygon.from_bbox(
                            (
                                center.x - half,
                                center.y - half,
                                center.x + half,
                                center.y + half,
                            )
                        ),
                        srid=4326,
                    ),
                    control_status=(
                        enums.ControlStatus.CONTROLLED
                        if controlled
                        else enums.ControlStatus.PENDING
                    ),
                    controlled_on=(
                        today - datetime.timedelta(days=rng.randint(1, 60))
                        if controlled
                        else None
                    ),
                    control_team="Tim contoh" if controlled else "",
                    urgency=rng.choice(enums.PlotUrgency.values),
                    source="Data contoh",
                    created_by=user,
                    note=f"{MARK} Bidang fiktif.",
                )
                LandPlotChange.objects.create(
                    plot=plot,
                    new_status=plot.control_status,
                    changed_by=user,
                    note="Data contoh",
                )
            if korwil.code in ("D", "H"):
                center = _random_point(rng, korwil.geometry)
                ThreatZone.objects.create(
                    name=f"Zona rawan contoh Korwil {korwil.code}",
                    level=(
                        enums.ThreatLevel.HIGH
                        if korwil.code == "D"
                        else enums.ThreatLevel.MEDIUM
                    ),
                    geometry=spatial.circle(center.y, center.x, 400),
                    korwil=korwil,
                    created_by=user,
                    note=f"{MARK} Zona fiktif.",
                )

    def _komsos(self, rng, korwil, residents, user, now):
        activity = Activity.objects.create(
            korwil=korwil,
            activity_type=enums.ActivityType.KOMSOS,
            title=f"Komsos – Korwil {korwil.code}",
            description=f"{MARK} Komsos contoh: warga menanyakan jadwal hunian baru "
            "dan bersedia hadir pada pertemuan berikutnya.",
            started_at=now - datetime.timedelta(days=rng.randint(1, 10)),
            location=_random_point(rng, korwil.geometry),
            companion="Petugas pendamping contoh",
            reported_by=user,
        )
        activity.residents.set(rng.sample(residents, min(2, len(residents))))
        activity.touch_residents()
        activity.refresh_effort()

    def _illegal(self, rng, korwil, user, now, kind, place):
        point = _random_point(rng, korwil.geometry)
        finding = IllegalFinding.objects.create(
            korwil=korwil,
            activity_kind=kind,
            location_name=place,
            location=point,
            owner_name=f"Bpk {rng.choice(LAST_NAMES)}",
            manager_name=f"Sdr. {rng.choice(FIRST_NAMES)}",
            area_ha=round(rng.uniform(0.5, 6), 2),
            forest_status="Hutan produksi",
            business_started="Sekitar pertengahan 2025",
            created_by=user,
            note=f"{MARK} Temuan fiktif.",
        )
        for visit in range(2):
            activity = Activity.objects.create(
                korwil=korwil,
                activity_type=enums.ActivityType.ILLEGAL,
                title=f"Temuan ilegal – {place}",
                location_name=place,
                description=f"{MARK} Pemeriksaan lokasi temuan.",
                started_at=now - datetime.timedelta(days=12 - visit * 6),
                location=point,
                reported_by=user,
            )
            IllegalFindingVisit.objects.create(
                activity=activity,
                finding=finding,
                is_new=visit == 0,
                permit=enums.PermitStatus.NO,
                business_activity=(
                    enums.BusinessActivity.ACTIVE
                    if visit == 0
                    else enums.BusinessActivity.INACTIVE
                ),
                equipment="1 unit gergaji mesin" if visit == 0 else "",
                follow_up=(
                    "Dilaporkan ke pihak terkait; dipasang papan peringatan."
                    if visit == 0
                    else "Kegiatan sudah berhenti; pemantauan lanjutan."
                ),
            )
            activity.refresh_effort()

    def _patrol(self, rng, korwil, user, now, place):
        activity = Activity.objects.create(
            korwil=korwil,
            activity_type=enums.ActivityType.HUNTING_PARK,
            title=f"Patroli Taman Buru – {place}",
            location_name=place,
            description=f"{MARK} Patroli rutin kawasan; jalur aman, ada jejak satwa.",
            started_at=now - datetime.timedelta(days=rng.randint(1, 7)),
            location=_random_point(rng, korwil.geometry),
            distance_m=rng.randint(2500, 6000),
            reported_by=user,
        )
        report = HuntingParkPatrol.objects.create(
            activity=activity,
            grid=f"TBPR{rng.randint(10, 99)}",
            routes=[enums.PatrolRoute.LOGGING_PATH, enums.PatrolRoute.POACHING],
            objective="Patroli rutin kawasan",
            team_leader=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
            team="Regu A",
            situation=enums.PatrolSituation.CONDUCIVE,
            personnel_condition=enums.PersonnelCondition.HEALTHY,
            materiel_condition=enums.MaterielCondition.SAFE,
            weather_morning=enums.Weather.CLEAR,
            weather_noon=enums.Weather.CLOUDY,
            weather_afternoon=enums.Weather.RAIN,
        )
        HuntingParkFinding.objects.create(
            patrol=report,
            category=enums.FindingCategory.FAUNA,
            description="Jejak babi hutan di tepi sungai",
            quantity=3,
            forest_status="Sekunder",
        )
        HuntingParkFinding.objects.create(
            patrol=report,
            category=enums.FindingCategory.FLORA,
            description="Hamparan pohon meranti",
            quantity=10,
            forest_status="Sekunder",
        )
        Seedling.objects.create(
            patrol=report,
            kind=enums.SeedlingKind.TENDED,
            species="Meranti",
            quantity=rng.randint(20, 80),
        )
        Seedling.objects.create(
            patrol=report,
            kind=enums.SeedlingKind.PRODUCED,
            species="Pulai",
            quantity=rng.randint(10, 40),
        )
        activity.refresh_effort()
        Activity.objects.create(
            korwil=korwil,
            activity_type=enums.ActivityType.OTHER,
            title=f"Koordinasi aparat kampung – Korwil {korwil.code}",
            description=f"{MARK} Koordinasi pengamanan kawasan bersama aparat kampung.",
            started_at=now - datetime.timedelta(days=rng.randint(1, 7)),
            location=_random_point(rng, korwil.geometry),
            impact_scope=enums.ImpactScope.KORWIL,
            impact_risk=enums.ImpactRisk.HIGH,
            impact_result=enums.ImpactResult.OUTPUT,
            reported_by=user,
        )


# --------------------------------------------------------------------------
# Rantai komando contoh: petugas lapangan -> koordinator Korwil -> pimpinan
# --------------------------------------------------------------------------

# (judul, jenis kegiatan, poin, tenggat (hari), urutan peristiwa)
DEMO_TASKS = [
    (
        "Sosialisasi jadwal pengukuran RT 02",
        enums.ActivityType.SOCIALIZATION,
        10,
        3,
        [],
    ),
    (
        "Pendataan ulang KK Pasir Panjang",
        enums.ActivityType.CENSUS,
        15,
        5,
        ["mulai"],
    ),
    (
        "Dokumentasi kondisi jalan kampung",
        enums.ActivityType.MAPPING,
        10,
        2,
        ["mulai", "lapor"],
    ),
    (
        "Patroli batas wilayah Korwil A",
        enums.ActivityType.PATROL,
        20,
        1,
        ["mulai", "lapor", "verifikasi"],
    ),
]
DEMO_EVENTS = {
    "mulai": (aset_enums.TaskStatus.IN_PROGRESS, enums.TaskEventKind.STARTED, ""),
    "lapor": (
        aset_enums.TaskStatus.REPORTED,
        enums.TaskEventKind.SUBMITTED,
        "Selesai dikerjakan; foto dan catatan lapangan terlampir di laporan harian.",
    ),
    "verifikasi": (
        aset_enums.TaskStatus.DONE,
        enums.TaskEventKind.VERIFIED,
        "Hasil sesuai.",
    ),
}


SAMPLE_AI_MODEL = "contoh"
SAMPLE_DOMAIN = "contoh.simlahan.invalid"


def delete_komando_demo():
    """Hapus data rantai komando contoh (dipanggil sebelum akun contoh dihapus)."""
    attendances = Attendance.objects.filter(note__startswith=MARK)
    delete_files(
        *(
            field
            for a in attendances
            for field in (a.check_in_photo, a.check_out_photo, a.attachment)
        )
    )
    attendances.delete()
    ChatMessage.objects.filter(body__startswith=MARK).delete()
    SosAlert.objects.filter(message__startswith=MARK).delete()
    OfficerPosition.objects.filter(user__email__iendswith=f"@{SAMPLE_DOMAIN}").delete()
    OfficerTrackPoint.objects.filter(
        user__email__iendswith=f"@{SAMPLE_DOMAIN}"
    ).delete()
    analyses = AreaAnalysis.objects.filter(ai_model=SAMPLE_AI_MODEL)
    delete_files(*(a.image for a in analyses))
    analyses.delete()
    reports = DailyReport.objects.filter(content__startswith=MARK)
    delete_files(
        *(a.file for a in DailyReportAttachment.objects.filter(report__in=reports))
    )
    DailyReport.objects.filter(consolidated_into__in=reports).update(
        consolidated_into=None
    )
    Activity.objects.filter(daily_report__in=reports).update(daily_report=None)
    reports.delete()
    Task.objects.filter(title__startswith=MARK).filter(
        komando_events__isnull=False
    ).delete()


def komando_demo(leader, coordinator, officer, korwil):
    """Profil jabatan, tugas berpoin, dan laporan harian contoh (idempoten)."""
    OfficerProfile.objects.update_or_create(
        user=coordinator,
        defaults={
            "position": f"Koordinator Korwil {korwil.code}",
            "supervisor": leader,
        },
    )
    OfficerProfile.objects.update_or_create(
        user=officer,
        defaults={
            "position": f"Petugas Lapangan Korwil {korwil.code}",
            "supervisor": coordinator,
        },
    )
    OfficerProfile.objects.get_or_create(user=leader, defaults={"position": "Pimpinan"})
    if not Task.objects.filter(title__startswith=MARK, assignee=officer).exists():
        _demo_tasks(leader, coordinator, officer, korwil)
    else:
        _demo_attachment(officer)
    if not Attendance.objects.filter(user=officer, note__startswith=MARK).exists():
        _demo_field(leader, coordinator, officer, korwil)


def _demo_tasks(leader, coordinator, officer, korwil):
    now = timezone.now()
    today = timezone.localdate()
    for title, kind, points, due, steps in DEMO_TASKS:
        task = Task.objects.create(
            title=f"{MARK} {title}",
            description="Tugas contoh rantai komando.",
            assignee=officer,
            korwil=korwil,
            activity_type=kind,
            point_value=points,
            priority=aset_enums.Priority.NORMAL,
            start_date=today,
            due_date=today + datetime.timedelta(days=due),
            created_by=coordinator,
        )
        TaskEvent.objects.create(
            task=task,
            kind=enums.TaskEventKind.CREATED,
            actor=coordinator,
            note=f"Untuk {officer.get_full_name() or officer}",
        )
        for step in steps:
            status, event_kind, note = DEMO_EVENTS[step]
            actor = coordinator if step == "verifikasi" else officer
            TaskEvent.objects.create(task=task, kind=event_kind, actor=actor, note=note)
            task.status = status
        if steps:
            task.progress = {1: 40, 2: 90, 3: 100}[len(steps)]
            if task.status == aset_enums.TaskStatus.DONE:
                task.completed_date = today
            task.save()
            if task.status == aset_enums.TaskStatus.DONE:
                task_flow.award_points(task)
    # Laporan petugas kemarin sudah dirangkum koordinator dan menunggu pimpinan;
    # laporan hari ini masih di kotak masuk koordinator.
    yesterday = now - datetime.timedelta(days=1)
    summary = _demo_report(
        coordinator,
        leader,
        korwil,
        yesterday,
        "Rangkuman Korwil: pendataan berjalan, satu jalan kampung rusak "
        "didokumentasikan, patroli batas wilayah selesai tanpa temuan baru.",
    )
    source = _demo_report(
        officer,
        coordinator,
        korwil,
        yesterday - datetime.timedelta(hours=2),
        "Patroli batas wilayah selesai; pendataan 6 KK; dokumentasi jalan kampung.",
    )
    source.consolidated_into = summary
    source.status = enums.DailyReportStatus.FORWARDED
    source.save(update_fields=["consolidated_into", "status"])
    DailyReportEvent.objects.create(
        report=source,
        action=enums.DailyReportAction.FORWARDED,
        actor=coordinator,
        target=leader,
        created_at=yesterday,
    )
    today_report = _demo_report(
        officer,
        coordinator,
        korwil,
        now - datetime.timedelta(hours=1),
        "Sosialisasi jadwal pengukuran disiapkan; pendataan ulang KK berlanjut.",
    )
    _demo_attachment(officer, today_report)


def _demo_attachment(officer, report=None):
    """Lampiran laporan harian contoh (juga untuk data contoh versi lama)."""
    reports = DailyReport.objects.filter(author=officer, content__startswith=MARK)
    if DailyReportAttachment.objects.filter(report__in=reports).exists():
        return
    report = report or reports.order_by("-pk").first()
    if report is None:
        return
    DailyReportAttachment.objects.create(
        report=report,
        file=pdf_upload(
            "Daftar hadir sosialisasi", ("Lampiran laporan harian contoh.",)
        ),
        name="daftar-hadir-sosialisasi-contoh.pdf",
        uploaded_by=officer,
    )


def _demo_field(leader, coordinator, officer, korwil):
    """Absensi, obrolan, SOS selesai, posisi & jejak GPS, dan analisis citra."""
    from operasi.satellite import data_summary

    now = timezone.now()
    today = timezone.localdate()
    # Korwil tanpa batas wilayah (dibuat manual) memakai titik acuan Rempang.
    center = (
        korwil.geometry.centroid if korwil.geometry else Point(104.12, 0.89, srid=4326)
    )
    near = [
        Point(center.x + dx, center.y + dy, srid=4326)
        for dx, dy in ((0.0006, 0.0004), (-0.0005, 0.0007), (0.0009, -0.0003))
    ]
    S = enums.AttendanceStatus
    for user, days, status, note, approval in (
        (officer, 0, S.PRESENT, "Hadir tepat waktu.", ""),
        (officer, 1, S.LATE, "Terlambat karena ban bocor.", ""),
        (officer, 2, S.SICK, "Demam, surat dokter terlampir.",
         enums.LeaveApproval.APPROVED),
        (officer, -1, S.DUTY, "Rapat koordinasi di kecamatan.",
         enums.LeaveApproval.PENDING),
        (coordinator, 0, S.PRESENT, "Hadir.", ""),
    ):  # fmt: skip
        date = today - datetime.timedelta(days=days)
        moment = timezone.make_aware(
            datetime.datetime.combine(date, datetime.time(7, 45 if days else 30))
        )
        present = status in (S.PRESENT, S.LATE)
        defaults = {
            "korwil": korwil,
            "status": status,
            "note": f"{MARK} {note}",
            "approval": approval,
            "approved_by": (
                coordinator if approval == enums.LeaveApproval.APPROVED else None
            ),
            "approved_at": now if approval == enums.LeaveApproval.APPROVED else None,
        }
        if present:
            defaults.update(
                check_in_at=moment,
                check_in_location=near[0],
                check_in_accuracy_m=8,
                check_in_in_area=True,
                check_in_photo=jpeg_upload(f"Swafoto absen {user.username}"),
            )
            if days:
                defaults.update(
                    check_out_at=moment + datetime.timedelta(hours=9),
                    check_out_location=near[1],
                    check_out_accuracy_m=10,
                    check_out_in_area=True,
                )
        elif status == S.SICK:
            defaults["attachment"] = pdf_upload("Surat keterangan sakit")
        Attendance.objects.update_or_create(user=user, date=date, defaults=defaults)

    for minutes, sender, body, is_system in (
        (180, None, "Absensi pagi dibuka.", True),
        (170, coordinator, "Pagi tim, fokus pendataan RT 02 hari ini.", False),
        (160, officer, "Siap, saya mulai dari rumah ujung jalan.", False),
        (30, officer, "Pendataan 6 KK selesai, lanjut dokumentasi jalan.", False),
    ):
        message = ChatMessage.objects.create(
            korwil=korwil,
            sender=sender,
            body=f"{MARK} {body}",
            location=near[2] if sender is officer else None,
            is_system=is_system,
        )
        ChatMessage.objects.filter(pk=message.pk).update(
            created_at=now - datetime.timedelta(minutes=minutes)
        )

    SosAlert.objects.create(
        raised_by=officer,
        korwil=korwil,
        location=near[1],
        accuracy_m=12,
        message=f"{MARK} Motor mogok di jalan hutan, minta jemput.",
        status=enums.SosStatus.RESOLVED,
        acknowledged_by=coordinator,
        acknowledged_at=now - datetime.timedelta(days=3, hours=2),
        resolved_by=coordinator,
        resolved_at=now - datetime.timedelta(days=3, hours=1),
        resolution_note="Dijemput tim; petugas aman (contoh).",
    )

    for user, point, minutes, battery in (
        (officer, near[2], 4, 76),
        (coordinator, near[0], 12, 58),
    ):
        OfficerPosition.objects.update_or_create(
            user=user,
            defaults={
                "location": point,
                "accuracy_m": 9,
                "heading": 90,
                "speed_mps": 0.8,
                "battery_pct": battery,
                "updated_at": now - datetime.timedelta(minutes=minutes),
            },
        )
    for step in range(12):
        OfficerTrackPoint.objects.create(
            user=officer,
            location=Point(
                center.x - 0.003 + step * 0.0003,
                center.y - 0.002 + (step % 3) * 0.0002,
                srid=4326,
            ),
            accuracy_m=8,
            recorded_at=now - datetime.timedelta(minutes=5 + (11 - step) * 10),
        )

    box = Polygon.from_bbox(
        (center.x - 0.004, center.y - 0.003, center.x + 0.004, center.y + 0.003)
    )
    box.srid = 4326
    AreaAnalysis.objects.create(
        bbox=box,
        requested_by=coordinator,
        zoom=17,
        image=png_upload("Mosaik citra area contoh", color="#3d6b4f"),
        data_summary=data_summary(box, coordinator),
        ai_model=SAMPLE_AI_MODEL,
        ai_result={
            "tutupan_lahan": {
                "vegetasi_pct": 62,
                "bangunan_pct": 9,
                "lahan_terbuka_pct": 18,
                "air_pct": 7,
                "jalan_pct": 4,
            },
            "perkiraan_jumlah_bangunan": 14,
            "temuan": ["Permukiman kecil di sisi barat", "Pembukaan lahan baru ±1 ha"],
            "rekomendasi": ["Verifikasi lapangan pembukaan lahan baru"],
            "ringkasan": f"{MARK} Hasil analisis fiktif untuk uji coba tampilan.",
        },
    )


def _demo_report(author, recipient, korwil, sent_at, text):
    position = getattr(getattr(author, "komando_profile", None), "position", "")
    report = DailyReport.objects.create(
        author=author,
        author_position=position,
        recipient=recipient,
        korwil=korwil,
        report_date=timezone.localtime(sent_at).date(),
        sent_at=sent_at,
        content=f"{MARK} {text}",
    )
    DailyReportEvent.objects.create(
        report=report,
        action=enums.DailyReportAction.SENT,
        actor=author,
        target=recipient,
        created_at=sent_at,
    )
    return report
