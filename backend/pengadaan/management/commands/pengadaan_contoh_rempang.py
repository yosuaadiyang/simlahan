"""Buat (atau hapus) DATA CONTOH proyek pengadaan tanah Pulau Rempang.

Data ini fiktif dan hanya untuk uji coba/peragaan: nama pihak, nomor bidang,
luas, dan batas bidang bukan hasil pengukuran. Geometri hanya ilustrasi kasar
di bagian tengah Pulau Rempang (Kec. Galang, Kota Batam).

    python manage.py pengadaan_contoh_rempang          # buat (idempoten)
    python manage.py pengadaan_contoh_rempang --hapus  # hapus permanen

Proyek contoh dikenali dari namanya (SAMPLE_PROJECT_NAME). `--hapus` menghapus
proyek itu beserta SELURUH data di bawahnya, termasuk yang ditambahkan manual.
"""

from decimal import Decimal
from typing import Any

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from safedelete.config import HARD_DELETE

from leasing.models import District, Municipality
from pengadaan import enums
from pengadaan.models import AcquisitionParcel, AcquisitionProject, EntitledParty

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

        self.stdout.write(
            self.style.SUCCESS(
                f"Proyek contoh Rempang dibuat: {project.identifier} "
                f"dengan {len(PARCELS)} bidang."
            )
        )
