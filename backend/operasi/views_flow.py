"""API pusat komando: tugas, laporan harian berjenjang, persetujuan, rekap."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _

from asetlahan import enums as aset_enums
from asetlahan.field_views import _parse_location
from operasi import (
    approvals,
    daily_reports,
    enums,
    hierarchy,
    recap,
    services,
    task_flow,
)
from operasi.models import TaskEvent
from operasi.views import _ids, _local, _name, api, file_url

# --------------------------------------------------------------------------
# Tugas
# --------------------------------------------------------------------------

TASK_FILTERS = ("saya", "tim", "verifikasi", "terlambat", "semua")


def _person(user) -> dict:
    return {
        "id": user.pk,
        "name": _name(user),
        "position": hierarchy.position_of(user),
    }


def _task_json(task, user, last=None) -> dict:
    stage = task_flow.stage(task, last)
    worker = task_flow.worker_id(task)
    return {
        "id": task.pk,
        "number": task.number,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "status_label": task.get_status_display(),
        "stage": stage,
        "stage_label": enums.TaskStage(stage).label,
        "stage_color": enums.TASK_STAGE_COLORS[stage],
        "priority": task.priority,
        "priority_label": task.get_priority_display(),
        "activity_type": task.activity_type,
        "activity_label": (
            task.get_activity_type_display() if task.activity_type else ""
        ),
        "points": task.point_value,
        "due_date": task.due_date.isoformat() if task.due_date else "",
        "progress": task.progress,
        "overdue": task.is_overdue,
        "korwil": task.korwil.code if task.korwil_id else "",
        "assignee": _name(task.assignee) if task.assignee_id else "",
        "giver": _name(task.created_by) if task.created_by_id else "",
        "mine": worker == user.pk,
        "given": task.created_by_id == user.pk,
        "actions": task_flow.allowed_actions(user, task),
        "can_cancel": task_flow.can_cancel(user, task),
    }


def _last_events(tasks) -> dict:
    last = {}
    for event in TaskEvent.objects.filter(task__in=tasks).order_by(
        "task_id", "-created_at", "-pk"
    ):
        last.setdefault(event.task_id, event)
    return last


def _filtered_tasks(user, name):
    queryset = task_flow.visible_tasks(user)
    open_statuses = aset_enums.OPEN_TASK_STATUSES
    if name == "saya":
        # Termasuk tugas wilayah tanpa penerima yang dikerjakan koordinatornya.
        queryset = queryset.filter(
            Q(assignee=user)
            | Q(created_by=user)
            | Q(contributors=user)
            | Q(assignee__isnull=True, korwil__coordinator=user)
        ).filter(status__in=open_statuses)
    elif name == "verifikasi":
        return approvals.task_queue(user)
    elif name == "terlambat":
        queryset = queryset.filter(
            status__in=open_statuses, due_date__lt=timezone.localdate()
        )
    elif name == "tim":
        queryset = queryset.filter(status__in=open_statuses)
    return list(queryset.distinct().order_by("due_date", "-priority", "pk")[:200])


@api(permission="asetlahan.view_task", methods=("GET", "POST"))
def tasks(request):
    user = request.user
    if request.method == "POST":
        task = task_flow.create_task(user, request.POST)
        return JsonResponse(_task_json(task, user), status=201)
    name = request.GET.get("filter", "saya")
    if request.GET.get("status") == "semua":
        name = "semua"
    if name not in TASK_FILTERS:
        name = "saya"
    items = _filtered_tasks(user, name)
    last = _last_events(items)
    return JsonResponse(
        {
            "results": [_task_json(t, user, last.get(t.pk)) for t in items],
            "can_create": user.has_perm("asetlahan.add_task")
            and task_flow.assignable_users(user).exists(),
        }
    )


@api(permission="asetlahan.add_task")
def task_assignees(request):
    return JsonResponse(
        {
            "results": [
                _person(u) for u in task_flow.assignable_users(request.user)[:500]
            ]
        }
    )


def _event_json(event) -> dict:
    return {
        "kind": event.kind,
        "label": event.get_kind_display(),
        "by": _name(event.actor),
        "note": event.note,
        "at": _local(event.created_at),
        "photo": file_url("tugas-foto", event) + "?lihat=1" if event.photo else "",
        "lat": event.location.y if event.location else None,
        "lng": event.location.x if event.location else None,
    }


@api(permission="asetlahan.view_task", methods=("GET", "POST"))
def task_detail(request, pk):
    user = request.user
    task = get_object_or_404(task_flow.visible_tasks(user), pk=pk)
    if request.method == "POST":
        if not user.has_perm("asetlahan.change_task"):
            raise PermissionDenied
        action = request.POST.get("aksi", "")
        if action:
            task = task_flow.transition(
                user,
                task,
                action,
                note=request.POST.get("catatan", ""),
                photo=request.FILES.get("foto"),
                location=_parse_location(request.POST),
            )
        if "progress" in request.POST:
            _update_progress(user, task, request.POST.get("progress"))
        task.refresh_from_db()
    events = list(task.komando_events.select_related("actor"))
    data = _task_json(task, user, events[0] if events else None)
    data["events"] = [_event_json(e) for e in events]
    data["contributors"] = [_name(u) for u in task.contributors.all()]
    data["points_awarded"] = [
        {"name": _name(p.user), "role": p.get_role_display(), "points": p.points}
        for p in task.komando_points.select_related("user")
    ]
    return JsonResponse(data)


def _update_progress(user, task, value):
    try:
        progress = int(value)
    except (TypeError, ValueError):
        progress = -1
    if not 0 <= progress <= 100:
        raise ValidationError({"progress": [_("Progres harus 0–100.")]})
    if task_flow.worker_id(task) != user.pk and not task_flow.can_verify(user, task):
        raise PermissionDenied
    if task.status not in aset_enums.OPEN_TASK_STATUSES:
        raise ValidationError({"progress": [_("Tugas sudah ditutup.")]})
    task.progress = progress
    task.save(update_fields=["progress", "modified_at"])


# --------------------------------------------------------------------------
# Laporan harian berjenjang
# --------------------------------------------------------------------------


def _report_summary(report, user) -> dict:
    return {
        "id": report.pk,
        "number": report.number,
        "date": report.report_date.isoformat(),
        "author": _name(report.author),
        "author_position": report.author_position,
        "korwil": report.korwil.code if report.korwil_id else "",
        "status": report.status,
        "status_label": report.get_status_display(),
        "excerpt": report.content[:240],
        "sent_at": _local(report.sent_at),
        "return_note": report.return_note,
        "returned_by": _name(report.returned_by) if report.returned_by_id else "",
        "mine": report.author_id == user.pk,
    }


def _activity_item(activity) -> dict:
    return {
        "id": activity.pk,
        "number": activity.number,
        "title": activity.title,
        "type_label": activity.get_activity_type_display(),
        "korwil": activity.korwil.code if activity.korwil_id else "",
        "at": _local(activity.started_at),
        "points": float(activity.effort_points),
    }


def _days(request) -> int:
    try:
        days = int(request.GET.get("hari", daily_reports.DEFAULT_DAYS))
    except ValueError:
        days = daily_reports.DEFAULT_DAYS
    return min(max(days, 1), daily_reports.MAX_DAYS)


@api(permission="operasi.view_dailyreport", methods=("GET", "POST"))
def daily_report_home(request):
    user = request.user
    if request.method == "POST":
        report = daily_reports.send(
            user,
            content=request.POST.get("isi", ""),
            activity_ids=_ids(request.POST.get("kegiatan")),
            report_ids=_ids(request.POST.get("laporan")),
            files=request.FILES.getlist("lampiran"),
            ai_generated=request.POST.get("ai") == "1",
        )
        return JsonResponse(
            {
                **_report_summary(report, user),
                "recipient": _name(report.recipient),
            },
            status=201,
        )
    supervisor = hierarchy.supervisor_of(user)
    subordinates = (
        get_user_model()
        .objects.filter(pk__in=hierarchy.direct_subordinate_ids(user))
        .order_by("first_name", "username")
    )
    return JsonResponse(
        {
            "supervisor": _person(supervisor) if supervisor else None,
            "position": hierarchy.position_of(user),
            "can_send": user.has_perm("operasi.add_dailyreport")
            and supervisor is not None,
            "can_finish": daily_reports.can_finish(user),
            "days": _days(request),
            "activities": [
                _activity_item(a)
                for a in daily_reports.pending_activities(user, _days(request))[:200]
            ],
            "inbox": [_report_summary(r, user) for r in daily_reports.inbox(user)],
            "revisions": [
                _report_summary(r, user) for r in daily_reports.revisions(user)
            ],
            "subordinates": [_person(u) for u in subordinates],
        }
    )


@api(permission="operasi.add_dailyreport", methods=("POST",))
def daily_report_compose(request):
    user = request.user
    activities = daily_reports.selected_activities(
        user, _ids(request.POST.get("kegiatan"))
    )
    reports = daily_reports.selected_reports(user, _ids(request.POST.get("laporan")))
    content, ai_used = daily_reports.compose(user, activities, reports)
    return JsonResponse({"content": content, "ai": ai_used})


@api(permission="operasi.change_dailyreport", methods=("POST",))
def daily_report_finish(request):
    count = daily_reports.mark_reviewed(request.user, _ids(request.POST.get("laporan")))
    return JsonResponse({"reviewed": count})


@api(permission="operasi.view_dailyreport")
def daily_report_trace(request):
    return JsonResponse({"results": daily_reports.trace(request.user)})


def _report_detail(report, user) -> dict:
    data = _report_summary(report, user)
    data.update(
        {
            "content": report.content,
            "ai_generated": report.ai_generated,
            "recipient": _name(report.recipient) if report.recipient_id else "",
            "position": daily_reports.position_text(daily_reports.chain(report)[-1]),
            "in_inbox": report.recipient_id == user.pk and report.in_inbox,
            "revision_owner": report.revision_owner_id == user.pk
            and report.status == enums.DailyReportStatus.RETURNED,
            "can_close": report.revision_owner_id == user.pk
            and report.author_id == user.pk
            and report.status == enums.DailyReportStatus.RETURNED
            and len(report.revision_stack) <= 1,
            "attachments": [
                {
                    "name": a.name or _("Lampiran"),
                    "url": file_url("laporan-lampiran", a) + "?lihat=1",
                }
                for a in report.attachments.all()
            ],
            "sources": [
                _report_summary(s, user)
                for s in report.sources.select_related("author", "korwil")
            ],
            "activities": [
                _activity_item(a) for a in report.activities.select_related("korwil")
            ],
            "events": [
                {
                    "label": e.get_action_display(),
                    "by": _name(e.actor),
                    "to": _name(e.target) if e.target_id else "",
                    "note": e.note,
                    "at": _local(e.created_at),
                }
                for e in report.events.select_related("actor", "target")
            ],
        }
    )
    return data


REPORT_ACTIONS = ("kembalikan", "teruskan", "perbaiki", "tutup")


@api(permission="operasi.view_dailyreport", methods=("GET", "POST"))
def daily_report_detail(request, pk, action=""):
    user = request.user
    report = get_object_or_404(daily_reports.visible_reports(user), pk=pk)
    if request.method == "POST":
        if action not in REPORT_ACTIONS or not user.has_perm(
            "operasi.change_dailyreport"
        ):
            raise PermissionDenied
        data = request.POST
        if action == "kembalikan":
            report = daily_reports.return_report(user, report, data.get("catatan"))
        elif action == "teruskan":
            report = daily_reports.delegate(
                user, report, data.get("bawahan", ""), data.get("catatan")
            )
        elif action == "perbaiki":
            report = daily_reports.revise(
                user, report, data.get("isi"), request.FILES.getlist("lampiran")
            )
        else:
            report = daily_reports.close(user, report)
    return JsonResponse(_report_detail(report, user))


# --------------------------------------------------------------------------
# Persetujuan & lencana
# --------------------------------------------------------------------------


@api()
def approval_queue(request):
    return JsonResponse(
        {
            "pending": approvals.pending(request.user),
            "history": approvals.history(request.user),
        }
    )


@api()
def badges(request):
    return JsonResponse(approvals.counts(request.user))


# --------------------------------------------------------------------------
# Rekap Excel
# --------------------------------------------------------------------------


@api(permission="operasi.view_activity")
def recap_excel(request):
    user = request.user
    start, end = recap.parse_period(request.GET)
    korwil = None
    if request.GET.get("korwil", "").isdigit():
        korwil = get_object_or_404(
            services.visible_korwils(user), pk=request.GET["korwil"]
        )
    activity_type = request.GET.get("jenis", "")
    if activity_type and activity_type not in enums.ActivityType.values:
        raise ValidationError({"jenis": [_("Jenis kegiatan tidak sah.")]})
    content = recap.workbook(user, start, end, korwil, activity_type)
    response = HttpResponse(
        content,
        content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
    filename = f"rekap-komando-{start:%Y%m%d}-{end:%Y%m%d}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
