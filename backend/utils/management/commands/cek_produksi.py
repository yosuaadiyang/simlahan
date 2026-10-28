from django.core.management.base import BaseCommand, CommandError

from utils.production_check import FAIL, INFO, WARN, run_checks


class Command(BaseCommand):
    help = (
        "Periksa kesiapan sebelum dibuka untuk publik: pengaturan, surel, alamat "
        "publik, akun & data contoh, sandi admin awal. Keluar dengan kode 1 bila "
        "ada temuan GAGAL."
    )

    def handle(self, *args, **options):
        findings = run_checks()
        for finding in findings:
            style = {
                FAIL: self.style.ERROR,
                WARN: self.style.WARNING,
                INFO: self.style.NOTICE,
            }[finding.level]
            self.stdout.write(style(f"[{finding.level}] {finding.message}"))
        failed = sum(1 for f in findings if f.level == FAIL)
        warned = sum(1 for f in findings if f.level == WARN)
        if failed:
            raise CommandError(
                f"{failed} temuan GAGAL dan {warned} peringatan. Perbaiki sebelum "
                "dibuka untuk publik."
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Siap dibuka untuk publik ({warned} peringatan)."
                if warned
                else "Siap dibuka untuk publik."
            )
        )
