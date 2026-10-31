"""Rekap Excel pusat komando: kegiatan, ringkasan, absensi, dan tugas.

Hanya data yang boleh dilihat pengguna yang ikut terekap. Teks selalu ditulis
sebagai teks (bukan rumus) agar isi seperti ``=HYPERLINK(...)`` dari lapangan
tidak dijalankan Excel.
"""

import datetime
import io
from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext as _

from asetlahan import scope as aset_scope
from operasi import enums, geo, services, task_flow
from operasi.models import Activity, Attendance

MAX_ROWS = 20_000
MAX_DAYS = 366


def _name(user) -> str:
    if user is None:
        return ""
    return user.get_full_name() or user.get_username()


def parse_period(params) -> tuple[datetime.date, datetime.date]:
    from django.core.exceptions import ValidationError

    today = timezone.localdate()
    period = params.get("periode", "hari")
    if period == "minggu":
        return today - datetime.timedelta(days=6), today
    if period == "bulan":
        return today.replace(day=1), today
    if period == "rentang":
        try:
            start = datetime.date.fromisoformat(params.get("dari", ""))
            end = datetime.date.fromisoformat(params.get("sampai", ""))
        except ValueError:
            raise ValidationError({"dari": [_("Tanggal tidak sah.")]})
        if end < start:
            raise ValidationError(
                {"sampai": [_("Tanggal akhir sebelum tanggal awal.")]}
            )
        if (end - start).days >= MAX_DAYS:
            raise ValidationError({"sampai": [_("Rentang maksimal satu tahun.")]})
        return start, end
    return today, today


def attendance_scope(user):
    queryset = Attendance.objects.all()
    if aset_scope.sees_all(user):
        return queryset
    return queryset.filter(Q(user=user) | Q(user__in=services.team_users(user)))


class _Book:
    def __init__(self):
        import xlsxwriter

        self.buffer = io.BytesIO()
        self.workbook = xlsxwriter.Workbook(
            self.buffer, {"in_memory": True, "remove_timezone": True}
        )
        self.head = self.workbook.add_format(
            {"bold": True, "bg_color": "#DDEBF7", "border": 1}
        )
        self.title = self.workbook.add_format({"bold": True, "font_size": 12})
        self.bold = self.workbook.add_format({"bold": True})

    def write(self, sheet, row, col, value, fmt=None):
        if value is None or value == "":
            sheet.write_blank(row, col, None, fmt)
        elif isinstance(value, bool):
            sheet.write_string(row, col, _("Ya") if value else _("Tidak"), fmt)
        elif isinstance(value, (int, float, Decimal)):
            sheet.write_number(row, col, float(value), fmt)
        else:
            sheet.write_string(row, col, str(value)[:32_000], fmt)

    def table(self, name, headers, rows, widths=None):
        sheet = self.workbook.add_worksheet(name[:31])
        for col, header in enumerate(headers):
            sheet.write_string(0, col, header, self.head)
            width = (widths or {}).get(col) or max(10, min(40, len(header) + 4))
            sheet.set_column(col, col, width)
        count = 0
        for r, row in enumerate(rows, start=1):
            for c, value in enumerate(row):
                self.write(sheet, r, c, value)
            count = r
        sheet.freeze_panes(1, 0)
        sheet.autofilter(0, 0, max(count, 1), max(len(headers) - 1, 0))
        return sheet

    def close(self) -> bytes:
        self.workbook.close()
        return self.buffer.getvalue()


def _activities(user, start, end, korwil, activity_type):
    queryset = (
        geo.scoped(Activity.objects.all(), user)
        .filter(started_at__date__gte=start, started_at__date__lte=end)
        .select_related("korwil", "reported_by")
        .prefetch_related("residents")
        .annotate(photo_count=Count("photos", distinct=True))
        .order_by("started_at", "pk")
    )
    if korwil is not None:
        queryset = queryset.filter(korwil=korwil)
    if activity_type:
        queryset = queryset.filter(activity_type=activity_type)
    return list(queryset[:MAX_ROWS])


def _activity_rows(activities):
    for i, a in enumerate(activities, start=1):
        moment = timezone.localtime(a.started_at)
        residents = list(a.residents.all())
        yield [
            i,
            a.number,
            moment.date().isoformat(),
            moment.strftime("%H:%M"),
            a.korwil.code if a.korwil_id else "",
            a.get_activity_type_display(),
            a.title,
            _name(a.reported_by),
            a.companion,
            a.location_name,
            ", ".join(r.head_name for r in residents),
            ", ".join(sorted({r.get_stance_display() for r in residents})),
            a.description,
            a.outcome,
            a.effort_points,
            a.impact_tier and enums.ImpactTier(a.impact_tier).label,
            a.photo_count,
            round(a.location.y, 6) if a.location else "",
            round(a.location.x, 6) if a.location else "",
            a.verified,
        ]


def _summary_sheet(book, user, start, end, activities, korwil, activity_type):
    sheet = book.workbook.add_worksheet(_("Ringkasan"))
    sheet.set_column(0, 0, 34)
    sheet.set_column(1, 2, 14)
    row = 0
    book.write(
        sheet,
        row,
        0,
        _("Rekap periode %(start)s s/d %(end)s")
        % {"start": start.isoformat(), "end": end.isoformat()},
        book.title,
    )
    row += 1
    filters = [
        _("Korwil: %(k)s") % {"k": korwil.code if korwil else _("semua")},
        _("Jenis: %(j)s")
        % {
            "j": (
                enums.ActivityType(activity_type).label if activity_type else _("semua")
            )
        },
        _("Dibuat oleh %(name)s, %(at)s")
        % {"name": _name(user), "at": timezone.localtime().strftime("%d-%m-%Y %H:%M")},
    ]
    for line in filters:
        book.write(sheet, row, 0, line)
        row += 1
    groups = (
        (_("PER KORWIL"), lambda a: a.korwil.code if a.korwil_id else "—"),
        (_("PER JENIS KEGIATAN"), lambda a: a.get_activity_type_display()),
        (_("PER PETUGAS"), lambda a: _name(a.reported_by) or "—"),
    )
    for title, key in groups:
        counts = defaultdict(int)
        points = defaultdict(Decimal)
        for activity in activities:
            counts[key(activity)] += 1
            points[key(activity)] += activity.effort_points
        row += 1
        book.write(sheet, row, 0, title, book.head)
        book.write(sheet, row, 1, _("Jumlah"), book.head)
        book.write(sheet, row, 2, _("Poin usaha"), book.head)
        ordered = sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))
        for label, count in ordered:
            row += 1
            book.write(sheet, row, 0, label)
            book.write(sheet, row, 1, count)
            book.write(sheet, row, 2, points[label])
        row += 1
    row += 1
    book.write(sheet, row, 0, _("TOTAL KEGIATAN"), book.bold)
    book.write(sheet, row, 1, len(activities), book.bold)
    book.write(
        sheet,
        row,
        2,
        sum((a.effort_points for a in activities), Decimal("0")),
        book.bold,
    )
    if len(activities) >= MAX_ROWS:
        row += 2
        book.write(
            sheet,
            row,
            0,
            _("Catatan: hanya %(n)d kegiatan pertama yang terekap; persempit periode.")
            % {"n": MAX_ROWS},
        )


def _attendance_rows(user, start, end, korwil):
    queryset = (
        attendance_scope(user)
        .filter(date__gte=start, date__lte=end)
        .select_related("user", "korwil")
        .order_by("date", "user__first_name", "user__username")
    )
    if korwil is not None:
        queryset = queryset.filter(korwil=korwil)
    for i, a in enumerate(queryset[:MAX_ROWS], start=1):
        yield [
            i,
            a.date.isoformat(),
            _name(a.user),
            a.get_status_display(),
            (
                timezone.localtime(a.check_in_at).strftime("%H:%M")
                if a.check_in_at
                else ""
            ),
            (
                timezone.localtime(a.check_out_at).strftime("%H:%M")
                if a.check_out_at
                else ""
            ),
            a.korwil.code if a.korwil_id else "",
            a.get_approval_display() if a.approval else "",
            a.note,
        ]


def _task_rows(user, start, end, korwil):
    queryset = task_flow.visible_tasks(user).filter(
        Q(created_at__date__gte=start, created_at__date__lte=end)
        | Q(due_date__gte=start, due_date__lte=end)
        | Q(completed_date__gte=start, completed_date__lte=end)
    )
    if korwil is not None:
        queryset = queryset.filter(korwil=korwil)
    for i, t in enumerate(queryset.order_by("due_date", "pk")[:MAX_ROWS], start=1):
        yield [
            i,
            t.number,
            t.title,
            _name(t.assignee),
            _name(t.created_by),
            t.korwil.code if t.korwil_id else "",
            t.get_activity_type_display() if t.activity_type else "",
            t.get_priority_display(),
            t.get_status_display(),
            t.due_date.isoformat() if t.due_date else "",
            t.completed_date.isoformat() if t.completed_date else "",
            t.point_value,
        ]


def workbook(user, start, end, korwil=None, activity_type="") -> bytes:
    book = _Book()
    activities = _activities(user, start, end, korwil, activity_type)
    book.table(
        _("Rekap kegiatan"),
        [
            _("No"),
            _("Nomor"),
            _("Tanggal"),
            _("Jam"),
            _("Korwil"),
            _("Jenis kegiatan"),
            _("Judul"),
            _("Petugas"),
            _("Pendamping"),
            _("Lokasi"),
            _("Warga"),
            _("Sikap warga"),
            _("Narasi"),
            _("Hasil & tindak lanjut"),
            _("Poin usaha"),
            _("Tingkat dampak"),
            _("Foto"),
            _("Lintang"),
            _("Bujur"),
            _("Diverifikasi"),
        ],
        _activity_rows(activities),
        widths={0: 5, 6: 30, 7: 22, 10: 30, 12: 50, 13: 40},
    )
    _summary_sheet(book, user, start, end, activities, korwil, activity_type)
    if user.has_perm("operasi.view_attendance"):
        book.table(
            _("Absensi"),
            [
                _("No"),
                _("Tanggal"),
                _("Petugas"),
                _("Status"),
                _("Masuk"),
                _("Pulang"),
                _("Korwil"),
                _("Persetujuan"),
                _("Keterangan"),
            ],
            _attendance_rows(user, start, end, korwil),
            widths={0: 5, 2: 24, 8: 40},
        )
    if user.has_perm("asetlahan.view_task"):
        book.table(
            _("Tugas"),
            [
                _("No"),
                _("Nomor"),
                _("Judul"),
                _("Penerima"),
                _("Pemberi"),
                _("Korwil"),
                _("Jenis kegiatan"),
                _("Prioritas"),
                _("Status"),
                _("Tenggat"),
                _("Selesai"),
                _("Nilai poin"),
            ],
            _task_rows(user, start, end, korwil),
            widths={0: 5, 2: 36, 3: 22, 4: 22},
        )
    return book.close()
