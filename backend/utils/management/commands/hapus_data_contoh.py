from django.core.management import call_command
from django.core.management.base import BaseCommand

# Urutan penting: data yang merujuk lahan/akun contoh dihapus lebih dahulu.
# Akun contoh (beserta permintaan investasi investor contoh) dihapus sebelum
# lahan contoh, karena permintaan itu merujuk lahan contoh.
SAMPLE_COMMANDS = (
    "dokumen_contoh_rempang",
    "operasi_contoh_rempang",
    "asetlahan_contoh_rempang",
    "pengadaan_contoh_rempang",
    "pengguna_contoh",
    "alokasi_contoh_rempang",
)


class Command(BaseCommand):
    help = (
        "Hapus semua data contoh (dokumen, pusat komando, aset, pengadaan, alokasi) "
        "dan akun contoh sebelum SimLahan dibuka untuk publik. Data kerja nyata "
        "tidak disentuh."
    )

    def handle(self, *args, **options):
        for command in SAMPLE_COMMANDS:
            self.stdout.write(f"{command} --hapus")
            call_command(command, "--hapus", stdout=self.stdout, stderr=self.stderr)
