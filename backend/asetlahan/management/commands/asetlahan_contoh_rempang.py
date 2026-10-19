"""Data contoh manajemen aset lahan di Pulau Rempang (fiktif, untuk uji coba).

python manage.py asetlahan_contoh_rempang          # buat (dilewati bila sudah ada)
python manage.py asetlahan_contoh_rempang --hapus  # hapus seluruh data contoh

Membuat aset dengan batas bidang, riwayat kepemilikan, silsilah waris,
pemangku kepentingan, penilaian, pajak, transaksi, perkara & sidang, kasus
okupasi, survei, urusan instansi, tugas, pengaduan, lelang, permukiman
kembali, dan peta berbagi. Semua nama & nomor fiktif.
"""

import datetime
from decimal import Decimal

from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from asetlahan import enums
from asetlahan.models import (
    Advocate,
    AssetCategory,
    AssetValuation,
    CaseHearing,
    EncroachmentActionLog,
    EncroachmentCase,
    Grievance,
    GrievanceCategory,
    HeirMember,
    Heirship,
    LandAsset,
    LandTransaction,
    LegalCase,
    LiaisonActivity,
    MapShare,
    OwnershipRecord,
    ResettlementSite,
    ResettlementUnit,
    Stakeholder,
    StakeholderEngagement,
    SurveyRequest,
    Task,
    TaxObligation,
    Tender,
    ValuationItem,
)

PREFIX = "CONTOH-AST-"
MARK = "[contoh]"

# (kode, nama, kategori, status, lon, lat, ukuran derajat, kelurahan, alas hak, nomor, pemegang, NJOP/m²)
ASSETS = [
    (
        "01",
        "Kantor Kecamatan Galang",
        "Kantor & fasilitas pemerintah",
        enums.AssetStatus.IN_USE,
        104.168,
        0.842,
        0.0012,
        "Sembulang",
        enums.TitleType.HP,
        "00012",
        "Pemerintah Kota",
        450000,
    ),
    (
        "02",
        "Tanah Cadangan Rempang Cate",
        "Tanah cadangan / kosong",
        enums.AssetStatus.ENCROACHED,
        104.142,
        0.852,
        0.0030,
        "Rempang Cate",
        enums.TitleType.HPL,
        "00003",
        "Pemerintah Kota",
        250000,
    ),
    (
        "03",
        "Lahan Kerja Sama Dermaga Nelayan",
        "Lahan disewakan / kerja sama",
        enums.AssetStatus.LEASED,
        104.198,
        0.812,
        0.0015,
        "Sembulang",
        enums.TitleType.HGB,
        "00145",
        "Koperasi Nelayan Contoh",
        350000,
    ),
    (
        "04",
        "Kawasan Permukiman Kembali Tanjung",
        "Permukiman kembali",
        enums.AssetStatus.ALLOCATED,
        104.176,
        0.826,
        0.0035,
        "Sembulang",
        enums.TitleType.HPL,
        "00007",
        "Pemerintah Kota",
        300000,
    ),
    (
        "05",
        "Bidang Sengketa Pasir Panjang",
        "Tanah cadangan / kosong",
        enums.AssetStatus.DISPUTED,
        104.212,
        0.834,
        0.0018,
        "Pasir Panjang",
        enums.TitleType.GIRIK,
        "C-221",
        "Ahli waris (dalam sengketa)",
        200000,
    ),
]


def _square(lon, lat, size) -> MultiPolygon:
    return MultiPolygon(
        Polygon.from_bbox((lon, lat, lon + size, lat + size)), srid=4326
    )


class Command(BaseCommand):
    help = "Buat atau hapus data contoh manajemen aset lahan di Pulau Rempang (fiktif)"

    def add_arguments(self, parser):
        parser.add_argument("--hapus", action="store_true", help="Hapus data contoh")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["hapus"]:
            self._delete()
            self.stdout.write(self.style.SUCCESS("Data contoh aset lahan dihapus."))
            return
        if LandAsset.objects.filter(code__startswith=PREFIX).exists():
            self.stdout.write(
                "Data contoh aset lahan sudah ada; jalankan --hapus dahulu untuk membuat ulang."
            )
            return
        assets = self._assets()
        self._ownership(assets)
        self._finance(assets)
        case = self._legal(assets)
        self._encroachment(assets, case)
        self._operations(assets)
        self._public(assets)
        self.stdout.write(
            self.style.SUCCESS(f"Data contoh aset lahan dibuat: {len(assets)} aset.")
        )

    def _delete(self):
        codes = LandAsset.objects.filter(code__startswith=PREFIX)
        MapShare.objects.filter(title__startswith=MARK).delete()
        Tender.objects.filter(title__startswith=MARK).delete()
        Grievance.objects.filter(subject__startswith=MARK).delete()
        Task.objects.filter(title__startswith=MARK).delete()
        LiaisonActivity.objects.filter(subject__startswith=MARK).delete()
        SurveyRequest.objects.filter(purpose__startswith=MARK).delete()
        EncroachmentCase.objects.filter(title__startswith=MARK).delete()
        LandTransaction.objects.filter(description__startswith=MARK).delete()
        LegalCase.objects.filter(title__startswith=MARK).delete()
        Advocate.objects.filter(name__startswith=MARK).delete()
        Stakeholder.objects.filter(name__startswith=MARK).delete()
        ResettlementSite.objects.filter(name__startswith=MARK).delete()
        Heirship.objects.filter(decedent_name__startswith=MARK).delete()
        codes.delete()

    def _assets(self) -> dict:
        categories = {c.name: c for c in AssetCategory.objects.all()}
        assets = {}
        for (
            code,
            name,
            category,
            status,
            lon,
            lat,
            size,
            village,
            title,
            number,
            owner,
            njop,
        ) in ASSETS:
            assets[code] = LandAsset.objects.create(
                code=PREFIX + code,
                name=name,
                category=categories.get(category),
                status=status,
                district="Galang",
                village=village,
                geometry=_square(lon, lat, size),
                title_type=title,
                title_number=number,
                registered_owner=owner,
                njop_per_m2=Decimal(njop),
                title_date=datetime.date(2010, 3, 1),
                title_expiry=(
                    timezone.localdate() + datetime.timedelta(days=60)
                    if code == "03"
                    else None
                ),
                acquisition_method=enums.AcquisitionMethod.DESIGNATION,
                note=MARK,
            )
        return assets

    def _ownership(self, assets):
        disputed = assets["05"]
        OwnershipRecord.objects.create(
            asset=disputed,
            owner_name="Almarhum Contoh Bin Fiktif",
            start_date=datetime.date(1985, 1, 1),
            end_date=datetime.date(2019, 6, 1),
            basis="Girik C-221",
        )
        OwnershipRecord.objects.create(
            asset=disputed,
            owner_name="Ahli waris (3 orang)",
            start_date=datetime.date(2019, 6, 1),
            basis="Waris, belum dibagi",
        )
        heirship = Heirship.objects.create(
            asset=disputed,
            decedent_name=f"{MARK} Contoh Bin Fiktif",
            date_of_death=datetime.date(2019, 6, 1),
        )
        HeirMember.objects.create(
            heirship=heirship,
            name="Siti Contoh",
            relation=enums.Kinship.SPOUSE,
            share_percentage=Decimal("12.5"),
        )
        child = HeirMember.objects.create(
            heirship=heirship,
            name="Ahmad Contoh",
            relation=enums.Kinship.CHILD,
            share_percentage=Decimal("43.75"),
        )
        HeirMember.objects.create(
            heirship=heirship,
            name="Rina Contoh",
            relation=enums.Kinship.CHILD,
            is_alive=False,
        )
        HeirMember.objects.create(
            heirship=heirship,
            parent=child,
            name="Dimas Contoh",
            relation=enums.Kinship.GRANDCHILD,
        )
        for name, kind, influence, interest, stance in (
            (
                "Ketua RW Kampung Contoh",
                enums.StakeholderType.COMMUNITY_LEADER,
                enums.Level.HIGH,
                enums.Level.HIGH,
                enums.Stance.NEUTRAL,
            ),
            (
                "Lembaga Adat Contoh",
                enums.StakeholderType.COMMUNITY_LEADER,
                enums.Level.HIGH,
                enums.Level.MEDIUM,
                enums.Stance.OPPOSE,
            ),
            (
                "Kantor Pertanahan Contoh",
                enums.StakeholderType.GOVERNMENT,
                enums.Level.HIGH,
                enums.Level.LOW,
                enums.Stance.SUPPORT,
            ),
            (
                "Koperasi Nelayan Contoh",
                enums.StakeholderType.COMPANY,
                enums.Level.LOW,
                enums.Level.HIGH,
                enums.Stance.SUPPORT,
            ),
        ):
            person = Stakeholder.objects.create(
                name=f"{MARK} {name}",
                stakeholder_type=kind,
                influence=influence,
                interest=interest,
                stance=stance,
            )
            person.assets.add(
                assets["05"] if stance == enums.Stance.OPPOSE else assets["04"]
            )
            StakeholderEngagement.objects.create(
                stakeholder=person,
                summary="Sosialisasi rencana penataan kawasan.",
                method=enums.EngagementMethod.SOCIALIZATION,
                follow_up="Pertemuan lanjutan",
                follow_up_date=timezone.localdate() + datetime.timedelta(days=14),
            )

    def _finance(self, assets):
        for asset in assets.values():
            valuation = AssetValuation.objects.create(
                asset=asset,
                method=enums.ValuationMethod.NJOP,
                land_value_per_m2=asset.njop_per_m2,
            )
            if asset.code.endswith("01"):
                ValuationItem.objects.create(
                    valuation=valuation,
                    description="Gedung kantor 2 lantai",
                    quantity=Decimal(600),
                    unit_value=Decimal(3500000),
                )
                valuation.recompute()
            TaxObligation.objects.create(
                asset=asset,
                tax_type=enums.TaxType.PBB,
                rate_percent=Decimal("0.3"),
                due_date=timezone.localdate() + datetime.timedelta(days=20),
                reference=f"SPPT-{asset.code}",
            )
        lease_asset = assets["03"]
        for months, kind, amount in (
            (3, enums.TransactionType.LEASE_INCOME, 45000000),
            (2, enums.TransactionType.SURVEY, 12500000),
            (1, enums.TransactionType.LEGAL, 30000000),
        ):
            LandTransaction.objects.create(
                asset=(
                    lease_asset
                    if kind == enums.TransactionType.LEASE_INCOME
                    else assets["05"]
                ),
                transaction_type=kind,
                amount=Decimal(amount),
                date=timezone.localdate() - datetime.timedelta(days=30 * months),
                counterparty=(
                    "Koperasi Nelayan Contoh"
                    if kind == enums.TransactionType.LEASE_INCOME
                    else "Penyedia contoh"
                ),
                description=f"{MARK} {enums.TransactionType(kind).label}",
            )

    def _legal(self, assets):
        advocate = Advocate.objects.create(
            name=f"{MARK} Biro Hukum Internal", is_internal=True
        )
        case = LegalCase.objects.create(
            title=f"{MARK} Gugatan kepemilikan bidang Pasir Panjang",
            court_case_number="12/Pdt.G/2026/PN Btm",
            case_type=enums.CaseType.CIVIL,
            court=enums.Court.PN,
            court_name="Pengadilan Negeri (contoh)",
            our_position=enums.CasePosition.DEFENDANT,
            opposing_party="Ahli waris Contoh Bin Fiktif",
            status=enums.CaseStatus.ONGOING,
            filed_date=timezone.localdate() - datetime.timedelta(days=90),
            claim_value=Decimal(1500000000),
            disputed_area_m2=assets["05"].area_m2,
        )
        case.assets.add(assets["05"])
        case.advocates.add(advocate)
        CaseHearing.objects.create(
            case=case,
            agenda="Pembuktian surat",
            scheduled_at=timezone.now() + datetime.timedelta(days=5),
            location="Ruang sidang 2",
        )
        CaseHearing.objects.create(
            case=case,
            agenda="Mediasi",
            result="Mediasi tidak berhasil.",
            scheduled_at=timezone.now() - datetime.timedelta(days=30),
        )
        return case

    def _encroachment(self, assets, case):
        asset = assets["02"]
        lon, lat = asset.geometry.centroid.coords
        encroachment = EncroachmentCase.objects.create(
            title=f"{MARK} Bangunan semi permanen di tanah cadangan",
            asset=asset,
            detected_on=timezone.localdate() - datetime.timedelta(days=75),
            detection_method=enums.DetectionMethod.SATELLITE,
            location=Point(lon, lat, srid=4326),
            area_geometry=_square(lon - 0.0004, lat - 0.0004, 0.0008),
            structure_type=enums.StructureType.SEMI,
            encroacher_name="Belum diketahui",
            occupant_count=3,
            severity=enums.Level.HIGH,
        )
        EncroachmentActionLog.objects.create(
            case=encroachment,
            action=enums.EncroachmentAction.VERIFICATION,
            date=timezone.localdate() - datetime.timedelta(days=70),
            description="Verifikasi lapangan, bangunan dihuni 3 KK.",
        )
        EncroachmentActionLog.objects.create(
            case=encroachment,
            action=enums.EncroachmentAction.WARNING_1,
            date=timezone.localdate() - datetime.timedelta(days=60),
            letter_number="ST-1/CONTOH/2026",
        )
        Task.objects.create(
            title=f"{MARK} Siapkan surat teguran kedua",
            task_type=enums.TaskType.LEGAL,
            priority=enums.Priority.HIGH,
            encroachment=encroachment,
            legal_case=case,
            start_date=timezone.localdate() - datetime.timedelta(days=10),
            due_date=timezone.localdate() - datetime.timedelta(days=2),
            progress=50,
            status=enums.TaskStatus.IN_PROGRESS,
        )

    def _operations(self, assets):
        survey_task = Task.objects.create(
            title=f"{MARK} Pengukuran ulang batas tanah cadangan",
            task_type=enums.TaskType.SURVEY,
            asset=assets["02"],
            start_date=timezone.localdate(),
            due_date=timezone.localdate() + datetime.timedelta(days=21),
            status=enums.TaskStatus.NEW,
        )
        Task.objects.create(
            title=f"{MARK} Pemasangan patok batas",
            task_type=enums.TaskType.MAINTENANCE,
            asset=assets["02"],
            depends_on=survey_task,
            start_date=timezone.localdate() + datetime.timedelta(days=22),
            due_date=timezone.localdate() + datetime.timedelta(days=35),
        )
        SurveyRequest.objects.create(
            survey_type=enums.SurveyType.BOUNDARY,
            asset=assets["02"],
            purpose=f"{MARK} Rekonstruksi batas untuk penyelesaian okupasi",
            status=enums.SurveyStatus.SCHEDULED,
            scheduled_date=timezone.localdate() + datetime.timedelta(days=7),
            vendor="KJSB Contoh",
            cost=Decimal(12500000),
        )
        LiaisonActivity.objects.create(
            subject=f"{MARK} Permohonan penerbitan HPL tanah cadangan",
            agency="Kantor Pertanahan (contoh)",
            asset=assets["02"],
            status=enums.LiaisonStatus.SUBMITTED,
            submitted_on=timezone.localdate() - datetime.timedelta(days=40),
            next_follow_up=timezone.localdate(),
        )
        site = ResettlementSite.objects.create(
            name=f"{MARK} Kawasan Permukiman Tanjung",
            asset=assets["04"],
            geometry=assets["04"].geometry,
            address="Sembulang, Galang",
            facilities="Masjid, sekolah dasar, puskesmas pembantu",
        )
        lon, lat = assets["04"].geometry.extent[:2]
        statuses = (
            [enums.ResettlementUnitStatus.OCCUPIED] * 3
            + [enums.ResettlementUnitStatus.ASSIGNED] * 2
            + [enums.ResettlementUnitStatus.BUILDING] * 2
            + [enums.ResettlementUnitStatus.VACANT] * 2
        )
        for index, status in enumerate(statuses):
            row, col = divmod(index, 3)
            ResettlementUnit.objects.create(
                site=site,
                unit_number=f"A-{index + 1:02d}",
                house_type="Tipe 45",
                status=status,
                geometry=_square(
                    lon + 0.0004 + col * 0.0009, lat + 0.0004 + row * 0.0009, 0.0007
                ),
            )

    def _public(self, assets):
        category = GrievanceCategory.objects.filter(
            name__startswith="Penyerobotan"
        ).first()
        Grievance.objects.create(
            complainant_name="Warga Contoh",
            phone="081200000000",
            category=category,
            subject=f"{MARK} Pemagaran liar di tanah cadangan",
            description="Ada pemagaran baru di sisi utara.",
            location_text="Rempang Cate",
            location=assets["02"].geometry.centroid,
            asset=assets["02"],
            channel=enums.GrievanceChannel.PHONE,
        )
        now = timezone.now()
        Tender.objects.create(
            title=f"{MARK} Seleksi mitra pengelola dermaga nelayan",
            method=enums.TenderMethod.BEAUTY_CONTEST,
            asset=assets["03"],
            description="Pemanfaatan dermaga untuk tempat pelelangan ikan selama 5 tahun.",
            requirements="Badan usaha/koperasi berbadan hukum, berpengalaman di bidang perikanan.",
            reserve_price=Decimal(150000000),
            open_at=now - datetime.timedelta(days=1),
            close_at=now + datetime.timedelta(days=14),
            status=enums.TenderStatus.ANNOUNCED,
        )
        share = MapShare.objects.create(
            title=f"{MARK} Peta aset Rempang untuk rapat koordinasi"
        )
        share.assets.set(assets.values())
