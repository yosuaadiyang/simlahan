"""Model pusat komando operasi lapangan.

Wilayah kerja dibagi per Korwil (koordinator wilayah). Di tiap Korwil petugas
mendata warga (sikap, status lahan, kesesuaian RTRW), melaporkan kegiatan,
mengambil sampel uji tanah, absen dengan GPS, menerima tugas, saling
berkirim pesan, dan dapat mengirim tanda darurat (SOS). Data warga dapat
dihubungkan ke modul pengadaan tanah dan bank tanah agar tidak dicatat dua kali.
"""

import datetime
import uuid
from decimal import Decimal

from auditlog.registry import auditlog
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.gis.db import models as gmodels
from django.contrib.gis.geos import Point
from django.contrib.postgres.fields import ArrayField
from django.core.cache import cache
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from sequences import get_next_value

from asetlahan.models import DOCUMENT_VALIDATORS, IMAGE_VALIDATORS
from file_operations.private_files import PrivateFileField
from leasing.models.mixins import TimeStampedModel
from operasi import enums
from pengadaan.crypto import EncryptedCharField, fingerprint

DEFAULT_SATELLITE_TILES = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/"
    "tile/{z}/{y}/{x}"
)
LOCK_CACHE_KEY = "operasi:system-lock"

MAX_AUDIO_BYTES = 10 * 1024 * 1024
# Batas kolom Resident.land_area_m2 (max_digits=16, decimal_places=2).
MAX_LAND_AREA_M2 = Decimal("99999999999999.99")


def validate_audio_size(value):
    from django.core.exceptions import ValidationError

    if value and value.size > MAX_AUDIO_BYTES:
        raise ValidationError(_("Ukuran rekaman maksimal 10 MB."))


AUDIO_VALIDATORS = [
    FileExtensionValidator(allowed_extensions=["m4a", "mp3", "wav", "ogg", "webm"]),
    validate_audio_size,
]


def _upload_to(name, prefix):
    def inner(instance, filename):
        return f"operasi/{prefix}/{timezone.now():%Y/%m}/{uuid.uuid4().hex}/{filename}"

    # Nama harus sama dengan nama variabel modul agar dapat diimpor oleh migrasi.
    inner.__name__ = inner.__qualname__ = name
    return inner


upload_attendance = _upload_to("upload_attendance", "absen")
upload_activity = _upload_to("upload_activity", "kegiatan")
upload_soil = _upload_to("upload_soil", "uji-tanah")
upload_analysis = _upload_to("upload_analysis", "ai-satelit")
upload_patrol = _upload_to("upload_patrol", "patroli")
upload_task = _upload_to("upload_task", "tugas")
upload_daily_report = _upload_to("upload_daily_report", "laporan-harian")


def next_number(prefix: str) -> str:
    year = timezone.localdate().year
    value = get_next_value(f"operasi_{prefix.lower()}_{year}")
    return f"{prefix}-{year}-{value:04d}"


def _user_field(verbose_name, related_name="+"):
    return models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=verbose_name,
        related_name=related_name,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )


def _korwil_field(related_name):
    return models.ForeignKey(
        "operasi.Korwil",
        verbose_name=_("Korwil"),
        related_name=related_name,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )


# --------------------------------------------------------------------------
# Pengaturan
# --------------------------------------------------------------------------


class CommandSettings(models.Model):
    """Pengaturan pusat komando (satu baris)."""

    work_start = models.TimeField(_("Jam masuk"), default=datetime.time(8, 0))
    late_tolerance_minutes = models.PositiveSmallIntegerField(
        _("Toleransi terlambat (menit)"), default=15
    )
    work_end = models.TimeField(_("Jam pulang"), default=datetime.time(17, 0))
    require_attendance_photo = models.BooleanField(
        _("Wajib swafoto saat absen"), default=False
    )
    enforce_geofence = models.BooleanField(
        _("Tolak absen di luar wilayah Korwil"),
        default=False,
        help_text=_(
            "Bila tidak dicentang, absen di luar wilayah tetap diterima tetapi ditandai."
        ),
    )
    geofence_tolerance_m = models.PositiveIntegerField(
        _("Toleransi jarak dari batas Korwil (m)"), default=300
    )
    weekly_activity_target = models.PositiveSmallIntegerField(
        _("Target kegiatan per petugas per minggu"), default=5
    )
    weight_attendance = models.PositiveSmallIntegerField(
        _("Bobot kehadiran pada skor kinerja (%)"),
        default=40,
        validators=[MaxValueValidator(100)],
    )
    weight_activity = models.PositiveSmallIntegerField(
        _("Bobot kegiatan pada skor kinerja (%)"),
        default=35,
        validators=[MaxValueValidator(100)],
    )
    weight_task = models.PositiveSmallIntegerField(
        _("Bobot tugas pada skor kinerja (%)"),
        default=25,
        validators=[MaxValueValidator(100)],
    )
    scoring_mode = models.CharField(
        _("Cara menghitung kegiatan pada KPI"),
        max_length=8,
        choices=enums.ScoringMode.choices,
        default=enums.ScoringMode.EFFORT,
    )
    effort_target_multiplier = models.DecimalField(
        _("Target poin usaha = target kegiatan × angka ini"),
        max_digits=4,
        decimal_places=1,
        default=Decimal("6"),
        validators=[MinValueValidator(Decimal("0.1"))],
    )
    effort_base_default = models.DecimalField(
        _("Poin dasar jenis yang belum diberi bobot"),
        max_digits=4,
        decimal_places=1,
        default=Decimal("4"),
        validators=[MinValueValidator(0)],
    )
    effort_per_finding = models.DecimalField(
        _("Bonus per temuan"),
        max_digits=4,
        decimal_places=1,
        default=Decimal("1"),
        validators=[MinValueValidator(0)],
    )
    effort_finding_max = models.DecimalField(
        _("Bonus temuan maksimal"),
        max_digits=4,
        decimal_places=1,
        default=Decimal("5"),
        validators=[MinValueValidator(0)],
    )
    effort_per_photo = models.DecimalField(
        _("Bonus per foto"),
        max_digits=4,
        decimal_places=1,
        default=Decimal("0.5"),
        validators=[MinValueValidator(0)],
    )
    effort_photo_max = models.DecimalField(
        _("Bonus foto maksimal"),
        max_digits=4,
        decimal_places=1,
        default=Decimal("3"),
        validators=[MinValueValidator(0)],
    )
    effort_narrative_bonus = models.DecimalField(
        _("Bonus narasi lengkap"),
        max_digits=4,
        decimal_places=1,
        default=Decimal("2"),
        validators=[MinValueValidator(0)],
    )
    effort_narrative_min_chars = models.PositiveSmallIntegerField(
        _("Narasi dianggap lengkap mulai (karakter)"), default=100
    )
    effort_per_km = models.DecimalField(
        _("Bonus per km jarak tempuh"),
        max_digits=4,
        decimal_places=1,
        default=Decimal("1"),
        validators=[MinValueValidator(0)],
    )
    effort_km_max = models.DecimalField(
        _("Bonus jarak maksimal"),
        max_digits=4,
        decimal_places=1,
        default=Decimal("4"),
        validators=[MinValueValidator(0)],
    )
    effort_geotag_bonus = models.DecimalField(
        _("Bonus lokasi GPS (geotag)"),
        max_digits=4,
        decimal_places=1,
        default=Decimal("1"),
        validators=[MinValueValidator(0)],
    )
    online_minutes = models.PositiveSmallIntegerField(
        _("Petugas dianggap daring bila lokasi terakhir dalam (menit)"), default=10
    )
    sos_emails = models.TextField(
        _("Surel penerima tanda darurat (SOS)"),
        blank=True,
        default="",
        help_text=_(
            "Pisahkan dengan koma. Koordinator Korwil dan Administrator selalu "
            "menerima."
        ),
    )
    satellite_tile_url = models.CharField(
        _("Sumber ubin citra satelit untuk AI Satelit"),
        max_length=500,
        default=DEFAULT_SATELLITE_TILES,
        help_text=_("Templat XYZ dengan {z}, {x}, {y}."),
    )

    class Meta:
        verbose_name = _("Pengaturan pusat komando")
        verbose_name_plural = _("Pengaturan pusat komando")

    def __str__(self):
        return str(self._meta.verbose_name)

    def clean(self):
        from django.core.exceptions import ValidationError

        total = self.weight_attendance + self.weight_activity + self.weight_task
        if total != 100:
            raise ValidationError(
                _("Jumlah bobot kinerja harus 100%% (sekarang %(total)s%%).")
                % {"total": total}
            )
        if self.work_end <= self.work_start:
            raise ValidationError(
                {"work_end": _("Jam pulang harus setelah jam masuk.")}
            )
        url = self.satellite_tile_url
        if not url.startswith("https://") or not all(
            key in url for key in ("{z}", "{x}", "{y}")
        ):
            raise ValidationError(
                {
                    "satellite_tile_url": _(
                        "Gunakan alamat https dengan {z}, {x}, dan {y}."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "CommandSettings":
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    def sos_recipients(self) -> list[str]:
        return [e.strip() for e in self.sos_emails.split(",") if e.strip()]


class SystemLock(models.Model):
    """Kunci sistem terjadwal (deadman switch) yang hanya dikelola superuser.

    Bila aktif, hitung mundur tampil bagi petugas. Saat waktunya tiba seluruh
    aplikasi berhenti melayani pengguna selain superuser sampai kunci
    dinonaktifkan dengan kode rahasia.
    """

    is_armed = models.BooleanField(_("Aktif"), default=False)
    shutdown_at = models.DateTimeField(
        _("Sistem dimatikan pada"), null=True, blank=True
    )
    message = models.CharField(
        _("Pesan untuk pengguna"),
        max_length=255,
        default="Sistem dihentikan sementara oleh administrator.",
    )
    passcode_hash = models.CharField(max_length=255, blank=True, default="")
    armed_by = _user_field(_("Diaktifkan oleh"))
    armed_at = models.DateTimeField(_("Diaktifkan pada"), null=True, blank=True)
    defused_by = _user_field(_("Dinonaktifkan oleh"))
    defused_at = models.DateTimeField(_("Dinonaktifkan pada"), null=True, blank=True)

    class Meta:
        verbose_name = _("Kunci hidup sistem")
        verbose_name_plural = _("Kunci hidup sistem")

    def __str__(self):
        return str(self._meta.verbose_name)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(LOCK_CACHE_KEY)

    @classmethod
    def load(cls) -> "SystemLock":
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    @classmethod
    def state(cls) -> dict:
        """Status kunci (disimpan sebentar di cache agar tidak membebani tiap permintaan)."""
        data = cache.get(LOCK_CACHE_KEY)
        if data is None:
            lock = cls.objects.filter(pk=1).first()
            data = {
                "armed": bool(lock and lock.is_armed and lock.shutdown_at),
                "shutdown_at": (
                    lock.shutdown_at.isoformat()
                    if lock and lock.is_armed and lock.shutdown_at
                    else ""
                ),
                "message": str(lock.message) if lock else "",
            }
            cache.set(LOCK_CACHE_KEY, data, 15)
        return data

    @staticmethod
    def is_locked_state(data: dict, now=None) -> bool:
        if not data.get("armed"):
            return False
        now = now or timezone.now()
        return now >= datetime.datetime.fromisoformat(data["shutdown_at"])

    def set_passcode(self, raw: str):
        self.passcode_hash = make_password(raw)

    def check_passcode(self, raw: str) -> bool:
        return bool(
            raw and self.passcode_hash and check_password(raw, self.passcode_hash)
        )

    def defuse(self, user):
        self.is_armed = False
        self.defused_by = user
        self.defused_at = timezone.now()
        self.save()


# --------------------------------------------------------------------------
# Wilayah & warga
# --------------------------------------------------------------------------


class Korwil(TimeStampedModel):
    code = models.CharField(
        _("Kode"), max_length=8, unique=True, help_text=_("Mis. A, B, … K.")
    )
    name = models.CharField(_("Nama wilayah"), max_length=128)
    color = models.CharField(
        _("Warna peta"), max_length=7, default="#10b981", help_text=_("Format #RRGGBB.")
    )
    geometry = gmodels.MultiPolygonField(
        _("Batas wilayah"), srid=4326, null=True, blank=True
    )
    coordinator = _user_field(_("Koordinator"), related_name="operasi_korwil_led")
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Petugas"),
        related_name="operasi_korwil",
        blank=True,
    )
    villages = models.CharField(
        _("Kampung / kelurahan cakupan"), max_length=500, blank=True, default=""
    )
    target_households = models.PositiveIntegerField(
        _("Target KK terdata"), null=True, blank=True
    )
    service_unit = models.ForeignKey(
        "leasing.ServiceUnit",
        verbose_name=_("Unit layanan / lokasi"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text=_("Membatasi siapa yang melihat data ini. Kosong = semua petugas."),
    )
    is_active = models.BooleanField(_("Aktif"), default=True)
    note = models.TextField(_("Catatan"), blank=True, default="")

    class Meta:
        verbose_name = _("Korwil (koordinator wilayah)")
        verbose_name_plural = _("Korwil (koordinator wilayah)")
        ordering = ["code"]

    def __str__(self):
        return f"Korwil {self.code} – {self.name}"


class Resident(TimeStampedModel):
    """Kepala keluarga terdata di lapangan beserta sikap dan status lahannya."""

    number = models.CharField(_("Nomor"), max_length=32, unique=True, editable=False)
    korwil = _korwil_field("residents")
    head_name = models.CharField(_("Nama kepala keluarga"), max_length=255)
    nik = EncryptedCharField(_("NIK"), blank=True, default="")
    nik_fingerprint = models.CharField(
        max_length=64, blank=True, default="", editable=False, db_index=True
    )
    family_card_number = EncryptedCharField(_("Nomor KK"), blank=True, default="")
    member_count = models.PositiveSmallIntegerField(
        _("Jumlah jiwa"), null=True, blank=True
    )
    # --- Detail sosial-ekonomi (dossier warga ala pusat komando lapangan) ---
    gender = models.CharField(
        _("Jenis kelamin"),
        max_length=1,
        choices=enums.Gender.choices,
        blank=True,
        default="",
    )
    age = models.PositiveSmallIntegerField(_("Umur (tahun)"), null=True, blank=True)
    occupation = models.CharField(
        _("Pekerjaan"), max_length=128, blank=True, default=""
    )
    origin = models.CharField(_("Asal daerah"), max_length=128, blank=True, default="")
    years_living = models.PositiveSmallIntegerField(
        _("Lama menetap (tahun)"), null=True, blank=True
    )
    spouse_name = models.CharField(
        _("Nama pasangan"), max_length=255, blank=True, default=""
    )
    child_count = models.PositiveSmallIntegerField(
        _("Jumlah anak"), null=True, blank=True
    )
    residency_status = models.CharField(
        _("Status responden"),
        max_length=16,
        choices=enums.ResidencyStatus.choices,
        blank=True,
        default="",
    )
    spouse_occupation = models.CharField(
        _("Pekerjaan pasangan"), max_length=128, blank=True, default=""
    )
    children_detail = models.TextField(
        _("Data anak"),
        blank=True,
        default="",
        help_text=_("Mis. Anak 1 = …; Anak 2 = …"),
    )
    land_area_m2 = models.DecimalField(
        _("Luas lahan yang dikuasai (m²)"),
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
    )
    cultivation_status = models.CharField(
        _("Status penggarapan lahan"),
        max_length=16,
        choices=enums.CultivationStatus.choices,
        blank=True,
        default="",
    )
    land_condition = models.TextField(
        _("Kondisi lahan (uraian)"), blank=True, default=""
    )
    phone = models.CharField(
        _("Telepon / WhatsApp"), max_length=32, blank=True, default=""
    )
    village = models.CharField(_("Kampung"), max_length=128, blank=True, default="")
    address = models.CharField(_("Alamat"), max_length=255, blank=True, default="")
    location = gmodels.PointField(_("Lokasi rumah"), srid=4326, null=True, blank=True)
    stance = models.CharField(
        _("Sikap terhadap program"),
        max_length=16,
        choices=enums.Stance.choices,
        default=enums.Stance.UNKNOWN,
    )
    land_status = models.CharField(
        _("Status lahan"),
        max_length=8,
        choices=enums.LandStatus.choices,
        default=enums.LandStatus.PENDING,
    )
    rtrw_status = models.CharField(
        _("Kesesuaian RTRW"),
        max_length=8,
        choices=enums.RtrwStatus.choices,
        default=enums.RtrwStatus.UNASSESSED,
    )
    rtrw_zone = models.CharField(
        _("Zona RTRW"),
        max_length=16,
        choices=enums.RtrwZone.choices,
        default=enums.RtrwZone.UNASSESSED,
        help_text=_("Kategori zona tata ruang untuk rekap drilldown."),
    )
    relocation_choice = models.CharField(
        _("Pilihan penyelesaian"),
        max_length=16,
        choices=enums.RelocationChoice.choices,
        default=enums.RelocationChoice.UNDECIDED,
    )
    pengadaan_household = models.ForeignKey(
        "pengadaan.AffectedHousehold",
        verbose_name=_("Rumah tangga terdampak (pengadaan)"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    pengadaan_parcel = models.ForeignKey(
        "pengadaan.AcquisitionParcel",
        verbose_name=_("Bidang pengadaan tanah"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text=_(
            "Bila bidang sudah dilepaskan/diserahkan, status lahan otomatis "
            "menjadi sudah dibebaskan."
        ),
    )
    land_asset = models.ForeignKey(
        "asetlahan.LandAsset",
        verbose_name=_("Aset lahan"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    last_visited_on = models.DateField(
        _("Terakhir dikunjungi"),
        null=True,
        blank=True,
        help_text=_("Diperbarui otomatis dari laporan kegiatan."),
    )
    created_by = _user_field(_("Didata oleh"))
    registered_activity = models.ForeignKey(
        "operasi.Activity",
        verbose_name=_("Didata pertama kali pada kegiatan"),
        related_name="registered_residents",
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        help_text=_("Komsos baru: warga didata pertama kali lewat laporan ini."),
    )
    note = models.TextField(_("Catatan"), blank=True, default="")

    class Meta:
        verbose_name = _("Warga terdata")
        verbose_name_plural = _("Warga terdata")
        ordering = ["korwil__code", "head_name"]
        permissions = [
            ("view_resident_nik", _("Dapat melihat NIK dan nomor KK warga")),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # __dict__ agar instance dengan field tertunda (.only()) tidak memicu query tambahan.
        self._initial_stance = self.__dict__.get("stance") if self.pk else None

    def __str__(self):
        return f"{self.number} {self.head_name}"

    def save(self, *args, **kwargs):
        from operasi import geo

        if not self.number:
            self.number = next_number("WRG")
        self.nik_fingerprint = fingerprint(self.nik) or ""
        if (
            self.korwil_id is None
            and self.location is not None
            and not getattr(self, "_korwil_resolved", False)
        ):
            self.korwil = geo.korwil_at(self.location)
        if self.pengadaan_parcel_id and self.land_status != enums.LandStatus.RELEASED:
            from pengadaan.models import AcquisitionParcel

            if AcquisitionParcel.all_objects.filter(
                pk=self.pengadaan_parcel_id, status__in=RELEASED_PARCEL_STATUSES
            ).exists():
                self.land_status = enums.LandStatus.RELEASED
        super().save(*args, **kwargs)
        if self._initial_stance != self.stance:
            if self._initial_stance is not None:
                StanceChange.objects.create(
                    resident=self,
                    old_stance=self._initial_stance,
                    new_stance=self.stance,
                    changed_by=getattr(self, "_changed_by", None),
                    activity=getattr(self, "_activity", None),
                )
            self._initial_stance = self.stance


RELEASED_PARCEL_STATUSES = ["released", "handed_over"]


class StanceChange(models.Model):
    """Riwayat perubahan sikap warga (dasar tren dukungan)."""

    resident = models.ForeignKey(
        Resident,
        verbose_name=_("Warga"),
        related_name="stance_changes",
        on_delete=models.CASCADE,
    )
    old_stance = models.CharField(
        _("Sikap sebelumnya"), max_length=16, choices=enums.Stance.choices
    )
    new_stance = models.CharField(
        _("Sikap baru"), max_length=16, choices=enums.Stance.choices
    )
    changed_by = _user_field(_("Diubah oleh"))
    changed_at = models.DateTimeField(_("Waktu"), auto_now_add=True)
    activity = models.ForeignKey(
        "operasi.Activity",
        verbose_name=_("Kegiatan"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = _("Perubahan sikap warga")
        verbose_name_plural = _("Perubahan sikap warga")
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.resident} {self.old_stance} → {self.new_stance}"


# --------------------------------------------------------------------------
# Kegiatan & uji tanah
# --------------------------------------------------------------------------


class Activity(TimeStampedModel):
    number = models.CharField(_("Nomor"), max_length=32, unique=True, editable=False)
    client_id = models.UUIDField(
        _("ID perangkat"),
        unique=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_("Mencegah laporan ganda saat sinkronisasi ulang."),
    )
    korwil = _korwil_field("activities")
    activity_type = models.CharField(
        _("Jenis kegiatan"),
        max_length=16,
        choices=enums.ActivityType.choices,
        default=enums.ActivityType.VISIT,
    )
    title = models.CharField(_("Judul"), max_length=255)
    description = models.TextField(_("Uraian / narasi"), blank=True, default="")
    companion = models.CharField(
        _("Personil pendamping"), max_length=255, blank=True, default=""
    )
    location_name = models.CharField(
        _("Nama lokasi"), max_length=255, blank=True, default=""
    )
    started_at = models.DateTimeField(_("Waktu kegiatan"), default=timezone.now)
    duration_minutes = models.PositiveIntegerField(
        _("Durasi (menit)"), null=True, blank=True
    )
    location = gmodels.PointField(_("Lokasi GPS"), srid=4326, null=True, blank=True)
    accuracy_m = models.DecimalField(
        _("Akurasi GPS (m)"), max_digits=8, decimal_places=1, null=True, blank=True
    )
    distance_m = models.PositiveIntegerField(
        _("Jarak tempuh (m)"), null=True, blank=True
    )
    participants_count = models.PositiveIntegerField(
        _("Jumlah warga hadir / ditemui"), null=True, blank=True
    )
    outcome = models.TextField(_("Hasil & tindak lanjut"), blank=True, default="")
    voice_note = PrivateFileField(
        verbose_name=_("Rekaman suara (catatan lisan)"),
        max_length=255,
        upload_to=upload_activity,
        null=True,
        blank=True,
        validators=AUDIO_VALIDATORS,
        help_text=_("M4A/MP3/WAV/OGG/WEBM hingga 10 MB."),
    )
    residents = models.ManyToManyField(
        Resident,
        verbose_name=_("Warga terkait"),
        related_name="activities",
        blank=True,
    )
    task = models.ForeignKey(
        "asetlahan.Task",
        verbose_name=_("Untuk tugas"),
        related_name="operasi_activities",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    reported_by = _user_field(_("Petugas"), related_name="operasi_activities")
    verified = models.BooleanField(_("Diverifikasi koordinator"), default=False)
    verified_by = _user_field(_("Diverifikasi oleh"))
    verified_at = models.DateTimeField(_("Diverifikasi pada"), null=True, blank=True)
    # --- Kegiatan lainnya: penilaian dampak (poin dari substansi, bukan foto) ---
    impact_scope = models.PositiveSmallIntegerField(
        _("Cakupan / siapa terdampak"),
        choices=enums.ImpactScope.choices,
        null=True,
        blank=True,
    )
    impact_risk = models.PositiveSmallIntegerField(
        _("Risiko / urgensi bila tidak dilakukan"),
        choices=enums.ImpactRisk.choices,
        null=True,
        blank=True,
    )
    impact_result = models.PositiveSmallIntegerField(
        _("Hasil konkret"),
        choices=enums.ImpactResult.choices,
        null=True,
        blank=True,
    )
    impact_confirmed = models.BooleanField(
        _("Dampak tinggi dikonfirmasi atasan"), default=False
    )
    impact_confirmed_by = _user_field(_("Dampak dikonfirmasi oleh"))
    impact_confirmed_at = models.DateTimeField(
        _("Dampak dikonfirmasi pada"), null=True, blank=True
    )
    ai_stance = models.CharField(
        _("Sikap menurut AI (dari narasi)"),
        max_length=16,
        choices=enums.Stance.choices,
        blank=True,
        default="",
    )
    effort_points = models.DecimalField(
        _("Poin usaha"),
        max_digits=6,
        decimal_places=1,
        default=Decimal("0"),
        editable=False,
        help_text=_(
            "Dihitung otomatis: bobot jenis + bonus temuan, foto, narasi, "
            "jarak, dan lokasi GPS."
        ),
    )
    daily_report = models.ForeignKey(
        "operasi.DailyReport",
        verbose_name=_("Masuk laporan harian"),
        related_name="activities",
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = _("Laporan kegiatan")
        verbose_name_plural = _("Laporan kegiatan")
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.number} {self.title}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.started_at and self.started_at > timezone.now() + datetime.timedelta(
            minutes=10
        ):
            raise ValidationError(
                {"started_at": _("Waktu kegiatan tidak boleh di masa depan.")}
            )
        if (
            self._state.adding
            and self.activity_type == enums.ActivityType.OTHER
            and None in (self.impact_scope, self.impact_risk, self.impact_result)
        ):
            raise ValidationError(
                _("Kegiatan lainnya wajib dinilai dampaknya (cakupan, risiko, hasil).")
            )

    def save(self, *args, **kwargs):
        from operasi import geo

        if not self.number:
            self.number = next_number("KGT")
        if self.korwil_id is None and not getattr(self, "_korwil_resolved", False):
            self.korwil = geo.korwil_for(self.location, self.reported_by)
        if self.verified and self.verified_at is None:
            self.verified_at = timezone.now()
        elif not self.verified:
            self.verified_at = None
            self.verified_by = None
        super().save(*args, **kwargs)
        self.refresh_effort()

    @property
    def impact_score(self) -> int | None:
        values = (self.impact_scope, self.impact_risk, self.impact_result)
        return None if None in values else sum(values)

    @property
    def impact_tier(self) -> str:
        score = self.impact_score
        return "" if score is None else enums.impact_tier(score)

    @property
    def needs_impact_confirmation(self) -> bool:
        return (
            self.activity_type == enums.ActivityType.OTHER
            and self.impact_tier in enums.HIGH_IMPACT_TIERS
            and not self.impact_confirmed
        )

    def refresh_effort(self, config=None, weights=None) -> None:
        """Hitung ulang poin usaha (setelah foto/temuan tersimpan) tanpa memicu save()."""
        from operasi import services

        points = services.effort_points(self, config, weights)
        if points != self.effort_points:
            self.effort_points = points
            if self.pk:
                Activity.objects.filter(pk=self.pk).update(effort_points=points)

    def touch_residents(self):
        day = timezone.localtime(self.started_at).date()
        self.residents.filter(
            models.Q(last_visited_on__isnull=True) | models.Q(last_visited_on__lt=day)
        ).update(last_visited_on=day)


class ActivityPhoto(models.Model):
    activity = models.ForeignKey(
        Activity,
        verbose_name=_("Kegiatan"),
        related_name="photos",
        on_delete=models.CASCADE,
    )
    photo = PrivateFileField(
        verbose_name=_("Foto"),
        upload_to=upload_activity,
        max_length=255,
        validators=IMAGE_VALIDATORS,
    )
    caption = models.CharField(_("Keterangan"), max_length=255, blank=True, default="")
    location = gmodels.PointField(
        _("Lokasi foto (geotag)"), srid=4326, null=True, blank=True
    )
    hunting_finding = models.ForeignKey(
        "operasi.HuntingParkFinding",
        verbose_name=_("Bukti temuan patroli"),
        related_name="photos",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    uploaded_at = models.DateTimeField(_("Diunggah"), auto_now_add=True)

    class Meta:
        verbose_name = _("Foto kegiatan")
        verbose_name_plural = _("Foto kegiatan")
        ordering = ["pk"]

    def __str__(self):
        return self.caption or self.photo.name.rsplit("/", 1)[-1]


class ActivityWeight(models.Model):
    """Poin kegiatan pada KPI per jenis (bobot USAHA ala pusat komando).

    Kosong/tidak diisi = setiap kegiatan bernilai 1. Izinkan nilai lebih
    tinggi untuk kegiatan berat (mis. patroli kawasan, temuan lapangan).
    """

    activity_type = models.CharField(
        _("Jenis kegiatan"),
        max_length=16,
        choices=enums.ActivityType.choices,
        unique=True,
    )
    points = models.PositiveSmallIntegerField(
        _("Poin per kegiatan"), default=1, validators=[MaxValueValidator(20)]
    )

    class Meta:
        verbose_name = _("Bobot kegiatan (KPI)")
        verbose_name_plural = _("Bobot kegiatan (KPI)")
        ordering = ["activity_type"]

    def __str__(self):
        return f"{self.get_activity_type_display()}: {self.points}"

    @classmethod
    def points_map(cls) -> dict[str, int]:
        return dict(cls.objects.values_list("activity_type", "points"))


# --------------------------------------------------------------------------
# Temuan ilegal & patroli Taman Buru
# --------------------------------------------------------------------------


class IllegalFinding(TimeStampedModel):
    """Profil temuan aktivitas ilegal (tetap); tiap kunjungan dicatat sebagai kegiatan."""

    number = models.CharField(_("Nomor"), max_length=32, unique=True, editable=False)
    korwil = _korwil_field("illegal_findings")
    activity_kind = models.CharField(
        _("Aktivitas"),
        max_length=16,
        choices=enums.IllegalActivityKind.choices,
        default=enums.IllegalActivityKind.OTHER,
    )
    location_name = models.CharField(
        _("Lokasi"), max_length=255, help_text=_("Mis. Hutan Pos 500, Sembulang.")
    )
    location = gmodels.PointField(_("Titik temuan"), srid=4326, null=True, blank=True)
    owner_name = models.CharField(_("Pemilik"), max_length=255, blank=True, default="")
    owner_phone = models.CharField(
        _("No. HP pemilik"), max_length=32, blank=True, default=""
    )
    owner_domicile = models.CharField(
        _("Domisili pemilik"), max_length=255, blank=True, default=""
    )
    manager_name = models.CharField(
        _("Pengurus"), max_length=255, blank=True, default=""
    )
    manager_phone = models.CharField(
        _("No. HP pengurus"), max_length=32, blank=True, default=""
    )
    area_ha = models.DecimalField(
        _("Luas lahan (ha)"),
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    forest_status = models.CharField(
        _("Status hutan"),
        max_length=128,
        blank=True,
        default="",
        help_text=_("Mis. Hutan Produksi / kawasan APL."),
    )
    business_started = models.CharField(
        _("Mulai usaha berjalan"), max_length=128, blank=True, default=""
    )
    created_by = _user_field(_("Dicatat oleh"))
    note = models.TextField(_("Catatan"), blank=True, default="")

    class Meta:
        verbose_name = _("Temuan ilegal")
        verbose_name_plural = _("Temuan ilegal")
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.number} {self.get_activity_kind_display()} – {self.location_name}"
        )

    def save(self, *args, **kwargs):
        from operasi import geo

        if not self.number:
            self.number = next_number("TIL")
        if self.korwil_id is None and not getattr(self, "_korwil_resolved", False):
            self.korwil = geo.korwil_for(self.location, self.created_by)
        super().save(*args, **kwargs)


class IllegalFindingVisit(models.Model):
    """Data satu kunjungan ke lokasi temuan ilegal (bagian dari laporan kegiatan)."""

    activity = models.OneToOneField(
        Activity,
        verbose_name=_("Kegiatan"),
        related_name="illegal_visit",
        on_delete=models.CASCADE,
    )
    finding = models.ForeignKey(
        IllegalFinding,
        verbose_name=_("Temuan"),
        related_name="visits",
        on_delete=models.CASCADE,
    )
    is_new = models.BooleanField(
        _("Temuan baru"), default=True, help_text=_("Tidak dicentang = berulang.")
    )
    permit = models.CharField(
        _("Izin usaha"),
        max_length=8,
        choices=enums.PermitStatus.choices,
        blank=True,
        default="",
    )
    business_activity = models.CharField(
        _("Kegiatan usaha"),
        max_length=8,
        choices=enums.BusinessActivity.choices,
        blank=True,
        default="",
    )
    persons_involved = models.TextField(
        _("Oknum yang terlibat"), blank=True, default=""
    )
    equipment = models.TextField(_("Peralatan usaha"), blank=True, default="")
    buildings = models.TextField(_("Bangunan"), blank=True, default="")
    follow_up = models.TextField(_("Tindak lanjut"), blank=True, default="")

    class Meta:
        verbose_name = _("Kunjungan temuan ilegal")
        verbose_name_plural = _("Kunjungan temuan ilegal")
        ordering = ["-activity__started_at"]

    def __str__(self):
        return f"{self.finding.number} – {self.activity.number}"

    @property
    def filled_count(self) -> int:
        return sum(
            1
            for value in (
                self.permit,
                self.business_activity,
                self.persons_involved,
                self.equipment,
                self.buildings,
                self.follow_up,
            )
            if str(value).strip()
        )


class HuntingParkPatrol(models.Model):
    """Laporan patroli Taman Buru (rute, temuan, bibit, kondisi tim)."""

    activity = models.OneToOneField(
        Activity,
        verbose_name=_("Kegiatan"),
        related_name="patrol_report",
        on_delete=models.CASCADE,
    )
    input_mode = models.CharField(
        _("Cara isi"),
        max_length=8,
        choices=enums.PatrolInput.choices,
        default=enums.PatrolInput.MANUAL,
    )
    grid = models.CharField(
        _("Nomor grid"),
        max_length=255,
        blank=True,
        default="",
        help_text=_("Mis. TBPR29, TBPR65."),
    )
    routes = ArrayField(
        models.CharField(max_length=16, choices=enums.PatrolRoute.choices),
        verbose_name=_("Cakupan patroli"),
        default=list,
        blank=True,
    )
    objective = models.CharField(
        _("Objektif patroli"), max_length=255, blank=True, default=""
    )
    team_leader = models.CharField(
        _("Ketua tim"), max_length=255, blank=True, default=""
    )
    team = models.CharField(_("Tim / regu"), max_length=255, blank=True, default="")
    station = models.CharField(
        _("Stasiun / pos"), max_length=255, blank=True, default=""
    )
    transport = models.CharField(
        _("Transportasi"), max_length=128, blank=True, default=""
    )
    patrol_started_at = models.DateTimeField(_("Waktu mulai"), null=True, blank=True)
    patrol_ended_at = models.DateTimeField(_("Waktu selesai"), null=True, blank=True)
    situation = models.CharField(
        _("Situasi"),
        max_length=16,
        choices=enums.PatrolSituation.choices,
        blank=True,
        default="",
    )
    personnel_condition = models.CharField(
        _("Kondisi personil"),
        max_length=8,
        choices=enums.PersonnelCondition.choices,
        blank=True,
        default="",
    )
    materiel_condition = models.CharField(
        _("Kondisi materiil"),
        max_length=8,
        choices=enums.MaterielCondition.choices,
        blank=True,
        default="",
    )
    weather_morning = models.CharField(
        _("Cuaca pagi"),
        max_length=8,
        choices=enums.Weather.choices,
        blank=True,
        default="",
    )
    weather_noon = models.CharField(
        _("Cuaca siang"),
        max_length=8,
        choices=enums.Weather.choices,
        blank=True,
        default="",
    )
    weather_afternoon = models.CharField(
        _("Cuaca sore"),
        max_length=8,
        choices=enums.Weather.choices,
        blank=True,
        default="",
    )
    obstacles = models.TextField(_("Kendala / hambatan"), blank=True, default="")
    suggestions = models.TextField(_("Saran"), blank=True, default="")

    class Meta:
        verbose_name = _("Laporan patroli Taman Buru")
        verbose_name_plural = _("Laporan patroli Taman Buru")
        ordering = ["-activity__started_at"]

    def __str__(self):
        return f"{self.activity.number} {self.activity.location_name}"

    def seedling_total(self, kind: str) -> int:
        return sum(s.quantity or 0 for s in self.seedlings.all() if s.kind == kind)


class HuntingParkFinding(models.Model):
    patrol = models.ForeignKey(
        HuntingParkPatrol,
        verbose_name=_("Patroli"),
        related_name="findings",
        on_delete=models.CASCADE,
    )
    category = models.CharField(
        _("Kategori"),
        max_length=16,
        choices=enums.FindingCategory.choices,
        default=enums.FindingCategory.OTHER,
    )
    description = models.CharField(_("Deskripsi"), max_length=500)
    quantity = models.PositiveIntegerField(_("Jumlah"), null=True, blank=True)
    forest_status = models.CharField(
        _("Status hutan"), max_length=128, blank=True, default=""
    )
    new_activity = models.BooleanField(
        _("Aktivitas baru"), null=True, blank=True, help_text=_("Ada / tidak ada.")
    )
    note = models.CharField(_("Keterangan"), max_length=500, blank=True, default="")
    location = gmodels.PointField(_("Titik temuan"), srid=4326, null=True, blank=True)

    class Meta:
        verbose_name = _("Temuan patroli")
        verbose_name_plural = _("Temuan patroli")
        ordering = ["pk"]

    def __str__(self):
        return f"{self.get_category_display()}: {self.description[:60]}"


class Seedling(models.Model):
    patrol = models.ForeignKey(
        HuntingParkPatrol,
        verbose_name=_("Patroli"),
        related_name="seedlings",
        on_delete=models.CASCADE,
    )
    kind = models.CharField(
        _("Jenis catatan"), max_length=16, choices=enums.SeedlingKind.choices
    )
    species = models.CharField(_("Jenis bibit"), max_length=128)
    quantity = models.PositiveIntegerField(_("Jumlah bibit"))

    class Meta:
        verbose_name = _("Bibit Taman Buru")
        verbose_name_plural = _("Bibit Taman Buru")
        ordering = ["kind", "pk"]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.species} ({self.quantity})"


class PatrolSession(TimeStampedModel):
    """Jejak patroli hasil impor ekspor SMART Mobile / CyberTracker (GeoJSON)."""

    number = models.CharField(_("Nomor"), max_length=32, unique=True, editable=False)
    activity = models.ForeignKey(
        Activity,
        verbose_name=_("Laporan kegiatan"),
        related_name="patrol_sessions",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    korwil = _korwil_field("patrol_sessions")
    smart_patrol_id = models.CharField(
        _("ID patroli SMART"), max_length=128, blank=True, default=""
    )
    name = models.CharField(_("Nama / objektif"), max_length=255)
    started_at = models.DateTimeField(_("Mulai"), null=True, blank=True)
    ended_at = models.DateTimeField(_("Selesai"), null=True, blank=True)
    leader = models.CharField(_("Ketua tim"), max_length=255, blank=True, default="")
    team = models.CharField(_("Tim"), max_length=255, blank=True, default="")
    station = models.CharField(_("Stasiun"), max_length=255, blank=True, default="")
    transport = models.CharField(
        _("Transportasi"), max_length=128, blank=True, default=""
    )
    comments = models.TextField(_("Catatan patroli"), blank=True, default="")
    distance_m = models.PositiveIntegerField(_("Jarak tempuh (m)"), default=0)
    track = gmodels.LineStringField(_("Jalur"), srid=4326, null=True, blank=True)
    source_name = models.CharField(
        _("Nama berkas"), max_length=255, blank=True, default=""
    )
    uploaded_by = _user_field(_("Diunggah oleh"))

    class Meta:
        verbose_name = _("Jejak patroli SMART")
        verbose_name_plural = _("Jejak patroli SMART")
        ordering = ["-started_at", "-pk"]

    def __str__(self):
        return f"{self.number} {self.name}"

    def save(self, *args, **kwargs):
        from operasi import geo

        if not self.number:
            self.number = next_number("PTR")
        if self.korwil_id is None and not getattr(self, "_korwil_resolved", False):
            start = Point(*self.track.coords[0], srid=4326) if self.track else None
            self.korwil = geo.korwil_for(start, self.uploaded_by)
        super().save(*args, **kwargs)


class PatrolObservation(models.Model):
    session = models.ForeignKey(
        PatrolSession,
        verbose_name=_("Patroli"),
        related_name="observations",
        on_delete=models.CASCADE,
    )
    seq = models.PositiveIntegerField(_("Urutan"))
    kind = models.CharField(_("Tipe"), max_length=64, default="Observation")
    location = gmodels.PointField(_("Lokasi"), srid=4326)
    observed_at = models.DateTimeField(_("Waktu"), null=True, blank=True)
    comment = models.TextField(_("Catatan"), blank=True, default="")
    leg_distance_m = models.DecimalField(
        _("Jarak dari titik sebelumnya (m)"),
        max_digits=10,
        decimal_places=1,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("Observasi patroli")
        verbose_name_plural = _("Observasi patroli")
        ordering = ["session", "seq"]

    def __str__(self):
        return f"{self.session.number} #{self.seq} {self.kind}"


class PatrolPhoto(models.Model):
    observation = models.ForeignKey(
        PatrolObservation,
        verbose_name=_("Observasi"),
        related_name="photos",
        on_delete=models.CASCADE,
    )
    photo = PrivateFileField(
        verbose_name=_("Foto"),
        upload_to=upload_patrol,
        max_length=255,
        validators=IMAGE_VALIDATORS,
    )

    class Meta:
        verbose_name = _("Foto observasi patroli")
        verbose_name_plural = _("Foto observasi patroli")
        ordering = ["pk"]

    def __str__(self):
        return self.photo.name.rsplit("/", 1)[-1]


class SoilTest(TimeStampedModel):
    number = models.CharField(_("Nomor"), max_length=32, unique=True, editable=False)
    client_id = models.UUIDField(
        _("ID perangkat"), unique=True, default=uuid.uuid4, editable=False
    )
    korwil = _korwil_field("soil_tests")
    location = gmodels.PointField(_("Titik sampel"), srid=4326)
    sampled_at = models.DateTimeField(_("Waktu pengambilan"), default=timezone.now)
    sampled_by = _user_field(_("Petugas"))
    depth_cm = models.PositiveIntegerField(_("Kedalaman (cm)"), null=True, blank=True)
    texture = models.CharField(
        _("Jenis / tekstur tanah"),
        max_length=16,
        choices=enums.SoilTexture.choices,
        blank=True,
        default="",
    )
    color = models.CharField(_("Warna tanah"), max_length=64, blank=True, default="")
    ph = models.DecimalField(
        _("pH"),
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(14)],
    )
    moisture_pct = models.DecimalField(
        _("Kadar air (%)"),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    organic_c_pct = models.DecimalField(
        _("C-organik (%)"),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    bearing_capacity_kpa = models.DecimalField(
        _("Daya dukung tanah (kPa)"),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    cbr_pct = models.DecimalField(
        _("CBR (%)"),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    suitability = models.CharField(
        _("Kelayakan"),
        max_length=16,
        choices=enums.SoilSuitability.choices,
        default=enums.SoilSuitability.PENDING,
    )
    lab_name = models.CharField(
        _("Laboratorium"), max_length=255, blank=True, default=""
    )
    lab_report = PrivateFileField(
        verbose_name=_("Laporan laboratorium"),
        upload_to=upload_soil,
        max_length=255,
        blank=True,
        validators=DOCUMENT_VALIDATORS,
    )
    photo = PrivateFileField(
        verbose_name=_("Foto sampel"),
        upload_to=upload_soil,
        max_length=255,
        blank=True,
        validators=IMAGE_VALIDATORS,
    )
    note = models.TextField(_("Catatan"), blank=True, default="")

    class Meta:
        verbose_name = _("Uji tanah")
        verbose_name_plural = _("Uji tanah")
        ordering = ["-sampled_at"]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        from operasi import geo

        if not self.number:
            self.number = next_number("UJT")
        if self.korwil_id is None and not getattr(self, "_korwil_resolved", False):
            self.korwil = geo.korwil_for(self.location, self.sampled_by)
        super().save(*args, **kwargs)


# --------------------------------------------------------------------------
# Absensi
# --------------------------------------------------------------------------


class Attendance(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Petugas"),
        related_name="operasi_attendances",
        on_delete=models.CASCADE,
    )
    date = models.DateField(_("Tanggal"))
    korwil = _korwil_field("attendances")
    status = models.CharField(
        _("Status"),
        max_length=16,
        choices=enums.AttendanceStatus.choices,
        default=enums.AttendanceStatus.PRESENT,
    )
    check_in_at = models.DateTimeField(_("Absen masuk"), null=True, blank=True)
    check_in_location = gmodels.PointField(
        _("Lokasi masuk"), srid=4326, null=True, blank=True
    )
    check_in_accuracy_m = models.DecimalField(
        _("Akurasi masuk (m)"), max_digits=8, decimal_places=1, null=True, blank=True
    )
    check_in_in_area = models.BooleanField(_("Masuk di wilayah"), null=True, blank=True)
    check_in_photo = PrivateFileField(
        verbose_name=_("Swafoto masuk"),
        upload_to=upload_attendance,
        max_length=255,
        blank=True,
        validators=IMAGE_VALIDATORS,
    )
    check_out_at = models.DateTimeField(_("Absen pulang"), null=True, blank=True)
    check_out_location = gmodels.PointField(
        _("Lokasi pulang"), srid=4326, null=True, blank=True
    )
    check_out_accuracy_m = models.DecimalField(
        _("Akurasi pulang (m)"), max_digits=8, decimal_places=1, null=True, blank=True
    )
    check_out_in_area = models.BooleanField(
        _("Pulang di wilayah"), null=True, blank=True
    )
    check_out_photo = PrivateFileField(
        verbose_name=_("Swafoto pulang"),
        upload_to=upload_attendance,
        max_length=255,
        blank=True,
        validators=IMAGE_VALIDATORS,
    )
    missing_checkout = models.BooleanField(_("Lupa absen pulang"), default=False)
    approval = models.CharField(
        _("Persetujuan izin"),
        max_length=16,
        choices=enums.LeaveApproval.choices,
        blank=True,
        default="",
        help_text=_(
            "Izin, sakit, cuti, dan dinas luar baru dihitung pada kinerja setelah "
            "disetujui koordinator Korwil atau Administrator."
        ),
    )
    approved_by = _user_field(_("Diputuskan oleh"))
    approved_at = models.DateTimeField(_("Diputuskan pada"), null=True, blank=True)
    note = models.TextField(_("Keterangan"), blank=True, default="")
    attachment = PrivateFileField(
        verbose_name=_("Lampiran (surat izin / sakit)"),
        upload_to=upload_attendance,
        max_length=255,
        blank=True,
        validators=DOCUMENT_VALIDATORS,
    )

    class Meta:
        verbose_name = _("Absensi")
        verbose_name_plural = _("Absensi")
        ordering = ["-date", "user"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"], name="operasi_one_attendance_per_day"
            )
        ]

    def __str__(self):
        return f"{self.user} {self.date:%d-%m-%Y}"

    @property
    def is_approved(self) -> bool:
        return self.approval == enums.LeaveApproval.APPROVED

    @property
    def status_text(self) -> str:
        """Status beserta keadaan persetujuan izin (mis. "Cuti (menunggu persetujuan)")."""
        label = str(self.get_status_display())
        if self.status in enums.ABSENCE_STATUSES and self.approval in (
            enums.LeaveApproval.PENDING,
            enums.LeaveApproval.REJECTED,
        ):
            return f"{label} ({str(self.get_approval_display()).lower()})"
        return label

    @property
    def worked_minutes(self) -> int | None:
        if self.check_in_at and self.check_out_at:
            return max(
                int((self.check_out_at - self.check_in_at).total_seconds() // 60), 0
            )
        return None


# --------------------------------------------------------------------------
# Komunikasi, darurat & posisi
# --------------------------------------------------------------------------


class ChatMessage(models.Model):
    korwil = models.ForeignKey(
        "operasi.Korwil",
        verbose_name=_("Kanal Korwil"),
        related_name="messages",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text=_("Kosong = kanal umum seluruh pusat komando."),
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Pengirim"),
        related_name="operasi_messages",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    body = models.TextField(_("Pesan"), max_length=2000)
    location = gmodels.PointField(
        _("Lokasi dibagikan"), srid=4326, null=True, blank=True
    )
    is_system = models.BooleanField(_("Pesan sistem"), default=False)
    created_at = models.DateTimeField(_("Dikirim"), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Pesan chat internal")
        verbose_name_plural = _("Chat internal")
        ordering = ["pk"]

    def __str__(self):
        return f"{self.sender or _('Sistem')}: {self.body[:40]}"


class SosAlert(TimeStampedModel):
    number = models.CharField(_("Nomor"), max_length=32, unique=True, editable=False)
    client_id = models.UUIDField(
        _("ID perangkat"), unique=True, default=uuid.uuid4, editable=False
    )
    raised_by = _user_field(_("Petugas"), related_name="operasi_sos")
    korwil = _korwil_field("sos_alerts")
    location = gmodels.PointField(_("Lokasi"), srid=4326, null=True, blank=True)
    accuracy_m = models.DecimalField(
        _("Akurasi GPS (m)"), max_digits=8, decimal_places=1, null=True, blank=True
    )
    message = models.TextField(_("Pesan"), blank=True, default="")
    status = models.CharField(
        _("Status"),
        max_length=16,
        choices=enums.SosStatus.choices,
        default=enums.SosStatus.ACTIVE,
    )
    acknowledged_by = _user_field(_("Ditangani oleh"))
    acknowledged_at = models.DateTimeField(_("Ditangani pada"), null=True, blank=True)
    resolved_by = _user_field(_("Diselesaikan oleh"))
    resolved_at = models.DateTimeField(_("Diselesaikan pada"), null=True, blank=True)
    resolution_note = models.TextField(_("Catatan penanganan"), blank=True, default="")

    class Meta:
        verbose_name = _("Tanda darurat (SOS)")
        verbose_name_plural = _("Tanda darurat (SOS)")
        ordering = ["-created_at"]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        from operasi import geo

        if not self.number:
            self.number = next_number("SOS")
        if self.korwil_id is None and not getattr(self, "_korwil_resolved", False):
            self.korwil = geo.korwil_for(self.location, self.raised_by)
        super().save(*args, **kwargs)

    @property
    def is_open(self) -> bool:
        return self.status in enums.OPEN_SOS_STATUSES


class OfficerPosition(models.Model):
    """Lokasi terakhir petugas yang menyalakan mode Live."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Petugas"),
        related_name="operasi_position",
        on_delete=models.CASCADE,
    )
    location = gmodels.PointField(_("Lokasi"), srid=4326)
    accuracy_m = models.DecimalField(
        _("Akurasi (m)"), max_digits=8, decimal_places=1, null=True, blank=True
    )
    heading = models.DecimalField(
        _("Arah (derajat)"), max_digits=5, decimal_places=1, null=True, blank=True
    )
    speed_mps = models.DecimalField(
        _("Kecepatan (m/detik)"), max_digits=6, decimal_places=2, null=True, blank=True
    )
    battery_pct = models.PositiveSmallIntegerField(
        _("Baterai (%)"), null=True, blank=True, validators=[MaxValueValidator(100)]
    )
    updated_at = models.DateTimeField(_("Diperbarui"), db_index=True)

    class Meta:
        verbose_name = _("Posisi petugas (Live)")
        verbose_name_plural = _("Posisi petugas (Live)")
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user} {self.updated_at:%d-%m-%Y %H:%M}"


class AreaAnalysis(models.Model):
    """Riwayat analisis AI Satelit atas kotak area yang digambar di peta."""

    bbox = gmodels.PolygonField(_("Area"), srid=4326)
    requested_by = _user_field(_("Diminta oleh"))
    created_at = models.DateTimeField(_("Waktu"), auto_now_add=True)
    zoom = models.PositiveSmallIntegerField(_("Level zoom citra"), default=17)
    image = PrivateFileField(
        verbose_name=_("Mosaik citra"),
        upload_to=upload_analysis,
        max_length=255,
        blank=True,
    )
    data_summary = models.JSONField(_("Ringkasan data"), default=dict, blank=True)
    ai_result = models.JSONField(_("Hasil AI"), default=dict, blank=True)
    ai_model = models.CharField(_("Model AI"), max_length=64, blank=True, default="")
    error = models.CharField(_("Catatan galat"), max_length=255, blank=True, default="")

    class Meta:
        verbose_name = _("Analisis AI Satelit")
        verbose_name_plural = _("Analisis AI Satelit")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{_('Analisis')} #{self.pk} {self.created_at:%d-%m-%Y %H:%M}"


# --------------------------------------------------------------------------
# Struktur atasan, siklus tugas, laporan harian berjenjang
# --------------------------------------------------------------------------


class OfficerProfile(models.Model):
    """Jabatan dan atasan langsung petugas di pusat komando.

    Atasan menentukan ke mana laporan harian dikirim dan siapa yang boleh
    memberi tugas. Tanpa atasan yang diatur, atasan petugas Korwil adalah
    koordinator Korwil-nya.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Petugas"),
        related_name="komando_profile",
        on_delete=models.CASCADE,
    )
    position = models.CharField(
        _("Jabatan"),
        max_length=128,
        blank=True,
        default="",
        help_text=_("Mis. Koordinator Korwil A, Staf manajemen, Penyelia, Pimpinan."),
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Atasan langsung"),
        related_name="komando_subordinate_profiles",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text=_(
            "Kosong = koordinator Korwil tempat petugas bertugas. Pimpinan "
            "tertinggi tidak punya atasan."
        ),
    )

    class Meta:
        verbose_name = _("Jabatan & atasan petugas")
        verbose_name_plural = _("Jabatan & atasan petugas")
        ordering = ["user__first_name", "user__username"]

    def __str__(self):
        return f"{self.user} – {self.position or _('tanpa jabatan')}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.supervisor_id:
            return
        if self.supervisor_id == self.user_id:
            raise ValidationError(
                {"supervisor": _("Petugas tidak boleh menjadi atasan dirinya sendiri.")}
            )
        seen = {self.user_id}
        current = self.supervisor_id
        for _step in range(50):
            if current in seen:
                raise ValidationError(
                    {"supervisor": _("Rantai atasan tidak boleh melingkar.")}
                )
            seen.add(current)
            current = (
                OfficerProfile.objects.filter(user_id=current)
                .values_list("supervisor_id", flat=True)
                .first()
            )
            if not current:
                return


class TaskEvent(models.Model):
    """Riwayat siklus tugas komando: penugasan, laporan, verifikasi, revisi."""

    task = models.ForeignKey(
        "asetlahan.Task",
        verbose_name=_("Tugas"),
        related_name="komando_events",
        on_delete=models.CASCADE,
    )
    kind = models.CharField(
        _("Peristiwa"), max_length=16, choices=enums.TaskEventKind.choices
    )
    actor = _user_field(_("Oleh"))
    note = models.TextField(_("Catatan"), blank=True, default="")
    photo = PrivateFileField(
        verbose_name=_("Foto bukti"),
        upload_to=upload_task,
        max_length=255,
        blank=True,
        validators=IMAGE_VALIDATORS,
    )
    location = gmodels.PointField(_("Lokasi"), srid=4326, null=True, blank=True)
    created_at = models.DateTimeField(_("Waktu"), default=timezone.now)

    class Meta:
        verbose_name = _("Riwayat tugas")
        verbose_name_plural = _("Riwayat tugas")
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.task} – {self.get_kind_display()}"


class TaskPoint(models.Model):
    """Poin KPI dari tugas yang diverifikasi selesai."""

    task = models.ForeignKey(
        "asetlahan.Task",
        verbose_name=_("Tugas"),
        related_name="komando_points",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Petugas"),
        related_name="komando_task_points",
        on_delete=models.CASCADE,
    )
    role = models.CharField(
        _("Peran"), max_length=16, choices=enums.TaskPointRole.choices
    )
    points = models.PositiveSmallIntegerField(_("Poin"))
    awarded_at = models.DateTimeField(_("Diberikan pada"), default=timezone.now)

    class Meta:
        verbose_name = _("Poin tugas")
        verbose_name_plural = _("Poin tugas")
        ordering = ["-awarded_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["task", "user"], name="operasi_taskpoint_unique_user"
            )
        ]

    def __str__(self):
        return f"{self.user} +{self.points} ({self.task})"


class DailyReport(TimeStampedModel):
    """Laporan harian yang naik berjenjang dari petugas ke atasan langsung.

    Atasan merangkum laporan masuk (dan kegiatannya sendiri) menjadi laporan
    baru untuk atasannya; laporan sumber lalu tercatat ``diteruskan``.
    Laporan bisa dikembalikan untuk revisi dan diteruskan ke bawahan
    (``revision_stack`` mencatat ke mana laporan kembali setelah diperbaiki).
    """

    number = models.CharField(_("Nomor"), max_length=32, unique=True, editable=False)
    report_date = models.DateField(_("Tanggal laporan"), default=timezone.localdate)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Pembuat"),
        related_name="komando_daily_reports",
        on_delete=models.PROTECT,
    )
    author_position = models.CharField(
        _("Jabatan pembuat"), max_length=128, blank=True, default=""
    )
    recipient = _user_field(_("Dikirim kepada"), related_name="komando_report_inbox")
    korwil = _korwil_field("daily_reports")
    content = models.TextField(_("Isi laporan"))
    ai_generated = models.BooleanField(_("Disusun dengan AI"), default=False)
    status = models.CharField(
        _("Status"),
        max_length=16,
        choices=enums.DailyReportStatus.choices,
        default=enums.DailyReportStatus.SENT,
    )
    consolidated_into = models.ForeignKey(
        "self",
        verbose_name=_("Dirangkum ke laporan"),
        related_name="sources",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    revision_owner = _user_field(
        _("Menunggu revisi oleh"), related_name="komando_report_revisions"
    )
    revision_stack = ArrayField(
        models.PositiveIntegerField(),
        verbose_name=_("Rantai pengembalian"),
        default=list,
        blank=True,
    )
    return_note = models.TextField(_("Catatan revisi"), blank=True, default="")
    returned_by = _user_field(_("Dikembalikan oleh"))
    returned_at = models.DateTimeField(_("Dikembalikan pada"), null=True, blank=True)
    sent_at = models.DateTimeField(_("Dikirim pada"), default=timezone.now)
    reviewed_by = _user_field(_("Ditinjau oleh"))
    reviewed_at = models.DateTimeField(_("Ditinjau pada"), null=True, blank=True)

    class Meta:
        verbose_name = _("Laporan harian berjenjang")
        verbose_name_plural = _("Laporan harian berjenjang")
        ordering = ["-sent_at", "-pk"]

    def __str__(self):
        return f"{self.number} {self.author} {self.report_date:%d-%m-%Y}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_number("LHR")
        super().save(*args, **kwargs)

    @property
    def in_inbox(self) -> bool:
        return (
            self.status == enums.DailyReportStatus.SENT
            and self.consolidated_into_id is None
        )


class DailyReportEvent(models.Model):
    report = models.ForeignKey(
        DailyReport,
        verbose_name=_("Laporan"),
        related_name="events",
        on_delete=models.CASCADE,
    )
    action = models.CharField(
        _("Tindakan"), max_length=20, choices=enums.DailyReportAction.choices
    )
    actor = _user_field(_("Oleh"))
    target = _user_field(_("Kepada"))
    note = models.TextField(_("Catatan"), blank=True, default="")
    created_at = models.DateTimeField(_("Waktu"), default=timezone.now)

    class Meta:
        verbose_name = _("Riwayat laporan harian")
        verbose_name_plural = _("Riwayat laporan harian")
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.report} – {self.get_action_display()}"


class DailyReportAttachment(models.Model):
    report = models.ForeignKey(
        DailyReport,
        verbose_name=_("Laporan"),
        related_name="attachments",
        on_delete=models.CASCADE,
    )
    file = PrivateFileField(
        verbose_name=_("Berkas"),
        upload_to=upload_daily_report,
        max_length=255,
        validators=DOCUMENT_VALIDATORS,
    )
    name = models.CharField(_("Nama berkas"), max_length=255, blank=True, default="")
    uploaded_by = _user_field(_("Diunggah oleh"))
    uploaded_at = models.DateTimeField(_("Diunggah pada"), default=timezone.now)

    class Meta:
        verbose_name = _("Lampiran laporan harian")
        verbose_name_plural = _("Lampiran laporan harian")
        ordering = ["uploaded_at", "pk"]

    def __str__(self):
        return self.name or str(self.pk)


for _model in (
    CommandSettings,
    Korwil,
    Activity,
    ActivityPhoto,
    IllegalFindingVisit,
    HuntingParkPatrol,
    HuntingParkFinding,
    Seedling,
    PatrolSession,
    SoilTest,
    Attendance,
    SosAlert,
    OfficerProfile,
    TaskPoint,
    DailyReport,
):
    auditlog.register(_model)

# Kode rahasia & data pribadi tidak boleh tersimpan apa adanya di log audit.
auditlog.register(SystemLock, exclude_fields=["passcode_hash"])
auditlog.register(IllegalFinding, mask_fields=["owner_phone", "manager_phone"])
auditlog.register(
    Resident,
    exclude_fields=["nik_fingerprint"],
    mask_fields=["nik", "family_card_number"],
)
