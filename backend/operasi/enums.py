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


class RtrwZone(models.TextChoices):
    """Kategori zona rencana tata ruang (drilldown per zona ala pusat komando)."""

    PROTECTED = "lindung", _("Zona Lindung")
    CULTIVATION = "budi_daya", _("Zona Budi Daya")
    SPECIAL = "khusus", _("Zona Khusus / Ditunjuk")
    OTHER = "lainnya", _("Zona lainnya")
    UNASSESSED = "belum", _("Belum diketahui")


class Gender(models.TextChoices):
    MALE = "L", _("Laki-laki")
    FEMALE = "P", _("Perempuan")
    UNKNOWN = "", _("Belum diketahui")


class CultivationStatus(models.TextChoices):
    CULTIVATED = "digarapi", _("Digarapi sendiri")
    LEASED = "disewakan", _("Disewakan / dieksploitasi pihak lain")
    IDLE = "tidak", _("Tidak digarapi")
    UNKNOWN = "", _("Belum diketahui")


class RelocationChoice(models.TextChoices):
    UNDECIDED = "belum", _("Belum memilih")
    RELOCATION = "relokasi", _("Relokasi / hunian baru")
    COMPENSATION = "uang", _("Ganti kerugian uang")
    SHIFT = "geser", _("Pergeseran dalam kampung")
    OTHER = "lainnya", _("Lainnya")


class ActivityType(models.TextChoices):
    KOMSOS = "komsos", _("Komsos (komunikasi sosial)")
    TOPOGRAPHY = "topografi", _("Topografi")
    ILLEGAL = "temuan_ilegal", _("Temuan ilegal")
    HUNTING_PARK = "taman_buru", _("Patroli Taman Buru")
    MAPPING = "pemetaan", _("Pemetaan / penguasaan lahan")
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
    OTHER = "lainnya", _("Kegiatan lainnya")


ACTIVITY_COLORS = {
    ActivityType.KOMSOS: "#0b5fcc",
    ActivityType.TOPOGRAPHY: "#9a6700",
    ActivityType.ILLEGAL: "#cf222e",
    ActivityType.HUNTING_PARK: "#116329",
    ActivityType.MAPPING: "#0a7a7a",
    ActivityType.SOCIALIZATION: "#8250df",
    ActivityType.CENSUS: "#0969da",
    ActivityType.VISIT: "#1a7f37",
    ActivityType.VERIFICATION: "#0550ae",
    ActivityType.MEASUREMENT: "#953800",
    ActivityType.SOIL: "#7d4e00",
    ActivityType.PATROL: "#57606a",
    ActivityType.MEDIATION: "#bf3989",
    ActivityType.MEETING: "#6639ba",
    ActivityType.ASSISTANCE: "#2da44e",
    ActivityType.OTHER: "#6e7781",
}

# Jenis kegiatan utama di formulir lapor pusat komando (urutan kartu pilihan).
FIELD_ACTIVITY_TYPES = [
    ActivityType.KOMSOS,
    ActivityType.TOPOGRAPHY,
    ActivityType.ILLEGAL,
    ActivityType.HUNTING_PARK,
    ActivityType.OTHER,
]

# Poin dasar USAHA per jenis bila belum diatur di "Bobot kegiatan (KPI)".
EFFORT_BASE_POINTS = {
    ActivityType.HUNTING_PARK: 10,
    ActivityType.KOMSOS: 6,
    ActivityType.MAPPING: 8,
    ActivityType.ILLEGAL: 8,
}
# Komsos dihitung per warga yang ditemui (paling banyak sekian orang per laporan).
KOMSOS_MAX_PERSONS = 10


class ScoringMode(models.TextChoices):
    EFFORT = "usaha", _("Poin usaha (bobot jenis + bonus kelengkapan laporan)")
    COUNT = "jumlah", _("Jumlah kegiatan × bobot jenis")


class ResidencyStatus(models.TextChoices):
    NATIVE = "tempatan", _("Tempatan")
    NEWCOMER = "pendatang", _("Pendatang")
    UNKNOWN = "", _("Belum diketahui")


# --- Kegiatan lainnya: tingkat dampak dari rubrik (cakupan + risiko + hasil) ---


class ImpactScope(models.IntegerChoices):
    SELF = 0, _("Diri sendiri / administratif")
    LOCAL = 1, _("Satu lokasi / kelompok kecil")
    KORWIL = 2, _("Skala Korwil / banyak warga")
    STRATEGIC = 3, _("Lintas Korwil / strategis proyek")


class ImpactRisk(models.IntegerChoices):
    LOW = 0, _("Rendah / rutin")
    MEDIUM = 1, _("Sedang")
    HIGH = 2, _("Tinggi")
    CRITICAL = 3, _("Kritis / mendesak (keselamatan, hukum, strategis)")


class ImpactResult(models.IntegerChoices):
    NONE = 0, _("Belum ada hasil terukur")
    OUTPUT = 1, _("Ada keluaran / kemajuan")
    SOLVED = 2, _("Menyelesaikan masalah / mencapai target")


class ImpactTier(models.TextChoices):
    ROUTINE = "rutin", _("Rutin")
    OPERATIONAL = "operasional", _("Operasional")
    SIGNIFICANT = "signifikan", _("Signifikan")
    CRITICAL = "kritis", _("Kritis")


IMPACT_POINTS = {
    ImpactTier.ROUTINE: 3,
    ImpactTier.OPERATIONAL: 6,
    ImpactTier.SIGNIFICANT: 9,
    ImpactTier.CRITICAL: 12,
}
# Klaim dampak tinggi dihitung sebagai Operasional sampai dikonfirmasi atasan.
HIGH_IMPACT_TIERS = [ImpactTier.SIGNIFICANT, ImpactTier.CRITICAL]


def impact_tier(score: int) -> str:
    if score <= 1:
        return ImpactTier.ROUTINE
    if score <= 3:
        return ImpactTier.OPERATIONAL
    if score <= 5:
        return ImpactTier.SIGNIFICANT
    return ImpactTier.CRITICAL


# --- Temuan ilegal ---


class IllegalActivityKind(models.TextChoices):
    LOGGING = "pembalakan", _("Pembalakan liar")
    MINING = "tambang", _("Tambang ilegal")
    ENCROACHMENT = "perambahan", _("Perambahan lahan")
    CLEARING = "pembukaan", _("Pembukaan lahan")
    BUILDING = "bangunan", _("Pembangunan liar")
    OTHER = "lainnya", _("Lainnya")


ILLEGAL_COLORS = {
    IllegalActivityKind.LOGGING: "#953800",
    IllegalActivityKind.MINING: "#6639ba",
    IllegalActivityKind.ENCROACHMENT: "#cf222e",
    IllegalActivityKind.CLEARING: "#bf8700",
    IllegalActivityKind.BUILDING: "#0550ae",
    IllegalActivityKind.OTHER: "#57606a",
}


class PermitStatus(models.TextChoices):
    YES = "ada", _("Ada")
    NO = "tidak", _("Tidak ada")
    UNKNOWN = "", _("Belum diketahui")


class BusinessActivity(models.TextChoices):
    ACTIVE = "aktif", _("Aktif")
    INACTIVE = "tidak", _("Tidak aktif")
    UNKNOWN = "", _("Belum diketahui")


# --- Patroli Taman Buru ---


class PatrolRoute(models.TextChoices):
    LOGGING_PATH = "jalur_kayu", _("Jalur pembalakan kayu")
    RAT_PATH = "jalur_tikus", _("Jalur tikus pengambilan kayu")
    POACHING = "perburuan", _("Perburuan liar")
    BURNT = "bekas_kebakaran", _("Bekas kebakaran hutan")


class PatrolInput(models.TextChoices):
    MANUAL = "manual", _("Manual")
    SMART = "smart", _("Unggah SMART")
    HYBRID = "hybrid", _("Hybrid")


class PatrolSituation(models.TextChoices):
    CONDUCIVE = "kondusif", _("Kondusif")
    ALERT = "waspada", _("Waspada")
    UNSAFE = "tidak_kondusif", _("Tidak kondusif")
    UNKNOWN = "", _("Belum diisi")


class PersonnelCondition(models.TextChoices):
    HEALTHY = "sehat", _("Sehat semua")
    SICK = "sakit", _("Ada yang sakit")
    INJURED = "cedera", _("Ada yang cedera")
    UNKNOWN = "", _("Belum diisi")


class MaterielCondition(models.TextChoices):
    SAFE = "aman", _("Aman")
    DAMAGED = "rusak", _("Ada yang rusak")
    LOST = "hilang", _("Ada yang hilang")
    UNKNOWN = "", _("Belum diisi")


class Weather(models.TextChoices):
    CLEAR = "cerah", _("Cerah")
    CLOUDY = "berawan", _("Berawan")
    RAIN = "hujan", _("Hujan")
    STORM = "badai", _("Badai")
    UNKNOWN = "", _("Belum diisi")


class FindingCategory(models.TextChoices):
    FLORA = "flora", _("Flora")
    FAUNA = "fauna", _("Fauna")
    ILLEGAL = "aktivitas_ilegal", _("Aktivitas ilegal")
    OTHER = "lainnya", _("Lainnya")


class SeedlingKind(models.TextChoices):
    TENDED = "dirawat", _("Bibit dirawat")
    PRODUCED = "diproduksi", _("Bibit diproduksi")


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


class LeaveApproval(models.TextChoices):
    """Persetujuan pengajuan izin / sakit / cuti / dinas luar oleh koordinator."""

    PENDING = "menunggu", _("Menunggu persetujuan")
    APPROVED = "disetujui", _("Disetujui")
    REJECTED = "ditolak", _("Ditolak")


class SosStatus(models.TextChoices):
    ACTIVE = "aktif", _("Aktif – butuh bantuan")
    ACKNOWLEDGED = "ditangani", _("Sedang ditangani")
    RESOLVED = "selesai", _("Selesai")
    FALSE_ALARM = "palsu", _("Alarm palsu")


OPEN_SOS_STATUSES = [SosStatus.ACTIVE, SosStatus.ACKNOWLEDGED]
