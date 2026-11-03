"""Perbarui blok role_guide.py di buku panduan per peran (docs/panduan/peran/).

cd backend && python manage.py panduan_buku          # tulis
cd backend && python manage.py panduan_buku --cek    # hanya periksa
"""

from django.core.management.base import BaseCommand, CommandError

from users.role_books import sync


class Command(BaseCommand):
    help = "Perbarui ringkasan peran di buku panduan per peran dari role_guide.py"

    def add_arguments(self, parser):
        parser.add_argument(
            "--cek",
            action="store_true",
            help="Hanya periksa; gagal bila ada buku yang belum diperbarui.",
        )

    def handle(self, *args, **options):
        changed = sync(write=not options["cek"])
        names = ", ".join(path.name for path in changed)
        if options["cek"]:
            if changed:
                raise CommandError(f"Buku belum diperbarui: {names}")
            self.stdout.write("Semua buku peran sesuai role_guide.py.")
        elif changed:
            self.stdout.write(f"Diperbarui: {names}")
        else:
            self.stdout.write("Tidak ada perubahan.")
