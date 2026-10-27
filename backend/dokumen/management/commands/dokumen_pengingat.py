"""Tugas harian modul dokumen & perizinan.

- Dokumen perizinan terverifikasi yang lewat masa berlakunya menjadi
  "Kedaluwarsa" (pemegang hak diberi tahu).
- Peringatan sekali per tanggal kedaluwarsa bagi izin yang akan habis.
- Dokumen tanda tangan yang lewat batas waktu menjadi "Kedaluwarsa".
- Pengingat surel bagi penerima yang belum menandatangani.

Pemberitahuan di atas selalu dikirim. Dengan --email, ringkasan dikirim juga ke
petugas yang berhak memverifikasi. Dijadwalkan harian lewat batchrun.
"""

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from dokumen import enums, services, signing
from dokumen.access import users_with_perm
from dokumen.models import DocumentSettings, DownloadRequest, PermitRecord


class Command(BaseCommand):
    help = "Kedaluwarsa izin, peringatan masa berlaku, dan pengingat tanda tangan"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email", action="store_true", help="Kirim ringkasan harian ke petugas"
        )

    def handle(self, *args, **options):
        config = DocumentSettings.load()
        expired = services.expire_records()
        warned = services.warn_expiring(days=config.expiry_warning_days)
        documents = signing.expire_documents()
        reminded = signing.send_due_reminders()
        waiting = PermitRecord.objects.filter(
            status=enums.RecordStatus.SUBMITTED
        ).count()
        downloads = DownloadRequest.objects.filter(
            status=enums.DownloadStatus.PENDING
        ).count()
        lines = [
            _("Izin kedaluwarsa hari ini: %d") % len(expired),
            _("Peringatan masa berlaku terkirim: %d") % len(warned),
            _("Dokumen tanda tangan kedaluwarsa: %d") % len(documents),
            _("Pengingat penanda tangan terkirim: %d") % reminded,
            _("Dokumen menunggu verifikasi: %d") % waiting,
            _("Permintaan unduh menunggu persetujuan: %d") % downloads,
        ]
        lines += [f"- {r.land_use.number} {r.permit_type.name}" for r in expired]
        summary = "\n".join(lines)
        self.stdout.write(summary)
        if options["email"] and (expired or waiting or downloads or documents):
            recipients = users_with_perm("dokumen.verify_permitrecord").exclude(
                is_superuser=True
            )
            services.email_users(
                recipients, _("Ringkasan harian dokumen & perizinan"), summary
            )
