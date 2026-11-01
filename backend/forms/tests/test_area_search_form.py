import importlib

import pytest
from django.apps import apps

from forms.management.commands.generate_areasearch_form import (
    AREA_FORM_SECTION_IDENTIFIERS,
    initialize_area_search_form,
)
from forms.models import Answer, Entry, EntrySection, Section
from forms.validators.answer import nik_is_valid
from plotsearch.models.plot_search import InformationCheck

repair = importlib.import_module(
    "plotsearch.migrations.0004_area_form_section_identifiers"
)


@pytest.mark.django_db
def test_area_form_keeps_identifiers_used_by_backend_and_spa():
    form = initialize_area_search_form()
    identifiers = set(form.sections.values_list("identifier", flat=True))
    assert identifiers == set(AREA_FORM_SECTION_IDENTIFIERS)


@pytest.mark.django_db
def test_repair_migration_restores_identifiers_paths_and_information_checks(
    admin_user,
):
    form = initialize_area_search_form()
    broken = {
        "hakijan-tiedot": "data-pemohon",
        "yrityksen-tiedot": "data-badan-usaha",
        "yhteyshenkilo-company": "narahubung",
        "henkilon-tiedot": "data-perorangan",
        "yhteyshenkilo-1": "narahubung-1",
        "päätöksen-toimitus": "saya-setuju",
    }
    for good, bad in broken.items():
        Section.objects.filter(form=form, identifier=good).update(identifier=bad)
    answer = Answer.objects.create(form=form, user=admin_user)
    entry_section = EntrySection.objects.create(
        answer=answer, identifier="data-pemohon[0]"
    )
    InformationCheck.objects.filter(entry_section=entry_section).delete()
    field = form.sections.get(identifier="data-badan-usaha").fields.get(
        identifier="yrityksen-nimi"
    )
    entry = Entry.objects.create(
        entry_section=entry_section,
        field=field,
        value="PT Uji",
        path="data-pemohon[0].data-badan-usaha",
    )

    repair.forwards(apps, None)

    identifiers = set(form.sections.values_list("identifier", flat=True))
    assert identifiers == set(AREA_FORM_SECTION_IDENTIFIERS)
    entry_section.refresh_from_db()
    entry.refresh_from_db()
    assert entry_section.identifier == "hakijan-tiedot[0]"
    assert entry.path == "hakijan-tiedot[0].yrityksen-tiedot"
    assert InformationCheck.objects.filter(entry_section=entry_section).count() == 7

    # Formulir yang sudah benar tidak berubah saat migrasi diulang.
    repair.forwards(apps, None)
    assert InformationCheck.objects.filter(entry_section=entry_section).count() == 7


@pytest.mark.parametrize(
    "value,valid",
    [
        ("2171014507900001", True),  # perempuan: tanggal + 40
        ("2171010507900001", True),
        ("2171014507G00001", False),
        ("217101450790000", False),
        ("0071014507900001", False),
        ("2171014507900000", False),
        ("2171013213900001", False),  # bulan 13
        ("010181-900C", False),
    ],
)
def test_nik_validation_matches_spa(value, valid):
    assert nik_is_valid(value) is valid
