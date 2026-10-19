"""Peringatan & tenggat lintas modul (dipakai dasbor, pengingat otomatis, asisten)."""

import datetime

from django.db.models import DateField, ExpressionWrapper, F, Max, Q
from django.db.models.functions import Cast, Coalesce, Greatest, TruncDate
from django.utils import timezone
from django.utils.translation import gettext as _

from asetlahan import enums, scope
from asetlahan.models import (
    CaseHearing,
    EncroachmentCase,
    Grievance,
    LandAsset,
    LiaisonActivity,
    ModuleSettings,
    Task,
    TaxObligation,
)


def _today() -> datetime.date:
    return timezone.localdate()


def _scoped(queryset, user, lookup="service_unit"):
    return scope.scoped(queryset, user, lookup) if user is not None else queryset


def last_activity(case) -> datetime.date:
    """Tanggal tindakan terakhir atas kasus okupasi (atau tanggal ditemukan)."""
    latest = case.actions.aggregate(last=Max("date"))["last"]
    return max(filter(None, [case.detected_on, latest]))


def leases_ending(days: int, user=None):
    from leasing.models import Lease

    today = _today()
    queryset = Lease.objects.filter(
        end_date__gte=today, end_date__lte=today + datetime.timedelta(days=days)
    ).select_related("identifier", "municipality")
    return _scoped(queryset, user).order_by("end_date")


def titles_expiring(days: int, user=None):
    today = _today()
    queryset = LandAsset.objects.filter(
        title_expiry__isnull=False,
        title_expiry__lte=today + datetime.timedelta(days=days),
    )
    return (
        _scoped(queryset, user)
        .exclude(status=enums.AssetStatus.RELEASED)
        .order_by("title_expiry")
    )


def taxes_due(days: int, user=None):
    queryset = TaxObligation.objects.filter(
        paid_date__isnull=True, due_date__lte=_today() + datetime.timedelta(days=days)
    ).select_related("asset")
    return _scoped(queryset, user, "asset__service_unit").order_by("due_date")


def hearings_upcoming(days: int, user=None):
    now = timezone.now()
    queryset = CaseHearing.objects.filter(
        scheduled_at__gte=now, scheduled_at__lte=now + datetime.timedelta(days=days)
    ).select_related("case")
    return _scoped(queryset, user, "case__service_unit").order_by("scheduled_at")


def tasks_overdue(user=None):
    queryset = Task.objects.filter(
        status__in=enums.OPEN_TASK_STATUSES, due_date__lt=_today()
    ).select_related("assignee", "team")
    return _scoped(queryset, user).order_by("due_date")


def grievances_overdue(user=None):
    queryset = Grievance.objects.filter(
        status__in=enums.OPEN_GRIEVANCE_STATUSES, due_date__lt=_today()
    )
    return _scoped(queryset, user).order_by("due_date")


def stale_encroachments(days: int, user=None):
    cutoff = _today() - datetime.timedelta(days=days)
    queryset = (
        EncroachmentCase.objects.filter(status__in=enums.OPEN_ENCROACHMENT_STATUSES)
        .annotate(
            last_action=Greatest(
                "detected_on", Coalesce(Max("actions__date"), "detected_on")
            )
        )
        .filter(last_action__lt=cutoff)
        .select_related("asset", "responsible")
    )
    return _scoped(queryset, user).order_by("last_action")


def monitoring_overdue(user=None, default_days: int | None = None):
    """Aset yang belum dipantau di lapangan melewati jadwal pemantauannya."""
    if default_days is None:
        default_days = ModuleSettings.load().monitoring_interval_days
    today = _today()
    queryset = (
        LandAsset.objects.exclude(status=enums.AssetStatus.RELEASED)
        .annotate(
            monitored_base=Coalesce(
                "last_monitored_on", "acquisition_date", TruncDate("created_at")
            ),
            interval=Coalesce("monitoring_interval_days", default_days),
        )
        .filter(interval__gt=0)
        .annotate(
            monitoring_due=ExpressionWrapper(
                Cast(
                    F("monitored_base") + F("interval") * datetime.timedelta(days=1),
                    DateField(),
                ),
                output_field=DateField(),
            )
        )
        .filter(Q(monitoring_due__lt=today))
        .select_related("responsible")
    )
    return _scoped(queryset, user).order_by("monitoring_due")


def liaison_followups(user=None):
    queryset = LiaisonActivity.objects.filter(
        next_follow_up__lte=_today(),
        status__in=[
            enums.LiaisonStatus.PREPARING,
            enums.LiaisonStatus.SUBMITTED,
            enums.LiaisonStatus.PROCESSING,
        ],
    )
    return _scoped(queryset, user).order_by("next_follow_up")


def alerts(user) -> list[dict]:
    """Ringkasan peringatan yang terlihat oleh pengguna, untuk dasbor."""
    config = ModuleSettings.load()
    checks = [
        (
            "leasing.view_lease",
            "",
            _("Sewa berakhir ≤ %d hari") % config.lease_alert_days,
            lambda: leases_ending(config.lease_alert_days, user),
            "admin:leasing_lease_changelist",
        ),
        (
            "asetlahan.view_landasset",
            "",
            _("Hak atas tanah berakhir ≤ %d hari") % config.title_alert_days,
            lambda: titles_expiring(config.title_alert_days, user),
            "admin:asetlahan_landasset_changelist",
        ),
        (
            "asetlahan.view_taxobligation",
            "enable_valuation",
            _("Pajak jatuh tempo ≤ %d hari / terlambat") % config.tax_alert_days,
            lambda: taxes_due(config.tax_alert_days, user),
            "admin:asetlahan_taxobligation_changelist",
        ),
        (
            "asetlahan.view_casehearing",
            "enable_litigation",
            _("Sidang ≤ %d hari") % config.hearing_alert_days,
            lambda: hearings_upcoming(config.hearing_alert_days, user),
            "admin:asetlahan_legalcase_changelist",
        ),
        (
            "asetlahan.view_task",
            "enable_tasks",
            _("Tugas lewat tenggat"),
            lambda: tasks_overdue(user),
            "admin:asetlahan_task_changelist",
        ),
        (
            "asetlahan.view_grievance",
            "enable_grievance",
            _("Pengaduan lewat batas"),
            lambda: grievances_overdue(user),
            "admin:asetlahan_grievance_changelist",
        ),
        (
            "asetlahan.view_encroachmentcase",
            "enable_encroachment",
            _("Okupasi tanpa tindak lanjut > %d hari")
            % config.encroachment_followup_days,
            lambda: stale_encroachments(config.encroachment_followup_days, user),
            "admin:asetlahan_encroachmentcase_changelist",
        ),
        (
            "asetlahan.view_landasset",
            "",
            _("Aset belum dipantau sesuai jadwal"),
            lambda: monitoring_overdue(user, config.monitoring_interval_days),
            "admin:asetlahan_landasset_changelist",
        ),
        (
            "asetlahan.view_liaisonactivity",
            "enable_survey",
            _("Urusan instansi perlu ditindaklanjuti"),
            lambda: liaison_followups(user),
            "admin:asetlahan_liaisonactivity_changelist",
        ),
    ]
    results = []
    for permission, flag, label, query, url_name in checks:
        if not user.has_perm(permission) or (flag and not getattr(config, flag)):
            continue
        items = list(query()[:5])
        count = query().count() if len(items) == 5 else len(items)
        results.append(
            {"label": label, "count": count, "items": items, "url_name": url_name}
        )
    return results
