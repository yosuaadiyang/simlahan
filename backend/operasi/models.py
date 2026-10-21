"""Model pusat komando operasi lapangan.

Wilayah kerja dibagi per Korwil (koordinator wilayah). Di tiap Korwil petugas
mendata warga (sikap, status lahan, kesesuaian RTRW), melaporkan kegiatan,
mengambil sampel uji tanah, absen dengan GPS, menerima tugas, saling
berkirim pesan, dan dapat mengirim tanda darurat (SOS). Data warga dapat
dihubungkan ke modul pengadaan tanah dan bank tanah agar tidak dicatat dua kali.
"""

import datetime
import uuid

from auditlog.registry import auditlog
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.gis.db import models as gmodels
from django.core.cache import cache
from django.core.validators import MaxValueValidator, MinValueValidator
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
    description = models.TextField(_("Uraian"), blank=True, default="")
    started_at = models.DateTimeField(_("Waktu kegiatan"), default=timezone.now)
    duration_minutes = models.PositiveIntegerField(
        _("Durasi (menit)"), null=True, blank=True
    )
    location = gmodels.PointField(_("Lokasi GPS"), srid=4326, null=True, blank=True)
    accuracy_m = models.DecimalField(
        _("Akurasi GPS (m)"), max_digits=8, decimal_places=1, null=True, blank=True
    )
    participants_count = models.PositiveIntegerField(
        _("Jumlah warga hadir / ditemui"), null=True, blank=True
    )
    outcome = models.TextField(_("Hasil & tindak lanjut"), blank=True, default="")
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
    uploaded_at = models.DateTimeField(_("Diunggah"), auto_now_add=True)

    class Meta:
        verbose_name = _("Foto kegiatan")
        verbose_name_plural = _("Foto kegiatan")
        ordering = ["pk"]

    def __str__(self):
        return self.caption or self.photo.name.rsplit("/", 1)[-1]


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


for _model in (
    CommandSettings,
    Korwil,
    Activity,
    ActivityPhoto,
    SoilTest,
    Attendance,
    SosAlert,
):
    auditlog.register(_model)

# Kode rahasia & data pribadi tidak boleh tersimpan apa adanya di log audit.
auditlog.register(SystemLock, exclude_fields=["passcode_hash"])
auditlog.register(
    Resident,
    exclude_fields=["nik_fingerprint"],
    mask_fields=["nik", "family_card_number"],
)
