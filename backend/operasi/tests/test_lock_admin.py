import datetime
import io
import json

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from operasi.models import (
    Activity,
    Attendance,
    Korwil,
    Resident,
    SoilTest,
    SosAlert,
    SystemLock,
)
from operasi.tests.conftest import PASSWORD, inside, login

pytestmark = pytest.mark.django_db


def arm(minutes: int, passcode="rahasia123"):
    lock = SystemLock.load()
    lock.set_passcode(passcode)
    lock.is_armed = True
    lock.shutdown_at = timezone.now() + datetime.timedelta(minutes=minutes)
    lock.save()
    return lock


# --------------------------------------------------------------------------
# Kunci hidup sistem
# --------------------------------------------------------------------------


def test_countdown_does_not_block(field, korwil):
    arm(60)
    client = login(field)
    response = client.get("/komando/")
    assert response.status_code == 200
    assert (
        json.loads(
            response.content.decode()
            .split('id="komando-config" type="application/json">')[1]
            .split("</script>")[0]
        )["lock"]["armed"]
        is True
    )
    assert "Kunci sistem aktif" in client.get("/admin/").content.decode()


def test_lock_blocks_everyone_but_superuser(field, admin_user, korwil):
    arm(-1)
    assert login(field).get("/komando/").status_code == 503
    response = login(field).get(
        "/komando/api/ringkasan/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 503 and response.json()["locked"] is True
    assert Client().get("/portal/").status_code == 503
    assert Client().get("/v1/aset/asset/").status_code == 503
    # Pengecualian: halaman masuk, pemeriksaan kesehatan, berkas statis.
    assert Client().get("/admin/login/").status_code == 200
    assert Client().get("/healthz").status_code != 503
    # Superuser tetap bekerja, termasuk lewat token aplikasi petugas.
    assert login(admin_user).get("/komando/").status_code == 200
    token = Client().post(
        "/v1/auth/login/",
        {"username": admin_user.username, "password": PASSWORD},
        content_type="application/json",
    )
    assert token.status_code == 200, token.content
    access = token.json()["access"]
    response = Client().get("/v1/aset/asset/", HTTP_AUTHORIZATION=f"Bearer {access}")
    assert response.status_code == 200


def test_defuse_api(field, admin_user, korwil):
    arm(30)
    assert (
        login(field).post("/komando/api/kunci/", {"passcode": "rahasia123"}).status_code
        == 403
    )
    client = login(admin_user)
    assert client.post("/komando/api/kunci/", {"passcode": "salah"}).status_code == 400
    assert client.post("/komando/api/kunci/", {"passcode": "rahasia123"}).json() == {
        "armed": False
    }
    lock = SystemLock.load()
    assert lock.is_armed is False and lock.defused_by == admin_user


def test_defuse_api_throttled(admin_user):
    arm(30)
    client = login(admin_user)
    for _i in range(5):
        client.post("/komando/api/kunci/", {"passcode": "salah"})
    assert (
        client.post("/komando/api/kunci/", {"passcode": "rahasia123"}).status_code
        == 429
    )


def test_lock_admin_form(admin_user, manager):
    url = reverse("admin:operasi_systemlock_change", args=[SystemLock.load().pk])
    assert login(manager).get(url).status_code == 403
    client = login(admin_user)
    assert client.get(url).status_code == 200
    future = timezone.localtime() + datetime.timedelta(hours=2)
    form = {
        "is_armed": "on",
        "shutdown_at_0": future.strftime("%Y-%m-%d"),
        "shutdown_at_1": future.strftime("%H:%M:%S"),
        "message": "Pemeliharaan",
    }
    response = client.post(url, form)
    assert (
        response.status_code == 200
        and "Tetapkan kode rahasia" in response.content.decode()
    )
    response = client.post(
        url, {**form, "new_passcode": "rahasia123", "confirm_passcode": "rahasia123"}
    )
    assert response.status_code == 302, response.content.decode()[:2000]
    lock = SystemLock.load()
    assert (
        lock.is_armed
        and lock.armed_by == admin_user
        and lock.check_passcode("rahasia123")
    )
    off = {
        "shutdown_at_0": form["shutdown_at_0"],
        "shutdown_at_1": form["shutdown_at_1"],
        "message": "x",
    }
    response = client.post(url, off)
    assert response.status_code == 200 and SystemLock.load().is_armed
    response = client.post(url, {**off, "current_passcode": "rahasia123"})
    assert response.status_code == 302
    assert SystemLock.load().is_armed is False


# --------------------------------------------------------------------------
# Panel admin
# --------------------------------------------------------------------------

CHANGELISTS = [
    "korwil",
    "resident",
    "activity",
    "soiltest",
    "attendance",
    "chatmessage",
    "sosalert",
    "officerposition",
    "areaanalysis",
]


def _seed(korwil, field):
    Resident.objects.create(head_name="Ahmad", korwil=korwil, location=inside(korwil))
    activity = Activity.objects.create(
        title="Rapat", korwil=korwil, reported_by=field, location=inside(korwil)
    )
    SoilTest.objects.create(location=inside(korwil), sampled_by=field)
    Attendance.objects.create(
        user=field, date=timezone.localdate(), status="hadir", korwil=korwil
    )
    SosAlert.objects.create(raised_by=field, korwil=korwil, location=inside(korwil))
    return activity


def test_admin_pages_render(admin_user, field, korwil):
    activity = _seed(korwil, field)
    client = login(admin_user)
    for name in CHANGELISTS:
        assert client.get(f"/admin/operasi/{name}/").status_code == 200, name
    for name, obj in (
        ("korwil", korwil),
        ("resident", Resident.objects.get()),
        ("activity", activity),
        ("soiltest", SoilTest.objects.get()),
        ("attendance", Attendance.objects.get()),
        ("sosalert", SosAlert.objects.get()),
    ):
        assert (
            client.get(f"/admin/operasi/{name}/{obj.pk}/change/").status_code == 200
        ), name
    for url in (
        "/admin/operasi/",
        "/admin/operasi/commandsettings/",
        "/admin/operasi/korwil/impor/",
        "/admin/operasi/resident/impor/",
        "/admin/operasi/korwil/add/",
        "/admin/operasi/resident/add/",
        "/admin/operasi/activity/add/",
    ):
        assert client.get(url, follow=True).status_code == 200, url
    page = client.get("/admin/operasi/").content.decode()
    assert "/komando/" in page and "Django" not in page


def test_admin_exports(admin_user, field, korwil):
    _seed(korwil, field)
    client = login(admin_user)
    for name in ("resident", "activity", "soiltest", "attendance"):
        model = {
            "resident": Resident,
            "activity": Activity,
            "soiltest": SoilTest,
            "attendance": Attendance,
        }[name]
        ids = list(model.objects.values_list("pk", flat=True))
        response = client.post(
            f"/admin/operasi/{name}/", {"action": "export_csv", "_selected_action": ids}
        )
        assert response.status_code == 200, name
        assert response["Content-Type"].startswith("text/csv"), name
    assert (
        "NIK"
        not in client.post(
            "/admin/operasi/resident/",
            {
                "action": "export_csv",
                "_selected_action": list(Resident.objects.values_list("pk", flat=True)),
            },
        ).content.decode()
    )


def test_admin_permissions_by_group(field, coordinator, manager, korwil, korwil_b):
    _seed(korwil, field)
    Resident.objects.create(head_name="Unit lain", korwil=korwil_b)
    client = login(field)
    assert client.get("/admin/operasi/resident/").status_code == 200
    assert "Unit lain" not in client.get("/admin/operasi/resident/").content.decode()
    assert client.get("/admin/operasi/korwil/add/").status_code == 403
    assert client.get("/admin/operasi/systemlock/", follow=True).status_code == 403
    assert client.get("/admin/operasi/commandsettings/", follow=True).status_code == 403
    # Absensi: petugas & koordinator hanya melihat; koreksi oleh Administrator.
    assert login(coordinator).get("/admin/operasi/attendance/").status_code == 200
    assert login(coordinator).get("/admin/operasi/attendance/add/").status_code == 403
    assert login(manager).get("/admin/operasi/attendance/add/").status_code == 200
    assert login(coordinator).get("/admin/operasi/sosalert/add/").status_code == 403


def test_admin_sos_actions(manager, field, korwil):
    alert = SosAlert.objects.create(raised_by=field, korwil=korwil)
    response = login(manager).post(
        "/admin/operasi/sosalert/",
        {"action": "acknowledge", "_selected_action": [alert.pk]},
    )
    assert response.status_code == 302
    alert.refresh_from_db()
    assert alert.status == "ditangani" and alert.acknowledged_by == manager


def test_korwil_import_via_admin(admin_user):
    from django.core.files.uploadedfile import SimpleUploadedFile

    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"kode": "c", "nama": "Rempang Cate", "warna": "#123456"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [104.1, 0.8],
                            [104.11, 0.8],
                            [104.11, 0.81],
                            [104.1, 0.81],
                            [104.1, 0.8],
                        ]
                    ],
                },
            }
        ],
    }
    upload = SimpleUploadedFile(
        "korwil.geojson", json.dumps(geojson).encode(), content_type="application/json"
    )
    response = login(admin_user).post("/admin/operasi/korwil/impor/", {"file": upload})
    assert response.status_code == 302
    korwil = Korwil.objects.get()
    assert (korwil.code, korwil.name, korwil.color) == ("C", "Rempang Cate", "#123456")


def test_resident_import_via_admin(admin_user, korwil):
    from django.core.files.uploadedfile import SimpleUploadedFile

    point = inside(korwil)
    csv_text = (
        "nama;nik;jiwa;kampung;korwil;lat;lng;sikap;status_lahan;rtrw;pilihan\n"
        f"Ahmad;2171010101010001;4;Pasir Panjang;A;{point.y};{point.x};pro;sudah;sesuai;relokasi\n"
        "Hasan;;3;Sembulang;;;;kontra;belum;tidak;\n"
    )
    upload = SimpleUploadedFile("warga.csv", csv_text.encode(), content_type="text/csv")
    response = login(admin_user).post(
        "/admin/operasi/resident/impor/", {"file": upload}
    )
    assert response.status_code == 302
    ahmad = Resident.objects.get(head_name="Ahmad")
    assert (
        ahmad.stance,
        ahmad.land_status,
        ahmad.rtrw_status,
        ahmad.relocation_choice,
    ) == (
        "mendukung",
        "sudah",
        "sesuai",
        "relokasi",
    )
    assert ahmad.korwil == korwil and ahmad.member_count == 4
    hasan = Resident.objects.get(head_name="Hasan")
    assert hasan.stance == "menolak" and hasan.korwil is None
    # Impor ulang dengan NIK sama memperbarui, bukan menggandakan.
    again = SimpleUploadedFile(
        "warga.csv", "nama,nik,sikap\nAhmad Baru,2171010101010001,netral\n".encode()
    )
    login(admin_user).post("/admin/operasi/resident/impor/", {"file": again})
    assert Resident.objects.filter(nik_fingerprint=ahmad.nik_fingerprint).count() == 1
    assert Resident.objects.get(pk=ahmad.pk).head_name == "Ahmad Baru"


def test_resident_import_errors_name_the_line(admin_user, korwil):
    from asetlahan.importers import AssetImportError
    from operasi.importers import import_residents

    with pytest.raises(AssetImportError, match="Baris 3"):
        import_residents(
            "nama,korwil\nA,A\nB,Z\n".encode(), "warga.csv", user=admin_user
        )
    with pytest.raises(AssetImportError, match="16 digit"):
        import_residents("nama,nik\nA,123\n".encode(), "warga.csv", user=admin_user)
    assert not Resident.objects.exists()


def test_sample_data_command(admin_user):
    call_command("operasi_contoh_rempang", stdout=io.StringIO())
    assert Korwil.objects.count() == 11
    assert Resident.objects.count() >= 88 and Activity.objects.count() == 33
    assert all(r.korwil_id for r in Resident.objects.all())
    out = io.StringIO()
    call_command("operasi_contoh_rempang", stdout=out)
    assert "dilewati" in out.getvalue()
    client = login(admin_user)
    assert len(client.get("/komando/api/lapisan/korwil/").json()["features"]) == 11
    call_command("operasi_contoh_rempang", "--hapus", stdout=io.StringIO())
    assert not Korwil.objects.exists() and not Resident.objects.exists()
    assert not Activity.objects.exists() and not SoilTest.objects.exists()


def test_korwil_import_from_kmz(admin_user, make_kmz):
    from django.core.files.uploadedfile import SimpleUploadedFile

    kmz = make_kmz([("Rempang Cate", {"kode": "c", "warna": "#123456"})])
    upload = SimpleUploadedFile("korwil.kmz", kmz)
    response = login(admin_user).post("/admin/operasi/korwil/impor/", {"file": upload})
    assert response.status_code == 302
    korwil = Korwil.objects.get()
    assert (korwil.code, korwil.name, korwil.color) == ("C", "Rempang Cate", "#123456")
