"""Regression test temuan audit: jalur admin & dasbor operasi harus mengikuti
lingkup Korwil yang sama dengan API pusat komando."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from operasi.models import PatrolSession
from operasi.tests.conftest import login
from operasi.tests.test_kegiatan_lapangan import smart_geojson

pytestmark = pytest.mark.django_db


def test_admin_smart_import_never_files_into_foreign_korwil(field, korwil, korwil_b):
    """NV-21: jejak yang dimulai di Korwil lain tidak masuk ke Korwil itu."""
    response = login(field).post(
        "/admin/operasi/patrolsession/impor/",
        {"file": SimpleUploadedFile("p.json", smart_geojson(korwil_b))},
    )
    assert response.status_code == 302
    session = PatrolSession.objects.get()
    assert session.korwil != korwil_b
    assert session.korwil == korwil  # satu-satunya Korwil milik pengunggah


def _admin_form(model, user):
    from django.contrib import admin
    from django.test import RequestFactory

    request = RequestFactory().get("/")
    request.user = user
    return admin.site._registry[model].get_form(request)()


def test_admin_relation_fields_only_accept_in_scope_records(field, korwil, korwil_b):
    """NV-22: pilihan Resident/SoilTest di formulir admin = lingkup API."""
    from django.core.exceptions import ValidationError

    from operasi import enums
    from operasi.models import Activity, GeotechPoint, LandPlot, Resident, SoilTest
    from operasi.tests.conftest import inside

    own = Resident.objects.create(head_name="Warga A", korwil=korwil)
    foreign = Resident.objects.create(head_name="Warga B", korwil=korwil_b)
    plot_field = _admin_form(LandPlot, field).fields["resident"]
    assert plot_field.clean(own.pk) == own
    with pytest.raises(ValidationError):
        plot_field.clean(foreign.pk)

    residents_field = _admin_form(Activity, field).fields["residents"]
    assert list(residents_field.clean([own.pk])) == [own]
    with pytest.raises(ValidationError):
        residents_field.clean([foreign.pk])

    foreign_test = SoilTest.objects.create(
        korwil=korwil_b,
        location=inside(korwil_b),
        sampled_by=field,
        texture=enums.SoilTexture.CLAY,
    )
    with pytest.raises(ValidationError):
        _admin_form(GeotechPoint, field).fields["soil_test"].clean(foreign_test.pk)


def test_admin_delete_follows_owner_or_coordinator_rule(
    coordinator, field, korwil, units
):
    """NV-23: anggota biasa (grup Koordinator Wilayah) di Korwil yang dipimpin
    orang lain tidak bisa menghapus foto 360 milik petugas lain lewat admin."""
    from operasi.models import SitePhoto360
    from operasi.tests.conftest import inside, make_user, png_bytes
    from utils.group_permissions import UserGroup

    member = make_user("anggota", UserGroup.KOORDINATOR_WILAYAH, units=[units[0]])
    korwil.members.add(member)
    photo = SitePhoto360.objects.create(
        title="Dermaga",
        korwil=korwil,
        location=inside(korwil),
        image=SimpleUploadedFile("pano.png", png_bytes((8, 4)), "image/png"),
        uploaded_by=field,
    )
    client = login(member)
    delete_url = f"/admin/operasi/sitephoto360/{photo.pk}/delete/"
    assert client.post(delete_url, {"post": "yes"}).status_code == 403
    bulk = client.post(
        "/admin/operasi/sitephoto360/",
        {"action": "delete_selected", "_selected_action": [photo.pk], "post": "yes"},
    )
    assert bulk.status_code in (302, 403)
    assert SitePhoto360.objects.filter(pk=photo.pk).exists()

    # Koordinator Korwil itu tetap boleh.
    assert login(coordinator).post(delete_url, {"post": "yes"}).status_code == 302
    assert not SitePhoto360.objects.filter(pk=photo.pk).exists()


def _nik(i):
    return f"21710{i:011d}"


def test_resident_import_nik_oracle_shares_api_budget(coordinator, korwil, korwil_b):
    """NV-24: NIK yang hanya terdata di Korwil lain memakai jatah 10/jam yang
    sama dengan API; melewati jatah membatalkan seluruh impor."""
    from asetlahan.importers import AssetImportError
    from operasi.importers import import_residents
    from operasi.models import Resident

    for i in range(15):
        Resident.objects.create(head_name=f"Warga B{i}", korwil=korwil_b, nik=_nik(i))
    small = "nama,nik,korwil\n" + f"Uji,{_nik(0)},A\nBaru,{_nik(900)},A\n"
    result = import_residents(small.encode(), "warga.csv", user=coordinator)
    assert result["created"] == 1 and result["skipped"] == 1

    probe = "nama,nik,korwil\n" + "".join(
        f"Uji {i},{_nik(i)},A\n" for i in range(1, 15)
    )
    with pytest.raises(AssetImportError, match="terlalu banyak NIK"):
        import_residents(probe.encode(), "warga.csv", user=coordinator)
    assert not Resident.objects.filter(head_name__startswith="Uji").exists()

    # Jatah yang terpakai tidak ikut dibatalkan bersama impor yang gagal:
    # impor ulang dengan satu NIK konflik saja tetap ditolak.
    retry = "nama,nik,korwil\n" + f"Uji ulang,{_nik(14)},A\nBaru lagi,{_nik(901)},A\n"
    with pytest.raises(AssetImportError, match="terlalu banyak NIK"):
        import_residents(retry.encode(), "warga.csv", user=coordinator)


def test_performance_detail_limited_to_viewer_korwils(
    coordinator, field, korwil, korwil_b
):
    """NV-25: koordinator Korwil A melihat rincian anggota yang juga bertugas
    di Korwil B: kegiatan & titik di Korwil B (dan tanpa Korwil) tidak ikut."""
    import datetime

    from django.utils import timezone

    from operasi import enums
    from operasi.models import Activity
    from operasi.tests.conftest import inside

    korwil_b.members.add(field)
    started = timezone.now() - datetime.timedelta(hours=2)
    for title, area in (("Di A", korwil), ("Di B", korwil_b)):
        Activity.objects.create(
            korwil=area,
            title=title,
            activity_type=enums.ActivityType.KOMSOS,
            started_at=started,
            location=inside(area),
            reported_by=field,
        )
    Activity.objects.create(
        title="Tanpa Korwil",
        activity_type=enums.ActivityType.KOMSOS,
        started_at=started,
        reported_by=field,
    )
    detail = (
        login(coordinator)
        .get(
            "/komando/api/kinerja/",
            {"rinci": "1", "petugas": field.pk, "periode": "minggu"},
        )
        .json()["detail"]
    )
    titles = {row["title"] for row in detail["recent"]}
    assert titles == {"Di A"}
    point_a = inside(korwil)
    assert all(abs(p["lng"] - point_a.x) < 0.02 for p in detail["points"]), detail[
        "points"
    ]

    # Petugas melihat rinciannya sendiri secara utuh.
    own = (
        login(field)
        .get("/komando/api/kinerja/", {"rinci": "1", "periode": "minggu"})
        .json()["detail"]
    )
    assert {row["title"] for row in own["recent"]} == {"Di A", "Di B", "Tanpa Korwil"}
