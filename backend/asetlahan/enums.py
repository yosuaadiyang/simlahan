"""Pilihan (choices) modul Manajemen Aset Lahan.

Modul ini melengkapi pengadaan tanah, alokasi lahan, dan sewa dengan bank
tanah terpusat: riwayat & silsilah kepemilikan, pemangku kepentingan,
penilaian & pajak, keuangan lahan, perkara & advokat, okupasi/perambahan,
citra satelit, survei, permukiman kembali, pengaduan, lelang, tugas & tim,
urusan instansi, dokumen ber-OCR, peta tematik, dan aplikasi lapangan.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class AssetStatus(models.TextChoices):
    CONTROLLED = "dikuasai", _("Dikuasai, belum dimanfaatkan")
    IN_USE = "dimanfaatkan", _("Dimanfaatkan sendiri")
    LEASED = "disewakan", _("Disewakan")
    ALLOCATED = "dialokasikan", _("Dialokasikan")
    ACQUIRING = "pengadaan", _("Dalam proses pengadaan")
    DISPUTED = "sengketa", _("Sengketa")
    ENCROACHED = "terokupasi", _("Terokupasi")
    RELEASED = "dilepas", _("Dilepas / dijual")


ASSET_STATUS_COLORS = {
    AssetStatus.CONTROLLED: "#8c959f",
    AssetStatus.IN_USE: "#1a7f37",
    AssetStatus.LEASED: "#0969da",
    AssetStatus.ALLOCATED: "#8250df",
    AssetStatus.ACQUIRING: "#bf8700",
    AssetStatus.DISPUTED: "#cf222e",
    AssetStatus.ENCROACHED: "#d1242f",
    AssetStatus.RELEASED: "#57606a",
}


class TitleType(models.TextChoices):
    SHM = "shm", _("Hak Milik (SHM)")
    HGB = "hgb", _("Hak Guna Bangunan (HGB)")
    HGU = "hgu", _("Hak Guna Usaha (HGU)")
    HP = "hp", _("Hak Pakai (HP)")
    HPL = "hpl", _("Hak Pengelolaan (HPL)")
    GIRIK = "girik", _("Girik / letter C / bukti lama")
    UNREGISTERED = "belum", _("Belum bersertipikat")
    OTHER = "lainnya", _("Lainnya")


class AcquisitionMethod(models.TextChoices):
    PURCHASE = "pembelian", _("Pembelian")
    PUBLIC_ACQUISITION = "pengadaan", _("Pengadaan tanah")
    GRANT = "hibah", _("Hibah")
    EXCHANGE = "tukar", _("Tukar menukar")
    DESIGNATION = "penetapan", _("Penetapan / penyerahan pemerintah")
    RECLAMATION = "reklamasi", _("Reklamasi")
    OTHER = "lainnya", _("Lainnya")


class OwnerType(models.TextChoices):
    INDIVIDUAL = "perorangan", _("Perorangan")
    COMPANY = "badan_usaha", _("Badan usaha")
    GOVERNMENT = "pemerintah", _("Instansi pemerintah")
    COMMUNITY = "masyarakat", _("Masyarakat adat / komunal")


class Kinship(models.TextChoices):
    CHILD = "anak", _("Anak")
    SPOUSE = "pasangan", _("Suami / istri")
    GRANDCHILD = "cucu", _("Cucu")
    SIBLING = "saudara", _("Saudara kandung")
    PARENT = "orang_tua", _("Orang tua")
    OTHER = "lainnya", _("Lainnya")


class StakeholderType(models.TextChoices):
    GOVERNMENT = "pemerintah", _("Instansi pemerintah")
    COMMUNITY_LEADER = "tokoh", _("Tokoh masyarakat / adat")
    RESIDENT = "warga", _("Warga / pemilik")
    NGO = "lsm", _("LSM / organisasi")
    COMPANY = "perusahaan", _("Perusahaan")
    MEDIA = "media", _("Media")
    OTHER = "lainnya", _("Lainnya")


class Level(models.TextChoices):
    HIGH = "tinggi", _("Tinggi")
    MEDIUM = "sedang", _("Sedang")
    LOW = "rendah", _("Rendah")


class Stance(models.TextChoices):
    SUPPORT = "mendukung", _("Mendukung")
    NEUTRAL = "netral", _("Netral")
    OPPOSE = "menolak", _("Menolak")
    UNKNOWN = "belum", _("Belum diketahui")


class EngagementMethod(models.TextChoices):
    MEETING = "rapat", _("Rapat / audiensi")
    SOCIALIZATION = "sosialisasi", _("Sosialisasi / konsultasi publik")
    VISIT = "kunjungan", _("Kunjungan")
    LETTER = "surat", _("Surat")
    PHONE = "telepon", _("Telepon / pesan")


class ValuationMethod(models.TextChoices):
    NJOP = "njop", _("NJOP")
    APPRAISER = "kjpp", _("Penilai publik (KJPP)")
    INTERNAL = "internal", _("Penilai internal")
    MARKET = "pasar", _("Data pasar / pembanding")


class ValuationItemType(models.TextChoices):
    BUILDING = "bangunan", _("Bangunan")
    PLANT = "tanaman", _("Tanaman")
    FACILITY = "sarana", _("Sarana pelengkap")
    OTHER = "lainnya", _("Lainnya")


class TaxType(models.TextChoices):
    PBB = "pbb", _("PBB-P2")
    BPHTB = "bphtb", _("BPHTB")
    UWT = "uwt", _("Uang Wajib Tahunan")
    RETRIBUTION = "retribusi", _("Retribusi daerah")
    LEASE = "sewa", _("Sewa tanah (kewajiban)")
    OTHER = "lainnya", _("Lainnya")


class TransactionType(models.TextChoices):
    PURCHASE = "pembelian", _("Pembelian tanah")
    SALE = "penjualan", _("Penjualan / pelepasan tanah")
    LEASE_INCOME = "sewa_masuk", _("Penerimaan sewa")
    LEASE_PAYMENT = "sewa_keluar", _("Pembayaran sewa")
    COMPENSATION = "ganti_kerugian", _("Ganti kerugian")
    RESETTLEMENT = "biaya_rr", _("Biaya permukiman kembali (R&R)")
    TAX = "pajak", _("Pajak & retribusi")
    SURVEY = "biaya_survei", _("Biaya survei & pemetaan")
    LEGAL = "biaya_hukum", _("Biaya hukum / perkara")
    OTHER_EXPENSE = "biaya_lain", _("Biaya lain")
    OTHER_INCOME = "pendapatan_lain", _("Pendapatan lain")


INCOME_TYPES = {
    TransactionType.SALE,
    TransactionType.LEASE_INCOME,
    TransactionType.OTHER_INCOME,
}


class ResettlementUnitStatus(models.TextChoices):
    VACANT = "kosong", _("Kosong")
    BUILDING = "dibangun", _("Dalam pembangunan")
    ASSIGNED = "dialokasikan", _("Dialokasikan, belum dihuni")
    OCCUPIED = "dihuni", _("Dihuni")


RESETTLEMENT_COLORS = {
    ResettlementUnitStatus.VACANT: "#8c959f",
    ResettlementUnitStatus.BUILDING: "#bf8700",
    ResettlementUnitStatus.ASSIGNED: "#0969da",
    ResettlementUnitStatus.OCCUPIED: "#1a7f37",
}


class Court(models.TextChoices):
    PN = "pn", _("Pengadilan Negeri")
    PTUN = "ptun", _("Pengadilan Tata Usaha Negara")
    PT = "pt", _("Pengadilan Tinggi / PT TUN")
    MA = "ma", _("Mahkamah Agung")
    ARBITRATION = "arbitrase", _("Arbitrase")
    NON_LITIGATION = "non_litigasi", _("Mediasi / non-litigasi")
    POLICE = "kepolisian", _("Kepolisian / pidana")


class CaseType(models.TextChoices):
    CIVIL = "perdata", _("Perdata (gugatan kepemilikan)")
    ADMINISTRATIVE = "tun", _("Tata usaha negara")
    CRIMINAL = "pidana", _("Pidana (penyerobotan, pemalsuan)")
    BOUNDARY = "batas", _("Sengketa batas")
    EXECUTION = "eksekusi", _("Eksekusi / pengosongan")
    COMPENSATION = "ganti_kerugian", _("Keberatan ganti kerugian")
    OTHER = "lainnya", _("Lainnya")


class CasePosition(models.TextChoices):
    PLAINTIFF = "penggugat", _("Penggugat / pelapor")
    DEFENDANT = "tergugat", _("Tergugat / terlapor")
    CO_DEFENDANT = "turut_tergugat", _("Turut tergugat")
    APPLICANT = "pemohon", _("Pemohon")
    RESPONDENT = "termohon", _("Termohon")
    INTERVENOR = "intervensi", _("Pihak intervensi")


class CaseStatus(models.TextChoices):
    PREPARATION = "persiapan", _("Persiapan")
    ONGOING = "berjalan", _("Persidangan berjalan")
    DECIDED = "putusan", _("Putusan tingkat pertama")
    APPEAL = "banding", _("Banding")
    CASSATION = "kasasi", _("Kasasi")
    REVIEW = "pk", _("Peninjauan kembali")
    FINAL = "inkracht", _("Berkekuatan hukum tetap")
    EXECUTION = "eksekusi", _("Eksekusi")
    CLOSED = "selesai", _("Selesai / ditutup")


OPEN_CASE_STATUSES = [
    CaseStatus.PREPARATION,
    CaseStatus.ONGOING,
    CaseStatus.DECIDED,
    CaseStatus.APPEAL,
    CaseStatus.CASSATION,
    CaseStatus.REVIEW,
    CaseStatus.FINAL,
    CaseStatus.EXECUTION,
]


class CaseOutcome(models.TextChoices):
    PENDING = "", _("Belum ada")
    WON = "menang", _("Menang")
    LOST = "kalah", _("Kalah")
    SETTLED = "damai", _("Damai")
    DISMISSED = "gugur", _("Gugur / tidak dapat diterima")


class DetectionMethod(models.TextChoices):
    PATROL = "patroli", _("Patroli lapangan")
    REPORT = "laporan", _("Laporan masyarakat / pengaduan")
    SATELLITE = "citra", _("Perbandingan citra satelit")
    DRONE = "drone", _("Foto udara / drone")
    SURVEY = "survei", _("Survei / pengukuran")
    OVERLAP = "tumpang_tindih", _("Analisis tumpang tindih")


class StructureType(models.TextChoices):
    PERMANENT = "permanen", _("Bangunan permanen")
    SEMI = "semi_permanen", _("Bangunan semi permanen")
    FARM = "kebun", _("Kebun / tanaman")
    FENCE = "pagar", _("Pagar / patok")
    EXCAVATION = "galian", _("Galian / timbunan")
    OTHER = "lainnya", _("Lainnya")


class EncroachmentStatus(models.TextChoices):
    REPORTED = "dilaporkan", _("Dilaporkan")
    VERIFIED = "diverifikasi", _("Terverifikasi")
    WARNING_1 = "teguran_1", _("Teguran I")
    WARNING_2 = "teguran_2", _("Teguran II")
    WARNING_3 = "teguran_3", _("Teguran III")
    ENFORCEMENT = "penertiban", _("Penertiban")
    LITIGATION = "litigasi", _("Dilimpahkan ke perkara")
    RESOLVED = "selesai", _("Selesai / lahan kembali")
    REJECTED = "ditolak", _("Tidak terbukti")


OPEN_ENCROACHMENT_STATUSES = [
    EncroachmentStatus.REPORTED,
    EncroachmentStatus.VERIFIED,
    EncroachmentStatus.WARNING_1,
    EncroachmentStatus.WARNING_2,
    EncroachmentStatus.WARNING_3,
    EncroachmentStatus.ENFORCEMENT,
    EncroachmentStatus.LITIGATION,
]


class EncroachmentAction(models.TextChoices):
    VERIFICATION = "verifikasi", _("Verifikasi lapangan")
    WARNING_1 = "teguran_1", _("Surat teguran I")
    WARNING_2 = "teguran_2", _("Surat teguran II")
    WARNING_3 = "teguran_3", _("Surat teguran III")
    MEDIATION = "mediasi", _("Mediasi")
    ENFORCEMENT = "penertiban", _("Penertiban / pembongkaran")
    POLICE_REPORT = "laporan_polisi", _("Laporan polisi")
    RESOLVED = "selesai", _("Lahan kembali dikuasai")
    OTHER = "lainnya", _("Lainnya")


# Tindakan yang sekaligus menaikkan status kasus okupasi.
ACTION_STATUS = {
    EncroachmentAction.VERIFICATION: EncroachmentStatus.VERIFIED,
    EncroachmentAction.WARNING_1: EncroachmentStatus.WARNING_1,
    EncroachmentAction.WARNING_2: EncroachmentStatus.WARNING_2,
    EncroachmentAction.WARNING_3: EncroachmentStatus.WARNING_3,
    EncroachmentAction.ENFORCEMENT: EncroachmentStatus.ENFORCEMENT,
    EncroachmentAction.RESOLVED: EncroachmentStatus.RESOLVED,
}


class ImageryStatus(models.TextChoices):
    REQUESTED = "diminta", _("Diminta")
    ORDERED = "dipesan", _("Dipesan")
    RECEIVED = "diterima", _("Diterima / tersedia")
    REJECTED = "ditolak", _("Ditolak / batal")


class SurveyType(models.TextChoices):
    BOUNDARY = "batas", _("Pengukuran batas / rekonstruksi")
    TOPOGRAPHIC = "topografi", _("Survei topografi")
    AERIAL = "udara", _("Foto udara / drone")
    INVENTORY = "inventarisasi", _("Inventarisasi aset")
    OWNERSHIP = "kepemilikan", _("Identifikasi pemilik / penguasaan")
    COMPENSATION = "ganti_kerugian", _("Survei objek ganti kerugian")
    DIGITIZATION = "digitasi", _("Digitalisasi peta & warkah")


class SurveyStatus(models.TextChoices):
    REQUESTED = "diajukan", _("Diajukan")
    SCHEDULED = "dijadwalkan", _("Dijadwalkan")
    IN_PROGRESS = "berlangsung", _("Berlangsung")
    DONE = "selesai", _("Selesai")
    CANCELLED = "batal", _("Batal")


class FacilitatorType(models.TextChoices):
    COMPANION = "pendamping", _("Pendamping masyarakat")
    BROKER = "perantara", _("Perantara / mediator")
    CONSULTANT = "konsultan", _("Konsultan")
    LIAISON = "penghubung", _("Penghubung instansi")
    APPRAISER = "penilai", _("Penilai")
    SURVEYOR = "surveyor", _("Surveyor berlisensi")


class LiaisonStatus(models.TextChoices):
    PREPARING = "persiapan", _("Persiapan berkas")
    SUBMITTED = "diajukan", _("Diajukan")
    PROCESSING = "diproses", _("Diproses instansi")
    DONE = "selesai", _("Selesai")
    REJECTED = "ditolak", _("Ditolak")


class TaskType(models.TextChoices):
    SURVEY = "survei", _("Survei / pengukuran")
    VERIFICATION = "verifikasi", _("Verifikasi")
    ADMINISTRATION = "administrasi", _("Administrasi")
    LEGAL = "hukum", _("Hukum")
    PATROL = "patroli", _("Patroli")
    MAINTENANCE = "pemeliharaan", _("Pemeliharaan aset")
    OTHER = "lainnya", _("Lainnya")


class Priority(models.TextChoices):
    LOW = "rendah", _("Rendah")
    NORMAL = "normal", _("Normal")
    HIGH = "tinggi", _("Tinggi")
    URGENT = "mendesak", _("Mendesak")


class TaskStatus(models.TextChoices):
    NEW = "baru", _("Baru")
    IN_PROGRESS = "dikerjakan", _("Dikerjakan")
    WAITING = "menunggu", _("Menunggu pihak lain")
    DONE = "selesai", _("Selesai")
    CANCELLED = "batal", _("Batal")


OPEN_TASK_STATUSES = [TaskStatus.NEW, TaskStatus.IN_PROGRESS, TaskStatus.WAITING]


class GrievanceChannel(models.TextChoices):
    PORTAL = "portal", _("Portal")
    PHONE = "telepon", _("Telepon / WhatsApp")
    LETTER = "surat", _("Surat")
    WALK_IN = "langsung", _("Datang langsung")
    FIELD = "lapangan", _("Petugas lapangan")


class GrievanceStatus(models.TextChoices):
    NEW = "baru", _("Diterima")
    VERIFIED = "diverifikasi", _("Diverifikasi")
    IN_PROGRESS = "ditindaklanjuti", _("Ditindaklanjuti")
    RESOLVED = "selesai", _("Selesai")
    REJECTED = "ditolak", _("Tidak dapat ditindaklanjuti")


OPEN_GRIEVANCE_STATUSES = [
    GrievanceStatus.NEW,
    GrievanceStatus.VERIFIED,
    GrievanceStatus.IN_PROGRESS,
]


class TenderMethod(models.TextChoices):
    AUCTION = "lelang", _("Lelang harga tertinggi")
    BEAUTY_CONTEST = "seleksi", _("Seleksi proposal (beauty contest)")


class TenderStatus(models.TextChoices):
    DRAFT = "draf", _("Draf")
    ANNOUNCED = "diumumkan", _("Diumumkan / menerima penawaran")
    CLOSED = "ditutup", _("Penawaran ditutup")
    AWARDED = "ditetapkan", _("Pemenang ditetapkan")
    CANCELLED = "batal", _("Dibatalkan")


class BidStatus(models.TextChoices):
    SUBMITTED = "masuk", _("Masuk")
    QUALIFIED = "lolos", _("Lolos evaluasi")
    DISQUALIFIED = "gugur", _("Gugur")
    WON = "menang", _("Pemenang")
    LOST = "kalah", _("Tidak menang")


class DocumentType(models.TextChoices):
    CERTIFICATE = "sertipikat", _("Sertipikat / alas hak")
    DEED = "akta", _("Akta (jual beli, hibah, waris)")
    COURT = "pengadilan", _("Gugatan / putusan / berkas perkara")
    LETTER = "surat", _("Surat / korespondensi")
    MAP = "peta", _("Peta / gambar ukur")
    PHOTO = "foto", _("Foto")
    REPORT = "laporan", _("Laporan")
    CONTRACT = "kontrak", _("Perjanjian / kontrak")
    PERMIT = "izin", _("Izin / keputusan")
    TAX = "pajak", _("Bukti pajak / SPPT")
    OTHER = "lainnya", _("Lainnya")


class PhotoPhase(models.TextChoices):
    NONE = "", _("-")
    BEFORE = "sebelum", _("Sebelum")
    AFTER = "sesudah", _("Sesudah")


class OcrStatus(models.TextChoices):
    NONE = "", _("Belum diproses")
    DONE = "selesai", _("Teks tersedia")
    EMPTY = "kosong", _("Tidak ada teks terbaca")
    FAILED = "gagal", _("Gagal")


class FieldReportType(models.TextChoices):
    PATROL = "patroli", _("Patroli rutin")
    ENCROACHMENT = "okupasi", _("Temuan okupasi / perambahan")
    CONDITION = "kondisi", _("Kondisi aset")
    SURVEY = "survei", _("Catatan survei")
    BOUNDARY = "patok", _("Patok batas")
