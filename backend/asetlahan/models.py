"""Model modul Manajemen Aset Lahan (bank tanah terpadu).

Setiap entitas utama punya ``service_unit`` (unit layanan MVJ) untuk pemisahan
data per lokasi: petugas hanya melihat data unit layanannya, sedangkan
Administrator melihat seluruhnya. Data tanpa unit layanan terlihat oleh semua
petugas yang berizin.
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
from django.utils.translation import gettext_lazy as _
from sequences import get_next_value

from asetlahan import enums
from file_operations.private_files import PrivateFileField
from leasing.models.mixins import TimeStampedModel

MONEY = {"max_digits": 20, "decimal_places": 2}
AREA = {"max_digits": 16, "decimal_places": 2}

DOCUMENT_EXTENSIONS = ["pdf", "jpg", "jpeg", "png", "tif", "tiff", "doc", "docx", "xls", "xlsx", "zip"]
IMAGE_EXTENSIONS = ["jpg", "jpeg", "png"]
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def validate_upload_size(value):
    from django.core.exceptions import ValidationError

    if value and value.size > MAX_UPLOAD_BYTES:
        raise ValidationError(_("Ukuran berkas maksimal 25 MB."))


DOCUMENT_VALIDATORS = [
    FileExtensionValidator(allowed_extensions=DOCUMENT_EXTENSIONS),
    validate_upload_size,
]
IMAGE_VALIDATORS = [
    FileExtensionValidator(allowed_extensions=IMAGE_EXTENSIONS),
    validate_upload_size,
]


def _upload_to(name, prefix):
    def inner(instance, filename):
        return f"asetlahan/{prefix}/{timezone.now():%Y/%m}/{uuid.uuid4().hex}/{filename}"

    # Nama harus sama dengan nama variabel modul agar dapat diimpor oleh migrasi.
    inner.__name__ = inner.__qualname__ = name
    return inner


upload_document = _upload_to("upload_document", "dokumen")
upload_imagery = _upload_to("upload_imagery", "citra")
upload_field = _upload_to("upload_field", "lapangan")
upload_bid = _upload_to("upload_bid", "penawaran")
upload_grievance = _upload_to("upload_grievance", "pengaduan")


def next_number(prefix: str) -> str:
    year = timezone.localdate().year
    value = get_next_value(f"asetlahan_{prefix.lower()}_{year}")
    return f"{prefix}-{year}-{value:04d}"


def _service_unit_field():
    return models.ForeignKey(
        "leasing.ServiceUnit",
        verbose_name=_("Unit layanan / lokasi"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text=_("Membatasi siapa yang melihat data ini. Kosong = semua petugas."),
    )


def _user_field(verbose_name, related_name="+"):
    return models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=verbose_name,
        related_name=related_name,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )


def current_year() -> int:
    return timezone.localdate().year


def _money(value) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------
# Pengaturan & data master
# --------------------------------------------------------------------------


class ModuleSettings(models.Model):
    """Pengaturan modul (satu baris): modul aktif dan batas waktu pengingat."""

    enable_ownership = models.BooleanField(_("Kepemilikan, silsilah & pemangku kepentingan"), default=True)
    enable_valuation = models.BooleanField(_("Penilaian, pajak & keuangan"), default=True)
    enable_litigation = models.BooleanField(_("Perkara & advokat"), default=True)
    enable_encroachment = models.BooleanField(_("Okupasi & citra satelit"), default=True)
    enable_resettlement = models.BooleanField(_("Permukiman kembali"), default=True)
    enable_survey = models.BooleanField(_("Survei, fasilitator & urusan instansi"), default=True)
    enable_tasks = models.BooleanField(_("Tugas & tim"), default=True)
    enable_grievance = models.BooleanField(_("Pengaduan masyarakat"), default=True)
    enable_tender = models.BooleanField(_("Lelang / seleksi lahan"), default=True)

    lease_alert_days = models.PositiveSmallIntegerField(
        _("Pengingat sewa berakhir (hari sebelumnya)"), default=90
    )
    title_alert_days = models.PositiveSmallIntegerField(
        _("Pengingat hak atas tanah berakhir (hari sebelumnya)"), default=180
    )
    tax_alert_days = models.PositiveSmallIntegerField(
        _("Pengingat jatuh tempo pajak (hari sebelumnya)"), default=14
    )
    hearing_alert_days = models.PositiveSmallIntegerField(
        _("Pengingat sidang (hari sebelumnya)"), default=7
    )
    grievance_sla_days = models.PositiveSmallIntegerField(
        _("Batas penyelesaian pengaduan (hari)"), default=14
    )
    encroachment_followup_days = models.PositiveSmallIntegerField(
        _("Okupasi tanpa tindak lanjut ditandai setelah (hari)"), default=30
    )
    cash_account_code = models.CharField(
        _("Kode akun kas/bank (jurnal ERP)"), max_length=32, default="1101",
        help_text=_("Akun lawan untuk setiap transaksi saat ekspor jurnal ke ERP."),
    )

    class Meta:
        verbose_name = _("Pengaturan modul aset lahan")
        verbose_name_plural = _("Pengaturan modul aset lahan")

    def __str__(self):
        return str(self._meta.verbose_name)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "ModuleSettings":
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj


class AssetCategory(models.Model):
    name = models.CharField(_("Nama"), max_length=128, unique=True)
    color = models.CharField(
        _("Warna peta"), max_length=7, default="#0969da", help_text=_("Format #RRGGBB.")
    )
    description = models.TextField(_("Keterangan"), blank=True, default="")
    is_active = models.BooleanField(_("Aktif"), default=True)

    class Meta:
        verbose_name = _("Kategori aset")
        verbose_name_plural = _("Kategori aset")
        ordering = ["name"]

    def __str__(self):
        return self.name


class GrievanceCategory(models.Model):
    name = models.CharField(_("Nama"), max_length=128, unique=True)
    sla_days = models.PositiveSmallIntegerField(
        _("Batas penyelesaian (hari)"), null=True, blank=True,
        help_text=_("Kosong = memakai pengaturan modul."),
    )
    is_active = models.BooleanField(_("Aktif"), default=True)

    class Meta:
        verbose_name = _("Kategori pengaduan")
        verbose_name_plural = _("Kategori pengaduan")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Team(TimeStampedModel):
    name = models.CharField(_("Nama tim"), max_length=128, unique=True)
    leader = _user_field(_("Ketua tim"))
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, verbose_name=_("Anggota"), related_name="asetlahan_teams", blank=True
    )
    description = models.TextField(_("Tugas pokok"), blank=True, default="")
    service_unit = _service_unit_field()

    class Meta:
        verbose_name = _("Tim internal")
        verbose_name_plural = _("Tim internal")
        ordering = ["name"]

    def __str__(self):
        return self.name


# --------------------------------------------------------------------------
# Bank tanah
# --------------------------------------------------------------------------


class LandAsset(TimeStampedModel):
    code = models.CharField(_("Kode aset"), max_length=32, unique=True)
    name = models.CharField(_("Nama / lokasi aset"), max_length=255)
    category = models.ForeignKey(
        AssetCategory, verbose_name=_("Kategori"), related_name="assets",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    status = models.CharField(
        _("Status penguasaan"), max_length=16, choices=enums.AssetStatus.choices,
        default=enums.AssetStatus.CONTROLLED,
    )
    service_unit = _service_unit_field()
    municipality = models.ForeignKey(
        "leasing.Municipality", verbose_name=_("Kabupaten / kota"), related_name="+",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    district = models.CharField(_("Kecamatan"), max_length=128, blank=True, default="")
    village = models.CharField(_("Kelurahan / desa"), max_length=128, blank=True, default="")
    address = models.CharField(_("Alamat / patokan"), max_length=255, blank=True, default="")
    area_m2 = models.DecimalField(_("Luas (m²)"), null=True, blank=True, **AREA)
    geometry = gmodels.MultiPolygonField(_("Batas bidang"), srid=4326, null=True, blank=True)

    title_type = models.CharField(
        _("Jenis alas hak"), max_length=16, choices=enums.TitleType.choices,
        default=enums.TitleType.UNREGISTERED,
    )
    title_number = models.CharField(_("Nomor sertipikat / alas hak"), max_length=128, blank=True, default="")
    nib = models.CharField(_("NIB (Nomor Identifikasi Bidang)"), max_length=64, blank=True, default="")
    title_date = models.DateField(_("Tanggal terbit hak"), null=True, blank=True)
    title_expiry = models.DateField(_("Hak berakhir"), null=True, blank=True)
    registered_owner = models.CharField(_("Pemegang hak tercatat"), max_length=255, blank=True, default="")

    acquisition_method = models.CharField(
        _("Cara perolehan"), max_length=16, choices=enums.AcquisitionMethod.choices, blank=True, default=""
    )
    acquisition_date = models.DateField(_("Tanggal perolehan"), null=True, blank=True)
    acquisition_cost = models.DecimalField(_("Nilai perolehan (Rp)"), null=True, blank=True, **MONEY)
    njop_per_m2 = models.DecimalField(_("NJOP tanah per m² (Rp)"), null=True, blank=True, **MONEY)
    zoning = models.CharField(_("Peruntukan ruang (RTRW/RDTR)"), max_length=255, blank=True, default="")
    land_use = models.CharField(_("Penggunaan saat ini"), max_length=255, blank=True, default="")

    pengadaan_parcel = models.ForeignKey(
        "pengadaan.AcquisitionParcel", verbose_name=_("Bidang pengadaan tanah"), related_name="+",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    alokasi_plot = models.ForeignKey(
        "alokasi.LandPlot", verbose_name=_("Lahan alokasi"), related_name="+",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    lease = models.ForeignKey(
        "leasing.Lease", verbose_name=_("Kontrak sewa"), related_name="+",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    responsible = _user_field(_("Penanggung jawab"))
    note = models.TextField(_("Catatan"), blank=True, default="")

    class Meta:
        verbose_name = _("Aset lahan")
        verbose_name_plural = _("Aset lahan (bank tanah)")
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} – {self.name}"

    def save(self, *args, **kwargs):
        if self.geometry and not self.area_m2:
            from asetlahan.geo import area_m2

            self.area_m2 = area_m2(self.geometry)
        super().save(*args, **kwargs)

    @property
    def latest_valuation(self):
        return self.valuations.order_by("-valuation_date", "-id").first()

    @property
    def status_color(self) -> str:
        return enums.ASSET_STATUS_COLORS.get(self.status, "#57606a")


class OwnershipRecord(TimeStampedModel):
    """Riwayat kepemilikan / penguasaan (rantai alas hak)."""

    asset = models.ForeignKey(LandAsset, verbose_name=_("Aset"), related_name="ownerships", on_delete=models.CASCADE)
    owner_name = models.CharField(_("Nama pemilik / penguasa"), max_length=255)
    owner_type = models.CharField(_("Jenis"), max_length=16, choices=enums.OwnerType.choices, default=enums.OwnerType.INDIVIDUAL)
    start_date = models.DateField(_("Sejak"), null=True, blank=True)
    end_date = models.DateField(_("Sampai"), null=True, blank=True)
    basis = models.CharField(_("Dasar peralihan"), max_length=255, blank=True, default="", help_text=_("Mis. AJB No. 12/2015, waris, hibah."))
    share_percentage = models.DecimalField(_("Bagian (%)"), max_digits=6, decimal_places=3, null=True, blank=True,
                                           validators=[MinValueValidator(0), MaxValueValidator(100)])
    note = models.TextField(_("Catatan"), blank=True, default="")

    class Meta:
        verbose_name = _("Riwayat kepemilikan")
        verbose_name_plural = _("Riwayat kepemilikan")
        ordering = ["asset", "start_date", "id"]

    def __str__(self):
        return self.owner_name


class Heirship(TimeStampedModel):
    """Silsilah ahli waris atas tanah (aset atau bidang pengadaan)."""

    asset = models.ForeignKey(LandAsset, verbose_name=_("Aset"), related_name="heirships", null=True, blank=True, on_delete=models.CASCADE)
    pengadaan_parcel = models.ForeignKey(
        "pengadaan.AcquisitionParcel", verbose_name=_("Bidang pengadaan tanah"), related_name="+",
        null=True, blank=True, on_delete=models.CASCADE,
    )
    decedent_name = models.CharField(_("Nama pewaris"), max_length=255)
    date_of_death = models.DateField(_("Tanggal meninggal"), null=True, blank=True)
    certificate_number = models.CharField(_("Nomor surat keterangan waris / akta"), max_length=128, blank=True, default="")
    note = models.TextField(_("Catatan"), blank=True, default="")

    class Meta:
        verbose_name = _("Silsilah ahli waris")
        verbose_name_plural = _("Silsilah ahli waris")
        ordering = ["decedent_name"]

    def __str__(self):
        return _("Ahli waris %(name)s") % {"name": self.decedent_name}

    def roots(self):
        return self.members.filter(parent__isnull=True)


class HeirMember(models.Model):
    heirship = models.ForeignKey(Heirship, verbose_name=_("Silsilah"), related_name="members", on_delete=models.CASCADE)
    parent = models.ForeignKey(
        "self", verbose_name=_("Melalui (orang tua dalam silsilah)"), related_name="children",
        null=True, blank=True, on_delete=models.CASCADE,
        help_text=_("Kosong = hubungan langsung dengan pewaris."),
    )
    name = models.CharField(_("Nama"), max_length=255)
    relation = models.CharField(_("Hubungan"), max_length=16, choices=enums.Kinship.choices, default=enums.Kinship.CHILD)
    is_alive = models.BooleanField(_("Masih hidup"), default=True)
    share_percentage = models.DecimalField(_("Bagian waris (%)"), max_digits=6, decimal_places=3, null=True, blank=True,
                                           validators=[MinValueValidator(0), MaxValueValidator(100)])
    entitled_party = models.ForeignKey(
        "pengadaan.EntitledParty", verbose_name=_("Pihak yang berhak (pengadaan)"), related_name="+",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    note = models.CharField(_("Catatan"), max_length=255, blank=True, default="")

    class Meta:
        verbose_name = _("Anggota silsilah")
        verbose_name_plural = _("Anggota silsilah")
        ordering = ["heirship", "id"]

    def __str__(self):
        return self.name

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.parent_id and self.parent.heirship_id != self.heirship_id:
            raise ValidationError({"parent": _("Harus anggota silsilah yang sama.")})
        node, seen = self.parent, set()
        while node is not None:
            if node.pk == self.pk or node.pk in seen:
                raise ValidationError({"parent": _("Silsilah tidak boleh melingkar.")})
            seen.add(node.pk)
            node = node.parent


class Stakeholder(TimeStampedModel):
    name = models.CharField(_("Nama"), max_length=255)
    stakeholder_type = models.CharField(_("Jenis"), max_length=16, choices=enums.StakeholderType.choices, default=enums.StakeholderType.RESIDENT)
    organization = models.CharField(_("Instansi / organisasi"), max_length=255, blank=True, default="")
    position = models.CharField(_("Jabatan / peran"), max_length=255, blank=True, default="")
    phone = models.CharField(_("Telepon / WhatsApp"), max_length=32, blank=True, default="")
    email = models.EmailField(_("Surel"), blank=True, default="")
    influence = models.CharField(_("Pengaruh"), max_length=8, choices=enums.Level.choices, default=enums.Level.MEDIUM)
    interest = models.CharField(_("Kepentingan"), max_length=8, choices=enums.Level.choices, default=enums.Level.MEDIUM)
    stance = models.CharField(_("Sikap"), max_length=16, choices=enums.Stance.choices, default=enums.Stance.UNKNOWN)
    assets = models.ManyToManyField(LandAsset, verbose_name=_("Aset terkait"), related_name="stakeholders", blank=True)
    pengadaan_project = models.ForeignKey(
        "pengadaan.AcquisitionProject", verbose_name=_("Proyek pengadaan"), related_name="+",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    service_unit = _service_unit_field()
    note = models.TextField(_("Catatan"), blank=True, default="")

    class Meta:
        verbose_name = _("Pemangku kepentingan")
        verbose_name_plural = _("Pemangku kepentingan")
        ordering = ["name"]

    def __str__(self):
        return self.name


class StakeholderEngagement(models.Model):
    stakeholder = models.ForeignKey(Stakeholder, verbose_name=_("Pemangku kepentingan"), related_name="engagements", on_delete=models.CASCADE)
    date = models.DateField(_("Tanggal"), default=datetime.date.today)
    method = models.CharField(_("Cara"), max_length=16, choices=enums.EngagementMethod.choices, default=enums.EngagementMethod.MEETING)
    summary = models.TextField(_("Ringkasan / hasil"))
    follow_up = models.CharField(_("Tindak lanjut"), max_length=255, blank=True, default="")
    follow_up_date = models.DateField(_("Tanggal tindak lanjut"), null=True, blank=True)
    officer = _user_field(_("Petugas"))

    class Meta:
        verbose_name = _("Keterlibatan pemangku kepentingan")
        verbose_name_plural = _("Keterlibatan pemangku kepentingan")
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.stakeholder} {self.date}"


# --------------------------------------------------------------------------
# Penilaian, pajak, keuangan
# --------------------------------------------------------------------------


class AssetValuation(TimeStampedModel):
    asset = models.ForeignKey(LandAsset, verbose_name=_("Aset"), related_name="valuations", on_delete=models.CASCADE)
    valuation_date = models.DateField(_("Tanggal penilaian"), default=datetime.date.today)
    method = models.CharField(_("Metode"), max_length=16, choices=enums.ValuationMethod.choices, default=enums.ValuationMethod.NJOP)
    land_value_per_m2 = models.DecimalField(_("Nilai tanah per m² (Rp)"), **MONEY)
    area_m2 = models.DecimalField(_("Luas dinilai (m²)"), null=True, blank=True, help_text=_("Kosong = luas aset."), **AREA)
    land_value = models.DecimalField(_("Nilai tanah (Rp)"), default=0, editable=False, **MONEY)
    structures_value = models.DecimalField(_("Nilai bangunan & benda lain (Rp)"), default=0, editable=False, **MONEY)
    total_value = models.DecimalField(_("Nilai total (Rp)"), default=0, editable=False, **MONEY)
    appraiser = models.CharField(_("Penilai"), max_length=255, blank=True, default="")
    report_number = models.CharField(_("Nomor laporan penilaian"), max_length=128, blank=True, default="")
    note = models.TextField(_("Catatan"), blank=True, default="")

    class Meta:
        verbose_name = _("Penilaian aset")
        verbose_name_plural = _("Penilaian aset")
        ordering = ["-valuation_date", "-id"]

    def __str__(self):
        return f"{self.asset.code} {self.valuation_date}"

    def recompute(self, save=True):
        area = self.area_m2 if self.area_m2 is not None else (self.asset.area_m2 or Decimal(0))
        self.land_value = _money(Decimal(self.land_value_per_m2 or 0) * Decimal(area))
        self.structures_value = _money(
            sum((item.total for item in self.items.all()), Decimal(0)) if self.pk else 0
        )
        self.total_value = self.land_value + self.structures_value
        if save and self.pk:
            AssetValuation.objects.filter(pk=self.pk).update(
                land_value=self.land_value,
                structures_value=self.structures_value,
                total_value=self.total_value,
            )

    def save(self, *args, **kwargs):
        self.recompute(save=False)
        super().save(*args, **kwargs)


class ValuationItem(models.Model):
    valuation = models.ForeignKey(AssetValuation, verbose_name=_("Penilaian"), related_name="items", on_delete=models.CASCADE)
    item_type = models.CharField(_("Jenis"), max_length=16, choices=enums.ValuationItemType.choices, default=enums.ValuationItemType.BUILDING)
    description = models.CharField(_("Uraian"), max_length=255)
    quantity = models.DecimalField(_("Volume"), max_digits=14, decimal_places=2, default=1)
    unit = models.CharField(_("Satuan"), max_length=16, default="m²")
    unit_value = models.DecimalField(_("Nilai satuan (Rp)"), **MONEY)

    class Meta:
        verbose_name = _("Rincian benda di atas tanah")
        verbose_name_plural = _("Rincian bangunan, tanaman & benda lain")

    def __str__(self):
        return self.description

    @property
    def total(self) -> Decimal:
        return _money(Decimal(self.quantity or 0) * Decimal(self.unit_value or 0))


class TaxObligation(TimeStampedModel):
    asset = models.ForeignKey(LandAsset, verbose_name=_("Aset"), related_name="taxes", on_delete=models.CASCADE)
    tax_type = models.CharField(_("Jenis"), max_length=16, choices=enums.TaxType.choices, default=enums.TaxType.PBB)
    period = models.PositiveSmallIntegerField(_("Tahun / periode"), default=current_year)
    base_value = models.DecimalField(_("Dasar pengenaan (Rp)"), null=True, blank=True,
                                     help_text=_("Mis. NJOP. Kosong = NJOP aset × luas."), **MONEY)
    rate_percent = models.DecimalField(_("Tarif (%)"), max_digits=7, decimal_places=4, null=True, blank=True)
    deduction = models.DecimalField(_("Pengurang / NJOPTKP (Rp)"), default=0, **MONEY)
    amount = models.DecimalField(_("Jumlah terutang (Rp)"), null=True, blank=True,
                                 help_text=_("Kosong = dihitung dari dasar × tarif."), **MONEY)
    due_date = models.DateField(_("Jatuh tempo"))
    paid_date = models.DateField(_("Tanggal bayar"), null=True, blank=True)
    paid_amount = models.DecimalField(_("Jumlah dibayar (Rp)"), null=True, blank=True, **MONEY)
    reference = models.CharField(_("Nomor SPPT / tagihan"), max_length=128, blank=True, default="")
    note = models.CharField(_("Catatan"), max_length=255, blank=True, default="")

    class Meta:
        verbose_name = _("Pajak & retribusi")
        verbose_name_plural = _("Pajak & retribusi")
        ordering = ["due_date"]

    def __str__(self):
        return f"{self.get_tax_type_display()} {self.period} – {self.asset.code}"

    def compute_amount(self) -> Decimal | None:
        base = self.base_value
        if base is None and self.asset_id and self.asset.njop_per_m2 and self.asset.area_m2:
            base = Decimal(self.asset.njop_per_m2) * Decimal(self.asset.area_m2)
        if base is None or self.rate_percent is None:
            return None
        taxable = max(Decimal(base) - Decimal(self.deduction or 0), Decimal(0))
        return _money(taxable * Decimal(self.rate_percent) / Decimal(100))

    def save(self, *args, **kwargs):
        if self.amount is None:
            self.amount = self.compute_amount()
        super().save(*args, **kwargs)

    @property
    def is_paid(self) -> bool:
        return self.paid_date is not None

    @property
    def is_overdue(self) -> bool:
        return not self.is_paid and self.due_date < timezone.localdate()


class LandTransaction(TimeStampedModel):
    """Buku besar keuangan lahan; dapat diekspor ke ERP (SAP, Navision, Tally)."""

    number = models.CharField(_("Nomor"), max_length=32, unique=True, editable=False)
    transaction_type = models.CharField(_("Jenis"), max_length=16, choices=enums.TransactionType.choices)
    date = models.DateField(_("Tanggal"), default=datetime.date.today)
    amount = models.DecimalField(_("Jumlah (Rp)"), validators=[MinValueValidator(0)], **MONEY)
    asset = models.ForeignKey(LandAsset, verbose_name=_("Aset"), related_name="transactions", null=True, blank=True, on_delete=models.PROTECT)
    pengadaan_project = models.ForeignKey(
        "pengadaan.AcquisitionProject", verbose_name=_("Proyek pengadaan"), related_name="+",
        null=True, blank=True, on_delete=models.PROTECT,
    )
    household = models.ForeignKey(
        "pengadaan.AffectedHousehold", verbose_name=_("Rumah tangga terdampak (R&R)"), related_name="+",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    tax = models.OneToOneField(TaxObligation, verbose_name=_("Pajak"), related_name="transaction", null=True, blank=True, on_delete=models.SET_NULL)
    legal_case = models.ForeignKey("LegalCase", verbose_name=_("Perkara"), related_name="transactions", null=True, blank=True, on_delete=models.SET_NULL)
    counterparty = models.CharField(_("Pihak lawan transaksi"), max_length=255, blank=True, default="")
    reference = models.CharField(_("Nomor bukti / referensi"), max_length=128, blank=True, default="")
    account_code = models.CharField(_("Kode akun (ERP)"), max_length=32, blank=True, default="")
    cost_center = models.CharField(_("Pusat biaya (ERP)"), max_length=32, blank=True, default="")
    description = models.CharField(_("Uraian"), max_length=255, blank=True, default="")
    service_unit = _service_unit_field()
    created_by = _user_field(_("Dicatat oleh"))

    class Meta:
        verbose_name = _("Transaksi keuangan lahan")
        verbose_name_plural = _("Transaksi keuangan lahan")
        ordering = ["-date", "-id"]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_number("TRX")
        super().save(*args, **kwargs)

    @property
    def is_income(self) -> bool:
        return self.transaction_type in enums.INCOME_TYPES


# --------------------------------------------------------------------------
# Permukiman kembali
# --------------------------------------------------------------------------


class ResettlementSite(TimeStampedModel):
    name = models.CharField(_("Nama kawasan permukiman kembali"), max_length=255)
    pengadaan_project = models.ForeignKey(
        "pengadaan.AcquisitionProject", verbose_name=_("Proyek pengadaan"), related_name="+",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    asset = models.ForeignKey(LandAsset, verbose_name=_("Aset lahan"), related_name="resettlement_sites", null=True, blank=True, on_delete=models.SET_NULL)
    address = models.CharField(_("Lokasi"), max_length=255, blank=True, default="")
    geometry = gmodels.MultiPolygonField(_("Batas kawasan"), srid=4326, null=True, blank=True)
    facilities = models.TextField(_("Fasilitas umum / sosial"), blank=True, default="")
    service_unit = _service_unit_field()

    class Meta:
        verbose_name = _("Kawasan permukiman kembali")
        verbose_name_plural = _("Kawasan permukiman kembali")
        ordering = ["name"]

    def __str__(self):
        return self.name


class ResettlementUnit(models.Model):
    site = models.ForeignKey(ResettlementSite, verbose_name=_("Kawasan"), related_name="units", on_delete=models.CASCADE)
    unit_number = models.CharField(_("Nomor kavling / unit"), max_length=32)
    house_type = models.CharField(_("Tipe rumah"), max_length=32, blank=True, default="")
    area_m2 = models.DecimalField(_("Luas kavling (m²)"), null=True, blank=True, **AREA)
    geometry = gmodels.MultiPolygonField(_("Batas kavling"), srid=4326, null=True, blank=True)
    status = models.CharField(_("Status hunian"), max_length=16, choices=enums.ResettlementUnitStatus.choices,
                              default=enums.ResettlementUnitStatus.VACANT)
    household = models.ForeignKey(
        "pengadaan.AffectedHousehold", verbose_name=_("Rumah tangga terdampak"), related_name="+",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    occupied_since = models.DateField(_("Dihuni sejak"), null=True, blank=True)
    note = models.CharField(_("Catatan"), max_length=255, blank=True, default="")

    class Meta:
        verbose_name = _("Unit / kavling permukiman kembali")
        verbose_name_plural = _("Unit / kavling permukiman kembali")
        ordering = ["site", "unit_number"]
        constraints = [
            models.UniqueConstraint(fields=["site", "unit_number"], name="asetlahan_unique_resettlement_unit"),
        ]

    def __str__(self):
        return f"{self.site} / {self.unit_number}"

    def save(self, *args, **kwargs):
        if self.geometry and not self.area_m2:
            from asetlahan.geo import area_m2

            self.area_m2 = area_m2(self.geometry)
        super().save(*args, **kwargs)


# --------------------------------------------------------------------------
# Perkara & advokat
# --------------------------------------------------------------------------


class Advocate(TimeStampedModel):
    name = models.CharField(_("Nama"), max_length=255)
    firm = models.CharField(_("Kantor hukum"), max_length=255, blank=True, default="")
    license_number = models.CharField(_("Nomor induk advokat"), max_length=64, blank=True, default="")
    is_internal = models.BooleanField(_("Biro hukum internal"), default=False)
    specialization = models.CharField(_("Keahlian"), max_length=255, blank=True, default="")
    phone = models.CharField(_("Telepon / WhatsApp"), max_length=32, blank=True, default="")
    email = models.EmailField(_("Surel"), blank=True, default="")
    address = models.TextField(_("Alamat"), blank=True, default="")
    contract_number = models.CharField(_("Nomor perjanjian jasa hukum"), max_length=128, blank=True, default="")
    is_active = models.BooleanField(_("Aktif"), default=True)

    class Meta:
        verbose_name = _("Advokat / kuasa hukum")
        verbose_name_plural = _("Advokat / kuasa hukum")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.firm})" if self.firm else self.name


class LegalCase(TimeStampedModel):
    number = models.CharField(_("Nomor internal"), max_length=32, unique=True, editable=False)
    court_case_number = models.CharField(_("Nomor perkara"), max_length=128, blank=True, default="")
    title = models.CharField(_("Pokok perkara"), max_length=255)
    case_type = models.CharField(_("Jenis perkara"), max_length=16, choices=enums.CaseType.choices, default=enums.CaseType.CIVIL)
    court = models.CharField(_("Forum"), max_length=16, choices=enums.Court.choices, default=enums.Court.PN)
    court_name = models.CharField(_("Nama pengadilan / lembaga"), max_length=255, blank=True, default="")
    our_position = models.CharField(_("Kedudukan instansi"), max_length=16, choices=enums.CasePosition.choices, default=enums.CasePosition.DEFENDANT)
    opposing_party = models.CharField(_("Pihak lawan"), max_length=255)
    status = models.CharField(_("Status"), max_length=16, choices=enums.CaseStatus.choices, default=enums.CaseStatus.PREPARATION)
    outcome = models.CharField(_("Hasil"), max_length=16, choices=enums.CaseOutcome.choices, blank=True, default="")
    filed_date = models.DateField(_("Tanggal didaftarkan"), null=True, blank=True)
    decision_date = models.DateField(_("Tanggal putusan"), null=True, blank=True)
    decision_summary = models.TextField(_("Amar / ringkasan putusan"), blank=True, default="")
    claim_value = models.DecimalField(_("Nilai gugatan (Rp)"), null=True, blank=True, **MONEY)
    disputed_area_m2 = models.DecimalField(_("Luas disengketakan (m²)"), null=True, blank=True, **AREA)
    assets = models.ManyToManyField(LandAsset, verbose_name=_("Aset terkait"), related_name="legal_cases", blank=True)
    pengadaan_objection = models.ForeignKey(
        "pengadaan.Objection", verbose_name=_("Keberatan / gugatan pengadaan"), related_name="+",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    advocates = models.ManyToManyField(Advocate, verbose_name=_("Kuasa hukum"), related_name="cases", blank=True)
    responsible = _user_field(_("Penanggung jawab"))
    service_unit = _service_unit_field()
    note = models.TextField(_("Catatan"), blank=True, default="")

    class Meta:
        verbose_name = _("Perkara")
        verbose_name_plural = _("Perkara & litigasi")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.number} {self.title}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_number("PRK")
        super().save(*args, **kwargs)

    @property
    def next_hearing(self):
        now = timezone.now()
        return self.hearings.filter(scheduled_at__gte=now).order_by("scheduled_at").first()

    @property
    def is_open(self) -> bool:
        return self.status in enums.OPEN_CASE_STATUSES


class CaseHearing(models.Model):
    case = models.ForeignKey(LegalCase, verbose_name=_("Perkara"), related_name="hearings", on_delete=models.CASCADE)
    scheduled_at = models.DateTimeField(_("Jadwal sidang"))
    agenda = models.CharField(_("Agenda"), max_length=255)
    location = models.CharField(_("Ruang / tempat"), max_length=255, blank=True, default="")
    result = models.TextField(_("Hasil sidang"), blank=True, default="")
    attended_by = models.CharField(_("Dihadiri oleh"), max_length=255, blank=True, default="")
    reminder_sent_at = models.DateTimeField(_("Pengingat terkirim"), null=True, blank=True, editable=False)

    class Meta:
        verbose_name = _("Jadwal sidang")
        verbose_name_plural = _("Jadwal sidang")
        ordering = ["scheduled_at"]

    def __str__(self):
        return f"{self.case.number} – {self.agenda}"


# --------------------------------------------------------------------------
# Okupasi / perambahan & citra satelit
# --------------------------------------------------------------------------


class SatelliteImage(TimeStampedModel):
    """Katalog & pengadaan citra satelit / foto udara untuk deteksi perubahan."""

    title = models.CharField(_("Judul"), max_length=255)
    provider = models.CharField(_("Penyedia"), max_length=128, help_text=_("Mis. BRIN, Maxar, Airbus, Planet, drone internal."))
    sensor = models.CharField(_("Sensor / satelit"), max_length=128, blank=True, default="")
    acquired_on = models.DateField(_("Tanggal perekaman"), null=True, blank=True)
    resolution_m = models.DecimalField(_("Resolusi (m)"), max_digits=6, decimal_places=2, null=True, blank=True)
    cloud_cover = models.PositiveSmallIntegerField(_("Tutupan awan (%)"), null=True, blank=True, validators=[MaxValueValidator(100)])
    coverage = gmodels.MultiPolygonField(_("Cakupan"), srid=4326, null=True, blank=True)
    status = models.CharField(_("Status pengadaan"), max_length=16, choices=enums.ImageryStatus.choices, default=enums.ImageryStatus.REQUESTED)
    requested_on = models.DateField(_("Tanggal permintaan"), default=datetime.date.today)
    cost = models.DecimalField(_("Biaya (Rp)"), null=True, blank=True, **MONEY)
    tile_url = models.CharField(
        _("URL ubin XYZ"), max_length=500, blank=True, default="",
        help_text=_("Mis. https://server/tiles/{z}/{x}/{y}.png – dipakai di peta & pembanding citra."),
    )
    wms_url = models.URLField(_("URL WMS"), max_length=500, blank=True, default="")
    wms_layers = models.CharField(_("Layer WMS"), max_length=255, blank=True, default="")
    file = PrivateFileField(verbose_name=_("Berkas citra (GeoTIFF/JPG)"), upload_to=upload_imagery, max_length=255, blank=True,
                            validators=[FileExtensionValidator(["tif", "tiff", "jpg", "jpeg", "png", "zip"])])
    note = models.TextField(_("Catatan"), blank=True, default="")

    class Meta:
        verbose_name = _("Citra satelit / foto udara")
        verbose_name_plural = _("Citra satelit & foto udara")
        ordering = ["-acquired_on", "-id"]

    def __str__(self):
        date = self.acquired_on.isoformat() if self.acquired_on else "-"
        return f"{self.title} ({date})"

    @property
    def is_viewable(self) -> bool:
        return bool(self.tile_url or (self.wms_url and self.wms_layers))


class EncroachmentCase(TimeStampedModel):
    number = models.CharField(_("Nomor kasus"), max_length=32, unique=True, editable=False)
    title = models.CharField(_("Judul temuan"), max_length=255)
    asset = models.ForeignKey(LandAsset, verbose_name=_("Aset"), related_name="encroachments", null=True, blank=True, on_delete=models.SET_NULL)
    detected_on = models.DateField(_("Tanggal ditemukan"), default=datetime.date.today)
    detection_method = models.CharField(_("Cara ditemukan"), max_length=16, choices=enums.DetectionMethod.choices, default=enums.DetectionMethod.PATROL)
    location = gmodels.PointField(_("Titik lokasi"), srid=4326, null=True, blank=True)
    area_geometry = gmodels.MultiPolygonField(_("Area okupasi"), srid=4326, null=True, blank=True)
    encroached_area_m2 = models.DecimalField(_("Luas terokupasi (m²)"), null=True, blank=True, **AREA)
    structure_type = models.CharField(_("Bentuk okupasi"), max_length=16, choices=enums.StructureType.choices, default=enums.StructureType.SEMI)
    encroacher_name = models.CharField(_("Nama pihak yang menguasai"), max_length=255, blank=True, default="")
    occupant_count = models.PositiveIntegerField(_("Jumlah penghuni / KK"), null=True, blank=True)
    severity = models.CharField(_("Tingkat"), max_length=8, choices=enums.Level.choices, default=enums.Level.MEDIUM)
    status = models.CharField(_("Status"), max_length=16, choices=enums.EncroachmentStatus.choices, default=enums.EncroachmentStatus.REPORTED)
    before_image = models.ForeignKey(SatelliteImage, verbose_name=_("Citra sebelum"), related_name="+", null=True, blank=True, on_delete=models.SET_NULL)
    after_image = models.ForeignKey(SatelliteImage, verbose_name=_("Citra sesudah"), related_name="+", null=True, blank=True, on_delete=models.SET_NULL)
    legal_case = models.ForeignKey(LegalCase, verbose_name=_("Perkara"), related_name="encroachments", null=True, blank=True, on_delete=models.SET_NULL)
    responsible = _user_field(_("Penanggung jawab"))
    resolved_on = models.DateField(_("Tanggal selesai"), null=True, blank=True)
    description = models.TextField(_("Uraian"), blank=True, default="")
    service_unit = _service_unit_field()

    class Meta:
        verbose_name = _("Kasus okupasi / perambahan")
        verbose_name_plural = _("Okupasi & perambahan")
        ordering = ["-detected_on", "-id"]

    def __str__(self):
        return f"{self.number} {self.title}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_number("OKP")
        if self.area_geometry and self.encroached_area_m2 is None:
            from asetlahan.geo import encroached_area

            self.encroached_area_m2 = encroached_area(self)
        if self.location is None and self.area_geometry:
            self.location = self.area_geometry.point_on_surface
        if self.asset_id is None and self.location is not None:
            from asetlahan.geo import asset_at

            found = asset_at(self.location)
            if found:
                self.asset = found
        if self.service_unit_id is None and self.asset_id:
            self.service_unit_id = self.asset.service_unit_id
        super().save(*args, **kwargs)

    @property
    def is_open(self) -> bool:
        return self.status in enums.OPEN_ENCROACHMENT_STATUSES


class EncroachmentActionLog(models.Model):
    case = models.ForeignKey(EncroachmentCase, verbose_name=_("Kasus"), related_name="actions", on_delete=models.CASCADE)
    date = models.DateField(_("Tanggal"), default=datetime.date.today)
    action = models.CharField(_("Tindakan"), max_length=16, choices=enums.EncroachmentAction.choices)
    letter_number = models.CharField(_("Nomor surat"), max_length=128, blank=True, default="")
    description = models.TextField(_("Uraian"), blank=True, default="")
    officer = _user_field(_("Petugas"))

    class Meta:
        verbose_name = _("Tindakan penanganan")
        verbose_name_plural = _("Tindakan penanganan")
        ordering = ["date", "id"]

    def __str__(self):
        return self.get_action_display()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        new_status = enums.ACTION_STATUS.get(self.action)
        if new_status:
            updates = {"status": new_status}
            if new_status == enums.EncroachmentStatus.RESOLVED:
                updates["resolved_on"] = self.date
            EncroachmentCase.objects.filter(pk=self.case_id).update(**updates)


# --------------------------------------------------------------------------
# Survei, fasilitator, urusan instansi
# --------------------------------------------------------------------------


class SurveyRequest(TimeStampedModel):
    number = models.CharField(_("Nomor"), max_length=32, unique=True, editable=False)
    survey_type = models.CharField(_("Jenis survei"), max_length=16, choices=enums.SurveyType.choices)
    asset = models.ForeignKey(LandAsset, verbose_name=_("Aset"), related_name="surveys", null=True, blank=True, on_delete=models.SET_NULL)
    pengadaan_project = models.ForeignKey(
        "pengadaan.AcquisitionProject", verbose_name=_("Proyek pengadaan"), related_name="+",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    purpose = models.TextField(_("Maksud & tujuan"))
    status = models.CharField(_("Status"), max_length=16, choices=enums.SurveyStatus.choices, default=enums.SurveyStatus.REQUESTED)
    requested_by = _user_field(_("Diajukan oleh"))
    assigned_to = _user_field(_("Petugas / surveyor internal"))
    team = models.ForeignKey(Team, verbose_name=_("Tim"), related_name="surveys", null=True, blank=True, on_delete=models.SET_NULL)
    vendor = models.CharField(_("Penyedia jasa / KJSB"), max_length=255, blank=True, default="")
    scheduled_date = models.DateField(_("Jadwal"), null=True, blank=True)
    completed_date = models.DateField(_("Tanggal selesai"), null=True, blank=True)
    cost = models.DecimalField(_("Biaya (Rp)"), null=True, blank=True, **MONEY)
    result_geometry = gmodels.MultiPolygonField(_("Hasil ukur (batas)"), srid=4326, null=True, blank=True)
    result_area_m2 = models.DecimalField(_("Luas hasil ukur (m²)"), null=True, blank=True, **AREA)
    findings = models.TextField(_("Temuan / hasil"), blank=True, default="")
    service_unit = _service_unit_field()

    class Meta:
        verbose_name = _("Survei & pemetaan")
        verbose_name_plural = _("Survei & pemetaan")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.number} {self.get_survey_type_display()}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_number("SRV")
        if self.result_geometry and not self.result_area_m2:
            from asetlahan.geo import area_m2

            self.result_area_m2 = area_m2(self.result_geometry)
        if self.service_unit_id is None and self.asset_id:
            self.service_unit_id = self.asset.service_unit_id
        super().save(*args, **kwargs)


class Facilitator(TimeStampedModel):
    name = models.CharField(_("Nama"), max_length=255)
    facilitator_type = models.CharField(_("Peran"), max_length=16, choices=enums.FacilitatorType.choices, default=enums.FacilitatorType.COMPANION)
    organization = models.CharField(_("Organisasi / perusahaan"), max_length=255, blank=True, default="")
    area = models.CharField(_("Wilayah kerja"), max_length=255, blank=True, default="")
    phone = models.CharField(_("Telepon / WhatsApp"), max_length=32, blank=True, default="")
    email = models.EmailField(_("Surel"), blank=True, default="")
    contract_number = models.CharField(_("Nomor kontrak / SK"), max_length=128, blank=True, default="")
    fee_note = models.CharField(_("Ketentuan honor / biaya"), max_length=255, blank=True, default="")
    is_active = models.BooleanField(_("Aktif"), default=True)

    class Meta:
        verbose_name = _("Fasilitator / pendamping")
        verbose_name_plural = _("Fasilitator & pendamping")
        ordering = ["name"]

    def __str__(self):
        return self.name


class LiaisonActivity(TimeStampedModel):
    """Urusan dengan instansi pemerintah (BPN, pemda, dinas, kementerian)."""

    subject = models.CharField(_("Perihal"), max_length=255)
    agency = models.CharField(_("Instansi tujuan"), max_length=255, help_text=_("Mis. Kantor Pertanahan, Dinas PUPR, Bapenda."))
    asset = models.ForeignKey(LandAsset, verbose_name=_("Aset"), related_name="liaisons", null=True, blank=True, on_delete=models.SET_NULL)
    pengadaan_project = models.ForeignKey(
        "pengadaan.AcquisitionProject", verbose_name=_("Proyek pengadaan"), related_name="+",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    facilitator = models.ForeignKey(Facilitator, verbose_name=_("Fasilitator"), related_name="liaisons", null=True, blank=True, on_delete=models.SET_NULL)
    officer = _user_field(_("Petugas"))
    status = models.CharField(_("Status"), max_length=16, choices=enums.LiaisonStatus.choices, default=enums.LiaisonStatus.PREPARING)
    submitted_on = models.DateField(_("Tanggal diajukan"), null=True, blank=True)
    reference_number = models.CharField(_("Nomor berkas / tanda terima"), max_length=128, blank=True, default="")
    next_follow_up = models.DateField(_("Tindak lanjut berikutnya"), null=True, blank=True)
    completed_on = models.DateField(_("Tanggal selesai"), null=True, blank=True)
    outcome = models.TextField(_("Hasil"), blank=True, default="")
    service_unit = _service_unit_field()

    class Meta:
        verbose_name = _("Urusan instansi pemerintah")
        verbose_name_plural = _("Urusan instansi pemerintah")
        ordering = ["-created_at"]

    def __str__(self):
        return self.subject


# --------------------------------------------------------------------------
# Tugas & sumber daya internal
# --------------------------------------------------------------------------


class Task(TimeStampedModel):
    number = models.CharField(_("Nomor"), max_length=32, unique=True, editable=False)
    title = models.CharField(_("Judul tugas"), max_length=255)
    description = models.TextField(_("Uraian"), blank=True, default="")
    task_type = models.CharField(_("Jenis"), max_length=16, choices=enums.TaskType.choices, default=enums.TaskType.ADMINISTRATION)
    priority = models.CharField(_("Prioritas"), max_length=16, choices=enums.Priority.choices, default=enums.Priority.NORMAL)
    status = models.CharField(_("Status"), max_length=16, choices=enums.TaskStatus.choices, default=enums.TaskStatus.NEW)
    assignee = _user_field(_("Ditugaskan kepada"), related_name="asetlahan_tasks")
    team = models.ForeignKey(Team, verbose_name=_("Tim"), related_name="tasks", null=True, blank=True, on_delete=models.SET_NULL)
    start_date = models.DateField(_("Mulai"), null=True, blank=True)
    due_date = models.DateField(_("Tenggat"), null=True, blank=True)
    completed_date = models.DateField(_("Selesai pada"), null=True, blank=True)
    progress = models.PositiveSmallIntegerField(_("Progres (%)"), default=0, validators=[MaxValueValidator(100)])
    depends_on = models.ForeignKey("self", verbose_name=_("Bergantung pada"), related_name="dependents", null=True, blank=True, on_delete=models.SET_NULL)
    asset = models.ForeignKey(LandAsset, verbose_name=_("Aset"), related_name="tasks", null=True, blank=True, on_delete=models.SET_NULL)
    legal_case = models.ForeignKey(LegalCase, verbose_name=_("Perkara"), related_name="tasks", null=True, blank=True, on_delete=models.SET_NULL)
    encroachment = models.ForeignKey(EncroachmentCase, verbose_name=_("Kasus okupasi"), related_name="tasks", null=True, blank=True, on_delete=models.SET_NULL)
    pengadaan_project = models.ForeignKey(
        "pengadaan.AcquisitionProject", verbose_name=_("Proyek pengadaan"), related_name="+",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    created_by = _user_field(_("Dibuat oleh"))
    service_unit = _service_unit_field()

    class Meta:
        verbose_name = _("Tugas / perintah kerja")
        verbose_name_plural = _("Tugas & perintah kerja")
        ordering = ["due_date", "-priority", "id"]

    def __str__(self):
        return f"{self.number} {self.title}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValidationError({"due_date": _("Tenggat tidak boleh sebelum tanggal mulai.")})
        node, seen = self.depends_on, set()
        while node is not None:
            if (self.pk and node.pk == self.pk) or node.pk in seen:
                raise ValidationError({"depends_on": _("Ketergantungan tugas tidak boleh melingkar.")})
            seen.add(node.pk)
            node = node.depends_on

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_number("TGS")
        if self.status == enums.TaskStatus.DONE:
            self.progress = 100
            self.completed_date = self.completed_date or timezone.localdate()
        elif self.completed_date and self.status != enums.TaskStatus.DONE:
            self.completed_date = None
        super().save(*args, **kwargs)

    @property
    def is_overdue(self) -> bool:
        return bool(
            self.due_date
            and self.status in enums.OPEN_TASK_STATUSES
            and self.due_date < timezone.localdate()
        )


# --------------------------------------------------------------------------
# Pengaduan masyarakat
# --------------------------------------------------------------------------


class Grievance(TimeStampedModel):
    number = models.CharField(_("Nomor pengaduan"), max_length=32, unique=True, editable=False)
    access_code = models.CharField(_("Kode akses"), max_length=12, editable=False)
    channel = models.CharField(_("Saluran"), max_length=16, choices=enums.GrievanceChannel.choices, default=enums.GrievanceChannel.PORTAL)
    category = models.ForeignKey(GrievanceCategory, verbose_name=_("Kategori"), related_name="grievances", null=True, blank=True, on_delete=models.SET_NULL)
    complainant_name = models.CharField(_("Nama pelapor"), max_length=255)
    phone = models.CharField(_("Telepon / WhatsApp"), max_length=32, blank=True, default="")
    email = models.EmailField(_("Surel"), blank=True, default="")
    subject = models.CharField(_("Perihal"), max_length=255)
    description = models.TextField(_("Uraian pengaduan"))
    location_text = models.CharField(_("Lokasi"), max_length=255, blank=True, default="")
    location = gmodels.PointField(_("Titik lokasi"), srid=4326, null=True, blank=True)
    attachment = PrivateFileField(verbose_name=_("Lampiran"), upload_to=upload_grievance, max_length=255, blank=True,
                                  validators=[FileExtensionValidator(["pdf", "jpg", "jpeg", "png"]), validate_upload_size])
    asset = models.ForeignKey(LandAsset, verbose_name=_("Aset"), related_name="grievances", null=True, blank=True, on_delete=models.SET_NULL)
    pengadaan_project = models.ForeignKey(
        "pengadaan.AcquisitionProject", verbose_name=_("Proyek pengadaan"), related_name="+",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    status = models.CharField(_("Status"), max_length=16, choices=enums.GrievanceStatus.choices, default=enums.GrievanceStatus.NEW)
    assigned_to = _user_field(_("Ditangani oleh"))
    due_date = models.DateField(_("Batas penyelesaian"), null=True, blank=True)
    response = models.TextField(_("Tanggapan untuk pelapor"), blank=True, default="",
                                help_text=_("Ditampilkan kepada pelapor saat mengecek status."))
    internal_note = models.TextField(_("Catatan internal"), blank=True, default="")
    resolved_on = models.DateField(_("Tanggal selesai"), null=True, blank=True)
    encroachment = models.ForeignKey(EncroachmentCase, verbose_name=_("Kasus okupasi"), related_name="grievances", null=True, blank=True, on_delete=models.SET_NULL)
    service_unit = _service_unit_field()

    class Meta:
        verbose_name = _("Pengaduan")
        verbose_name_plural = _("Pengaduan masyarakat")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.number} {self.subject}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_number("ADU")
        if not self.access_code:
            import secrets

            self.access_code = secrets.token_hex(4).upper()
        if self.due_date is None:
            days = (self.category.sla_days if self.category_id and self.category.sla_days else None) or (
                ModuleSettings.load().grievance_sla_days
            )
            self.due_date = timezone.localdate() + datetime.timedelta(days=days)
        if self.status in (enums.GrievanceStatus.RESOLVED, enums.GrievanceStatus.REJECTED):
            self.resolved_on = self.resolved_on or timezone.localdate()
        else:
            self.resolved_on = None
        super().save(*args, **kwargs)

    @property
    def is_overdue(self) -> bool:
        return bool(
            self.due_date
            and self.status in enums.OPEN_GRIEVANCE_STATUSES
            and self.due_date < timezone.localdate()
        )


# --------------------------------------------------------------------------
# Lelang / seleksi pemanfaatan lahan
# --------------------------------------------------------------------------


class Tender(TimeStampedModel):
    number = models.CharField(_("Nomor lelang"), max_length=32, unique=True, editable=False)
    title = models.CharField(_("Judul"), max_length=255)
    method = models.CharField(_("Metode"), max_length=16, choices=enums.TenderMethod.choices, default=enums.TenderMethod.AUCTION)
    asset = models.ForeignKey(LandAsset, verbose_name=_("Aset"), related_name="tenders", null=True, blank=True, on_delete=models.PROTECT)
    alokasi_plot = models.ForeignKey(
        "alokasi.LandPlot", verbose_name=_("Lahan alokasi"), related_name="+",
        null=True, blank=True, on_delete=models.PROTECT,
    )
    description = models.TextField(_("Uraian & peruntukan"))
    requirements = models.TextField(_("Persyaratan peserta"), blank=True, default="")
    reserve_price = models.DecimalField(_("Harga / nilai limit (Rp)"), null=True, blank=True, **MONEY)
    deposit = models.DecimalField(_("Jaminan penawaran (Rp)"), null=True, blank=True, **MONEY)
    open_at = models.DateTimeField(_("Penawaran dibuka"))
    close_at = models.DateTimeField(_("Penawaran ditutup"))
    status = models.CharField(_("Status"), max_length=16, choices=enums.TenderStatus.choices, default=enums.TenderStatus.DRAFT)
    winner = models.ForeignKey("Bid", verbose_name=_("Penawaran pemenang"), related_name="+", null=True, blank=True, on_delete=models.SET_NULL)
    awarded_on = models.DateField(_("Tanggal penetapan"), null=True, blank=True)
    service_unit = _service_unit_field()

    class Meta:
        verbose_name = _("Lelang / seleksi lahan")
        verbose_name_plural = _("Lelang & seleksi lahan")
        ordering = ["-open_at"]

    def __str__(self):
        return f"{self.number} {self.title}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.open_at and self.close_at and self.close_at <= self.open_at:
            raise ValidationError({"close_at": _("Waktu tutup harus setelah waktu buka.")})
        if not self.asset_id and not self.alokasi_plot_id:
            raise ValidationError(_("Pilih aset atau lahan alokasi yang dilelang."))

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_number("LLG")
        super().save(*args, **kwargs)

    @property
    def is_accepting_bids(self) -> bool:
        now = timezone.now()
        return self.status == enums.TenderStatus.ANNOUNCED and self.open_at <= now < self.close_at

    @property
    def location_name(self) -> str:
        if self.asset_id:
            return str(self.asset)
        if self.alokasi_plot_id:
            return str(self.alokasi_plot)
        return ""


class Bid(TimeStampedModel):
    tender = models.ForeignKey(Tender, verbose_name=_("Lelang"), related_name="bids", on_delete=models.CASCADE)
    applicant = models.ForeignKey(
        "alokasi.Applicant", verbose_name=_("Akun pemohon"), related_name="bids",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    bidder_name = models.CharField(_("Nama peserta"), max_length=255)
    email = models.EmailField(_("Surel"), blank=True, default="")
    phone = models.CharField(_("Telepon"), max_length=32, blank=True, default="")
    amount = models.DecimalField(_("Nilai penawaran (Rp)"), validators=[MinValueValidator(0)], **MONEY)
    proposal = PrivateFileField(verbose_name=_("Dokumen penawaran"), upload_to=upload_bid, max_length=255, blank=True,
                                validators=[FileExtensionValidator(["pdf", "zip"]), validate_upload_size])
    technical_score = models.DecimalField(_("Nilai teknis"), max_digits=5, decimal_places=2, null=True, blank=True,
                                          validators=[MinValueValidator(0), MaxValueValidator(100)])
    status = models.CharField(_("Status"), max_length=16, choices=enums.BidStatus.choices, default=enums.BidStatus.SUBMITTED)
    evaluation_note = models.TextField(_("Catatan evaluasi"), blank=True, default="")

    class Meta:
        verbose_name = _("Penawaran")
        verbose_name_plural = _("Penawaran")
        ordering = ["tender", "-amount"]
        constraints = [
            models.UniqueConstraint(
                fields=["tender", "applicant"], condition=models.Q(applicant__isnull=False),
                name="asetlahan_one_bid_per_applicant",
            )
        ]

    def __str__(self):
        return f"{self.bidder_name} – {self.tender.number}"


# --------------------------------------------------------------------------
# Dokumen, berbagi peta, laporan lapangan
# --------------------------------------------------------------------------


class Document(TimeStampedModel):
    title = models.CharField(_("Judul"), max_length=255)
    doc_type = models.CharField(_("Jenis"), max_length=16, choices=enums.DocumentType.choices, default=enums.DocumentType.OTHER)
    number = models.CharField(_("Nomor"), max_length=128, blank=True, default="")
    document_date = models.DateField(_("Tanggal dokumen"), null=True, blank=True)
    file = PrivateFileField(verbose_name=_("Berkas"), upload_to=upload_document, max_length=255, validators=DOCUMENT_VALIDATORS)
    phase = models.CharField(_("Foto sebelum/sesudah"), max_length=8, choices=enums.PhotoPhase.choices, blank=True, default="")
    asset = models.ForeignKey(LandAsset, verbose_name=_("Aset"), related_name="documents", null=True, blank=True, on_delete=models.CASCADE)
    legal_case = models.ForeignKey(LegalCase, verbose_name=_("Perkara"), related_name="documents", null=True, blank=True, on_delete=models.CASCADE)
    encroachment = models.ForeignKey(EncroachmentCase, verbose_name=_("Kasus okupasi"), related_name="documents", null=True, blank=True, on_delete=models.CASCADE)
    survey = models.ForeignKey(SurveyRequest, verbose_name=_("Survei"), related_name="documents", null=True, blank=True, on_delete=models.CASCADE)
    liaison = models.ForeignKey(LiaisonActivity, verbose_name=_("Urusan instansi"), related_name="documents", null=True, blank=True, on_delete=models.CASCADE)
    tender = models.ForeignKey(Tender, verbose_name=_("Lelang"), related_name="documents", null=True, blank=True, on_delete=models.CASCADE)
    extracted_text = models.TextField(_("Teks hasil OCR / ekstraksi"), blank=True, default="")
    extracted_fields = models.JSONField(_("Data terbaca"), default=dict, blank=True)
    ocr_status = models.CharField(_("Status OCR"), max_length=16, choices=enums.OcrStatus.choices, blank=True, default="")
    uploaded_by = _user_field(_("Diunggah oleh"))
    service_unit = _service_unit_field()
    note = models.CharField(_("Catatan"), max_length=255, blank=True, default="")

    class Meta:
        verbose_name = _("Dokumen")
        verbose_name_plural = _("Dokumen & arsip")
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.service_unit_id is None:
            for related in (self.asset, self.legal_case, self.encroachment, self.survey, self.liaison, self.tender):
                if related is not None and getattr(related, "service_unit_id", None):
                    self.service_unit_id = related.service_unit_id
                    break
        super().save(*args, **kwargs)

    @property
    def is_image(self) -> bool:
        return (self.file.name or "").lower().rsplit(".", 1)[-1] in IMAGE_EXTENSIONS


def _default_share_expiry():
    return timezone.now() + datetime.timedelta(days=30)


class MapShare(TimeStampedModel):
    """Tautan baca-saja peta batas bidang untuk pemangku kepentingan."""

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(_("Judul peta"), max_length=255)
    assets = models.ManyToManyField(LandAsset, verbose_name=_("Aset ditampilkan"), related_name="shares", blank=True)
    pengadaan_project = models.ForeignKey(
        "pengadaan.AcquisitionProject", verbose_name=_("Bidang proyek pengadaan"), related_name="+",
        null=True, blank=True, on_delete=models.CASCADE,
    )
    resettlement_site = models.ForeignKey(ResettlementSite, verbose_name=_("Kawasan permukiman kembali"), related_name="+",
                                          null=True, blank=True, on_delete=models.CASCADE)
    show_owner_names = models.BooleanField(_("Tampilkan nama pemegang hak"), default=False)
    expires_at = models.DateTimeField(_("Berlaku sampai"), default=_default_share_expiry)
    is_active = models.BooleanField(_("Aktif"), default=True)
    created_by = _user_field(_("Dibuat oleh"))
    view_count = models.PositiveIntegerField(_("Dilihat"), default=0, editable=False)

    class Meta:
        verbose_name = _("Peta berbagi")
        verbose_name_plural = _("Peta berbagi (tautan publik)")
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def is_valid(self) -> bool:
        return self.is_active and self.expires_at > timezone.now()


class FieldReport(TimeStampedModel):
    """Catatan petugas lapangan dari aplikasi seluler (bisa direkam luring)."""

    client_id = models.UUIDField(_("ID perangkat"), unique=True, help_text=_("Mencegah laporan ganda saat sinkronisasi ulang."))
    report_type = models.CharField(_("Jenis"), max_length=16, choices=enums.FieldReportType.choices, default=enums.FieldReportType.PATROL)
    location = gmodels.PointField(_("Lokasi GPS"), srid=4326)
    accuracy_m = models.DecimalField(_("Akurasi GPS (m)"), max_digits=8, decimal_places=1, null=True, blank=True)
    captured_at = models.DateTimeField(_("Direkam pada"))
    note = models.TextField(_("Catatan"), blank=True, default="")
    photo = PrivateFileField(verbose_name=_("Foto"), upload_to=upload_field, max_length=255, blank=True, validators=IMAGE_VALIDATORS)
    asset = models.ForeignKey(LandAsset, verbose_name=_("Aset"), related_name="field_reports", null=True, blank=True, on_delete=models.SET_NULL)
    reported_by = _user_field(_("Petugas"))
    encroachment = models.ForeignKey(EncroachmentCase, verbose_name=_("Dijadikan kasus okupasi"), related_name="field_reports",
                                     null=True, blank=True, on_delete=models.SET_NULL)
    service_unit = _service_unit_field()

    class Meta:
        verbose_name = _("Laporan lapangan")
        verbose_name_plural = _("Laporan lapangan")
        ordering = ["-captured_at"]

    def __str__(self):
        return f"{self.get_report_type_display()} {self.captured_at:%d-%m-%Y %H:%M}"

    def save(self, *args, **kwargs):
        if self.asset_id is None and self.location is not None:
            from asetlahan.geo import asset_at

            self.asset = asset_at(self.location)
        if self.service_unit_id is None and self.asset_id:
            self.service_unit_id = self.asset.service_unit_id
        super().save(*args, **kwargs)


for _model in (
    ModuleSettings, AssetCategory, GrievanceCategory, Team, LandAsset, OwnershipRecord, Heirship, HeirMember,
    Stakeholder, StakeholderEngagement, AssetValuation, ValuationItem, TaxObligation, LandTransaction,
    ResettlementSite, ResettlementUnit, Advocate, LegalCase, CaseHearing, SatelliteImage, EncroachmentCase,
    EncroachmentActionLog, SurveyRequest, Facilitator, LiaisonActivity, Task, Grievance, Tender, Bid, Document,
    MapShare, FieldReport,
):
    auditlog.register(_model)
