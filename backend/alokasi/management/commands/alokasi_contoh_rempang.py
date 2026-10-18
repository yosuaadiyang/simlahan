"""Data contoh lahan alokasi di Pulau Rempang (fiktif, untuk uji coba portal).

python manage.py alokasi_contoh_rempang          # buat/perbarui
python manage.py alokasi_contoh_rempang --hapus  # hapus lahan contoh yang belum dimohonkan
"""

from decimal import Decimal

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.management.base import BaseCommand
from django.db import transaction

from alokasi import enums
from alokasi.importers import area_m2
from alokasi.models import LandPlot

PREFIX = "CONTOH-RMP-"

# (kode, nama, jenis, lon, lat, ukuran derajat, kecamatan, kelurahan, arahan, tarif UWT/m²/tahun)
PLOTS = [
    (
        "01",
        "Kawasan Industri Rempang Blok A",
        "reguler",
        104.150,
        0.830,
        0.004,
        "Galang",
        "Rempang Cate",
        "Industri",
        1500,
    ),
    (
        "02",
        "Kawasan Industri Rempang Blok B",
        "reguler",
        104.156,
        0.830,
        0.003,
        "Galang",
        "Rempang Cate",
        "Industri",
        1500,
    ),
    (
        "03",
        "Kawasan Pariwisata Pantai Rempang",
        "terbuka",
        104.205,
        0.815,
        0.003,
        "Galang",
        "Sembulang",
        "Pariwisata",
        2000,
    ),
    (
        "04",
        "Kawasan Pergudangan dan Logistik",
        "reguler",
        104.140,
        0.860,
        0.0025,
        "Galang",
        "Rempang Cate",
        "Pergudangan",
        1200,
    ),
    (
        "05",
        "Fasilitas Umum dan Sosial",
        "langsung",
        104.175,
        0.845,
        0.0015,
        "Galang",
        "Sembulang",
        "Fasilitas umum",
        0,
    ),
    (
        "06",
        "Kawasan Perdagangan dan Jasa",
        "terbuka",
        104.165,
        0.800,
        0.002,
        "Galang",
        "Sembulang",
        "Perdagangan dan jasa",
        1800,
    ),
]


class Command(BaseCommand):
    help = "Buat atau hapus data contoh lahan alokasi Pulau Rempang (fiktif)"

    def add_arguments(self, parser):
        parser.add_argument("--hapus", action="store_true", help="Hapus lahan contoh")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["hapus"]:
            plots = LandPlot.objects.filter(
                code__startswith=PREFIX, applications__isnull=True
            )
            count = plots.count()
            plots.delete()
            self.stdout.write(self.style.SUCCESS(f"{count} lahan contoh dihapus."))
            return
        created = 0
        for code, name, kind, lon, lat, size, district, village, use, rate in PLOTS:
            geom = MultiPolygon(
                Polygon(
                    (
                        (lon, lat),
                        (lon + size, lat),
                        (lon + size, lat + size),
                        (lon, lat + size),
                        (lon, lat),
                    )
                ),
                srid=4326,
            )
            is_open = kind == enums.AllocationType.OPEN
            plot, was_created = LandPlot.objects.update_or_create(
                code=f"{PREFIX}{code}",
                defaults={
                    "name": f"{name} (CONTOH)",
                    "allocation_type": kind,
                    "district": district,
                    "village": village,
                    "area_m2": area_m2(geom),
                    "zoning": use,
                    "intended_use": use,
                    "uwt_rate_per_m2_year": Decimal(rate),
                    "has_technical_documents": is_open,
                    "land_preparation_done": is_open,
                    "description": "Data fiktif untuk uji coba portal. Hapus dengan --hapus.",
                    "geometry": geom,
                    "is_published": True,
                },
            )
            created += was_created
        self.stdout.write(
            self.style.SUCCESS(
                f"{created} lahan contoh dibuat, {len(PLOTS) - created} diperbarui."
            )
        )
