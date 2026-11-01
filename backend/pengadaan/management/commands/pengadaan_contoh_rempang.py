"""Buat (atau hapus) DATA CONTOH proyek pengadaan tanah Pulau Rempang.

Data ini fiktif dan hanya untuk uji coba/peragaan: nama pihak, nomor bidang,
luas, dan batas bidang bukan hasil pengukuran. Geometri hanya ilustrasi kasar
di bagian tengah Pulau Rempang (Kec. Galang, Kota Batam).

    python manage.py pengadaan_contoh_rempang          # buat (idempoten)
    python manage.py pengadaan_contoh_rempang --hapus  # hapus permanen

Proyek contoh berisi seluruh tahapan UU 2/2012 agar setiap menu terisi:
pengumuman, inventarisasi & identifikasi, penilaian, musyawarah, ganti kerugian
& pembayaran, keberatan, konsinyasi, pelepasan hak, penyerahan hasil, warga
terdampak, dan dokumen. Status keenam bidang berbeda-beda (diserahkan, dibayar,
sepakat, keberatan, dikonsinyasi, musyawarah).

Proyek contoh dikenali dari namanya (SAMPLE_PROJECT_NAME). `--hapus` menghapus
proyek itu beserta SELURUH data di bawahnya, termasuk yang ditambahkan manual.
Bila proyek contoh sudah ada tanpa tahapan (versi lama), tahapannya dilengkapi.
"""

import datetime
from decimal import Decimal
from typing import Any

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.utils import timezone
from safedelete.config import HARD_DELETE

from leasing.models import District, Municipality
from pengadaan import enums
from pengadaan.models import (
    AcquisitionDocument,
    AcquisitionParcel,
    AcquisitionProject,
    AffectedHousehold,
    Announcement,
    Compensation,
    CompensationPayment,
    Consignment,
    Deliberation,
    DeliberationResult,
    EntitledParty,
    Handover,
    InventoryItem,
    Objection,
    ParcelSurvey,
    RightsRelease,
    Valuation,
)
from utils.sample_files import delete_files, pdf_upload

SAMPLE_PROJECT_NAME = "[CONTOH] Pengadaan Tanah Pulau Rempang"
SAMPLE_NOTE = (
    "DATA CONTOH – fiktif, bukan data resmi. "
    "Hapus dengan `manage.py pengadaan_contoh_rempang --hapus`."
)
BATAM_IDENTIFIER = "2171"

# Titik acuan bidang contoh (WGS84), bagian tengah Pulau Rempang.
ORIGIN_LNG = 104.1500
ORIGIN_LAT = 0.8700
SIDE = 0.000285  # ≈ 31,7 m di khatulistiwa → bidang ≈ 1.000 m²
GAP = 0.0001  # jarak antarbidang ≈ 11 m

E = enums
PARCELS = [
    # nomor, kelurahan, hak, penggunaan, luas terkena, (pihak, jenis pihak), kolom, baris
    ("RMP-001", "Rempang Cate", E.LandRightType.SHM, E.LandUse.RESIDENTIAL, "1000",
     ("Pemilik Contoh 1", E.PartyType.INDIVIDUAL), 0, 0),
    ("RMP-002", "Rempang Cate", E.LandRightType.SHM, E.LandUse.DRY_FIELD, "600",
     ("Pemilik Contoh 2", E.PartyType.INDIVIDUAL), 1, 0),
    ("RMP-003", "Rempang Cate", E.LandRightType.UNREGISTERED, E.LandUse.PLANTATION, "1000",
     ("Pemilik Contoh 3", E.PartyType.INDIVIDUAL), 2, 0),
    ("RMP-004", "Sembulang", E.LandRightType.CUSTOMARY, E.LandUse.RESIDENTIAL, "1000",
     ("Masyarakat Adat Contoh", E.PartyType.CUSTOMARY_COMMUNITY), 0, 1),
    ("RMP-005", "Sembulang", E.LandRightType.STATE_LAND, E.LandUse.VACANT, "1000",
     None, 1, 1),
    ("RMP-006", "Sembulang", E.LandRightType.HGB, E.LandUse.COMMERCIAL, "400",
     ("PT Contoh Rempang", E.PartyType.LEGAL_ENTITY), 2, 1),
]  # fmt: skip
MEASURED_AREA = Decimal("1000")


def _square(col: int, row: int) -> Polygon:
    west = ORIGIN_LNG + col * (SIDE + GAP)
    north = ORIGIN_LAT - row * (SIDE + GAP)
    east, south = west + SIDE, north - SIDE
    ring = ((west, south), (east, south), (east, north), (west, north), (west, south))
    return Polygon(ring, srid=4326)


class Command(BaseCommand):
    help = "Buat atau hapus data contoh proyek pengadaan tanah Pulau Rempang"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--hapus",
            action="store_true",
            help="Hapus permanen proyek contoh Rempang beserta seluruh datanya",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["hapus"]:
            self._delete()
        else:
            self._create()

    @transaction.atomic
    def _delete(self) -> None:
        projects = list(AcquisitionProject.all_objects.filter(name=SAMPLE_PROJECT_NAME))
        if not projects:
            self.stdout.write("Proyek contoh Rempang tidak ditemukan.")
            return
        for project in projects:
            delete_files(*(d.file for d in project.documents.all()))
            # Bidang memakai PROTECT terhadap proyek, jadi dihapus lebih dulu;
            # data di bawah bidang (pihak, survei, penilaian, …) ikut CASCADE.
            for parcel in AcquisitionParcel.all_objects.filter(project=project):
                parcel.delete(force_policy=HARD_DELETE)
            project.delete(force_policy=HARD_DELETE)
        self.stdout.write(self.style.SUCCESS("Proyek contoh Rempang dihapus."))

    @transaction.atomic
    def _create(self) -> None:
        existing = AcquisitionProject.all_objects.filter(
            name=SAMPLE_PROJECT_NAME
        ).first()
        if existing:
            if existing.deleted is None and not existing.announcements.exists():
                _lifecycle(existing)
                self.stdout.write(
                    f"Tahapan proyek contoh {existing.identifier} dilengkapi."
                )
            else:
                self.stdout.write(
                    f"Proyek contoh Rempang sudah ada ({existing.identifier}), dilewati."
                )
            return

        municipality = Municipality.objects.filter(identifier=BATAM_IDENTIFIER).first()
        district = District.objects.filter(
            municipality=municipality, name="Galang"
        ).first()

        polygons = {number: _square(col, row) for number, *_, col, row in PARCELS}
        project = AcquisitionProject.objects.create(
            name=SAMPLE_PROJECT_NAME,
            description=SAMPLE_NOTE,
            acquisition_type=enums.AcquisitionType.PUBLIC_INTEREST,
            purpose_category=enums.PublicInterestCategory.OTHER,
            priority=enums.Priority.NATIONAL_STRATEGIC,
            funding_source=enums.FundingSource.OTHER,
            requiring_agency="Instansi Contoh",
            municipality=municipality,
            location_description="Pulau Rempang, Kecamatan Galang, Kota Batam (contoh)",
            estimated_area_m2=MEASURED_AREA * len(PARCELS),
            geometry=MultiPolygon(list(polygons.values()), srid=4326),
        )

        for number, village, right, use, affected, party, *_ in PARCELS:
            parcel = AcquisitionParcel.objects.create(
                project=project,
                parcel_number=number,
                district=district,
                village=village,
                right_type=right,
                land_use=use,
                measured_area_m2=MEASURED_AREA,
                affected_area_m2=Decimal(affected),
                geometry=MultiPolygon(polygons[number], srid=4326),
                note=SAMPLE_NOTE,
            )
            if party:
                name, party_type = party
                EntitledParty.objects.create(
                    parcel=parcel,
                    name=name,
                    party_type=party_type,
                    share_percentage=Decimal("100"),
                    note=SAMPLE_NOTE,
                )

        _lifecycle(project)
        self.stdout.write(
            self.style.SUCCESS(
                f"Proyek contoh Rempang dibuat: {project.identifier} "
                f"dengan {len(PARCELS)} bidang."
            )
        )


# ----------------------------------------------------------------------
# Tahapan pengadaan contoh (semua nomor, nama, dan nilai fiktif)
# ----------------------------------------------------------------------

D = datetime.timedelta
# nomor bidang → (nilai tanah/m², bangunan, tanaman, nonfisik, hasil musyawarah)
VALUATIONS = {
    "RMP-001": (350000, 85000000, 12000000, 15000000, E.DeliberationOutcome.AGREED),
    "RMP-002": (300000, 0, 18000000, 6000000, E.DeliberationOutcome.AGREED),
    "RMP-003": (250000, 0, 40000000, 5000000, E.DeliberationOutcome.AGREED),
    "RMP-004": (320000, 60000000, 8000000, 20000000, E.DeliberationOutcome.REJECTED),
    "RMP-005": (200000, 0, 0, 0, E.DeliberationOutcome.ABSENT),
    "RMP-006": (450000, 150000000, 0, 30000000, E.DeliberationOutcome.POSTPONED),
}
# nomor bidang → [(jenis, uraian, jumlah, satuan, nilai satuan)]
INVENTORY = {
    "RMP-001": [
        (E.InventoryItemType.BUILDING, "Rumah semi permanen", 1, "unit", 85000000),
        (E.InventoryItemType.PLANT, "Pohon kelapa produktif", 24, "batang", 500000),
        (E.InventoryItemType.WELL, "Sumur gali", 1, "unit", 3500000),
    ],
    "RMP-002": [(E.InventoryItemType.PLANT, "Pohon mangga", 30, "batang", 600000)],
    "RMP-003": [
        (E.InventoryItemType.PLANT, "Kebun karet", 80, "batang", 500000),
        (E.InventoryItemType.FENCE, "Pagar kawat berduri", 120, "m", 25000),
    ],
    "RMP-004": [
        (E.InventoryItemType.BUILDING, "Rumah panggung kayu", 1, "unit", 60000000),
        (E.InventoryItemType.GRAVE, "Makam keluarga", 2, "titik", None),
    ],
    "RMP-006": [
        (E.InventoryItemType.BUILDING, "Ruko 2 lantai", 1, "unit", 150000000),
        (E.InventoryItemType.UTILITY, "Sambungan listrik 2.200 VA", 1, "unit", None),
    ],
}


def _lifecycle(project: AcquisitionProject) -> None:  # noqa: C901
    today = timezone.localdate()
    project.status = enums.ProjectStatus.ACTIVE
    project.stage = enums.ProjectStage.IMPLEMENTATION
    project.requiring_agency_contact = "Contoh Penanggung Jawab, 0778-000000"
    project.executing_office = "Kantor Pertanahan Contoh"
    project.estimated_budget = Decimal("12500000000")
    project.planning_document_number = "DPPT/CONTOH/001"
    project.planning_document_date = today - D(days=300)
    project.notification_date = today - D(days=270)
    project.public_consultation_date = today - D(days=240)
    project.location_decree_number = "PENLOK/CONTOH/001"
    project.location_decree_date = today - D(days=200)
    project.location_announcement_date = today - D(days=195)
    project.start_date = today - D(days=300)
    project.target_completion_date = today + D(days=180)
    project.save()

    for milestone in project.milestones.order_by("sequence"):
        if milestone.stage in (
            enums.ProjectStage.PLANNING,
            enums.ProjectStage.PREPARATION,
        ):
            milestone.status = enums.MilestoneStatus.DONE
            milestone.actual_date = today - D(days=300 - milestone.sequence)
        elif milestone.stage == enums.ProjectStage.IMPLEMENTATION:
            milestone.status = enums.MilestoneStatus.IN_PROGRESS
            milestone.planned_date = today + D(days=milestone.sequence)
        else:
            milestone.planned_date = today + D(days=150 + milestone.sequence)
        milestone.note = "Contoh"
        milestone.save()

    announcements = [
        (E.AnnouncementType.LOCATION_PLAN, 270, "Kantor kelurahan Rempang Cate"),
        (E.AnnouncementType.LOCATION_DETERMINATION, 195, "Kantor kecamatan Galang"),
        (E.AnnouncementType.INVENTORY, 120, "Balai warga Sembulang"),
        (E.AnnouncementType.VALUATION, 60, "Balai warga Sembulang"),
    ]
    for kind, days, place in announcements:
        Announcement.objects.create(
            project=project,
            announcement_type=kind,
            announced_on=today - D(days=days),
            location=f"{place} (contoh)",
            document_number=f"PENG/CONTOH/{days:03d}",
            note=SAMPLE_NOTE,
        )

    parcels = {
        p.parcel_number: p
        for p in AcquisitionParcel.objects.filter(project=project).prefetch_related(
            "parties"
        )
    }
    deliberation = Deliberation.objects.create(
        project=project,
        held_on=today - D(days=45),
        location="Balai warga Sembulang (contoh)",
        minutes_number="BA-MUSY/CONTOH/001",
        note=SAMPLE_NOTE,
    )
    for number, parcel in parcels.items():
        party = parcel.parties.first()
        centroid = parcel.geometry.centroid if parcel.geometry else None
        for survey_type in (E.SurveyType.PHYSICAL, E.SurveyType.JURIDICAL):
            needs_check = number == "RMP-006" and survey_type == E.SurveyType.JURIDICAL
            ParcelSurvey.objects.create(
                parcel=parcel,
                survey_type=survey_type,
                status=(
                    E.SurveyStatus.NEEDS_VERIFICATION
                    if needs_check
                    else E.SurveyStatus.DONE
                ),
                survey_date=today - D(days=150),
                team_name=(
                    "Satgas A (contoh)"
                    if survey_type == E.SurveyType.PHYSICAL
                    else "Satgas B (contoh)"
                ),
                latitude=Decimal(f"{centroid.y:.6f}") if centroid else None,
                longitude=Decimal(f"{centroid.x:.6f}") if centroid else None,
                findings=(
                    "Batas bidang perlu dicocokkan dengan peta desa."
                    if needs_check
                    else "Sesuai data awal. " + SAMPLE_NOTE
                ),
            )
        for item_type, description, qty, unit, value in INVENTORY.get(number, []):
            InventoryItem.objects.create(
                parcel=parcel,
                party=party,
                item_type=item_type,
                description=description,
                quantity=Decimal(qty),
                unit=unit,
                condition="Baik",
                unit_value=Decimal(value) if value is not None else None,
                note=SAMPLE_NOTE,
            )
        land, building, plants, non_physical, outcome = VALUATIONS[number]
        valuation = Valuation.objects.create(
            parcel=parcel,
            status=enums.ValuationStatus.FINAL,
            appraiser_firm="KJPP Contoh & Rekan",
            appraiser_name="Penilai Contoh",
            appraiser_license="P-CONTOH-001",
            report_number=f"LAP-NILAI/CONTOH/{number}",
            valuation_date=today - D(days=80),
            submitted_on=today - D(days=70),
            value_land=Decimal(land) * (parcel.affected_area_m2 or MEASURED_AREA),
            value_building=Decimal(building),
            value_plants=Decimal(plants),
            value_non_physical=Decimal(non_physical),
            note=SAMPLE_NOTE,
        )
        result = DeliberationResult.objects.create(
            deliberation=deliberation,
            parcel=parcel,
            party=party,
            outcome=outcome,
            agreed_amount=(
                valuation.total_value
                if outcome == E.DeliberationOutcome.AGREED
                else None
            ),
            signed_on=(
                deliberation.held_on
                if outcome == E.DeliberationOutcome.AGREED
                else None
            ),
            note={
                E.DeliberationOutcome.REJECTED: "Pihak berhak tidak setuju nilai.",
                E.DeliberationOutcome.ABSENT: "Pihak berhak tidak diketahui keberadaannya.",
                E.DeliberationOutcome.POSTPONED: "Diminta penjadwalan ulang.",
            }.get(outcome, "Sepakat bentuk uang."),
        )
        if outcome == E.DeliberationOutcome.POSTPONED:
            continue
        validated = number in ("RMP-001", "RMP-002", "RMP-005")
        compensation = Compensation.objects.create(
            parcel=parcel,
            party=party,
            form=enums.CompensationForm.MONEY,
            amount=valuation.total_value,
            status=(
                enums.CompensationStatus.VALIDATED
                if validated
                else enums.CompensationStatus.DETERMINED
            ),
            valuation=valuation,
            deliberation_result=result,
            validated_on=today - D(days=35) if validated else None,
            description="Ganti kerugian bentuk uang (contoh).",
            note=SAMPLE_NOTE,
        )
        if number == "RMP-001":
            _pay(compensation, party, [(30, compensation.amount)])
            RightsRelease.objects.create(
                parcel=parcel,
                party=party,
                minutes_number="BA-PELEPASAN/CONTOH/001",
                released_on=today - D(days=20),
                certificate_surrendered=True,
                note=SAMPLE_NOTE,
            )
        elif number == "RMP-002":
            half = (compensation.amount / 2).quantize(Decimal("1"))
            _pay(
                compensation,
                party,
                [(28, half), (14, compensation.amount - half)],
            )
        elif number == "RMP-004":
            Objection.objects.create(
                project=project,
                parcel=parcel,
                party=party,
                objection_type=E.ObjectionType.COMPENSATION,
                status=E.ObjectionStatus.IN_PROCESS,
                filed_by_name=party.name if party else "Pihak berhak contoh",
                court_name="Pengadilan Negeri Contoh",
                case_number="1/Pdt.P/CONTOH/PN",
                filed_on=today - D(days=40),
                received_on=today - D(days=39),
                note=SAMPLE_NOTE,
            )
        elif number == "RMP-005":
            Consignment.objects.create(
                parcel=parcel,
                party=party,
                reason=E.ConsignmentReason.UNKNOWN_WHEREABOUTS,
                status=E.ConsignmentStatus.DEPOSITED,
                court_name="Pengadilan Negeri Contoh",
                application_date=today - D(days=30),
                decree_number="2/Pdt.P.Kons/CONTOH/PN",
                decree_date=today - D(days=21),
                deposited_on=today - D(days=18),
                amount=compensation.amount,
                note=SAMPLE_NOTE,
            )

    Objection.objects.create(
        project=project,
        objection_type=E.ObjectionType.LOCATION,
        status=E.ObjectionStatus.REJECTED,
        filed_by_name="Kelompok Warga Contoh",
        court_name="Tim Kajian Keberatan (contoh)",
        filed_on=today - D(days=230),
        decided_on=today - D(days=215),
        decision_summary="Keberatan atas rencana lokasi ditolak; lokasi tetap.",
        note=SAMPLE_NOTE,
    )
    handover = Handover.objects.create(
        project=project,
        minutes_number="BA-SERAH/CONTOH/001",
        handed_over_on=today - D(days=10),
        recipient="Instansi Contoh",
        registration_applied_on=today - D(days=5),
        note=SAMPLE_NOTE,
    )
    handover.parcels.set([parcels["RMP-001"]])

    households = [
        ("Kepala Keluarga Contoh 1", "RMP-001", 4, E.DisplacementStatus.PARTIAL,
         E.ResettlementStage.RESETTLED, 100, "Hunian pengganti tipe 45 (contoh)."),
        ("Kepala Keluarga Contoh 4", "RMP-004", 6, E.DisplacementStatus.FULL,
         E.ResettlementStage.ASSISTANCE, 40, "Biaya pindah dan sewa sementara."),
        ("Kepala Keluarga Contoh 6", "RMP-006", 3, E.DisplacementStatus.NONE,
         E.ResettlementStage.VERIFICATION, 10, ""),
    ]  # fmt: skip
    for head, number, members, displacement, stage, progress, help_ in households:
        AffectedHousehold.objects.create(
            project=project,
            parcel=parcels.get(number),
            head_name=head,
            member_count=members,
            displacement=displacement,
            stage=stage,
            assistance_description=help_,
            monetary_assistance_amount=Decimal("15000000") if help_ else None,
            progress_percentage=progress,
            note=SAMPLE_NOTE,
        )

    documents = [
        (E.DocumentType.DPPT, "Dokumen perencanaan pengadaan tanah", "DPPT/CONTOH/001",
         300, None),
        (E.DocumentType.LOCATION_DECREE, "Keputusan penetapan lokasi",
         "PENLOK/CONTOH/001", 200, None),
        (E.DocumentType.DELIBERATION_MINUTES, "Berita acara musyawarah",
         "BA-MUSY/CONTOH/001", 45, None),
        (E.DocumentType.PAYMENT_PROOF, "Bukti transfer ganti kerugian RMP-001",
         "TRF/CONTOH/001", 30, "RMP-001"),
    ]  # fmt: skip
    for kind, title, number, days, parcel_number in documents:
        parcel = parcels.get(parcel_number) if parcel_number else None
        AcquisitionDocument.objects.create(
            project=project,
            parcel=parcel,
            party=parcel.parties.first() if parcel else None,
            document_type=kind,
            title=f"{title} (contoh)",
            number=number,
            document_date=today - D(days=days),
            file=pdf_upload(title, (SAMPLE_NOTE, f"Nomor: {number}")),
            note=SAMPLE_NOTE,
        )


def _pay(compensation, party, installments) -> None:
    today = timezone.localdate()
    for index, (days, amount) in enumerate(installments, 1):
        CompensationPayment.objects.create(
            compensation=compensation,
            paid_on=today - D(days=days),
            amount=amount,
            method=enums.PaymentMethod.TRANSFER,
            bank_reference=f"TRF/CONTOH/{compensation.parcel.parcel_number}/{index}",
            recipient_name=party.name if party else "",
            note=SAMPLE_NOTE,
        )
