"""Pengingat tenggat modul aset lahan (dijadwalkan harian lewat batchrun).

Mendaftar sewa yang segera berakhir, hak atas tanah yang segera berakhir,
pajak jatuh tempo, sidang mendatang, tugas & pengaduan lewat tenggat, okupasi
tanpa tindak lanjut, dan urusan instansi yang perlu ditindaklanjuti.

Dengan --email: pengingat pribadi dikirim ke penanggung jawab (surel) dan
kuasa hukum (surel/WhatsApp; sekali per sidang), serta ringkasan ke setiap
anggota grup Petugas Aset Lahan dan Administrator. Ringkasan disusun per
penerima: hanya data unit layanannya dan jenis data yang boleh ia lihat.
"""

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.translation import gettext as _

from asetlahan import monitoring, services
from asetlahan.models import ModuleSettings
from utils.group_permissions import UserGroup


def _date(value) -> str:
    if value is None:
        return "-"
    if hasattr(value, "hour"):
        return timezone.localtime(value).strftime("%d-%m-%Y %H:%M")
    return value.strftime("%d-%m-%Y")


class Command(BaseCommand):
    help = (
        "Pengingat tenggat aset lahan: sewa, hak, pajak, sidang, tugas, pengaduan, "
        "okupasi, pemantauan lapangan, urusan instansi"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            action="store_true",
            help="Kirim pengingat (surel/WhatsApp) dan ringkasan",
        )

    # (izin melihat, metode bagian) — izin sama dengan peringatan di dasbor.
    SECTIONS = (
        ("leasing.view_lease", "_leases"),
        ("asetlahan.view_landasset", "_titles"),
        ("asetlahan.view_taxobligation", "_taxes"),
        ("asetlahan.view_casehearing", "_hearings"),
        ("asetlahan.view_task", "_tasks"),
        ("asetlahan.view_grievance", "_grievances"),
        ("asetlahan.view_encroachmentcase", "_encroachments"),
        ("asetlahan.view_landasset", "_monitoring"),
        ("asetlahan.view_liaisonactivity", "_liaisons"),
    )

    def handle(self, *args, **options):
        self.send = options["email"]
        self.config = ModuleSettings.load()
        self.personal = defaultdict(list)
        # Tanpa pengguna: seluruh data, untuk keluaran konsol & pengingat pribadi.
        lines = self._lines()
        for line in lines:
            self.stdout.write(line)
        if not self.send:
            return
        for email, items in self.personal.items():
            services.send_email(
                [email], _("Pengingat tenggat (%d)") % len(items), "\n".join(items)
            )
        for officer in services.officers(UserGroup.PETUGAS_ASET, UserGroup.PAAKAYTTAJA):
            own = self._lines(officer)
            if own:
                services.send_email(
                    [officer.email],
                    _("Ringkasan tenggat aset lahan (%d)") % len(own),
                    "\n".join(own)
                    + "\n\n"
                    + _("Dasbor: %s") % services.admin_url("dasbor/"),
                )
        self.stdout.write(self.style.SUCCESS(_("%d pengingat diproses.") % len(lines)))

    def _lines(self, user=None) -> list[str]:
        """Baris ringkasan; dengan ``user`` hanya data yang boleh dilihatnya."""
        lines = []
        for permission, method in self.SECTIONS:
            if user is not None and not user.has_perm(permission):
                continue
            lines.extend(getattr(self, method)(user))
        return lines

    def _remind(self, user, line: str) -> None:
        if user is not None and user.is_active and user.email:
            self.personal[user.email].append(line)

    def _leases(self, user=None):
        return [
            _("[SEWA BERAKHIR] %(lease)s – %(date)s")
            % {"lease": lease, "date": _date(lease.end_date)}
            for lease in monitoring.leases_ending(self.config.lease_alert_days, user)
        ]

    def _titles(self, user=None):
        lines = []
        for asset in monitoring.titles_expiring(
            self.config.title_alert_days, user
        ).select_related("responsible"):
            line = _(
                "[HAK BERAKHIR] %(code)s %(name)s – %(type)s %(number)s, %(date)s"
            ) % {
                "code": asset.code,
                "name": asset.name,
                "type": asset.get_title_type_display(),
                "number": asset.title_number,
                "date": _date(asset.title_expiry),
            }
            lines.append(line)
            if user is None:
                self._remind(asset.responsible, line)
        return lines

    def _taxes(self, user=None):
        if not self.config.enable_valuation:
            return []
        lines = []
        for tax in monitoring.taxes_due(
            self.config.tax_alert_days, user
        ).select_related("asset__responsible"):
            line = _("[PAJAK] %(asset)s – %(tax)s, jatuh tempo %(date)s") % {
                "asset": tax.asset.code,
                "tax": tax,
                "date": _date(tax.due_date),
            }
            lines.append(line)
            if user is None:
                self._remind(tax.asset.responsible, line)
        return lines

    def _hearings(self, user=None):
        if not self.config.enable_litigation:
            return []
        lines = []
        hearings = monitoring.hearings_upcoming(
            self.config.hearing_alert_days, user
        ).select_related("case__responsible")
        for hearing in hearings.prefetch_related("case__advocates"):
            case = hearing.case
            line = _(
                "[SIDANG] %(case)s %(number)s – %(agenda)s, %(date)s %(place)s"
            ) % {
                "case": case.number,
                "number": case.court_case_number,
                "agenda": hearing.agenda,
                "date": _date(hearing.scheduled_at),
                "place": hearing.location,
            }
            lines.append(line.strip())
            if user is not None or hearing.reminder_sent_at is not None:
                continue
            self._remind(case.responsible, line)
            if self.send:
                for advocate in case.advocates.all():
                    services.notify_contact(
                        email=advocate.email,
                        phone=advocate.phone,
                        subject=_("Pengingat sidang %s") % case.number,
                        body=line,
                    )
                hearing.reminder_sent_at = timezone.now()
                hearing.save(update_fields=["reminder_sent_at"])
        return lines

    def _tasks(self, user=None):
        if not self.config.enable_tasks:
            return []
        lines = []
        for task in monitoring.tasks_overdue(user):
            line = _("[TUGAS TERLAMBAT] %(number)s %(title)s – tenggat %(date)s") % {
                "number": task.number,
                "title": task.title,
                "date": _date(task.due_date),
            }
            lines.append(line)
            if user is None:
                self._remind(task.assignee, line)
        return lines

    def _grievances(self, user=None):
        if not self.config.enable_grievance:
            return []
        lines = []
        for grievance in monitoring.grievances_overdue(user).select_related(
            "assigned_to"
        ):
            line = _("[PENGADUAN] %(number)s %(subject)s – batas %(date)s") % {
                "number": grievance.number,
                "subject": grievance.subject,
                "date": _date(grievance.due_date),
            }
            lines.append(line)
            if user is None:
                self._remind(grievance.assigned_to, line)
        return lines

    def _encroachments(self, user=None):
        if not self.config.enable_encroachment:
            return []
        lines = []
        for case in monitoring.stale_encroachments(
            self.config.encroachment_followup_days, user
        ):
            line = _("[OKUPASI] %(number)s %(title)s – tindakan terakhir %(date)s") % {
                "number": case.number,
                "title": case.title,
                "date": _date(case.last_action),
            }
            lines.append(line)
            if user is None:
                self._remind(case.responsible, line)
        return lines

    def _monitoring(self, user=None):
        lines = []
        for asset in monitoring.monitoring_overdue(
            user, default_days=self.config.monitoring_interval_days
        ):
            line = _(
                "[PEMANTAUAN] %(code)s %(name)s – jadwal pemantauan lapangan %(date)s"
            ) % {
                "code": asset.code,
                "name": asset.name,
                "date": _date(asset.monitoring_due),
            }
            lines.append(line)
            if user is None:
                self._remind(asset.responsible, line)
        return lines

    def _liaisons(self, user=None):
        if not self.config.enable_survey:
            return []
        lines = []
        for item in monitoring.liaison_followups(user).select_related("officer"):
            line = _(
                "[URUSAN INSTANSI] %(subject)s (%(agency)s) – tindak lanjut %(date)s"
            ) % {
                "subject": item.subject,
                "agency": item.agency,
                "date": _date(item.next_follow_up),
            }
            lines.append(line)
            if user is None:
                self._remind(item.officer, line)
        return lines
