"""Impor lahan dari berkas GeoJSON atau KML/KMZ.

python manage.py alokasi_impor_lahan lahan.geojson --jenis reguler --tampilkan
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from alokasi import enums
from alokasi.importers import PlotImportError, import_plots


class Command(BaseCommand):
    help = "Impor/perbarui data lahan alokasi dari GeoJSON atau KML/KMZ (Polygon/MultiPolygon, WGS84)"

    def add_arguments(self, parser):
        parser.add_argument("path", help="Berkas GeoJSON atau KML/KMZ")
        parser.add_argument(
            "--jenis",
            choices=enums.AllocationType.values,
            default=enums.AllocationType.REGULAR,
            help="Jenis alokasi bawaan bila tidak ada di properti fitur",
        )
        parser.add_argument(
            "--tampilkan",
            action="store_true",
            help="Langsung tampilkan lahan baru di portal",
        )

    def handle(self, *args, **options):
        try:
            with open(options["path"], "rb") as fp:
                data = fp.read()
        except OSError as error:
            raise CommandError(str(error))
        try:
            with transaction.atomic():
                created, updated = import_plots(
                    data,
                    filename=options["path"],
                    defaults={
                        "allocation_type": options["jenis"],
                        "is_published": options["tampilkan"],
                    },
                )
        except PlotImportError as error:
            raise CommandError(str(error))
        self.stdout.write(
            self.style.SUCCESS(f"{created} lahan baru, {updated} diperbarui.")
        )
