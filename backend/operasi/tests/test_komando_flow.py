"""Tugas berpoin, laporan harian berjenjang, antrian persetujuan, dan rekap Excel."""

import datetime
import io
import zipfile

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from asetlahan import enums as aset_enums
from asetlahan.models import Task
from operasi import enums, hierarchy
from operasi.models import (
    Activity,
    Attendance,
    DailyReport,
    OfficerProfile,
    TaskEvent,
    TaskPoint,
)
from operasi.tests.conftest import inside, login, make_user, photo
from utils.group_permissions import UserGroup

pytestmark = pytest.mark.django_db

BASE = "/komando/"


def api(path):
    return f"{BASE}api/{path}"


@pytest.fixture
def chain(korwil, field, coordinator, manager):
    """Petugas -> koordinator Korwil (fallback) -> Administrator (profil)."""
    OfficerProfile.objects.create(
        user=coordinator, position="Koordinator Korwil A", supervisor=manager
    )
    OfficerProfile.objects.create(user=manager, position="Pimpinan")
    return field, coordinator, manager


def activity(user, korwil, title="Komsos RT 01", **extra):
    extra.setdefault("activity_type", enums.ActivityType.KOMSOS)
    return Activity.objects.create(
        korwil=korwil,
        title=title,
        started_at=timezone.now() - datetime.timedelta(hours=2),
        location=inside(korwil),
        reported_by=user,
        **extra,
    )


def act(user, task, action, **data):
    return login(user).post(api(f"tugas/{task.pk}/"), {"aksi": action, **data})


# --------------------------------------------------------------------------
# Struktur komando
# --------------------------------------------------------------------------


def test_hierarchy_fallback_profile_and_cycles(chain, other_field):
    field, coordinator, manager = chain
    assert hierarchy.supervisor_of(field) == coordinator
    assert hierarchy.supervisor_of(coordinator) == manager
    assert hierarchy.supervisor_of(manager) is None
    assert hierarchy.descendant_ids(manager) == {coordinator.pk, field.pk}
    assert hierarchy.direct_subordinate_ids(manager) == {coordinator.pk}
    assert hierarchy.is_ancestor(manager, field)
    assert not hierarchy.is_ancestor(field, manager)
    assert hierarchy.position_of(coordinator) == "Koordinator Korwil A"
    # Atasan eksplisit menimpa koordinator Korwil.
    OfficerProfile.objects.create(user=field, supervisor=manager)
    assert hierarchy.supervisor_of(field) == manager
    # Siklus dan atasan diri sendiri ditolak.
    loop = OfficerProfile.objects.get(user=manager)
    loop.supervisor = coordinator
    with pytest.raises(ValidationError):
        loop.full_clean()
    loop.supervisor = manager
    with pytest.raises(ValidationError):
        loop.full_clean()
    assert hierarchy.supervisor_of(other_field) is None


# --------------------------------------------------------------------------
# Siklus tugas
# --------------------------------------------------------------------------


def test_create_task_only_for_subordinates(chain, other_field, korwil):
    field, coordinator, manager = chain
    client = login(coordinator)
    people = {p["id"] for p in client.get(api("tugas/penerima/")).json()["results"]}
    assert people == {field.pk}
    response = client.post(
        api("tugas/"), {"judul": "Salah alamat", "penerima": other_field.pk}
    )
    assert response.status_code == 400
    response = client.post(
        api("tugas/"),
        {
            "judul": "Pendataan RT 03",
            "penerima": field.pk,
            "kontributor": str(other_field.pk),
            "poin": "10",
        },
    )
    assert response.status_code == 400 and "kontributor" in response.json()["errors"]
    response = client.post(
        api("tugas/"),
        {"judul": "Pendataan RT 03", "penerima": field.pk, "poin": "101"},
    )
    assert response.status_code == 400
    yesterday = timezone.localdate() - datetime.timedelta(days=1)
    response = client.post(
        api("tugas/"),
        {"judul": "Pendataan RT 03", "penerima": field.pk, "tenggat": yesterday},
    )
    assert response.status_code == 400
    response = client.post(
        api("tugas/"),
        {
            "judul": "Pendataan RT 03",
            "penerima": field.pk,
            "jenis": enums.ActivityType.CENSUS,
            "prioritas": aset_enums.Priority.HIGH,
            "poin": "10",
        },
    )
    assert response.status_code == 201, response.content
    task = Task.objects.get(pk=response.json()["id"])
    assert task.korwil == korwil and task.created_by == coordinator
    assert task.service_unit == korwil.service_unit
    assert task.komando_events.get().kind == enums.TaskEventKind.CREATED
    # Petugas lapangan tidak memberi tugas; koordinator hanya ke bawahannya.
    data = login(field).get(api("tugas/")).json()
    assert data["can_create"] is False
    response = login(field).post(
        api("tugas/"), {"judul": "Ke atas", "penerima": coordinator.pk}
    )
    assert response.status_code == 403
    response = login(coordinator).post(
        api("tugas/"), {"judul": "Ke atas", "penerima": manager.pk}
    )
    assert response.status_code == 400


def test_task_lifecycle_points_and_kpi(chain, other_field, korwil, private_storage):
    field, coordinator, manager = chain
    helper = make_user("pembantu", UserGroup.PETUGAS_LAPANGAN)
    korwil.members.add(helper)
    task = Task.objects.create(
        title="Dokumentasi jalan",
        assignee=field,
        korwil=korwil,
        created_by=coordinator,
        point_value=15,
    )
    task.contributors.add(helper)
    # Hanya penerima yang memulai; pemberi tidak.
    assert act(coordinator, task, "mulai").status_code == 403
    assert act(field, task, "lapor", catatan="x").status_code == 400
    assert act(field, task, "mulai").status_code == 200
    assert act(field, task, "kendala").status_code == 400
    response = act(field, task, "kendala", catatan="Hujan deras")
    assert response.json()["stage"] == enums.TaskStage.BLOCKED
    assert act(field, task, "lanjut").json()["stage"] == enums.TaskStage.WORKING
    assert act(field, task, "lapor").status_code == 400  # tanpa catatan/foto
    response = act(field, task, "lapor", foto=photo(), lat="0.805", lng="104.105")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["stage"] == enums.TaskStage.REPORTED and body["progress"] == 90
    proof = body["events"][0]  # terbaru lebih dahulu
    assert proof["photo"] and proof["lat"] == pytest.approx(0.805)
    # Foto bukti hanya untuk yang boleh melihat tugas.
    assert login(coordinator).get(proof["photo"]).status_code == 200
    assert login(other_field).get(proof["photo"]).status_code == 404
    # Pengembalian wajib bercatatan dan menandai tahap revisi.
    assert act(coordinator, task, "kembalikan").status_code == 400
    response = act(coordinator, task, "kembalikan", catatan="Foto kurang jelas")
    assert response.json()["stage"] == enums.TaskStage.REVISION
    assert act(field, task, "lapor", catatan="Foto baru").status_code == 200
    assert act(field, task, "verifikasi").status_code == 403
    response = act(coordinator, task, "verifikasi")
    assert response.status_code == 200
    awarded = {(p.user_id, p.role) for p in TaskPoint.objects.filter(task=task)}
    assert awarded == {
        (field.pk, enums.TaskPointRole.ASSIGNEE),
        (helper.pk, enums.TaskPointRole.CONTRIBUTOR),
        (coordinator.pk, enums.TaskPointRole.GIVER),
    }
    assert set(TaskPoint.objects.values_list("points", flat=True)) == {15}
    task.refresh_from_db()
    assert task.status == aset_enums.TaskStatus.DONE
    assert act(coordinator, task, "verifikasi").status_code == 400
    assert act(coordinator, task, "batal").status_code == 400
    kinds = list(task.komando_events.values_list("kind", flat=True))
    assert kinds[0] == enums.TaskEventKind.VERIFIED and len(kinds) == 7
    # Poin tugas masuk KPI usaha periode berjalan.
    data = login(field).get(api("kinerja/?periode=bulan")).json()
    assert data["me"]["task_points"] == 15


def test_task_filters_and_progress(chain, korwil):
    field, coordinator, manager = chain
    late = Task.objects.create(
        title="Terlambat",
        assignee=field,
        due_date=timezone.localdate() - datetime.timedelta(days=1),
    )
    reported = Task.objects.create(
        title="Dilaporkan",
        assignee=field,
        status=aset_enums.TaskStatus.REPORTED,
        created_by=coordinator,
    )

    def titles(user, name):
        response = login(user).get(api(f"tugas/?filter={name}"))
        return {t["title"] for t in response.json()["results"]}

    assert titles(coordinator, "verifikasi") == {reported.title}
    assert titles(field, "verifikasi") == set()
    assert titles(manager, "terlambat") >= {late.title}
    assert titles(coordinator, "tim") == {late.title, reported.title}
    response = login(field).post(api(f"tugas/{late.pk}/"), {"progress": "40"})
    assert response.status_code == 200 and response.json()["progress"] == 40
    # Pengamat bukan penerima/pemeriksa tidak mengubah progres.
    stranger = make_user("asing", UserGroup.PETUGAS_LAPANGAN)
    korwil.members.add(stranger)
    assert (
        login(stranger).post(api(f"tugas/{late.pk}/"), {"progress": "50"}).status_code
        == 404
    )


def test_admin_list_edit_by_assignee_becomes_reported(chain, units):
    field, coordinator, manager = chain
    task = Task.objects.create(
        title="Lewat panel", assignee=field, service_unit=units[0], point_value=5
    )

    def list_edit(user, status):
        login(user).post(
            reverse("admin:asetlahan_task_changelist"),
            {
                "form-TOTAL_FORMS": 1,
                "form-INITIAL_FORMS": 1,
                "form-0-id": task.pk,
                "form-0-status": status,
                "form-0-progress": 100,
                "_save": "Simpan",
            },
        )
        task.refresh_from_db()

    list_edit(field, aset_enums.TaskStatus.DONE)
    assert task.status == aset_enums.TaskStatus.REPORTED
    assert not TaskPoint.objects.exists()
    assert task.komando_events.get().kind == enums.TaskEventKind.SUBMITTED
    list_edit(manager, aset_enums.TaskStatus.DONE)
    assert task.status == aset_enums.TaskStatus.DONE
    assert TaskPoint.objects.filter(task=task, user=field, points=5).exists()


# --------------------------------------------------------------------------
# Laporan harian berjenjang
# --------------------------------------------------------------------------


def send(user, **data):
    return login(user).post(api("laporan-harian/"), data)


def test_daily_report_full_chain(chain, korwil, other_field, private_storage):
    field, coordinator, manager = chain
    own = activity(field, korwil)
    foreign = activity(other_field, korwil, title="Bukan milik petugas")
    home = login(field).get(api("laporan-harian/")).json()
    assert home["supervisor"]["id"] == coordinator.pk and home["can_send"]
    assert [a["id"] for a in home["activities"]] == [own.pk]
    # Kegiatan orang lain tidak bisa ikut dilaporkan.
    assert send(field, isi="x", kegiatan=str(foreign.pk)).status_code == 400
    assert send(field, isi="  ", kegiatan=str(own.pk)).status_code == 400
    compose = login(field).post(api("laporan-harian/susun/"), {"kegiatan": own.pk})
    assert compose.status_code == 200 and own.title in compose.json()["content"]
    response = send(
        field, isi="Komsos selesai.", kegiatan=str(own.pk), lampiran=photo()
    )
    assert response.status_code == 201, response.content
    first = DailyReport.objects.get(pk=response.json()["id"])
    assert first.recipient == coordinator and first.number.startswith("LHR")
    own.refresh_from_db()
    assert own.daily_report == first
    attachment = (
        login(coordinator)
        .get(api(f"laporan-harian/{first.pk}/"))
        .json()["attachments"][0]["url"]
    )
    assert login(coordinator).get(attachment).status_code == 200
    assert login(other_field).get(attachment).status_code == 404
    assert login(other_field).get(api(f"laporan-harian/{first.pk}/")).status_code == 404
    # Koordinator: kembalikan (wajib catatan), petugas memperbaiki.
    url = api(f"laporan-harian/{first.pk}/kembalikan/")
    assert login(field).post(url, {"catatan": "x"}).status_code == 400
    assert login(coordinator).post(url).status_code == 400
    assert login(coordinator).post(url, {"catatan": "Tambah jumlah warga"}).json()[
        "status"
    ] == (enums.DailyReportStatus.RETURNED)
    revise = api(f"laporan-harian/{first.pk}/perbaiki/")
    assert login(coordinator).post(revise, {"isi": "x"}).status_code == 400
    data = login(field).post(revise, {"isi": "Komsos: 25 warga."}).json()
    assert data["status"] == enums.DailyReportStatus.SENT
    # Koordinator bukan puncak: tidak bisa menandai selesai, tetapi merangkum.
    finish = api("laporan-harian/selesai/")
    assert login(coordinator).post(finish, {"laporan": first.pk}).status_code == 400
    response = send(coordinator, isi="Rangkuman Korwil A", laporan=str(first.pk))
    assert response.status_code == 201
    summary = DailyReport.objects.get(pk=response.json()["id"])
    first.refresh_from_db()
    assert summary.recipient == manager and first.consolidated_into == summary
    assert first.status == enums.DailyReportStatus.FORWARDED
    trace = login(field).get(api("laporan-harian/lacak/")).json()["results"]
    assert trace[0]["steps"] == ["Lapangan", "Korwil", "Pengelola"]
    # Pimpinan kembalikan -> koordinator teruskan ke petugas -> naik lagi.
    url = api(f"laporan-harian/{summary.pk}/")
    login(manager).post(url + "kembalikan/", {"catatan": "Perjelas temuan"})
    response = login(coordinator).post(
        url + "teruskan/", {"bawahan": other_field.pk, "catatan": "x"}
    )
    assert response.status_code == 400
    response = login(coordinator).post(
        url + "teruskan/", {"bawahan": field.pk, "catatan": "Lengkapi temuan"}
    )
    assert response.status_code == 200
    summary.refresh_from_db()
    assert summary.revision_owner == field
    assert summary.revision_stack == [manager.pk, coordinator.pk]
    # Petugas bukan pembuat: tidak bisa menutup.
    assert login(field).post(url + "tutup/").status_code == 400
    login(field).post(url + "perbaiki/", {"isi": "Rangkuman + temuan"})
    summary.refresh_from_db()
    assert summary.revision_owner == coordinator
    assert summary.status == enums.DailyReportStatus.RETURNED
    login(coordinator).post(url + "perbaiki/", {"isi": "Rangkuman final"})
    summary.refresh_from_db()
    assert summary.status == enums.DailyReportStatus.SENT
    assert summary.recipient == manager
    response = login(manager).post(finish, {"laporan": summary.pk})
    assert response.json() == {"reviewed": 1}
    trace = login(field).get(api("laporan-harian/lacak/")).json()["results"]
    assert trace[0]["done"] is True


def test_close_releases_sources(chain, korwil):
    field, coordinator, manager = chain
    own = activity(field, korwil)
    first = DailyReport.objects.get(
        pk=send(field, isi="Laporan", kegiatan=str(own.pk)).json()["id"]
    )
    summary = DailyReport.objects.get(
        pk=send(coordinator, isi="Rangkuman", laporan=str(first.pk)).json()["id"]
    )
    url = api(f"laporan-harian/{summary.pk}/")
    login(manager).post(url + "kembalikan/", {"catatan": "Kirim ulang besok"})
    response = login(coordinator).post(url + "tutup/")
    assert response.status_code == 200
    assert response.json()["status"] == enums.DailyReportStatus.CLOSED
    first.refresh_from_db()
    assert first.consolidated_into is None
    assert first.status == enums.DailyReportStatus.SENT
    inbox = login(coordinator).get(api("laporan-harian/")).json()["inbox"]
    assert [r["id"] for r in inbox] == [first.pk]


def test_top_of_chain_cannot_send(chain):
    field, coordinator, manager = chain
    home = login(manager).get(api("laporan-harian/")).json()
    assert home["supervisor"] is None and home["can_finish"] and not home["can_send"]
    assert send(manager, isi="Ke siapa?").status_code == 400


# --------------------------------------------------------------------------
# Persetujuan & lencana
# --------------------------------------------------------------------------


def test_approval_queue_and_badges(chain, korwil):
    field, coordinator, manager = chain
    task = Task.objects.create(
        title="Menunggu verifikasi",
        assignee=field,
        korwil=korwil,
        status=aset_enums.TaskStatus.REPORTED,
    )
    report = send(field, isi="Laporan harian").json()
    Attendance.objects.create(
        user=field,
        date=timezone.localdate() + datetime.timedelta(days=1),
        status=enums.AttendanceStatus.LEAVE,
        approval=enums.LeaveApproval.PENDING,
        korwil=korwil,
    )
    impact = activity(
        field,
        korwil,
        title="Mediasi",
        activity_type=enums.ActivityType.OTHER,
    )
    impact.impact_scope = enums.ImpactScope.values[-1]
    impact.impact_risk = enums.ImpactRisk.values[-1]
    impact.impact_result = enums.ImpactResult.values[-1]
    impact.save()
    data = login(coordinator).get(api("persetujuan/")).json()
    kinds = {(i["kind"], i["id"]) for i in data["pending"]}
    assert ("tugas", task.pk) in kinds and ("laporan", report["id"]) in kinds
    assert any(kind == "izin" for kind, _id in kinds)
    assert impact.needs_impact_confirmation and ("dampak", impact.pk) in kinds
    badges = login(coordinator).get(api("lencana/")).json()
    assert badges["tugas"] == 1 and badges["laporan"] == 1
    assert badges["persetujuan"] == len(data["pending"])
    assert login(field).get(api("lencana/")).json() == {
        "laporan": 0,
        "persetujuan": 0,
        "tugas": 0,
    }
    act(coordinator, task, "verifikasi")
    history = login(coordinator).get(api("persetujuan/")).json()["history"]
    assert history[0]["kind"] == "tugas" and history[0]["approved"] is True


# --------------------------------------------------------------------------
# Rekap Excel
# --------------------------------------------------------------------------


def _sheets(content):
    book = zipfile.ZipFile(io.BytesIO(content))
    names = [n for n in book.namelist() if n.startswith("xl/worksheets/sheet")]
    return book, names


def test_recap_excel_scoped_and_formula_safe(chain, korwil, korwil_b, other_field):
    field, coordinator, manager = chain
    activity(field, korwil, title='=HYPERLINK("http://contoh.invalid","klik")')
    activity(other_field, korwil_b, title="Rahasia Korwil B")
    response = login(field).get(api("rekap/?periode=minggu"))
    assert response.status_code == 200
    assert response["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument"
    )
    assert "rekap-komando-" in response["Content-Disposition"]
    book, sheets = _sheets(response.content)
    xml = "".join(book.read(name).decode() for name in sheets)
    strings = book.read("xl/sharedStrings.xml").decode()
    # Teks berawalan "=" disimpan sebagai teks, bukan rumus.
    assert "<f>" not in xml and "HYPERLINK" in strings
    assert "Rahasia Korwil B" not in strings
    workbook = book.read("xl/workbook.xml").decode()
    assert "Absensi" in workbook and "Tugas" in workbook
    # Korwil di luar wilayah ditolak; rentang tak sah 400.
    assert login(field).get(api(f"rekap/?korwil={korwil_b.pk}")).status_code == 404
    bad = "rekap/?periode=rentang&dari=2026-02-01&sampai=2026-01-01"
    assert login(field).get(api(bad)).status_code == 400
    too_long = "rekap/?periode=rentang&dari=2024-01-01&sampai=2026-01-01"
    assert login(field).get(api(too_long)).status_code == 400
    assert login(field).get(api("rekap/?jenis=bukan")).status_code == 400
    response = login(manager).get(api("rekap/?periode=bulan"))
    assert (
        "Rahasia Korwil B"
        in _sheets(response.content)[0].read("xl/sharedStrings.xml").decode()
    )


def test_new_admin_pages_render(chain, korwil, admin_user):
    field, coordinator, manager = chain
    task = Task.objects.create(title="T", assignee=field, created_by=coordinator)
    TaskEvent.objects.create(task=task, kind=enums.TaskEventKind.CREATED, actor=field)
    send(field, isi="Laporan")
    client = login(admin_user)
    for name in (
        "officerprofile",
        "taskevent",
        "taskpoint",
        "dailyreport",
    ):
        response = client.get(reverse(f"admin:operasi_{name}_changelist"))
        assert response.status_code == 200, name
    report = DailyReport.objects.get()
    response = client.get(reverse("admin:operasi_dailyreport_change", args=[report.pk]))
    assert response.status_code == 200
    # Laporan harian hanya dibaca di panel admin.
    response = client.get(reverse("admin:operasi_dailyreport_add"))
    assert response.status_code == 403
    # Koordinator hanya melihat laporan yang terkait dengannya.
    response = login(coordinator).get(reverse("admin:operasi_dailyreport_changelist"))
    assert report.number in response.content.decode()
