import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from asetlahan import enums as aset_enums
from asetlahan.models import Bid, ModuleSettings, Tender

pytestmark = pytest.mark.django_db


def _awarded_tender(plot, number):
    now = timezone.now()
    tender = Tender.objects.create(
        title=f"Seleksi {plot.name}",
        alokasi_plot=plot,
        reserve_price=Decimal("1000000"),
        open_at=now - datetime.timedelta(days=10),
        close_at=now - datetime.timedelta(days=3),
        status=aset_enums.TenderStatus.CLOSED,
    )
    winner = Bid.objects.create(
        tender=tender, bidder_name=f"Pemenang {number}", amount=Decimal("3000000")
    )
    Bid.objects.create(
        tender=tender, bidder_name=f"Peserta kalah {number}", amount=Decimal("2000000")
    )
    tender.status = aset_enums.TenderStatus.AWARDED
    tender.winner = winner
    tender.awarded_on = timezone.localdate()
    tender.save()
    return tender


def _page(client):
    response = client.get(reverse("portal:open_winners"))
    assert response.status_code == 200
    return response.content.decode()


def test_open_winners_lists_published_plots(client, make_plot):
    _awarded_tender(make_plot(code="LHN-TERBIT", name="Kavling Terbit"), 1)
    page = _page(client)
    assert "LHN-TERBIT" in page
    assert "Pemenang 1" in page and "Peserta kalah 1" in page


def test_open_winners_hides_unpublished_plot(client, make_plot):
    _awarded_tender(make_plot(code="LHN-TERBIT", name="Kavling Terbit"), 1)
    hidden = make_plot(code="LHN-DITARIK", name="Kavling Ditarik", is_published=False)
    _awarded_tender(hidden, 2)
    page = _page(client)
    assert "LHN-TERBIT" in page
    assert "LHN-DITARIK" not in page
    assert "Pemenang 2" not in page and "Peserta kalah 2" not in page
    # Sama dengan halaman detail lahan, yang menolak lahan tidak terbit.
    detail = client.get(reverse("portal:plot_detail", args=["LHN-DITARIK"]))
    assert detail.status_code == 404


def test_open_winners_empty_when_tender_module_disabled(client, make_plot):
    _awarded_tender(make_plot(code="LHN-TERBIT", name="Kavling Terbit"), 1)
    settings = ModuleSettings.load()
    settings.enable_tender = False
    settings.save()
    page = _page(client)
    assert "LHN-TERBIT" not in page
    assert "Pemenang 1" not in page and "Peserta kalah 1" not in page
