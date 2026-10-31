"""Alat pusat komando: tiket & masukan, OCR, AI dokumen/foto, audit data,
uji tanah PLTS (aksi cepat, foto, impor/ekspor Excel), dan sinkron Excel."""

import datetime
import io
import zipfile
from decimal import Decimal

import pytest
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from operasi import enums, geotech, tabular, tools
from operasi.models import (
    GeotechChange,
    GeotechPhoto,
    GeotechPoint,
    LandPlot,
    Ticket,
    geotech_key,
)
from operasi.tests.conftest import inside, login, make_user, photo, png_bytes
from utils.group_permissions import UserGroup

pytestmark = pytest.mark.django_db

BASE = "/komando/api/"
W = enums.GeotechWorkStatus


def point(korwil, code="PV-BH01", **extra):
    location = extra.pop("location", inside(korwil) if korwil else None)
    return GeotechPoint.objects.create(
        code=code, korwil=korwil, location=location, area_name="PV Area", **extra
    )


def csv_file(text: str, name="progres.csv"):
    return SimpleUploadedFile(name, text.encode("utf-8"), "text/csv")


def sheets(content: bytes) -> list[str]:
    book = zipfile.ZipFile(io.BytesIO(content))
    workbook = book.read("xl/workbook.xml").decode()
    return [part.split('"')[0] for part in workbook.split('<sheet name="')[1:]]


@pytest.fixture
def ai_on(settings, monkeypatch):
    settings.ANTHROPIC_API_KEY = "uji"
    calls = []

    def fake(content, schema, max_tokens=3000):
        calls.append({"content": content, "schema": schema})
        return fake.answer

    fake.answer = {}
    monkeypatch.setattr(tools, "_ai_json", fake)
    fake.calls = calls
    return fake


# --------------------------------------------------------------------------
# Pembaca tabel
# --------------------------------------------------------------------------


def test_xlsx_round_trip_reads_strings_numbers_and_gaps(korwil):
    point(korwil, "PV-BH01", batch=2, work_status=W.DONE)
    content = geotech.workbook(GeotechPoint.objects.all())
    sheet, rows = tabular.read_xlsx(content)
    assert sheet == "Uji tanah PLTS"
    assert rows[0][0] == "Kode titik"
    assert rows[1][0] == "PV-BH01"
    assert rows[1][5] == 2  # batch tetap angka
    assert rows[1][11] == 100


def test_csv_reader_detects_semicolon_and_cp1252():
    rows = tabular.read_csv("Kode;Status\nPV 01;Selesai\n".encode("cp1252"))
    assert rows == [["Kode", "Status"], ["PV 01", "Selesai"]]


def test_tabular_rejects_xls_and_broken_zip():
    with pytest.raises(ValidationError):
        tabular.read_table("lama.xls", b"\xd0\xcf\x11\xe0")
    with pytest.raises(ValidationError):
        tabular.read_table("rusak.xlsx", b"bukan zip")


def test_excel_date_and_number_parsing():
    assert tabular.excel_date(45658) == datetime.date(2025, 1, 1)
    assert tabular.excel_date("05/03/2026") == datetime.date(2026, 3, 5)
    assert tabular.excel_date("kemarin") is None
    assert tabular.number("12,5") == 12.5
    assert tabular.number("80%") == 80


# --------------------------------------------------------------------------
# Model titik uji PLTS
# --------------------------------------------------------------------------


def test_geotech_code_key_segment_and_status_normalization(korwil):
    assert geotech_key("pv-bh 01/") == "PVBH01"
    item = point(korwil, "TJB BH1", work_status=W.DONE, progress_pct=20)
    assert item.segment == enums.GeotechSegment.JOINT_BAY
    assert item.progress_pct == 100
    assert item.survey_status == enums.SurveyStatus.DONE
    assert item.finished_on == timezone.localdate()
    item.work_status = W.NOT_STARTED
    item.save()
    assert item.progress_pct == 0
    item.work_status = W.IN_PROGRESS
    item.progress_pct = 100
    item.save()
    assert item.progress_pct == 99


def test_geotech_code_variants_are_one_point(korwil):
    point(korwil, "PV-BH01")
    twin = GeotechPoint(code="PV BH 01", korwil=korwil)
    with pytest.raises(ValidationError) as error:
        twin.full_clean()
    assert "PV-BH01" in str(error.value)


def test_system_recommendations(korwil):
    item = point(
        korwil,
        location=None,
        social_condition=enums.SocialCondition.PROBLEM,
        work_status=W.STOPPED,
        progress_pct=40,
        obstacle="Pemilik menolak",
    )
    tips = " ".join(geotech.system_recommendations(item))
    assert "koordinat" in tips
    assert "koordinasi sosial" in tips
    assert "Pemilik menolak" in tips


# --------------------------------------------------------------------------
# API uji tanah PLTS
# --------------------------------------------------------------------------


def test_points_are_scoped_to_korwil(field, korwil, korwil_b):
    point(korwil, "PV-BH01")
    point(korwil_b, "PV-BH02")
    data = login(field).get(BASE + "uji-plts/").json()
    assert [r["code"] for r in data["rows"]] == ["PV-BH01"]
    assert data["summary"]["total"] == 1
    assert data["can_change"] and not data["can_add"]


def test_point_filters_and_search(coordinator, korwil):
    point(korwil, "PV-BH01", batch=1)
    point(korwil, "TL-TP02", batch=2, method=enums.GeotechMethod.TEST_PIT)
    client = login(coordinator)
    assert [
        r["code"] for r in client.get(BASE + "uji-plts/?q=tl tp").json()["rows"]
    ] == ["TL-TP02"]
    assert [
        r["code"] for r in client.get(BASE + "uji-plts/?batch=1").json()["rows"]
    ] == ["PV-BH01"]
    rows = client.get(BASE + "uji-plts/?bagian=tl").json()["rows"]
    assert [r["code"] for r in rows] == ["TL-TP02"]


def test_coordinator_creates_point_field_cannot(coordinator, field, korwil):
    location = inside(korwil)
    payload = {
        "kode": "SS-ERT01",
        "metode": "resistivitas",
        "area": "Gardu",
        "batch": "2",
        "lat": location.y,
        "lng": location.x,
    }
    assert login(field).post(BASE + "uji-plts/", payload).status_code == 403
    response = login(coordinator).post(BASE + "uji-plts/", payload)
    assert response.status_code == 201, response.content
    data = response.json()
    assert data["segment"] == "gi" and data["korwil"] == "A"


def test_quick_actions_log_history(field, korwil):
    item = point(korwil)
    client = login(field)
    url = BASE + f"uji-plts/{item.pk}/"
    stop = client.post(url + "terhenti/", {})
    assert stop.status_code == 400
    assert (
        client.post(url + "terhenti/", {"catatan": "Akses banjir"}).status_code == 200
    )
    item.refresh_from_db()
    assert item.work_status == W.STOPPED and item.obstacle == "Akses banjir"
    done = client.post(url + "selesai/", {"catatan": "Bor 20 m"}).json()
    assert done["status"] == "selesai" and done["progress"] == 100
    assert done["obstacle"] == ""
    fields = {c["field"] for c in done["history"]}
    assert "Status pekerjaan" in fields and "Progres" in fields
    assert "Bor 20 m" in done["work_note"]
    assert client.post(url + "hapus/", {}).status_code == 400


def test_out_of_scope_point_is_hidden(other_field, korwil, korwil_b):
    item = point(korwil)
    client = login(other_field)
    assert client.get(BASE + f"uji-plts/{item.pk}/").status_code == 404
    assert client.post(BASE + f"uji-plts/{item.pk}/selesai/").status_code == 404


def test_point_form_update(coordinator, korwil):
    item = point(korwil)
    response = login(coordinator).post(
        BASE + f"uji-plts/{item.pk}/",
        {
            "status": "proses",
            "progres": "60",
            "pemilik": "Pak Amat",
            "mulai": "2026-10-01",
        },
    )
    assert response.status_code == 200, response.content
    data = response.json()
    assert data["progress"] == 60 and data["landowner"] == "Pak Amat"
    bad = login(coordinator).post(
        BASE + f"uji-plts/{item.pk}/", {"mulai": "2026-10-05", "selesai": "2026-10-01"}
    )
    assert bad.status_code == 400


def test_point_photos_limit_and_delete(field, other_field, coordinator, korwil):
    item = point(korwil)
    client = login(field)
    for _ in range(geotech.MAX_PHOTOS):
        assert (
            client.post(
                BASE + f"uji-plts/{item.pk}/foto/", {"foto": photo()}
            ).status_code
            == 201
        )
    over = client.post(BASE + f"uji-plts/{item.pk}/foto/", {"foto": photo()})
    assert over.status_code == 400
    first = GeotechPhoto.objects.filter(point=item).first()
    assert login(field).get(f"/komando/berkas/uji-plts/{first.pk}/").status_code == 200
    assert (
        login(other_field).get(f"/komando/berkas/uji-plts/{first.pk}/").status_code
        == 404
    )
    assert client.post(BASE + f"uji-plts/foto/{first.pk}/hapus/").status_code == 200
    second = GeotechPhoto.objects.filter(point=item).first()
    second.uploaded_by = coordinator
    second.save()
    assert client.post(BASE + f"uji-plts/foto/{second.pk}/hapus/").status_code == 403
    assert (
        login(coordinator).post(BASE + f"uji-plts/foto/{second.pk}/hapus/").status_code
        == 200
    )


def test_geotech_layer_and_excel(field, korwil):
    point(korwil, "PV-BH01")
    point(korwil, "PV-BH02", location=None)
    client = login(field)
    layer = client.get(BASE + "lapisan/uji-plts/").json()
    assert [f["properties"]["title"] for f in layer["features"]] == ["PV-BH01"]
    response = client.get(BASE + "uji-plts/excel/")
    assert response.status_code == 200
    _sheet, rows = tabular.read_xlsx(response.content)
    assert [r[0] for r in rows[1:]] == ["PV-BH01", "PV-BH02"]


def test_import_preview_and_apply_updates_by_canonical_code(field, korwil, korwil_b):
    item = point(korwil, "PV-BH01")
    point(korwil_b, "PV-BH09")
    text = (
        "Rekap progres titik\n\n"
        "No;Kode Titik;Jenis;Status;Progres;Tgl Selesai;Kendala\n"
        "1;PV BH 01;Borehole;Selesai;;05/03/2026;\n"
        "2;PV-BH09;Borehole;Selesai;;;\n"
        "3;PV-BH77;Borehole;Belum Mulai;;;\n"
        "4;PV-BH01;Borehole;Selesai;;;\n"
        "5;PV-BH05;Gempa;Selesai;;;\n"
    )
    client = login(field)
    preview = client.post(
        BASE + "uji-plts/impor/", {"berkas": csv_file(text), "mode": "lengkap"}
    )
    assert preview.status_code == 200, preview.content
    actions = [i["action"] for i in preview.json()["items"]]
    # Petugas lapangan tanpa izin tambah: kode baru tidak dibuat.
    assert actions == ["ubah", "luar", "tak_dikenal", "galat", "galat"]
    applied = client.post(
        BASE + "uji-plts/impor/",
        {
            "berkas": csv_file(text),
            "mode": "lengkap",
            "tahap": "terapkan",
            "pilih": "0,1,2",
        },
    ).json()
    assert applied == {"updated": 1, "created": 0, "errors": []}
    item.refresh_from_db()
    assert item.work_status == W.DONE
    assert item.finished_on == datetime.date(2026, 3, 5)
    change = GeotechChange.objects.filter(point=item).first()
    assert change.source == "progres.csv"


def test_import_creates_points_for_coordinator(coordinator, korwil):
    location = inside(korwil)
    text = (
        "Kode titik,Metode,Korwil,Lintang,Bujur,Status pekerjaan\n"
        f"PV-BH30,Sondir,A,{location.y},{location.x},Dalam proses\n"
        "PV-BH31,Test/Trial Pit,,0,0,Belum Mulai\n"
    )
    client = login(coordinator)
    preview = client.post(
        BASE + "uji-plts/impor/", {"berkas": csv_file(text), "mode": "lengkap"}
    ).json()
    assert [i["action"] for i in preview["items"]] == ["baru", "baru"]
    result = client.post(
        BASE + "uji-plts/impor/",
        {
            "berkas": csv_file(text),
            "mode": "lengkap",
            "tahap": "terapkan",
            "pilih": "0,1",
        },
    ).json()
    assert result["created"] == 2, result
    first = GeotechPoint.objects.get(code="PV-BH30")
    assert first.method == enums.GeotechMethod.SONDIR
    assert first.work_status == W.IN_PROGRESS and first.korwil == korwil
    second = GeotechPoint.objects.get(code="PV-BH31")
    assert second.location is None and second.method == enums.GeotechMethod.TEST_PIT
    update_only = client.post(
        BASE + "uji-plts/impor/",
        {"berkas": csv_file(text.replace("PV-BH30", "PV-BH40")), "mode": "perbarui"},
    ).json()
    assert update_only["items"][0]["action"] == "tak_dikenal"


def test_import_requires_code_column(coordinator, korwil):
    response = login(coordinator).post(
        BASE + "uji-plts/impor/", {"berkas": csv_file("Nama,Status\nA,Selesai\n")}
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------
# Tiket & masukan
# --------------------------------------------------------------------------


def test_ticket_points_rule():
    ticket = Ticket(
        category=enums.TicketCategory.BUG,
        priority=enums.TicketPriority.CRITICAL,
        created_at=timezone.now() - datetime.timedelta(hours=10),
    )
    now = timezone.now()
    assert tools.ticket_points(ticket, "selesai", "", now) == (28, Decimal("10.0"))
    ticket.created_at = now - datetime.timedelta(hours=48)
    ticket.category = enums.TicketCategory.SUGGESTION
    ticket.priority = enums.TicketPriority.NORMAL
    assert tools.ticket_points(ticket, "selesai", "", now)[0] == 14
    assert tools.ticket_points(ticket, "ditolak", "Bukan galat", now)[0] == 1
    assert tools.ticket_points(ticket, "ditolak", "", now)[0] == 0
    assert tools.ticket_points(ticket, "diproses", "", now) == (0, None)


def test_ticket_flow(field, other_field, manager, korwil):
    client = login(field)
    created = client.post(
        BASE + "tiket/",
        {
            "kategori": "bug",
            "judul": "Peta kosong",
            "deskripsi": "Ubin tidak muncul",
            "lampiran": photo(),
        },
    )
    assert created.status_code == 201, created.content
    ticket_id = created.json()["id"]
    assert created.json()["number"].startswith("TKT-")
    login(other_field).post(
        BASE + "tiket/",
        {"kategori": "saran", "judul": "Mode gelap", "deskripsi": "Tolong"},
    )
    mine = client.get(BASE + "tiket/").json()
    assert [r["title"] for r in mine["rows"]] == ["Peta kosong"]
    assert not mine["can_handle"]
    attachment = created.json()["attachment"]
    assert client.get(attachment).status_code == 200
    assert login(other_field).get(attachment).status_code == 404
    assert login(manager).get(attachment).status_code == 200
    assert (
        client.post(
            BASE + f"tiket/{ticket_id}/status/", {"status": "selesai"}
        ).status_code
        == 403
    )
    admin = login(manager)
    assert len(admin.get(BASE + "tiket/").json()["rows"]) == 2
    rejected = admin.post(BASE + f"tiket/{ticket_id}/status/", {"status": "ditolak"})
    assert rejected.status_code == 400
    done = admin.post(
        BASE + f"tiket/{ticket_id}/status/",
        {"status": "selesai", "catatan": "Sudah diperbaiki"},
    ).json()
    assert done["points"] == 20 and done["handler"]
    board = client.get(BASE + "tiket/").json()
    assert board["my_points"] == 20
    assert board["leaderboard"][0]["points"] == 20
    reopened = admin.post(
        BASE + f"tiket/{ticket_id}/status/", {"status": "diproses"}
    ).json()
    assert reopened["points"] == 0 and reopened["resolved_at"] == ""


def test_ticket_validation_and_excel(field, manager, korwil):
    client = login(field)
    assert (
        client.post(BASE + "tiket/", {"judul": "", "deskripsi": "x"}).status_code == 400
    )
    bad = SimpleUploadedFile("x.png", b"bukan gambar", "image/png")
    assert (
        client.post(
            BASE + "tiket/", {"judul": "a", "deskripsi": "b", "lampiran": bad}
        ).status_code
        == 400
    )
    client.post(BASE + "tiket/", {"judul": "Lambat", "deskripsi": "Peta lambat"})
    response = login(manager).get(BASE + "tiket/excel/")
    assert response.status_code == 200
    _sheet, rows = tabular.read_xlsx(response.content)
    assert rows[1][2] == "Lambat"


# --------------------------------------------------------------------------
# OCR & AI
# --------------------------------------------------------------------------


def upload(name, data, content_type="application/octet-stream"):
    return SimpleUploadedFile(name, data, content_type)


def test_ocr_without_ai_or_tesseract(field, korwil, monkeypatch):
    monkeypatch.setattr(tools.aset_ocr, "tesseract_available", lambda: False)
    response = login(field).post(
        BASE + "alat/ocr/", {"berkas": upload("nota.png", png_bytes())}
    )
    assert response.status_code == 400
    assert "Tesseract" in response.content.decode()


def test_ocr_with_tesseract(field, korwil, monkeypatch):
    monkeypatch.setattr(tools.aset_ocr, "tesseract_available", lambda: True)
    monkeypatch.setattr(
        tools.aset_ocr, "_image_text", lambda data: "NOTA\nTotal 50.000\n"
    )
    data = (
        login(field)
        .post(BASE + "alat/ocr/", {"berkas": upload("nota.png", png_bytes())})
        .json()
    )
    assert data["source"] == "ocr" and "Total 50.000" in data["text"]


def test_ocr_with_ai(field, korwil, ai_on):
    ai_on.answer = {
        "jenis_dokumen": "Nota",
        "teks": "Total 50.000",
        "isian": [{"label": "Total", "nilai": "50.000"}],
    }
    data = (
        login(field)
        .post(BASE + "alat/ocr/", {"berkas": upload("nota.jpg", png_bytes())})
        .json()
    )
    assert data == {
        "source": "ai",
        "type": "Nota",
        "text": "Total 50.000",
        "fields": [{"label": "Total", "nilai": "50.000"}],
    }
    assert ai_on.calls[0]["content"][0]["type"] == "image"
    assert (
        login(field)
        .post(BASE + "alat/ocr/", {"berkas": upload("a.docx", b"x")})
        .status_code
        == 400
    )


def test_document_profile_without_ai(field, korwil):
    text = "Korwil,Warga,Luas\nA,10,1.5\nB,20,2.5\nA,5,1\n"
    data = (
        login(field)
        .post(BASE + "alat/dokumen-ai/", {"berkas": upload("rekap.csv", text.encode())})
        .json()
    )
    assert data["ai"] is False and "AI belum dikonfigurasi" in data["message"]
    columns = {c["name"]: c for c in data["profile"]["columns"]}
    assert data["profile"]["rows"] == 3
    assert columns["Warga"]["total"] == 35
    assert columns["Korwil"]["top"][0] == {"value": "A", "count": 2}


def test_document_report_with_ai_and_quota(field, korwil, ai_on, monkeypatch):
    ai_on.answer = {
        "judul": "Rekap",
        "ringkasan": "Ringkas",
        "temuan_utama": ["A"],
        "data_kunci": [{"label": "Warga", "nilai": "35"}],
        "rekomendasi": ["B"],
    }
    client = login(field)
    data = client.post(
        BASE + "alat/dokumen-ai/",
        {"berkas": upload("catatan.txt", b"Warga 35 orang"), "fokus": "warga"},
    ).json()
    assert data["ai"] is True and data["report"]["judul"] == "Rekap"
    assert "Fokus pengguna: warga" in ai_on.calls[0]["content"][1]["text"]
    monkeypatch.setattr(tools, "AI_LIMIT_PER_HOUR", 1)
    over = client.post(
        BASE + "alat/dokumen-ai/", {"berkas": upload("catatan.txt", b"lagi")}
    )
    assert over.status_code == 400


def test_field_photo_ai(field, korwil, ai_on, settings):
    ai_on.answer = {
        "ringkasan": "Pembukaan lahan baru",
        "temuan": [
            {
                "label": "Lahan dibuka",
                "kategori": "pembukaan",
                "keyakinan": "tinggi",
                "x0": 0.8,
                "y0": 1.4,
                "x1": 0.2,
                "y1": -1,
                "catatan": "",
            },
            {
                "label": "?",
                "kategori": "aneh",
                "keyakinan": "rendah",
                "x0": 0,
                "y0": 0,
                "x1": 1,
                "y1": 1,
                "catatan": "",
            },
        ],
        "rekomendasi": ["Cek pemilik"],
    }
    client = login(field)
    data = client.post(
        BASE + "alat/foto-lapangan-ai/",
        {"berkas": upload("drone.png", png_bytes((40, 30)))},
    ).json()
    assert data["findings"][0]["box"] == [0.2, 0.0, 0.8, 1.0]
    assert data["findings"][1]["category"] == "lain"
    assert data["recommendations"] == ["Cek pemilik"]
    bad = client.post(
        BASE + "alat/foto-lapangan-ai/", {"berkas": upload("drone.png", b"bukan foto")}
    )
    assert bad.status_code == 400
    settings.ANTHROPIC_API_KEY = ""
    off = client.post(
        BASE + "alat/foto-lapangan-ai/", {"berkas": upload("drone.png", png_bytes())}
    )
    assert off.status_code == 400


# --------------------------------------------------------------------------
# Audit data
# --------------------------------------------------------------------------


def test_data_audit_scoped_and_permissioned(
    field, coordinator, manager, korwil, korwil_b
):
    assert login(field).get(BASE + "alat/audit-data/").status_code == 403
    point(korwil, "PV-BH01", location=None)
    point(korwil, "PV-BH02", location=Point(110.0, -5.0, srid=4326))
    point(korwil_b, "PV-BH03", location=None)
    data = login(coordinator).get(BASE + "alat/audit-data/").json()
    labels = {g["label"]: g for g in data["groups"]}
    assert labels["Titik uji PLTS tanpa koordinat"]["sample"] == ["PV-BH01"]
    assert labels["Titik uji PLTS di luar wilayah kerja"]["count"] == 1
    assert data["status"] == "tindakan" and data["work_area"]
    full = login(manager).get(BASE + "alat/audit-data/").json()
    assert {g["label"]: g for g in full["groups"]}["Titik uji PLTS tanpa koordinat"][
        "count"
    ] == 2
    lonely = make_user("tanpakorwil", UserGroup.PETUGAS_LAPANGAN)
    names = {
        g["label"]: g
        for g in login(manager).get(BASE + "alat/audit-data/").json()["groups"]
    }
    sample = names["Petugas lapangan/koordinator tanpa Korwil"]["sample"]
    assert tools._name(lonely) in sample
    assert login(manager).post(BASE + "alat/audit-data/").status_code == 400


def test_data_audit_ai_summary(manager, korwil, settings, monkeypatch):
    settings.ANTHROPIC_API_KEY = "uji"

    class Response:
        pass

    monkeypatch.setattr(tools.ai, "create", lambda **kw: Response())
    monkeypatch.setattr(tools.ai, "text_of", lambda r: "Prioritas: lengkapi koordinat.")
    point(korwil, location=None)
    data = login(manager).post(BASE + "alat/audit-data/").json()
    assert data["summary"] == "Prioritas: lengkapi koordinat."


# --------------------------------------------------------------------------
# Sinkron Excel & konfigurasi
# --------------------------------------------------------------------------


def test_sync_excel_sheets_follow_permissions(field, manager, korwil):
    point(korwil, "PV-BH01", work_status=W.DONE)
    LandPlot.objects.create(korwil=korwil, geometry=korwil.geometry, name="Bidang 1")
    Ticket.objects.create(title="a", description="b", created_by=field)
    field_book = login(field).get(BASE + "alat/sinkron-excel/").content
    assert sheets(field_book) == ["Ringkasan Korwil", "Bidang lahan", "Uji tanah PLTS"]
    admin_book = login(manager).get(BASE + "alat/sinkron-excel/").content
    assert sheets(admin_book)[-1] == "Tiket"
    _sheet, rows = tabular.read_xlsx(admin_book, "Ringkasan Korwil")
    korwil_row = [r for r in rows if r and r[0] == "A"][0]
    assert korwil_row[6] == 1 and korwil_row[10] == 1 and korwil_row[11] == 1


def test_config_exposes_tool_permissions(field, coordinator, manager, korwil):
    from django.test import RequestFactory

    from operasi.views import _config

    def config(user):
        request = RequestFactory().get("/komando/")
        request.user = user
        return _config(request)

    data = config(field)
    assert (
        data["perms"]["kirimTiket"]
        and data["perms"]["ujiPlts"]
        and data["perms"]["ubahUjiPlts"]
    )
    assert not data["perms"]["tanganiTiket"] and not data["perms"]["auditData"]
    assert not data["perms"]["tambahUjiPlts"]
    assert data["urls"]["geotech"] == BASE + "uji-plts/"
    assert config(coordinator)["perms"]["auditData"]
    assert config(manager)["perms"]["tanganiTiket"]


# --------------------------------------------------------------------------
# Panel admin
# --------------------------------------------------------------------------


def test_admin_ticket_archive_is_scoped_and_read_only(field, other_field, manager):
    own = Ticket.objects.create(title="Punya saya", description="x", created_by=field)
    other = Ticket.objects.create(
        title="Punya orang lain", description="x", created_by=other_field
    )
    client = login(field)
    page = client.get("/admin/operasi/ticket/").content.decode()
    assert "Punya saya" in page and "Punya orang lain" not in page
    assert client.get(f"/admin/operasi/ticket/{other.pk}/change/").status_code == 302
    detail = client.get(f"/admin/operasi/ticket/{own.pk}/change/")
    assert detail.status_code == 200 and b'name="status"' not in detail.content
    page = login(manager).get("/admin/operasi/ticket/").content.decode()
    assert "Punya saya" in page and "Punya orang lain" in page


def test_admin_point_scope_history_and_excel(coordinator, field, korwil, korwil_b):
    from django.contrib.admin.sites import site
    from django.test import RequestFactory

    mine = point(korwil, "PV-ADM01")
    point(korwil_b, "PV-LAIN01")
    page = login(field).get("/admin/operasi/geotechpoint/").content.decode()
    assert "PV-ADM01" in page and "PV-LAIN01" not in page
    admin_class = site._registry[GeotechPoint]
    request = RequestFactory().post("/")
    request.user = coordinator
    mine.work_status = W.DONE
    admin_class.save_model(request, mine, None, change=True)
    change = GeotechChange.objects.get(point=mine, field="Status pekerjaan")
    assert change.new_value == "Selesai" and change.source == "Panel admin"
    response = admin_class.export_excel(
        request, GeotechPoint.objects.filter(pk=mine.pk)
    )
    assert response["Content-Type"].startswith("application/vnd.openxmlformats")
    assert sheets(response.content) == ["Uji tanah PLTS"]
