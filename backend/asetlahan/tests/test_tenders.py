import datetime
from decimal import Decimal

import pytest
from django.core import mail
from django.utils import timezone

from asetlahan import enums, tenders
from asetlahan.models import Bid, Tender

pytestmark = pytest.mark.django_db


@pytest.fixture
def tender(make_asset):
    now = timezone.now()
    return Tender.objects.create(
        title="Dermaga",
        description="D",
        asset=make_asset(),
        reserve_price=Decimal("100"),
        open_at=now - datetime.timedelta(days=2),
        close_at=now - datetime.timedelta(minutes=1),
        status=enums.TenderStatus.ANNOUNCED,
    )


def test_award_picks_highest_bid_above_reserve(tender):
    low = Bid.objects.create(
        tender=tender, bidder_name="A", amount=Decimal("90"), email="a@x.id"
    )
    high = Bid.objects.create(
        tender=tender, bidder_name="B", amount=Decimal("150"), email="b@x.id"
    )
    mid = Bid.objects.create(
        tender=tender, bidder_name="C", amount=Decimal("120"), email="c@x.id"
    )
    winner = tenders.award(tender)
    assert winner == high
    tender.refresh_from_db()
    assert tender.status == enums.TenderStatus.AWARDED and tender.winner == high
    statuses = {b.pk: b.status for b in Bid.objects.all()}
    assert statuses[high.pk] == enums.BidStatus.WON
    assert statuses[mid.pk] == statuses[low.pk] == enums.BidStatus.LOST
    assert len(mail.outbox) == 3


def test_beauty_contest_uses_technical_score(tender):
    tender.method = enums.TenderMethod.BEAUTY_CONTEST
    tender.save()
    Bid.objects.create(
        tender=tender, bidder_name="A", amount=Decimal("500"), technical_score=70
    )
    best = Bid.objects.create(
        tender=tender, bidder_name="B", amount=Decimal("200"), technical_score=90
    )
    Bid.objects.create(tender=tender, bidder_name="C", amount=Decimal("900"))
    assert tenders.award(tender) == best


def test_award_refuses_open_tender(tender):
    tender.close_at = timezone.now() + datetime.timedelta(days=1)
    tender.save()
    Bid.objects.create(tender=tender, bidder_name="A", amount=Decimal("500"))
    with pytest.raises(tenders.TenderError):
        tenders.award(tender)


def test_award_without_eligible_bids(tender):
    Bid.objects.create(tender=tender, bidder_name="A", amount=Decimal("10"))
    with pytest.raises(tenders.TenderError):
        tenders.award(tender)
