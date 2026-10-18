"""Penetapan pemenang lelang / seleksi pemanfaatan lahan."""

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from asetlahan import enums, services
from asetlahan.models import Bid, Tender


class TenderError(Exception):
    pass


def eligible_bids(tender: Tender):
    bids = tender.bids.filter(
        status__in=[enums.BidStatus.SUBMITTED, enums.BidStatus.QUALIFIED]
    )
    if tender.reserve_price is not None:
        bids = bids.filter(amount__gte=tender.reserve_price)
    if tender.method == enums.TenderMethod.BEAUTY_CONTEST:
        return bids.filter(technical_score__isnull=False).order_by(
            "-technical_score", "-amount", "created_at"
        )
    return bids.order_by("-amount", "created_at")


def award(tender: Tender) -> Bid:
    """Pemenang: nilai tertinggi (lelang) atau nilai teknis tertinggi (seleksi)."""
    closed = tender.status == enums.TenderStatus.CLOSED or (
        tender.status == enums.TenderStatus.ANNOUNCED
        and tender.close_at <= timezone.now()
    )
    if not closed:
        raise TenderError(_("Penawaran belum ditutup."))
    winner = eligible_bids(tender).first()
    if winner is None:
        raise TenderError(
            _("Tidak ada penawaran yang memenuhi syarat (nilai limit / nilai teknis).")
        )
    with transaction.atomic():
        winner.status = enums.BidStatus.WON
        winner.save(update_fields=["status", "modified_at"])
        tender.bids.exclude(pk=winner.pk).exclude(
            status=enums.BidStatus.DISQUALIFIED
        ).update(status=enums.BidStatus.LOST)
        tender.winner = winner
        tender.status = enums.TenderStatus.AWARDED
        tender.awarded_on = timezone.localdate()
        tender.save(update_fields=["winner", "status", "awarded_on", "modified_at"])
    _notify_bidders(tender, winner)
    return winner


def _notify_bidders(tender: Tender, winner: Bid):
    for bid in tender.bids.all():
        result = (
            _("ditetapkan sebagai PEMENANG")
            if bid.pk == winner.pk
            else _("belum berhasil")
        )
        services.notify_contact(
            email=bid.email,
            phone=bid.phone,
            subject=_("Hasil %(n)s") % {"n": tender.number},
            body=_(
                "Penawaran Anda untuk %(t)s %(r)s. Terima kasih atas partisipasi Anda."
            )
            % {"t": tender.title, "r": result},
        )
