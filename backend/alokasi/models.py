"""Model modul alokasi lahan: portal pemohon dan panel petugas.

Alur utama:
Lahan tersedia → pemohon mendaftar → permohonan + dokumen → verifikasi teknis
(penilaian berbobot) → disetujui → tagihan UWT & administrasi → pembayaran
terverifikasi → KPT & PPT terbit otomatis → pemegang alokasi melapor progres
perizinan & pembangunan → pemantauan lahan tidur → izin peralihan hak.
"""

import datetime
import uuid
from decimal import ROUND_HALF_UP, Decimal

from auditlog.registry import auditlog
from django.conf import settings
from django.contrib.gis.db import models as gmodels
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from sequences import get_next_value

from alokasi import enums
from file_operations.private_files import PrivateFileField
from leasing.models.mixins import TimeStampedModel
from pengadaan.crypto import EncryptedCharField

MONEY = {"max_digits": 20, "decimal_places": 2}
AREA = {"max_digits": 16, "decimal_places": 2}

UPLOAD_EXTENSIONS = ["pdf", "jpg", "jpeg", "png"]
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def validate_upload_size(value):
    from django.core.exceptions import ValidationError

    if value and value.size > MAX_UPLOAD_BYTES:
        raise ValidationError(_("Ukuran berkas maksimal 10 MB."))


UPLOAD_VALIDATORS = [
    FileExtensionValidator(allowed_extensions=UPLOAD_EXTENSIONS),
    validate_upload_size,
]


def _upload_to(name, prefix):
    def inner(instance, filename):
        return f"alokasi/{prefix}/{timezone.now():%Y/%m}/{uuid.uuid4().hex}/{filename}"

    # Nama harus sama dengan nama variabel modul agar dapat diimpor oleh migrasi.
    inner.__name__ = inner.__qualname__ = name
    return inner


upload_document = _upload_to("upload_document", "dokumen")
upload_info = _upload_to("upload_info", "informasi")
upload_proof = _upload_to("upload_proof", "bukti_bayar")
upload_issued = _upload_to("upload_issued", "terbitan")
upload_report = _upload_to("upload_report", "laporan")
upload_plot = _upload_to("upload_plot", "lahan")


def _next_number(prefix: str) -> str:
    year = timezone.localdate().year
    value = get_next_value(f"alokasi_{prefix.lower()}_{year}")
    return f"{prefix}-{year}-{value:05d}"


class AllocationSettings(models.Model):
    """Pengaturan layanan (satu baris), dapat diubah petugas di /admin/."""

    authority_name = models.CharField(
        verbose_name=_("Nama otoritas"),
        max_length=255,
        default="Instansi Pengelola Lahan",
    )
    authority_short_name = models.CharField(
        verbose_name=_("Singkatan otoritas"), max_length=64, default="Pengelola Lahan"
    )
    city = models.CharField(
        verbose_name=_("Kota penerbitan"), max_length=64, default="Batam"
    )
    signatory_name = models.CharField(
        verbose_name=_("Nama pejabat penandatangan"),
        max_length=255,
        blank=True,
        default="",
    )
    signatory_title = models.CharField(
        verbose_name=_("Jabatan pejabat penandatangan"),
        max_length=255,
        default="Kepala Instansi Pengelola Lahan",
    )
    allocation_admin_fee = models.DecimalField(
        verbose_name=_("Biaya administrasi alokasi (Rp)"), default=Decimal("0"), **MONEY
    )
    transfer_admin_fee = models.DecimalField(
        verbose_name=_("Biaya administrasi peralihan hak, tetap (Rp)"),
        default=Decimal("0"),
        **MONEY,
    )
    transfer_fee_per_m2 = models.DecimalField(
        verbose_name=_("Biaya administrasi peralihan hak per m² (Rp)"),
        default=Decimal("0"),
        **MONEY,
    )
    default_term_years = models.PositiveSmallIntegerField(
        verbose_name=_("Jangka waktu alokasi bawaan (tahun)"), default=30
    )
    passing_score = models.DecimalField(
        verbose_name=_("Nilai minimum verifikasi teknis"),
        max_digits=5,
        decimal_places=2,
        default=Decimal("70"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    invoice_due_days = models.PositiveSmallIntegerField(
        verbose_name=_("Batas waktu pembayaran (hari)"), default=30
    )
    idle_years = models.PositiveSmallIntegerField(
        verbose_name=_("Batas lahan tidur (tahun sejak KPT)"),
        default=2,
        help_text=_(
            "Lahan yang belum dibangun dalam jangka ini ditandai lahan tidur."
        ),
    )
    report_interval_months = models.PositiveSmallIntegerField(
        verbose_name=_("Interval wajib lapor progres (bulan)"), default=6
    )
    payment_instructions = models.TextField(
        verbose_name=_("Petunjuk pembayaran"),
        blank=True,
        default="Pembayaran melalui rekening resmi instansi sesuai nomor tagihan.",
    )
    contact_info = models.TextField(
        verbose_name=_("Kontak layanan"), blank=True, default=""
    )

    class Meta:
        verbose_name = _("Pengaturan layanan alokasi")
        verbose_name_plural = _("Pengaturan layanan alokasi")

    def __str__(self):
        return str(self._meta.verbose_name)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "AllocationSettings":
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj


class LandPlot(TimeStampedModel):
    """Lahan yang ditawarkan untuk dialokasikan."""

    code = models.CharField(
        verbose_name=_("Kode lahan"),
        max_length=32,
        unique=True,
        blank=True,
        help_text=_("Dikosongkan untuk dibuat otomatis."),
    )
    name = models.CharField(verbose_name=_("Nama / lokasi"), max_length=255)
    allocation_type = models.CharField(
        verbose_name=_("Jenis alokasi"),
        max_length=16,
        choices=enums.AllocationType.choices,
        default=enums.AllocationType.REGULAR,
    )
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=16,
        choices=enums.PlotStatus.choices,
        default=enums.PlotStatus.AVAILABLE,
    )
    district = models.CharField(
        verbose_name=_("Kecamatan"), max_length=128, blank=True, default=""
    )
    village = models.CharField(
        verbose_name=_("Kelurahan"), max_length=128, blank=True, default=""
    )
    address = models.CharField(
        verbose_name=_("Alamat / patokan"), max_length=255, blank=True, default=""
    )
    area_m2 = models.DecimalField(verbose_name=_("Luas (m²)"), **AREA)
    zoning = models.CharField(
        verbose_name=_("Peruntukan (RTRW/RDTR)"), max_length=255, blank=True, default=""
    )
    intended_use = models.CharField(
        verbose_name=_("Arahan pemanfaatan"), max_length=255, blank=True, default=""
    )
    uwt_rate_per_m2_year = models.DecimalField(
        verbose_name=_("Tarif UWT per m² per tahun (Rp)"), default=Decimal("0"), **MONEY
    )
    term_years = models.PositiveSmallIntegerField(
        verbose_name=_("Jangka waktu alokasi (tahun)"),
        null=True,
        blank=True,
        help_text=_("Kosongkan untuk memakai jangka waktu bawaan."),
    )
    has_technical_documents = models.BooleanField(
        verbose_name=_("Dokumen teknis tersedia"), default=False
    )
    land_preparation_done = models.BooleanField(
        verbose_name=_("Pematangan lahan selesai"), default=False
    )
    infrastructure = models.TextField(
        verbose_name=_("Sarana & prasarana"), blank=True, default=""
    )
    description = models.TextField(verbose_name=_("Keterangan"), blank=True, default="")
    geometry = gmodels.MultiPolygonField(
        verbose_name=_("Batas lahan"), srid=4326, null=True, blank=True
    )
    photo = PrivateFileField(
        max_length=255,
        verbose_name=_("Foto"),
        upload_to=upload_plot,
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png"]),
            validate_upload_size,
        ],
    )
    is_published = models.BooleanField(verbose_name=_("Tampil di portal"), default=True)

    class Meta:
        verbose_name = _("Lahan")
        verbose_name_plural = _("Lahan")
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.name}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"LHN-{get_next_value('alokasi_lahan'):05d}"
        super().save(*args, **kwargs)

    @property
    def effective_term_years(self) -> int:
        return self.term_years or AllocationSettings.load().default_term_years

    @property
    def uwt_total(self) -> Decimal:
        return (
            self.area_m2 * self.uwt_rate_per_m2_year * self.effective_term_years
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    @property
    def is_open_for_application(self) -> bool:
        return self.is_published and self.status == enums.PlotStatus.AVAILABLE


class InfoPage(TimeStampedModel):
    """Konten informasi portal: regulasi, persyaratan, prosedur, pengumuman, tutorial."""

    category = models.CharField(
        verbose_name=_("Kategori"), max_length=16, choices=enums.InfoCategory.choices
    )
    title = models.CharField(verbose_name=_("Judul"), max_length=255)
    slug = models.SlugField(
        verbose_name=_("Slug"), max_length=255, unique=True, blank=True
    )
    summary = models.CharField(
        verbose_name=_("Ringkasan"), max_length=500, blank=True, default=""
    )
    body = models.TextField(verbose_name=_("Isi"), blank=True, default="")
    video_url = models.URLField(
        verbose_name=_("Tautan video (YouTube)"), blank=True, default=""
    )
    attachment = PrivateFileField(
        max_length=255,
        verbose_name=_("Lampiran"),
        upload_to=upload_info,
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(
                ["pdf", "doc", "docx", "xls", "xlsx", "jpg", "jpeg", "png", "zip"]
            ),
            validate_upload_size,
        ],
    )
    order = models.PositiveIntegerField(verbose_name=_("Urutan"), default=0)
    is_published = models.BooleanField(verbose_name=_("Terbit"), default=True)
    published_at = models.DateField(
        verbose_name=_("Tanggal terbit"), default=datetime.date.today
    )

    class Meta:
        verbose_name = _("Konten informasi")
        verbose_name_plural = _("Konten informasi")
        ordering = ["category", "order", "-published_at", "title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or "informasi"
            slug = base
            n = 2
            while InfoPage.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def youtube_embed_url(self) -> str:
        """URL embed YouTube dari tautan biasa; kosong bila bukan YouTube."""
        from urllib.parse import parse_qs, urlparse

        if not self.video_url:
            return ""
        url = urlparse(self.video_url)
        host = (url.hostname or "").lower()
        video_id = ""
        if host in ("youtu.be", "www.youtu.be"):
            video_id = url.path.lstrip("/").split("/")[0]
        elif host.endswith("youtube.com"):
            if url.path == "/watch":
                video_id = parse_qs(url.query).get("v", [""])[0]
            elif url.path.startswith(("/embed/", "/shorts/", "/live/")):
                video_id = url.path.split("/")[2]
        if not video_id or not all(c.isalnum() or c in "-_" for c in video_id):
            return ""
        return f"https://www.youtube-nocookie.com/embed/{video_id}"


class Applicant(TimeStampedModel):
    """Profil pemohon (akun portal). Pemohon tidak pernah menjadi anggota grup petugas."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Akun"),
        on_delete=models.CASCADE,
        related_name="pemohon",
    )
    applicant_type = models.CharField(
        verbose_name=_("Jenis pemohon"),
        max_length=16,
        choices=enums.ApplicantType.choices,
        default=enums.ApplicantType.COMPANY,
    )
    name = models.CharField(
        verbose_name=_("Nama pemohon / badan usaha"), max_length=255
    )
    nib = models.CharField(verbose_name=_("NIB"), max_length=32, blank=True, default="")
    npwp = models.CharField(
        verbose_name=_("NPWP"), max_length=32, blank=True, default=""
    )
    nik = EncryptedCharField(
        verbose_name=_("NIK penanggung jawab"), blank=True, default=""
    )
    pic_name = models.CharField(verbose_name=_("Nama penanggung jawab"), max_length=255)
    pic_position = models.CharField(
        verbose_name=_("Jabatan penanggung jawab"),
        max_length=255,
        blank=True,
        default="",
    )
    phone = models.CharField(verbose_name=_("Telepon"), max_length=32)
    address = models.TextField(verbose_name=_("Alamat"))
    city = models.CharField(
        verbose_name=_("Kota"), max_length=128, blank=True, default=""
    )

    class Meta:
        verbose_name = _("Pemohon")
        verbose_name_plural = _("Pemohon")
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def email(self) -> str:
        return self.user.email


class RequirementDocType(models.Model):
    """Jenis dokumen persyaratan yang diunggah pemohon."""

    service_type = models.CharField(
        verbose_name=_("Layanan"), max_length=16, choices=enums.ServiceType.choices
    )
    allocation_type = models.CharField(
        verbose_name=_("Khusus jenis alokasi"),
        max_length=16,
        choices=enums.AllocationType.choices,
        blank=True,
        default="",
        help_text=_("Kosongkan bila berlaku untuk semua jenis alokasi."),
    )
    name = models.CharField(verbose_name=_("Nama dokumen"), max_length=255)
    description = models.TextField(verbose_name=_("Keterangan"), blank=True, default="")
    is_required = models.BooleanField(verbose_name=_("Wajib"), default=True)
    order = models.PositiveIntegerField(verbose_name=_("Urutan"), default=0)
    is_active = models.BooleanField(verbose_name=_("Aktif"), default=True)

    class Meta:
        verbose_name = _("Jenis dokumen persyaratan")
        verbose_name_plural = _("Jenis dokumen persyaratan")
        ordering = ["service_type", "order", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_service_type_display()})"

    @classmethod
    def for_application(cls, application: "Application"):
        qs = cls.objects.filter(is_active=True, service_type=application.service_type)
        if (
            application.service_type == enums.ServiceType.ALLOCATION
            and application.plot_id
        ):
            qs = qs.filter(
                models.Q(allocation_type="")
                | models.Q(allocation_type=application.plot.allocation_type)
            )
        return qs


class VerificationCriterion(models.Model):
    """Kriteria penilaian Tim Verifikasi Teknis."""

    name = models.CharField(verbose_name=_("Kriteria"), max_length=255)
    description = models.TextField(verbose_name=_("Keterangan"), blank=True, default="")
    weight = models.DecimalField(
        verbose_name=_("Bobot (%)"),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(100)],
    )
    order = models.PositiveIntegerField(verbose_name=_("Urutan"), default=0)
    is_active = models.BooleanField(verbose_name=_("Aktif"), default=True)

    class Meta:
        verbose_name = _("Kriteria verifikasi teknis")
        verbose_name_plural = _("Kriteria verifikasi teknis")
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.name} ({self.weight}%)"


class Application(TimeStampedModel):
    """Permohonan layanan: alokasi tanah atau izin peralihan hak."""

    number = models.CharField(
        verbose_name=_("Nomor"), max_length=32, unique=True, editable=False
    )
    service_type = models.CharField(
        verbose_name=_("Layanan"), max_length=16, choices=enums.ServiceType.choices
    )
    applicant = models.ForeignKey(
        Applicant,
        verbose_name=_("Pemohon"),
        on_delete=models.PROTECT,
        related_name="applications",
    )
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=16,
        choices=enums.ApplicationStatus.choices,
        default=enums.ApplicationStatus.DRAFT,
    )
    # --- Alokasi tanah ---
    plot = models.ForeignKey(
        LandPlot,
        verbose_name=_("Lahan"),
        on_delete=models.PROTECT,
        related_name="applications",
        null=True,
        blank=True,
    )
    activity = models.CharField(
        verbose_name=_("Rencana kegiatan / pemanfaatan"),
        max_length=255,
        blank=True,
        default="",
    )
    investment_value = models.DecimalField(
        verbose_name=_("Nilai investasi (Rp)"), null=True, blank=True, **MONEY
    )
    workforce = models.PositiveIntegerField(
        verbose_name=_("Rencana tenaga kerja (orang)"), null=True, blank=True
    )
    development_months = models.PositiveIntegerField(
        verbose_name=_("Rencana jangka waktu pembangunan (bulan)"),
        null=True,
        blank=True,
    )
    description = models.TextField(
        verbose_name=_("Uraian rencana usaha"), blank=True, default=""
    )
    # --- Peralihan hak ---
    source_allocation = models.ForeignKey(
        "Allocation",
        verbose_name=_("Alokasi yang dialihkan"),
        on_delete=models.PROTECT,
        related_name="transfer_applications",
        null=True,
        blank=True,
    )
    recipient = models.ForeignKey(
        Applicant,
        verbose_name=_("Penerima hak"),
        on_delete=models.PROTECT,
        related_name="incoming_transfers",
        null=True,
        blank=True,
    )
    transfer_reason = models.TextField(
        verbose_name=_("Alasan / dasar peralihan"), blank=True, default=""
    )
    # --- Proses ---
    submitted_at = models.DateTimeField(
        verbose_name=_("Tanggal diajukan"), null=True, blank=True
    )
    decided_at = models.DateTimeField(
        verbose_name=_("Tanggal keputusan"), null=True, blank=True
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Diputuskan oleh"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    officer_note = models.TextField(
        verbose_name=_("Catatan petugas untuk pemohon"), blank=True, default=""
    )
    score = models.DecimalField(
        verbose_name=_("Nilai verifikasi teknis"),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("Permohonan")
        verbose_name_plural = _("Permohonan")
        ordering = ["-created_at"]
        permissions = [
            ("verify_application", _("Dapat menilai verifikasi teknis")),
            ("decide_application", _("Dapat memproses dan memutuskan permohonan")),
        ]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        if not self.number:
            prefix = (
                "ALK" if self.service_type == enums.ServiceType.ALLOCATION else "PRL"
            )
            self.number = _next_number(prefix)
        super().save(*args, **kwargs)

    @property
    def is_editable(self) -> bool:
        return self.status in enums.EDITABLE_STATUSES

    @property
    def is_allocation(self) -> bool:
        return self.service_type == enums.ServiceType.ALLOCATION

    @property
    def area_m2(self) -> Decimal | None:
        if self.is_allocation:
            return self.plot.area_m2 if self.plot_id else None
        return self.source_allocation.area_m2 if self.source_allocation_id else None

    def missing_required_documents(self):
        uploaded = set(self.documents.values_list("doc_type_id", flat=True))
        return [
            d
            for d in RequirementDocType.for_application(self)
            if d.is_required and d.pk not in uploaded
        ]

    def compute_score(self) -> Decimal | None:
        """Rata-rata nilai antarverifikator per kriteria, lalu dibobot.

        Mengembalikan None bila masih ada kriteria aktif yang belum dinilai.
        """
        criteria = list(VerificationCriterion.objects.filter(is_active=True))
        if not criteria:
            return None
        total_weight = Decimal("0")
        total = Decimal("0")
        for criterion in criteria:
            scores = [
                s.score for s in self.scores.all() if s.criterion_id == criterion.pk
            ]
            if not scores:
                return None
            average = sum(scores, Decimal("0")) / len(scores)
            total += average * criterion.weight
            total_weight += criterion.weight
        return (total / total_weight).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ApplicationDocument(TimeStampedModel):
    application = models.ForeignKey(
        Application,
        verbose_name=_("Permohonan"),
        on_delete=models.CASCADE,
        related_name="documents",
    )
    doc_type = models.ForeignKey(
        RequirementDocType,
        verbose_name=_("Jenis dokumen"),
        on_delete=models.PROTECT,
        related_name="+",
    )
    file = PrivateFileField(
        max_length=255,
        verbose_name=_("Berkas"),
        upload_to=upload_document,
        validators=UPLOAD_VALIDATORS,
    )
    original_name = models.CharField(
        verbose_name=_("Nama berkas"), max_length=255, blank=True, default=""
    )

    class Meta:
        verbose_name = _("Dokumen permohonan")
        verbose_name_plural = _("Dokumen permohonan")
        ordering = ["doc_type__order", "created_at"]

    def __str__(self):
        return f"{self.application} – {self.doc_type.name}"


class VerificationScore(TimeStampedModel):
    application = models.ForeignKey(
        Application,
        verbose_name=_("Permohonan"),
        on_delete=models.CASCADE,
        related_name="scores",
    )
    criterion = models.ForeignKey(
        VerificationCriterion,
        verbose_name=_("Kriteria"),
        on_delete=models.PROTECT,
        related_name="scores",
    )
    verifier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Verifikator"),
        on_delete=models.PROTECT,
        related_name="+",
    )
    score = models.DecimalField(
        verbose_name=_("Nilai (0–100)"),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    note = models.TextField(verbose_name=_("Catatan"), blank=True, default="")

    class Meta:
        verbose_name = _("Nilai verifikasi teknis")
        verbose_name_plural = _("Nilai verifikasi teknis")
        constraints = [
            models.UniqueConstraint(
                fields=["application", "criterion", "verifier"],
                name="alokasi_unique_score_per_verifier",
            )
        ]

    def __str__(self):
        return f"{self.application} / {self.criterion.name}: {self.score}"


class ApplicationEvent(models.Model):
    """Riwayat status permohonan yang terlihat oleh pemohon."""

    application = models.ForeignKey(
        Application,
        verbose_name=_("Permohonan"),
        on_delete=models.CASCADE,
        related_name="events",
    )
    status = models.CharField(
        verbose_name=_("Status"), max_length=16, choices=enums.ApplicationStatus.choices
    )
    note = models.TextField(verbose_name=_("Catatan"), blank=True, default="")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Oleh"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(verbose_name=_("Waktu"), default=timezone.now)

    class Meta:
        verbose_name = _("Riwayat permohonan")
        verbose_name_plural = _("Riwayat permohonan")
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.application} {self.get_status_display()}"


class Invoice(TimeStampedModel):
    """Tagihan (UWT, administrasi alokasi, administrasi peralihan)."""

    number = models.CharField(
        verbose_name=_("Nomor tagihan"), max_length=32, unique=True, editable=False
    )
    application = models.ForeignKey(
        Application,
        verbose_name=_("Permohonan"),
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    kind = models.CharField(
        verbose_name=_("Jenis"), max_length=16, choices=enums.InvoiceKind.choices
    )
    description = models.CharField(verbose_name=_("Uraian"), max_length=500)
    amount = models.DecimalField(verbose_name=_("Jumlah (Rp)"), **MONEY)
    due_date = models.DateField(verbose_name=_("Jatuh tempo"))
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=24,
        choices=enums.InvoiceStatus.choices,
        default=enums.InvoiceStatus.UNPAID,
    )
    payment_proof = PrivateFileField(
        max_length=255,
        verbose_name=_("Bukti pembayaran"),
        upload_to=upload_proof,
        null=True,
        blank=True,
        validators=UPLOAD_VALIDATORS,
    )
    proof_uploaded_at = models.DateTimeField(
        verbose_name=_("Bukti diunggah"), null=True, blank=True
    )
    paid_at = models.DateTimeField(
        verbose_name=_("Tanggal lunas"), null=True, blank=True
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Diverifikasi oleh"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    note = models.TextField(verbose_name=_("Catatan petugas"), blank=True, default="")

    class Meta:
        verbose_name = _("Tagihan")
        verbose_name_plural = _("Tagihan")
        ordering = ["-created_at"]
        permissions = [("verify_payment", _("Dapat memverifikasi pembayaran"))]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = _next_number("TGH")
        super().save(*args, **kwargs)

    @property
    def is_overdue(self) -> bool:
        return (
            self.status
            in (enums.InvoiceStatus.UNPAID, enums.InvoiceStatus.PROOF_UPLOADED)
            and self.due_date < timezone.localdate()
        )


class Allocation(TimeStampedModel):
    """Hasil alokasi: hak pemanfaatan lahan berdasarkan KPT dan PPT."""

    application = models.OneToOneField(
        Application,
        verbose_name=_("Permohonan asal"),
        on_delete=models.PROTECT,
        related_name="allocation",
    )
    plot = models.ForeignKey(
        LandPlot,
        verbose_name=_("Lahan"),
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    holder = models.ForeignKey(
        Applicant,
        verbose_name=_("Pemegang alokasi"),
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    kpt_number = models.CharField(
        verbose_name=_("Nomor KPT"), max_length=64, unique=True
    )
    ppt_number = models.CharField(
        verbose_name=_("Nomor PPT"), max_length=64, unique=True
    )
    issued_date = models.DateField(verbose_name=_("Tanggal terbit"))
    start_date = models.DateField(verbose_name=_("Mulai berlaku"))
    end_date = models.DateField(verbose_name=_("Berakhir"))
    area_m2 = models.DecimalField(verbose_name=_("Luas (m²)"), **AREA)
    activity = models.CharField(verbose_name=_("Peruntukan / kegiatan"), max_length=255)
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=16,
        choices=enums.AllocationStatus.choices,
        default=enums.AllocationStatus.ACTIVE,
    )
    revoked_at = models.DateTimeField(
        verbose_name=_("Dicabut pada"), null=True, blank=True
    )
    revoke_reason = models.TextField(
        verbose_name=_("Alasan pencabutan"), blank=True, default=""
    )

    class Meta:
        verbose_name = _("Alokasi lahan")
        verbose_name_plural = _("Alokasi lahan")
        ordering = ["-issued_date", "-pk"]
        permissions = [("revoke_allocation", _("Dapat mencabut alokasi lahan"))]

    def __str__(self):
        return f"{self.kpt_number} – {self.holder}"

    @property
    def idle_deadline(self) -> datetime.date:
        years = AllocationSettings.load().idle_years
        try:
            return self.start_date.replace(year=self.start_date.year + years)
        except ValueError:  # 29 Februari
            return self.start_date.replace(year=self.start_date.year + years, day=28)

    @property
    def has_started_development(self) -> bool:
        return self.development_reports.filter(
            stage__in=(
                enums.DevelopmentStage.CONSTRUCTION,
                enums.DevelopmentStage.OPERATIONAL,
            )
        ).exists()

    @property
    def is_idle(self) -> bool:
        """Lahan tidur: aktif, lewat batas waktu, dan pembangunan belum dimulai."""
        return (
            self.status == enums.AllocationStatus.ACTIVE
            and timezone.localdate() >= self.idle_deadline
            and not self.has_started_development
        )

    @property
    def last_report_date(self) -> datetime.date | None:
        report = self.development_reports.order_by("-report_date").first()
        return report.report_date if report else None

    @property
    def latest_progress(self) -> int:
        report = self.development_reports.order_by("-report_date", "-pk").first()
        return report.progress_percent if report else 0


class IssuedDocument(models.Model):
    """Dokumen yang diterbitkan sistem (KPT, PPT, izin peralihan hak)."""

    KIND_CHOICES = (
        ("kpt", _("Keputusan Pengalokasian Tanah (KPT)")),
        ("ppt", _("Perjanjian Pemanfaatan Tanah (PPT)")),
        ("iph", _("Surat Izin Persetujuan Peralihan Hak Atas Tanah")),
    )

    kind = models.CharField(verbose_name=_("Jenis"), max_length=8, choices=KIND_CHOICES)
    number = models.CharField(verbose_name=_("Nomor"), max_length=64, unique=True)
    application = models.ForeignKey(
        Application,
        verbose_name=_("Permohonan"),
        on_delete=models.PROTECT,
        related_name="issued_documents",
    )
    allocation = models.ForeignKey(
        Allocation,
        verbose_name=_("Alokasi"),
        on_delete=models.PROTECT,
        related_name="issued_documents",
    )
    holder_name = models.CharField(verbose_name=_("Atas nama"), max_length=255)
    file = PrivateFileField(
        verbose_name=_("Berkas PDF"), max_length=255, upload_to=upload_issued
    )
    token = models.UUIDField(
        verbose_name=_("Kode verifikasi"),
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    issued_at = models.DateTimeField(
        verbose_name=_("Diterbitkan"), default=timezone.now
    )

    class Meta:
        verbose_name = _("Dokumen terbit")
        verbose_name_plural = _("Dokumen terbit")
        ordering = ["-issued_at", "kind"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.number}"


class PermitReport(TimeStampedModel):
    """Progres perizinan pemegang alokasi (satu baris per jenis izin)."""

    allocation = models.ForeignKey(
        Allocation,
        verbose_name=_("Alokasi"),
        on_delete=models.CASCADE,
        related_name="permit_reports",
    )
    permit_type = models.CharField(
        verbose_name=_("Jenis izin"), max_length=16, choices=enums.PermitType.choices
    )
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=16,
        choices=enums.PermitStatus.choices,
        default=enums.PermitStatus.NOT_STARTED,
    )
    permit_number = models.CharField(
        verbose_name=_("Nomor izin"), max_length=128, blank=True, default=""
    )
    issued_date = models.DateField(
        verbose_name=_("Tanggal terbit"), null=True, blank=True
    )
    document = PrivateFileField(
        max_length=255,
        verbose_name=_("Dokumen izin"),
        upload_to=upload_report,
        null=True,
        blank=True,
        validators=UPLOAD_VALIDATORS,
    )
    note = models.TextField(verbose_name=_("Keterangan"), blank=True, default="")

    class Meta:
        verbose_name = _("Laporan perizinan")
        verbose_name_plural = _("Laporan perizinan")
        ordering = ["allocation", "permit_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["allocation", "permit_type"], name="alokasi_unique_permit_type"
            )
        ]

    def __str__(self):
        return f"{self.allocation} / {self.get_permit_type_display()}"


class DevelopmentReport(TimeStampedModel):
    """Laporan berkala progres pembangunan di lahan yang dialokasikan."""

    allocation = models.ForeignKey(
        Allocation,
        verbose_name=_("Alokasi"),
        on_delete=models.CASCADE,
        related_name="development_reports",
    )
    report_date = models.DateField(
        verbose_name=_("Tanggal laporan"), default=datetime.date.today
    )
    stage = models.CharField(
        verbose_name=_("Tahap"), max_length=16, choices=enums.DevelopmentStage.choices
    )
    progress_percent = models.PositiveSmallIntegerField(
        verbose_name=_("Progres fisik (%)"), validators=[MaxValueValidator(100)]
    )
    realized_investment = models.DecimalField(
        verbose_name=_("Realisasi investasi (Rp)"), null=True, blank=True, **MONEY
    )
    workforce = models.PositiveIntegerField(
        verbose_name=_("Tenaga kerja saat ini"), null=True, blank=True
    )
    description = models.TextField(verbose_name=_("Uraian kegiatan"))
    photo = PrivateFileField(
        max_length=255,
        verbose_name=_("Foto / dokumen pendukung"),
        upload_to=upload_report,
        null=True,
        blank=True,
        validators=UPLOAD_VALIDATORS,
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Dilaporkan oleh"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = _("Laporan pembangunan")
        verbose_name_plural = _("Laporan pembangunan")
        ordering = ["-report_date", "-pk"]

    def __str__(self):
        return f"{self.allocation} {self.report_date:%d-%m-%Y} {self.progress_percent}%"


for _model in (
    AllocationSettings,
    LandPlot,
    InfoPage,
    Applicant,
    RequirementDocType,
    VerificationCriterion,
    Application,
    ApplicationDocument,
    VerificationScore,
    Invoice,
    Allocation,
    IssuedDocument,
    PermitReport,
    DevelopmentReport,
):
    auditlog.register(_model)
