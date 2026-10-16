"""Kirim ringkasan tenggat waktu pengadaan tanah yang terlewat / segera jatuh tempo.

Dijalankan harian lewat batchrun (lihat fixture) atau cron:
    python manage.py pengadaan_cek_tenggat --email
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import override

from pengadaan.deadlines import collect_deadlines


class Command(BaseCommand):
    help = "Laporkan tenggat pengadaan tanah yang terlewat atau segera jatuh tempo"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            action="store_true",
            help="Kirim email ke ketua pelaksana proyek dan grup Pelaksana Pengadaan",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=5,
            help="Ambang 'segera jatuh tempo' dalam hari kerja (bawaan 5)",
        )

    def handle(self, *args, **options):
        with override(settings.LANGUAGE_CODE):
            items = [
                d
                for d in collect_deadlines(soon_workdays=options["days"])
                if d.state in ("overdue", "due_soon")
            ]
            if not items:
                self.stdout.write(_("No overdue or upcoming deadlines."))
                return
            lines = []
            for d in items:
                state = _("OVERDUE") if d.state == "overdue" else _("due soon")
                parcel = f" / {d.parcel_number}" if d.parcel_number else ""
                lines.append(
                    f"[{state}] {d.due_date:%d-%m-%Y} {d.project_identifier}{parcel}: {d.title}"
                )
            body = "\n".join(lines)
            self.stdout.write(body)

            if not options["email"]:
                return
            from pengadaan.models import AcquisitionProject

            recipients = set(
                get_user_model()
                .objects.filter(is_active=True, groups__id=8)
                .exclude(email="")
                .values_list("email", flat=True)
            )
            chairs = AcquisitionProject.objects.filter(
                id__in={d.project_id for d in items}, executing_chair__isnull=False
            ).values_list("executing_chair__email", flat=True)
            recipients |= {e for e in chairs if e}
            if not recipients:
                self.stdout.write(_("No recipients with an email address."))
                return
            send_mail(
                subject=_("Land acquisition deadlines %(date)s")
                % {"date": timezone.localdate().strftime("%d-%m-%Y")},
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=sorted(recipients),
            )
            self.stdout.write(
                _("Email sent to %(count)s recipients.") % {"count": len(recipients)}
            )
