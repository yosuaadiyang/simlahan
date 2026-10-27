from django.db import models
from django.utils.translation import gettext_lazy as _


class Scheme(models.TextChoices):
    ALLOCATION = "alokasi", _("Alokasi lahan")
    LEASE = "sewa", _("Sewa lahan")
    PARTNERSHIP = "kerja_sama", _("Kerja sama pemanfaatan")
    OTHER = "lainnya", _("Lainnya")


class LandUseStatus(models.TextChoices):
    ACTIVE = "aktif", _("Aktif")
    ENDED = "berakhir", _("Berakhir")
    REVOKED = "dicabut", _("Dicabut")


class Category(models.TextChoices):
    PERMIT = "perizinan", _("Perizinan")
    CONTRACT = "kontrak", _("Kontrak & perjanjian")
    TECHNICAL = "teknis", _("Dokumen teknis")
    OTHER = "lainnya", _("Lainnya")


class Confidentiality(models.TextChoices):
    NORMAL = "biasa", _("Biasa")
    SECRET = "rahasia", _("Rahasia")


class RecordStatus(models.TextChoices):
    NOT_STARTED = "belum", _("Belum diurus")
    IN_PROGRESS = "proses", _("Sedang diurus")
    SUBMITTED = "diajukan", _("Menunggu verifikasi")
    REVISION = "perbaikan", _("Perlu perbaikan")
    VERIFIED = "terverifikasi", _("Terverifikasi")
    EXPIRED = "kedaluwarsa", _("Kedaluwarsa")
    WAIVED = "tidak_wajib", _("Tidak wajib")


# Status yang dianggap beres untuk progres kelengkapan.
DONE_RECORD_STATUSES = (RecordStatus.VERIFIED, RecordStatus.WAIVED)
# Status yang boleh diisi sendiri oleh pemegang hak (sisanya diatur petugas).
HOLDER_RECORD_STATUSES = (RecordStatus.NOT_STARTED, RecordStatus.IN_PROGRESS)


class VersionSource(models.TextChoices):
    HOLDER = "pemegang", _("Unggahan pemegang hak")
    OFFICER = "petugas", _("Unggahan petugas")
    TEMPLATE = "templat", _("Dibuat dari templat")
    SIGNED = "tanda_tangan", _("Hasil tanda tangan elektronik")
    MIGRATED = "migrasi", _("Pindahan laporan perizinan lama")


class TemplateKind(models.TextChoices):
    HTML = "html", _("Dokumen isian (bisa ditandatangani elektronik)")
    DOCX = "docx", _("Word dengan isian otomatis")
    FILE = "berkas", _("Format / formulir siap unduh")


class SigningStatus(models.TextChoices):
    DRAFT = "draf", _("Draf")
    PENDING_APPROVAL = "menunggu_persetujuan", _("Menunggu persetujuan internal")
    APPROVED = "disetujui", _("Disetujui, siap dikirim")
    SENT = "dikirim", _("Dikirim")
    VIEWED = "dilihat", _("Dilihat penerima")
    COMPLETED = "selesai", _("Selesai")
    DECLINED = "ditolak", _("Ditolak penerima")
    EXPIRED = "kedaluwarsa", _("Kedaluwarsa")
    CANCELLED = "dibatalkan", _("Dibatalkan")


OPEN_SIGNING_STATUSES = (SigningStatus.SENT, SigningStatus.VIEWED)
FINAL_SIGNING_STATUSES = (
    SigningStatus.COMPLETED,
    SigningStatus.DECLINED,
    SigningStatus.EXPIRED,
    SigningStatus.CANCELLED,
)


class SigningSource(models.TextChoices):
    HTML = "html", _("Isi dari templat / editor")
    PDF = "pdf", _("Berkas PDF unggahan")


class RecipientAction(models.TextChoices):
    SIGN = "tanda_tangan", _("Menandatangani")
    APPROVE = "setuju", _("Menyetujui")
    COPY = "salinan", _("Menerima salinan")


class RecipientStatus(models.TextChoices):
    WAITING = "menunggu", _("Menunggu")
    VIEWED = "dilihat", _("Sudah melihat")
    DONE = "selesai", _("Selesai")
    DECLINED = "ditolak", _("Menolak")


class DownloadStatus(models.TextChoices):
    PENDING = "menunggu", _("Menunggu persetujuan")
    APPROVED = "disetujui", _("Disetujui")
    REJECTED = "ditolak", _("Ditolak")
    CANCELLED = "dibatalkan", _("Dibatalkan")


class DownloadPurpose(models.TextChoices):
    ARCHIVE = "arsip", _("Arsip / administrasi")
    PERMIT = "perizinan", _("Pengurusan izin ke instansi lain")
    FINANCING = "pembiayaan", _("Pengajuan pembiayaan / bank")
    LEGAL = "hukum", _("Keperluan hukum / pengadilan")
    AUDIT = "audit", _("Pemeriksaan / audit")
    OTHER = "lainnya", _("Lainnya")


class Action(models.TextChoices):
    CREATED = "dibuat", _("Dibuat")
    UPDATED = "diubah", _("Diubah")
    STATUS = "status", _("Status diperbarui")
    UPLOADED = "unggah", _("Berkas diunggah")
    VERIFIED = "verifikasi", _("Diverifikasi")
    REVISION = "perbaikan", _("Diminta perbaikan")
    WAIVED = "tidak_wajib", _("Dinyatakan tidak wajib")
    REOPENED = "dibuka", _("Dibuka kembali")
    GENERATED = "dari_templat", _("Dibuat dari templat")
    APPROVAL_REQUESTED = "minta_persetujuan", _("Persetujuan internal diminta")
    APPROVED = "disetujui", _("Disetujui internal")
    APPROVAL_REJECTED = "persetujuan_ditolak", _("Persetujuan internal ditolak")
    SENT = "dikirim", _("Dikirim ke penerima")
    VIEWED = "dilihat", _("Dilihat")
    SIGNED = "ditandatangani", _("Ditandatangani")
    RECIPIENT_APPROVED = "disetujui_penerima", _("Disetujui penerima")
    DECLINED = "ditolak", _("Ditolak penerima")
    COMPLETED = "selesai", _("Selesai")
    REMINDED = "pengingat", _("Pengingat dikirim")
    CANCELLED = "dibatalkan", _("Dibatalkan")
    EXPIRED = "kedaluwarsa", _("Kedaluwarsa")
    COMMENTED = "komentar", _("Komentar")
    OTP_SENT = "otp", _("Kode verifikasi dikirim")
    DOWNLOAD_REQUESTED = "minta_unduh", _("Unduhan diminta")
    DOWNLOAD_APPROVED = "unduh_disetujui", _("Unduhan disetujui")
    DOWNLOAD_REJECTED = "unduh_ditolak", _("Unduhan ditolak")
    DOWNLOAD_CANCELLED = "unduh_dibatalkan", _("Permintaan unduhan dibatalkan")
    DOWNLOADED = "diunduh", _("Diunduh")
    PREVIEWED = "pratinjau", _("Dipratinjau")
