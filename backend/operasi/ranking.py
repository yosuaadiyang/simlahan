"""Peringkat tim (tier, lencana, Excel) dan rincian kinerja pribadi.

Wawasan (insight) disusun AI bila tersedia; bila tidak, dari aturan sederhana
atas angka yang sama sehingga selalu ada ringkasan yang bisa dibaca.
"""

import datetime
import logging
from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from asetlahan import enums as aset_enums
from asetlahan import scope as aset_scope
from operasi import enums, geo, hierarchy, recap, services, task_flow
from operasi.models import Activity, Attendance, Korwil
from utils.group_permissions import UserGroup

LOG = logging.getLogger(__name__)

TIERS = (
    ("lapangan", _lazy("Lapangan")),
    ("koordinator", _lazy("Koordinator")),
    ("manajemen", _lazy("Manajemen")),
)
VIEWS = ("semua", "atas", "bawah")
VIEW_SIZE = 10
HEAT_DAYS = 90
MAX_POINTS = 500

BADGES = {
    "hadir": ("🎯", _lazy("Hadir penuh")),
    "tepat": ("⏰", _lazy("Selalu tepat waktu")),
    "komsos": ("🗣️", _lazy("Komsos terbanyak")),
    "pendata": ("🏠", _lazy("Pendata warga terbanyak")),
    "tuntas": ("✅", _lazy("Tugas tuntas")),
    "melesat": ("🚀", _lazy("Peringkat naik")),
}

INSIGHT_PROMPT = (
    "Anda analis kinerja tim lapangan pendataan warga dan pembebasan lahan. "
    "Tulis wawasan singkat dalam bahasa Indonesia (maksimal 6 poin berawalan "
    "'- '), berdasarkan angka yang diberikan saja: siapa menonjol, siapa perlu "
    "dibina dan pada aspek apa (kehadiran, ketepatan waktu, volume kegiatan, "
    "tugas), serta satu saran tindakan konkret. Jangan mengarang angka."
)


def _name(user) -> str:
    return user.get_full_name() or user.get_username()


def _local(moment) -> str:
    return timezone.localtime(moment).isoformat() if moment else ""


# --------------------------------------------------------------------------
# Tier & peringkat
# --------------------------------------------------------------------------


def tiers_for(users) -> dict[int, str]:
    """Tier pembanding: manajemen (Administrator, pengawas unit, atau atasan
    di luar Korwil yang dipimpinnya), koordinator (memimpin Korwil), selain
    itu lapangan."""
    from django.contrib.auth import get_user_model

    ids = [u.pk for u in users]
    leaders = set(
        Korwil.objects.filter(coordinator__in=ids, is_active=True).values_list(
            "coordinator", flat=True
        )
    )
    groups = defaultdict(set)
    for user_id, group_id in (
        get_user_model()
        .groups.through.objects.filter(user_id__in=ids)
        .values_list("user_id", "group_id")
    ):
        groups[user_id].add(group_id)
    result = {}
    for user in users:
        if aset_scope.sees_all(user) or UserGroup.PETUGAS_ASET in groups[user.pk]:
            result[user.pk] = "manajemen"
        elif user.pk in leaders or UserGroup.KOORDINATOR_WILAYAH in groups[user.pk]:
            led_members = set(
                Korwil.objects.filter(coordinator=user).values_list(
                    "members", flat=True
                )
            )
            beyond = hierarchy.direct_subordinate_ids(user) - led_members
            result[user.pk] = "manajemen" if beyond else "koordinator"
        else:
            result[user.pk] = "lapangan"
    return result


def _komsos_stats(user_ids, start, end) -> dict[int, dict]:
    komsos = Activity.objects.filter(
        reported_by__in=user_ids,
        activity_type=enums.ActivityType.KOMSOS,
        started_at__date__gte=start,
        started_at__date__lte=end,
    )
    stats = defaultdict(lambda: {"komsos": 0, "new_residents": 0})
    for user_id, n in (
        komsos.order_by().values_list("reported_by").annotate(n=Count("pk"))
    ):
        stats[user_id]["komsos"] = n
    through = Activity.residents.through
    for user_id, n in (
        through.objects.filter(
            activity__in=komsos.values("pk"),
            resident__registered_activity=F("activity_id"),
        )
        .order_by()
        .values_list("activity__reported_by")
        .annotate(n=Count("pk"))
    ):
        stats[user_id]["new_residents"] = n
    return stats


def _award_badges(rows):
    for row in rows:
        row["badges"] = []
    if not rows:
        return
    top_komsos = max(r["komsos"] for r in rows)
    top_new = max(r["new_residents"] for r in rows)
    for row in rows:
        badges = row["badges"]
        if row["workdays"] >= 3 and row["attendance_pct"] == 100:
            badges.append("hadir")
        if row["present_days"] >= 3 and row["on_time_pct"] == 100:
            badges.append("tepat")
        if top_komsos and row["komsos"] == top_komsos:
            badges.append("komsos")
        if top_new and row["new_residents"] == top_new:
            badges.append("pendata")
        if row["tasks_due"] and row["task_pct"] == 100 and not row["tasks_overdue"]:
            badges.append("tuntas")
        if row.get("trend") == "naik":
            badges.append("melesat")


def _korwil_codes(people) -> dict[int, list[str]]:
    codes = defaultdict(list)
    for code, member, coordinator in Korwil.objects.filter(
        Q(members__in=list(people)) | Q(coordinator__in=list(people)), is_active=True
    ).values_list("code", "members", "coordinator"):
        for user_id in (member, coordinator):
            if user_id in people and code not in codes[user_id]:
                codes[user_id].append(code)
    return codes


def _enrich(rows, start, end):
    """Tambahkan tier, komsos, warga baru, dan kode Korwil ke tiap baris."""
    from django.contrib.auth import get_user_model

    people = {
        u.pk: u
        for u in get_user_model().objects.filter(pk__in=[r["user_id"] for r in rows])
    }
    tiers = tiers_for(list(people.values()))
    komsos = _komsos_stats(list(people), start, end)
    codes = _korwil_codes(people)
    labels = dict(TIERS)
    for row in rows:
        user_id = row["user_id"]
        row["tier"] = tiers.get(user_id, "lapangan")
        row["tier_label"] = str(labels[row["tier"]])
        row["komsos"] = komsos[user_id]["komsos"]
        row["new_residents"] = komsos[user_id]["new_residents"]
        row["korwils"] = sorted(codes.get(user_id, []))


def _only_korwil(rows, korwil):
    allowed = set(korwil.members.values_list("pk", flat=True))
    if korwil.coordinator_id:
        allowed.add(korwil.coordinator_id)
    return [r for r in rows if r["user_id"] in allowed]


def _only_tier(rows, tier):
    rows = [r for r in rows if r["tier"] == tier]
    ranks = services._ranks({r["user_id"]: r["score"] for r in rows})
    for row in rows:
        row["rank"] = ranks[row["user_id"]]
    return rows


def _view_slice(rows, view):
    if view == "atas":
        return rows[:VIEW_SIZE]
    if view == "bawah":
        return list(reversed(rows[-VIEW_SIZE:]))
    return rows


def board(user, period, korwil=None, tier="", view="semua") -> dict:
    start, end = services.period_bounds(period)
    rows = services.leaderboard(user, start, end)
    if korwil is not None:
        rows = _only_korwil(rows, korwil)
    _enrich(rows, start, end)
    if tier in dict(TIERS):
        rows = _only_tier(rows, tier)
    _award_badges(rows)
    total = len(rows)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "count": total,
        "average": round(sum(r["score"] for r in rows) / total, 1) if total else None,
        "grades": {g: sum(1 for r in rows if r["grade"] == g) for g in "ABCD"},
        "results": _view_slice(rows, view),
        "badges": {
            key: {"icon": icon, "label": str(label)}
            for key, (icon, label) in BADGES.items()
        },
    }


def board_workbook(data) -> bytes:
    book = recap._Book()
    labels = {key: str(label) for key, (_icon, label) in BADGES.items()}
    trend = {
        "naik": _("naik"),
        "turun": _("turun"),
        "baru": _("baru"),
        "stabil": _("stabil"),
    }
    book.table(
        _("Peringkat"),
        [
            _("Peringkat"),
            _("Petugas"),
            _("Tier"),
            _("Korwil"),
            _("Skor"),
            _("Nilai"),
            _("Kehadiran (%)"),
            _("Tepat waktu (%)"),
            _("Poin kegiatan"),
            _("Target"),
            _("Komsos"),
            _("Warga baru"),
            _("Tugas tepat waktu (%)"),
            _("Tren"),
            _("Lencana"),
        ],
        (
            [
                row["rank"],
                row["user"],
                row["tier_label"],
                ", ".join(row["korwils"]),
                row["score"],
                row["grade"],
                row["attendance_pct"],
                row["on_time_pct"],
                row["activities"],
                row["activity_target"],
                row["komsos"],
                row["new_residents"],
                row["task_pct"],
                str(trend.get(row.get("trend"), "")),
                ", ".join(labels[b] for b in row["badges"]),
            ]
            for row in data["results"]
        ),
        widths={1: 26, 14: 40},
    )
    return book.close()


# --------------------------------------------------------------------------
# Rincian kinerja pribadi
# --------------------------------------------------------------------------


def _week_key(day) -> str:
    year, week, _weekday = day.isocalendar()
    return f"{year}-W{week:02d}"


def personal(target, start, end, me: dict) -> dict:
    """Pelengkap :func:`services.performance`: tren harian/mingguan, radar,
    kalender 90 hari, sebaran titik kerja, riwayat, dan tugas terbuka."""
    activities = Activity.objects.filter(reported_by=target)
    in_period = activities.filter(
        started_at__date__gte=start, started_at__date__lte=end
    )
    effort = defaultdict(Decimal)
    for day, points in (
        in_period.order_by()
        .values_list("started_at__date")
        .annotate(points=Sum("effort_points"))
    ):
        effort[day] = points or Decimal("0")
    daily = []
    weekly = {}
    for item in me["days"]:
        day = datetime.date.fromisoformat(item["date"])
        present = item["status"] in enums.PRESENT_STATUSES
        row = {
            "date": item["date"],
            "activities": item["activities"],
            "points": float(effort.get(day, 0)),
            "present": present,
            "workday": item["workday"],
        }
        daily.append(row)
        week = weekly.setdefault(
            _week_key(day),
            {
                "week": _week_key(day),
                "start": item["date"],
                "activities": 0,
                "points": 0.0,
                "present": 0,
                "workdays": 0,
            },
        )
        week["activities"] += row["activities"]
        week["points"] += row["points"]
        week["present"] += int(present)
        week["workdays"] += int(item["workday"])
    total = in_period.count()
    complete = (
        in_period.filter(location__isnull=False)
        .annotate(n=Count("photos"))
        .filter(n__gt=0)
        .count()
    )
    radar = [
        {"key": "hadir", "label": _("Kehadiran"), "value": me["attendance_pct"]},
        {
            "key": "tepat",
            "label": _("Tepat waktu"),
            "value": me["on_time_pct"] if me["on_time_pct"] is not None else 0,
        },
        {"key": "volume", "label": _("Volume kerja"), "value": me["activity_pct"]},
        {"key": "tugas", "label": _("Tugas"), "value": me["task_pct"]},
        {
            "key": "lengkap",
            "label": _("Laporan lengkap"),
            "value": round(complete * 100 / total) if total else 0,
        },
    ]
    today = timezone.localdate()
    heat_start = today - datetime.timedelta(days=HEAT_DAYS - 1)
    counts = dict(
        activities.filter(started_at__date__gte=heat_start)
        .order_by()
        .values_list("started_at__date")
        .annotate(n=Count("pk"))
    )
    statuses = dict(
        Attendance.objects.filter(user=target, date__gte=heat_start).values_list(
            "date", "status"
        )
    )
    heat = [
        {
            "date": (heat_start + datetime.timedelta(days=i)).isoformat(),
            "activities": counts.get(heat_start + datetime.timedelta(days=i), 0),
            "status": statuses.get(heat_start + datetime.timedelta(days=i), ""),
        }
        for i in range(HEAT_DAYS)
    ]
    points = [
        {"lat": p.y, "lng": p.x, "kind": "kegiatan", "label": kind_label}
        for p, kind_label in (
            (a.location, a.get_activity_type_display())
            for a in in_period.exclude(location=None).only("location", "activity_type")[
                :MAX_POINTS
            ]
        )
    ]
    points += [
        {"lat": p.y, "lng": p.x, "kind": "absen", "label": _("Absen masuk")}
        for p in Attendance.objects.filter(user=target, date__gte=start, date__lte=end)
        .exclude(check_in_location=None)
        .values_list("check_in_location", flat=True)[:MAX_POINTS]
    ]
    tasks = (
        task_flow.visible_tasks(target)
        .filter(assignee=target, status__in=aset_enums.OPEN_TASK_STATUSES)
        .order_by("due_date", "pk")[:20]
    )
    return {
        "daily": daily,
        "weekly": list(weekly.values()),
        "radar": radar,
        "heat": heat,
        "points": points,
        "recent": [
            {
                "id": a.pk,
                "number": a.number,
                "title": a.title,
                "type_label": a.get_activity_type_display(),
                "korwil": a.korwil.code if a.korwil_id else "",
                "at": _local(a.started_at),
                "points": float(a.effort_points),
                "verified": a.verified,
            }
            for a in activities.select_related("korwil").order_by("-started_at", "-pk")[
                :15
            ]
        ],
        "tasks": [
            {
                "id": t.pk,
                "number": t.number,
                "title": t.title,
                "status_label": t.get_status_display(),
                "due_date": t.due_date.isoformat() if t.due_date else "",
                "overdue": t.is_overdue,
                "points": t.point_value,
            }
            for t in tasks
        ],
    }


# --------------------------------------------------------------------------
# Wawasan
# --------------------------------------------------------------------------


def _ai_or(fallback: str, material: str) -> tuple[str, bool]:
    from asetlahan import ai

    if not ai.enabled():
        return fallback, False
    try:
        response = ai.create(
            max_tokens=800,
            system=INSIGHT_PROMPT,
            messages=[{"role": "user", "content": material[:30_000]}],
        )
        text = ai.text_of(response).strip()
    except ai.AIError as error:
        LOG.warning("Wawasan AI gagal: %s", error)
        return fallback, False
    return (text, True) if text else (fallback, False)


def _row_line(row) -> str:
    return (
        f"{row['user']}: skor {row['score']} ({row['grade']}), hadir "
        f"{row['attendance_pct']}%, tepat waktu {row['on_time_pct']}%, kegiatan "
        f"{row['activities']}/{row['activity_target']}, komsos {row.get('komsos', 0)}, "
        f"tugas tepat waktu {row['task_pct']}%, tren {row.get('trend', '-')}"
    )


def board_insight(data) -> tuple[str, bool]:
    rows = data["results"]
    if not rows:
        return _("Belum ada anggota tim pada periode ini."), False
    lines = []
    best = rows[0]
    lines.append(
        _("- Teratas: %(name)s dengan skor %(score)s (%(grade)s).")
        % {"name": best["user"], "score": best["score"], "grade": best["grade"]}
    )
    if data["average"] is not None:
        lines.append(
            _("- Rata-rata skor tim %(avg)s dari %(n)d petugas.")
            % {"avg": data["average"], "n": data["count"]}
        )
    weak = [r for r in rows if r["grade"] == "D"]
    if weak:
        lines.append(
            _("- Perlu pembinaan (nilai D): %(names)s.")
            % {"names": ", ".join(r["user"] for r in weak[:5])}
        )
    absent = [r for r in rows if r["attendance_pct"] < 80]
    if absent:
        lines.append(
            _("- Kehadiran di bawah 80%%: %(names)s.")
            % {"names": ", ".join(r["user"] for r in absent[:5])}
        )
    falling = [r for r in rows if r.get("trend") == "turun"]
    if falling:
        lines.append(
            _("- Peringkat turun dibanding periode lalu: %(names)s.")
            % {"names": ", ".join(r["user"] for r in falling[:5])}
        )
    low_volume = [r for r in rows if r["activity_pct"] < 50]
    if low_volume:
        lines.append(
            _(
                "- Saran: dampingi %(names)s menyusun rencana kunjungan harian agar "
                "volume kegiatan mencapai target."
            )
            % {"names": ", ".join(r["user"] for r in low_volume[:3])}
        )
    fallback = "\n".join(lines)
    material = (
        f"Periode {data['start']} s/d {data['end']}. Rata-rata {data['average']}.\n"
        + "\n".join(_row_line(r) for r in rows[:60])
    )
    return _ai_or(fallback, material)


def personal_insight(me: dict, detail: dict) -> tuple[str, bool]:
    lines = [
        _("- Skor %(score)s (%(grade)s) untuk %(start)s s/d %(end)s.")
        % {
            "score": me["score"],
            "grade": me["grade"],
            "start": me["start"],
            "end": me["end"],
        }
    ]
    weakest = min(detail["radar"], key=lambda r: r["value"])
    strongest = max(detail["radar"], key=lambda r: r["value"])
    lines.append(
        _("- Terkuat: %(s)s (%(sv)s%%). Terlemah: %(w)s (%(wv)s%%).")
        % {
            "s": strongest["label"],
            "sv": strongest["value"],
            "w": weakest["label"],
            "wv": weakest["value"],
        }
    )
    if me["tasks_overdue"]:
        lines.append(
            _("- Ada %(n)d tugas terlambat; selesaikan atau laporkan kendalanya.")
            % {"n": me["tasks_overdue"]}
        )
    if me["late_days"]:
        lines.append(
            _("- Terlambat absen %(n)d kali; usahakan tiba sebelum jam masuk.")
            % {"n": me["late_days"]}
        )
    if me["activity_pct"] < 100:
        lines.append(
            _(
                "- Volume kegiatan %(p)s%% dari target; tambah kunjungan/komsos terencana."
            )
            % {"p": me["activity_pct"]}
        )
    fallback = "\n".join(lines)
    material = (
        f"Petugas {me['user']}, periode {me['start']} s/d {me['end']}.\n"
        f"Skor {me['score']} ({me['grade']}); hadir {me['attendance_pct']}% "
        f"({me['present_days']} hari, terlambat {me['late_days']}); tepat waktu "
        f"{me['on_time_pct']}%; kegiatan {me['activities']}/{me['activity_target']} "
        f"({me['activity_count']} laporan, poin tugas {me['task_points']}); warga "
        f"dikunjungi {me['residents_visited']}; tugas tepat waktu "
        f"{me['tasks_on_time']}/{me['tasks_due']}, terlambat {me['tasks_overdue']}.\n"
        + "Radar: "
        + ", ".join(f"{r['label']} {r['value']}%" for r in detail["radar"])
    )
    return _ai_or(fallback, material)


def team_scope_korwils(user):
    """Korwil yang boleh dipakai sebagai filter peringkat."""
    if aset_scope.sees_all(user):
        return services.visible_korwils(user)
    return geo.visible_korwils(user).filter(
        Q(coordinator=user) | Q(pk__in=geo.user_korwils(user).values("pk"))
    )
