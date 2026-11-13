"""Model modul alokasi lahan: portal pemohon dan panel petugas.

Alur utama:
Lahan tersedia → pemohon mendaftar → permohonan + dokumen → verifikasi teknis
(penilaian berbobot) → disetujui → tagihan UWT & administrasi → pembayaran
terverifikasi → KPT & PPT terbit otomatis → pemegang alokasi melapor progres
perizinan & pembangunan → pemantauan lahan tidur → izin peralihan hak.
"""

import datetime
import secrets
import uuid
from decimal import ROUND_HALF_UP, Decimal

from auditlog.registry import auditlog
from django.conf import settings
from django.contrib.gis.db import models as gmodels
from django.core.exceptions import ValidationError
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
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
upload_zone = _upload_to("upload_zone", "kawasan")
upload_investment = _upload_to("upload_investment", "investasi")
upload_letterhead = _upload_to("upload_letterhead", "kop")


def _next_number(prefix: str) -> str:
    year = timezone.localdate().year
    value = get_next_value(f"alokasi_{prefix.lower()}_{year}")
    return f"{prefix}-{year}-{value:05d}"


# Jangka waktu dalam tahun; batas atas mencegah tanggal berakhir melewati
# kalender (tahun 9999) yang membuat proses penerbitan gagal.
MAX_TERM_YEARS = 99


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
    extension_admin_fee = models.DecimalField(
        verbose_name=_("Biaya administrasi perpanjangan/pembaruan hak (Rp)"),
        default=Decimal("0"),
        **MONEY,
    )
    service_admin_fee = models.DecimalField(
        verbose_name=_("Biaya administrasi pecah PL / pengukuran ulang (Rp)"),
        default=Decimal("0"),
        **MONEY,
    )
    default_term_years = models.PositiveSmallIntegerField(
        verbose_name=_("Jangka waktu alokasi bawaan (tahun)"),
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_TERM_YEARS)],
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
        validators=[MaxValueValidator(MAX_TERM_YEARS)],
        help_text=_("Lahan yang belum dibangun dalam jangka ini ditandai lahan tidur."),
    )
    report_interval_months = models.PositiveSmallIntegerField(
        verbose_name=_("Interval wajib lapor progres (bulan)"), default=6
    )
    letterhead_logo = PrivateFileField(
        max_length=255,
        verbose_name=_("Logo kop surat"),
        upload_to=upload_letterhead,
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(["png", "jpg", "jpeg"]),
            validate_upload_size,
        ],
        help_text=_("Tampil di kop semua PDF (KPT, PPT, PL, surat, dokumen e-sign)."),
    )
    letterhead_lines = models.TextField(
        verbose_name=_("Baris kop surat"),
        blank=True,
        default="",
        help_text=_("Di bawah nama otoritas, mis. alamat, telepon, surel, situs."),
    )
    payment_instructions = models.TextField(
        verbose_name=_("Petunjuk pembayaran"),
        blank=True,
        default="Pembayaran melalui rekening resmi instansi sesuai nomor tagihan.",
    )
    contact_info = models.TextField(
        verbose_name=_("Kontak layanan"), blank=True, default=""
    )
    investment_intro = models.TextField(
        verbose_name=_("Pengantar portal investasi"),
        blank=True,
        default=(
            "Temukan lahan siap investasi, bandingkan skema sewa dan alokasi, lalu "
            "ajukan minat secara daring. Petugas mendampingi sejak konsultasi hingga "
            "kontrak."
        ),
    )
    investment_contact = models.TextField(
        verbose_name=_("Kontak layanan investasi"),
        blank=True,
        default="",
        help_text=_(
            "Ditampilkan di portal investasi. Kosongkan untuk memakai kontak layanan."
        ),
    )
    # Kontak Kami & kaki halaman portal
    office_hours = models.CharField(
        verbose_name=_("Jam layanan"),
        max_length=255,
        blank=True,
        default="Senin–Jumat, 08.00–16.00 WIB",
    )
    contact_email = models.EmailField(
        verbose_name=_("Surel layanan"),
        blank=True,
        default="",
        help_text=_("Pesan dari formulir Kontak Kami juga diteruskan ke surel ini."),
    )
    contact_whatsapp = models.TextField(
        verbose_name=_("Kanal WhatsApp"),
        blank=True,
        default="",
        help_text=_("Satu kanal per baris: Label: nomor (mis. Konsultasi: 0811…)."),
    )
    social_links = models.TextField(
        verbose_name=_("Media sosial"),
        blank=True,
        default="",
        help_text=_("Satu tautan per baris: Label: https://…"),
    )
    # Simulasi biaya UWT
    uwt_penalty_percent = models.DecimalField(
        verbose_name=_("Denda keterlambatan UWT per bulan (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal("2"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    uwt_penalty_max_months = models.PositiveSmallIntegerField(
        verbose_name=_("Batas bulan denda UWT"),
        default=24,
        validators=[MaxValueValidator(600)],
        help_text=_("0 = tanpa batas."),
    )
    publish_open_winners = models.BooleanField(
        verbose_name=_("Umumkan pemenang alokasi terbuka"),
        default=True,
        help_text=_(
            "Tampilkan hasil lelang/seleksi alokasi terbuka (pemenang dan peserta) "
            "di portal."
        ),
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

    @property
    def letterhead_logo_data_uri(self) -> str:
        """Logo kop sebagai data URI untuk xhtml2pdf (kosong bila tidak ada)."""
        import base64
        import mimetypes

        if not self.letterhead_logo:
            return ""
        try:
            with self.letterhead_logo.open("rb") as handle:
                data = handle.read()
        except Exception:  # noqa: BLE001 - berkas hilang/belum dipindai
            return ""
        mime = mimetypes.guess_type(self.letterhead_logo.name)[0] or "image/png"
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"

    @property
    def letterhead_line_list(self) -> list[str]:
        return [
            line.strip() for line in self.letterhead_lines.splitlines() if line.strip()
        ]

    @staticmethod
    def _pairs(text: str) -> list[tuple[str, str]]:
        pairs = []
        for line in (text or "").splitlines():
            label, sep, value = line.partition(":")
            if not sep:
                label, value = "", line
            label, value = label.strip(), value.strip()
            if value:
                pairs.append((label or value, value))
        return pairs

    @property
    def whatsapp_channels(self) -> list[dict]:
        """Kanal WhatsApp dengan tautan wa.me (nomor dinormalkan ke 62…)."""
        channels = []
        for label, number in self._pairs(self.contact_whatsapp):
            digits = "".join(c for c in number if c.isdigit())
            if digits.startswith("0"):
                digits = "62" + digits[1:]
            if digits:
                channels.append(
                    {"label": label, "number": number, "url": f"https://wa.me/{digits}"}
                )
        return channels

    @property
    def social_channels(self) -> list[dict]:
        # Label sebelum titik dua pertama; "https://" di nilai tetap utuh.
        links = []
        for line in (self.social_links or "").splitlines():
            line = line.strip()
            if not line:
                continue
            label, sep, url = line.partition(": ")
            if not sep:
                label, url = "", line
            url = url.strip()
            if url.startswith(("https://", "http://")):
                links.append({"label": label.strip() or url, "url": url})
        return links


HEX_COLOR = RegexValidator(
    r"^#[0-9a-fA-F]{6}$", _("Gunakan kode warna heksadesimal, mis. #0d7e74.")
)
# Batas usulan luas/jarak agar nilai yang salah ketik tidak merusak perhitungan.
MAX_DISTANCE_KM = Decimal("9999")


def _unique_slug(instance, source: str, max_length: int = 80) -> str:
    base = slugify(source)[: max_length - 6] or "item"
    slug = base
    n = 2
    model = type(instance)
    while model.objects.filter(slug=slug).exclude(pk=instance.pk).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


class InvestmentSector(models.Model):
    """Sektor usaha untuk mengelompokkan lahan di portal investasi."""

    name = models.CharField(verbose_name=_("Nama sektor"), max_length=100, unique=True)
    slug = models.SlugField(
        verbose_name=_("Slug"),
        max_length=80,
        unique=True,
        blank=True,
        help_text=_("Dipakai di alamat halaman; dikosongkan untuk dibuat otomatis."),
    )
    icon = models.CharField(
        verbose_name=_("Ikon (emoji)"), max_length=8, blank=True, default=""
    )
    color = models.CharField(
        verbose_name=_("Warna peta"),
        max_length=7,
        default="#0d7e74",
        validators=[HEX_COLOR],
    )
    description = models.TextField(verbose_name=_("Keterangan"), blank=True, default="")
    order = models.PositiveSmallIntegerField(verbose_name=_("Urutan"), default=0)
    is_active = models.BooleanField(verbose_name=_("Aktif"), default=True)

    class Meta:
        verbose_name = _("Sektor investasi")
        verbose_name_plural = _("Sektor investasi")
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(self, self.name)
        super().save(*args, **kwargs)


class InvestmentZone(TimeStampedModel):
    """Kawasan investasi: kumpulan lahan dengan arahan dan insentif yang sama."""

    name = models.CharField(verbose_name=_("Nama kawasan"), max_length=255)
    slug = models.SlugField(
        verbose_name=_("Slug"),
        max_length=80,
        unique=True,
        blank=True,
        help_text=_("Dipakai di alamat halaman; dikosongkan untuk dibuat otomatis."),
    )
    sectors = models.ManyToManyField(
        InvestmentSector,
        verbose_name=_("Sektor unggulan"),
        blank=True,
        related_name="zones",
    )
    summary = models.CharField(
        verbose_name=_("Ringkasan"), max_length=300, blank=True, default=""
    )
    description = models.TextField(verbose_name=_("Uraian"), blank=True, default="")
    incentives = models.TextField(
        verbose_name=_("Insentif & kemudahan"),
        blank=True,
        default="",
        help_text=_("Satu butir per baris."),
    )
    infrastructure = models.TextField(
        verbose_name=_("Infrastruktur pendukung"),
        blank=True,
        default="",
        help_text=_("Satu butir per baris."),
    )
    geometry = gmodels.MultiPolygonField(
        verbose_name=_("Batas kawasan"), srid=4326, null=True, blank=True
    )
    photo = PrivateFileField(
        max_length=255,
        verbose_name=_("Foto"),
        upload_to=upload_zone,
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png"]),
            validate_upload_size,
        ],
    )
    order = models.PositiveSmallIntegerField(verbose_name=_("Urutan"), default=0)
    is_featured = models.BooleanField(verbose_name=_("Unggulan"), default=False)
    is_published = models.BooleanField(verbose_name=_("Tampil di portal"), default=True)

    class Meta:
        verbose_name = _("Kawasan investasi")
        verbose_name_plural = _("Kawasan investasi")
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(self, self.name)
        super().save(*args, **kwargs)

    @property
    def incentive_list(self) -> list[str]:
        return _lines(self.incentives)

    @property
    def infrastructure_list(self) -> list[str]:
        return _lines(self.infrastructure)


def _lines(text: str) -> list[str]:
    return [
        line.strip(" -•\t") for line in (text or "").splitlines() if line.strip(" -•\t")
    ]


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
        validators=[MinValueValidator(1), MaxValueValidator(MAX_TERM_YEARS)],
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
    # Profil investasi (portal /portal/investasi/)
    sector = models.ForeignKey(
        InvestmentSector,
        verbose_name=_("Sektor investasi"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plots",
    )
    zone = models.ForeignKey(
        InvestmentZone,
        verbose_name=_("Kawasan investasi"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plots",
    )
    offer_allocation = models.BooleanField(
        verbose_name=_("Ditawarkan dengan skema alokasi (UWT)"),
        default=True,
        help_text=_("Bila tidak dicentang, lahan tidak dapat dimohonkan alokasinya."),
    )
    offer_lease = models.BooleanField(
        verbose_name=_("Ditawarkan untuk disewa"), default=False
    )
    lease_rate_per_m2_year = models.DecimalField(
        verbose_name=_("Tarif sewa per m² per tahun (Rp)"),
        default=Decimal("0"),
        **MONEY,
    )
    lease_min_years = models.PositiveSmallIntegerField(
        verbose_name=_("Masa sewa minimum (tahun)"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_TERM_YEARS)],
    )
    lease_max_years = models.PositiveSmallIntegerField(
        verbose_name=_("Masa sewa maksimum (tahun)"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_TERM_YEARS)],
    )
    highlights = models.TextField(
        verbose_name=_("Keunggulan lokasi"),
        blank=True,
        default="",
        help_text=_("Satu butir per baris."),
    )
    incentives = models.TextField(
        verbose_name=_("Insentif"),
        blank=True,
        default="",
        help_text=_("Satu butir per baris. Kosongkan untuk memakai insentif kawasan."),
    )
    distance_port_km = models.DecimalField(
        verbose_name=_("Jarak ke pelabuhan (km)"),
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(MAX_DISTANCE_KM)],
    )
    distance_airport_km = models.DecimalField(
        verbose_name=_("Jarak ke bandara (km)"),
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(MAX_DISTANCE_KM)],
    )
    distance_road_km = models.DecimalField(
        verbose_name=_("Jarak ke jalan utama (km)"),
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(MAX_DISTANCE_KM)],
    )
    distance_city_km = models.DecimalField(
        verbose_name=_("Jarak ke pusat kota (km)"),
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(MAX_DISTANCE_KM)],
    )
    has_power = models.BooleanField(verbose_name=_("Jaringan listrik"), default=False)
    has_water = models.BooleanField(
        verbose_name=_("Jaringan air bersih"), default=False
    )
    has_telecom = models.BooleanField(
        verbose_name=_("Jaringan telekomunikasi"), default=False
    )
    has_road_access = models.BooleanField(verbose_name=_("Akses jalan"), default=False)
    is_featured = models.BooleanField(
        verbose_name=_("Unggulan di portal investasi"), default=False
    )

    class Meta:
        verbose_name = _("Lahan")
        verbose_name_plural = _("Lahan")
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.name}"

    def clean(self):
        super().clean()
        if self.area_m2 is not None and self.uwt_rate_per_m2_year is not None:
            from utils.money import check_fits

            # Total UWT menjadi tagihan; harus muat di kolom jumlah tagihan.
            check_fits(Invoice, "amount", self.uwt_total)
        if self.area_m2 is not None and self.lease_rate_per_m2_year:
            from utils.money import check_fits

            years = self.lease_max_years or self.lease_min_years or 1
            check_fits(Invoice, "amount", self.lease_total(years))
        if (
            self.lease_min_years
            and self.lease_max_years
            and self.lease_min_years > self.lease_max_years
        ):
            raise ValidationError(
                {
                    "lease_max_years": _(
                        "Masa sewa maksimum tidak boleh kurang dari minimum."
                    )
                }
            )
        if self.offer_lease and not self.lease_rate_per_m2_year:
            raise ValidationError(
                {
                    "lease_rate_per_m2_year": _(
                        "Isi tarif sewa bila lahan ditawarkan untuk disewa."
                    )
                }
            )

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
    def is_available(self) -> bool:
        return self.is_published and self.status == enums.PlotStatus.AVAILABLE

    @property
    def is_open_for_application(self) -> bool:
        return self.is_available and self.offer_allocation

    def lease_total(self, years: int) -> Decimal:
        return (self.area_m2 * self.lease_rate_per_m2_year * years).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )

    @property
    def lease_term_years(self) -> int:
        """Masa sewa untuk perkiraan biaya: minimum yang ditetapkan, atau 1 tahun."""
        return self.lease_min_years or 1

    @property
    def lease_estimate(self) -> Decimal:
        return self.lease_total(self.lease_term_years)

    @property
    def highlight_list(self) -> list[str]:
        return _lines(self.highlights)

    @property
    def incentive_list(self) -> list[str]:
        own = _lines(self.incentives)
        if own or self.zone_id is None:
            return own
        return self.zone.incentive_list

    @property
    def schemes(self) -> list[tuple[str, str]]:
        result = []
        if self.offer_lease:
            result.append(
                (enums.InvestmentScheme.LEASE, enums.InvestmentScheme.LEASE.label)
            )
        if self.offer_allocation:
            result.append(
                (
                    enums.InvestmentScheme.ALLOCATION,
                    enums.InvestmentScheme.ALLOCATION.label,
                )
            )
        return result

    @property
    def utilities(self) -> list[str]:
        names = (
            ("has_road_access", _("Akses jalan")),
            ("has_power", _("Listrik")),
            ("has_water", _("Air bersih")),
            ("has_telecom", _("Telekomunikasi")),
        )
        return [str(label) for field, label in names if getattr(self, field)]

    @property
    def distances(self) -> list[tuple[str, Decimal]]:
        names = (
            ("distance_port_km", _("Pelabuhan")),
            ("distance_airport_km", _("Bandara")),
            ("distance_road_km", _("Jalan utama")),
            ("distance_city_km", _("Pusat kota")),
        )
        return [
            (str(label), getattr(self, field))
            for field, label in names
            if getattr(self, field) is not None
        ]


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
    image = PrivateFileField(
        max_length=255,
        verbose_name=_("Gambar sampul"),
        upload_to=upload_info,
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png"]),
            validate_upload_size,
        ],
    )
    # Formulir unduhan dikelompokkan per jenis pelayanan (kosong = semua).
    service = models.ForeignKey(
        "ServiceCatalog",
        verbose_name=_("Jenis pelayanan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="info_pages",
        help_text=_("Untuk formulir unduhan: kosongkan bila berlaku semua pelayanan."),
    )
    is_pinned = models.BooleanField(
        verbose_name=_("Sematkan di beranda"),
        default=False,
        help_text=_("Pengumuman sematan tampil sebagai banner di beranda portal."),
    )
    view_count = models.PositiveIntegerField(
        verbose_name=_("Dilihat"), default=0, editable=False
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
    # Profil investor: dasbor portal mendahulukan peluang & permintaan investasi.
    is_investor = models.BooleanField(
        verbose_name=_("Akun investor"),
        default=False,
        help_text=_(
            "Dasbor portal mendahulukan permintaan investasi, penawaran, dan lahan "
            "yang sesuai minat. Otomatis aktif saat mengajukan minat investasi."
        ),
    )
    interest_sectors = models.ManyToManyField(
        InvestmentSector,
        verbose_name=_("Sektor usaha yang diminati"),
        blank=True,
        related_name="interested_applicants",
    )
    capital_origin = models.CharField(
        verbose_name=_("Asal modal"),
        max_length=8,
        choices=enums.CapitalOrigin.choices,
        default=enums.CapitalOrigin.DOMESTIC,
    )
    origin_country = models.CharField(
        verbose_name=_("Negara asal investor"), max_length=100, blank=True, default=""
    )
    website = models.URLField(
        verbose_name=_("Situs web perusahaan"), max_length=255, blank=True, default=""
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
            qs = cls.filter_allocation_type(qs, application.plot.allocation_type)
        return qs

    @staticmethod
    def filter_allocation_type(qs, allocation_type: str):
        """Dokumen umum alokasi + dokumen khusus jenisnya. Penataan/KSB hanya
        memakai dokumen khususnya (tanpa proposal usaha, laporan keuangan, dsb.)."""
        if allocation_type in enums.SETTLEMENT_ALLOCATION_TYPES:
            return qs.filter(allocation_type=allocation_type)
        return qs.filter(
            models.Q(allocation_type="") | models.Q(allocation_type=allocation_type)
        )


class ServiceCatalog(models.Model):
    """Katalog layanan perizinan portal (katalog terstruktur ala LMS).

    Satu baris per layanan; tab halaman detail portal (deskripsi, syarat,
    alur, durasi, tarif, dokumen terbit, dasar hukum) diambil dari isian di
    sini plus daftar RequirementDocType yang berlaku untuk layanan tersebut.
    """

    class Category(models.TextChoices):
        LAND = "pertanahan", _("Layanan pertanahan")
        DOCUMENT = "perubahan_dokumen", _("Layanan perubahan dokumen")
        REPORTING = "pelaporan", _("Layanan pelaporan")

    name = models.CharField(verbose_name=_("Nama layanan"), max_length=255)
    slug = models.SlugField(
        verbose_name=_("Slug"), max_length=255, unique=True, blank=True
    )
    category = models.CharField(
        verbose_name=_("Kelompok"),
        max_length=32,
        choices=Category.choices,
        default=Category.LAND,
    )
    # Layanan daring: kosongkan bila hanya informasi (belum/tidak daring).
    service_type = models.CharField(
        verbose_name=_("Jenis permohonan daring"),
        max_length=16,
        choices=enums.ServiceType.choices,
        blank=True,
        default="",
        help_text=_("Kosongkan bila layanan belum dapat diajukan secara daring."),
    )
    allocation_type = models.CharField(
        verbose_name=_("Jenis alokasi"),
        max_length=16,
        choices=enums.AllocationType.choices,
        blank=True,
        default="",
        help_text=_(
            "Khusus permohonan alokasi: dokumen persyaratan yang ditampilkan "
            "mengikuti jenis alokasi ini."
        ),
    )
    summary = models.CharField(
        verbose_name=_("Ringkasan"), max_length=500, blank=True, default=""
    )
    description = models.TextField(verbose_name=_("Deskripsi"), blank=True, default="")
    flow = models.TextField(
        verbose_name=_("Alur layanan"),
        blank=True,
        default="",
        help_text=_("Satu langkah per baris."),
    )
    duration_note = models.CharField(
        verbose_name=_("Durasi pemrosesan"), max_length=255, blank=True, default=""
    )
    tariff_note = models.TextField(
        verbose_name=_("Tarif"), blank=True, default="", help_text=_("Uraian tarif.")
    )
    issued_note = models.TextField(
        verbose_name=_("Dokumen terbit"), blank=True, default=""
    )
    legal_basis = models.TextField(
        verbose_name=_("Dasar hukum"), blank=True, default=""
    )
    order = models.PositiveIntegerField(verbose_name=_("Urutan"), default=0)
    is_active = models.BooleanField(verbose_name=_("Aktif"), default=True)

    class Meta:
        verbose_name = _("Katalog layanan")
        verbose_name_plural = _("Katalog layanan")
        ordering = ["category", "order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:200] or "layanan"
            slug = base
            n = 2
            while ServiceCatalog.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def requirement_docs(self):
        if not self.service_type:
            return ()
        qs = RequirementDocType.objects.filter(
            is_active=True, service_type=self.service_type
        )
        if self.service_type == enums.ServiceType.ALLOCATION and self.allocation_type:
            qs = RequirementDocType.filter_allocation_type(qs, self.allocation_type)
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
    # PIN pelacakan publik: nomor + PIN membuka halaman /portal/lacak/ tanpa
    # login. Dibuat otomatis sekali dan tidak pernah ditampilkan ke publik
    # selain kepada pemilik permohonan.
    tracking_pin = models.CharField(
        verbose_name=_("PIN pelacakan"),
        max_length=20,
        blank=True,
        default="",
        editable=False,
        help_text=_("Nomor + PIN ini dapat dipakai melacak status tanpa login."),
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
    recipient_accepted_at = models.DateTimeField(
        verbose_name=_("Penerima hak menyetujui"),
        null=True,
        blank=True,
        help_text=_(
            "Peralihan hanya dapat disetujui petugas setelah penerima hak "
            "menyetujuinya di portal."
        ),
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

    NUMBER_PREFIXES = {
        enums.ServiceType.ALLOCATION: "ALK",
        enums.ServiceType.TRANSFER: "PRL",
        enums.ServiceType.EXTENSION: "PPJ",
        enums.ServiceType.RENEWAL: "PMB",
        enums.ServiceType.SPLIT: "PCH",
        enums.ServiceType.REMEASURE: "PGU",
        enums.ServiceType.REVISE_PL: "RPL",
        enums.ServiceType.MERGE_PL: "GPL",
        enums.ServiceType.ADJUSTMENT: "PSD",
        enums.ServiceType.RECOMMENDATION: "REK",
        enums.ServiceType.UNBLOCK: "BBL",
        enums.ServiceType.REPLACEMENT: "DPG",
        enums.ServiceType.MORTGAGE: "PHT",
        enums.ServiceType.AUCTION: "PLL",
        enums.ServiceType.KPT_CHANGE: "KPU",
        enums.ServiceType.KPT_NEW: "KPB",
    }

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = _next_number(
                self.NUMBER_PREFIXES.get(self.service_type, "PRM")
            )
        if not self.tracking_pin:
            # 16 karakter acak (64 bit): nomor permohonan sekuensial, jadi PIN
            # adalah satu-satunya rahasia halaman pelacakan publik.
            self.tracking_pin = secrets.token_hex(8).upper()
        super().save(*args, **kwargs)

    @property
    def is_editable(self) -> bool:
        return self.status in enums.EDITABLE_STATUSES

    @property
    def is_allocation(self) -> bool:
        return self.service_type == enums.ServiceType.ALLOCATION

    @property
    def is_transfer(self) -> bool:
        return self.service_type == enums.ServiceType.TRANSFER

    @property
    def is_extension(self) -> bool:
        return self.service_type in (
            enums.ServiceType.EXTENSION,
            enums.ServiceType.RENEWAL,
        )

    @property
    def is_reissue(self) -> bool:
        return self.service_type in enums.REISSUE_SERVICES

    @property
    def is_settlement(self) -> bool:
        """Alokasi penataan / KSB: tanpa syarat rencana investasi usaha."""
        return (
            self.is_allocation
            and self.plot_id is not None
            and self.plot.allocation_type in enums.SETTLEMENT_ALLOCATION_TYPES
        )

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
    # Blokir penetapan lokasi (mis. sengketa, sita, tunggakan): selama
    # terblokir pemegang hanya dapat mengajukan pembukaan blokir.
    is_blocked = models.BooleanField(verbose_name=_("PL diblokir"), default=False)
    blocked_at = models.DateTimeField(
        verbose_name=_("Diblokir pada"), null=True, blank=True
    )
    block_reason = models.TextField(
        verbose_name=_("Alasan blokir"), blank=True, default=""
    )

    class Meta:
        verbose_name = _("Alokasi lahan")
        verbose_name_plural = _("Alokasi lahan")
        ordering = ["-issued_date", "-pk"]
        permissions = [
            ("revoke_allocation", _("Dapat mencabut alokasi lahan")),
            ("block_allocation", _("Dapat memblokir dan membuka blokir PL")),
        ]

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
        ("sph", _("Surat Perpanjangan / Pembaruan Hak Atas Tanah")),
        ("spt", _("Surat Persetujuan Layanan Tanah")),
        ("pl", _("Penetapan Lokasi (PL)")),
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
    # KPT/PPT/PL yang diterbitkan ulang (dokumen pengganti, perubahan, baru)
    # tetap tersimpan, tetapi verifikasi menyatakan sudah tidak berlaku.
    replaced_by = models.ForeignKey(
        "self",
        verbose_name=_("Diganti oleh"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replaces",
    )
    replaced_at = models.DateTimeField(
        verbose_name=_("Diganti pada"), null=True, blank=True
    )

    class Meta:
        verbose_name = _("Dokumen terbit")
        verbose_name_plural = _("Dokumen terbit")
        ordering = ["-issued_at", "kind"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.number}"


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


# --------------------------------------------------------------------------
# Portal investasi: permintaan investasi & penggunaan lahan
# --------------------------------------------------------------------------

# Usulan area yang digambar investor: batas atas luas dan jumlah titik agar
# satu permintaan tidak membebani peta dan basis data.
MAX_REQUEST_AREA_M2 = Decimal("100000000")  # 10.000 ha
MAX_REQUEST_VERTICES = 500


class InvestmentRequest(TimeStampedModel):
    """Minat investasi atau penggunaan lahan dari investor (pemohon portal).

    Alur: diajukan → ditinjau → konsultasi/kunjungan lapangan → penawaran →
    diterima investor → selesai (diteruskan ke permohonan alokasi atau kontrak
    sewa/kerja sama). Ditolak atau dibatalkan dapat terjadi sebelum selesai.
    """

    number = models.CharField(
        verbose_name=_("Nomor"), max_length=32, unique=True, editable=False
    )
    applicant = models.ForeignKey(
        Applicant,
        verbose_name=_("Investor"),
        on_delete=models.PROTECT,
        related_name="investment_requests",
    )
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=16,
        choices=enums.InvestmentStatus.choices,
        default=enums.InvestmentStatus.SUBMITTED,
    )
    scheme = models.CharField(
        verbose_name=_("Skema yang diminati"),
        max_length=16,
        choices=enums.InvestmentScheme.choices,
        default=enums.InvestmentScheme.UNDECIDED,
    )
    sector = models.ForeignKey(
        InvestmentSector,
        verbose_name=_("Sektor usaha"),
        on_delete=models.PROTECT,
        null=True,
        related_name="requests",
    )
    project_name = models.CharField(verbose_name=_("Nama proyek"), max_length=255)
    activity = models.TextField(verbose_name=_("Rencana kegiatan usaha"))
    plots = models.ManyToManyField(
        LandPlot,
        verbose_name=_("Lahan yang diminati"),
        blank=True,
        related_name="investment_requests",
    )
    zone = models.ForeignKey(
        InvestmentZone,
        verbose_name=_("Kawasan yang diminati"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requests",
    )
    requested_area = gmodels.MultiPolygonField(
        verbose_name=_("Usulan lokasi (digambar)"), srid=4326, null=True, blank=True
    )
    requested_area_m2 = models.DecimalField(
        verbose_name=_("Kebutuhan luas (m²)"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_REQUEST_AREA_M2)],
        **AREA,
    )
    term_years = models.PositiveSmallIntegerField(
        verbose_name=_("Jangka waktu yang diinginkan (tahun)"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_TERM_YEARS)],
    )
    investment_value = models.DecimalField(
        verbose_name=_("Rencana nilai investasi (Rp)"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        **MONEY,
    )
    workforce = models.PositiveIntegerField(
        verbose_name=_("Rencana tenaga kerja (orang)"),
        null=True,
        blank=True,
        validators=[MaxValueValidator(10_000_000)],
    )
    capital_origin = models.CharField(
        verbose_name=_("Asal modal"),
        max_length=8,
        choices=enums.CapitalOrigin.choices,
        default=enums.CapitalOrigin.DOMESTIC,
    )
    origin_country = models.CharField(
        verbose_name=_("Negara asal investor"), max_length=100, blank=True, default=""
    )
    target_start = models.DateField(
        verbose_name=_("Rencana mulai pembangunan"), null=True, blank=True
    )
    power_kva = models.PositiveIntegerField(
        verbose_name=_("Kebutuhan listrik (kVA)"),
        null=True,
        blank=True,
        validators=[MaxValueValidator(100_000_000)],
    )
    water_m3_day = models.PositiveIntegerField(
        verbose_name=_("Kebutuhan air (m³/hari)"),
        null=True,
        blank=True,
        validators=[MaxValueValidator(100_000_000)],
    )
    attachment = PrivateFileField(
        max_length=255,
        verbose_name=_("Proposal / profil perusahaan"),
        upload_to=upload_investment,
        null=True,
        blank=True,
        validators=UPLOAD_VALIDATORS,
    )
    attachment_name = models.CharField(
        verbose_name=_("Nama berkas"), max_length=255, blank=True, default=""
    )
    submitted_at = models.DateTimeField(
        verbose_name=_("Diajukan"), default=timezone.now, editable=False
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Petugas penanggung jawab"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    internal_note = models.TextField(
        verbose_name=_("Catatan internal petugas"),
        blank=True,
        default="",
        help_text=_("Tidak ditampilkan kepada investor."),
    )
    meeting_at = models.DateTimeField(
        verbose_name=_("Jadwal konsultasi / kunjungan"), null=True, blank=True
    )
    meeting_place = models.CharField(
        verbose_name=_("Tempat / tautan pertemuan"),
        max_length=255,
        blank=True,
        default="",
    )
    # Penawaran petugas
    offer_scheme = models.CharField(
        verbose_name=_("Skema ditawarkan"),
        max_length=16,
        choices=enums.InvestmentScheme.choices,
        blank=True,
        default="",
    )
    offer_plot = models.ForeignKey(
        LandPlot,
        verbose_name=_("Lahan ditawarkan"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="investment_offers",
    )
    offer_area_m2 = models.DecimalField(
        verbose_name=_("Luas ditawarkan (m²)"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_REQUEST_AREA_M2)],
        **AREA,
    )
    offer_rate_per_m2_year = models.DecimalField(
        verbose_name=_("Tarif ditawarkan per m² per tahun (Rp)"),
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        **MONEY,
    )
    offer_term_years = models.PositiveSmallIntegerField(
        verbose_name=_("Jangka waktu ditawarkan (tahun)"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_TERM_YEARS)],
    )
    offer_valid_until = models.DateField(
        verbose_name=_("Penawaran berlaku s.d."), null=True, blank=True
    )
    offer_note = models.TextField(
        verbose_name=_("Ketentuan penawaran"), blank=True, default=""
    )
    offered_at = models.DateTimeField(
        verbose_name=_("Penawaran dikirim"), null=True, blank=True
    )
    # Penyelesaian
    application = models.ForeignKey(
        Application,
        verbose_name=_("Permohonan alokasi"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="investment_requests",
    )
    contract_number = models.CharField(
        verbose_name=_("Nomor kontrak / perjanjian"),
        max_length=64,
        blank=True,
        default="",
    )
    closed_at = models.DateTimeField(verbose_name=_("Ditutup"), null=True, blank=True)

    class Meta:
        verbose_name = _("Permintaan investasi")
        verbose_name_plural = _("Permintaan investasi")
        ordering = ["-submitted_at", "-pk"]
        permissions = [
            (
                "process_investmentrequest",
                _("Dapat memproses permintaan investasi"),
            )
        ]

    def __str__(self):
        return f"{self.number} {self.project_name}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = _next_number("INV")
        super().save(*args, **kwargs)

    @property
    def is_final(self) -> bool:
        return self.status in enums.INVESTMENT_FINAL_STATUSES

    @property
    def requested_area_size_m2(self) -> Decimal | None:
        if self.requested_area is None:
            return None
        from asetlahan.geo import area_m2

        return area_m2(self.requested_area)

    @property
    def offer_total(self) -> Decimal | None:
        if None in (
            self.offer_area_m2,
            self.offer_rate_per_m2_year,
            self.offer_term_years,
        ):
            return None
        return (
            self.offer_area_m2 * self.offer_rate_per_m2_year * self.offer_term_years
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    @property
    def offer_expired(self) -> bool:
        return bool(
            self.offer_valid_until and self.offer_valid_until < timezone.localdate()
        )

    @property
    def can_accept_offer(self) -> bool:
        return self.status == enums.InvestmentStatus.OFFERED and not self.offer_expired


class InvestmentMessage(models.Model):
    """Percakapan investor ↔ petugas atas satu permintaan investasi."""

    request = models.ForeignKey(
        InvestmentRequest,
        verbose_name=_("Permintaan investasi"),
        on_delete=models.CASCADE,
        related_name="messages",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Pengirim"),
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    from_officer = models.BooleanField(verbose_name=_("Dari petugas"), default=False)
    body = models.TextField(verbose_name=_("Pesan"), max_length=5000)
    attachment = PrivateFileField(
        max_length=255,
        verbose_name=_("Lampiran"),
        upload_to=upload_investment,
        null=True,
        blank=True,
        validators=UPLOAD_VALIDATORS,
    )
    attachment_name = models.CharField(
        verbose_name=_("Nama berkas"), max_length=255, blank=True, default=""
    )
    created_at = models.DateTimeField(verbose_name=_("Waktu"), default=timezone.now)

    class Meta:
        verbose_name = _("Pesan permintaan investasi")
        verbose_name_plural = _("Pesan permintaan investasi")
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.request.number} {self.created_at:%d-%m-%Y %H:%M}"


class InvestmentEvent(models.Model):
    request = models.ForeignKey(
        InvestmentRequest,
        verbose_name=_("Permintaan investasi"),
        on_delete=models.CASCADE,
        related_name="events",
    )
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=16,
        choices=enums.InvestmentStatus.choices,
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
        verbose_name = _("Riwayat permintaan investasi")
        verbose_name_plural = _("Riwayat permintaan investasi")
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.request.number} {self.get_status_display()}"


class SavedPlot(models.Model):
    """Lahan yang disimpan investor untuk ditinjau kembali."""

    applicant = models.ForeignKey(
        Applicant,
        verbose_name=_("Investor"),
        on_delete=models.CASCADE,
        related_name="saved_plots",
    )
    plot = models.ForeignKey(
        LandPlot,
        verbose_name=_("Lahan"),
        on_delete=models.CASCADE,
        related_name="saved_by",
    )
    created_at = models.DateTimeField(verbose_name=_("Disimpan"), default=timezone.now)

    class Meta:
        verbose_name = _("Lahan tersimpan")
        verbose_name_plural = _("Lahan tersimpan")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=("applicant", "plot"), name="alokasi_savedplot_unique"
            )
        ]

    def __str__(self):
        return f"{self.applicant} – {self.plot}"


class UwtRegion(models.Model):
    """Wilayah / sub wilayah tarif UWT untuk simulasi biaya di portal."""

    name = models.CharField(verbose_name=_("Wilayah"), max_length=128)
    sub_name = models.CharField(
        verbose_name=_("Sub wilayah"), max_length=128, blank=True, default=""
    )
    description = models.TextField(verbose_name=_("Keterangan"), blank=True, default="")
    order = models.PositiveSmallIntegerField(verbose_name=_("Urutan"), default=0)
    is_active = models.BooleanField(verbose_name=_("Aktif"), default=True)

    class Meta:
        verbose_name = _("Wilayah tarif UWT")
        verbose_name_plural = _("Wilayah tarif UWT")
        ordering = ["order", "name", "sub_name"]
        constraints = [
            models.UniqueConstraint(
                fields=("name", "sub_name"), name="alokasi_uwtregion_unique"
            )
        ]

    def __str__(self):
        return f"{self.name} – {self.sub_name}" if self.sub_name else self.name


class UwtTariff(models.Model):
    """Tarif UWT per m² per tahun menurut wilayah, peruntukan, dan jenis pengurusan."""

    class Kind(models.TextChoices):
        NEW = "baru", _("Tarif alokasi baru")
        EXTENSION = "perpanjangan", _("Tarif perpanjangan")
        RENEWAL = "pembaruan", _("Tarif pembaruan")

    region = models.ForeignKey(
        UwtRegion,
        verbose_name=_("Wilayah"),
        on_delete=models.CASCADE,
        related_name="tariffs",
    )
    land_use = models.CharField(verbose_name=_("Peruntukan"), max_length=128)
    kind = models.CharField(
        verbose_name=_("Jenis pengurusan"), max_length=16, choices=Kind.choices
    )
    rate_per_m2_year = models.DecimalField(
        verbose_name=_("Tarif per m² per tahun (Rp)"),
        validators=[MinValueValidator(Decimal("0"))],
        **MONEY,
    )
    term_years = models.PositiveSmallIntegerField(
        verbose_name=_("Jangka waktu (tahun)"),
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_TERM_YEARS)],
    )
    note = models.CharField(
        verbose_name=_("Catatan"), max_length=255, blank=True, default=""
    )
    is_active = models.BooleanField(verbose_name=_("Aktif"), default=True)

    class Meta:
        verbose_name = _("Tarif UWT")
        verbose_name_plural = _("Tarif UWT")
        ordering = ["region__order", "region__name", "land_use", "kind"]
        constraints = [
            models.UniqueConstraint(
                fields=("region", "land_use", "kind"), name="alokasi_uwttariff_unique"
            )
        ]

    def __str__(self):
        return f"{self.region} · {self.land_use} · {self.get_kind_display()}"


class ContactMessage(models.Model):
    """Pesan dari formulir Kontak Kami portal."""

    class Status(models.TextChoices):
        NEW = "baru", _("Baru")
        IN_PROGRESS = "diproses", _("Diproses")
        DONE = "selesai", _("Selesai")

    created_at = models.DateTimeField(verbose_name=_("Diterima"), default=timezone.now)
    name = models.CharField(verbose_name=_("Nama lengkap"), max_length=255)
    email = models.EmailField(verbose_name=_("Surel"))
    phone = models.CharField(verbose_name=_("No. telepon"), max_length=32)
    subject = models.CharField(verbose_name=_("Subjek"), max_length=255)
    body = models.TextField(verbose_name=_("Isi pesan"), max_length=5000)
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=16,
        choices=Status.choices,
        default=Status.NEW,
    )
    reply = models.TextField(
        verbose_name=_("Balasan ke pengirim"),
        blank=True,
        default="",
        help_text=_("Diisi lalu disimpan: balasan dikirim ke surel pengirim."),
    )
    replied_at = models.DateTimeField(
        verbose_name=_("Dibalas pada"), null=True, blank=True, editable=False
    )
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Ditangani oleh"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )
    ip_address = models.GenericIPAddressField(
        verbose_name=_("Alamat IP"), null=True, blank=True, editable=False
    )

    class Meta:
        verbose_name = _("Pesan Kontak Kami")
        verbose_name_plural = _("Pesan Kontak Kami")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} – {self.name}"


for _model in (
    UwtRegion,
    UwtTariff,
    ContactMessage,
    AllocationSettings,
    LandPlot,
    InfoPage,
    Applicant,
    RequirementDocType,
    ServiceCatalog,
    VerificationCriterion,
    Application,
    ApplicationDocument,
    VerificationScore,
    Invoice,
    Allocation,
    IssuedDocument,
    DevelopmentReport,
    InvestmentSector,
    InvestmentZone,
    InvestmentRequest,
    InvestmentMessage,
):
    auditlog.register(_model)
