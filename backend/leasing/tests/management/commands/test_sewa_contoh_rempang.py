import pytest
from django.core.management import call_command

from forms.models import Answer, EntrySection
from forms.serializers.form import AnswerSerializer
from leasing.management.commands.sewa_contoh_rempang import (
    AREA_SEARCHES,
    sample_area_searches,
    sample_contacts,
    sample_leases,
)
from leasing.models import Invoice, Rent, Tenant
from plotsearch.models import AreaSearchIntendedUse
from plotsearch.models.plot_search import AreaSearchStatus, InformationCheck
from plotsearch.utils import get_applicant
from utils.production_check import _sample_data


@pytest.fixture
def area_search_uses():
    for _code, name, *_rest in AREA_SEARCHES:
        AreaSearchIntendedUse.objects.get_or_create(name=name)


@pytest.mark.django_db
def test_sewa_contoh_is_complete_idempotent_and_fully_removable(
    admin_user, area_search_uses
):
    statuses_before = AreaSearchStatus.objects.count()

    call_command("sewa_contoh_rempang")
    call_command("sewa_contoh_rempang")

    leases = sample_leases()
    assert leases.count() == 3
    assert sample_contacts().count() == 6
    assert Tenant.objects.filter(lease__in=leases).count() == 4
    invoices = Invoice.objects.filter(lease__in=leases)
    assert invoices.filter(outstanding_amount=0).exists()
    assert invoices.filter(outstanding_amount__gt=0).exists()
    # Tagihan contoh tidak memakai nomor urut tagihan sungguhan.
    assert not invoices.exclude(number=None).exists()
    rents = Rent.objects.filter(lease__in=leases, payable_rent_amount__gt=0)
    assert rents.count() == 2

    area_searches = sample_area_searches()
    assert area_searches.count() == len(AREA_SEARCHES)
    for area_search in area_searches:
        applicants = []
        get_applicant(area_search.answer, applicants)
        assert applicants, area_search.identifier
        data = AnswerSerializer(area_search.answer).data
        assert "hakijan-tiedot[0]" in data["entries_data"]
        assert len(data["information_checks"]) == 7
    assert any("sewa contoh" in f.message for f in _sample_data())
    assert any("pencarian area contoh" in f.message for f in _sample_data())

    call_command("sewa_contoh_rempang", "--hapus")

    assert not sample_leases().exists()
    assert not sample_contacts().exists()
    assert not Invoice.objects.filter(lease__in=leases).exists()
    assert not sample_area_searches().exists()
    assert not Answer.objects.filter(area_search__isnull=False).exists()
    assert not EntrySection.objects.filter(answer__isnull=True).exists()
    assert not InformationCheck.objects.exists()
    assert AreaSearchStatus.objects.count() == statuses_before

    call_command("sewa_contoh_rempang")
    assert sample_leases().count() == 3
    assert sample_area_searches().count() == len(AREA_SEARCHES)
