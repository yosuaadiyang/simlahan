"""Pengerasan pusat komando: sikap AI, pencarian, ubin satelit, verifikasi
ulang klaim, dan catatan SOS (catatan hardening audit keamanan run 1)."""

from unittest import mock

import pytest
from django.contrib.auth.models import Permission

from operasi import enums, satellite, services
from operasi.models import Activity, Resident

pytestmark = pytest.mark.django_db


def test_ai_stance_does_not_write_residents_without_change_permission(field, korwil):
    resident = Resident.objects.create(head_name="Belum", korwil=korwil)
    activity = Activity.objects.create(
        activity_type=enums.ActivityType.KOMSOS,
        title="Komsos",
        description="Warga bersedia pindah ke hunian baru bila jadwal jelas.",
        korwil=korwil,
        reported_by=field,
    )
    activity.residents.set([resident])
    field.groups.clear()
    field.user_permissions.add(
        *Permission.objects.filter(codename__in=["add_activity", "view_resident"])
    )
    assert not field.has_perm("operasi.change_resident")
    response = mock.Mock(content=[mock.Mock(type="text", text="Pro")])
    with (
        mock.patch("asetlahan.ai.enabled", return_value=True),
        mock.patch("asetlahan.ai.create", return_value=response),
    ):
        assert services.apply_ai_stance(activity.pk, field.pk) == enums.Stance.SUPPORT
    resident.refresh_from_db()
    assert resident.stance == enums.Stance.UNKNOWN
    activity.refresh_from_db()
    assert activity.ai_stance == enums.Stance.SUPPORT


def test_search_tasks_follow_task_visibility(field, coordinator, korwil, units):
    from asetlahan.models import Task

    Task.objects.create(
        title="Tugas Rahasia Koordinator",
        service_unit=units[0],
        created_by=coordinator,
    )
    results = services.search(field, "Rahasia")
    assert not [r for r in results if r["kind"] == "tugas"]
    own = services.search(coordinator, "Rahasia")
    assert [r for r in own if r["kind"] == "tugas"]


def test_search_parcels_follow_project_scope(field, korwil):
    from pengadaan.models import AcquisitionParcel, AcquisitionProject

    project = AcquisitionProject.objects.create(name="Proyek Lain")
    AcquisitionParcel.objects.create(project=project, parcel_number="RHS-1")
    field.user_permissions.add(
        Permission.objects.get(codename="view_acquisitionparcel")
    )
    penilai = Permission.objects.get(codename="view_acquisitionproject")
    field.user_permissions.add(penilai)
    from django.contrib.auth.models import Group

    from utils.group_permissions import UserGroup

    field.groups.add(Group.objects.get(pk=UserGroup.PENILAI))
    field = type(field).objects.get(pk=field.pk)
    results = services.search(field, "RHS")
    assert not [r for r in results if r["kind"] == "bidang"]


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/1/2/3.png",
        "https://10.0.0.5/tiles/1/2/3.png",
        "https://169.254.169.254/latest/meta-data",
        "http://tile.example.com/1/2/3.png",
    ],
)
def test_satellite_tiles_never_fetch_internal_addresses(url):
    with mock.patch("requests.get") as get:
        assert satellite._fetch_tile(url) is None
    get.assert_not_called()


def test_satellite_tiles_do_not_follow_redirects(monkeypatch):
    monkeypatch.setattr(satellite, "_public_host", lambda url: True)
    with mock.patch("requests.get") as get:
        get.return_value = mock.Mock(status_code=302, content=b"")
        assert satellite._fetch_tile("https://tile.example.com/1/2/3.png") is None
    assert get.call_args.kwargs["allow_redirects"] is False


def test_reporter_edit_resets_verification(rf, field, korwil):
    from django.contrib.admin.sites import site

    activity = Activity.objects.create(
        activity_type=enums.ActivityType.OTHER,
        title="Kegiatan",
        description="Uraian",
        korwil=korwil,
        reported_by=field,
        verified=True,
        impact_confirmed=True,
    )
    model_admin = site._registry[Activity]
    request = rf.post("/")
    request.user = field
    form = mock.Mock(changed_data=["impact_scope"])
    model_admin.save_model(request, activity, form, change=True)
    activity.refresh_from_db()
    assert activity.impact_confirmed is False
    assert activity.verified is True  # cakupan dampak bukan isi verifikasi

    form = mock.Mock(changed_data=["description"])
    model_admin.save_model(request, activity, form, change=True)
    activity.refresh_from_db()
    assert activity.verified is False


def test_closed_sos_note_is_read_only(rf, coordinator, korwil):
    from django.contrib.admin.sites import site

    from operasi.models import SosAlert

    alert = SosAlert.objects.create(
        raised_by=coordinator, korwil=korwil, status=enums.SosStatus.RESOLVED
    )
    request = rf.get("/")
    request.user = coordinator
    model_admin = site._registry[SosAlert]
    assert "resolution_note" in model_admin.get_readonly_fields(request, alert)
    alert.status = enums.SosStatus.ACTIVE
    assert "resolution_note" not in model_admin.get_readonly_fields(request, alert)
