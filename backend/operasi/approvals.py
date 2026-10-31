"""Antrian persetujuan pusat komando: semua yang menunggu keputusan pengguna.

Menggabungkan pengajuan izin, konfirmasi dampak tinggi, verifikasi tugas,
laporan harian masuk, dan laporan yang menunggu revisi, beserta riwayat
keputusan pengguna 30 hari terakhir.
"""

import datetime

from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

from asetlahan import enums as aset_enums
from asetlahan import scope as aset_scope
from operasi import daily_reports, enums, geo, hierarchy, services, task_flow
from operasi.models import Activity, Attendance, DailyReportEvent, TaskEvent

LIMIT = 100
HISTORY_DAYS = 30


def _name(user) -> str:
    if user is None:
        return "—"
    return user.get_full_name() or user.get_username()


def _local(moment) -> str:
    return timezone.localtime(moment).isoformat() if moment else ""


def can_confirm_impact(user, activity) -> bool:
    """Klaim dampak tinggi dikonfirmasi atasan pelapor (koordinator Korwil,
    rantai atasan, atau Administrator), tidak pernah oleh pelapornya."""
    if not activity.needs_impact_confirmation or activity.reported_by_id == user.pk:
        return False
    if not user.has_perm("operasi.change_activity"):
        return False
    if aset_scope.sees_all(user):
        return True
    if activity.korwil_id and activity.korwil.coordinator_id == user.pk:
        return True
    return bool(
        activity.reported_by_id and hierarchy.is_ancestor(user, activity.reported_by)
    )


def impact_queue(user):
    if not user.has_perm("operasi.change_activity"):
        return []
    queryset = (
        geo.scoped(Activity.objects.all(), user)
        .filter(
            activity_type=enums.ActivityType.OTHER,
            impact_confirmed=False,
            impact_scope__isnull=False,
            impact_risk__isnull=False,
            impact_result__isnull=False,
        )
        .exclude(reported_by=user)
        .select_related("korwil", "reported_by")
    )
    if not aset_scope.sees_all(user):
        queryset = queryset.filter(
            Q(korwil__coordinator=user)
            | Q(reported_by__in=hierarchy.descendant_ids(user))
        )
    return [
        a
        for a in queryset.order_by("started_at")[: LIMIT * 2]
        if can_confirm_impact(user, a)
    ][:LIMIT]


def task_queue(user):
    tasks = (
        task_flow.visible_tasks(user)
        .filter(status=aset_enums.TaskStatus.REPORTED)
        .order_by("due_date", "pk")
    )
    return [t for t in tasks[: LIMIT * 2] if task_flow.can_verify(user, t)][:LIMIT]


def pending(user) -> list[dict]:
    items = []
    if user.has_perm("operasi.view_attendance"):
        for record in services.leave_requests(user)[:LIMIT]:
            items.append(
                {
                    "kind": "izin",
                    "kind_label": _("Izin / cuti"),
                    "id": record.pk,
                    "title": f"{_name(record.user)}: {record.get_status_display()}",
                    "sub": record.date.strftime("%d-%m-%Y")
                    + (f" · {record.note[:120]}" if record.note else ""),
                    "at": _local(record.created_at),
                }
            )
    for activity in impact_queue(user):
        items.append(
            {
                "kind": "dampak",
                "kind_label": _("Konfirmasi dampak"),
                "id": activity.pk,
                "title": f"{activity.number} {activity.title}",
                "sub": " · ".join(
                    filter(
                        None,
                        [
                            _name(activity.reported_by),
                            str(enums.ImpactTier(activity.impact_tier).label),
                            (
                                _("Korwil %(c)s") % {"c": activity.korwil.code}
                                if activity.korwil_id
                                else ""
                            ),
                        ],
                    )
                ),
                "at": _local(activity.started_at),
            }
        )
    if user.has_perm("asetlahan.view_task"):
        for task in task_queue(user):
            items.append(
                {
                    "kind": "tugas",
                    "kind_label": _("Verifikasi tugas"),
                    "id": task.pk,
                    "title": f"{task.number} {task.title}",
                    "sub": " · ".join(
                        filter(
                            None,
                            [
                                _name(task.assignee),
                                (
                                    _("%(n)d poin") % {"n": task.point_value}
                                    if task.point_value
                                    else ""
                                ),
                            ],
                        )
                    ),
                    "at": _local(task.modified_at),
                }
            )
    if user.has_perm("operasi.view_dailyreport"):
        for report in daily_reports.inbox(user)[:LIMIT]:
            items.append(
                {
                    "kind": "laporan",
                    "kind_label": _("Laporan harian masuk"),
                    "id": report.pk,
                    "title": f"{report.number} {_name(report.author)}",
                    "sub": " · ".join(
                        filter(
                            None,
                            [
                                report.report_date.strftime("%d-%m-%Y"),
                                report.author_position,
                            ],
                        )
                    ),
                    "at": _local(report.sent_at),
                }
            )
        for report in daily_reports.revisions(user)[:LIMIT]:
            items.append(
                {
                    "kind": "revisi",
                    "kind_label": _("Revisi laporan"),
                    "id": report.pk,
                    "title": f"{report.number} {_name(report.author)}",
                    "sub": report.return_note[:160],
                    "at": _local(report.returned_at),
                }
            )
    return items


def history(user) -> list[dict]:
    since = timezone.now() - datetime.timedelta(days=HISTORY_DAYS)
    rows = []
    for event in TaskEvent.objects.filter(
        actor=user,
        created_at__gte=since,
        kind__in=[enums.TaskEventKind.VERIFIED, enums.TaskEventKind.REJECTED],
    ).select_related("task")[:LIMIT]:
        rows.append(
            {
                "kind": "tugas",
                "decision": event.get_kind_display(),
                "approved": event.kind == enums.TaskEventKind.VERIFIED,
                "title": f"{event.task.number} {event.task.title}",
                "note": event.note,
                "at": event.created_at,
            }
        )
    for event in DailyReportEvent.objects.filter(
        actor=user,
        created_at__gte=since,
        action__in=[
            enums.DailyReportAction.RETURNED,
            enums.DailyReportAction.REVIEWED,
        ],
    ).select_related("report__author")[:LIMIT]:
        rows.append(
            {
                "kind": "laporan",
                "decision": event.get_action_display(),
                "approved": event.action == enums.DailyReportAction.REVIEWED,
                "title": f"{event.report.number} {_name(event.report.author)}",
                "note": event.note,
                "at": event.created_at,
            }
        )
    for record in Attendance.objects.filter(
        approved_by=user, approved_at__gte=since
    ).select_related("user")[:LIMIT]:
        rows.append(
            {
                "kind": "izin",
                "decision": record.get_approval_display(),
                "approved": record.approval == enums.LeaveApproval.APPROVED,
                "title": f"{_name(record.user)}: {record.get_status_display()} "
                f"{record.date:%d-%m-%Y}",
                "note": "",
                "at": record.approved_at,
            }
        )
    for activity in Activity.objects.filter(
        impact_confirmed_by=user, impact_confirmed_at__gte=since
    )[:LIMIT]:
        rows.append(
            {
                "kind": "dampak",
                "decision": _("Dampak dikonfirmasi"),
                "approved": True,
                "title": f"{activity.number} {activity.title}",
                "note": "",
                "at": activity.impact_confirmed_at,
            }
        )
    rows.sort(key=lambda r: r["at"], reverse=True)
    for row in rows:
        row["at"] = _local(row["at"])
    return rows[:LIMIT]


def counts(user) -> dict:
    """Jumlah ringkas untuk lencana tab (dipanggil berkala, harus ringan)."""
    items = pending(user)
    return {
        "laporan": sum(1 for i in items if i["kind"] in ("laporan", "revisi")),
        "persetujuan": len(items),
        "tugas": sum(1 for i in items if i["kind"] == "tugas"),
    }
