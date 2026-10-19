import datetime
import io

import pytest
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.utils import timezone

from asetlahan import enums as aset_enums
from asetlahan.models import Task
from operasi import enums, services
from operasi.models import Activity, Attendance, CommandSettings, OfficerPosition
from operasi.tests.conftest import inside, login

pytestmark = pytest.mark.django_db

FAR = Point(105.5, 1.5, srid=4326)


def at(day: datetime.date, hour: int, minute: int = 0):
    return timezone.make_aware(
        datetime.datetime.combine(day, datetime.time(hour, minute))
    )


def test_check_in_on_time_and_late(field, other_field, korwil):
    today = timezone.localdate()
    attendance, created, warnings = services.check_in(
        field, location=inside(korwil), now=at(today, 8, 10)
    )
    assert (
        created and attendance.status == enums.AttendanceStatus.PRESENT and not warnings
    )
    assert attendance.korwil == korwil and attendance.check_in_in_area is True
    again, created, _warnings = services.check_in(
        field, location=inside(korwil), now=at(today, 9)
    )
    assert not created and again.pk == attendance.pk
    late, _created, warnings = services.check_in(
        other_field, location=FAR, now=at(today, 8, 16)
    )
    assert late.status == enums.AttendanceStatus.LATE and warnings


def test_geofence_and_photo_rules(field, korwil):
    config = CommandSettings.load()
    config.enforce_geofence = True
    config.save()
    with pytest.raises(ValidationError):
        services.check_in(field, location=FAR)
    with pytest.raises(ValidationError):
        services.check_in(field, location=None)
    config.enforce_geofence = False
    config.require_attendance_photo = True
    config.save()
    with pytest.raises(ValidationError):
        services.check_in(field, location=inside(korwil))
    config.require_attendance_photo = False
    config.save()
    attendance, _created, warnings = services.check_in(field, location=FAR)
    assert attendance.check_in_in_area is False and warnings


def test_check_out(field, korwil):
    today = timezone.localdate()
    with pytest.raises(ValidationError):
        services.check_out(field, location=inside(korwil))
    services.check_in(field, location=inside(korwil), now=at(today, 7, 55))
    attendance, created, warnings = services.check_out(
        field, location=inside(korwil), now=at(today, 15)
    )
    assert created and warnings  # pulang sebelum jam kerja berakhir
    assert attendance.worked_minutes == 7 * 60 + 5


def test_leave_request_rules(field, korwil):
    today = timezone.localdate()
    with pytest.raises(ValidationError):
        services.request_leave(field, status="hadir", date=today, note="x")
    with pytest.raises(ValidationError):
        services.request_leave(
            field, status="sakit", date=today - datetime.timedelta(days=30), note="x"
        )
    with pytest.raises(ValidationError):
        services.request_leave(field, status="sakit", date=today, note=" ")
    leave = services.request_leave(field, status="sakit", date=today, note="Demam")
    assert leave.status == enums.AttendanceStatus.SICK and leave.korwil == korwil
    with pytest.raises(ValidationError):
        services.check_in(field, location=inside(korwil))


def test_attendance_api(field, korwil):
    client = login(field)
    point = inside(korwil)
    response = client.post(
        "/komando/api/absen/",
        {"aksi": "masuk", "lat": point.y, "lng": point.x, "accuracy": "12.345"},
    )
    assert response.status_code == 200, response.content
    data = client.get("/komando/api/absen/").json()
    assert data["today"]["check_in_at"] and data["history"]
    response = client.post(
        "/komando/api/absen/", {"aksi": "pulang", "lat": point.y, "lng": point.x}
    )
    assert response.status_code == 200
    tomorrow = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()
    response = client.post(
        "/komando/api/absen/",
        {"aksi": "izin", "jenis": "cuti", "tanggal": tomorrow, "note": "Cuti"},
    )
    assert response.status_code == 200
    assert (
        client.post(
            "/komando/api/absen/", {"aksi": "izin", "jenis": "cuti", "tanggal": "x"}
        ).status_code
        == 400
    )
    assert client.post("/komando/api/absen/", {"aksi": "terbang"}).status_code == 400


def test_performance_score(field, korwil):
    today = timezone.localdate()
    start, end = services.period_bounds("bulan", today)
    field.date_joined = timezone.make_aware(
        datetime.datetime.combine(start, datetime.time(0, 0))
    )
    field.save()
    workdays = services._workdays(start, min(end, today))
    past = [d for d in workdays if d < today]
    for day in past:
        Attendance.objects.create(
            user=field, date=day, status=enums.AttendanceStatus.PRESENT
        )
    for _i in range(60):
        Activity.objects.create(
            title="Kunjungan",
            reported_by=field,
            korwil=korwil,
            started_at=timezone.now() - datetime.timedelta(minutes=5),
        )
    data = services.performance(field, start, end)
    assert (
        data["attendance_pct"] == 100
        and data["activity_pct"] == 100
        and data["task_pct"] == 100
    )
    assert data["score"] == 100 and data["grade"] == "A"
    assert len(data["days"]) == (end - start).days + 1
    # Tugas jatuh tempo yang belum selesai menurunkan skor tugas.
    if past:
        Task.objects.create(title="Terlambat", assignee=field, due_date=past[0])
        data = services.performance(field, start, end)
        assert (
            data["task_pct"] == 0 and data["tasks_overdue"] == 1 and data["score"] == 75
        )


def test_new_officer_is_not_penalised_before_joining(field):
    today = timezone.localdate()
    start, end = services.period_bounds("bulan", today)
    field.date_joined = timezone.now()
    field.save()
    data = services.performance(field, start, end)
    assert data["attendance_pct"] == 100 and data["workdays"] <= 1


def test_grades():
    assert [services.grade(s) for s in (90, 70, 55, 10)] == ["A", "B", "C", "D"]


def test_period_bounds():
    day = datetime.date(2026, 3, 18)
    assert services.period_bounds("minggu", day) == (
        datetime.date(2026, 3, 16),
        datetime.date(2026, 3, 22),
    )
    assert services.period_bounds("bulan", day) == (
        datetime.date(2026, 3, 1),
        datetime.date(2026, 3, 31),
    )
    assert services.period_bounds("bulan-lalu", day) == (
        datetime.date(2026, 2, 1),
        datetime.date(2026, 2, 28),
    )


def test_daily_job(field, korwil):
    yesterday = timezone.localdate() - datetime.timedelta(days=1)
    open_day = Attendance.objects.create(
        user=field,
        date=yesterday,
        status=enums.AttendanceStatus.PRESENT,
        check_in_at=at(yesterday, 8),
    )
    OfficerPosition.objects.create(
        user=field,
        location=inside(korwil),
        updated_at=timezone.now() - datetime.timedelta(days=2),
    )
    out = io.StringIO()
    call_command("operasi_harian", stdout=out)
    open_day.refresh_from_db()
    assert open_day.missing_checkout is True
    assert not OfficerPosition.objects.exists()
    assert "1 absensi" in out.getvalue()


def test_daily_job_is_scheduled(db):
    from batchrun.models import ScheduledJob
    from operasi.setup import ensure_daily_job

    assert ensure_daily_job() is True
    assert ensure_daily_job() is False
    assert ScheduledJob.objects.get(job__name="Rekap harian pusat komando").hours == "0"


def test_task_korwil_open_statuses(field, korwil):
    task = Task.objects.create(
        title="Wilayah", korwil=korwil, status=aset_enums.TaskStatus.DONE
    )
    assert task in korwil.tasks.all()
