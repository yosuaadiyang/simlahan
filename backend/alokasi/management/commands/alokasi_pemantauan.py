"""Pemantauan pasca-alokasi dan pengingat.

- Menandai alokasi yang masa berlakunya habis sebagai "Berakhir".
- Mendaftar lahan tidur (belum dibangun setelah batas waktu) dan alokasi yang
  terlambat melapor progres.
- Mendaftar tagihan yang segera/sudah jatuh tempo.

Dengan --email: pengingat dikirim ke pemegang alokasi/pemohon dan ringkasan
ke grup Petugas Alokasi Lahan. Dijadwalkan mingguan lewat batchrun.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from alokasi import monitoring, services
from utils.group_permissions import UserGroup


class Command(BaseCommand):
    help = "Pemantauan lahan tidur, kewajiban lapor, tagihan, dan masa berlaku alokasi"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email", action="store_true", help="Kirim pengingat dan ringkasan surel"
        )
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Ambang tagihan segera jatuh tempo (hari, bawaan 7)",
        )

    def handle(self, *args, **options):
        send = options["email"]
        expired = monitoring.expire_allocations()
        idle = list(
            monitoring.idle_queryset().select_related("holder", "holder__user", "plot")
        )
        overdue_reports = monitoring.overdue_report_allocations()
        invoices = list(monitoring.invoices_needing_payment(options["days"]))

        lines = []
        for a in expired:
            lines.append(
                _("[BERAKHIR] %(kpt)s %(holder)s – lahan %(plot)s") % self._a(a)
            )
        for a in idle:
            lines.append(
                _(
                    "[LAHAN TIDUR] %(kpt)s %(holder)s – lahan %(plot)s, batas %(deadline)s"
                )
                % self._a(a)
            )
            if send:
                services.notify(
                    a.holder,
                    _("Peringatan lahan tidur %s") % a.kpt_number,
                    _(
                        "Lahan %(plot)s (%(kpt)s) belum dibangun hingga batas %(deadline)s. "
                        "Lahan yang tidak dimanfaatkan dapat dicabut alokasinya. Segera mulai "
                        "pembangunan dan laporkan progresnya di %(url)s"
                    )
                    % {**self._a(a), "url": services.portal_url(f"alokasi/{a.pk}/")},
                )
        for a in overdue_reports:
            lines.append(
                _("[LAPORAN TERLAMBAT] %(kpt)s %(holder)s – lahan %(plot)s")
                % self._a(a)
            )
            if send:
                services.notify(
                    a.holder,
                    _("Pengingat laporan progres %s") % a.kpt_number,
                    _(
                        "Laporan progres perizinan dan pembangunan untuk %(kpt)s sudah jatuh tempo. "
                        "Kirim laporan di %(url)s"
                    )
                    % {**self._a(a), "url": services.portal_url(f"alokasi/{a.pk}/")},
                )
        for invoice in invoices:
            state = (
                _("LEWAT JATUH TEMPO")
                if invoice.is_overdue
                else _("SEGERA JATUH TEMPO")
            )
            lines.append(
                f"[{state}] {invoice.number} {invoice.application.applicant.name} "
                f"Rp{invoice.amount:,.0f} {invoice.due_date:%d-%m-%Y}".replace(",", ".")
            )
            if send:
                services.notify(
                    invoice.application.applicant,
                    _("Pengingat tagihan %s") % invoice.number,
                    _(
                        "Tagihan %(number)s sebesar Rp%(amount)s jatuh tempo %(due)s. Unggah bukti bayar di %(url)s"
                    )
                    % {
                        "number": invoice.number,
                        "amount": f"{invoice.amount:,.0f}".replace(",", "."),
                        "due": f"{invoice.due_date:%d-%m-%Y}",
                        "url": services.portal_url(
                            f"permohonan/{invoice.application.number}/"
                        ),
                    },
                )

        if not lines:
            self.stdout.write(_("Tidak ada temuan pemantauan."))
            return
        body = "\n".join(lines)
        self.stdout.write(body)
        if send:
            officers = (
                get_user_model()
                .objects.filter(is_active=True, groups__id=UserGroup.PETUGAS_ALOKASI)
                .exclude(email="")
                .values_list("email", flat=True)
                .distinct()
            )
            services.send_email(
                list(officers), _("Ringkasan pemantauan alokasi lahan"), body
            )

    @staticmethod
    def _a(allocation):
        return {
            "kpt": allocation.kpt_number,
            "holder": allocation.holder.name,
            "plot": allocation.plot.code,
            "deadline": f"{allocation.idle_deadline:%d-%m-%Y}",
        }
