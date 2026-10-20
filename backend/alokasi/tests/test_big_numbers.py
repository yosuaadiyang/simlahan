"""Nominal & jangka waktu ekstrem: pesan jelas, bukan galat server."""

import json
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.template import Context, Template
from django.urls import reverse

from alokasi import enums, services
from alokasi.importers import PlotImportError, import_plots
from alokasi.models import Invoice
from alokasi.templatetags.alokasi_tags import rupiah

from .conftest import score_all

BIG = Decimal("987654321987654321.99")


def test_plot_with_uwt_total_beyond_invoice_limit_is_rejected(make_plot):
    plot = make_plot(area_m2=Decimal("98765432198765.43"), uwt_rate_per_m2_year=BIG)
    with pytest.raises(ValidationError, match="terlalu besar"):
        plot.clean()
    plot.area_m2 = Decimal("1000000")
    plot.uwt_rate_per_m2_year = Decimal("1000")
    plot.clean()


def test_plot_term_years_are_limited(make_plot):
    plot = make_plot(term_years=32000)
    with pytest.raises(ValidationError):
        plot.full_clean()


@pytest.mark.django_db
def test_import_rejects_out_of_range_term():
    feature = {
        "type": "Feature",
        "properties": {"kode": "LHN-X", "nama": "Uji", "jangka_tahun": 5000},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[104.1, 0.8], [104.11, 0.8], [104.11, 0.81], [104.1, 0.8]]
            ],
        },
    }
    data = {"type": "FeatureCollection", "features": [feature]}
    with pytest.raises(PlotImportError, match="jangka_tahun"):
        import_plots(json.dumps(data).encode())


def test_approval_with_overflowing_invoice_is_rolled_back(
    filled_application, officer, verifier
):
    application = filled_application
    services.submit(application, application.applicant.user)
    services.start_verification(application, officer)
    score_all(application, verifier, 80)
    # Tarif diubah langsung di basis data (melewati validasi formulir).
    plot = application.plot
    type(plot).objects.filter(pk=plot.pk).update(
        area_m2=Decimal("98765432198765.43"), uwt_rate_per_m2_year=BIG
    )
    application.refresh_from_db()
    with pytest.raises(ValidationError, match="terlalu besar"):
        services.approve(application, officer)
    application.refresh_from_db()
    assert application.status == enums.ApplicationStatus.VERIFYING
    assert not Invoice.objects.filter(application=application).exists()


def test_landplot_admin_change_page_with_huge_values(client, plot, django_user_model):
    type(plot).objects.filter(pk=plot.pk).update(
        area_m2=Decimal("98765432198765.43"), uwt_rate_per_m2_year=BIG
    )
    admin = django_user_model.objects.create_superuser(
        "kepala", "kepala@instansi.go.id", "RahasiaKuat123!"
    )
    client.force_login(admin)
    response = client.get(reverse("admin:alokasi_landplot_change", args=[plot.pk]))
    assert response.status_code == 200
    plot.refresh_from_db()
    assert rupiah(plot.uwt_total) in response.content.decode()


def test_patah_filter_inserts_soft_breaks_and_escapes():
    template = Template("{% load alokasi_tags %}{{ value|rupiah|patah }}|{{ t|patah }}")
    html = template.render(Context({"value": Decimal("1234567"), "t": "<b>1.2</b>"}))
    assert html == "Rp1.<wbr>234.<wbr>567|&lt;b&gt;1.<wbr>2&lt;/b&gt;"


def test_portal_plot_detail_breaks_long_area(client, plot):
    type(plot).objects.filter(pk=plot.pk).update(area_m2=Decimal("98765432198765.43"))
    response = client.get(reverse("portal:plot_detail", args=[plot.code]))
    assert response.status_code == 200
    assert "98.<wbr>765.<wbr>432.<wbr>198.<wbr>765,43 m²" in response.content.decode()


def test_rupiah_negative_sign_before_currency():
    assert rupiah(Decimal("-1975308643975308644")) == "-Rp1.975.308.643.975.308.644"
    assert rupiah(0) == "Rp0"
