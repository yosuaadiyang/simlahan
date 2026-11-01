import io

import pytest
from django.apps import apps
from django.core.management import CommandError, call_command

from utils.management.commands.data_contoh import (
    CHECKED_APPS,
    NOT_SAMPLED,
    SAMPLE_COMMANDS,
    coverage,
)
from utils.management.commands.hapus_data_contoh import (
    SAMPLE_COMMANDS as DELETE_COMMANDS,
)


def test_every_sample_command_is_also_deleted():
    assert set(SAMPLE_COMMANDS) == set(DELETE_COMMANDS)


def test_exclusions_name_real_models_with_a_reason():
    labels = {
        model._meta.label
        for app in CHECKED_APPS
        for model in apps.get_app_config(app).get_models()
    }
    assert set(NOT_SAMPLED) <= labels
    assert all(reason.strip() for reason in NOT_SAMPLED.values())


@pytest.mark.django_db
def test_check_reports_empty_tables_but_not_excluded_ones():
    empty, excluded = coverage()
    assert empty
    assert not set(empty) & set(NOT_SAMPLED)
    assert set(excluded) <= set(NOT_SAMPLED)
    with pytest.raises(CommandError, match="Tabel tanpa data"):
        call_command("data_contoh", "--cek", stdout=io.StringIO())


@pytest.mark.django_db
def test_delete_option_runs_delete_all():
    out = io.StringIO()
    call_command("data_contoh", "--hapus", stdout=out)
    assert "sewa_contoh_rempang --hapus" in out.getvalue()
    assert "pengguna_contoh --hapus" in out.getvalue()
