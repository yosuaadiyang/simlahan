"""Penentuan status bidang tanah secara otomatis berdasarkan bukti/peristiwa terakhir."""

from decimal import Decimal

from django.utils import timezone

from pengadaan import enums


def derive_parcel_status(parcel) -> str:  # noqa: C901
    P = enums.ParcelStatus
    if parcel.is_excluded:
        return P.EXCLUDED
    if not parcel.pk:
        return P.IDENTIFIED

    if parcel.handovers.exists():
        return P.HANDED_OVER
    if parcel.rights_releases.exists():
        return P.RELEASED

    compensations = [
        c
        for c in parcel.compensations.prefetch_related("payments")
        if c.status != enums.CompensationStatus.CANCELLED
    ]
    if compensations:
        total = sum((c.amount or Decimal("0") for c in compensations), Decimal("0"))
        paid = sum((c.paid_amount for c in compensations), Decimal("0"))
        in_kind_done = all(
            c.form != enums.CompensationForm.MONEY
            and c.status == enums.CompensationStatus.PAID
            for c in compensations
        )
        if (total > 0 and paid >= total) or in_kind_done:
            return P.PAID

    if parcel.consignments.filter(
        status__in=[
            enums.ConsignmentStatus.DEPOSITED,
            enums.ConsignmentStatus.COLLECTED,
        ]
    ).exists():
        return P.CONSIGNED

    if parcel.objections.filter(
        objection_type__in=[
            enums.ObjectionType.COMPENSATION,
            enums.ObjectionType.CASSATION,
        ],
        status__in=[enums.ObjectionStatus.FILED, enums.ObjectionStatus.IN_PROCESS],
    ).exists():
        return P.OBJECTION

    latest_result = (
        parcel.deliberation_results.select_related("deliberation")
        .order_by("-deliberation__held_on", "-id")
        .first()
    )
    if latest_result is not None:
        if latest_result.outcome == enums.DeliberationOutcome.AGREED:
            return P.AGREED
        return P.DELIBERATION

    if parcel.valuations.filter(status=enums.ValuationStatus.FINAL).exists():
        return P.VALUED

    surveyed = parcel.surveys.filter(status=enums.SurveyStatus.DONE).exists()
    if surveyed:
        announced = parcel.project.announcements.filter(
            announcement_type=enums.AnnouncementType.INVENTORY,
            announced_on__lte=timezone.localdate(),
        ).exists()
        return P.ANNOUNCED if announced else P.INVENTORIED

    return P.IDENTIFIED


SETTLED_CONSIGNMENT_STATUSES = (
    enums.ConsignmentStatus.DEPOSITED,
    enums.ConsignmentStatus.COLLECTED,
)


def consignment_coverage(parcel_id) -> tuple[bool, set[int]]:
    """Cakupan konsinyasi yang sudah dititipkan di pengadilan pada sebuah bidang.

    Mengembalikan (seluruh bidang tercakup, id pihak yang tercakup). Konsinyasi
    tanpa pihak mencakup semua pihak bidang tersebut.
    """
    from pengadaan.models import Consignment

    party_ids = set(
        Consignment.objects.filter(
            parcel_id=parcel_id, status__in=SETTLED_CONSIGNMENT_STATUSES
        ).values_list("party_id", flat=True)
    )
    covers_all = None in party_ids
    party_ids.discard(None)
    return covers_all, party_ids


def is_parcel_settled(parcel) -> bool:
    """Semua ganti kerugian bidang (yang tidak dibatalkan) sudah lunas/dititipkan.

    Bidang tanpa ganti kerugian dianggap selesai hanya bila ada konsinyasi
    yang sudah dititipkan.
    """
    compensations = list(
        parcel.compensations.exclude(status=enums.CompensationStatus.CANCELLED)
    )
    covers_all, party_ids = consignment_coverage(parcel.pk)
    if not compensations:
        return covers_all or bool(party_ids)
    return all(
        c.status in (enums.CompensationStatus.PAID, enums.CompensationStatus.CONSIGNED)
        or covers_all
        or (c.party_id is not None and c.party_id in party_ids)
        for c in compensations
    )
