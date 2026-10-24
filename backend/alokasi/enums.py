"""Pilihan (choices) modul alokasi lahan.

Modul ini menyediakan layanan alokasi lahan secara daring: informasi
ketersediaan lahan, permohonan alokasi tanah (reguler, langsung, terbuka),
verifikasi teknis, tagihan UWT, penerbitan Keputusan Pengalokasian Tanah (KPT)
dan Perjanjian Pemanfaatan Tanah (PPT), pelaporan progres perizinan dan
pembangunan, pemantauan lahan tidur, serta izin peralihan hak.

Label ditulis langsung dalam Bahasa Indonesia karena portal hanya berbahasa
Indonesia.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class AllocationType(models.TextChoices):
    REGULAR = "reguler", _("Alokasi tanah reguler")
    DIRECT = "langsung", _("Alokasi tanah langsung")
    OPEN = "terbuka", _("Alokasi tanah terbuka")


class PlotStatus(models.TextChoices):
    AVAILABLE = "tersedia", _("Tersedia")
    RESERVED = "dipesan", _("Dalam proses permohonan")
    ALLOCATED = "dialokasikan", _("Sudah dialokasikan")
    CLOSED = "ditutup", _("Ditutup")


class InfoCategory(models.TextChoices):
    REGULATION = "regulasi", _("Regulasi")
    REQUIREMENT = "persyaratan", _("Persyaratan")
    PROCEDURE = "prosedur", _("Prosedur & tahapan")
    ANNOUNCEMENT = "pengumuman", _("Pengumuman")
    TUTORIAL = "tutorial", _("Video tutorial")
    DOWNLOAD = "unduhan", _("Unduhan")
    FAQ = "faq", _("Tanya jawab")


class ApplicantType(models.TextChoices):
    PERSON = "perorangan", _("Perorangan")
    COMPANY = "badan_usaha", _("Badan usaha")
    GOVERNMENT = "instansi", _("Instansi pemerintah")


class ServiceType(models.TextChoices):
    ALLOCATION = "alokasi", _("Permohonan alokasi tanah")
    TRANSFER = "peralihan", _("Permohonan izin peralihan hak")
    EXTENSION = "perpanjangan", _("Permohonan perpanjangan hak atas tanah")
    RENEWAL = "pembaruan", _("Permohonan pembaruan hak atas tanah")
    SPLIT = "pecah_pl", _("Permohonan pemecahan penetapan lokasi (PL)")
    REMEASURE = "ukur_ulang", _("Permohonan pengukuran ulang")


# Layanan atas alokasi milik sendiri (bukan alokasi lahan baru).
OWN_ALLOCATION_SERVICES = (
    ServiceType.TRANSFER,
    ServiceType.EXTENSION,
    ServiceType.RENEWAL,
    ServiceType.SPLIT,
    ServiceType.REMEASURE,
)


class ApplicationStatus(models.TextChoices):
    DRAFT = "draf", _("Draf")
    SUBMITTED = "diajukan", _("Diajukan")
    VERIFYING = "verifikasi", _("Verifikasi teknis")
    REVISION = "perbaikan", _("Perlu perbaikan")
    APPROVED = "disetujui", _("Disetujui, menunggu pembayaran")
    PAID = "lunas", _("Pembayaran terverifikasi")
    ISSUED = "terbit", _("Dokumen terbit")
    REJECTED = "ditolak", _("Ditolak")
    CANCELLED = "dibatalkan", _("Dibatalkan pemohon")


# Status yang masih bisa diubah pemohon.
EDITABLE_STATUSES = (ApplicationStatus.DRAFT, ApplicationStatus.REVISION)
# Status yang sudah selesai (tidak bisa berubah lagi).
FINAL_STATUSES = (
    ApplicationStatus.ISSUED,
    ApplicationStatus.REJECTED,
    ApplicationStatus.CANCELLED,
)


class InvoiceKind(models.TextChoices):
    UWT = "uwt", _("Uang Wajib Tahunan (UWT)")
    ALLOCATION_FEE = "adm_alokasi", _("Biaya administrasi alokasi")
    TRANSFER_FEE = "adm_peralihan", _("Biaya administrasi peralihan hak")
    EXTENSION_FEE = "adm_perpanjangan", _(
        "Biaya administrasi perpanjangan/pembaruan hak"
    )
    SERVICE_FEE = "adm_layanan", _("Biaya administrasi layanan tanah")


class InvoiceStatus(models.TextChoices):
    UNPAID = "belum_bayar", _("Belum dibayar")
    PROOF_UPLOADED = "menunggu_verifikasi", _("Bukti bayar menunggu verifikasi")
    PAID = "lunas", _("Lunas")
    CANCELLED = "batal", _("Dibatalkan")


class AllocationStatus(models.TextChoices):
    ACTIVE = "aktif", _("Aktif")
    TRANSFERRED = "dialihkan", _("Dialihkan")
    REVOKED = "dicabut", _("Dicabut")
    EXPIRED = "berakhir", _("Berakhir")


class PermitType(models.TextChoices):
    PKKPR = "pkkpr", _("PKKPR (Persetujuan Kesesuaian Kegiatan Pemanfaatan Ruang)")
    PKKPRL = "pkkprl", _(
        "PKKPRL (Persetujuan Kesesuaian Kegiatan Pemanfaatan Ruang Laut)"
    )
    ENVIRONMENT = "lingkungan", _("Persetujuan Lingkungan")
    PBG = "pbg", _("PBG (Persetujuan Bangunan Gedung)")
    SLF = "slf", _("SLF (Sertifikat Laik Fungsi)")
    OTHER = "lainnya", _("Izin lainnya")


class PermitStatus(models.TextChoices):
    NOT_STARTED = "belum", _("Belum diurus")
    IN_PROCESS = "proses", _("Dalam proses")
    ISSUED = "terbit", _("Sudah terbit")
    NOT_REQUIRED = "tidak_wajib", _("Tidak diwajibkan")


class DevelopmentStage(models.TextChoices):
    NOT_STARTED = "belum_mulai", _("Belum dimulai")
    PREPARATION = "persiapan", _("Pematangan / persiapan lahan")
    CONSTRUCTION = "konstruksi", _("Konstruksi")
    OPERATIONAL = "operasional", _("Sudah beroperasi")
