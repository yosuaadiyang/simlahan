"""Data contoh menu Sewa, Kontak, Tagihan, dan menu terkait di aplikasi petugas.

python manage.py sewa_contoh_rempang          # buat (dilewati bila sudah ada)
python manage.py sewa_contoh_rempang --hapus  # hapus seluruh data contoh

Membuat kontak (pemberi sewa, badan usaha, perorangan), tiga sewa di Kec. Galang
(gudang industri aktif, kios komersial dua penyewa, dan sewa lama yang sudah
berakhir lalu dialihkan), lengkap dengan penyewa & kontak penagihan, area sewa
(alamat, kavling, unit rencana & distribusi pemakaian, kesiapan bangun,
lampiran), sewa (sewa kontrak, sewa awal tetap, tanggal jatuh tempo,
penyesuaian & subsidi, sewa terhutang tahun berjalan), dasar sewa & subsidinya,
keputusan & syarat, kontrak & perubahan & jaminan, inspeksi & lampiran,
komentar, riwayat status sewa, tanggal permohonan diterima, catatan penagihan,
surat penagihan, putusan pengadilan, tagihan yang dibuat dengan perhitungan
tagihan sungguhan (sebagian lunas), catatan tagihan, prinsip sewa (tarif,
keputusan, nomor properti), catatan area di peta, kompensasi pembangunan
sisipan, dan tiga pencarian area (diproses, diterima, ditolak) beserta isian
formulir, cek informasi pemohon, catatan status, dan lampiran.

Semua nama, nomor, dan nilai fiktif; surel memakai domain
``contoh.simlahan.invalid``. Sewa contoh dikenali dari catatannya (MARK).
Indeks biaya hidup dan suku bunga tidak diisi: itu data acuan resmi yang
dipakai perhitungan sewa sungguhan.
"""

import datetime
import logging
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from safedelete.config import HARD_DELETE

from leasing.enums import (
    AreaUnit,
    BasisOfRentType,
    CollectionStage,
    ConstructabilityState,
    ConstructabilityType,
    ContactType,
    DueDatesType,
    InfillDevelopmentCompensationState,
    LeaseAreaAttachmentType,
    LeaseAreaType,
    LeaseRelationType,
    LeaseState,
    LocationType,
    PeriodType,
    PlotType,
    RentAdjustmentAmountType,
    RentAdjustmentType,
    RentCycle,
    RentType,
    SubventionType,
    TenantContactType,
)
from leasing.management.commands.create_invoices import create_invoices_for_lease
from leasing.models import (
    AreaNote,
    BasisOfRent,
    BasisOfRentDecision,
    BasisOfRentPlotType,
    BasisOfRentPropertyIdentifier,
    BasisOfRentRate,
    CollateralType,
    CollectionCourtDecision,
    CollectionLetter,
    CollectionNote,
    Comment,
    CommentTopic,
    ConditionType,
    Contact,
    ContractType,
    DecisionMaker,
    DecisionType,
    District,
    InfillDevelopmentCompensation,
    IntendedUse,
    Invoice,
    InvoiceNote,
    InvoicePayment,
    Lease,
    LeaseIdentifier,
    LeaseStateLog,
    LeaseType,
    Municipality,
    NoticePeriod,
    RelatedLease,
    RentIntendedUse,
    ServiceUnit,
)
from leasing.models.contract import Collateral, Contract, ContractChange
from leasing.models.decision import Condition, Decision
from leasing.models.infill_development_compensation import (
    InfillDevelopmentCompensationAttachment,
    InfillDevelopmentCompensationDecision,
    InfillDevelopmentCompensationIntendedUse,
    InfillDevelopmentCompensationLease,
)
from leasing.models.inspection import Inspection, InspectionAttachment
from leasing.models.land_area import (
    ConstructabilityDescription,
    CustomDetailedPlan,
    LeaseArea,
    LeaseAreaAddress,
    LeaseAreaAttachment,
    PlanUnit,
    Plot,
    UsageDistribution,
)
from leasing.models.lease import ApplicationMetadata
from leasing.models.rent import (
    ContractRent,
    FixedInitialYearRent,
    LeaseBasisOfRent,
    LeaseBasisOfRentManagementSubvention,
    LeaseBasisOfRentTemporarySubvention,
    ManagementSubvention,
    ManagementSubventionFormOfManagement,
    Rent,
    RentAdjustment,
    RentDueDate,
    TemporarySubvention,
)
from leasing.models.tenant import Tenant, TenantContact, TenantRentShare
from plotsearch.enums import AreaSearchState, DeclineReason
from utils.sample_files import hard_delete, jpeg_upload, pdf_upload

MARK = "[CONTOH]"
CONTACT_MARK = "[contoh]"
DOMAIN = "contoh.simlahan.invalid"
BATAM = "2171"
DISTRICT = "Galang"
SERVICE_UNIT = 1  # Pengelolaan Aset Lahan dan Kavling (punya jenis piutang sewa)

# Titik acuan area sewa contoh (WGS84), Rempang Cate, tidak tumpang tindih
# dengan bidang pengadaan atau lahan alokasi contoh.
ORIGIN = (104.1200, 0.8880)

# kunci → (jenis, nama/nama depan, nama belakang, kota, lessor?)
CONTACTS = {
    "lessor": (ContactType.UNIT, "Unit Pengelola Lahan (CONTOH)", "", True),
    "gudang": (ContactType.BUSINESS, "PT Contoh Gudang Rempang", "", False),
    "nelayan": (ContactType.ASSOCIATION, "Koperasi Nelayan Contoh", "", False),
    "satu": (ContactType.PERSON, "Contoh", "Penyewa Satu", False),
    "dua": (ContactType.PERSON, "Contoh", "Penyewa Dua", False),
    "tagihan": (ContactType.PERSON, "Contoh", "Bagian Keuangan", False),
}


def sample_leases():
    return Lease.all_objects.filter(note__startswith=MARK)


def sample_contacts():
    return Contact.all_objects.filter(note__startswith=CONTACT_MARK)


def _box(col, row, size=0.0015, gap=0.0004):
    west = ORIGIN[0] + col * (size + gap)
    south = ORIGIN[1] - row * (size + gap)
    return MultiPolygon(
        Polygon.from_bbox((west, south, west + size, south + size)), srid=4326
    )


class Command(BaseCommand):
    help = "Buat atau hapus data contoh sewa, kontak, dan tagihan (fiktif)"

    def add_arguments(self, parser):
        parser.add_argument("--hapus", action="store_true", help="Hapus data contoh")

    def handle(self, *args, **options):
        if options["hapus"]:
            counts = delete_samples()
            self.stdout.write(
                self.style.SUCCESS(
                    "Data contoh sewa dihapus: {} sewa, {} kontak.".format(*counts)
                )
            )
            return
        user = get_user_model().objects.filter(is_superuser=True).order_by("pk").first()
        if user is None:
            raise CommandError(
                "Belum ada akun admin. Jalankan dahulu: python manage.py simlahan_bootstrap"
            )
        if sample_leases().exists():
            with transaction.atomic():
                added = area_search_demo(user)
            if added:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Data contoh sewa sudah ada; {added} pencarian area ditambahkan."
                    )
                )
            else:
                self.stdout.write("Data contoh sewa sudah ada, dilewati.")
            return
        with transaction.atomic():
            leases = self._create(user)
        self.stdout.write(
            self.style.SUCCESS(f"Data contoh sewa dibuat: {len(leases)} sewa.")
        )

    # ------------------------------------------------------------------

    def _lookups(self):
        municipality = Municipality.objects.filter(identifier=BATAM).first()
        district = District.objects.filter(
            municipality=municipality, name=DISTRICT
        ).first()
        unit = ServiceUnit.objects.filter(pk=SERVICE_UNIT).first()
        if not (municipality and district and unit):
            raise CommandError(
                "Data dasar sewa (Kota Batam, Kec. Galang, unit layanan) belum ada. "
                "Jalankan dahulu: python manage.py migrate"
            )
        return municipality, district, unit

    def _contacts(self, unit):
        contacts = {}
        for key, (kind, first, last, lessor) in CONTACTS.items():
            is_person = kind == ContactType.PERSON
            contacts[key] = Contact.objects.create(
                type=kind,
                first_name=first if is_person else None,
                last_name=last if is_person else None,
                name=None if is_person else first,
                business_id=None if is_person else f"CONTOH-{len(contacts) + 1:03d}",
                address=f"Jl. Contoh No. {len(contacts) + 1}",
                postal_code="29400",
                city="Batam",
                country="ID",
                email=f"{key}@{DOMAIN}",
                phone=f"0812000001{len(contacts):02d}",
                language="id" if hasattr(Contact, "language") else None,
                is_lessor=lessor,
                service_unit=unit,
                note=f"{CONTACT_MARK} Kontak fiktif untuk uji coba.",
            )
        return contacts

    def _create(self, user):  # noqa: C901
        municipality, district, unit = self._lookups()
        contacts = self._contacts(unit)
        today = timezone.localdate()
        types = {t.identifier: t for t in LeaseType.objects.all()}
        intended = {i.name: i for i in IntendedUse.objects.filter(service_unit=unit)}
        rent_uses = {r.name: r for r in RentIntendedUse.objects.all()}
        notice = NoticePeriod.objects.order_by("pk").first()
        topic = CommentTopic.objects.order_by("pk").first()
        maker = DecisionMaker.objects.order_by("pk").first()
        decision_types = list(DecisionType.objects.order_by("pk")[:2])
        condition_type = ConditionType.objects.order_by("pk").first()
        contract_type = ContractType.objects.filter(
            name__iexact="Perjanjian sewa"
        ).first()
        collateral_type = CollateralType.objects.filter(name="Jaminan uang").first()

        def lease(code, type_id, use, start, end, note, **extra):
            return Lease.objects.create(
                type=types.get(type_id) or LeaseType.objects.order_by("pk").first(),
                municipality=municipality,
                district=district,
                service_unit=unit,
                intended_use=intended.get(use),
                intended_use_note=note,
                start_date=start,
                end_date=end,
                state=LeaseState.LEASE,
                lessor=contacts["lessor"],
                notice_period=notice,
                preparer=user,
                note=f"{MARK} Sewa contoh {code} – fiktif, bukan perjanjian sah.",
                **extra,
            )

        warehouse = lease(
            "01",
            "T1",
            "Bangunan produksi/industri",
            datetime.date(today.year - 1, 1, 1),
            datetime.date(today.year + 29, 12, 31),
            "Gudang dan pabrik pengemasan hasil laut.",
            transferable=True,
            reference_number="SEWA/CONTOH/001",
        )
        kiosk = lease(
            "02",
            "L1",
            "Bangunan komersial",
            datetime.date(today.year - 1, 1, 1),
            datetime.date(today.year + 4, 12, 31),
            "Kios dan warung makan di simpang jalan.",
        )
        old = lease(
            "03",
            "L1",
            "Bangunan komersial",
            datetime.date(today.year - 8, 1, 1),
            datetime.date(today.year - 1, 12, 31),
            "Sewa lama kios; dialihkan ke sewa contoh 02.",
        )
        RelatedLease.objects.create(
            from_lease=old,
            to_lease=kiosk,
            type=LeaseRelationType.TRANSFER,
            start_date=kiosk.start_date,
        )

        # Penyewa dan kontak (bagian sewa per peruntukan dipakai saat penagihan)
        industry = rent_uses.get("Industri/gudang") or RentIntendedUse.objects.first()
        commercial = rent_uses.get("Komersial") or industry
        self._tenant(warehouse, industry, contacts["gudang"], 1, 1, contacts["tagihan"])
        self._tenant(kiosk, commercial, contacts["satu"], 1, 2)
        self._tenant(kiosk, commercial, contacts["dua"], 1, 2)
        self._tenant(old, commercial, contacts["nelayan"], 1, 1, ended=old.end_date)

        # Area sewa
        areas = {}
        plan_units = {}
        for index, (item, address, area) in enumerate(
            (
                (warehouse, "Jl. Contoh Kawasan Industri No. 1", 12000),
                (kiosk, "Jl. Contoh Simpang Rempang No. 7", 150),
                (old, "Jl. Contoh Simpang Rempang No. 7", 150),
            )
        ):
            geometry = _box(index, 0, 0.003 if index == 0 else 0.0006)
            lease_area = LeaseArea.objects.create(
                lease=item,
                identifier=f"CONTOH-AREA-{index + 1:02d}",
                area=area,
                section_area=area,
                type=LeaseAreaType.REAL_PROPERTY,
                location=LocationType.SURFACE,
                geometry=geometry,
                preconstruction_state=ConstructabilityState.COMPLETE,
                demolition_state=ConstructabilityState.UNVERIFIED,
                polluted_land_state=(
                    ConstructabilityState.REQUIRES_MEASURES
                    if index == 0
                    else ConstructabilityState.COMPLETE
                ),
            )
            LeaseAreaAddress.objects.create(
                lease_area=lease_area,
                address=address,
                postal_code="29400",
                city="Batam",
                is_primary=True,
            )
            Plot.objects.create(
                lease_area=lease_area,
                identifier=f"CONTOH-KAV-{index + 1:02d}",
                area=area,
                section_area=area,
                type=PlotType.REAL_PROPERTY,
                geometry=geometry,
                in_contract=True,
            )
            plan_units[item.pk] = PlanUnit.objects.create(
                lease_area=lease_area,
                identifier=f"CONTOH-UR-{index + 1:02d}",
                area=area,
                section_area=area,
                geometry=geometry,
                in_contract=True,
                detailed_plan_identifier="RDTR-CONTOH-01",
            )
            areas[item.pk] = lease_area
        warehouse_area = areas[warehouse.pk]
        ConstructabilityDescription.objects.create(
            lease_area=warehouse_area,
            type=ConstructabilityType.POLLUTED_LAND,
            user=user,
            text="Bekas tempat penimbunan oli; uji tanah diperlukan sebelum konstruksi.",
        )
        ConstructabilityDescription.objects.create(
            lease_area=warehouse_area,
            type=ConstructabilityType.PRECONSTRUCTION,
            user=user,
            text="Pematangan lahan selesai (contoh).",
        )
        for distribution, permission, note in (
            ("Bangunan produksi", "8.000 m²", "Gedung pengemasan hasil laut."),
            ("Gudang berpendingin", "2.500 m²", "Penyimpanan beku."),
        ):
            UsageDistribution.objects.create(
                plan_unit=plan_units[warehouse.pk],
                distribution=distribution,
                build_permission=permission,
                note=f"{note} (contoh)",
            )
        LeaseAreaAttachment.objects.create(
            lease_area=warehouse_area,
            type=LeaseAreaAttachmentType.GEOTECHNICAL,
            file=pdf_upload("Laporan geoteknik area sewa contoh"),
            uploader=user,
        )
        plan_use = None
        from leasing.models import PlanUnitIntendedUse

        plan_use = PlanUnitIntendedUse.objects.order_by("pk").first()
        if plan_use is not None:
            CustomDetailedPlan.objects.create(
                lease_area=warehouse_area,
                identifier="RDTR-CONTOH-01",
                intended_use=plan_use,
                address="Jl. Contoh Kawasan Industri No. 1",
                area=12000,
                rent_build_permission=6000,
                detailed_plan="Rencana detail tata ruang contoh",
            )

        # Sewa (rent)
        self._rent(
            warehouse,
            industry,
            Decimal("96000000"),
            PeriodType.PER_YEAR,
            due_dates=[(1, 1), (1, 7)],
            initial=Decimal("60000000"),
            discount=True,
        )
        self._rent(
            kiosk,
            commercial,
            Decimal("1500000"),
            PeriodType.PER_MONTH,
            due_dates=[(1, month) for month in (1, 4, 7, 10)],
        )
        self._rent(old, commercial, Decimal("9000000"), PeriodType.PER_YEAR, [(1, 1)])
        basis_of_rent = LeaseBasisOfRent.objects.create(
            lease=warehouse,
            type=BasisOfRentType.LEASE,
            intended_use=industry,
            area=Decimal("12000"),
            area_unit=AreaUnit.SQUARE_METRE,
            amount_per_area=Decimal("15000"),
            profit_margin_percentage=Decimal("5"),
            discount_percentage=Decimal("0"),
            subvention_type=SubventionType.FORM_OF_MANAGEMENT,
        )
        self._subventions(warehouse, basis_of_rent)
        for rent in Rent.objects.filter(lease__in=(warehouse, kiosk, old)):
            rent.calculate_payable_rent()

        # Keputusan, syarat, kontrak, jaminan
        for item, days, reference in (
            (warehouse, 400, "KEP/CONTOH/001"),
            (kiosk, 380, "KEP/CONTOH/002"),
        ):
            decision = Decision.objects.create(
                lease=item,
                reference_number=reference,
                decision_maker=maker,
                decision_date=today - datetime.timedelta(days=days),
                section="3",
                type=decision_types[0] if decision_types else None,
                description="Persetujuan sewa lahan (contoh).",
            )
            Condition.objects.create(
                decision=decision,
                type=condition_type,
                supervision_date=today + datetime.timedelta(days=60),
                description="Penyewa wajib membangun dalam 2 tahun (contoh).",
            )
            if contract_type is None:
                continue
            contract = Contract.objects.create(
                lease=item,
                type=contract_type,
                contract_number=reference.replace("KEP", "PKS"),
                signing_date=decision.decision_date + datetime.timedelta(days=14),
                sign_by_date=decision.decision_date + datetime.timedelta(days=30),
                decision=decision,
                executor=user,
            )
            ContractChange.objects.create(
                contract=contract,
                signing_date=today - datetime.timedelta(days=40),
                description="Perubahan jadwal pembayaran (contoh).",
                decision=decision,
                executor=user,
            )
            if collateral_type is not None:
                Collateral.objects.create(
                    contract=contract,
                    type=collateral_type,
                    number="JAM/CONTOH/001",
                    start_date=item.start_date,
                    end_date=item.end_date,
                    total_amount=Decimal("45000000"),
                    paid_date=item.start_date,
                    note="Jaminan contoh.",
                )

        inspection = Inspection.objects.create(
            lease=warehouse,
            inspector="Petugas Pengawas Contoh",
            supervision_date=today - datetime.timedelta(days=20),
            supervised_date=today - datetime.timedelta(days=18),
            description="Pembangunan gudang sesuai rencana; pagar sudah terpasang.",
        )
        InspectionAttachment.objects.create(
            inspection=inspection,
            file=jpeg_upload("Foto inspeksi gudang contoh"),
            uploader=user,
        )
        if topic is not None:
            for item, text in (
                (warehouse, "Penyewa meminta jadwal ulang pembayaran semester 2."),
                (kiosk, "Kedua penyewa sepakat pembagian 50:50."),
            ):
                Comment.objects.create(
                    lease=item, user=user, topic=topic, text=f"{MARK} {text}"
                )

        # Tagihan dibuat bulan demi bulan dengan fungsi yang sama dengan tugas
        # terjadwal create_invoices, seolah penagihan berjalan sejak awal sewa.
        loggers = [
            logging.getLogger(name)
            for name in (
                "leasing",
                "leasing.models.lease",
                create_invoices_for_lease.__module__,
            )
        ]
        levels = [item.level for item in loggers]
        for item in loggers:
            item.setLevel(logging.WARNING)
        try:
            for item in (warehouse, kiosk):
                item.rent_info_completed_at = timezone.now()
                item.invoicing_enabled_at = timezone.now()
                item.save()
                month = item.start_date.replace(day=1)
                while month <= today.replace(day=1):
                    create_invoices_for_lease(
                        item,
                        month,
                        month + relativedelta(day=31),
                        month - relativedelta(months=1),
                    )
                    month += relativedelta(months=1)
        finally:
            for item, level in zip(loggers, levels):
                item.setLevel(level)
        self._settle_invoices(warehouse, keep_open=1)
        self._settle_invoices(kiosk, keep_open=2)
        open_invoice = (
            Invoice.objects.filter(lease=warehouse, outstanding_amount__gt=0)
            .order_by("due_date")
            .first()
        )
        if open_invoice is not None:
            CollectionNote.objects.create(
                lease=warehouse,
                user=user,
                note=f"{MARK} Pengingat pembayaran dikirim lewat surel.",
                collection_stage=CollectionStage.SIMPLE_PAYMENT_REMINDER,
                sent_date=today - datetime.timedelta(days=3),
            )
        InvoiceNote.objects.create(
            lease=warehouse,
            billing_period_start_date=datetime.date(today.year, 7, 1),
            billing_period_end_date=datetime.date(today.year, 12, 31),
            notes=f"{MARK} Cantumkan nomor PO penyewa pada tagihan semester 2.",
        )

        CollectionLetter.objects.create(
            lease=warehouse,
            file=pdf_upload(
                "Surat penagihan sewa contoh", ("Penagihan tunggakan sewa gudang.",)
            ),
            uploader=user,
        )
        CollectionCourtDecision.objects.create(
            lease=old,
            file=pdf_upload("Putusan pengadilan penagihan contoh"),
            decision_date=today - datetime.timedelta(days=200),
            note=f"{MARK} Putusan fiktif atas tunggakan sewa lama.",
            uploader=user,
        )
        for item, states in (
            (warehouse, (LeaseState.RESERVATION, LeaseState.LEASE)),
            (kiosk, (LeaseState.LEASE,)),
            (old, (LeaseState.LEASE, LeaseState.LONG_TERM_LEASE)),
        ):
            for state in states:
                LeaseStateLog.objects.create(lease=item, state=state)
        for item, days in ((warehouse, 430), (kiosk, 410)):
            item.application_metadata = ApplicationMetadata.objects.create(
                application_received_at=today - datetime.timedelta(days=days)
            )
            item.save(update_fields=["application_metadata"])

        self._basis_of_rent(today)
        self._area_note(user)
        self._infill(warehouse, user, maker)
        area_search_demo(user)
        return [warehouse, kiosk, old]

    # ------------------------------------------------------------------

    def _tenant(
        self, lease, use, contact, numerator, denominator, billing=None, ended=None
    ):
        tenant = Tenant.objects.create(
            lease=lease,
            share_numerator=numerator,
            share_denominator=denominator,
            reference=f"PENYEWA-{lease.pk}-{contact.pk}",
        )
        TenantRentShare.objects.create(
            tenant=tenant,
            intended_use=use,
            share_numerator=numerator,
            share_denominator=denominator,
        )
        TenantContact.objects.create(
            tenant=tenant,
            contact=contact,
            type=TenantContactType.TENANT,
            start_date=lease.start_date,
            end_date=ended,
        )
        if billing is not None:
            TenantContact.objects.create(
                tenant=tenant,
                contact=billing,
                type=TenantContactType.BILLING,
                start_date=lease.start_date,
            )
        return tenant

    def _rent(
        self,
        lease,
        use,
        amount,
        period,
        due_dates,
        initial=None,
        discount=False,
    ):
        rent = Rent.objects.create(
            lease=lease,
            type=RentType.FIXED,
            cycle=RentCycle.JANUARY_TO_DECEMBER,
            due_dates_type=DueDatesType.CUSTOM,
            start_date=lease.start_date,
            end_date=lease.end_date,
            note="Sewa tetap (contoh).",
        )
        for day, month in due_dates:
            RentDueDate.objects.create(rent=rent, day=day, month=month)
        start = lease.start_date
        if initial is not None:
            FixedInitialYearRent.objects.create(
                rent=rent,
                amount=initial,
                intended_use=use,
                start_date=start,
                end_date=start + relativedelta(years=1, days=-1),
            )
            start = start + relativedelta(years=1)
        ContractRent.objects.create(
            rent=rent,
            amount=amount,
            period=period,
            intended_use=use,
            base_amount=amount,
            base_amount_period=period,
            start_date=start,
            end_date=lease.end_date,
        )
        if discount:
            RentAdjustment.objects.create(
                rent=rent,
                type=RentAdjustmentType.DISCOUNT,
                intended_use=use,
                start_date=lease.start_date + relativedelta(years=1),
                end_date=lease.start_date + relativedelta(years=2, days=-1),
                full_amount=Decimal("10"),
                amount_type=RentAdjustmentAmountType.PERCENT_PER_YEAR,
                note="Potongan masa konstruksi (contoh).",
            )
        return rent

    def _subventions(self, lease, basis_of_rent):
        """Subsidi bentuk pengelolaan dan subsidi sementara, pada dasar sewa
        dan pada penyesuaian sewa (hanya tampilan; tidak mengubah tagihan)."""
        management = ManagementSubventionFormOfManagement.objects.order_by("pk").first()
        if management is not None:
            LeaseBasisOfRentManagementSubvention.objects.create(
                lease_basis_of_rent=basis_of_rent,
                management=management,
                subvention_amount=Decimal("2400000"),
            )
        LeaseBasisOfRentTemporarySubvention.objects.create(
            lease_basis_of_rent=basis_of_rent,
            description="Keringanan masa pemulihan usaha (contoh)",
            subvention_percent=Decimal("5"),
        )
        adjustment = RentAdjustment.objects.filter(rent__lease=lease).first()
        if adjustment is None:
            return
        adjustment.subvention_type = SubventionType.FORM_OF_MANAGEMENT
        adjustment.subvention_base_percent = Decimal("10")
        adjustment.save(update_fields=["subvention_type", "subvention_base_percent"])
        if management is not None:
            ManagementSubvention.objects.create(
                rent_adjustment=adjustment,
                management=management,
                subvention_amount=Decimal("2400000"),
            )
        TemporarySubvention.objects.create(
            rent_adjustment=adjustment,
            description="Keringanan masa konstruksi (contoh)",
            subvention_percent=Decimal("5"),
        )

    def _settle_invoices(self, lease, keep_open: int):
        invoices = list(Invoice.objects.filter(lease=lease).order_by("due_date", "pk"))
        paid = invoices[: max(len(invoices) - keep_open, 0)]
        for invoice in paid:
            InvoicePayment.objects.create(
                invoice=invoice,
                paid_amount=invoice.billed_amount,
                paid_date=invoice.due_date or timezone.localdate(),
                filing_code="CONTOH",
            )
            invoice.update_amounts()

    def _basis_of_rent(self, today):
        plot_type = BasisOfRentPlotType.objects.order_by("pk").first()
        if plot_type is None:
            return
        basis = BasisOfRent.objects.create(
            plot_type=plot_type,
            start_date=datetime.date(today.year, 1, 1),
            end_date=datetime.date(today.year + 4, 12, 31),
            detailed_plan_identifier="RDTR-CONTOH-01",
            note=f"{CONTACT_MARK} Prinsip sewa kawasan industri contoh.",
            geometry=_box(0, 2, 0.006),
        )
        from leasing.models import BasisOfRentBuildPermissionType

        for permission, amount in zip(
            BasisOfRentBuildPermissionType.objects.order_by("pk")[:2],
            (Decimal("15000"), Decimal("22000")),
        ):
            BasisOfRentRate.objects.create(
                basis_of_rent=basis,
                build_permission_type=permission,
                amount=amount,
                area_unit=AreaUnit.SQUARE_METRE,
            )
        BasisOfRentPropertyIdentifier.objects.create(
            basis_of_rent=basis, identifier="CONTOH-KAV-01", geometry=_box(0, 0, 0.003)
        )
        BasisOfRentDecision.objects.create(
            basis_of_rent=basis,
            reference_number="KEP/CONTOH/PRINSIP/01",
            decision_maker=DecisionMaker.objects.order_by("pk").first(),
            decision_date=datetime.date(today.year, 1, 1),
            section="5",
        )

    def _area_note(self, user):
        AreaNote.objects.create(
            user=user,
            geometry=_box(3, 1, 0.004),
            note=f"{CONTACT_MARK} Rencana jalan akses kawasan; jangan disewakan dulu.",
        )

    def _infill(self, lease, user, maker):
        compensation = InfillDevelopmentCompensation.objects.create(
            user=user,
            name=f"{MARK} Kompensasi pembangunan sisipan gudang",
            reference_number="KPS/CONTOH/001",
            detailed_plan_identifier="RDTR-CONTOH-01",
            state=InfillDevelopmentCompensationState.NEGOTIATING,
            note="Perluasan hak bangun di area sewa contoh 01.",
            geometry=_box(0, 0, 0.003),
        )
        link = InfillDevelopmentCompensationLease.objects.create(
            infill_development_compensation=compensation,
            lease=lease,
            monetary_compensation_amount=Decimal("85000000"),
            compensation_investment_amount=Decimal("50000000"),
            increase_in_value=Decimal("95000000"),
            part_of_the_increase_in_value=Decimal("30"),
            discount_in_rent=Decimal("0"),
            year=timezone.localdate().year,
            note="Contoh.",
        )
        InfillDevelopmentCompensationDecision.objects.create(
            infill_development_compensation_lease=link,
            reference_number="KEP/CONTOH/KPS/01",
            decision_maker=maker,
            decision_date=timezone.localdate() - datetime.timedelta(days=15),
            section="7",
        )
        InfillDevelopmentCompensationIntendedUse.objects.create(
            infill_development_compensation_lease=link,
            intended_use=lease.intended_use,
            floor_m2=Decimal("2500"),
            amount_per_floor_m2=Decimal("100000"),
        )
        InfillDevelopmentCompensationAttachment.objects.create(
            infill_development_compensation_lease=link,
            file=pdf_upload("Hitungan kompensasi pembangunan sisipan contoh"),
            uploader=user,
        )


# --------------------------------------------------------------------------
# Pencarian area (permohonan lahan oleh petugas atas nama pemohon)
# --------------------------------------------------------------------------

AREA_SEARCHES = (
    # (kode, peruntukan, status, jenis pemohon, nama, uraian)
    (
        "01",
        "Kapal dan dermaga",
        AreaSearchState.IN_ACTION,
        "company",
        "PT Contoh Bahari Rempang",
        "Dermaga apung untuk kapal wisata dan tambatan perahu nelayan.",
    ),
    (
        "02",
        "Kuliner, penjualan dan periklanan",
        AreaSearchState.RECEIVED,
        "person",
        "Contoh Pemohon Area",
        "Lapak kuliner musiman di tepi pantai selama libur sekolah.",
    ),
    (
        "03",
        "Pergudangan dan distribusi",
        AreaSearchState.DECLINED,
        "company",
        "CV Contoh Logistik",
        "Gudang transit material bangunan.",
    ),
)


def sample_area_searches():
    from plotsearch.models import AreaSearch

    return AreaSearch.objects.filter(description_intended_use__startswith=MARK)


def _yes(value=True):
    return {"value": value, "extraValue": ""}


def _area_entries(kind, name, code):
    """Isian formulir pencarian area dengan susunan yang sama dengan yang
    dikirim SPA (application/helpers.ts prepareApplicationForSubmission)."""
    phone = f"08120000{int(code):02d}11"
    email = f"area{code}@{DOMAIN}"
    if kind == "company":
        npwp = f"0100000000000{int(code):02d}"
        applicant = {
            "metadata": {"applicantType": "company", "identifier": npwp},
            "fields": {"hakija": _yes("1")},
            "sections": {
                "yrityksen-tiedot": {
                    "fields": {
                        "yrityksen-nimi": _yes(f"{name} (contoh)"),
                        "y-tunnus": _yes(npwp),
                        "katuosoite": _yes(f"Jl. Contoh Pelabuhan No. {code}"),
                        "postinumero": _yes("29400"),
                        "postitoimipaikka": _yes("Batam"),
                        "maa": _yes("Indonesia"),
                        "puhelinnumero": _yes(phone),
                        "sahkoposti": _yes(email),
                    },
                    "sections": {
                        "yhteyshenkilo-company": {
                            "fields": {
                                "etunimi": _yes("Contoh"),
                                "Sukunimi": _yes("Narahubung"),
                                "sahkoposti": _yes(email),
                                "puhelinnumero": _yes(phone),
                            },
                        },
                    },
                },
            },
        }
    else:
        nik = f"21710145079000{int(code):02d}"
        applicant = {
            "metadata": {"applicantType": "person", "identifier": nik},
            "fields": {"hakija": _yes("2")},
            "sections": {
                "henkilon-tiedot": {
                    "fields": {
                        "etunimi": _yes("Contoh"),
                        "Sukunimi": _yes("Pemohon Area"),
                        "henkilotunnus": _yes(nik),
                        "kieli": _yes("indonesia"),
                        "puhelinnumero": _yes(phone),
                        "sahkoposti": _yes(email),
                        "katuosoite": _yes(f"Jl. Contoh Kampung No. {code}"),
                        "postinumero": _yes("29400"),
                        "postitoimipaikka": _yes("Batam"),
                        "maa": _yes("Indonesia"),
                        "turvakielto": _yes("ei"),
                    },
                },
            },
        }
    return {
        "sections": {
            "hakijan-tiedot": [applicant],
            "päätöksen-toimitus": {
                "fields": {
                    "vakuutan-antamani-tiedot-oikeiksi": _yes(True),
                    "pakotelista-vakuutus": _yes(True),
                    "sahkoisesti-ilmoittamaani-sahkopostiosoitteeseen": _yes(True),
                    "hyvaksyn-tietojeni-tallentamisen": _yes(True),
                },
            },
        },
    }


def area_search_demo(user) -> int:
    """Buat pencarian area contoh bila belum ada. Formulir pencarian area dibuat
    dengan fungsi yang sama dengan API bila belum ada, dan formulir itu tidak
    ikut dihapus karena dipakai pencarian area sungguhan."""
    from types import SimpleNamespace

    from forms.management.commands.generate_areasearch_form import (
        initialize_area_search_form,
    )
    from forms.models import Form
    from forms.serializers.form import AnswerSerializer
    from plotsearch.models import AreaSearch, AreaSearchIntendedUse
    from plotsearch.models.plot_search import (
        AreaSearchAttachment,
        AreaSearchStatus,
        AreaSearchStatusNote,
    )
    from plotsearch.utils import map_intended_use_to_lessor

    if sample_area_searches().exists():
        return 0
    form = Form.objects.filter(is_area_form=True).last()
    if form is None:
        form = initialize_area_search_form()
    if not form.sections.filter(identifier="hakijan-tiedot").exists():
        # Formulir lama dengan identifier keliru: jalankan migrate dahulu.
        return 0
    uses = {use.name: use for use in AreaSearchIntendedUse.objects.all()}
    unit = ServiceUnit.objects.filter(pk=SERVICE_UNIT).first()
    now = timezone.now()
    created = 0
    for index, (code, use_name, state, kind, name, text) in enumerate(AREA_SEARCHES):
        use = uses.get(use_name) or AreaSearchIntendedUse.objects.order_by("pk").first()
        if use is None:
            return created
        status = AreaSearchStatus.objects.create(
            decline_reason=(
                DeclineReason.NOT_AVAILABLE_LEASE
                if state == AreaSearchState.DECLINED
                else None
            ),
            preparer_note=f"{CONTACT_MARK} Catatan petugas untuk permohonan {code}.",
        )
        area_search = AreaSearch.objects.create(
            geometry=_box(index, 4, 0.0012),
            description_area=f"Area contoh {code} di pesisir Rempang Cate.",
            address=f"Jl. Contoh Pesisir No. {code}",
            district=DISTRICT,
            intended_use=use,
            description_intended_use=f"{MARK} {text}",
            start_date=now + datetime.timedelta(days=30),
            end_date=now + datetime.timedelta(days=30 + 365 * (index + 1)),
            state=state,
            settled_date=now if state == AreaSearchState.DECLINED else None,
            form=form,
            user=user,
            preparer=user,
            area_search_status=status,
            service_unit=unit,
            lessor=map_intended_use_to_lessor(use),
        )
        AreaSearch.objects.filter(pk=area_search.pk).update(
            received_date=now - datetime.timedelta(days=12 - index * 4)
        )
        AreaSearchStatusNote.objects.create(
            note=(
                "Ditolak: area direncanakan untuk jalan akses (contoh)."
                if state == AreaSearchState.DECLINED
                else "Permohonan diterima dan sedang ditelaah (contoh)."
            ),
            preparer=user,
            time_stamp=now - datetime.timedelta(days=10 - index * 4),
            area_search_status=status,
        )
        serializer = AnswerSerializer(
            data={
                "form": form.pk,
                "entries": _area_entries(kind, name, code),
                "area_search": area_search.pk,
                "ready": True,
            },
            context={"request": SimpleNamespace(user=user)},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        attachment = AreaSearchAttachment(
            name=f"Sketsa lokasi permohonan {code} (contoh).pdf",
            attachment=pdf_upload(f"Sketsa lokasi pencarian area {code}"),
            user=user,
            area_search=area_search,
        )
        attachment.save(skip_virus_scan=True)
        created += 1
    return created


# --------------------------------------------------------------------------
# Penghapusan
# --------------------------------------------------------------------------


@transaction.atomic
def delete_samples() -> tuple[int, int]:
    leases = list(sample_leases())
    identifiers = [lease.identifier_id for lease in leases if lease.identifier_id]
    metadata = [lease.application_metadata_id for lease in leases]
    from forms.models import Answer

    area_searches = list(sample_area_searches())
    roots = [
        *Answer.objects.filter(area_search__in=area_searches),
        *area_searches,
        *[item.area_search_status for item in area_searches if item.area_search_status],
        *InfillDevelopmentCompensation.all_objects.filter(name__startswith=MARK),
        *Invoice.all_objects.filter(lease__in=leases),
        *leases,
        *BasisOfRent.all_objects.filter(note__startswith=CONTACT_MARK),
        *AreaNote.all_objects.filter(note__startswith=CONTACT_MARK),
    ]
    hard_delete(roots)
    LeaseIdentifier.all_objects.filter(pk__in=identifiers).delete(
        force_policy=HARD_DELETE
    )
    ApplicationMetadata.objects.filter(pk__in=[pk for pk in metadata if pk]).delete()
    removed = 0
    for contact in sample_contacts():
        # Kontak contoh yang terlanjur dipakai data sungguhan dibiarkan.
        try:
            with transaction.atomic():
                contact.delete(force_policy=HARD_DELETE)
            removed += 1
        except ProtectedError:
            continue
    return len(leases), removed
