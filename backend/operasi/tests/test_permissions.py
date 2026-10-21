"""Hak akses & pemisahan data pusat komando per peran.

Administrator, superuser, dan Petugas Aset Lahan mengawasi per unit layanan;
Petugas Lapangan dan Koordinator Wilayah hanya melihat Korwil tempat mereka
menjadi anggota atau koordinator.
"""

import datetime
import json
import uuid

import pytest
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

from asetlahan import enums as aset_enums
from asetlahan.models import Task
from operasi import enums, services
from operasi.admin import SoilTestAdmin
from operasi.models import (
    Activity,
    Attendance,
    ChatMessage,
    Korwil,
    OfficerPosition,
    Resident,
    SoilTest,
    SosAlert,
    SystemLock,
)
from operasi.tests.conftest import PASSWORD, inside, login, make_user, photo, square
from utils.group_permissions import UserGroup

pytestmark = pytest.mark.django_db

NIK = "3171012345678901"


def api(path):
    return f"/komando/api/{path}"


@pytest.fixture
def korwil_c(units):
    """Korwil lain di unit yang sama dengan Korwil A, tanpa petugas kita."""
    return Korwil.objects.create(
        code="C", name="Tanjung Banun", geometry=square(104.30), service_unit=units[0]
    )


@pytest.fixture
def aset(seeded, units):
    return make_user("aset", UserGroup.PETUGAS_ASET, units=[units[0]])


def import_csv(client, text):
    upload = SimpleUploadedFile("warga.csv", text.encode(), content_type="text/csv")
    return client.post(
        reverse("admin:operasi_resident_import"), {"file": upload}, follow=True
    )


def page_messages(response) -> str:
    return " ".join(str(m) for m in response.context["messages"])


# --------------------------------------------------------------------------
# Lingkup Korwil untuk petugas lapangan & koordinator
# --------------------------------------------------------------------------


def test_field_officer_sees_only_own_korwils(
    field, aset, manager, korwil, korwil_b, korwil_c
):
    mine = Resident.objects.create(head_name="Warga A", korwil=korwil)
    other = Resident.objects.create(
        head_name="Warga C", korwil=korwil_c, location=inside(korwil_c)
    )
    own_orphan = Resident.objects.create(head_name="Tanpa Korwil", created_by=field)
    foreign_orphan = Resident.objects.create(head_name="Yatim", created_by=aset)
    client = login(field)
    names = {r["name"] for r in client.get(api("warga/")).json()["results"]}
    assert names == {mine.head_name, own_orphan.head_name}
    assert client.get(api(f"warga/{other.pk}/")).status_code == 404
    assert client.get(api(f"warga/{foreign_orphan.pk}/")).status_code == 404
    assert [
        k["properties"]["code"]
        for k in client.get(api("lapisan/korwil/")).json()["features"]
    ] == ["A"]
    assert client.get(api("lapisan/warga/")).json()["features"] == []
    assert client.get(api("ringkasan/")).json()["korwil"] == 1
    page = client.get(reverse("admin:operasi_resident_changelist")).content.decode()
    assert "Warga A" in page and "Warga C" not in page and "Yatim" not in page
    # Pengawas tetap memakai lingkup unit layanan: A dan C (unit sama), bukan B.
    codes = {
        k["properties"]["code"]
        for k in login(aset).get(api("lapisan/korwil/")).json()["features"]
    }
    assert codes == {"A", "C"}
    assert login(aset).get(api(f"warga/{other.pk}/")).status_code == 200
    assert len(login(manager).get(api("warga/")).json()["results"]) == 4


def test_scope_applies_to_files_chat_and_admin(field, coordinator, korwil, korwil_c):
    test = SoilTest.objects.create(location=inside(korwil_c), photo=photo())
    assert test.korwil == korwil_c
    client = login(field)
    assert client.get(f"/komando/berkas/tanah-foto/{test.pk}/").status_code == 404
    assert client.get(api("tanah/?lingkup=semua")).json()["results"] == []
    ChatMessage.objects.create(korwil=korwil_c, body="rahasia C")
    assert client.get(api(f"chat/?kanal={korwil_c.pk}")).status_code == 404
    assert (
        client.post(api("chat/"), {"kanal": korwil_c.pk, "pesan": "halo"}).status_code
        == 404
    )
    page = login(coordinator).get(reverse("admin:operasi_chatmessage_changelist"))
    assert "rahasia C" not in page.content.decode()
    own = SoilTest.objects.create(location=inside(korwil), photo=photo())
    assert client.get(f"/komando/berkas/tanah-foto/{own.pk}/").status_code == 200


# --------------------------------------------------------------------------
# 1. Impor warga tidak boleh menimpa warga di luar wilayah kerja
# --------------------------------------------------------------------------


def test_import_skips_nik_outside_scope(field, korwil, korwil_b):
    victim = Resident.objects.create(
        head_name="Korban", nik=NIK, korwil=korwil_b, phone="0811", note="catatan lama"
    )
    response = import_csv(
        login(field),
        f"nama;nik;korwil;telepon;catatan;sikap\n"
        f"Diubah;{NIK};A;0000;ditimpa;kontra\n"
        f"Baru;2171010101010001;A;0812;;pro\n",
    )
    assert response.status_code == 200
    victim.refresh_from_db()
    assert victim.head_name == "Korban" and victim.korwil == korwil_b
    assert victim.phone == "0811" and victim.note == "catatan lama"
    text = page_messages(response)
    assert "1 warga dibuat, 0 diperbarui, 1 dilewati" in text
    assert "Baris 2: NIK tidak dapat dipakai" in text
    assert "Korban" not in text and "Korwil B" not in text
    assert Resident.objects.filter(head_name="Baru", korwil=korwil).exists()


def test_import_update_appends_note_and_needs_change_permission(
    seeded, units, field, korwil
):
    resident = Resident.objects.create(
        head_name="Lama", nik=NIK, korwil=korwil, note="catatan lama"
    )
    import_csv(login(field), f"nama;nik;catatan\nBaru;{NIK};kunjungan kedua\n")
    resident.refresh_from_db()
    assert resident.head_name == "Baru"
    assert (
        resident.note.startswith("catatan lama\n[")
        and "kunjungan kedua" in resident.note
    )
    # Hanya hak tambah warga: warga yang sudah ada tidak diperbarui.
    adder = make_user("penambah", units=[units[0]])
    adder.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="operasi",
            codename__in=["view_resident", "add_resident", "view_korwil"],
        )
    )
    korwil.members.add(adder)
    response = import_csv(login(adder), f"nama;nik\nDitimpa;{NIK}\n")
    resident.refresh_from_db()
    assert resident.head_name == "Baru"
    assert "tidak berhak mengubahnya" in page_messages(response)


# --------------------------------------------------------------------------
# 2. NIK & KK hanya untuk pemegang izin NIK (Administrator)
# --------------------------------------------------------------------------


def test_nik_hidden_without_permission(
    field, coordinator, aset, manager, korwil, units
):
    resident = Resident.objects.create(
        head_name="Rahasia",
        nik=NIK,
        family_card_number="2171999988887777",
        korwil=korwil,
    )
    url = reverse("admin:operasi_resident_change", args=[resident.pk])
    for user in (field, coordinator, aset):
        assert not user.has_perm("operasi.view_resident_nik")
        page = login(user).get(url)
        assert page.status_code == 200
        body = page.content.decode()
        assert NIK not in body and "2171999988887777" not in body
        # Cari dengan NIK di panel tidak menemukan apa pun.
        listing = login(user).get(
            reverse("admin:operasi_resident_changelist"), {"q": NIK}
        )
        assert "Rahasia" not in listing.content.decode()
    assert manager.has_perm("operasi.view_resident_nik")
    assert NIK in login(manager).get(url).content.decode()
    listing = login(manager).get(
        reverse("admin:operasi_resident_changelist"), {"q": NIK}
    )
    assert "Rahasia" in listing.content.decode()
    # Menyimpan tanpa izin NIK tidak menghapus NIK yang ada.
    login(coordinator).post(
        url,
        {
            "korwil": korwil.pk,
            "head_name": "Rahasia",
            "stance": "belum",
            "land_status": "belum",
            "rtrw_status": "belum",
            "relocation_choice": "belum",
            "stance_changes-TOTAL_FORMS": "0",
            "stance_changes-INITIAL_FORMS": "0",
        },
    )
    resident.refresh_from_db()
    assert resident.nik == NIK


def test_duplicate_nik_message_does_not_reveal_other_scope(field, korwil, korwil_b):
    Resident.objects.create(head_name="Korban", nik=NIK, korwil=korwil_b)
    response = login(field).post(api("warga/"), {"nama": "x", "nik": NIK})
    assert response.status_code == 400
    body = response.content.decode()
    assert "sudah terdata" not in body and "tidak dapat dipakai" in body
    assert Resident.objects.filter(nik_fingerprint__isnull=False).count() == 1


# --------------------------------------------------------------------------
# 3. Posisi Live & ringkasan hanya rekan yang terlihat
# --------------------------------------------------------------------------


def test_live_positions_scoped(field, other_field, manager, korwil, korwil_b):
    now = timezone.now()
    OfficerPosition.objects.create(user=field, location=inside(korwil), updated_at=now)
    OfficerPosition.objects.create(
        user=other_field, location=inside(korwil_b), updated_at=now
    )
    ids = {
        f["properties"]["id"]
        for f in login(other_field).get(api("lapisan/petugas/")).json()["features"]
    }
    assert ids == {other_field.pk}
    page = login(other_field).get(reverse("admin:operasi_officerposition_changelist"))
    assert page.status_code == 200 and "Lapangan2" in page.content.decode()
    assert "Lapangan<" not in page.content.decode()
    assert login(other_field).get(api("ringkasan/")).json()["online"] == 1
    assert login(manager).get(api("ringkasan/")).json()["online"] == 2
    ids = {
        f["properties"]["id"]
        for f in login(manager).get(api("lapisan/petugas/")).json()["features"]
    }
    assert ids == {field.pk, other_field.pk}


# --------------------------------------------------------------------------
# 4. Verifikasi & ubah laporan di panel
# --------------------------------------------------------------------------


def test_admin_verify_only_led_korwil(seeded, units, coordinator, manager, korwil):
    other_lead = make_user("korwil2", UserGroup.KOORDINATOR_WILAYAH, units=[units[0]])
    other = Korwil.objects.create(
        code="C", name="C", geometry=square(104.3), service_unit=units[0]
    )
    other.members.add(coordinator)  # anggota, bukan koordinator
    other.coordinator = other_lead
    other.save()
    act = Activity.objects.create(title="t", korwil=other, started_at=timezone.now())
    own = Activity.objects.create(title="u", korwil=korwil, started_at=timezone.now())
    client = login(coordinator)
    client.post(
        reverse("admin:operasi_activity_changelist"),
        {"action": "mark_verified", "_selected_action": [act.pk, own.pk]},
    )
    act.refresh_from_db()
    own.refresh_from_db()
    assert not act.verified and own.verified and own.verified_by == coordinator
    # Kotak "diverifikasi" tidak dapat diubah koordinator; laporan Korwil lain
    # (tempat ia hanya anggota) tidak dapat diubah sama sekali.
    page = client.get(reverse("admin:operasi_activity_change", args=[own.pk]))
    assert 'name="verified"' not in page.content.decode()
    url = reverse("admin:operasi_activity_change", args=[act.pk])
    assert client.get(url).status_code == 200
    assert client.post(url, {"title": "diubah"}).status_code == 403
    act.refresh_from_db()
    assert act.title == "t"
    # Administrator tetap dapat memverifikasi apa saja.
    page = login(manager).get(url)
    assert 'name="verified"' in page.content.decode()


def test_admin_soil_test_change_by_owner_or_coordinator(
    seeded, units, coordinator, field, korwil
):
    peer = make_user("korwil3", UserGroup.KOORDINATOR_WILAYAH, units=[units[0]])
    korwil.members.add(peer)
    test = SoilTest.objects.create(
        location=inside(korwil), sampled_by=field, korwil=korwil
    )
    url = reverse("admin:operasi_soiltest_change", args=[test.pk])
    model_admin = SoilTestAdmin(SoilTest, admin.site)
    request = RequestFactory().get(url)
    request.user = coordinator
    assert model_admin.has_change_permission(request, test)
    request.user = peer
    assert not model_admin.has_change_permission(request, test)
    assert login(peer).post(url, {"note": "x"}).status_code == 403


# --------------------------------------------------------------------------
# 5. KPI: izin perlu persetujuan, tugas tidak dibatalkan penerima
# --------------------------------------------------------------------------


def test_self_declared_leave_needs_approval(field, coordinator, other_field, korwil):
    today = timezone.localdate()
    start = today - datetime.timedelta(days=7)
    end = today - datetime.timedelta(days=1)
    field.date_joined = timezone.now() - datetime.timedelta(days=30)
    field.save()
    client = login(field)
    days = [start + datetime.timedelta(days=d) for d in range(7)]
    for day in days:
        response = client.post(
            api("absen/"),
            {"aksi": "izin", "jenis": "dinas", "tanggal": day.isoformat(), "note": "x"},
        )
        assert response.status_code == 200, response.content
        assert response.json()["attendance"]["approval"] == "menunggu"
    perf = services.performance(field, start, end)
    if perf["workdays"]:
        assert perf["attendance_pct"] == 0 and perf["present_days"] == 0
    # Petugas tidak dapat menyetujui sendiri; koordinator Korwil lain juga tidak.
    assert client.get(api("absen/persetujuan/")).json()["results"] == []
    pending = Attendance.objects.filter(user=field).first()
    assert client.post(
        api(f"absen/{pending.pk}/persetujuan/"), {"keputusan": "setuju"}
    ).status_code in (403, 404)
    assert login(other_field).post(
        api(f"absen/{pending.pk}/persetujuan/"), {"keputusan": "setuju"}
    ).status_code in (403, 404)
    lead = login(coordinator)
    listed = lead.get(api("absen/persetujuan/")).json()["results"]
    assert {item["id"] for item in listed} == set(
        Attendance.objects.filter(user=field).values_list("pk", flat=True)
    )
    for item in listed:
        response = lead.post(
            api(f"absen/{item['id']}/persetujuan/"), {"keputusan": "setuju"}
        )
        assert (
            response.status_code == 200 and response.json()["approval"] == "disetujui"
        )
    perf = services.performance(field, start, end)
    assert perf["attendance_pct"] == 100
    # Pengajuan baru untuk tanggal yang sama kembali menunggu persetujuan.
    record = Attendance.objects.filter(user=field).first()
    services.request_leave(field, status="cuti", date=record.date, note="ubah")
    record.refresh_from_db()
    assert record.approval == enums.LeaveApproval.PENDING


def test_unapproved_duty_does_not_skip_late(field, coordinator, korwil):
    today = timezone.localdate()
    late = timezone.make_aware(datetime.datetime.combine(today, datetime.time(10, 0)))
    services.request_leave(field, status="dinas", date=today, note="rapat")
    record, _created, warnings = services.check_in(
        field, location=inside(korwil), now=late
    )
    assert "Tercatat terlambat." in [str(w) for w in warnings]
    perf = services.performance(field, today, today)
    assert perf["late_days"] == 1
    services.decide_leave(record, coordinator, True)
    perf = services.performance(field, today, today)
    assert perf["late_days"] == 0 and perf["present_days"] == 1


def test_assignee_cannot_cancel_task(field, coordinator, korwil):
    task = Task.objects.create(
        title="Pendataan",
        assignee=field,
        due_date=timezone.localdate() - datetime.timedelta(days=2),
    )
    data = login(field).get(api("tugas/")).json()["results"]
    assert data[0]["can_cancel"] is False
    response = login(field).post(
        api(f"tugas/{task.pk}/"), {"status": aset_enums.TaskStatus.CANCELLED}
    )
    assert response.status_code == 403
    task.refresh_from_db()
    assert task.status == aset_enums.TaskStatus.NEW
    assert (
        login(field)
        .post(api(f"tugas/{task.pk}/"), {"status": aset_enums.TaskStatus.IN_PROGRESS})
        .status_code
        == 200
    )
    # Koordinator Korwil tempat penerima tugas bertugas boleh membatalkan.
    task.korwil = korwil
    task.save()
    response = login(coordinator).post(
        api(f"tugas/{task.pk}/"), {"status": aset_enums.TaskStatus.CANCELLED}
    )
    assert response.status_code == 200, response.content
    task.refresh_from_db()
    assert task.status == aset_enums.TaskStatus.CANCELLED


# --------------------------------------------------------------------------
# 6. Pesan sistem SOS hanya untuk yang boleh melihat SOS-nya
# --------------------------------------------------------------------------


def test_sos_system_message_scoped(field, other_field, manager, korwil, korwil_b):
    point = inside(korwil_b)
    response = login(other_field).post(
        api("sos/"),
        {
            "client_id": str(uuid.uuid4()),
            "lat": point.y,
            "lng": point.x,
            "pesan": "tolong",
        },
    )
    assert response.status_code == 201
    message = ChatMessage.objects.get(is_system=True)
    assert message.korwil == korwil_b
    general = login(field).get(api("chat/")).json()["results"]
    assert not any("tolong" in m["body"] for m in general)
    assert any(
        "tolong" in m["body"]
        for m in login(other_field).get(api("chat/")).json()["results"]
    )
    data = login(manager).get(api("chat/")).json()
    assert any("tolong" in m["body"] for m in data["results"]), data
    alert = SosAlert.objects.get()
    login(manager).post(api(f"sos/{alert.pk}/tangani/"))
    assert ChatMessage.objects.filter(is_system=True, korwil=korwil_b).count() == 2


# --------------------------------------------------------------------------
# 7. Data baru tidak masuk Korwil di luar wilayah kerja
# --------------------------------------------------------------------------


def test_writes_fall_back_to_own_korwil(field, korwil, korwil_b):
    point = inside(korwil_b)
    client = login(field)
    response = client.post(
        api("warga/"), {"nama": "Baru", "lat": point.y, "lng": point.x}
    )
    assert response.status_code == 201
    assert Resident.objects.get(pk=response.json()["id"]).korwil == korwil
    response = client.post(
        api("kegiatan/"),
        {
            "client_id": str(uuid.uuid4()),
            "judul": "Kunjungan",
            "lat": point.y,
            "lng": point.x,
        },
    )
    assert response.status_code == 201, response.content
    assert Activity.objects.get(pk=response.json()["id"]).korwil == korwil
    response = client.post(
        api("tanah/"), {"client_id": str(uuid.uuid4()), "lat": point.y, "lng": point.x}
    )
    assert SoilTest.objects.get(pk=response.json()["id"]).korwil == korwil


def test_writes_rejected_without_single_korwil(
    seeded, units, korwil, korwil_b, korwil_c
):
    roamer = make_user("keliling", UserGroup.PETUGAS_LAPANGAN, units=[units[0]])
    korwil.members.add(roamer)
    korwil_c.members.add(roamer)
    point = inside(korwil_b)
    client = login(roamer)
    response = client.post(
        api("warga/"), {"nama": "Baru", "lat": point.y, "lng": point.x}
    )
    assert response.status_code == 400
    assert "luar wilayah kerja" in response.content.decode()
    assert not Resident.objects.filter(head_name="Baru").exists()
    # Korwil pilihan sendiri tetap diterima.
    response = client.post(
        api("warga/"),
        {"nama": "Baru", "lat": point.y, "lng": point.x, "korwil": korwil_c.pk},
    )
    assert response.status_code == 201
    # SOS tidak pernah ditolak: tanpa Korwil, tetapi tetap dikirim.
    response = client.post(
        api("sos/"), {"client_id": str(uuid.uuid4()), "lat": point.y, "lng": point.x}
    )
    assert response.status_code == 201
    alert = SosAlert.objects.get()
    assert alert.korwil is None and alert.raised_by == roamer
    assert ChatMessage.objects.filter(is_system=True).exists()


# --------------------------------------------------------------------------
# 8. Data di perangkat setelah keluar
# --------------------------------------------------------------------------


def test_service_worker_does_not_keep_personal_data(field, korwil):
    from operasi.views import SW_VERSION

    client = login(field)
    body = client.get("/komando/sw.js").content.decode()
    assert SW_VERSION == "4" and 'var VERSION = "4";' in body
    # Hanya halaman utama yang disimpan (bukan navigasi lain seperti berkas).
    assert 'request.mode === "navigate" ||' not in body
    assert "purgePersonal" in body and "response.redirected" in body
    page = client.get("/komando/").content.decode()
    config = json.loads(
        page.split('id="komando-config" type="application/json">')[1].split(
            "</script>"
        )[0]
    )
    assert config["urls"]["logout"] == reverse("admin:logout")
    assert 'id="keluar"' in page
    from django.contrib.staticfiles import finders

    script = open(finders.find("operasi/komando.js"), encoding="utf-8").read()
    assert "user_id: config.user.id" in script and "purgeOfflineData" in script


# --------------------------------------------------------------------------
# Kunci sistem: profil & ganti sandi ikut terkunci
# --------------------------------------------------------------------------


def test_lock_blocks_profile_and_password(field, admin_user, korwil):
    lock = SystemLock.load()
    lock.set_passcode("rahasia123")
    lock.is_armed = True
    lock.shutdown_at = timezone.now() - datetime.timedelta(minutes=1)
    lock.save()
    client = login(field)
    assert client.get("/v1/auth/me/").status_code == 503
    assert client.post("/v1/auth/password/", {}).status_code == 503
    response = Client().post(
        "/v1/auth/login/",
        {"username": admin_user.username, "password": PASSWORD},
        content_type="application/json",
    )
    assert response.status_code == 200
    access = response.json()["access"]
    me = Client().get("/v1/auth/me/", HTTP_AUTHORIZATION=f"Bearer {access}")
    assert me.status_code == 200
    refresh = Client().post(
        "/v1/auth/refresh/",
        {"refresh": response.json()["refresh"]},
        content_type="application/json",
    )
    assert refresh.status_code != 503
