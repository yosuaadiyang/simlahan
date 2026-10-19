"""Rekap harian pusat komando (dijadwalkan lewat batchrun setiap 00.30 WIB).

- Absensi hari sebelumnya yang belum absen pulang ditandai "lupa absen pulang".
- Posisi Live yang tidak diperbarui lebih dari 24 jam dihapus.
"""

import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from operasi.models import Attendance, OfficerPosition


class Command(BaseCommand):
    help = "Tandai lupa absen pulang dan hapus posisi Live yang usang"

    def handle(self, *args, **options):
        today = timezone.localdate()
        marked = Attendance.objects.filter(
            date__lt=today,
            check_in_at__isnull=False,
            check_out_at__isnull=True,
            missing_checkout=False,
        ).update(missing_checkout=True)
        removed, _ = OfficerPosition.objects.filter(
            updated_at__lt=timezone.now() - datetime.timedelta(hours=24)
        ).delete()
        self.stdout.write(
            f"{marked} absensi ditandai lupa absen pulang, {removed} posisi Live usang dihapus."
        )
