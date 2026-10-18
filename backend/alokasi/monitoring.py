"""Pemantauan pasca-alokasi: lahan tidur, kewajiban lapor, tagihan, masa berlaku."""

import datetime

from django.db.models import Exists, Max, OuterRef
from django.utils import timezone

from alokasi import enums
from alokasi.models import Allocation, AllocationSettings, DevelopmentReport, Invoice


def _years_ago(date: datetime.date, years: int) -> datetime.date:
    try:
        return date.replace(year=date.year - years)
    except ValueError:  # 29 Februari
        return date.replace(year=date.year - years, day=28)


def idle_queryset(queryset=None):
    """Alokasi aktif yang lewat batas waktu dan belum mulai konstruksi."""
    queryset = Allocation.objects.all() if queryset is None else queryset
    config = AllocationSettings.load()
    cutoff = _years_ago(timezone.localdate(), config.idle_years)
    started = DevelopmentReport.objects.filter(
        allocation=OuterRef("pk"),
        stage__in=(
            enums.DevelopmentStage.CONSTRUCTION,
            enums.DevelopmentStage.OPERATIONAL,
        ),
    )
    return queryset.filter(
        status=enums.AllocationStatus.ACTIVE, start_date__lte=cutoff
    ).exclude(Exists(started))


def report_deadline(last: datetime.date, months: int) -> datetime.date:
    return last + datetime.timedelta(days=round(months * 30.44))


def overdue_report_allocations():
    config = AllocationSettings.load()
    today = timezone.localdate()
    rows = (
        Allocation.objects.filter(status=enums.AllocationStatus.ACTIVE)
        .annotate(last_report=Max("development_reports__report_date"))
        .select_related("holder", "holder__user", "plot")
    )
    return [
        a
        for a in rows
        if today
        >= report_deadline(a.last_report or a.start_date, config.report_interval_months)
    ]


def expire_allocations() -> list[Allocation]:
    expired = list(
        Allocation.objects.filter(
            status=enums.AllocationStatus.ACTIVE, end_date__lt=timezone.localdate()
        ).select_related("holder", "plot")
    )
    for allocation in expired:
        allocation.status = enums.AllocationStatus.EXPIRED
        allocation.save(update_fields=["status", "modified_at"])
    return expired


def invoices_needing_payment(days: int = 7):
    """Tagihan belum lunas yang jatuh tempo dalam `days` hari atau sudah lewat."""
    limit = timezone.localdate() + datetime.timedelta(days=days)
    return Invoice.objects.filter(
        status=enums.InvoiceStatus.UNPAID, due_date__lte=limit
    ).select_related(
        "application", "application__applicant", "application__applicant__user"
    )
