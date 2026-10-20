import datetime
from decimal import Decimal

from django.utils import translation

from leasing.models import Vat


def test_vat_str_without_end_date_does_not_show_none():
    vat = Vat(percent=Decimal("11.0"), start_date=datetime.date(2022, 4, 1))
    with translation.override("id"):
        assert str(vat) == "PPN 11.0% mulai 2022-04-01"
    vat.end_date = datetime.date(2024, 12, 31)
    with translation.override("id"):
        assert str(vat) == "PPN 11.0% 2022-04-01 - 2024-12-31"
