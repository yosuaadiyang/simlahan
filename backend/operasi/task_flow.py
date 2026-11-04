"""Siklus tugas pusat komando.

Tugas memakai model ``asetlahan.Task``. Pemberi tugas (atasan) membuat tugas
untuk bawahan, penerima memulai, melapor selesai dengan bukti (foto + GPS),
atau menandai terkendala; pemberi tugas / atasan penerima memverifikasi atau
mengembalikan untuk revisi. Poin KPI dibagikan saat tugas diverifikasi.
"""

import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.formats import number_format
from django.utils.translation import gettext as _

from asetlahan import enums as aset_enums
from asetlahan import scope as aset_scope
from asetlahan.models import Task
from operasi import enums, geo, hierarchy
from operasi.models import Korwil, TaskEvent, TaskPoint
from utils.group_permissions import UserGroup

MAX_CONTRIBUTORS = 20
MAX_NOTE = 2000

# Grup petugas yang dapat menerima tugas dari pusat komando.
FIELD_GROUPS = (
    UserGroup.PETUGAS_LAPANGAN,
    UserGroup.KOORDINATOR_WILAYAH,
    UserGroup.PETUGAS_ASET,
    UserGroup.PAAKAYTTAJA,
)


def visible_tasks(user):
    """Tugas yang boleh dilihat: milik sendiri, yang diberikan, sebagai
    kontributor, tugas Korwil yang dipimpin, dan tugas para bawahan."""
    queryset = Task.objects.all()
    if not aset_scope.sees_all(user):
        led = Korwil.objects.filter(coordinator=user)
        condition = (
            Q(assignee=user)
            | Q(created_by=user)
            | Q(contributors=user)
            | Q(korwil__in=led)
        )
        below = hierarchy.descendant_ids(user)
        if below:
            condition |= Q(assignee__in=below)
        queryset = queryset.filter(pk__in=Task.objects.filter(condition).values("pk"))
    return aset_scope.scoped(queryset, user).select_related(
        "assignee", "korwil", "created_by"
    )


def worker_id(task):
    """Yang mengerjakan dan melapor di sistem: penerima utama, atau koordinator
    Korwil untuk tugas wilayah tanpa penerima."""
    if task.assignee_id:
        return task.assignee_id
    if task.korwil_id and task.korwil.coordinator_id:
        return task.korwil.coordinator_id
    return None


def last_event(task):
    return task.komando_events.order_by("-created_at", "-pk").first()


def stage(task, last=None) -> str:
    status = task.status
    if status == aset_enums.TaskStatus.DONE:
        return enums.TaskStage.DONE
    if status == aset_enums.TaskStatus.CANCELLED:
        return enums.TaskStage.CANCELLED
    if status == aset_enums.TaskStatus.REPORTED:
        return enums.TaskStage.REPORTED
    if status == aset_enums.TaskStatus.WAITING:
        return enums.TaskStage.BLOCKED
    if status == aset_enums.TaskStatus.NEW:
        return enums.TaskStage.ASSIGNED
    if last is not None and last.kind == enums.TaskEventKind.REJECTED:
        return enums.TaskStage.REVISION
    return enums.TaskStage.WORKING


def can_verify(user, task) -> bool:
    """Pemberi tugas, atasan penerima, koordinator Korwil tugas, atau
    Administrator — tidak pernah yang mengerjakan tugas itu sendiri."""
    if not user.has_perm("asetlahan.change_task"):
        return False
    worker = worker_id(task)
    if worker is not None and worker == user.pk:
        return False
    if aset_scope.sees_all(user) or task.created_by_id == user.pk:
        return True
    if task.korwil_id and task.korwil.coordinator_id == user.pk:
        return True
    return worker is not None and hierarchy.is_ancestor(
        user, get_user_model()(pk=worker)
    )


def can_cancel(user, task) -> bool:
    """Batal hanya oleh pembuat tugas, koordinator Korwil terkait, atasan
    penerima, atau Administrator."""
    if not user.has_perm("asetlahan.change_task"):
        return False
    if aset_scope.sees_all(user):
        return True
    if task.created_by_id == user.pk and task.assignee_id != user.pk:
        return True
    led = Korwil.objects.filter(coordinator=user, is_active=True)
    if task.korwil_id and led.filter(pk=task.korwil_id).exists():
        return True
    if not task.assignee_id or task.assignee_id == user.pk:
        return False
    return led.filter(members=task.assignee_id).exists() or hierarchy.is_ancestor(
        user, task.assignee
    )


def assignable_users(user):
    """Penerima tugas yang boleh dipilih: seluruh bawahan, atau semua petugas
    aktif bagi Administrator. Tidak pernah diri sendiri."""
    User = get_user_model()
    queryset = User.objects.filter(is_active=True).exclude(pk=user.pk)
    if aset_scope.sees_all(user):
        queryset = queryset.filter(groups__in=FIELD_GROUPS)
    else:
        queryset = queryset.filter(pk__in=hierarchy.descendant_ids(user))
    return queryset.distinct().order_by("first_name", "last_name", "username")


def _note(value, required=False, field="catatan"):
    note = (value or "").strip()
    if required and not note:
        raise ValidationError({field: [_("Catatan wajib diisi.")]})
    if len(note) > MAX_NOTE:
        raise ValidationError({field: [_("Catatan maksimal 2000 karakter.")]})
    return note


def _date(value):
    if not value:
        return None
    try:
        day = datetime.date.fromisoformat(str(value))
    except ValueError:
        raise ValidationError({"tenggat": [_("Tanggal tidak sah.")]})
    if day < timezone.localdate():
        raise ValidationError({"tenggat": [_("Tenggat tidak boleh di masa lalu.")]})
    return day


def _task_type(activity_type):
    if activity_type == enums.ActivityType.HUNTING_PARK:
        return aset_enums.TaskType.PATROL
    if activity_type == enums.ActivityType.ILLEGAL:
        return aset_enums.TaskType.VERIFICATION
    if activity_type:
        return aset_enums.TaskType.SURVEY
    return aset_enums.TaskType.ADMINISTRATION


def _choice(value, choices, field):
    value = (value or "").strip()
    if value and value not in choices:
        raise ValidationError({field: [_("Pilihan tidak sah.")]})
    return value


def _korwil(user, value, assignee):
    if value and str(value).isdigit():
        korwil = geo.visible_korwils(user).filter(pk=value).first()
        if korwil is None:
            raise ValidationError({"korwil": [_("Korwil tidak sah.")]})
        return korwil
    return (
        Korwil.objects.filter(
            Q(members=assignee) | Q(coordinator=assignee), is_active=True
        )
        .order_by("code")
        .first()
    )


@transaction.atomic
def create_task(user, data) -> Task:
    """Buat tugas komando untuk bawahan (``data`` = QueryDict formulir)."""
    if not user.has_perm("asetlahan.add_task"):
        raise PermissionDenied
    allowed = assignable_users(user)
    assignee_id = str(data.get("penerima", ""))
    if not assignee_id.isdigit():
        raise ValidationError({"penerima": [_("Pilih penerima utama tugas.")]})
    assignee = allowed.filter(pk=assignee_id).first()
    if assignee is None:
        raise ValidationError(
            {"penerima": [_("Penerima harus bawahan Anda di struktur komando.")]}
        )
    contributor_ids = {
        int(v)
        for v in str(data.get("kontributor", "")).split(",")
        if v.strip().isdigit()
    } - {assignee.pk}
    if len(contributor_ids) > MAX_CONTRIBUTORS:
        raise ValidationError({"kontributor": [_("Kontributor maksimal 20 orang.")]})
    contributors = list(allowed.filter(pk__in=contributor_ids))
    if len(contributors) != len(contributor_ids):
        raise ValidationError(
            {"kontributor": [_("Kontributor harus bawahan Anda di struktur komando.")]}
        )
    title = (data.get("judul") or "").strip()
    if not title:
        raise ValidationError({"judul": [_("Judul tugas wajib diisi.")]})
    activity_type = _choice(data.get("jenis"), enums.ActivityType.values, "jenis")
    priority = _choice(data.get("prioritas"), aset_enums.Priority.values, "prioritas")
    try:
        points = int(data.get("poin") or 0)
    except ValueError:
        points = -1
    if not 0 <= points <= enums.MAX_TASK_POINTS:
        raise ValidationError(
            {
                "poin": [
                    _("Nilai poin harus 0–%(max)s.")
                    % {"max": number_format(enums.MAX_TASK_POINTS, force_grouping=True)}
                ]
            }
        )
    korwil = _korwil(user, data.get("korwil"), assignee)
    task = Task(
        title=title[:255],
        description=_note(data.get("uraian"), field="uraian")[:MAX_NOTE],
        assignee=assignee,
        korwil=korwil,
        activity_type=activity_type,
        task_type=_task_type(activity_type),
        priority=priority or aset_enums.Priority.NORMAL,
        due_date=_date(data.get("tenggat")),
        start_date=timezone.localdate(),
        point_value=points,
        created_by=user,
        service_unit=korwil.service_unit if korwil else None,
    )
    task.full_clean()
    task.save()
    task.contributors.set(contributors)
    TaskEvent.objects.create(
        task=task,
        kind=enums.TaskEventKind.CREATED,
        actor=user,
        note=_("Untuk %(name)s") % {"name": assignee.get_full_name() or assignee},
    )
    return task


def award_points(task) -> int:
    """Bagikan poin tugas yang diverifikasi selesai (sekali saja)."""
    if not task.point_value or task.komando_points.exists():
        return 0
    rows = {}
    worker = worker_id(task)
    if worker:
        rows[worker] = enums.TaskPointRole.ASSIGNEE
    for pk in task.contributors.values_list("pk", flat=True):
        rows.setdefault(pk, enums.TaskPointRole.CONTRIBUTOR)
    if task.created_by_id:
        rows.setdefault(task.created_by_id, enums.TaskPointRole.GIVER)
    TaskPoint.objects.bulk_create(
        [
            TaskPoint(task=task, user_id=pk, role=role, points=task.point_value)
            for pk, role in rows.items()
        ],
        ignore_conflicts=True,
    )
    return len(rows)


ACTIONS = {
    # aksi: (status asal yang sah, status tujuan, peristiwa, catatan wajib, siapa)
    "mulai": (
        (aset_enums.TaskStatus.NEW,),
        aset_enums.TaskStatus.IN_PROGRESS,
        enums.TaskEventKind.STARTED,
        False,
        "worker",
    ),
    "lapor": (
        (aset_enums.TaskStatus.IN_PROGRESS,),
        aset_enums.TaskStatus.REPORTED,
        enums.TaskEventKind.SUBMITTED,
        False,
        "worker",
    ),
    "kendala": (
        (aset_enums.TaskStatus.IN_PROGRESS,),
        aset_enums.TaskStatus.WAITING,
        enums.TaskEventKind.BLOCKED,
        True,
        "worker",
    ),
    "lanjut": (
        (aset_enums.TaskStatus.WAITING,),
        aset_enums.TaskStatus.IN_PROGRESS,
        enums.TaskEventKind.RESUMED,
        False,
        "worker",
    ),
    "verifikasi": (
        (aset_enums.TaskStatus.REPORTED,),
        aset_enums.TaskStatus.DONE,
        enums.TaskEventKind.VERIFIED,
        False,
        "verifier",
    ),
    "kembalikan": (
        (aset_enums.TaskStatus.REPORTED,),
        aset_enums.TaskStatus.IN_PROGRESS,
        enums.TaskEventKind.REJECTED,
        True,
        "verifier",
    ),
    "batal": (
        tuple(aset_enums.OPEN_TASK_STATUSES),
        aset_enums.TaskStatus.CANCELLED,
        enums.TaskEventKind.CANCELLED,
        False,
        "canceller",
    ),
}


def allowed_actions(user, task) -> list[str]:
    result = []
    is_worker = worker_id(task) == user.pk
    for name, (sources, _target, _kind, _required, who) in ACTIONS.items():
        if task.status not in sources:
            continue
        if who == "worker" and is_worker and user.has_perm("asetlahan.change_task"):
            result.append(name)
        elif who == "verifier" and can_verify(user, task):
            result.append(name)
        elif who == "canceller" and can_cancel(user, task):
            result.append(name)
    return result


@transaction.atomic
def transition(user, task, action, *, note="", photo=None, location=None):
    if action not in ACTIONS:
        raise ValidationError({"aksi": [_("Tindakan tidak dikenal.")]})
    task = Task.objects.select_for_update().get(pk=task.pk)
    sources, target, kind, required, _who = ACTIONS[action]
    if action not in allowed_actions(user, task):
        if task.status not in sources:
            raise ValidationError(
                {"aksi": [_("Tindakan ini tidak berlaku untuk status tugas sekarang.")]}
            )
        raise PermissionDenied
    note = _note(note, required=required)
    if action == "lapor" and not note and not photo:
        raise ValidationError(
            {"catatan": [_("Isi ringkasan hasil atau lampirkan foto bukti.")]}
        )
    event = TaskEvent(task=task, kind=kind, actor=user, note=note, location=location)
    if photo:
        event.photo = photo
    event.full_clean()
    task.status = target
    if action == "lapor":
        task.progress = max(task.progress, 90)
    task.full_clean()
    task.save()
    event.save()
    if target == aset_enums.TaskStatus.DONE:
        award_points(task)
    return task
