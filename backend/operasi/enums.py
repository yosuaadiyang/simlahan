"""Pilihan (choices) modul pusat komando operasi lapangan."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from asetlahan.enums import Stance

__all__ = ["Stance"]

STANCE_COLORS = {
    Stance.SUPPORT: "#1a7f37",
    Stance.NEUTRAL: "#bf8700",
    Stance.OPPOSE: "#cf222e",
    Stance.UNKNOWN: "#8c959f",
}


class LandStatus(models.TextChoices):
    PENDING = "belum", _("Lahan belum dibebaskan")
    RELEASED = "sudah", _("Lahan sudah dibebaskan")


LAND_STATUS_COLORS = {LandStatus.PENDING: "#d1242f", LandStatus.RELEASED: "#0969da"}


class RtrwStatus(models.TextChoices):
    CONFORM = "sesuai", _("Sesuai RTRW")
    NONCONFORM = "tidak", _("Tidak sesuai RTRW")
    UNASSESSED = "belum", _("Belum dinilai")


RTRW_COLORS = {
    RtrwStatus.CONFORM: "#1a7f37",
    RtrwStatus.NONCONFORM: "#cf222e",
    RtrwStatus.UNASSESSED: "#8c959f",
}


class RelocationChoice(models.TextChoices):
    UNDECIDED = "belum", _("Belum memilih")
    RELOCATION = "relokasi", _("Relokasi / hunian baru")
    COMPENSATION = "uang", _("Ganti kerugian uang")
    SHIFT = "geser", _("Pergeseran dalam kampung")
    OTHER = "lainnya", _("Lainnya")


class ActivityType(models.TextChoices):
    SOCIALIZATION = "sosialisasi", _("Sosialisasi")
    CENSUS = "pendataan", _("Pendataan warga")
    VISIT = "kunjungan", _("Kunjungan / pendekatan warga")
    VERIFICATION = "verifikasi", _("Verifikasi data")
    MEASUREMENT = "pengukuran", _("Pengukuran / pematokan")
    SOIL = "uji_tanah", _("Uji tanah")
    PATROL = "patroli", _("Patroli")
    MEDIATION = "mediasi", _("Mediasi / musyawarah")
    MEETING = "rapat", _("Rapat koordinasi")
    ASSISTANCE = "pendampingan", _("Pendampingan relokasi")
    OTHER = "lainnya", _("Lainnya")


ACTIVITY_COLORS = {
    ActivityType.SOCIALIZATION: "#8250df",
    ActivityType.CENSUS: "#0969da",
    ActivityType.VISIT: "#1a7f37",
    ActivityType.VERIFICATION: "#0550ae",
    ActivityType.MEASUREMENT: "#953800",
    ActivityType.SOIL: "#7d4e00",
    ActivityType.PATROL: "#57606a",
    ActivityType.MEDIATION: "#bf3989",
    ActivityType.MEETING: "#6639ba",
    ActivityType.ASSISTANCE: "#116329",
    ActivityType.OTHER: "#6e7781",
}


class SoilTexture(models.TextChoices):
    CLAY = "lempung", _("Lempung")
    SILT = "lanau", _("Lanau")
    SAND = "pasir", _("Pasir")
    GRAVEL = "kerikil", _("Kerikil / batuan")
    PEAT = "gambut", _("Gambut")
    LATERITE = "laterit", _("Laterit")
    MIXED = "campuran", _("Campuran")


class SoilSuitability(models.TextChoices):
    SUITABLE = "layak", _("Layak dibangun")
    CONDITIONAL = "bersyarat", _("Layak bersyarat (perlu perbaikan)")
    UNSUITABLE = "tidak", _("Tidak layak")
    PENDING = "belum", _("Menunggu hasil lab")


SOIL_COLORS = {
    SoilSuitability.SUITABLE: "#1a7f37",
    SoilSuitability.CONDITIONAL: "#bf8700",
    SoilSuitability.UNSUITABLE: "#cf222e",
    SoilSuitability.PENDING: "#8c959f",
}


class AttendanceStatus(models.TextChoices):
    PRESENT = "hadir", _("Hadir")
    LATE = "terlambat", _("Hadir terlambat")
    PERMIT = "izin", _("Izin")
    SICK = "sakit", _("Sakit")
    LEAVE = "cuti", _("Cuti")
    DUTY = "dinas", _("Dinas luar")


PRESENT_STATUSES = [AttendanceStatus.PRESENT, AttendanceStatus.LATE]
ABSENCE_STATUSES = [
    AttendanceStatus.PERMIT,
    AttendanceStatus.SICK,
    AttendanceStatus.LEAVE,
    AttendanceStatus.DUTY,
]


class SosStatus(models.TextChoices):
    ACTIVE = "aktif", _("Aktif – butuh bantuan")
    ACKNOWLEDGED = "ditangani", _("Sedang ditangani")
    RESOLVED = "selesai", _("Selesai")
    FALSE_ALARM = "palsu", _("Alarm palsu")


OPEN_SOS_STATUSES = [SosStatus.ACTIVE, SosStatus.ACKNOWLEDGED]
