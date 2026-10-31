"""Beranda, detail Korwil, dan Historis pusat komando.

Semua angka dihitung hanya dari data yang boleh dilihat pengguna (lingkup
Korwil dari :mod:`operasi.geo`).
"""

import datetime
from collections import Counter, defaultdict
from decimal import Decimal

from django.db.models import Count, Max, Q
from django.utils import timezone
from django.utils.translation import gettext as _

from operasi import enums, geo, hierarchy, services
from operasi.models import (
    Activity,
    ActivityWeight,
    CommandSettings,
    LandAreaChange,
    Resident,
    SoilTest,
    StanceChange,
)

Stance = enums.Stance
TREND_WEEKS = 12
STANCE_ORDER = (Stance.SUPPORT, Stance.NEUTRAL, Stance.OPPOSE, Stance.UNKNOWN)
# Urutan dukungan untuk menilai perubahan sikap membaik/memburuk.
STANCE_RANK = {Stance.OPPOSE: 0, Stance.NEUTRAL: 1, Stance.SUPPORT: 2}
LIST_LIMIT = 200
KORWIL_RESIDENT_LIMIT = 500


def _name(user) -> str:
    if user is None:
        return "—"
    return user.get_full_name() or user.get_username()


def _local(moment) -> str:
    return timezone.localtime(moment).isoformat() if moment else ""


def _end_of(day) -> datetime.datetime:
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time.max))


def stance_counts(queryset) -> dict:
    counts = dict(
        queryset.order_by().values_list("stance").annotate(n=Count("pk", distinct=True))
    )
    data = {str(s): counts.get(s, 0) for s in STANCE_ORDER}
    data["total"] = sum(data.values())
    known = data["total"] - data[Stance.UNKNOWN]
    for stance in (Stance.SUPPORT, Stance.NEUTRAL, Stance.OPPOSE):
        data[f"{stance}_pct"] = services.pct(data[stance], known)
    return data


def support_trend(residents, weeks: int = TREND_WEEKS) -> list[dict]:
    """Sebaran sikap warga di akhir tiap pekan, direkonstruksi dari riwayat
    perubahan sikap (warga yang belum terdata saat itu tidak dihitung)."""
    today = timezone.localdate()
    days = [today - datetime.timedelta(days=7 * i) for i in reversed(range(weeks))]
    moments = [_end_of(day) for day in days]
    rows = list(residents.order_by().values_list("pk", "stance", "created_at"))
    changes = defaultdict(list)
    for resident_id, old, at in (
        StanceChange.objects.filter(
            resident__in=residents.values("pk"), changed_at__gt=moments[0]
        )
        .order_by("changed_at", "pk")
        .values_list("resident_id", "old_stance", "changed_at")
    ):
        changes[resident_id].append((at, old))
    points = []
    for day, moment in zip(days, moments):
        counter = Counter()
        for resident_id, stance, created_at in rows:
            if created_at > moment:
                continue
            for at, old in changes.get(resident_id, ()):
                if at > moment:
                    stance = old
                    break
            counter[stance] += 1
        total = sum(counter.values())
        known = total - counter[Stance.UNKNOWN]
        points.append(
            {
                "date": day.isoformat(),
                "total": total,
                **{str(s): counter[s] for s in STANCE_ORDER},
                "pro_pct": services.pct(counter[Stance.SUPPORT], known),
                "contra_pct": services.pct(counter[Stance.OPPOSE], known),
                "neutral_pct": services.pct(counter[Stance.NEUTRAL], known),
            }
        )
    return points


# --------------------------------------------------------------------------
# Beranda
# --------------------------------------------------------------------------


def home(user) -> dict:
    residents = geo.scoped(Resident.objects.all(), user)
    activities = geo.scoped(Activity.objects.all(), user)
    week_start = timezone.localdate() - datetime.timedelta(days=6)
    counts = services.resident_counts(residents)
    korwils = list(
        services.visible_korwils(user)
        .select_related("coordinator")
        .annotate(member_count=Count("members", distinct=True))
        .order_by("code")
    )
    per_korwil = defaultdict(Counter)
    for korwil_id, stance, n in (
        residents.exclude(korwil=None)
        .order_by()
        .values_list("korwil", "stance")
        .annotate(n=Count("pk", distinct=True))
    ):
        per_korwil[korwil_id][stance] += n
    released = dict(
        residents.exclude(korwil=None)
        .filter(services.released_q())
        .order_by()
        .values_list("korwil")
        .annotate(n=Count("pk", distinct=True))
    )
    recent = dict(
        activities.filter(started_at__date__gte=week_start)
        .exclude(korwil=None)
        .order_by()
        .values_list("korwil")
        .annotate(n=Count("pk"))
    )
    rows = []
    for korwil in korwils:
        stances = per_korwil.get(korwil.pk, Counter())
        total = sum(stances.values())
        known = total - stances[Stance.UNKNOWN]
        rows.append(
            {
                "id": korwil.pk,
                "code": korwil.code,
                "name": korwil.name,
                "color": korwil.color,
                "coordinator": (
                    _name(korwil.coordinator) if korwil.coordinator_id else ""
                ),
                "members": korwil.member_count,
                "residents": total,
                "target": korwil.target_households,
                "target_pct": services.pct(total, korwil.target_households or 0),
                "pro": stances[Stance.SUPPORT],
                "neutral": stances[Stance.NEUTRAL],
                "contra": stances[Stance.OPPOSE],
                "unknown": stances[Stance.UNKNOWN],
                "pro_pct": services.pct(stances[Stance.SUPPORT], known),
                "released_pct": services.pct(released.get(korwil.pk, 0), total),
                "activities_week": recent.get(korwil.pk, 0),
            }
        )
    by_type = (
        activities.filter(started_at__date__gte=week_start)
        .order_by()
        .values_list("activity_type")
        .annotate(n=Count("pk"))
        .order_by("-n")
    )
    soil = dict(
        geo.scoped(SoilTest.objects.all(), user)
        .order_by()
        .values_list("suitability")
        .annotate(n=Count("pk"))
    )
    return {
        "counts": counts,
        "stances": stance_counts(residents),
        "trend": support_trend(residents),
        "korwils": rows,
        "activities_week": [
            {
                "type": kind,
                "label": str(enums.ActivityType(kind).label),
                "color": enums.ACTIVITY_COLORS.get(kind, "#57606a"),
                "count": n,
            }
            for kind, n in by_type
            if kind in enums.ActivityType.values
        ],
        "soil": [
            {"value": str(value), "label": str(label), "count": soil.get(value, 0)}
            for value, label in enums.SoilSuitability.choices
        ],
        "updated_at": timezone.now().isoformat(),
    }


# --------------------------------------------------------------------------
# Detail Korwil
# --------------------------------------------------------------------------


def korwil_detail(user, korwil) -> dict:
    """Ringkasan satu Korwil. Skor anggota hanya untuk petugas yang kinerjanya
    boleh dilihat (:func:`services.team_users`); daftar warga dan kegiatan
    mengikuti izin lihat masing-masing."""
    residents = geo.scoped(Resident.objects.filter(korwil=korwil), user)
    activities = geo.scoped(Activity.objects.filter(korwil=korwil), user)
    team = set(services.team_users(user).values_list("pk", flat=True))
    show_residents = user.has_perm("operasi.view_resident")
    show_activities = user.has_perm("operasi.view_activity")
    start, end = services.period_bounds("bulan")
    config = CommandSettings.load()
    weights = ActivityWeight.points_map()
    people = list(korwil.members.filter(is_active=True))
    if korwil.coordinator_id and korwil.coordinator not in people:
        people.insert(0, korwil.coordinator)
    members = []
    for person in people:
        row = {
            "id": person.pk,
            "name": _name(person),
            "role": (
                _("Koordinator") if person.pk == korwil.coordinator_id else _("Anggota")
            ),
            "position": hierarchy.position_of(person),
            "score": None,
            "grade": "",
            "attendance_pct": None,
            "activities": None,
            "residents_visited": None,
        }
        if person.pk in team:
            perf = services.performance(person, start, end, config, weights)
            for key in (
                "score",
                "grade",
                "attendance_pct",
                "activities",
                "residents_visited",
            ):
                row[key] = perf[key]
        members.append(row)
    members.sort(
        key=lambda m: (m["score"] is None, -(m["score"] or 0), m["name"].lower())
    )
    komsos = Q(activities__activity_type=enums.ActivityType.KOMSOS)
    grouped = {str(s): [] for s in STANCE_ORDER}
    for resident in (
        (residents if show_residents else residents.none())
        .annotate(
            komsos_count=Count("activities", filter=komsos, distinct=True),
            last_komsos=Max("activities__started_at", filter=komsos),
        )
        .order_by("head_name")[:KORWIL_RESIDENT_LIMIT]
    ):
        grouped[resident.stance].append(
            {
                "id": resident.pk,
                "number": resident.number,
                "name": resident.head_name,
                "village": resident.village,
                "komsos": resident.komsos_count,
                "last_komsos": _local(resident.last_komsos),
                "last_visited": (
                    resident.last_visited_on.isoformat()
                    if resident.last_visited_on
                    else ""
                ),
            }
        )
    week_start = timezone.localdate() - datetime.timedelta(days=6)
    month_start = timezone.localdate() - datetime.timedelta(days=29)
    return {
        "id": korwil.pk,
        "code": korwil.code,
        "name": korwil.name,
        "color": korwil.color,
        "villages": korwil.villages,
        "coordinator": _name(korwil.coordinator) if korwil.coordinator_id else "",
        "target": korwil.target_households,
        "counts": services.resident_counts(residents),
        "stances": stance_counts(residents),
        "activities_week": activities.filter(started_at__date__gte=week_start).count(),
        "activities_month": activities.filter(
            started_at__date__gte=month_start
        ).count(),
        "members": members,
        "residents": grouped,
        "residents_truncated": (
            show_residents and residents.count() > KORWIL_RESIDENT_LIMIT
        ),
        "show_residents": show_residents,
        "recent": [
            {
                "id": a.pk,
                "number": a.number,
                "title": a.title,
                "type_label": a.get_activity_type_display(),
                "by": _name(a.reported_by),
                "at": _local(a.started_at),
                "points": float(a.effort_points),
            }
            for a in (activities if show_activities else activities.none())
            .select_related("reported_by")
            .order_by("-started_at", "-pk")[:15]
        ],
        "trend": support_trend(residents, weeks=8),
    }


# --------------------------------------------------------------------------
# Historis
# --------------------------------------------------------------------------


def can_view_history(user) -> bool:
    """Riwayat lintas petugas: koordinator, atasan, dan pengawas."""
    if not user.has_perm("operasi.view_resident"):
        return False
    if geo.is_supervisor(user) or hierarchy.descendant_ids(user):
        return True
    return services.team_users(user).exclude(pk=user.pk).exists()


def _stance_direction(old, new) -> str:
    if old == Stance.UNKNOWN and new != Stance.UNKNOWN:
        return "teridentifikasi"
    if old in STANCE_RANK and new in STANCE_RANK:
        if STANCE_RANK[new] > STANCE_RANK[old]:
            return "membaik"
        if STANCE_RANK[new] < STANCE_RANK[old]:
            return "memburuk"
    return "lainnya"


def komsos_ranking(user, start, end, korwil=None) -> list[dict]:
    """Komsos per petugas: jumlah kegiatan, warga baru (didata lewat komsos
    itu), kunjungan berulang, dan warga unik."""
    komsos = geo.scoped(
        Activity.objects.filter(
            activity_type=enums.ActivityType.KOMSOS,
            started_at__date__gte=start,
            started_at__date__lte=end,
        ),
        user,
    ).exclude(reported_by=None)
    if korwil is not None:
        komsos = komsos.filter(korwil=korwil)
    stats = defaultdict(
        lambda: {"activities": 0, "new": 0, "repeat": 0, "unique": set()}
    )
    names = {}
    for user_id, first, last, username in komsos.values_list(
        "reported_by",
        "reported_by__first_name",
        "reported_by__last_name",
        "reported_by__username",
    ):
        stats[user_id]["activities"] += 1
        names[user_id] = f"{first} {last}".strip() or username
    through = Activity.residents.through
    for activity_id, resident_id, user_id, registered_id in through.objects.filter(
        activity__in=komsos.values("pk")
    ).values_list(
        "activity_id",
        "resident_id",
        "activity__reported_by",
        "resident__registered_activity_id",
    ):
        row = stats[user_id]
        if registered_id == activity_id:
            row["new"] += 1
        else:
            row["repeat"] += 1
        row["unique"].add(resident_id)
    rows = [
        {
            "user_id": user_id,
            "user": names.get(user_id, "—"),
            "activities": row["activities"],
            "new": row["new"],
            "repeat": row["repeat"],
            "unique": len(row["unique"]),
        }
        for user_id, row in stats.items()
    ]
    rows.sort(key=lambda r: (-r["activities"], -r["unique"], r["user"]))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def stance_history(user, start, end, korwil=None) -> dict:
    changes = (
        StanceChange.objects.filter(
            geo.korwil_q(user, "resident__korwil", "resident__created_by"),
            changed_at__date__gte=start,
            changed_at__date__lte=end,
        )
        .select_related("resident__korwil", "changed_by")
        .order_by("-changed_at", "-pk")
    )
    if korwil is not None:
        changes = changes.filter(resident__korwil=korwil)
    totals = Counter()
    per_korwil = defaultdict(Counter)
    items = []
    for change in changes:
        direction = _stance_direction(change.old_stance, change.new_stance)
        totals[direction] += 1
        code = change.resident.korwil.code if change.resident.korwil_id else "—"
        per_korwil[code][direction] += 1
        if len(items) < LIST_LIMIT:
            items.append(
                {
                    "resident_id": change.resident_id,
                    "resident": change.resident.head_name,
                    "korwil": "" if code == "—" else code,
                    "old": change.old_stance,
                    "old_label": change.get_old_stance_display(),
                    "new": change.new_stance,
                    "new_label": change.get_new_stance_display(),
                    "direction": direction,
                    "by": _name(change.changed_by),
                    "at": _local(change.changed_at),
                }
            )
    return {
        "totals": {
            key: totals[key]
            for key in ("membaik", "memburuk", "teridentifikasi", "lainnya")
        },
        "per_korwil": [
            {
                "korwil": code,
                "membaik": counter["membaik"],
                "memburuk": counter["memburuk"],
                "teridentifikasi": counter["teridentifikasi"],
                "net": counter["membaik"] - counter["memburuk"],
            }
            for code, counter in sorted(per_korwil.items())
        ],
        "items": items,
    }


def land_history(user, start, end, korwil=None) -> dict:
    changes = (
        LandAreaChange.objects.filter(
            geo.korwil_q(user, "resident__korwil", "resident__created_by"),
            changed_at__date__gte=start,
            changed_at__date__lte=end,
        )
        .select_related("resident__korwil", "changed_by")
        .order_by("-changed_at", "-pk")
    )
    if korwil is not None:
        changes = changes.filter(resident__korwil=korwil)
    increased = decreased = 0
    net = Decimal("0")
    items = []
    for change in changes:
        delta = change.delta_m2
        net += delta
        increased += delta > 0
        decreased += delta < 0
        if len(items) < LIST_LIMIT:
            items.append(
                {
                    "resident_id": change.resident_id,
                    "resident": change.resident.head_name,
                    "korwil": (
                        change.resident.korwil.code if change.resident.korwil_id else ""
                    ),
                    "old": (
                        float(change.old_area_m2)
                        if change.old_area_m2 is not None
                        else None
                    ),
                    "new": (
                        float(change.new_area_m2)
                        if change.new_area_m2 is not None
                        else None
                    ),
                    "delta": float(delta),
                    "by": _name(change.changed_by),
                    "at": _local(change.changed_at),
                }
            )
    return {
        "increased": increased,
        "decreased": decreased,
        "net_m2": float(net),
        "items": items,
    }


def history(user, start, end, korwil=None) -> dict:
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "komsos": komsos_ranking(user, start, end, korwil),
        "stance": stance_history(user, start, end, korwil),
        "land": land_history(user, start, end, korwil),
    }
