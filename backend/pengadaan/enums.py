"""Pilihan (choices) modul pengadaan tanah.

Rujukan utama:
- UU No. 2 Tahun 2012 tentang Pengadaan Tanah bagi Pembangunan untuk Kepentingan
  Umum, sebagaimana diubah UU No. 6 Tahun 2023 (Penetapan Perppu Cipta Kerja).
- PP No. 19 Tahun 2021 tentang Penyelenggaraan Pengadaan Tanah bagi Pembangunan
  untuk Kepentingan Umum, sebagaimana diubah PP No. 39 Tahun 2023.
- Permen ATR/Kepala BPN No. 19 Tahun 2021 (ketentuan pelaksanaan).
- Perma No. 3 Tahun 2016 jo. Perma No. 2 Tahun 2021 (keberatan & penitipan).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class AcquisitionType(models.TextChoices):
    PUBLIC_INTEREST = "public_interest", _("Public interest (Law 2/2012)")
    SMALL_SCALE = "small_scale", _("Small scale public interest (max. 5 ha)")
    PRIVATE = "private", _("Private / business-to-business acquisition")


class PublicInterestCategory(models.TextChoices):
    """Jenis pembangunan untuk kepentingan umum (Pasal 10 UU 2/2012 jo. UU 6/2023)."""

    DEFENSE = "defense", _("National defense and security")
    ROADS = "roads", _("Public roads, toll roads, tunnels, railways, stations")
    WATER = "water", _("Dams, irrigation, drinking water, drainage, sanitation")
    PORTS = "ports", _("Ports, airports and terminals")
    OIL_GAS = "oil_gas", _("Oil, gas and geothermal infrastructure")
    ELECTRICITY = "electricity", _("Power generation, transmission and distribution")
    TELECOM = "telecom", _("Government telecommunications and informatics")
    WASTE = "waste", _("Waste disposal and processing sites")
    HOSPITAL = "hospital", _("Government hospitals and public health centers")
    PUBLIC_SAFETY = "public_safety", _("Public safety facilities")
    CEMETERY = "cemetery", _("Public cemeteries")
    SOCIAL = "social", _("Social facilities, public facilities and green open space")
    NATURE = "nature", _("Nature reserves and cultural heritage")
    GOVERNMENT_OFFICE = "government_office", _("Government offices")
    HOUSING = "housing", _("Slum rearrangement, land consolidation, public housing")
    EDUCATION = "education", _("Government education and school infrastructure")
    SPORTS = "sports", _("Government sports infrastructure")
    MARKET = "market", _("Public markets and public parking")
    INDUSTRIAL = "industrial", _("Upstream/downstream oil & gas industrial estates")
    SEZ = "sez", _("Special economic zones")
    INDUSTRIAL_ESTATE = "industrial_estate", _("Industrial estates")
    TOURISM = "tourism", _("Tourism areas")
    FOOD_SECURITY = "food_security", _("Food security areas")
    TECHNOLOGY = "technology", _("Technology development areas")
    OTHER = "other", _("Other")


class FundingSource(models.TextChoices):
    APBN = "apbn", _("State budget (APBN)")
    APBD = "apbd", _("Regional budget (APBD)")
    LMAN = "lman", _("State Asset Management Agency (LMAN)")
    SOE = "soe", _("State-owned enterprise")
    PRIVATE = "private", _("Private / business entity")
    OTHER = "other", _("Other")


class ProjectStage(models.TextChoices):
    PLANNING = "planning", _("Planning")
    PREPARATION = "preparation", _("Preparation")
    IMPLEMENTATION = "implementation", _("Implementation")
    HANDOVER = "handover", _("Handover of results")
    COMPLETED = "completed", _("Completed")


STAGE_ORDER = [
    ProjectStage.PLANNING,
    ProjectStage.PREPARATION,
    ProjectStage.IMPLEMENTATION,
    ProjectStage.HANDOVER,
    ProjectStage.COMPLETED,
]


class ProjectStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    ACTIVE = "active", _("Active")
    ON_HOLD = "on_hold", _("On hold")
    COMPLETED = "completed", _("Completed")
    CANCELLED = "cancelled", _("Cancelled")


class Priority(models.TextChoices):
    LOW = "low", _("Low")
    MEDIUM = "medium", _("Medium")
    HIGH = "high", _("High")
    NATIONAL_STRATEGIC = "national_strategic", _("National strategic project (PSN)")


class MilestoneStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    IN_PROGRESS = "in_progress", _("In progress")
    DONE = "done", _("Done")
    SKIPPED = "skipped", _("Not applicable")


class LandRightType(models.TextChoices):
    """Jenis hak/alas hak atas tanah."""

    SHM = "shm", _("Freehold title (SHM)")
    HGB = "hgb", _("Right to build (HGB)")
    HGU = "hgu", _("Right to cultivate (HGU)")
    HP = "hp", _("Right of use (Hak Pakai)")
    HPL = "hpl", _("Right of management (HPL)")
    SRS = "srs", _("Strata title (SHMSRS)")
    WAQF = "waqf", _("Waqf land")
    CUSTOMARY = "customary", _("Customary (ulayat) land")
    UNREGISTERED = "unregistered", _("Unregistered evidence (girik, letter C, petok D)")
    STATE_LAND = "state_land", _("State land controlled by a party")
    STATE_ASSET = "state_asset", _("State/regional asset (BMN/BMD)")
    OTHER = "other", _("Other")


class LandUse(models.TextChoices):
    RICE_FIELD = "rice_field", _("Rice field")
    DRY_FIELD = "dry_field", _("Dry field / garden")
    PLANTATION = "plantation", _("Plantation")
    RESIDENTIAL = "residential", _("Residential yard")
    COMMERCIAL = "commercial", _("Commercial")
    INDUSTRIAL = "industrial", _("Industrial")
    FOREST = "forest", _("Forest")
    FISHPOND = "fishpond", _("Fishpond")
    PUBLIC_FACILITY = "public_facility", _("Public facility")
    VACANT = "vacant", _("Vacant land")
    OTHER = "other", _("Other")


class ParcelStatus(models.TextChoices):
    """Status bidang tanah sepanjang tahapan pelaksanaan."""

    IDENTIFIED = "identified", _("Identified")
    INVENTORIED = "inventoried", _("Inventoried")
    ANNOUNCED = "announced", _("Inventory results announced")
    VALUED = "valued", _("Valued")
    DELIBERATION = "deliberation", _("In deliberation")
    AGREED = "agreed", _("Agreed")
    OBJECTION = "objection", _("Objection in court")
    CONSIGNED = "consigned", _("Compensation consigned to court")
    PAID = "paid", _("Compensation paid")
    RELEASED = "released", _("Rights released")
    HANDED_OVER = "handed_over", _("Handed over")
    EXCLUDED = "excluded", _("Excluded from acquisition")


PARCEL_STATUS_ORDER = [s.value for s in ParcelStatus if s != ParcelStatus.EXCLUDED]


class PartyType(models.TextChoices):
    INDIVIDUAL = "individual", _("Individual")
    LEGAL_ENTITY = "legal_entity", _("Legal entity")
    GOVERNMENT = "government", _("Government agency")
    CUSTOMARY_COMMUNITY = "customary_community", _("Customary law community")
    WAQF_MANAGER = "waqf_manager", _("Waqf manager (nazhir)")


class PartyRole(models.TextChoices):
    OWNER = "owner", _("Right holder / owner")
    HEIR = "heir", _("Heir")
    MANAGER = "manager", _("Holder of management right")
    OCCUPANT = "occupant", _("Party controlling state land in good faith")
    TENANT = "tenant", _("Tenant / user")
    PROXY = "proxy", _("Proxy / attorney")


class InventoryItemType(models.TextChoices):
    BUILDING = "building", _("Building / house")
    PLANT = "plant", _("Plants / trees")
    POND = "pond", _("Pond / fishpond")
    WELL = "well", _("Well")
    FENCE = "fence", _("Fence / wall")
    ACCESS_ROAD = "access_road", _("Access road / easement")
    UTILITY = "utility", _("Utility (electricity, water, telecom)")
    GRAVE = "grave", _("Grave")
    PUBLIC_FACILITY = "public_facility", _("Public / social facility")
    WATER_BODY = "water_body", _("Water body / river")
    FOREST = "forest", _("Forest / natural vegetation")
    OTHER = "other", _("Other object")


class SurveyType(models.TextChoices):
    PHYSICAL = "physical", _("Physical inventory (task force A)")
    JURIDICAL = "juridical", _("Juridical identification (task force B)")


class SurveyStatus(models.TextChoices):
    SCHEDULED = "scheduled", _("Scheduled")
    DONE = "done", _("Done")
    NEEDS_VERIFICATION = "needs_verification", _("Needs verification")


class AnnouncementType(models.TextChoices):
    LOCATION_PLAN = "location_plan", _("Notification of development plan")
    LOCATION_DETERMINATION = "location_determination", _(
        "Location determination (Penlok) announcement"
    )
    INVENTORY = "inventory", _("Inventory results (parcel map and nominative list)")
    VALUATION = "valuation", _("Valuation results")
    OTHER = "other", _("Other")


class ValuationStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    FINAL = "final", _("Final")
    REVISED = "revised", _("Revised")


class DeliberationOutcome(models.TextChoices):
    AGREED = "agreed", _("Agreed")
    REJECTED = "rejected", _("Rejected")
    ABSENT = "absent", _("Absent")
    POSTPONED = "postponed", _("Postponed")


class CompensationForm(models.TextChoices):
    """Bentuk ganti kerugian (Pasal 36 UU 2/2012)."""

    MONEY = "money", _("Money")
    REPLACEMENT_LAND = "replacement_land", _("Replacement land")
    RESETTLEMENT = "resettlement", _("Resettlement")
    SHARES = "shares", _("Share ownership")
    OTHER = "other", _("Other agreed form")


class ObjectionType(models.TextChoices):
    LOCATION = "location", _("Objection to development location plan")
    PTUN = "ptun", _(
        "Lawsuit against location determination (State Administrative Court)"
    )
    INVENTORY = "inventory", _("Objection to inventory results")
    COMPENSATION = "compensation", _("Objection to compensation (District Court)")
    CASSATION = "cassation", _("Cassation to the Supreme Court")
    OWNERSHIP_DISPUTE = "ownership_dispute", _("Ownership dispute")
    OTHER_LITIGATION = "other_litigation", _("Other litigation")


class ObjectionStatus(models.TextChoices):
    FILED = "filed", _("Filed")
    IN_PROCESS = "in_process", _("In process")
    GRANTED = "granted", _("Granted")
    REJECTED = "rejected", _("Rejected")
    FINAL = "final", _("Final and binding")
    WITHDRAWN = "withdrawn", _("Withdrawn")


class ConsignmentReason(models.TextChoices):
    """Alasan penitipan ganti kerugian (Pasal 42 UU 2/2012)."""

    REFUSED = "refused", _("Entitled party refuses the agreed/decided compensation")
    UNKNOWN_WHEREABOUTS = "unknown_whereabouts", _(
        "Whereabouts of the entitled party unknown"
    )
    DISPUTED = "disputed", _("Object is in an ownership dispute")
    COURT_CASE = "court_case", _("Object is in a court case")
    SEIZED = "seized", _("Object is seized by an authorized official")
    COLLATERAL = "collateral", _("Object is used as collateral at a bank")


class ConsignmentStatus(models.TextChoices):
    REQUESTED = "requested", _("Requested to court")
    DEPOSITED = "deposited", _("Deposited")
    COLLECTED = "collected", _("Collected by entitled party")


class CompensationStatus(models.TextChoices):
    DETERMINED = "determined", _("Determined")
    VALIDATED = "validated", _("Validated by executing chair")
    PAID = "paid", _("Paid")
    CONSIGNED = "consigned", _("Consigned")
    CANCELLED = "cancelled", _("Cancelled")


class PaymentMethod(models.TextChoices):
    TRANSFER = "transfer", _("Bank transfer")
    CHEQUE = "cheque", _("Cheque / giro")
    IN_KIND = "in_kind", _("In kind (land, housing, shares)")
    OTHER = "other", _("Other")


class DisplacementStatus(models.TextChoices):
    NONE = "none", _("Not displaced")
    PARTIAL = "partial", _("Partially displaced")
    FULL = "full", _("Fully displaced")


class ResettlementStage(models.TextChoices):
    IDENTIFICATION = "identification", _("Identification")
    VERIFICATION = "verification", _("Verification")
    ASSISTANCE = "assistance", _("Assistance being provided")
    RESETTLED = "resettled", _("Resettled")


class DocumentType(models.TextChoices):
    DPPT = "dppt", _("Land acquisition planning document (DPPT)")
    FEASIBILITY = "feasibility", _("Feasibility study / environmental document")
    NOTIFICATION = "notification", _("Notification of development plan")
    PUBLIC_CONSULTATION = "public_consultation", _("Public consultation minutes")
    LOCATION_DECREE = "location_decree", _("Location determination decree (Penlok)")
    PARCEL_MAP = "parcel_map", _("Parcel map")
    NOMINATIVE_LIST = "nominative_list", _("Nominative list")
    ANNOUNCEMENT = "announcement", _("Announcement")
    VALUATION_REPORT = "valuation_report", _("Valuation report")
    DELIBERATION_MINUTES = "deliberation_minutes", _("Deliberation minutes")
    COURT_DECISION = "court_decision", _("Court decision")
    CONSIGNMENT_DECREE = "consignment_decree", _("Consignment decree")
    PAYMENT_PROOF = "payment_proof", _("Proof of payment / receipt")
    RELEASE_MINUTES = "release_minutes", _("Minutes of rights release")
    CERTIFICATE = "certificate", _("Land certificate / evidence of rights")
    ID_CARD = "id_card", _("Identity document")
    HANDOVER_MINUTES = "handover_minutes", _("Handover minutes (BAST)")
    PHOTO = "photo", _("Photo")
    OTHER = "other", _("Other")
