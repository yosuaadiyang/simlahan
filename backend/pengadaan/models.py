"""Model modul pengadaan tanah (land acquisition).

Struktur domain diadaptasi dari AtulTejaswi/land-acquisition-management-system
(lisensi MIT) lalu disesuaikan dengan tahapan UU 2/2012 jo. UU 6/2023 dan
PP 19/2021 jo. PP 39/2023: Perencanaan → Persiapan → Pelaksanaan → Penyerahan Hasil.
"""

import datetime
from decimal import Decimal

from auditlog.registry import auditlog
from django.conf import settings
from django.contrib.gis.db import models as gmodels
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from sequences import get_next_value

from file_operations.private_files import PrivateFileField
from file_operations.viewsets.mixins import FileScanMixin
from leasing.models.mixins import TimeStampedModel, TimeStampedSafeDeleteModel
from pengadaan import enums
from pengadaan.crypto import EncryptedCharField, fingerprint

MONEY = {"max_digits": 20, "decimal_places": 2}
AREA = {"max_digits": 16, "decimal_places": 2}


class Holiday(models.Model):
    """Libur nasional dan cuti bersama (SKB 3 Menteri) untuk perhitungan hari kerja."""

    date = models.DateField(verbose_name=_("Date"), unique=True)
    name = models.CharField(verbose_name=_("Name"), max_length=255)
    is_collective_leave = models.BooleanField(
        verbose_name=_("Collective leave"), default=False
    )

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Holiday")
        verbose_name_plural = pgettext_lazy("Model name", "Holidays")
        ordering = ["date"]

    def __str__(self):
        return f"{self.date:%d.%m.%Y} {self.name}"


class DeadlineRule(models.Model):
    """Batas waktu yang dapat dikonfigurasi, beserta dasar hukumnya."""

    UNIT_CHOICES = (
        ("workdays", _("working days")),
        ("days", _("days")),
        ("years", _("years")),
    )

    code = models.CharField(verbose_name=_("Code"), max_length=64, unique=True)
    name = models.CharField(verbose_name=_("Name"), max_length=255)
    amount = models.PositiveIntegerField(verbose_name=_("Amount"))
    unit = models.CharField(
        verbose_name=_("Unit"), max_length=16, choices=UNIT_CHOICES, default="workdays"
    )
    legal_basis = models.CharField(
        verbose_name=_("Legal basis"), max_length=255, blank=True, default=""
    )
    description = models.TextField(
        verbose_name=_("Description"), blank=True, default=""
    )

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Deadline rule")
        verbose_name_plural = pgettext_lazy("Model name", "Deadline rules")
        ordering = ["code"]

    def __str__(self):
        return f"{self.name} ({self.amount} {self.get_unit_display()})"

    @classmethod
    def get(cls, code: str) -> "DeadlineRule | None":
        return cls.objects.filter(code=code).first()

    def apply(self, start: datetime.date | None) -> datetime.date | None:
        from pengadaan.workdays import add_workdays, add_years

        if start is None:
            return None
        if self.unit == "workdays":
            return add_workdays(start, self.amount)
        if self.unit == "years":
            return add_years(start, self.amount)
        return start + datetime.timedelta(days=self.amount)


def apply_rule(code: str, start: datetime.date | None) -> datetime.date | None:
    rule = DeadlineRule.get(code)
    if rule is None:
        return None
    return rule.apply(start)


def _project_identifier() -> str:
    year = timezone.localdate().year
    value = get_next_value(f"pengadaan_project_{year}")
    return f"PT-{year}-{value:04d}"


class AcquisitionProject(TimeStampedSafeDeleteModel):
    """Proyek pengadaan tanah."""

    identifier = models.CharField(
        verbose_name=_("Identifier"), max_length=32, unique=True, editable=False
    )
    name = models.CharField(verbose_name=_("Name"), max_length=255)
    description = models.TextField(
        verbose_name=_("Description"), blank=True, default=""
    )
    acquisition_type = models.CharField(
        verbose_name=_("Acquisition type"),
        max_length=32,
        choices=enums.AcquisitionType.choices,
        default=enums.AcquisitionType.PUBLIC_INTEREST,
    )
    purpose_category = models.CharField(
        verbose_name=_("Purpose category"),
        max_length=32,
        choices=enums.PublicInterestCategory.choices,
        default=enums.PublicInterestCategory.OTHER,
    )
    priority = models.CharField(
        verbose_name=_("Priority"),
        max_length=32,
        choices=enums.Priority.choices,
        default=enums.Priority.MEDIUM,
    )
    funding_source = models.CharField(
        verbose_name=_("Funding source"),
        max_length=16,
        choices=enums.FundingSource.choices,
        default=enums.FundingSource.APBN,
    )
    requiring_agency = models.CharField(
        verbose_name=_("Agency requiring the land"), max_length=255
    )
    requiring_agency_contact = models.CharField(
        verbose_name=_("Contact of the requiring agency"),
        max_length=255,
        blank=True,
        default="",
    )
    executing_office = models.CharField(
        verbose_name=_("Executing land office"), max_length=255, blank=True, default=""
    )
    executing_chair = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Executing chair"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    service_unit = models.ForeignKey(
        "leasing.ServiceUnit",
        verbose_name=_("Service unit"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    municipality = models.ForeignKey(
        "leasing.Municipality",
        verbose_name=_("Regency / city"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    location_description = models.TextField(
        verbose_name=_("Location description"), blank=True, default=""
    )
    estimated_area_m2 = models.DecimalField(
        verbose_name=_("Estimated land requirement (m²)"),
        null=True,
        blank=True,
        **AREA,
    )
    estimated_budget = models.DecimalField(
        verbose_name=_("Estimated budget (IDR)"), null=True, blank=True, **MONEY
    )
    stage = models.CharField(
        verbose_name=_("Stage"),
        max_length=32,
        choices=enums.ProjectStage.choices,
        default=enums.ProjectStage.PLANNING,
    )
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=16,
        choices=enums.ProjectStatus.choices,
        default=enums.ProjectStatus.DRAFT,
    )
    # Perencanaan
    planning_document_number = models.CharField(
        verbose_name=_("Planning document (DPPT) number"),
        max_length=255,
        blank=True,
        default="",
    )
    planning_document_date = models.DateField(
        verbose_name=_("Planning document (DPPT) date"), null=True, blank=True
    )
    # Persiapan
    notification_date = models.DateField(
        verbose_name=_("Notification of development plan date"), null=True, blank=True
    )
    public_consultation_date = models.DateField(
        verbose_name=_("Public consultation date"), null=True, blank=True
    )
    location_decree_number = models.CharField(
        verbose_name=_("Location determination (Penlok) decree number"),
        max_length=255,
        blank=True,
        default="",
    )
    location_decree_date = models.DateField(
        verbose_name=_("Location determination (Penlok) date"), null=True, blank=True
    )
    location_decree_extended = models.BooleanField(
        verbose_name=_("Location determination extended"), default=False
    )
    location_announcement_date = models.DateField(
        verbose_name=_("Location determination announcement date"),
        null=True,
        blank=True,
    )
    start_date = models.DateField(verbose_name=_("Start date"), null=True, blank=True)
    target_completion_date = models.DateField(
        verbose_name=_("Target completion date"), null=True, blank=True
    )
    geometry = gmodels.MultiPolygonField(
        srid=4326, verbose_name=_("Geometry"), null=True, blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Created by"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Land acquisition project")
        verbose_name_plural = pgettext_lazy("Model name", "Land acquisition projects")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.identifier} {self.name}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if not self.identifier:
            self.identifier = _project_identifier()
        super().save(*args, **kwargs)
        if is_new:
            from pengadaan.milestones import create_default_milestones

            create_default_milestones(self)

    @property
    def location_decree_expires_on(self) -> datetime.date | None:
        expires = apply_rule("penlok_validity", self.location_decree_date)
        if expires and self.location_decree_extended:
            return apply_rule("penlok_extension", expires) or expires
        return expires

    @property
    def ptun_filing_deadline(self) -> datetime.date | None:
        return apply_rule(
            "ptun_filing",
            self.location_announcement_date or self.location_decree_date,
        )


class AcquisitionMilestone(TimeStampedModel):
    """Langkah kerja/jadwal per tahapan (dibuat otomatis dari templat)."""

    project = models.ForeignKey(
        AcquisitionProject,
        verbose_name=_("Project"),
        related_name="milestones",
        on_delete=models.CASCADE,
    )
    stage = models.CharField(
        verbose_name=_("Stage"), max_length=32, choices=enums.ProjectStage.choices
    )
    code = models.CharField(
        verbose_name=_("Code"), max_length=64, blank=True, default=""
    )
    sequence = models.PositiveIntegerField(verbose_name=_("Order"), default=0)
    title = models.CharField(verbose_name=_("Title"), max_length=255)
    legal_basis = models.CharField(
        verbose_name=_("Legal basis"), max_length=255, blank=True, default=""
    )
    planned_date = models.DateField(
        verbose_name=_("Planned date"), null=True, blank=True
    )
    actual_date = models.DateField(verbose_name=_("Actual date"), null=True, blank=True)
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=16,
        choices=enums.MilestoneStatus.choices,
        default=enums.MilestoneStatus.PENDING,
    )
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Responsible person"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    note = models.TextField(verbose_name=_("Note"), blank=True, default="")

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Milestone")
        verbose_name_plural = pgettext_lazy("Model name", "Milestones")
        ordering = ["project", "sequence", "id"]

    def __str__(self):
        return self.title


class AcquisitionParcel(TimeStampedSafeDeleteModel):
    """Bidang tanah yang terkena pengadaan."""

    project = models.ForeignKey(
        AcquisitionProject,
        verbose_name=_("Project"),
        related_name="parcels",
        on_delete=models.PROTECT,
    )
    parcel_number = models.CharField(verbose_name=_("Parcel number"), max_length=64)
    nib = models.CharField(
        verbose_name=_("Parcel identification number (NIB)"),
        max_length=64,
        blank=True,
        default="",
    )
    district = models.ForeignKey(
        "leasing.District",
        verbose_name=_("Sub-district (kecamatan)"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    village = models.CharField(
        verbose_name=_("Village (desa/kelurahan)"),
        max_length=255,
        blank=True,
        default="",
    )
    address = models.CharField(
        verbose_name=_("Address"), max_length=255, blank=True, default=""
    )
    right_type = models.CharField(
        verbose_name=_("Type of right"),
        max_length=32,
        choices=enums.LandRightType.choices,
        default=enums.LandRightType.SHM,
    )
    certificate_number = models.CharField(
        verbose_name=_("Certificate / evidence number"),
        max_length=128,
        blank=True,
        default="",
    )
    measured_area_m2 = models.DecimalField(
        verbose_name=_("Measured area (m²)"), null=True, blank=True, **AREA
    )
    affected_area_m2 = models.DecimalField(
        verbose_name=_("Affected area (m²)"), null=True, blank=True, **AREA
    )
    land_use = models.CharField(
        verbose_name=_("Land use"),
        max_length=32,
        choices=enums.LandUse.choices,
        default=enums.LandUse.OTHER,
    )
    building_description = models.TextField(
        verbose_name=_("Buildings"), blank=True, default=""
    )
    building_area_m2 = models.DecimalField(
        verbose_name=_("Building area (m²)"), null=True, blank=True, **AREA
    )
    plants_description = models.TextField(
        verbose_name=_("Plants"), blank=True, default=""
    )
    other_objects_description = models.TextField(
        verbose_name=_("Other objects related to the land"), blank=True, default=""
    )
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=32,
        choices=enums.ParcelStatus.choices,
        default=enums.ParcelStatus.IDENTIFIED,
        editable=False,
    )
    is_excluded = models.BooleanField(
        verbose_name=_("Excluded from acquisition"), default=False
    )
    is_disputed = models.BooleanField(verbose_name=_("Disputed"), default=False)
    geometry = gmodels.MultiPolygonField(
        srid=4326, verbose_name=_("Geometry"), null=True, blank=True
    )
    note = models.TextField(verbose_name=_("Note"), blank=True, default="")

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Parcel")
        verbose_name_plural = pgettext_lazy("Model name", "Parcels")
        ordering = ["project", "parcel_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "parcel_number"],
                condition=models.Q(deleted__isnull=True),
                name="pengadaan_unique_parcel_number_per_project",
            )
        ]

    def __str__(self):
        return f"{self.project.identifier} / {self.parcel_number}"

    @property
    def remaining_area_m2(self) -> Decimal | None:
        if self.measured_area_m2 is None or self.affected_area_m2 is None:
            return None
        return max(self.measured_area_m2 - self.affected_area_m2, Decimal("0"))

    def recompute_status(self, save: bool = True) -> str:
        from pengadaan.status import derive_parcel_status

        new_status = derive_parcel_status(self)
        if new_status != self.status:
            self.status = new_status
            if save and self.pk:
                AcquisitionParcel.all_objects.filter(pk=self.pk).update(
                    status=new_status
                )
        return new_status


class EntitledParty(TimeStampedSafeDeleteModel):
    """Pihak yang berhak atas bidang tanah."""

    parcel = models.ForeignKey(
        AcquisitionParcel,
        verbose_name=_("Parcel"),
        related_name="parties",
        on_delete=models.CASCADE,
    )
    party_type = models.CharField(
        verbose_name=_("Party type"),
        max_length=32,
        choices=enums.PartyType.choices,
        default=enums.PartyType.INDIVIDUAL,
    )
    role = models.CharField(
        verbose_name=_("Role"),
        max_length=32,
        choices=enums.PartyRole.choices,
        default=enums.PartyRole.OWNER,
    )
    name = models.CharField(verbose_name=_("Name"), max_length=255)
    nik = EncryptedCharField(
        verbose_name=_("National identification number (NIK)"), blank=True, default=""
    )
    nik_fingerprint = models.CharField(
        max_length=64, blank=True, default="", editable=False, db_index=True
    )
    npwp = models.CharField(
        verbose_name=_("Taxpayer identification number (NPWP)"),
        max_length=32,
        blank=True,
        default="",
    )
    address = models.TextField(verbose_name=_("Address"), blank=True, default="")
    phone = models.CharField(
        verbose_name=_("Phone"), max_length=64, blank=True, default=""
    )
    email = models.EmailField(verbose_name=_("Email"), blank=True, default="")
    share_percentage = models.DecimalField(
        verbose_name=_("Share (%)"),
        max_digits=6,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    bank_name = models.CharField(
        verbose_name=_("Bank name"), max_length=128, blank=True, default=""
    )
    bank_account_number = EncryptedCharField(
        verbose_name=_("Bank account number"), blank=True, default=""
    )
    bank_account_holder = models.CharField(
        verbose_name=_("Bank account holder"), max_length=255, blank=True, default=""
    )
    contact = models.ForeignKey(
        "leasing.Contact",
        verbose_name=_("Contact"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    note = models.TextField(verbose_name=_("Note"), blank=True, default="")

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Entitled party")
        verbose_name_plural = pgettext_lazy("Model name", "Entitled parties")
        ordering = ["parcel", "id"]
        permissions = [
            (
                "view_sensitive_personal_data",
                _("Can view sensitive personal data (NIK, bank account)"),
            )
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.nik_fingerprint = fingerprint(self.nik) or ""
        super().save(*args, **kwargs)


class ParcelSurvey(TimeStampedModel):
    """Inventarisasi (Satgas A, fisik) dan identifikasi (Satgas B, yuridis)."""

    parcel = models.ForeignKey(
        AcquisitionParcel,
        verbose_name=_("Parcel"),
        related_name="surveys",
        on_delete=models.CASCADE,
    )
    survey_type = models.CharField(
        verbose_name=_("Survey type"), max_length=16, choices=enums.SurveyType.choices
    )
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=32,
        choices=enums.SurveyStatus.choices,
        default=enums.SurveyStatus.SCHEDULED,
    )
    survey_date = models.DateField(verbose_name=_("Survey date"), null=True, blank=True)
    team_name = models.CharField(
        verbose_name=_("Task force"), max_length=255, blank=True, default=""
    )
    surveyor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Surveyor"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    latitude = models.DecimalField(
        verbose_name=_("Latitude"),
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        verbose_name=_("Longitude"),
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
    )
    findings = models.TextField(verbose_name=_("Findings"), blank=True, default="")

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Parcel survey")
        verbose_name_plural = pgettext_lazy("Model name", "Parcel surveys")
        ordering = ["parcel", "-survey_date", "-id"]


class Announcement(TimeStampedModel):
    """Pengumuman (rencana pembangunan, penlok, hasil inventarisasi, dll.)."""

    project = models.ForeignKey(
        AcquisitionProject,
        verbose_name=_("Project"),
        related_name="announcements",
        on_delete=models.CASCADE,
    )
    announcement_type = models.CharField(
        verbose_name=_("Announcement type"),
        max_length=32,
        choices=enums.AnnouncementType.choices,
    )
    announced_on = models.DateField(verbose_name=_("Announced on"))
    location = models.CharField(
        verbose_name=_("Place of announcement"), max_length=255, blank=True, default=""
    )
    document_number = models.CharField(
        verbose_name=_("Document number"), max_length=255, blank=True, default=""
    )
    note = models.TextField(verbose_name=_("Note"), blank=True, default="")

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Announcement")
        verbose_name_plural = pgettext_lazy("Model name", "Announcements")
        ordering = ["project", "-announced_on"]

    @property
    def period_ends_on(self) -> datetime.date | None:
        code = {
            enums.AnnouncementType.INVENTORY: "inventory_announcement",
            enums.AnnouncementType.LOCATION_DETERMINATION: "penlok_announcement",
        }.get(self.announcement_type)
        return apply_rule(code, self.announced_on) if code else None

    @property
    def objection_deadline(self) -> datetime.date | None:
        if self.announcement_type == enums.AnnouncementType.INVENTORY:
            return apply_rule("inventory_objection", self.announced_on)
        return None


class Valuation(TimeStampedModel):
    """Penilaian ganti kerugian oleh Penilai/KJPP per bidang."""

    parcel = models.ForeignKey(
        AcquisitionParcel,
        verbose_name=_("Parcel"),
        related_name="valuations",
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=16,
        choices=enums.ValuationStatus.choices,
        default=enums.ValuationStatus.DRAFT,
    )
    appraiser_firm = models.CharField(
        verbose_name=_("Public appraiser firm (KJPP)"),
        max_length=255,
        blank=True,
        default="",
    )
    appraiser_name = models.CharField(
        verbose_name=_("Appraiser name"), max_length=255, blank=True, default=""
    )
    appraiser_license = models.CharField(
        verbose_name=_("Appraiser license number"),
        max_length=128,
        blank=True,
        default="",
    )
    report_number = models.CharField(
        verbose_name=_("Report number"), max_length=128, blank=True, default=""
    )
    valuation_date = models.DateField(
        verbose_name=_("Valuation date"), null=True, blank=True
    )
    submitted_on = models.DateField(
        verbose_name=_("Results submitted to the land agency on"),
        null=True,
        blank=True,
    )
    value_land = models.DecimalField(
        verbose_name=_("Land value"), default=Decimal("0"), **MONEY
    )
    value_space = models.DecimalField(
        verbose_name=_("Above- and below-ground space value"),
        default=Decimal("0"),
        **MONEY,
    )
    value_building = models.DecimalField(
        verbose_name=_("Building value"), default=Decimal("0"), **MONEY
    )
    value_plants = models.DecimalField(
        verbose_name=_("Plants value"), default=Decimal("0"), **MONEY
    )
    value_other_objects = models.DecimalField(
        verbose_name=_("Other objects value"), default=Decimal("0"), **MONEY
    )
    value_non_physical = models.DecimalField(
        verbose_name=_("Non-physical losses value"),
        help_text=_(
            "E.g. transaction costs, waiting period compensation, relocation costs, "
            "loss of business, profession change costs, remaining land value."
        ),
        default=Decimal("0"),
        **MONEY,
    )
    total_value = models.DecimalField(
        verbose_name=_("Total value"), default=Decimal("0"), editable=False, **MONEY
    )
    note = models.TextField(verbose_name=_("Note"), blank=True, default="")

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Valuation")
        verbose_name_plural = pgettext_lazy("Model name", "Valuations")
        ordering = ["parcel", "-valuation_date", "-id"]

    def save(self, *args, **kwargs):
        self.total_value = sum(
            (
                self.value_land or 0,
                self.value_space or 0,
                self.value_building or 0,
                self.value_plants or 0,
                self.value_other_objects or 0,
                self.value_non_physical or 0,
            ),
            Decimal("0"),
        )
        super().save(*args, **kwargs)

    @property
    def deliberation_deadline(self) -> datetime.date | None:
        return apply_rule("deliberation", self.submitted_on)


class Deliberation(TimeStampedModel):
    """Musyawarah penetapan bentuk dan/atau besarnya ganti kerugian."""

    project = models.ForeignKey(
        AcquisitionProject,
        verbose_name=_("Project"),
        related_name="deliberations",
        on_delete=models.CASCADE,
    )
    held_on = models.DateField(verbose_name=_("Held on"))
    location = models.CharField(
        verbose_name=_("Location"), max_length=255, blank=True, default=""
    )
    minutes_number = models.CharField(
        verbose_name=_("Minutes number"), max_length=128, blank=True, default=""
    )
    chaired_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Chaired by"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    note = models.TextField(verbose_name=_("Note"), blank=True, default="")

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Deliberation")
        verbose_name_plural = pgettext_lazy("Model name", "Deliberations")
        ordering = ["project", "-held_on"]

    def __str__(self):
        return f"{self.held_on:%d.%m.%Y} {self.minutes_number}".strip()


class DeliberationResult(TimeStampedModel):
    deliberation = models.ForeignKey(
        Deliberation,
        verbose_name=_("Deliberation"),
        related_name="results",
        on_delete=models.CASCADE,
    )
    parcel = models.ForeignKey(
        AcquisitionParcel,
        verbose_name=_("Parcel"),
        related_name="deliberation_results",
        on_delete=models.CASCADE,
    )
    party = models.ForeignKey(
        EntitledParty,
        verbose_name=_("Entitled party"),
        related_name="deliberation_results",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    outcome = models.CharField(
        verbose_name=_("Outcome"),
        max_length=16,
        choices=enums.DeliberationOutcome.choices,
    )
    compensation_form = models.CharField(
        verbose_name=_("Form of compensation"),
        max_length=32,
        choices=enums.CompensationForm.choices,
        default=enums.CompensationForm.MONEY,
    )
    agreed_amount = models.DecimalField(
        verbose_name=_("Agreed amount (IDR)"), null=True, blank=True, **MONEY
    )
    signed_on = models.DateField(
        verbose_name=_("Minutes signed on"), null=True, blank=True
    )
    note = models.TextField(verbose_name=_("Note"), blank=True, default="")

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Deliberation result")
        verbose_name_plural = pgettext_lazy("Model name", "Deliberation results")
        ordering = ["deliberation", "parcel"]

    @property
    def objection_deadline(self) -> datetime.date | None:
        if self.outcome != enums.DeliberationOutcome.REJECTED:
            return None
        return apply_rule(
            "compensation_objection", self.signed_on or self.deliberation.held_on
        )


class Objection(TimeStampedModel):
    """Keberatan, gugatan dan perkara terkait pengadaan."""

    project = models.ForeignKey(
        AcquisitionProject,
        verbose_name=_("Project"),
        related_name="objections",
        on_delete=models.CASCADE,
    )
    parcel = models.ForeignKey(
        AcquisitionParcel,
        verbose_name=_("Parcel"),
        related_name="objections",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    party = models.ForeignKey(
        EntitledParty,
        verbose_name=_("Entitled party"),
        related_name="objections",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    parent = models.ForeignKey(
        "self",
        verbose_name=_("Previous instance"),
        related_name="appeals",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    objection_type = models.CharField(
        verbose_name=_("Type"), max_length=32, choices=enums.ObjectionType.choices
    )
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=16,
        choices=enums.ObjectionStatus.choices,
        default=enums.ObjectionStatus.FILED,
    )
    filed_by_name = models.CharField(
        verbose_name=_("Filed by"), max_length=255, blank=True, default=""
    )
    court_name = models.CharField(
        verbose_name=_("Court / handling body"), max_length=255, blank=True, default=""
    )
    case_number = models.CharField(
        verbose_name=_("Case number"), max_length=128, blank=True, default=""
    )
    filed_on = models.DateField(verbose_name=_("Filed on"), null=True, blank=True)
    received_on = models.DateField(
        verbose_name=_("Received by court on"), null=True, blank=True
    )
    decided_on = models.DateField(verbose_name=_("Decided on"), null=True, blank=True)
    decision_summary = models.TextField(
        verbose_name=_("Decision summary"), blank=True, default=""
    )
    decided_amount = models.DecimalField(
        verbose_name=_("Compensation amount decided (IDR)"),
        null=True,
        blank=True,
        **MONEY,
    )
    note = models.TextField(verbose_name=_("Note"), blank=True, default="")

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Objection / case")
        verbose_name_plural = pgettext_lazy("Model name", "Objections / cases")
        ordering = ["project", "-filed_on", "-id"]

    DECISION_RULES = {
        enums.ObjectionType.LOCATION: "location_objection_handling",
        enums.ObjectionType.PTUN: "ptun_decision",
        enums.ObjectionType.COMPENSATION: "district_court_decision",
        enums.ObjectionType.CASSATION: "supreme_court_decision",
    }

    @property
    def decision_deadline(self) -> datetime.date | None:
        code = self.DECISION_RULES.get(self.objection_type)
        if not code:
            return None
        return apply_rule(code, self.received_on or self.filed_on)

    @property
    def appeal_deadline(self) -> datetime.date | None:
        """Batas pengajuan kasasi atas putusan PN/PTUN."""
        if self.objection_type in (
            enums.ObjectionType.COMPENSATION,
            enums.ObjectionType.PTUN,
        ):
            return apply_rule("cassation_filing", self.decided_on)
        return None

    @property
    def is_open(self) -> bool:
        return self.status in (
            enums.ObjectionStatus.FILED,
            enums.ObjectionStatus.IN_PROCESS,
        )


class Consignment(TimeStampedModel):
    """Penitipan ganti kerugian di Pengadilan Negeri (konsinyasi)."""

    parcel = models.ForeignKey(
        AcquisitionParcel,
        verbose_name=_("Parcel"),
        related_name="consignments",
        on_delete=models.CASCADE,
    )
    party = models.ForeignKey(
        EntitledParty,
        verbose_name=_("Entitled party"),
        related_name="consignments",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    reason = models.CharField(
        verbose_name=_("Reason"), max_length=32, choices=enums.ConsignmentReason.choices
    )
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=16,
        choices=enums.ConsignmentStatus.choices,
        default=enums.ConsignmentStatus.REQUESTED,
    )
    court_name = models.CharField(
        verbose_name=_("District court"), max_length=255, blank=True, default=""
    )
    application_date = models.DateField(
        verbose_name=_("Application date"), null=True, blank=True
    )
    decree_number = models.CharField(
        verbose_name=_("Court decree number"), max_length=128, blank=True, default=""
    )
    decree_date = models.DateField(verbose_name=_("Decree date"), null=True, blank=True)
    deposited_on = models.DateField(
        verbose_name=_("Deposited on"), null=True, blank=True
    )
    amount = models.DecimalField(
        verbose_name=_("Amount (IDR)"), default=Decimal("0"), **MONEY
    )
    collected_on = models.DateField(
        verbose_name=_("Collected by entitled party on"), null=True, blank=True
    )
    note = models.TextField(verbose_name=_("Note"), blank=True, default="")

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Consignment")
        verbose_name_plural = pgettext_lazy("Model name", "Consignments")
        ordering = ["parcel", "-application_date", "-id"]

    @property
    def acceptance_deadline(self) -> datetime.date | None:
        return apply_rule("consignment_acceptance", self.application_date)


class Compensation(TimeStampedModel):
    """Ganti kerugian yang ditetapkan untuk pihak yang berhak."""

    parcel = models.ForeignKey(
        AcquisitionParcel,
        verbose_name=_("Parcel"),
        related_name="compensations",
        on_delete=models.CASCADE,
    )
    party = models.ForeignKey(
        EntitledParty,
        verbose_name=_("Entitled party"),
        related_name="compensations",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    form = models.CharField(
        verbose_name=_("Form of compensation"),
        max_length=32,
        choices=enums.CompensationForm.choices,
        default=enums.CompensationForm.MONEY,
    )
    amount = models.DecimalField(
        verbose_name=_("Amount (IDR)"), default=Decimal("0"), **MONEY
    )
    description = models.TextField(
        verbose_name=_("Description of non-monetary compensation"),
        blank=True,
        default="",
    )
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=16,
        choices=enums.CompensationStatus.choices,
        default=enums.CompensationStatus.DETERMINED,
    )
    valuation = models.ForeignKey(
        Valuation,
        verbose_name=_("Valuation"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    deliberation_result = models.ForeignKey(
        DeliberationResult,
        verbose_name=_("Deliberation result"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    court_decision = models.ForeignKey(
        Objection,
        verbose_name=_("Court decision"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    validated_on = models.DateField(
        verbose_name=_("Validated on"), null=True, blank=True
    )
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Validated by"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    note = models.TextField(verbose_name=_("Note"), blank=True, default="")

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Compensation")
        verbose_name_plural = pgettext_lazy("Model name", "Compensations")
        ordering = ["parcel", "id"]
        permissions = [
            (
                "validate_compensation",
                _("Can validate compensation (Chair of the Implementing Team)"),
            )
        ]

    @property
    def paid_amount(self) -> Decimal:
        return sum((p.amount for p in self.payments.all()), Decimal("0"))

    @property
    def outstanding_amount(self) -> Decimal:
        return max((self.amount or Decimal("0")) - self.paid_amount, Decimal("0"))


class CompensationPayment(TimeStampedModel):
    compensation = models.ForeignKey(
        Compensation,
        verbose_name=_("Compensation"),
        related_name="payments",
        on_delete=models.CASCADE,
    )
    paid_on = models.DateField(verbose_name=_("Paid on"))
    amount = models.DecimalField(verbose_name=_("Amount (IDR)"), **MONEY)
    method = models.CharField(
        verbose_name=_("Payment method"),
        max_length=16,
        choices=enums.PaymentMethod.choices,
        default=enums.PaymentMethod.TRANSFER,
    )
    bank_reference = models.CharField(
        verbose_name=_("Bank reference"), max_length=128, blank=True, default=""
    )
    recipient_name = models.CharField(
        verbose_name=_("Recipient"), max_length=255, blank=True, default=""
    )
    note = models.TextField(verbose_name=_("Note"), blank=True, default="")

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Compensation payment")
        verbose_name_plural = pgettext_lazy("Model name", "Compensation payments")
        ordering = ["compensation", "paid_on", "id"]


class RightsRelease(TimeStampedModel):
    """Pelepasan hak objek pengadaan tanah."""

    parcel = models.ForeignKey(
        AcquisitionParcel,
        verbose_name=_("Parcel"),
        related_name="rights_releases",
        on_delete=models.CASCADE,
    )
    party = models.ForeignKey(
        EntitledParty,
        verbose_name=_("Entitled party"),
        related_name="rights_releases",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    minutes_number = models.CharField(
        verbose_name=_("Minutes number"), max_length=128, blank=True, default=""
    )
    released_on = models.DateField(verbose_name=_("Released on"))
    certificate_surrendered = models.BooleanField(
        verbose_name=_("Original certificate/evidence surrendered"), default=False
    )
    note = models.TextField(verbose_name=_("Note"), blank=True, default="")

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Rights release")
        verbose_name_plural = pgettext_lazy("Model name", "Rights releases")
        ordering = ["parcel", "-released_on"]

    @property
    def handover_deadline(self) -> datetime.date | None:
        return apply_rule("handover", self.released_on)


class Handover(TimeStampedModel):
    """Penyerahan hasil pengadaan tanah kepada instansi yang memerlukan tanah."""

    project = models.ForeignKey(
        AcquisitionProject,
        verbose_name=_("Project"),
        related_name="handovers",
        on_delete=models.CASCADE,
    )
    minutes_number = models.CharField(
        verbose_name=_("Handover minutes (BAST) number"),
        max_length=128,
        blank=True,
        default="",
    )
    handed_over_on = models.DateField(verbose_name=_("Handed over on"))
    recipient = models.CharField(verbose_name=_("Recipient"), max_length=255)
    parcels = models.ManyToManyField(
        AcquisitionParcel,
        verbose_name=_("Parcels"),
        related_name="handovers",
        blank=True,
    )
    registration_applied_on = models.DateField(
        verbose_name=_("Land registration applied on"), null=True, blank=True
    )
    registration_number = models.CharField(
        verbose_name=_("Registration / certificate number"),
        max_length=128,
        blank=True,
        default="",
    )
    note = models.TextField(verbose_name=_("Note"), blank=True, default="")

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Handover")
        verbose_name_plural = pgettext_lazy("Model name", "Handovers")
        ordering = ["project", "-handed_over_on"]

    @property
    def registration_deadline(self) -> datetime.date | None:
        return apply_rule("registration", self.handed_over_on)


class AffectedHousehold(TimeStampedModel):
    """Rumah tangga terdampak / permukiman kembali."""

    project = models.ForeignKey(
        AcquisitionProject,
        verbose_name=_("Project"),
        related_name="households",
        on_delete=models.CASCADE,
    )
    parcel = models.ForeignKey(
        AcquisitionParcel,
        verbose_name=_("Parcel"),
        related_name="households",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    head_name = models.CharField(verbose_name=_("Head of household"), max_length=255)
    nik = EncryptedCharField(
        verbose_name=_("National identification number (NIK)"), blank=True, default=""
    )
    nik_fingerprint = models.CharField(
        max_length=64, blank=True, default="", editable=False, db_index=True
    )
    family_card_number = EncryptedCharField(
        verbose_name=_("Family card number (KK)"), blank=True, default=""
    )
    member_count = models.PositiveIntegerField(
        verbose_name=_("Number of members"), null=True, blank=True
    )
    displacement = models.CharField(
        verbose_name=_("Displacement"),
        max_length=16,
        choices=enums.DisplacementStatus.choices,
        default=enums.DisplacementStatus.NONE,
    )
    stage = models.CharField(
        verbose_name=_("Stage"),
        max_length=32,
        choices=enums.ResettlementStage.choices,
        default=enums.ResettlementStage.IDENTIFICATION,
    )
    assistance_description = models.TextField(
        verbose_name=_("Assistance provided"), blank=True, default=""
    )
    monetary_assistance_amount = models.DecimalField(
        verbose_name=_("Monetary assistance (IDR)"), null=True, blank=True, **MONEY
    )
    progress_percentage = models.PositiveIntegerField(
        verbose_name=_("Progress (%)"),
        default=0,
        validators=[MaxValueValidator(100)],
    )
    note = models.TextField(verbose_name=_("Note"), blank=True, default="")

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Affected household")
        verbose_name_plural = pgettext_lazy("Model name", "Affected households")
        ordering = ["project", "head_name"]

    def save(self, *args, **kwargs):
        self.nik_fingerprint = fingerprint(self.nik) or ""
        super().save(*args, **kwargs)


def get_document_upload_to(instance, filename):
    project_id = instance.project_id or "umum"
    return f"pengadaan/{project_id}/{timezone.localdate():%Y-%m-%d}/{filename}"


class AcquisitionDocument(FileScanMixin, TimeStampedModel):
    project = models.ForeignKey(
        AcquisitionProject,
        verbose_name=_("Project"),
        related_name="documents",
        on_delete=models.CASCADE,
    )
    parcel = models.ForeignKey(
        AcquisitionParcel,
        verbose_name=_("Parcel"),
        related_name="documents",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    party = models.ForeignKey(
        EntitledParty,
        verbose_name=_("Entitled party"),
        related_name="documents",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    document_type = models.CharField(
        verbose_name=_("Document type"),
        max_length=32,
        choices=enums.DocumentType.choices,
        default=enums.DocumentType.OTHER,
    )
    title = models.CharField(verbose_name=_("Title"), max_length=255)
    number = models.CharField(
        verbose_name=_("Document number"), max_length=128, blank=True, default=""
    )
    document_date = models.DateField(
        verbose_name=_("Document date"), null=True, blank=True
    )
    file = PrivateFileField(verbose_name=_("File"), upload_to=get_document_upload_to)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Uploaded by"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    note = models.TextField(verbose_name=_("Note"), blank=True, default="")

    class Meta:
        verbose_name = pgettext_lazy("Model name", "Acquisition document")
        verbose_name_plural = pgettext_lazy("Model name", "Acquisition documents")
        ordering = ["project", "-created_at"]

    def __str__(self):
        return self.title


for _model in (
    Holiday,
    DeadlineRule,
    AcquisitionProject,
    AcquisitionMilestone,
    AcquisitionParcel,
    ParcelSurvey,
    Announcement,
    Valuation,
    Deliberation,
    DeliberationResult,
    Objection,
    Consignment,
    Compensation,
    CompensationPayment,
    RightsRelease,
    Handover,
    AcquisitionDocument,
):
    auditlog.register(_model)

# Data pribadi tidak boleh tersimpan apa adanya di log audit.
auditlog.register(
    EntitledParty,
    exclude_fields=["nik_fingerprint"],
    mask_fields=["nik", "bank_account_number"],
)
auditlog.register(
    AffectedHousehold,
    exclude_fields=["nik_fingerprint"],
    mask_fields=["nik", "family_card_number"],
)
