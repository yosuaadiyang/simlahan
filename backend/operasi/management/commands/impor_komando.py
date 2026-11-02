"""Pindahkan seluruh data sistem pusat komando lama ke SimLahan.

Contoh (di server, di dalam kontainer backend)::

    python manage.py impor_komando /tmp/komando.dump --coba
    python manage.py impor_komando /tmp/komando.dump --sandi-awal /tmp/sandi.csv

``--coba`` menjalankan seluruh impor lalu membatalkannya, sehingga laporan
dapat diperiksa tanpa mengubah apa pun. Impor boleh diulang: baris yang sudah
dipindahkan tidak dibuat dua kali.
"""

import logging
import os

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from operasi.legacy_import import LegacyImporter
from operasi.pgdump import Dump, DumpError


class Command(BaseCommand):
    help = (
        "Impor data sistem pusat komando lama (cadangan pg_dump Supabase: .dump "
        "atau .sql) ke modul komando SimLahan. Aman diulang."
    )

    def add_arguments(self, parser):
        parser.add_argument("berkas", help="Berkas cadangan (.dump atau .sql)")
        parser.add_argument(
            "--coba",
            "--dry-run",
            dest="coba",
            action="store_true",
            help="Jalankan lalu batalkan semua perubahan; hanya tampilkan laporan.",
        )
        parser.add_argument(
            "--perbarui",
            action="store_true",
            help="Timpa data yang sudah pernah diimpor dengan isi cadangan.",
        )
        parser.add_argument(
            "--sertakan-uji",
            action="store_true",
            help="Ikut impor akun uji coba sistem lama (nama diawali 'UJI').",
        )
        parser.add_argument(
            "--sandi-awal",
            metavar="CSV",
            help=(
                "Buat sandi acak untuk petugas aktif yang belum punya sandi dan "
                "tulis ke berkas CSV ini (hanya dapat dibaca pemilik)."
            ),
        )

    def handle(self, *args, **options):
        path = options["berkas"]
        if not os.path.isfile(path):
            raise CommandError(f"Berkas tidak ditemukan: {path}")
        password_file = options["sandi_awal"]
        if password_file:
            folder = os.path.dirname(os.path.abspath(password_file))
            if not os.path.isdir(folder):
                raise CommandError(f"Folder untuk berkas sandi tidak ada: {folder}")
            if os.path.exists(password_file):
                raise CommandError(
                    f"Berkas sandi {password_file} sudah ada; pakai nama lain agar "
                    "sandi lama tidak tertimpa."
                )
        dry_run = options["coba"]
        # Poligon tidak sah di data lama diperbaiki otomatis; catatan GEOS-nya
        # hanya mengotori laporan.
        gis_logger = logging.getLogger("django.contrib.gis")
        level = gis_logger.level
        gis_logger.setLevel(logging.ERROR)
        try:
            with Dump(path) as dump:
                importer = LegacyImporter(
                    dump,
                    update=options["perbarui"],
                    include_test=options["sertakan_uji"],
                    dry_run=dry_run,
                    password_file=None if dry_run else password_file,
                    log=lambda message: self.stdout.write(message),
                )
                report = importer.run()
        except DumpError as error:
            raise CommandError(f"Berkas cadangan tidak dapat dibaca: {error}")
        except ValidationError as error:
            raise CommandError(" ".join(error.messages))
        finally:
            gis_logger.setLevel(level)
        self._print(report, dry_run, password_file)

    def _print(self, report, dry_run, password_file):
        write = self.stdout.write
        write("")
        write(
            "LAPORAN IMPOR PUSAT KOMANDO"
            + (" (UJI COBA – DIBATALKAN)" if dry_run else "")
        )
        write("=" * 60)
        for table, counts in report.counts.items():
            parts = ", ".join(f"{key} {value}" for key, value in counts.items())
            write(f"{table}: {parts}")
            for reason, amount in report.reasons[table].most_common():
                write(f"    - dilewati {amount}: {reason}")
        if report.not_imported:
            write("")
            write("Tidak dipindahkan:")
            for table, count, reason in report.not_imported:
                write(f"  {table} ({count} baris): {reason}")
        if report.warnings:
            write("")
            write("Perhatian:")
            for message in dict.fromkeys(report.warnings):
                write(f"  - {message}")
        write("")
        if dry_run:
            write(
                self.style.WARNING(
                    "Uji coba selesai. Tidak ada data yang disimpan. Jalankan lagi "
                    "tanpa --coba untuk mengimpor."
                )
            )
            return
        if password_file and report.passwords:
            write(
                self.style.WARNING(
                    f"{len(report.passwords)} sandi awal ditulis ke {password_file}. "
                    "Bagikan ke petugas lewat jalur pribadi, lalu hapus berkasnya."
                )
            )
        elif password_file:
            write("Tidak ada petugas yang perlu sandi awal.")
        write(self.style.SUCCESS("Impor selesai."))
