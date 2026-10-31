"""Kegiatan lapangan setara pusat komando rempangops: Komsos (warga baru,
multi-orang, AI sikap), temuan ilegal (baru/berulang), patroli Taman Buru
(temuan, bibit, impor SMART), Kegiatan lainnya (rubrik dampak + konfirmasi
atasan), dan poin usaha KPI."""

import base64
import datetime
import io
import json
import uuid
from decimal import Decimal
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from operasi import enums, patrol, services
from operasi.models import (
    Activity,
    ActivityPhoto,
    CommandSettings,
    HuntingParkPatrol,
    IllegalFinding,
    IllegalFindingVisit,
    PatrolSession,
    Resident,
)
from operasi.tests.conftest import inside, login, make_user, photo
from utils.group_permissions import UserGroup

pytestmark = pytest.mark.django_db

API = "/komando/api/"


def post_activity(client, korwil, **fields):
    point = inside(korwil)
    data = {
        "client_id": str(uuid.uuid4()),
        "lat": str(point.y),
        "lng": str(point.x),
        **fields,
    }
    return client.post(API + "kegiatan/", data)


def noise_jpeg() -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.effect_noise((48, 48), 80).convert("RGB").save(buffer, format="JPEG")
    return buffer.getvalue()


def smart_geojson(korwil) -> bytes:
    point = inside(korwil)
    x, y = point.x, point.y
    picture = base64.b64encode(noise_jpeg()).decode()
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [x + i * 0.001, y]},
            "properties": {"dateTime": f"2026-10-20T08:0{i}:00+07:00"},
        }
        for i in range(4)
    ]
    features += [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [x, y]},
            "properties": {
                "dateTime": "2026-10-20T08:00:00+07:00",
                "sighting": {
                    "SMART_ObservationType": "NewPatrol",
                    "SMART_PatrolID": "RPG-001",
                    "SMART_Objective": "PATROLI WILAYAH SERANGGONG. Rutin",
                    "SMART_Leader": "Budi Santoso",
                    "SMART_Team": "t:kode-tim",
                    "SMART_Comments": "Mulai patroli",
                },
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [x + 0.002, y]},
            "properties": {
                "dateTime": "2026-10-20T08:02:00+07:00",
                "sighting": {
                    "SMART_ObservationType": "Observation",
                    "a:catatan": "TEMUAN JEJAK BABI DI GRID TBPR29. JUMLAH: 3. "
                    "STATUS HUTAN: Sekunder",
                    "SMART_Photo1": picture,
                    "SMART_PatrolLegDistance": 220.5,
                },
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [x + 0.003, y]},
            "properties": {
                "dateTime": "2026-10-20T08:03:00+07:00",
                "sighting": {
                    "SMART_ObservationType": "StopPatrol",
                    "SMART_Comments": "Selesai patroli",
                },
            },
        },
    ]
    return json.dumps({"type": "FeatureCollection", "features": features}).encode()


# --------------------------------------------------------------------------
# Komsos
# --------------------------------------------------------------------------


def test_komsos_registers_new_residents_and_counts_per_person(field, korwil):
    people = [
        {
            "nama": "Siti Aminah",
            "status_warga": "tempatan",
            "gender": "P",
            "pekerjaan": "Nelayan",
            "umur": "54",
            "pekerjaan_pasangan": "Petani",
            "data_anak": "Anak 1 = Rina",
            "sikap": "mendukung",
        },
        {"nama": "Ahmad Yani", "status_warga": "pendatang"},
    ]
    response = post_activity(
        login(field),
        korwil,
        jenis="komsos",
        uraian="Warga bersedia ikut pertemuan relokasi.",
        warga_baru=json.dumps(people),
    )
    assert response.status_code == 201, response.content
    activity = Activity.objects.get()
    assert activity.title == "Komsos (komunikasi sosial): Siti Aminah, Ahmad Yani"
    residents = Resident.objects.order_by("head_name")
    assert [r.head_name for r in residents] == ["Ahmad Yani", "Siti Aminah"]
    siti = residents[1]
    assert siti.registered_activity == activity
    assert siti.korwil == korwil
    assert siti.residency_status == "tempatan"
    assert siti.spouse_occupation == "Petani" and siti.age == 54
    assert siti.stance == enums.Stance.SUPPORT
    assert set(activity.residents.all()) == set(residents)
    # Komsos 6 poin per warga (2 orang) + lokasi GPS 1.
    assert activity.effort_points == Decimal("13.0")


def test_komsos_new_resident_needs_name_and_permission(field, korwil):
    from django.contrib.auth.models import Permission

    client = login(field)
    response = post_activity(
        client, korwil, jenis="komsos", warga_baru=json.dumps([{"umur": "5"}])
    )
    assert response.status_code == 400
    field.groups.clear()
    field.is_staff = True
    field.save(update_fields=["is_staff"])
    for codename in ("view_korwil", "view_activity", "add_activity"):
        field.user_permissions.add(
            Permission.objects.get(codename=codename, content_type__app_label="operasi")
        )
    response = post_activity(
        login(field), korwil, jenis="komsos", warga_baru=json.dumps([{"nama": "X"}])
    )
    assert response.status_code == 403
    assert not Activity.objects.exists() and not Resident.objects.exists()


def test_ai_stance_fills_only_unknown_stances(field, korwil):
    known = Resident.objects.create(
        head_name="Sudah", korwil=korwil, stance=enums.Stance.OPPOSE
    )
    unknown = Resident.objects.create(head_name="Belum", korwil=korwil)
    activity = Activity.objects.create(
        activity_type=enums.ActivityType.KOMSOS,
        title="Komsos",
        description="Warga bersedia pindah ke hunian baru bila jadwal jelas.",
        korwil=korwil,
        reported_by=field,
    )
    activity.residents.set([known, unknown])
    response = mock.Mock(content=[mock.Mock(type="text", text="Pro")])
    with (
        mock.patch("asetlahan.ai.enabled", return_value=True),
        mock.patch("asetlahan.ai.create", return_value=response),
    ):
        assert services.apply_ai_stance(activity.pk) == enums.Stance.SUPPORT
    activity.refresh_from_db()
    known.refresh_from_db()
    unknown.refresh_from_db()
    assert activity.ai_stance == enums.Stance.SUPPORT
    assert known.stance == enums.Stance.OPPOSE
    assert unknown.stance == enums.Stance.SUPPORT
    assert unknown.stance_changes.get().activity == activity


def test_ai_stance_skipped_without_api_key(field, korwil):
    activity = Activity.objects.create(
        activity_type=enums.ActivityType.KOMSOS,
        title="Komsos",
        description="Narasi cukup panjang untuk diklasifikasi.",
        korwil=korwil,
        reported_by=field,
    )
    assert services.apply_ai_stance(activity.pk) == ""


# --------------------------------------------------------------------------
# Temuan ilegal
# --------------------------------------------------------------------------


def test_illegal_finding_new_then_repeat_visit(field, coordinator, korwil):
    client = login(field)
    response = post_activity(
        client,
        korwil,
        jenis="temuan_ilegal",
        ti_aktivitas="pembalakan",
        ti_lokasi="Hutan Pos 500",
        ti_pemilik="Bpk Tampubolon",
        ti_luas="2.5",
        ti_izin="tidak",
        ti_usaha="aktif",
        ti_peralatan="2 chainsaw",
    )
    assert response.status_code == 201, response.content
    finding = IllegalFinding.objects.get()
    assert finding.korwil == korwil and finding.location is not None
    assert finding.area_ha == Decimal("2.5000") and finding.created_by == field
    first = IllegalFindingVisit.objects.get()
    assert first.is_new and first.permit == "tidak"
    assert first.activity.location_name == "Hutan Pos 500"
    assert first.activity.title == "Temuan ilegal – Hutan Pos 500"
    # Kunjungan berulang oleh koordinator: profil diperbarui, kunjungan baru.
    found = login(coordinator).get(API + "temuan-ilegal/?q=Pos 500").json()
    assert [f["id"] for f in found["results"]] == [finding.pk]
    response = post_activity(
        login(coordinator),
        korwil,
        jenis="temuan_ilegal",
        temuan_id=str(finding.pk),
        ti_lokasi="Hutan Pos 500",
        ti_pengurus="Sdr. Anto",
        ti_usaha="tidak",
        ti_tindak="Dipasang papan peringatan",
    )
    assert response.status_code == 201, response.content
    finding.refresh_from_db()
    assert finding.manager_name == "Sdr. Anto"
    assert finding.owner_name == "Bpk Tampubolon"
    assert finding.visits.count() == 2
    assert not finding.visits.get(is_new=False).activity.illegal_visit.is_new


def test_illegal_finding_requires_location_and_scope(
    field, other_field, korwil, korwil_b
):
    client = login(field)
    response = client.post(
        API + "kegiatan/",
        {
            "client_id": str(uuid.uuid4()),
            "jenis": "temuan_ilegal",
            "ti_aktivitas": "tambang",
            "ti_lokasi": "Tanpa GPS",
        },
    )
    assert response.status_code == 400
    other = IllegalFinding.objects.create(
        korwil=korwil_b, location_name="Wilayah lain", location=inside(korwil_b)
    )
    response = post_activity(
        client, korwil, jenis="temuan_ilegal", temuan_id=str(other.pk)
    )
    assert response.status_code == 404
    assert login(field).get(API + "temuan-ilegal/").json()["results"] == []
    assert not Activity.objects.exists()


# --------------------------------------------------------------------------
# Patroli Taman Buru
# --------------------------------------------------------------------------


def test_hunting_park_patrol_with_findings_seedlings_and_photos(field, korwil):
    response = login(field).post(
        API + "kegiatan/",
        {
            "client_id": str(uuid.uuid4()),
            "lat": str(inside(korwil).y),
            "lng": str(inside(korwil).x),
            "jenis": "taman_buru",
            "lokasi": "Seranggong",
            "tb_grid": "TBPR29",
            "tb_rute": "jalur_kayu,perburuan",
            "tb_situasi": "kondusif",
            "tb_cuaca_pagi": "cerah",
            "jarak_m": "3200",
            "temuan_patroli": json.dumps(
                [
                    {
                        "kategori": "fauna",
                        "deskripsi": "Jejak babi",
                        "jumlah": "3",
                        "aktivitas_baru": "tidak",
                    },
                    {"kategori": "flora", "deskripsi": "Pohon meranti"},
                ]
            ),
            "bibit": json.dumps(
                [
                    {"jenis": "dirawat", "nama": "Meranti", "jumlah": "40"},
                    {"jenis": "diproduksi", "nama": "Pulai", "jumlah": "15"},
                ]
            ),
            "foto_temuan_0": [photo("bukti.png")],
        },
    )
    assert response.status_code == 201, response.content
    activity = Activity.objects.get()
    report = HuntingParkPatrol.objects.get()
    assert activity.title == "Patroli Taman Buru – Seranggong"
    assert report.routes == ["jalur_kayu", "perburuan"]
    assert report.seedling_total(enums.SeedlingKind.TENDED) == 40
    assert report.seedling_total(enums.SeedlingKind.PRODUCED) == 15
    babi = report.findings.get(category="fauna")
    assert babi.quantity == 3 and babi.new_activity is False
    assert ActivityPhoto.objects.get().hunting_finding == babi
    # Taman Buru 10 + 2 temuan + 1 foto (0,5) + jarak 3,2 km + GPS 1.
    assert activity.effort_points == Decimal("16.7")
    data = login(field).get(API + "kegiatan/").json()["results"][0]
    assert data["patroli"]["findings"] == 2 and data["patroli"]["tended"] == 40


def test_hunting_park_rejects_bad_rows(field, korwil):
    client = login(field)
    base = {"jenis": "taman_buru", "lokasi": "Seranggong"}
    bad = [
        {"tb_rute": "terbang"},
        {"temuan_patroli": json.dumps([{"deskripsi": ""}])},
        {"bibit": json.dumps([{"jenis": "dirawat", "nama": "X", "jumlah": "-1"}])},
        {"tb_mulai": "2026-10-20T10:00", "tb_selesai": "2026-10-20T08:00"},
        {"lokasi": ""},
    ]
    for extra in bad:
        response = post_activity(client, korwil, **{**base, **extra})
        assert response.status_code == 400, extra
    assert not Activity.objects.exists()


def test_smart_preview_and_import_with_report(field, korwil):
    client = login(field)
    raw = smart_geojson(korwil)
    preview = client.post(
        API + "patroli/pratinjau/",
        {"smart": SimpleUploadedFile("patroli.json", raw)},
    ).json()
    assert preview["location_name"] == "SERANGGONG"
    assert preview["grid"] == "TBPR29"
    assert preview["team_leader"] == "Budi Santoso"
    assert preview["team"] == ""  # kode SMART tidak diisikan
    assert preview["counts"] == {"observations": 3, "track": 4, "photos": 1}
    [finding] = preview["findings"]
    assert finding["category"] == "fauna" and finding["quantity"] == 3
    assert finding["forest_status"] == "Sekunder"
    response = client.post(
        API + "kegiatan/",
        {
            "client_id": str(uuid.uuid4()),
            "jenis": "taman_buru",
            "lokasi": preview["location_name"],
            "tb_mode": "smart",
            "smart": SimpleUploadedFile("patroli.json", raw),
        },
    )
    assert response.status_code == 201, response.content
    activity = Activity.objects.get()
    session = PatrolSession.objects.get()
    assert session.activity == activity and session.korwil == korwil
    assert session.smart_patrol_id == "RPG-001"
    assert session.observations.count() == 3
    assert session.track.num_points == 4 and session.distance_m > 0
    assert activity.location is not None
    assert activity.distance_m == session.distance_m
    photo_obj = session.observations.get(kind="Observation").photos.get()
    url = f"/komando/berkas/patroli-foto/{photo_obj.pk}/"
    assert client.get(url).status_code == 200
    layer = client.get(API + "lapisan/patroli/").json()
    kinds = {f["geometry"]["type"] for f in layer["features"]}
    assert kinds == {"LineString", "Point"}


def test_smart_parser_rejects_garbage():
    with pytest.raises(Exception):
        patrol.parse(b"bukan json")
    with pytest.raises(Exception):
        patrol.parse(json.dumps({"features": []}).encode())


# --------------------------------------------------------------------------
# Kegiatan lainnya: rubrik dampak & konfirmasi atasan
# --------------------------------------------------------------------------


def test_other_activity_impact_needs_supervisor_confirmation(
    field, coordinator, other_field, korwil
):
    client = login(field)
    response = post_activity(client, korwil, jenis="lainnya", judul="Koordinasi")
    assert response.status_code == 400  # rubrik wajib
    response = post_activity(
        client,
        korwil,
        jenis="lainnya",
        judul="Koordinasi aparat",
        dampak_cakupan="2",
        dampak_risiko="2",
        dampak_hasil="1",
    )
    assert response.status_code == 201, response.content
    activity = Activity.objects.get()
    assert activity.impact_tier == enums.ImpactTier.SIGNIFICANT
    assert activity.needs_impact_confirmation
    assert activity.effort_points == Decimal("7.0")  # 6 sementara + GPS 1
    url = API + f"kegiatan/{activity.pk}/konfirmasi-dampak/"
    assert client.post(url).status_code == 403  # pelapor tidak boleh
    assert login(other_field).post(url).status_code in (403, 404)
    listed = login(coordinator).get(API + "kegiatan/?lingkup=korwil").json()
    assert listed["results"][0]["can_confirm"] is True
    response = login(coordinator).post(url)
    assert response.status_code == 200
    activity.refresh_from_db()
    assert activity.impact_confirmed and activity.impact_confirmed_by == coordinator
    assert activity.effort_points == Decimal("10.0")  # 9 + GPS 1
    assert login(coordinator).post(url).status_code == 403  # sudah dikonfirmasi


# --------------------------------------------------------------------------
# Poin usaha, peta, panel admin
# --------------------------------------------------------------------------


def test_effort_bonuses_follow_settings(field, korwil):
    config = CommandSettings.load()
    config.effort_geotag_bonus = Decimal("2")
    config.save()
    activity = Activity.objects.create(
        activity_type=enums.ActivityType.TOPOGRAPHY,
        title="Topografi",
        description="x" * 120,
        location=inside(korwil),
        korwil=korwil,
        reported_by=field,
    )
    # Dasar 4 + narasi 2 + GPS 2.
    assert activity.effort_points == Decimal("8.0")
    config.effort_narrative_bonus = Decimal("0")
    config.save()
    assert services.recompute_effort() == 1
    activity.refresh_from_db()
    assert activity.effort_points == Decimal("6.0")


def test_effort_points_drive_performance_target(field, korwil):
    import math

    start, end = datetime.date(2026, 10, 19), datetime.date(2026, 10, 25)
    field.date_joined = timezone.make_aware(datetime.datetime(2026, 10, 1))
    field.save(update_fields=["date_joined"])
    Activity.objects.create(
        activity_type=enums.ActivityType.HUNTING_PARK,
        title="Patroli",
        korwil=korwil,
        reported_by=field,
        started_at=timezone.make_aware(datetime.datetime(2026, 10, 21, 9)),
    )
    row = services.performance(field, start, end)
    assert row["activities"] == 10 and row["activity_count"] == 1
    assert row["scoring"] == "usaha"
    # Target = 5 kegiatan/minggu × 6 poin, sebanding jumlah hari kerja.
    workdays = len(services._workdays(start, end))
    assert workdays and row["activity_target"] == math.ceil(30 * workdays / 5)


def test_illegal_layer_and_admin_pages(admin_user, field, korwil):
    finding = IllegalFinding.objects.create(
        korwil=korwil, location_name="Hutan Pos 500", location=inside(korwil)
    )
    layer = login(field).get(API + "lapisan/temuan/").json()
    assert [f["properties"]["id"] for f in layer["features"]] == [finding.pk]
    client = login(admin_user)
    for path in (
        "/admin/operasi/illegalfinding/",
        f"/admin/operasi/illegalfinding/{finding.pk}/change/",
        "/admin/operasi/huntingparkpatrol/",
        "/admin/operasi/patrolsession/",
        "/admin/operasi/patrolsession/impor/",
        "/admin/operasi/commandsettings/",
    ):
        assert client.get(path, follow=True).status_code == 200, path


def test_admin_smart_import(admin_user, korwil):
    client = login(admin_user)
    response = client.post(
        "/admin/operasi/patrolsession/impor/",
        {"file": SimpleUploadedFile("p.json", smart_geojson(korwil))},
    )
    assert response.status_code == 302
    session = PatrolSession.objects.get()
    assert session.korwil == korwil and session.activity is None
    assert (
        client.get(f"/admin/operasi/patrolsession/{session.pk}/change/").status_code
        == 200
    )


def test_field_officer_permissions_on_new_models(field):
    for perm in (
        "add_illegalfinding",
        "change_illegalfinding",
        "add_huntingparkpatrol",
        "add_patrolsession",
    ):
        assert field.has_perm(f"operasi.{perm}"), perm
    assert not field.has_perm("operasi.delete_illegalfinding")
    aset = make_user("aset", UserGroup.PETUGAS_ASET)
    assert aset.has_perm("operasi.view_illegalfinding")
    assert not aset.has_perm("operasi.add_illegalfinding")
