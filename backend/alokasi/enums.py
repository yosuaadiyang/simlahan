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
    ARRANGEMENT = "penataan", _("Pengalokasian penataan")
    KSB = "ksb", _("Pengalokasian kavling siap bangun (KSB)")


# Alokasi untuk penataan permukiman / KSB: pemohon (umumnya perorangan yang
# menguasai fisik bidang) tidak wajib mengisi rencana investasi usaha.
SETTLEMENT_ALLOCATION_TYPES = (AllocationType.ARRANGEMENT, AllocationType.KSB)


class PlotStatus(models.TextChoices):
    AVAILABLE = "tersedia", _("Tersedia")
    RESERVED = "dipesan", _("Dalam proses permohonan")
    ALLOCATED = "dialokasikan", _("Sudah dialokasikan")
    LEASED = "disewa", _("Sudah disewakan")
    CLOSED = "ditutup", _("Ditutup")


# Lahan yang sudah terikat permohonan, alokasi, atau sewa: ukuran & tarifnya
# dikunci dan tidak boleh ditimpa impor.
BOUND_PLOT_STATUSES = (PlotStatus.RESERVED, PlotStatus.ALLOCATED, PlotStatus.LEASED)


class InfoCategory(models.TextChoices):
    REGULATION = "regulasi", _("Regulasi")
    REQUIREMENT = "persyaratan", _("Persyaratan")
    PROCEDURE = "prosedur", _("Prosedur & tahapan")
    ANNOUNCEMENT = "pengumuman", _("Pengumuman")
    TUTORIAL = "tutorial", _("Video tutorial")
    GUIDE = "panduan", _("Buku panduan")
    DOWNLOAD = "unduhan", _("Unduhan")
    FAQ = "faq", _("Tanya jawab")
    INVESTMENT = "investasi", _("Panduan investasi")


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
    REVISE_PL = "revisi_pl", _("Permohonan revisi penetapan lokasi (PL)")
    MERGE_PL = "gabung_pl", _("Permohonan penggabungan penetapan lokasi (PL)")
    ADJUSTMENT = "penyesuaian", _("Permohonan penyesuaian dokumen alokasi tanah")
    RECOMMENDATION = "rekomendasi", _("Permohonan surat rekomendasi")
    UNBLOCK = "buka_blokir", _("Permohonan pembukaan blokir penetapan lokasi (PL)")
    REPLACEMENT = "dok_pengganti", _("Permohonan dokumen pengganti")
    MORTGAGE = "hak_tanggungan", _("Permohonan persetujuan hak tanggungan")
    AUCTION = "lelang", _("Permohonan persetujuan lelang")
    KPT_CHANGE = "kpt_perubahan", _("Permohonan penerbitan KPT dan PPT perubahan")
    KPT_NEW = "kpt_baru", _("Permohonan penerbitan KPT dan PPT baru")


# Layanan atas alokasi milik sendiri (bukan alokasi lahan baru).
OWN_ALLOCATION_SERVICES = (
    ServiceType.TRANSFER,
    ServiceType.EXTENSION,
    ServiceType.RENEWAL,
    ServiceType.SPLIT,
    ServiceType.REMEASURE,
    ServiceType.REVISE_PL,
    ServiceType.MERGE_PL,
    ServiceType.ADJUSTMENT,
    ServiceType.RECOMMENDATION,
    ServiceType.UNBLOCK,
    ServiceType.REPLACEMENT,
    ServiceType.MORTGAGE,
    ServiceType.AUCTION,
    ServiceType.KPT_CHANGE,
    ServiceType.KPT_NEW,
)

# Layanan yang menerbitkan ulang KPT dan PPT bernomor baru; dokumen lama
# ditandai sudah diganti.
REISSUE_SERVICES = (
    ServiceType.REPLACEMENT,
    ServiceType.KPT_CHANGE,
    ServiceType.KPT_NEW,
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
# Status saat data identitas pemohon sedang/sudah diverifikasi petugas dan akan
# dicetak pada dokumen terbit (KPT/PPT/PL/IPH): identitas tidak boleh diubah
# pemohon. Saat PERBAIKAN pemohon boleh membetulkannya; pengajuan ulang akan
# diverifikasi lagi.
IDENTITY_LOCK_STATUSES = (
    ApplicationStatus.SUBMITTED,
    ApplicationStatus.VERIFYING,
    ApplicationStatus.APPROVED,
    ApplicationStatus.PAID,
)
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


class DevelopmentStage(models.TextChoices):
    NOT_STARTED = "belum_mulai", _("Belum dimulai")
    PREPARATION = "persiapan", _("Pematangan / persiapan lahan")
    CONSTRUCTION = "konstruksi", _("Konstruksi")
    OPERATIONAL = "operasional", _("Sudah beroperasi")


# --------------------------------------------------------------------------
# Portal investasi
# --------------------------------------------------------------------------


class InvestmentScheme(models.TextChoices):
    LEASE = "sewa", _("Sewa lahan")
    ALLOCATION = "alokasi", _("Alokasi lahan (UWT)")
    PARTNERSHIP = "kerja_sama", _("Kerja sama pemanfaatan")
    UNDECIDED = "belum", _("Belum ditentukan, minta saran petugas")


# Skema yang dapat ditawarkan petugas (bukan "belum ditentukan").
OFFER_SCHEMES = (
    InvestmentScheme.LEASE,
    InvestmentScheme.ALLOCATION,
    InvestmentScheme.PARTNERSHIP,
)


class CapitalOrigin(models.TextChoices):
    DOMESTIC = "pmdn", _("Penanaman modal dalam negeri (PMDN)")
    FOREIGN = "pma", _("Penanaman modal asing (PMA)")


class InvestmentStatus(models.TextChoices):
    SUBMITTED = "diajukan", _("Diajukan")
    REVIEW = "ditinjau", _("Sedang ditinjau")
    CONSULTATION = "konsultasi", _("Konsultasi / kunjungan lapangan")
    OFFERED = "ditawarkan", _("Penawaran dikirim")
    ACCEPTED = "diterima", _("Penawaran diterima")
    COMPLETED = "selesai", _("Selesai, diteruskan")
    REJECTED = "ditolak", _("Ditolak")
    CANCELLED = "dibatalkan", _("Dibatalkan investor")


INVESTMENT_FINAL_STATUSES = (
    InvestmentStatus.COMPLETED,
    InvestmentStatus.REJECTED,
    InvestmentStatus.CANCELLED,
)
