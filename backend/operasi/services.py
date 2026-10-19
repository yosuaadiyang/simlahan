"""Logika pusat komando: ringkasan, absensi, kinerja (KPI), SOS, dan pencarian."""

import datetime
import math

from django.core.exceptions import ValidationError
from django.db.models import Count, F, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from asetlahan import enums as aset_enums
from asetlahan import scope as aset_scope
from asetlahan import services as aset_services
from operasi import enums, geo
from operasi.models import (
    RELEASED_PARCEL_STATUSES,
    Activity,
    Attendance,
    ChatMessage,
    CommandSettings,
    Korwil,
    OfficerPosition,
    Resident,
    SoilTest,
    SosAlert,
)
from pengadaan.workdays import is_workday
from utils.group_permissions import UserGroup


def pct(part: int, whole: int) -> int | None:
    return round(part * 100 / whole) if whole else None


def released_q(prefix: str = "") -> Q:
    """Lahan sudah dibebaskan: ditandai di lapangan atau bidang pengadaannya sudah lepas."""
    return Q(**{f"{prefix}land_status": enums.LandStatus.RELEASED}) | Q(
        **{f"{prefix}pengadaan_parcel__status__in": RELEASED_PARCEL_STATUSES}
    )


# --------------------------------------------------------------------------
# Ringkasan & statistik per Korwil
# --------------------------------------------------------------------------


def visible_korwils(user):
    return geo.scoped(Korwil.objects.filter(is_active=True), user, prefix="")


def resident_counts(queryset) -> dict:
    data = queryset.aggregate(
        total=Count("pk", distinct=True),
        known=Count("pk", filter=~Q(stance=enums.Stance.UNKNOWN), distinct=True),
        pro=Count("pk", filter=Q(stance=enums.Stance.SUPPORT), distinct=True),
        contra=Count("pk", filter=Q(stance=enums.Stance.OPPOSE), distinct=True),
        assessed=Count(
            "pk", filter=~Q(rtrw_status=enums.RtrwStatus.UNASSESSED), distinct=True
        ),
        conform=Count(
            "pk", filter=Q(rtrw_status=enums.RtrwStatus.CONFORM), distinct=True
        ),
        released=Count("pk", filter=released_q(), distinct=True),
    )
    data["pending"] = data["total"] - data["released"]
    data["pro_pct"] = pct(data["pro"], data["known"])
    data["rtrw_pct"] = pct(data["conform"], data["assessed"])
    data["released_pct"] = pct(data["released"], data["total"])
    return data


def summary(user, korwil=None) -> dict:
    residents = geo.scoped(Resident.objects.all(), user)
    activities = geo.scoped(Activity.objects.all(), user)
    soil = geo.scoped(SoilTest.objects.all(), user)
    sos = geo.scoped(SosAlert.objects.filter(status__in=enums.OPEN_SOS_STATUSES), user)
    if korwil is not None:
        residents = residents.filter(korwil=korwil)
        activities = activities.filter(korwil=korwil)
        soil = soil.filter(korwil=korwil)
        sos = sos.filter(korwil=korwil)
    config = CommandSettings.load()
    now = timezone.now()
    week_start = timezone.localdate() - datetime.timedelta(days=6)
    data = resident_counts(residents)
    data.update(
        {
            "activities": activities.count(),
            "activities_week": activities.filter(
                started_at__date__gte=week_start
            ).count(),
            "soil": soil.count(),
            "korwil": visible_korwils(user).count(),
            "sos_open": sos.count(),
            "online": OfficerPosition.objects.filter(
                updated_at__gte=now - datetime.timedelta(minutes=config.online_minutes)
            ).count(),
            "present_today": Attendance.objects.filter(
                date=timezone.localdate(), status__in=enums.PRESENT_STATUSES
            ).count(),
            "updated_at": now.isoformat(),
        }
    )
    return data


def korwil_stats(user) -> dict[int, dict]:
    """Statistik per Korwil untuk peta tematik (persentase Pro, RTRW, lahan)."""
    residents = geo.scoped(Resident.objects.exclude(korwil=None), user)
    rows = residents.values("korwil").annotate(
        total=Count("pk"),
        known=Count("pk", filter=~Q(stance=enums.Stance.UNKNOWN)),
        pro=Count("pk", filter=Q(stance=enums.Stance.SUPPORT)),
        assessed=Count("pk", filter=~Q(rtrw_status=enums.RtrwStatus.UNASSESSED)),
        conform=Count("pk", filter=Q(rtrw_status=enums.RtrwStatus.CONFORM)),
        released=Count("pk", filter=released_q()),
    )
    stats = {}
    for row in rows:
        stats[row["korwil"]] = {
            "total": row["total"],
            "pro_pct": pct(row["pro"], row["known"]),
            "rtrw_pct": pct(row["conform"], row["assessed"]),
            "released": row["released"],
            "pending": row["total"] - row["released"],
            "released_pct": pct(row["released"], row["total"]),
        }
    for row in (
        geo.scoped(Activity.objects.exclude(korwil=None), user)
        .values("korwil")
        .annotate(n=Count("pk"))
    ):
        stats.setdefault(row["korwil"], {})["activities"] = row["n"]
    for row in (
        geo.scoped(SoilTest.objects.exclude(korwil=None), user)
        .values("korwil")
        .annotate(n=Count("pk"))
    ):
        stats.setdefault(row["korwil"], {})["soil"] = row["n"]
    return stats


# --------------------------------------------------------------------------
# Absensi
# --------------------------------------------------------------------------


def _late(moment, config) -> bool:
    local = timezone.localtime(moment)
    limit = datetime.datetime.combine(
        local.date(), config.work_start
    ) + datetime.timedelta(minutes=config.late_tolerance_minutes)
    return local.replace(tzinfo=None) > limit


def _validate_check_in(attendance, location, photo, config):
    if (
        attendance is not None
        and attendance.status in enums.ABSENCE_STATUSES
        and attendance.status != enums.AttendanceStatus.DUTY
    ):
        raise ValidationError(
            _("Hari ini sudah tercatat %(status)s.")
            % {"status": attendance.get_status_display().lower()}
        )
    if location is None:
        raise ValidationError(_("Lokasi GPS wajib untuk absen."))
    if config.require_attendance_photo and not photo:
        raise ValidationError(_("Swafoto wajib untuk absen."))


def _check_in_area(user, location, config):
    """Korwil absen dan apakah lokasi di dalam wilayahnya (geofence)."""
    korwil = geo.korwil_for(location, user)
    if korwil is None:
        korwil = next(iter(geo.user_korwils(user)[:1]), None)
    inside = geo.in_area(korwil, location, config.geofence_tolerance_m)
    warnings = []
    if inside is False:
        if config.enforce_geofence:
            raise ValidationError(
                _("Anda berada di luar wilayah %(korwil)s. Absen ditolak.")
                % {"korwil": korwil}
            )
        warnings.append(_("Lokasi absen di luar wilayah Korwil (ditandai)."))
    return korwil, inside, warnings


def check_in(user, *, location, accuracy=None, photo=None, note="", now=None):
    """Absen masuk hari ini. Mengembalikan (absensi, baru_dibuat, peringatan)."""
    config = CommandSettings.load()
    now = now or timezone.now()
    today = timezone.localtime(now).date()
    attendance = Attendance.objects.filter(user=user, date=today).first()
    if attendance is not None and attendance.check_in_at:
        return attendance, False, []
    _validate_check_in(attendance, location, photo, config)
    korwil, inside, warnings = _check_in_area(user, location, config)
    attendance = attendance or Attendance(user=user, date=today)
    if attendance.status != enums.AttendanceStatus.DUTY:
        attendance.status = (
            enums.AttendanceStatus.LATE
            if _late(now, config)
            else enums.AttendanceStatus.PRESENT
        )
        if attendance.status == enums.AttendanceStatus.LATE:
            warnings.append(_("Tercatat terlambat."))
    attendance.korwil = korwil
    attendance.check_in_at = now
    attendance.check_in_location = location
    attendance.check_in_accuracy_m = accuracy
    attendance.check_in_in_area = inside
    if photo:
        attendance.check_in_photo = photo
    if note:
        attendance.note = note[:2000]
    attendance.full_clean(validate_unique=False)
    attendance.save()
    return attendance, True, warnings


def check_out(user, *, location, accuracy=None, photo=None, note="", now=None):
    config = CommandSettings.load()
    now = now or timezone.now()
    today = timezone.localtime(now).date()
    attendance = Attendance.objects.filter(user=user, date=today).first()
    if attendance is None or not attendance.check_in_at:
        raise ValidationError(_("Belum absen masuk hari ini."))
    if attendance.check_out_at:
        return attendance, False, []
    if location is None:
        raise ValidationError(_("Lokasi GPS wajib untuk absen."))
    if config.require_attendance_photo and not photo:
        raise ValidationError(_("Swafoto wajib untuk absen."))
    inside = geo.in_area(attendance.korwil, location, config.geofence_tolerance_m)
    warnings = []
    if inside is False:
        if config.enforce_geofence:
            raise ValidationError(
                _("Anda berada di luar wilayah %(korwil)s. Absen ditolak.")
                % {"korwil": attendance.korwil}
            )
        warnings.append(_("Lokasi absen di luar wilayah Korwil (ditandai)."))
    if timezone.localtime(now).time() < config.work_end:
        warnings.append(_("Pulang sebelum jam kerja berakhir."))
    attendance.check_out_at = now
    attendance.check_out_location = location
    attendance.check_out_accuracy_m = accuracy
    attendance.check_out_in_area = inside
    attendance.missing_checkout = False
    if photo:
        attendance.check_out_photo = photo
    if note:
        attendance.note = "\n".join(filter(None, [attendance.note, note[:2000]]))
    attendance.full_clean(validate_unique=False)
    attendance.save()
    return attendance, True, warnings


def request_leave(user, *, status, date, note, attachment=None):
    """Ajukan izin / sakit / cuti / dinas luar untuk suatu tanggal."""
    if status not in enums.ABSENCE_STATUSES:
        raise ValidationError(_("Jenis izin tidak dikenal."))
    today = timezone.localdate()
    if not (
        today - datetime.timedelta(days=7)
        <= date
        <= today + datetime.timedelta(days=60)
    ):
        raise ValidationError(
            _("Tanggal izin hanya boleh 7 hari ke belakang sampai 60 hari ke depan.")
        )
    if not note.strip():
        raise ValidationError(_("Keterangan izin wajib diisi."))
    attendance = Attendance.objects.filter(user=user, date=date).first()
    if attendance is not None and attendance.check_in_at:
        raise ValidationError(_("Tanggal ini sudah ada absen masuk."))
    attendance = attendance or Attendance(user=user, date=date)
    attendance.status = status
    attendance.note = note.strip()[:2000]
    if attendance.korwil_id is None:
        attendance.korwil = next(iter(geo.user_korwils(user)[:1]), None)
    if attachment:
        attendance.attachment = attachment
    attendance.full_clean(validate_unique=False)
    attendance.save()
    return attendance


# --------------------------------------------------------------------------
# Kinerja (KPI)
# --------------------------------------------------------------------------


def period_bounds(period: str, today=None) -> tuple[datetime.date, datetime.date]:
    today = today or timezone.localdate()
    if period == "minggu":
        start = today - datetime.timedelta(days=today.weekday())
        return start, start + datetime.timedelta(days=6)
    if period == "bulan-lalu":
        end = today.replace(day=1) - datetime.timedelta(days=1)
        return end.replace(day=1), end
    start = today.replace(day=1)
    next_month = (start + datetime.timedelta(days=32)).replace(day=1)
    return start, next_month - datetime.timedelta(days=1)


def _workdays(start, end) -> list[datetime.date]:
    from pengadaan.models import Holiday

    holidays = set(
        Holiday.objects.filter(date__gte=start, date__lte=end).values_list(
            "date", flat=True
        )
    )
    days, current = [], start
    while current <= end:
        if is_workday(current, holidays):
            days.append(current)
        current += datetime.timedelta(days=1)
    return days


def grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    return "D"


def performance(user, start: datetime.date, end: datetime.date, config=None) -> dict:
    from asetlahan.models import Task

    config = config or CommandSettings.load()
    today = timezone.localdate()
    counted_end = min(end, today)
    # Petugas baru tidak dinilai untuk hari sebelum akunnya dibuat.
    joined = timezone.localtime(user.date_joined).date() if user.date_joined else start
    counted_start = max(start, joined)
    workdays = (
        _workdays(counted_start, counted_end) if counted_end >= counted_start else []
    )
    attendances = {
        a.date: a
        for a in Attendance.objects.filter(user=user, date__gte=start, date__lte=end)
    }
    present = [
        a
        for a in attendances.values()
        if a.status in enums.PRESENT_STATUSES or a.status == enums.AttendanceStatus.DUTY
    ]
    # Hari ini baru dihitung setelah ada catatan absen (pagi hari belum terlambat absen).
    attendance_days = [d for d in workdays if d < today or d in attendances]
    excused = sum(
        1
        for day, a in attendances.items()
        if day in attendance_days
        and a.status
        in (
            enums.AttendanceStatus.PERMIT,
            enums.AttendanceStatus.SICK,
            enums.AttendanceStatus.LEAVE,
        )
    )
    late = sum(1 for a in present if a.status == enums.AttendanceStatus.LATE)
    expected_days = max(len(attendance_days) - excused, 0)
    attendance_rate = (
        min(len([a for a in present if a.date in attendance_days]) / expected_days, 1.0)
        if expected_days
        else 1.0
    )
    on_time_rate = (len(present) - late) / len(present) if present else None

    activities = Activity.objects.filter(
        reported_by=user, started_at__date__gte=start, started_at__date__lte=end
    )
    activity_count = activities.count()
    activity_target = (
        max(math.ceil(config.weekly_activity_target * len(workdays) / 5), 1)
        if workdays and config.weekly_activity_target
        else 0
    )
    activity_rate = (
        min(activity_count / activity_target, 1.0) if activity_target else 1.0
    )
    visited = Resident.objects.filter(activities__in=activities).distinct().count()

    tasks = Task.objects.filter(assignee=user)
    due = tasks.filter(due_date__gte=start, due_date__lte=counted_end).exclude(
        status=aset_enums.TaskStatus.CANCELLED
    )
    due_count = due.count()
    done_on_time = due.filter(
        status=aset_enums.TaskStatus.DONE, completed_date__lte=F("due_date")
    ).count()
    overdue = tasks.filter(
        status__in=aset_enums.OPEN_TASK_STATUSES, due_date__lt=today
    ).count()
    completed = tasks.filter(
        status=aset_enums.TaskStatus.DONE,
        completed_date__gte=start,
        completed_date__lte=end,
    ).count()
    task_rate = done_on_time / due_count if due_count else 1.0

    score = round(
        config.weight_attendance * attendance_rate
        + config.weight_activity * activity_rate
        + config.weight_task * task_rate,
        1,
    )
    per_day = dict(activities.values_list("started_at__date").annotate(n=Count("pk")))
    days = []
    current = start
    while current <= end:
        record = attendances.get(current)
        days.append(
            {
                "date": current.isoformat(),
                "workday": current in workdays,
                "status": record.status if record else "",
                "activities": per_day.get(current, 0),
            }
        )
        current += datetime.timedelta(days=1)
    return {
        "user": user.get_full_name() or user.get_username(),
        "user_id": user.pk,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "workdays": len(workdays),
        "present_days": len(present),
        "late_days": late,
        "excused_days": excused,
        "attendance_pct": round(attendance_rate * 100),
        "on_time_pct": round(on_time_rate * 100) if on_time_rate is not None else None,
        "activities": activity_count,
        "activity_target": activity_target,
        "activity_pct": round(activity_rate * 100),
        "residents_visited": visited,
        "tasks_due": due_count,
        "tasks_on_time": done_on_time,
        "tasks_completed": completed,
        "tasks_overdue": overdue,
        "task_pct": round(task_rate * 100),
        "score": score,
        "grade": grade(score),
        "days": days,
    }


def team_users(user):
    """Petugas yang kinerjanya boleh dilihat.

    Seluruh petugas (Administrator), anggota Korwil yang dipimpin, atau diri sendiri.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if user.has_perm("operasi.view_attendance") and aset_scope.sees_all(user):
        korwils = visible_korwils(user)
    else:
        korwils = Korwil.objects.filter(coordinator=user, is_active=True)
    return (
        User.objects.filter(
            Q(operasi_korwil__in=korwils)
            | Q(operasi_korwil_led__in=korwils)
            | Q(pk=user.pk),
            is_active=True,
        )
        .distinct()
        .order_by("first_name", "username")
    )


def leaderboard(user, start, end) -> list[dict]:
    config = CommandSettings.load()
    rows = [performance(member, start, end, config) for member in team_users(user)]
    for row in rows:
        row.pop("days", None)
    return sorted(rows, key=lambda r: (-r["score"], r["user"]))


# --------------------------------------------------------------------------
# SOS
# --------------------------------------------------------------------------


def _map_link(point) -> str:
    if point is None:
        return ""
    return f"https://www.google.com/maps?q={point.y:.6f},{point.x:.6f}"


def raise_sos(alert: SosAlert) -> None:
    """Kirim pesan sistem ke chat dan surel ke koordinator, Administrator, dan daftar SOS."""
    who = alert.raised_by.get_full_name() if alert.raised_by else ""
    who = who or (alert.raised_by.get_username() if alert.raised_by else _("Petugas"))
    where = _map_link(alert.location)
    text = _("🆘 SOS dari %(who)s%(korwil)s. %(message)s") % {
        "who": who,
        "korwil": f" ({alert.korwil})" if alert.korwil_id else "",
        "message": alert.message or _("Butuh bantuan segera."),
    }
    ChatMessage.objects.create(
        korwil=None, sender=None, body=text, location=alert.location, is_system=True
    )
    recipients = set(CommandSettings.load().sos_recipients())
    recipients.update(aset_services.group_emails(UserGroup.PAAKAYTTAJA))
    if (
        alert.korwil_id
        and alert.korwil.coordinator_id
        and alert.korwil.coordinator.email
    ):
        recipients.add(alert.korwil.coordinator.email)
    body = "\n".join(
        filter(
            None,
            [
                text,
                _("Waktu: %s")
                % timezone.localtime(alert.created_at).strftime("%d-%m-%Y %H:%M"),
                _("Lokasi: %s") % where if where else _("Lokasi tidak tersedia."),
                aset_services.app_url(reverse("operasi-command")),
            ],
        )
    )
    aset_services.send_email(recipients, _("SOS %s") % alert.number, body)


def update_sos(alert: SosAlert, action: str, user, note: str = "") -> SosAlert:
    now = timezone.now()
    if action == "tangani":
        if alert.status != enums.SosStatus.ACTIVE:
            raise ValidationError(_("SOS ini sudah ditangani."))
        alert.status = enums.SosStatus.ACKNOWLEDGED
        alert.acknowledged_by, alert.acknowledged_at = user, now
        message = _("✅ SOS %(number)s ditangani oleh %(who)s.")
    elif action in ("selesai", "palsu"):
        if not alert.is_open:
            raise ValidationError(_("SOS ini sudah ditutup."))
        alert.status = (
            enums.SosStatus.RESOLVED
            if action == "selesai"
            else enums.SosStatus.FALSE_ALARM
        )
        if alert.acknowledged_at is None:
            alert.acknowledged_by, alert.acknowledged_at = user, now
        alert.resolved_by, alert.resolved_at = user, now
        alert.resolution_note = note[:2000]
        message = _("☑️ SOS %(number)s ditutup oleh %(who)s.")
    else:
        raise ValidationError(_("Tindakan tidak dikenal."))
    alert.save()
    ChatMessage.objects.create(
        body=message
        % {"number": alert.number, "who": user.get_full_name() or user.get_username()},
        is_system=True,
    )
    return alert


# --------------------------------------------------------------------------
# Pencarian (palet perintah)
# --------------------------------------------------------------------------


def _point_result(kind, label, sub, point, **extra):
    item = {"kind": kind, "label": label, "sub": sub, **extra}
    if point is not None:
        item["lat"], item["lng"] = round(point.y, 7), round(point.x, 7)
    return item


def _bounds(geom):
    if geom is None:
        return None
    xmin, ymin, xmax, ymax = geom.extent
    return [[ymin, xmin], [ymax, xmax]]


def _search_korwils(user, query, limit):
    korwils = visible_korwils(user).filter(
        Q(code__iexact=query.removeprefix("korwil ").strip())
        | Q(name__icontains=query)
        | Q(villages__icontains=query)
    )
    return [
        {
            "kind": "korwil",
            "label": str(korwil),
            "sub": korwil.villages,
            "id": korwil.pk,
            "bounds": _bounds(korwil.geometry),
        }
        for korwil in korwils[:limit]
    ]


def _search_residents(user, query, limit):
    from pengadaan.crypto import fingerprint

    digits = "".join(ch for ch in query if ch.isdigit())
    match = (
        Q(number__icontains=query)
        | Q(head_name__icontains=query)
        | Q(village__icontains=query)
        | Q(address__icontains=query)
    )
    if len(digits) >= 16:
        match |= Q(nik_fingerprint=fingerprint(digits))
    residents = geo.scoped(Resident.objects.select_related("korwil"), user)
    return [
        _point_result(
            "warga",
            resident.head_name,
            " · ".join(
                filter(
                    None,
                    [resident.number, resident.village, resident.get_stance_display()],
                )
            ),
            resident.location,
            id=resident.pk,
        )
        for resident in residents.filter(match)[:limit]
    ]


def _search_activities(user, query, limit):
    activities = geo.scoped(Activity.objects.all(), user).filter(
        Q(number__icontains=query) | Q(title__icontains=query)
    )
    return [
        _point_result(
            "kegiatan",
            activity.title,
            f"{activity.number} · {timezone.localtime(activity.started_at):%d-%m-%Y}",
            activity.location,
            id=activity.pk,
        )
        for activity in activities[:limit]
    ]


def _search_soil_tests(user, query, limit):
    tests = geo.scoped(SoilTest.objects.all(), user).filter(number__icontains=query)
    return [
        _point_result(
            "tanah", test.number, test.get_suitability_display(), test.location
        )
        for test in tests[:limit]
    ]


def _search_tasks(user, query, limit):
    from asetlahan.models import Task

    tasks = aset_scope.scoped(Task.objects.all(), user).filter(
        Q(number__icontains=query) | Q(title__icontains=query)
    )
    return [
        {
            "kind": "tugas",
            "label": task.title,
            "sub": f"{task.number} · {task.get_status_display()}",
            "id": task.pk,
        }
        for task in tasks[:limit]
    ]


def _search_assets(user, query, limit):
    from asetlahan.models import LandAsset

    assets = aset_scope.scoped(LandAsset.objects.all(), user).filter(
        Q(code__icontains=query) | Q(name__icontains=query)
    )
    return [
        {
            "kind": "aset",
            "label": f"{asset.code} – {asset.name}",
            "sub": asset.get_status_display(),
            "bounds": _bounds(asset.geometry),
        }
        for asset in assets[:limit]
    ]


def _search_parcels(user, query, limit):
    from pengadaan.models import AcquisitionParcel

    parcels = AcquisitionParcel.objects.select_related("project").filter(
        Q(parcel_number__icontains=query) | Q(nib__icontains=query)
    )
    return [
        {
            "kind": "bidang",
            "label": _("Bidang %s") % parcel.parcel_number,
            "sub": f"{parcel.project.identifier} · {parcel.get_status_display()}",
            "bounds": _bounds(parcel.geometry),
        }
        for parcel in parcels[:limit]
    ]


# (izin yang diperlukan, fungsi pencarian), dalam urutan tampil.
SEARCH_SOURCES = (
    ("operasi.view_korwil", _search_korwils),
    ("operasi.view_resident", _search_residents),
    ("operasi.view_activity", _search_activities),
    ("operasi.view_soiltest", _search_soil_tests),
    ("asetlahan.view_task", _search_tasks),
    ("asetlahan.view_landasset", _search_assets),
    ("pengadaan.view_acquisitionparcel", _search_parcels),
)


def search(user, query: str, limit: int = 8) -> list[dict]:
    query = (query or "").strip()
    if len(query) < 2:
        return []
    results = []
    for permission, source in SEARCH_SOURCES:
        if user.has_perm(permission):
            results.extend(source(user, query, limit))
    return results
