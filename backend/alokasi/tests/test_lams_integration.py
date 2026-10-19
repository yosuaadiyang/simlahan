import json

import pytest

from alokasi import services
from alokasi.importers import PlotImportError, import_plots
from alokasi.models import LandPlot
from asetlahan import assistant

from .test_workflow import approve_and_pay

pytestmark = pytest.mark.django_db


@pytest.fixture
def allocation(filled_application, officer, verifier):
    services.submit(filled_application, filled_application.applicant.user)
    approve_and_pay(filled_application, officer, verifier)
    return filled_application.allocation


def test_assistant_lists_allocations_by_period(allocation, officer, settings):
    settings.ANTHROPIC_API_KEY = ""
    issued = allocation.issued_date
    result = assistant.answer(officer, f"alokasi lahan tahun {issued.year}")
    table = result["tables"][0]
    assert allocation.kpt_number in str(table["rows"])
    assert table["note"].startswith("1 alokasi")
    other_year = assistant.allocations(officer, issued.year - 1)
    assert other_year["rows"] == []
    month = assistant.allocations(officer, issued.year, issued.month)
    assert len(month["rows"]) == 1


def test_assistant_allocations_need_permission(applicant):
    table = assistant.allocations(applicant.user)
    assert "tidak memiliki akses" in str(table)


def test_plot_import_drops_z_coordinates(seeded):
    feature = {
        "type": "Feature",
        "properties": {"kode": "Z-01", "nama": "Lahan GPS"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [104.1, 0.8, 7],
                    [104.101, 0.8, 7],
                    [104.101, 0.801, 8],
                    [104.1, 0.801, 8],
                    [104.1, 0.8, 7],
                ]
            ],
        },
    }
    data = json.dumps({"type": "FeatureCollection", "features": [feature]})
    assert import_plots(data) == (1, 0)
    assert not LandPlot.objects.get(code="Z-01").geometry.hasz


def test_plot_import_json_error_message_is_indonesian(seeded):
    with pytest.raises(PlotImportError) as excinfo:
        import_plots(b"bukan json")
    assert str(excinfo.value) == "Berkas bukan JSON yang valid (baris 1, kolom 1)."
