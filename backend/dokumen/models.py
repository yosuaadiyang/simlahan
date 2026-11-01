"""Model modul dokumen & perizinan.

Setiap pemanfaatan lahan (alokasi, sewa, kerja sama, atau lainnya) punya daftar
dokumen perizinan wajib sesuai jenis izin yang berlaku untuk skemanya. Pemegang
hak mengunggah versi dokumen lewat portal, petugas memverifikasi. Templat
dokumen (isian, Word, atau formulir) dapat diunggah/diimpor dan dipakai untuk
membuat dokumen bertanda tangan elektronik dengan alur penerima berurutan,
persetujuan internal, pengingat, dan sertifikat penyelesaian. Setiap unduhan
berkas wajib lewat permintaan yang disetujui pejabat berwenang dan tercatat.
"""

import datetime
import uuid

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from sequences import get_next_value

from alokasi.models import MAX_TERM_YEARS
from dokumen import enums
from file_operations.private_files import PrivateFileField
from leasing.models.mixins import TimeStampedModel

AREA = {"max_digits": 16, "decimal_places": 2}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
DOCUMENT_EXTENSIONS = ["pdf", "jpg", "jpeg", "png", "docx", "xlsx"]
TEMPLATE_FILE_EXTENSIONS = ["pdf", "docx", "xlsx", "jpg", "jpeg", "png"]
# Isi templat/dokumen HTML (termasuk logo tersemat) dibatasi agar PDF tetap ringan.
MAX_BODY_CHARS = 2_000_000


def validate_upload_size(value):
    if value and value.size > MAX_UPLOAD_BYTES:
        raise ValidationError(_("Ukuran berkas maksimal 20 MB."))


DOCUMENT_VALIDATORS = [
    FileExtensionValidator(allowed_extensions=DOCUMENT_EXTENSIONS),
    validate_upload_size,
]
TEMPLATE_FILE_VALIDATORS = [
    FileExtensionValidator(allowed_extensions=TEMPLATE_FILE_EXTENSIONS),
    validate_upload_size,
]
PDF_VALIDATORS = [
    FileExtensionValidator(allowed_extensions=["pdf"]),
    validate_upload_size,
]


def _upload_to(name, prefix):
    def inner(instance, filename):
        return f"dokumen/{prefix}/{timezone.now():%Y/%m}/{uuid.uuid4().hex}/{filename}"

    # Nama harus sama dengan nama variabel modul agar dapat diimpor oleh migrasi.
    inner.__name__ = inner.__qualname__ = name
    return inner


upload_version = _upload_to("upload_version", "versi")
upload_template = _upload_to("upload_template", "templat")
upload_signing = _upload_to("upload_signing", "tanda_tangan")
upload_field = _upload_to("upload_field", "lampiran_penerima")


def next_number(prefix: str) -> str:
    year = timezone.localdate().year
    value = get_next_value(f"dokumen_{prefix.lower()}_{year}")
    return f"{prefix}-{year}-{value:05d}"


def _add_months(date: datetime.date, months: int) -> datetime.date:
    month = date.month - 1 + months
    year = date.year + month // 12
    month = month % 12 + 1
    day = date.day
    while day > 28:
        try:
            return date.replace(year=year, month=month, day=day)
        except ValueError:
            day -= 1
    return date.replace(year=year, month=month, day=day)


class DocumentSettings(models.Model):
    """Aturan unduhan, tanda tangan elektronik, dan pengingat (satu baris)."""

    download_valid_hours = models.PositiveSmallIntegerField(
        verbose_name=_("Masa berlaku izin unduh (jam)"),
        default=24,
        validators=[MinValueValidator(1), MaxValueValidator(720)],
    )
    download_max_count = models.PositiveSmallIntegerField(
        verbose_name=_("Batas unduh per persetujuan"),
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
    )
    applicant_needs_approval = models.BooleanField(
        verbose_name=_("Pemegang hak wajib minta persetujuan unduh"),
        default=True,
        help_text=_(
            "Bila dimatikan, permintaan unduh pemegang hak atas dokumennya sendiri "
            "(kategori biasa) langsung disetujui sistem; tetap tercatat."
        ),
    )
    allow_self_approval = models.BooleanField(
        verbose_name=_("Izinkan menyetujui permintaan sendiri"),
        default=False,
        help_text=_(
            "Hanya untuk instansi dengan satu pemberi persetujuan. Sebaiknya tetap "
            "mati agar setiap unduhan diperiksa orang lain."
        ),
    )
    watermark = models.BooleanField(
        verbose_name=_("Beri tanda air pada PDF yang diunduh"),
        default=True,
        help_text=_(
            "Nama pengunduh, waktu, dan nomor permintaan dicetak di setiap halaman."
        ),
    )
    signing_expiry_days = models.PositiveSmallIntegerField(
        verbose_name=_("Batas waktu tanda tangan bawaan (hari)"),
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
    )
    reminder_every_days = models.PositiveSmallIntegerField(
        verbose_name=_("Pengingat penanda tangan setiap (hari)"),
        default=3,
        validators=[MaxValueValidator(60)],
        help_text=_("0 = tanpa pengingat otomatis."),
    )
    expiry_warning_days = models.PositiveSmallIntegerField(
        verbose_name=_("Peringatan izin akan kedaluwarsa (hari sebelumnya)"),
        default=60,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
    )

    class Meta:
        verbose_name = _("Pengaturan dokumen")
        verbose_name_plural = _("Pengaturan dokumen")

    def __str__(self):
        return str(self._meta.verbose_name)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "DocumentSettings":
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj


class ContentBlock(TimeStampedModel):
    """Pustaka konten: paragraf baku yang disisipkan ke templat lewat
    ``{{ blok.<kode> }}`` (mis. pasal sanksi, ketentuan umum)."""

    code = models.SlugField(
        verbose_name=_("Kode"),
        max_length=40,
        unique=True,
        help_text=_(
            "Huruf kecil, angka, dan garis bawah; dipakai sebagai {{ blok.kode }}."
        ),
        validators=[
            RegexValidator(r"^[a-z0-9_]+$", _("Hanya huruf kecil, angka, dan _."))
        ],
    )
    name = models.CharField(verbose_name=_("Nama"), max_length=255)
    body = models.TextField(verbose_name=_("Isi"), max_length=MAX_BODY_CHARS)
    is_active = models.BooleanField(verbose_name=_("Aktif"), default=True)

    class Meta:
        verbose_name = _("Blok konten")
        verbose_name_plural = _("Pustaka konten")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({{{{ blok.{self.code} }}}})"


class DocumentTemplate(TimeStampedModel):
    """Templat/format dokumen: isian HTML, Word ber-isian, atau formulir siap unduh."""

    name = models.CharField(verbose_name=_("Nama templat"), max_length=255)
    category = models.CharField(
        verbose_name=_("Kategori"),
        max_length=16,
        choices=enums.Category.choices,
        default=enums.Category.PERMIT,
    )
    kind = models.CharField(
        verbose_name=_("Jenis templat"),
        max_length=8,
        choices=enums.TemplateKind.choices,
        default=enums.TemplateKind.HTML,
    )
    description = models.TextField(verbose_name=_("Keterangan"), blank=True, default="")
    body = models.TextField(
        verbose_name=_("Isi dokumen"),
        blank=True,
        default="",
        max_length=MAX_BODY_CHARS,
        help_text=_(
            "Sisipkan isian otomatis, mis. {{ pemohon.nama }} atau {{ lahan.kode }}."
        ),
    )
    file = PrivateFileField(
        verbose_name=_("Berkas templat"),
        max_length=255,
        upload_to=upload_template,
        null=True,
        blank=True,
        validators=TEMPLATE_FILE_VALIDATORS,
    )
    original_name = models.CharField(
        verbose_name=_("Nama berkas asli"), max_length=255, blank=True, default=""
    )
    version = models.PositiveIntegerField(verbose_name=_("Versi"), default=1)
    signer_roles = models.TextField(
        verbose_name=_("Peran penerima bawaan"),
        blank=True,
        default="",
        help_text=_(
            'Satu peran per baris, berurutan, mis. "Pemegang hak" lalu '
            '"Pejabat penandatangan". Dipakai mengisi daftar penerima.'
        ),
    )
    confidentiality = models.CharField(
        verbose_name=_("Sifat dokumen"),
        max_length=8,
        choices=enums.Confidentiality.choices,
        default=enums.Confidentiality.NORMAL,
    )
    needs_approval = models.BooleanField(
        verbose_name=_("Wajib persetujuan internal sebelum dikirim"), default=False
    )
    expiry_days = models.PositiveSmallIntegerField(
        verbose_name=_("Batas waktu tanda tangan (hari)"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        help_text=_("Kosongkan untuk memakai pengaturan umum."),
    )
    is_active = models.BooleanField(verbose_name=_("Aktif"), default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Dibuat oleh"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = _("Templat dokumen")
        verbose_name_plural = _("Templat dokumen")
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} (v{self.version})"

    def clean(self):
        super().clean()
        if self.kind == enums.TemplateKind.HTML and not (self.body or "").strip():
            raise ValidationError({"body": _("Isi dokumen wajib diisi.")})
        if (
            self.kind in (enums.TemplateKind.DOCX, enums.TemplateKind.FILE)
            and not self.file
        ):
            raise ValidationError({"file": _("Unggah berkas templat.")})
        if self.kind == enums.TemplateKind.DOCX and self.file:
            name = (self.original_name or self.file.name or "").lower()
            if not name.endswith(".docx"):
                raise ValidationError(
                    {"file": _("Templat Word harus berformat .docx.")}
                )

    @property
    def roles(self) -> list[str]:
        return [r.strip()[:100] for r in self.signer_roles.splitlines() if r.strip()][
            :10
        ]

    @property
    def can_sign(self) -> bool:
        return self.kind == enums.TemplateKind.HTML


class PermitType(models.Model):
    """Jenis dokumen perizinan/kelengkapan yang wajib dimiliki pemanfaatan lahan."""

    code = models.SlugField(
        verbose_name=_("Kode"),
        max_length=32,
        unique=True,
        validators=[
            RegexValidator(r"^[a-z0-9_]+$", _("Hanya huruf kecil, angka, dan _."))
        ],
    )
    name = models.CharField(verbose_name=_("Nama dokumen / izin"), max_length=255)
    category = models.CharField(
        verbose_name=_("Kategori"),
        max_length=16,
        choices=enums.Category.choices,
        default=enums.Category.PERMIT,
    )
    issuer = models.CharField(
        verbose_name=_("Instansi penerbit"), max_length=255, blank=True, default=""
    )
    description = models.TextField(
        verbose_name=_("Persyaratan & cara mengurus"), blank=True, default=""
    )
    applies_allocation = models.BooleanField(
        verbose_name=_("Berlaku untuk alokasi"), default=True
    )
    applies_lease = models.BooleanField(
        verbose_name=_("Berlaku untuk sewa"), default=True
    )
    applies_partnership = models.BooleanField(
        verbose_name=_("Berlaku untuk kerja sama"), default=True
    )
    applies_other = models.BooleanField(
        verbose_name=_("Berlaku untuk pemanfaatan lainnya"), default=True
    )
    sectors = models.ManyToManyField(
        "alokasi.InvestmentSector",
        verbose_name=_("Hanya untuk sektor"),
        blank=True,
        related_name="permit_types",
        help_text=_("Kosongkan bila berlaku untuk semua sektor."),
    )
    is_required = models.BooleanField(verbose_name=_("Wajib"), default=True)
    validity_months = models.PositiveSmallIntegerField(
        verbose_name=_("Masa berlaku bawaan (bulan)"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_TERM_YEARS * 12)],
        help_text=_(
            "Untuk menghitung tanggal kedaluwarsa bila tidak diisi. Kosong = tidak kedaluwarsa."
        ),
    )
    confidentiality = models.CharField(
        verbose_name=_("Sifat dokumen"),
        max_length=8,
        choices=enums.Confidentiality.choices,
        default=enums.Confidentiality.NORMAL,
        help_text=_("Unduhan dokumen rahasia hanya dapat disetujui Administrator."),
    )
    template = models.ForeignKey(
        DocumentTemplate,
        verbose_name=_("Templat / format"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="permit_types",
    )
    order = models.PositiveSmallIntegerField(verbose_name=_("Urutan"), default=0)
    is_active = models.BooleanField(verbose_name=_("Aktif"), default=True)

    class Meta:
        verbose_name = _("Jenis dokumen perizinan")
        verbose_name_plural = _("Jenis dokumen perizinan")
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    SCHEME_FLAGS = {
        enums.Scheme.ALLOCATION: "applies_allocation",
        enums.Scheme.LEASE: "applies_lease",
        enums.Scheme.PARTNERSHIP: "applies_partnership",
        enums.Scheme.OTHER: "applies_other",
    }

    @classmethod
    def applicable(cls, scheme: str, sector_id: int | None):
        flag = cls.SCHEME_FLAGS.get(scheme, "applies_other")
        sector_filter = Q(sectors__isnull=True)
        if sector_id:
            sector_filter |= Q(sectors=sector_id)
        return (
            cls.objects.filter(is_active=True, **{flag: True})
            .filter(sector_filter)
            .distinct()
        )


class LandUse(TimeStampedModel):
    """Pemanfaatan lahan: dasar hak tempat dokumen perizinan dikumpulkan."""

    number = models.CharField(
        verbose_name=_("Nomor"), max_length=32, unique=True, editable=False
    )
    title = models.CharField(verbose_name=_("Nama kegiatan / proyek"), max_length=255)
    scheme = models.CharField(
        verbose_name=_("Skema"),
        max_length=16,
        choices=enums.Scheme.choices,
        default=enums.Scheme.OTHER,
    )
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=16,
        choices=enums.LandUseStatus.choices,
        default=enums.LandUseStatus.ACTIVE,
    )
    holder = models.ForeignKey(
        "alokasi.Applicant",
        verbose_name=_("Pemegang hak (akun portal)"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="land_uses",
        help_text=_(
            "Pemegang hak dengan akun portal dapat melihat dan mengunggah dokumennya."
        ),
    )
    holder_name = models.CharField(
        verbose_name=_("Nama pemegang hak"),
        max_length=255,
        blank=True,
        default="",
        help_text=_("Diisi otomatis dari akun portal; isi manual bila tanpa akun."),
    )
    plot = models.ForeignKey(
        "alokasi.LandPlot",
        verbose_name=_("Lahan"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="land_uses",
    )
    allocation = models.OneToOneField(
        "alokasi.Allocation",
        verbose_name=_("Alokasi"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="land_use",
    )
    investment = models.OneToOneField(
        "alokasi.InvestmentRequest",
        verbose_name=_("Permintaan investasi"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="land_use",
    )
    sector = models.ForeignKey(
        "alokasi.InvestmentSector",
        verbose_name=_("Sektor"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="land_uses",
    )
    reference = models.CharField(
        verbose_name=_("Nomor dasar hak / kontrak"),
        max_length=128,
        blank=True,
        default="",
    )
    area_m2 = models.DecimalField(
        verbose_name=_("Luas (m²)"),
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        **AREA,
    )
    start_date = models.DateField(verbose_name=_("Mulai"), null=True, blank=True)
    end_date = models.DateField(verbose_name=_("Berakhir"), null=True, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Petugas penanggung jawab"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    note = models.TextField(verbose_name=_("Catatan internal"), blank=True, default="")

    class Meta:
        verbose_name = _("Pemanfaatan lahan")
        verbose_name_plural = _("Pemanfaatan lahan")
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.number} – {self.title}"

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError(
                {"end_date": _("Tanggal berakhir sebelum tanggal mulai.")}
            )
        if not self.holder_id and not (self.holder_name or "").strip():
            raise ValidationError(
                {
                    "holder_name": _(
                        "Pilih akun pemegang hak atau isi nama pemegang hak."
                    )
                }
            )

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_number("PML")
        if self.holder_id and not self.holder_name:
            self.holder_name = self.holder.name
        super().save(*args, **kwargs)

    @property
    def holder_display(self) -> str:
        return self.holder.name if self.holder_id else self.holder_name

    def progress(self) -> dict:
        """Ringkasan kelengkapan dokumen wajib (dipakai portal, panel, dasbor)."""
        records = list(self.records.select_related("permit_type"))
        required = [r for r in records if r.permit_type.is_required]
        done = [r for r in required if r.status in enums.DONE_RECORD_STATUSES]
        return {
            "total": len(records),
            "required": len(required),
            "done": len(done),
            "percent": round(len(done) * 100 / len(required)) if required else 100,
            "waiting": sum(
                1 for r in records if r.status == enums.RecordStatus.SUBMITTED
            ),
            "revision": sum(
                1 for r in records if r.status == enums.RecordStatus.REVISION
            ),
            "expired": sum(
                1 for r in records if r.status == enums.RecordStatus.EXPIRED
            ),
        }


class PermitRecord(TimeStampedModel):
    """Status satu dokumen perizinan pada satu pemanfaatan lahan."""

    land_use = models.ForeignKey(
        LandUse,
        verbose_name=_("Pemanfaatan lahan"),
        on_delete=models.CASCADE,
        related_name="records",
    )
    permit_type = models.ForeignKey(
        PermitType,
        verbose_name=_("Jenis dokumen"),
        on_delete=models.PROTECT,
        related_name="records",
    )
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=16,
        choices=enums.RecordStatus.choices,
        default=enums.RecordStatus.NOT_STARTED,
    )
    number = models.CharField(
        verbose_name=_("Nomor dokumen / izin"), max_length=128, blank=True, default=""
    )
    issued_date = models.DateField(
        verbose_name=_("Tanggal terbit"), null=True, blank=True
    )
    expiry_date = models.DateField(
        verbose_name=_("Berlaku sampai"), null=True, blank=True
    )
    holder_note = models.TextField(
        verbose_name=_("Catatan pemegang hak"), blank=True, default=""
    )
    review_note = models.TextField(
        verbose_name=_("Catatan petugas"), blank=True, default=""
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Diverifikasi oleh"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    verified_at = models.DateTimeField(
        verbose_name=_("Diverifikasi"), null=True, blank=True
    )
    expiry_warned_for = models.DateField(
        verbose_name=_("Peringatan kedaluwarsa terkirim untuk"),
        null=True,
        blank=True,
        editable=False,
    )

    class Meta:
        verbose_name = _("Dokumen perizinan")
        verbose_name_plural = _("Dokumen perizinan")
        ordering = ["land_use", "permit_type__order", "permit_type__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["land_use", "permit_type"], name="dokumen_unique_record_type"
            )
        ]
        permissions = [
            ("verify_permitrecord", _("Dapat memverifikasi dokumen perizinan"))
        ]

    def __str__(self):
        return f"{self.land_use.number} / {self.permit_type}"

    def clean(self):
        super().clean()
        if (
            self.issued_date
            and self.expiry_date
            and self.expiry_date < self.issued_date
        ):
            raise ValidationError(
                {"expiry_date": _("Masa berlaku berakhir sebelum tanggal terbit.")}
            )

    @property
    def latest_version(self):
        return self.versions.order_by("-number").first()

    @property
    def confidentiality(self) -> str:
        return self.permit_type.confidentiality

    @property
    def days_to_expiry(self) -> int | None:
        if not self.expiry_date:
            return None
        return (self.expiry_date - timezone.localdate()).days

    def default_expiry(self) -> datetime.date | None:
        months = self.permit_type.validity_months
        if self.issued_date and months:
            return _add_months(self.issued_date, months) - datetime.timedelta(days=1)
        return None


class DocumentVersion(models.Model):
    """Satu versi berkas dokumen perizinan (riwayat tidak pernah ditimpa)."""

    record = models.ForeignKey(
        PermitRecord,
        verbose_name=_("Dokumen perizinan"),
        on_delete=models.CASCADE,
        related_name="versions",
    )
    number = models.PositiveIntegerField(verbose_name=_("Versi"))
    file = PrivateFileField(
        verbose_name=_("Berkas"),
        max_length=255,
        upload_to=upload_version,
        validators=DOCUMENT_VALIDATORS,
    )
    original_name = models.CharField(verbose_name=_("Nama berkas"), max_length=255)
    size = models.PositiveBigIntegerField(verbose_name=_("Ukuran (bita)"), default=0)
    sha256 = models.CharField(
        verbose_name=_("Sidik SHA-256"), max_length=64, blank=True, default=""
    )
    source = models.CharField(
        verbose_name=_("Sumber"),
        max_length=16,
        choices=enums.VersionSource.choices,
        default=enums.VersionSource.HOLDER,
    )
    note = models.TextField(verbose_name=_("Keterangan"), blank=True, default="")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Diunggah oleh"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(verbose_name=_("Waktu"), default=timezone.now)

    class Meta:
        verbose_name = _("Versi dokumen")
        verbose_name_plural = _("Versi dokumen")
        ordering = ["record", "-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["record", "number"], name="dokumen_unique_version_number"
            )
        ]

    def __str__(self):
        return f"{self.record} v{self.number}"

    @property
    def extension(self) -> str:
        return (
            self.original_name.rsplit(".", 1)[-1] if "." in self.original_name else ""
        ).lower()


class SigningDocument(TimeStampedModel):
    """Dokumen yang dikirim untuk ditandatangani/disetujui secara elektronik."""

    number = models.CharField(
        verbose_name=_("Nomor"), max_length=32, unique=True, editable=False
    )
    title = models.CharField(verbose_name=_("Judul dokumen"), max_length=255)
    source = models.CharField(
        verbose_name=_("Sumber isi"),
        max_length=8,
        choices=enums.SigningSource.choices,
        default=enums.SigningSource.HTML,
    )
    template = models.ForeignKey(
        DocumentTemplate,
        verbose_name=_("Templat"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signing_documents",
    )
    template_version = models.PositiveIntegerField(
        verbose_name=_("Versi templat"), null=True, blank=True
    )
    land_use = models.ForeignKey(
        LandUse,
        verbose_name=_("Pemanfaatan lahan"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="signing_documents",
    )
    record = models.ForeignKey(
        PermitRecord,
        verbose_name=_("Untuk dokumen perizinan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signing_documents",
        help_text=_(
            "Saat selesai, PDF bertanda tangan menjadi versi baru dokumen ini."
        ),
    )
    body = models.TextField(
        verbose_name=_("Isi dokumen"), blank=True, default="", max_length=MAX_BODY_CHARS
    )
    source_file = PrivateFileField(
        verbose_name=_("Berkas PDF"),
        max_length=255,
        upload_to=upload_signing,
        null=True,
        blank=True,
        validators=PDF_VALIDATORS,
    )
    source_name = models.CharField(
        verbose_name=_("Nama berkas asli"), max_length=255, blank=True, default=""
    )
    content_sha256 = models.CharField(
        verbose_name=_("Sidik isi saat dikirim"), max_length=64, blank=True, default=""
    )
    final_file = PrivateFileField(
        verbose_name=_("PDF bertanda tangan"),
        max_length=255,
        upload_to=upload_signing,
        null=True,
        blank=True,
    )
    final_sha256 = models.CharField(
        verbose_name=_("Sidik PDF final"), max_length=64, blank=True, default=""
    )
    confidentiality = models.CharField(
        verbose_name=_("Sifat dokumen"),
        max_length=8,
        choices=enums.Confidentiality.choices,
        default=enums.Confidentiality.NORMAL,
    )
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=24,
        choices=enums.SigningStatus.choices,
        default=enums.SigningStatus.DRAFT,
    )
    needs_approval = models.BooleanField(
        verbose_name=_("Wajib persetujuan internal sebelum dikirim"), default=False
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Disetujui oleh"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    approved_at = models.DateTimeField(
        verbose_name=_("Disetujui"), null=True, blank=True
    )
    message = models.TextField(
        verbose_name=_("Pesan untuk penerima"), blank=True, default="", max_length=5000
    )
    expires_on = models.DateField(
        verbose_name=_("Batas tanda tangan"), null=True, blank=True
    )
    reminder_every_days = models.PositiveSmallIntegerField(
        verbose_name=_("Pengingat setiap (hari)"),
        default=3,
        validators=[MaxValueValidator(60)],
        help_text=_("0 = tanpa pengingat otomatis."),
    )
    last_reminder_at = models.DateTimeField(
        verbose_name=_("Pengingat terakhir"), null=True, blank=True
    )
    sent_at = models.DateTimeField(verbose_name=_("Dikirim"), null=True, blank=True)
    completed_at = models.DateTimeField(
        verbose_name=_("Selesai"), null=True, blank=True
    )
    closed_reason = models.TextField(
        verbose_name=_("Alasan penolakan / pembatalan"), blank=True, default=""
    )
    verify_token = models.UUIDField(
        verbose_name=_("Kode verifikasi"),
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Dibuat oleh"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = _("Dokumen tanda tangan")
        verbose_name_plural = _("Dokumen tanda tangan")
        ordering = ["-created_at", "-pk"]
        permissions = [
            ("send_signingdocument", _("Dapat mengirim dokumen untuk ditandatangani")),
            ("approve_signingdocument", _("Dapat menyetujui dokumen sebelum dikirim")),
        ]

    def __str__(self):
        return f"{self.number} – {self.title}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_number("DOK")
        super().save(*args, **kwargs)

    @property
    def is_open(self) -> bool:
        return self.status in enums.OPEN_SIGNING_STATUSES

    @property
    def is_final(self) -> bool:
        return self.status in enums.FINAL_SIGNING_STATUSES

    @property
    def is_editable(self) -> bool:
        return self.status == enums.SigningStatus.DRAFT

    def acting_recipients(self):
        """Penerima yang harus bertindak (tanda tangan/setuju), berurutan."""
        return self.recipients.exclude(action=enums.RecipientAction.COPY).order_by(
            "order", "pk"
        )

    def current_order(self) -> int | None:
        """Urutan yang sedang mendapat giliran; None bila semua sudah selesai."""
        pending = self.acting_recipients().exclude(status=enums.RecipientStatus.DONE)
        first = pending.first()
        return first.order if first else None

    def progress(self) -> tuple[int, int]:
        acting = list(self.acting_recipients())
        done = sum(1 for r in acting if r.status == enums.RecipientStatus.DONE)
        return done, len(acting)


class DocumentRecipient(models.Model):
    """Penerima dokumen: penanda tangan, penyetuju, atau penerima salinan."""

    document = models.ForeignKey(
        SigningDocument,
        verbose_name=_("Dokumen"),
        on_delete=models.CASCADE,
        related_name="recipients",
    )
    order = models.PositiveSmallIntegerField(
        verbose_name=_("Urutan"),
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
        help_text=_("Urutan sama = bertindak bersamaan."),
    )
    role = models.CharField(
        verbose_name=_("Peran"), max_length=100, blank=True, default=""
    )
    action = models.CharField(
        verbose_name=_("Tindakan"),
        max_length=16,
        choices=enums.RecipientAction.choices,
        default=enums.RecipientAction.SIGN,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Akun"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="signing_tasks",
        help_text=_("Penerima dengan akun wajib masuk sebelum menandatangani."),
    )
    name = models.CharField(verbose_name=_("Nama"), max_length=255)
    email = models.EmailField(
        verbose_name=_("Surel"),
        blank=True,
        default="",
        help_text=_(
            "Boleh kosong hanya untuk tanda tangan langsung di hadapan petugas."
        ),
    )
    in_person = models.BooleanField(
        verbose_name=_("Tanda tangan langsung"),
        default=False,
        help_text=_(
            "Penerima menandatangani di perangkat petugas setelah identitasnya "
            "diperiksa (mis. warga tanpa surel). Tautan surel tidak dikirim."
        ),
    )
    access_code_hash = models.CharField(
        max_length=128, blank=True, default="", editable=False
    )
    # Posisi cap tanda tangan pada PDF unggahan (persen dari kiri/atas halaman).
    stamp_page = models.SmallIntegerField(
        verbose_name=_("Halaman cap TTD"),
        null=True,
        blank=True,
        validators=[MinValueValidator(-1), MaxValueValidator(999)],
        help_text=_(
            "Khusus PDF unggahan: nomor halaman (1 = pertama, -1 = terakhir). "
            "Kosongkan bila tanda tangan cukup di lembar pengesahan."
        ),
    )
    stamp_x = models.PositiveSmallIntegerField(
        verbose_name=_("Posisi kiri (%)"),
        default=60,
        validators=[MaxValueValidator(95)],
    )
    stamp_y = models.PositiveSmallIntegerField(
        verbose_name=_("Posisi atas (%)"),
        default=80,
        validators=[MaxValueValidator(95)],
    )
    stamp_width = models.PositiveSmallIntegerField(
        verbose_name=_("Lebar cap (%)"),
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(60)],
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=16,
        choices=enums.RecipientStatus.choices,
        default=enums.RecipientStatus.WAITING,
    )
    view_count = models.PositiveIntegerField(
        verbose_name=_("Dibuka"), default=0, editable=False
    )
    last_viewed_at = models.DateTimeField(
        verbose_name=_("Terakhir dibuka"), null=True, blank=True, editable=False
    )
    hosted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Dipandu petugas"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )
    hosted_until = models.DateTimeField(null=True, blank=True, editable=False)
    host_evidence = models.CharField(
        verbose_name=_("Bukti identitas (TTD langsung)"),
        max_length=255,
        blank=True,
        default="",
        editable=False,
    )
    verification_note = models.CharField(
        verbose_name=_("Cara verifikasi"),
        max_length=255,
        blank=True,
        default="",
        editable=False,
    )
    notified_at = models.DateTimeField(
        verbose_name=_("Diberi tahu"), null=True, blank=True
    )
    viewed_at = models.DateTimeField(verbose_name=_("Dilihat"), null=True, blank=True)
    completed_at = models.DateTimeField(
        verbose_name=_("Selesai"), null=True, blank=True
    )
    signature_name = models.CharField(
        verbose_name=_("Nama pada tanda tangan"), max_length=255, blank=True, default=""
    )
    signature_image = models.TextField(
        verbose_name=_("Gambar tanda tangan"), blank=True, default="", editable=False
    )
    decline_reason = models.TextField(
        verbose_name=_("Alasan menolak"), blank=True, default=""
    )
    ip_address = models.GenericIPAddressField(
        verbose_name=_("Alamat IP"), null=True, blank=True
    )
    user_agent = models.CharField(
        verbose_name=_("Peramban"), max_length=255, blank=True, default=""
    )
    otp_hash = models.CharField(max_length=128, blank=True, default="", editable=False)
    otp_expires_at = models.DateTimeField(null=True, blank=True, editable=False)
    otp_attempts = models.PositiveSmallIntegerField(default=0, editable=False)
    otp_verified_at = models.DateTimeField(
        verbose_name=_("Kode verifikasi cocok"), null=True, blank=True, editable=False
    )

    class Meta:
        verbose_name = _("Penerima dokumen")
        verbose_name_plural = _("Penerima dokumen")
        ordering = ["document", "order", "pk"]

    def __str__(self):
        return f"{self.name} ({self.get_action_display()})"

    @property
    def needs_otp(self) -> bool:
        """Kode surel wajib bagi penerima tanpa akun dan penerima berkode akses."""
        return self.user_id is None or bool(self.access_code_hash)

    @property
    def has_access_code(self) -> bool:
        return bool(self.access_code_hash)

    @property
    def is_acting(self) -> bool:
        return self.action != enums.RecipientAction.COPY

    def hosted_for(self, user) -> bool:
        """Sesi tanda tangan langsung yang dibuka ``user`` masih berlaku."""
        return bool(
            user is not None
            and getattr(user, "pk", None)
            and self.hosted_by_id == user.pk
            and self.hosted_until
            and self.hosted_until > timezone.now()
        )


class SigningField(models.Model):
    """Kolom isian yang diisi penerima saat menandatangani (seperti PandaDoc).

    Pada dokumen isian, tempatnya ditandai ``{{ kolom.<kunci> }}``; pada PDF
    unggahan nilainya dicantumkan di lembar pengesahan.
    """

    class Kind(models.TextChoices):
        TEXT = "teks", _("Teks singkat")
        PARAGRAPH = "paragraf", _("Teks panjang")
        DATE = "tanggal", _("Tanggal")
        NUMBER = "angka", _("Angka")
        CHECKBOX = "centang", _("Kotak centang")
        CHOICE = "pilihan", _("Pilihan")
        INITIALS = "paraf", _("Paraf")
        FILE = "berkas", _("Lampiran berkas")

    document = models.ForeignKey(
        SigningDocument,
        verbose_name=_("Dokumen"),
        on_delete=models.CASCADE,
        related_name="fields",
    )
    recipient = models.ForeignKey(
        DocumentRecipient,
        verbose_name=_("Diisi oleh"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fields",
    )
    key = models.CharField(
        verbose_name=_("Kunci"),
        max_length=40,
        validators=[
            RegexValidator(
                r"^[a-z0-9_]{1,40}$",
                _("Gunakan huruf kecil, angka, atau garis bawah."),
            )
        ],
        help_text=_("Ditulis {{ kolom.<kunci> }} di isi dokumen."),
    )
    label = models.CharField(verbose_name=_("Label"), max_length=255)
    kind = models.CharField(
        verbose_name=_("Jenis"), max_length=16, choices=Kind.choices, default=Kind.TEXT
    )
    options = models.TextField(
        verbose_name=_("Pilihan"),
        blank=True,
        default="",
        help_text=_("Untuk jenis Pilihan: satu pilihan per baris."),
    )
    required = models.BooleanField(verbose_name=_("Wajib"), default=True)
    order = models.PositiveSmallIntegerField(verbose_name=_("Urutan"), default=0)
    value = models.TextField(verbose_name=_("Nilai"), blank=True, default="")
    file = PrivateFileField(
        verbose_name=_("Berkas"),
        max_length=255,
        upload_to=upload_field,
        null=True,
        blank=True,
        validators=DOCUMENT_VALIDATORS,
    )
    file_name = models.CharField(
        verbose_name=_("Nama berkas"), max_length=255, blank=True, default=""
    )
    file_sha256 = models.CharField(max_length=64, blank=True, default="")
    filled_at = models.DateTimeField(verbose_name=_("Diisi"), null=True, blank=True)

    class Meta:
        verbose_name = _("Kolom isian penerima")
        verbose_name_plural = _("Kolom isian penerima")
        ordering = ["document", "order", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=("document", "key"), name="dokumen_signingfield_unique_key"
            )
        ]

    def __str__(self):
        return self.label

    @property
    def choices(self) -> list[str]:
        return [line.strip() for line in self.options.splitlines() if line.strip()]

    @property
    def display_value(self) -> str:
        if self.kind == self.Kind.FILE:
            return self.file_name
        if self.kind == self.Kind.CHECKBOX:
            return str(_("Ya")) if self.value == "1" else str(_("Tidak"))
        if self.kind == self.Kind.DATE and self.value:
            try:
                return datetime.date.fromisoformat(self.value).strftime("%d-%m-%Y")
            except ValueError:
                return self.value
        return self.value


class SavedSignature(models.Model):
    """Tanda tangan tersimpan milik akun (aktivasi TTD digital)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Akun"),
        on_delete=models.CASCADE,
        related_name="saved_signature",
    )
    name = models.CharField(verbose_name=_("Nama pada tanda tangan"), max_length=255)
    image = models.TextField(verbose_name=_("Gambar tanda tangan"), editable=False)
    updated_at = models.DateTimeField(verbose_name=_("Diperbarui"), auto_now=True)

    class Meta:
        verbose_name = _("Tanda tangan tersimpan")
        verbose_name_plural = _("Tanda tangan tersimpan")

    def __str__(self):
        return f"{self.name} ({self.user})"


class DocumentComment(models.Model):
    document = models.ForeignKey(
        SigningDocument,
        verbose_name=_("Dokumen"),
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Penulis"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    author_name = models.CharField(verbose_name=_("Nama penulis"), max_length=255)
    body = models.TextField(verbose_name=_("Komentar"), max_length=5000)
    is_internal = models.BooleanField(
        verbose_name=_("Catatan internal (hanya petugas)"), default=False
    )
    created_at = models.DateTimeField(verbose_name=_("Waktu"), default=timezone.now)

    class Meta:
        verbose_name = _("Komentar dokumen")
        verbose_name_plural = _("Komentar dokumen")
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.author_name}: {self.body[:40]}"


class DownloadRequest(models.Model):
    """Permintaan izin mengunduh berkas dokumen (wajib disetujui)."""

    number = models.CharField(
        verbose_name=_("Nomor"), max_length=32, unique=True, editable=False
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Pemohon unduhan"),
        on_delete=models.PROTECT,
        related_name="document_download_requests",
    )
    version = models.ForeignKey(
        DocumentVersion,
        verbose_name=_("Versi dokumen"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="download_requests",
    )
    signing = models.ForeignKey(
        SigningDocument,
        verbose_name=_("Dokumen tanda tangan"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="download_requests",
    )
    confidentiality = models.CharField(
        verbose_name=_("Sifat dokumen"),
        max_length=8,
        choices=enums.Confidentiality.choices,
        default=enums.Confidentiality.NORMAL,
    )
    purpose = models.CharField(
        verbose_name=_("Keperluan"),
        max_length=16,
        choices=enums.DownloadPurpose.choices,
        default=enums.DownloadPurpose.ARCHIVE,
    )
    reason = models.TextField(verbose_name=_("Alasan"), max_length=2000)
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=16,
        choices=enums.DownloadStatus.choices,
        default=enums.DownloadStatus.PENDING,
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Diputuskan oleh"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    decided_at = models.DateTimeField(
        verbose_name=_("Diputuskan"), null=True, blank=True
    )
    decision_note = models.TextField(
        verbose_name=_("Catatan keputusan"), blank=True, default=""
    )
    valid_until = models.DateTimeField(
        verbose_name=_("Berlaku sampai"), null=True, blank=True
    )
    max_downloads = models.PositiveSmallIntegerField(
        verbose_name=_("Batas unduh"),
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
    )
    download_count = models.PositiveSmallIntegerField(
        verbose_name=_("Sudah diunduh"), default=0
    )
    created_at = models.DateTimeField(verbose_name=_("Diajukan"), default=timezone.now)

    class Meta:
        verbose_name = _("Permintaan unduhan")
        verbose_name_plural = _("Permintaan unduhan")
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(version__isnull=False, signing__isnull=True)
                    | Q(version__isnull=True, signing__isnull=False)
                ),
                name="dokumen_download_one_target",
            )
        ]
        permissions = [
            ("approve_downloadrequest", _("Dapat menyetujui permintaan unduhan")),
            (
                "approve_confidential_download",
                _("Dapat menyetujui unduhan dokumen rahasia"),
            ),
        ]

    def __str__(self):
        return f"{self.number} – {self.target_label}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_number("UNH")
        super().save(*args, **kwargs)

    @property
    def target_label(self) -> str:
        if self.version_id:
            return f"{self.version.record.permit_type} v{self.version.number} ({self.version.record.land_use.number})"
        if self.signing_id:
            return f"{self.signing.number} {self.signing.title}"
        return "–"

    @property
    def is_expired(self) -> bool:
        return bool(self.valid_until and self.valid_until < timezone.now())

    @property
    def remaining(self) -> int:
        return max(self.max_downloads - self.download_count, 0)

    @property
    def is_usable(self) -> bool:
        return (
            self.status == enums.DownloadStatus.APPROVED
            and not self.is_expired
            and self.remaining > 0
        )

    @property
    def state_label(self) -> str:
        if self.status == enums.DownloadStatus.APPROVED:
            if self.remaining <= 0:
                return str(_("Kuota habis"))
            if self.is_expired:
                return str(_("Kedaluwarsa"))
        return self.get_status_display()


class DownloadLog(models.Model):
    """Catatan setiap berkas yang diunduh atau dipratinjau."""

    created_at = models.DateTimeField(verbose_name=_("Waktu"), default=timezone.now)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Pengguna"),
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    user_name = models.CharField(verbose_name=_("Nama pengguna"), max_length=255)
    request = models.ForeignKey(
        DownloadRequest,
        verbose_name=_("Permintaan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
    )
    version = models.ForeignKey(
        DocumentVersion,
        verbose_name=_("Versi dokumen"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    signing = models.ForeignKey(
        SigningDocument,
        verbose_name=_("Dokumen tanda tangan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    template = models.ForeignKey(
        DocumentTemplate,
        verbose_name=_("Templat"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    is_preview = models.BooleanField(verbose_name=_("Pratinjau"), default=False)
    filename = models.CharField(verbose_name=_("Nama berkas"), max_length=255)
    sha256 = models.CharField(
        verbose_name=_("Sidik berkas terkirim"), max_length=64, blank=True, default=""
    )
    watermarked = models.BooleanField(verbose_name=_("Bertanda air"), default=False)
    ip_address = models.GenericIPAddressField(
        verbose_name=_("Alamat IP"), null=True, blank=True
    )
    user_agent = models.CharField(
        verbose_name=_("Peramban"), max_length=255, blank=True, default=""
    )

    class Meta:
        verbose_name = _("Riwayat unduhan")
        verbose_name_plural = _("Riwayat unduhan")
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{timezone.localtime(self.created_at):%d-%m-%Y %H.%M} {self.user_name}: {self.filename}"


class Activity(models.Model):
    """Jejak aktivitas modul dokumen (tidak dapat diubah)."""

    created_at = models.DateTimeField(verbose_name=_("Waktu"), default=timezone.now)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Pelaku"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    actor_name = models.CharField(
        verbose_name=_("Nama pelaku"), max_length=255, blank=True, default=""
    )
    action = models.CharField(
        verbose_name=_("Aktivitas"), max_length=24, choices=enums.Action.choices
    )
    land_use = models.ForeignKey(
        LandUse,
        verbose_name=_("Pemanfaatan lahan"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="activities",
    )
    record = models.ForeignKey(
        PermitRecord,
        verbose_name=_("Dokumen perizinan"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="activities",
    )
    signing = models.ForeignKey(
        SigningDocument,
        verbose_name=_("Dokumen tanda tangan"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="activities",
    )
    download = models.ForeignKey(
        DownloadRequest,
        verbose_name=_("Permintaan unduhan"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="activities",
    )
    detail = models.TextField(verbose_name=_("Keterangan"), blank=True, default="")
    ip_address = models.GenericIPAddressField(
        verbose_name=_("Alamat IP"), null=True, blank=True
    )

    class Meta:
        verbose_name = _("Jejak aktivitas dokumen")
        verbose_name_plural = _("Jejak aktivitas dokumen")
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{timezone.localtime(self.created_at):%d-%m-%Y %H.%M} {self.actor_name}: {self.get_action_display()}"


for _model in (
    DocumentSettings,
    ContentBlock,
    DocumentTemplate,
    PermitType,
    LandUse,
    PermitRecord,
    SigningDocument,
):
    auditlog.register(_model)
auditlog.register(
    DocumentRecipient,
    exclude_fields=[
        "signature_image",
        "otp_hash",
        "otp_expires_at",
        "otp_attempts",
        "access_code_hash",
        "view_count",
        "last_viewed_at",
    ],
)
auditlog.register(SigningField, exclude_fields=["value"])
