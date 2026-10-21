"""Uji batas hak akses per peran & unit layanan (temuan audit izin modul aset lahan)."""

import datetime
import io
import json
from decimal import Decimal

import pytest
from django.contrib import admin as django_admin
from django.contrib.auth.models import Group, Permission
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from asetlahan import enums, geo, scope
from asetlahan.importers import AssetImportError, import_assets
from asetlahan.models import (
    AssetValuation,
    Bid,
    Document,
    EncroachmentCase,
    FieldReport,
    Grievance,
    LegalCase,
    MapShare,
    SurveyRequest,
    Task,
    TaxObligation,
    Tender,
)
from asetlahan.tests.conftest import make_user, square
from utils.group_permissions import UserGroup

pytestmark = pytest.mark.django_db


def grant(user, *perms):
    for perm in perms:
        app_label, codename = perm.split(".")
        user.user_permissions.add(
            Permission.objects.get(content_type__app_label=app_label, codename=codename)
        )
    # Bersihkan cache izin pada objek pengguna.
    for attr in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        user.__dict__.pop(attr, None)
    return user


def model_admin(model):
    return django_admin.site._registry[model]


def admin_request(user, method="get", path="/"):
    request = getattr(RequestFactory(), method)(path)
    request.user = user
    return request


@pytest.fixture
def korwil_user(seeded, units):
    return make_user("korwil", UserGroup.KOORDINATOR_WILAYAH, units=[units[0]])


@pytest.fixture
def project():
    from leasing.models import Municipality
    from pengadaan import enums as pe
    from pengadaan.models import AcquisitionParcel, AcquisitionProject, EntitledParty

    municipality = Municipality.objects.create(name="Kota Uji", identifier="9979")
    project = AcquisitionProject.objects.create(
        name="Proyek Rahasia",
        requiring_agency="Instansi",
        municipality=municipality,
        acquisition_type=pe.AcquisitionType.PUBLIC_INTEREST,
        purpose_category=pe.PublicInterestCategory.ROADS,
    )
    parcel = AcquisitionParcel.objects.create(
        project=project,
        parcel_number="001",
        right_type=pe.LandRightType.SHM,
        measured_area_m2=Decimal(500),
        affected_area_m2=Decimal(200),
        geometry=square(105.0),
    )
    EntitledParty.objects.create(
        parcel=parcel,
        name="Budi Rahasia",
        nik="2171010101900001",
        share_percentage=Decimal(100),
    )
    return project


def _share_post(**extra):
    data = {
        "title": "Peta warga",
        "expires_at_0": "2030-01-01",
        "expires_at_1": "00:00:00",
        "is_active": "on",
    }
    data.update(extra)
    return data


# --------------------------------------------------------------------------
# H1 Peta berbagi
# --------------------------------------------------------------------------


def test_share_rejects_asset_of_other_unit(client, officer, make_asset, units):
    other = make_asset(service_unit=units[1], registered_owner="Pemilik Unit Lain")
    client.force_login(officer)
    page = client.get(reverse("admin:asetlahan_mapshare_add")).content.decode()
    assert other.code not in page
    response = client.post(
        reverse("admin:asetlahan_mapshare_add"),
        _share_post(assets=[other.pk], show_owner_names="on"),
    )
    assert response.status_code == 200
    assert not MapShare.objects.exists()


def test_share_cannot_publish_pengadaan_without_permission(
    client, officer, make_asset, units, project
):
    own = make_asset(service_unit=units[0], registered_owner="Pemilik Sendiri")
    client.force_login(officer)
    page = client.get(reverse("admin:asetlahan_mapshare_add")).content.decode()
    assert 'name="pengadaan_project"' not in page
    response = client.post(
        reverse("admin:asetlahan_mapshare_add"),
        _share_post(
            assets=[own.pk], pengadaan_project=project.pk, show_owner_names="on"
        ),
    )
    assert response.status_code == 302
    share = MapShare.objects.get()
    assert share.pengadaan_project_id is None
    assert share.service_unit == units[0]
    client.logout()
    data = json.dumps(
        client.get(reverse("asetlahan-share-data", args=[share.token])).json()
    )
    assert "Budi Rahasia" not in data
    assert "Pemilik Sendiri" in data


def test_share_owner_names_need_entitled_party_permission(
    client, officer, units, project
):
    grant(
        officer,
        "pengadaan.view_acquisitionproject",
        "pengadaan.view_acquisitionparcel",
    )
    client.force_login(officer)
    response = client.post(
        reverse("admin:asetlahan_mapshare_add"),
        _share_post(pengadaan_project=project.pk, show_owner_names="on"),
    )
    assert response.status_code == 200
    assert "tidak berhak menampilkan nama pemegang hak" in response.content.decode()
    assert not MapShare.objects.exists()
    # Tanpa nama pemilik, bidang proyek boleh dibagikan.
    response = client.post(
        reverse("admin:asetlahan_mapshare_add"),
        _share_post(pengadaan_project=project.pk),
    )
    assert response.status_code == 302
    grant(officer, "pengadaan.view_entitledparty")
    share = MapShare.objects.get()
    share.show_owner_names = True
    share.save()
    data = json.dumps(
        client.get(reverse("asetlahan-share-data", args=[share.token])).json()
    )
    assert "Bidang 001" in data


def test_share_list_scoped_to_unit_or_creator(client, officer, admin, units):
    other = make_user("aset-b", UserGroup.PETUGAS_ASET, units=[units[1]])
    MapShare.objects.create(title="SHARE-UNIT-B", service_unit=units[1])
    MapShare.objects.create(title="SHARE-TANPA-UNIT", created_by=other)
    MapShare.objects.create(title="SHARE-UNIT-A", service_unit=units[0])
    MapShare.objects.create(title="SHARE-SAYA", created_by=officer)
    client.force_login(officer)
    page = client.get(reverse("admin:asetlahan_mapshare_changelist")).content.decode()
    assert "SHARE-UNIT-A" in page and "SHARE-SAYA" in page
    assert "SHARE-UNIT-B" not in page and "SHARE-TANPA-UNIT" not in page
    client.force_login(admin)
    page = client.get(reverse("admin:asetlahan_mapshare_changelist")).content.decode()
    assert "SHARE-UNIT-B" in page and "SHARE-TANPA-UNIT" in page


def test_lawyer_cannot_create_share(client, lawyer):
    assert not lawyer.has_perm("asetlahan.add_mapshare")
    client.force_login(lawyer)
    assert client.get(reverse("admin:asetlahan_mapshare_add")).status_code == 403


# --------------------------------------------------------------------------
# H2 Impor aset
# --------------------------------------------------------------------------


def _geojson(code, name="DIBAJAK"):
    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"kode": code, "nama": name, "nomor_hak": "999"},
                    "geometry": json.loads(square(120.0).geojson),
                }
            ],
        }
    ).encode()


def test_import_does_not_overwrite_other_unit_asset(client, officer, make_asset, units):
    other = make_asset(service_unit=units[1], code="AST-B01", name="Milik Unit B")
    client.force_login(officer)
    response = client.post(
        reverse("admin:asetlahan_landasset_import"),
        {
            "file": SimpleUploadedFile("x.geojson", _geojson("AST-B01")),
            "status": enums.AssetStatus.CONTROLLED,
        },
        follow=True,
    )
    content = response.content.decode()
    assert "AST-B01 sudah dipakai di luar unit layanan" in content
    assert "Milik Unit B" not in content
    other.refresh_from_db()
    assert other.name == "Milik Unit B" and other.title_number != "999"


def test_import_updates_own_asset_only_with_change_permission(
    seeded, officer, make_asset, units
):
    own = make_asset(service_unit=units[0], code="AST-A01")
    clerk = make_user("juru", units=[units[0]])
    grant(clerk, "asetlahan.view_landasset", "asetlahan.add_landasset")
    with pytest.raises(AssetImportError, match="tidak berhak memperbaruinya"):
        import_assets(_geojson("AST-A01"), user=clerk)
    created, updated = import_assets(_geojson("AST-A01", "Baru"), user=officer)
    own.refresh_from_db()
    assert (created, updated) == (0, 1) and own.name == "Baru"


# --------------------------------------------------------------------------
# M1 Terapkan hasil survei
# --------------------------------------------------------------------------


def _survey(asset, unit):
    return SurveyRequest.objects.create(
        purpose="Ukur ulang",
        asset=asset,
        status=enums.SurveyStatus.DONE,
        result_geometry=square(110.0),
        service_unit=unit,
    )


def test_apply_survey_result_requires_asset_change(
    client, field_officer, officer, make_asset, units
):
    asset = make_asset(service_unit=units[0])
    old = asset.geometry.wkt
    survey = _survey(asset, units[0])
    url = reverse("admin:asetlahan_surveyrequest_changelist")
    payload = {"action": "apply_result", "_selected_action": [survey.pk]}
    client.force_login(field_officer)
    client.post(url, payload)
    asset.refresh_from_db()
    assert asset.geometry.wkt == old
    client.force_login(officer)
    client.post(url, payload)
    asset.refresh_from_db()
    assert asset.geometry.wkt != old


def test_apply_survey_result_skips_asset_outside_unit(
    client, officer, make_asset, units
):
    other = make_asset(service_unit=units[1])
    old = other.geometry.wkt
    survey = _survey(other, units[0])
    client.force_login(officer)
    client.post(
        reverse("admin:asetlahan_surveyrequest_changelist"),
        {"action": "apply_result", "_selected_action": [survey.pk]},
    )
    other.refresh_from_db()
    assert other.geometry.wkt == old


# --------------------------------------------------------------------------
# M2 Aksi pembuat objek
# --------------------------------------------------------------------------


def test_create_legal_case_requires_add_permission(
    client, officer, field_officer, admin, units
):
    case = EncroachmentCase.objects.create(
        title="Okupasi", service_unit=units[0], detected_on=timezone.localdate()
    )
    url = reverse("admin:asetlahan_encroachmentcase_changelist")
    payload = {"action": "create_legal_case", "_selected_action": [case.pk]}
    for user in (officer, field_officer):
        client.force_login(user)
        client.post(url, payload)
        assert not LegalCase.objects.exists()
    client.force_login(admin)
    client.post(url, payload)
    assert LegalCase.objects.count() == 1


def test_create_encroachment_requires_add_permission(client, lawyer, officer, units):
    grievance = Grievance.objects.create(
        complainant_name="Warga",
        phone="0812",
        subject="Pagar liar",
        description="d",
        service_unit=units[0],
    )
    url = reverse("admin:asetlahan_grievance_changelist")
    payload = {"action": "create_encroachment", "_selected_action": [grievance.pk]}
    client.force_login(lawyer)
    client.post(url, payload)
    assert not EncroachmentCase.objects.exists()
    client.force_login(officer)
    client.post(url, payload)
    assert EncroachmentCase.objects.count() == 1


# --------------------------------------------------------------------------
# M3 Dokumen mengikuti objek tautannya
# --------------------------------------------------------------------------


@pytest.fixture
def documents(units, make_asset):
    case = LegalCase.objects.create(
        title="Gugatan rahasia", opposing_party="X", service_unit=units[0]
    )
    tender = Tender.objects.create(
        title="Lelang",
        description="d",
        open_at=timezone.now(),
        close_at=timezone.now() + datetime.timedelta(days=1),
        service_unit=units[0],
    )
    asset = make_asset(service_unit=units[0])
    return {
        "legal": Document.objects.create(
            title="Strategi litigasi",
            legal_case=case,
            file=SimpleUploadedFile("s.pdf", b"%PDF-1.4 x"),
            extracted_text="strategi damai nilai 5 miliar",
        ),
        "tender": Document.objects.create(
            title="Evaluasi lelang",
            tender=tender,
            file=SimpleUploadedFile("e.pdf", b"%PDF-1.4 x"),
        ),
        "asset": Document.objects.create(
            title="Sertipikat aset",
            asset=asset,
            file=SimpleUploadedFile("c.pdf", b"%PDF-1.4 x"),
        ),
    }


def test_field_officer_cannot_open_legal_or_tender_documents(
    client, field_officer, documents
):
    client.force_login(field_officer)
    for key in ("legal", "tender"):
        doc = documents[key]
        page = client.get(reverse("admin:asetlahan_document_change", args=[doc.pk]))
        assert page.status_code == 302  # dialihkan: objek tidak ditemukan
        download = client.get(reverse("asetlahan-file", args=["dokumen", doc.pk]))
        assert download.status_code == 404
    results = client.get(reverse("asetlahan-search"), {"q": "miliar"}).content
    assert "5 miliar" not in results.decode()
    changelist = client.get(reverse("admin:asetlahan_document_changelist")).content
    assert "Strategi litigasi" not in changelist.decode()
    assert "Sertipikat aset" in changelist.decode()


def test_lawyer_cannot_edit_asset_or_see_tender_documents(lawyer, documents):
    document_admin = model_admin(Document)
    request = admin_request(lawyer)
    visible = set(document_admin.get_queryset(request))
    assert documents["tender"] not in visible
    assert {documents["legal"], documents["asset"]} <= visible
    assert document_admin.has_change_permission(request, documents["legal"])
    assert document_admin.has_delete_permission(request, documents["legal"])
    assert not document_admin.has_change_permission(request, documents["asset"])
    assert not document_admin.has_delete_permission(request, documents["asset"])


def test_lawyer_bulk_delete_skips_asset_documents(client, lawyer, documents):
    client.force_login(lawyer)
    client.post(
        reverse("admin:asetlahan_document_changelist"),
        {
            "action": "delete_selected",
            "_selected_action": [documents["asset"].pk],
            "post": "yes",
        },
    )
    assert Document.objects.filter(pk=documents["asset"].pk).exists()


def test_document_link_choices_need_change_permission(lawyer, documents):
    form = model_admin(Document).get_form(admin_request(lawyer))()
    assert not form.fields["asset"].queryset.exists()
    assert form.fields["legal_case"].queryset.exists()


def test_documents_helper_respects_link_unit(officer, make_asset, units):
    other = make_asset(service_unit=units[1])
    doc = Document.objects.create(
        title="Tertaut unit lain",
        asset=other,
        service_unit=units[0],
        file=SimpleUploadedFile("x.pdf", b"%PDF-1.4 x"),
    )
    assert doc not in scope.documents(officer)


# --------------------------------------------------------------------------
# M4 Nilai penilaian & catatan terkait
# --------------------------------------------------------------------------


def _valued_asset(make_asset, unit):
    asset = make_asset(service_unit=unit)
    AssetValuation.objects.create(
        asset=asset,
        valuation_date=timezone.localdate(),
        land_value_per_m2=Decimal(1),
        land_value=Decimal("987654321"),
        total_value=Decimal("987654321"),
    )
    AssetValuation.objects.filter(asset=asset).update(total_value=Decimal("987654321"))
    return asset


def test_valuation_hidden_without_permission(
    client, field_officer, korwil_user, officer, make_asset, units
):
    asset = _valued_asset(make_asset, units[0])
    for user in (field_officer, korwil_user):
        assert not user.has_perm("asetlahan.view_assetvaluation")
        client.force_login(user)
        dash = client.get(reverse("asetlahan-dashboard")).content.decode()
        page = client.get(
            reverse("admin:asetlahan_landasset_change", args=[asset.pk])
        ).content.decode()
        assert "Nilai portofolio" not in dash
        assert "987.654.321" not in dash and "987.654.321" not in page
    client.force_login(officer)
    dash = client.get(reverse("asetlahan-dashboard")).content.decode()
    assert "Nilai portofolio" in dash


def test_related_records_follow_permission_and_unit(
    client, field_officer, officer, make_asset, units
):
    asset = make_asset(service_unit=units[0])
    LegalCase.objects.create(
        title="Perkara unit sendiri", opposing_party="X", service_unit=units[0]
    ).assets.add(asset)
    LegalCase.objects.create(
        title="Perkara unit lain", opposing_party="X", service_unit=units[1]
    ).assets.add(asset)
    url = reverse("admin:asetlahan_landasset_change", args=[asset.pk])
    client.force_login(field_officer)
    page = client.get(url).content.decode()
    assert "Perkara unit sendiri" not in page
    client.force_login(officer)
    page = client.get(url).content.decode()
    assert "Perkara unit sendiri" in page and "Perkara unit lain" not in page


# --------------------------------------------------------------------------
# M5 & L4 Sinkronisasi lapangan
# --------------------------------------------------------------------------


def _sync(client, point, client_id, captured="2026-10-20T10:00:00+07:00"):
    return client.post(
        reverse("asetlahan-field-sync"),
        {
            "client_id": client_id,
            "lat": point.y,
            "lng": point.x,
            "captured_at": captured,
        },
    )


def test_field_sync_ignores_asset_of_other_unit(
    client, field_officer, make_asset, units
):
    other = make_asset(service_unit=units[1], name="Aset Unit Lain Rahasia")
    client.force_login(field_officer)
    response = _sync(
        client, other.geometry.centroid, "11111111-1111-1111-1111-111111111111"
    )
    assert response.status_code == 201
    assert "Rahasia" not in response.content.decode()
    report = FieldReport.objects.get()
    assert report.asset_id is None and report.service_unit == units[0]
    other.refresh_from_db()
    assert other.last_monitored_on is None


def test_future_capture_time_does_not_advance_monitoring(
    field_officer, make_asset, units
):
    asset = make_asset(service_unit=units[0])
    FieldReport.objects.create(
        client_id="22222222-2222-2222-2222-222222222222",
        location=asset.geometry.centroid,
        captured_at=timezone.now() + datetime.timedelta(days=30),
        reported_by=field_officer,
    )
    asset.refresh_from_db()
    assert asset.last_monitored_on == timezone.localdate()


def test_duplicate_client_id_of_other_user_not_leaked(
    client, field_officer, officer, make_asset, units
):
    asset = make_asset(service_unit=units[0])
    point = asset.geometry.centroid
    client_id = "33333333-3333-3333-3333-333333333333"
    client.force_login(officer)
    first = _sync(client, point, client_id).json()
    assert _sync(client, point, client_id).json() == {
        "id": first["id"],
        "duplicate": True,
    }
    client.force_login(field_officer)
    response = _sync(client, point, client_id)
    assert response.status_code == 400
    assert "id" not in response.json()
    assert FieldReport.objects.count() == 1


# --------------------------------------------------------------------------
# M6 Penawaran gugur tidak dapat diajukan ulang
# --------------------------------------------------------------------------


def test_evaluated_bid_cannot_be_resubmitted(client, seeded, make_asset):
    from alokasi.models import Applicant
    from users.models import User

    cache.clear()
    now = timezone.now()
    tender = Tender.objects.create(
        title="Lelang",
        description="d",
        asset=make_asset(),
        open_at=now - datetime.timedelta(hours=1),
        close_at=now + datetime.timedelta(days=3),
        status=enums.TenderStatus.ANNOUNCED,
    )
    user = User.objects.create_user(
        username="p@x.id", email="p@x.id", password="RahasiaKuat123!"
    )
    applicant = Applicant.objects.create(
        user=user, name="PT", pic_name="B", phone="0812", address="B"
    )
    Bid.objects.create(
        tender=tender,
        applicant=applicant,
        bidder_name="PT",
        amount=Decimal(100),
        status=enums.BidStatus.DISQUALIFIED,
        evaluation_note="dokumen palsu",
    )
    client.force_login(user)
    response = client.post(
        reverse("aset_portal:bid_submit", args=[tender.number]),
        {"bidder_name": "PT", "email": "p@x.id", "phone": "0812", "amount": "200"},
    )
    assert response.status_code == 302
    bid = Bid.objects.get()
    assert bid.status == enums.BidStatus.DISQUALIFIED and bid.amount == 100


# --------------------------------------------------------------------------
# M7 Pengingat & surel pengaduan per penerima
# --------------------------------------------------------------------------


def test_reminder_summary_per_recipient_scope(seeded, officer, make_asset, units):
    officer_b = make_user("aset-b", UserGroup.PETUGAS_ASET, units=[units[1]])
    asset = make_asset(service_unit=units[1], code="AST-UNITB")
    TaxObligation.objects.create(
        asset=asset, amount=Decimal(100), due_date=timezone.localdate()
    )
    call_command("asetlahan_pengingat", "--email", stdout=io.StringIO())
    bodies = {m.to[0]: m.body for m in mail.outbox if len(m.to) == 1}
    assert "AST-UNITB" in bodies[officer_b.email]
    assert "AST-UNITB" not in bodies.get(officer.email, "")


def test_reminder_summary_skips_data_without_permission(seeded, make_asset, units):
    clerk = make_user("juru", UserGroup.PETUGAS_ASET, units=[units[0]])
    clerk.groups.clear()
    clerk.groups.add(Group.objects.get(pk=UserGroup.PETUGAS_ASET))
    asset = make_asset(service_unit=units[0], code="AST-PAJAK")
    TaxObligation.objects.create(
        asset=asset, amount=Decimal(100), due_date=timezone.localdate()
    )
    Group.objects.get(pk=UserGroup.PETUGAS_ASET).permissions.remove(
        Permission.objects.get(codename="view_taxobligation")
    )
    call_command("asetlahan_pengingat", "--email", stdout=io.StringIO())
    body = "".join(m.body for m in mail.outbox if m.to == [clerk.email])
    assert "[PAJAK]" not in body


def test_new_grievance_email_only_to_officers_of_unit(seeded, officer, units):
    from asetlahan.portal_views import _notify_new_grievance

    officer_b = make_user("aset-b", UserGroup.PETUGAS_ASET, units=[units[1]])
    grievance = Grievance.objects.create(
        complainant_name="Warga",
        phone="0812",
        subject="Pagar",
        description="d",
        service_unit=units[1],
    )
    _notify_new_grievance(grievance)
    recipients = {r for m in mail.outbox for r in m.to}
    assert officer_b.email in recipients
    assert officer.email not in recipients


# --------------------------------------------------------------------------
# M8 M2M dibatasi unit layanan
# --------------------------------------------------------------------------


def test_m2m_asset_choices_scoped_and_preserved(client, lawyer, make_asset, units):
    own = make_asset(service_unit=units[0])
    other = make_asset(service_unit=units[1])
    request = admin_request(lawyer)
    form_class = model_admin(LegalCase).get_form(request)
    assert set(form_class().fields["assets"].queryset) == {own}
    case = LegalCase.objects.create(
        title="Perkara", opposing_party="X", service_unit=units[0]
    )
    case.assets.add(other)
    client.force_login(lawyer)
    response = client.post(
        reverse("admin:asetlahan_legalcase_change", args=[case.pk]),
        {
            "title": "Perkara diubah",
            "case_type": case.case_type,
            "court": case.court,
            "our_position": case.our_position,
            "opposing_party": "X",
            "service_unit": units[0].pk,
            "status": case.status,
            "assets": [own.pk],
            "hearings-TOTAL_FORMS": 0,
            "hearings-INITIAL_FORMS": 0,
            "documents-TOTAL_FORMS": 0,
            "documents-INITIAL_FORMS": 0,
        },
    )
    assert response.status_code == 302, response.content.decode()[:2000]
    case.refresh_from_db()
    assert case.title == "Perkara diubah"
    assert set(case.assets.all()) == {own, other}


# --------------------------------------------------------------------------
# L1 Tugas: petugas lapangan & koordinator wilayah
# --------------------------------------------------------------------------


def test_field_officer_only_updates_progress_of_own_tasks(
    field_officer, officer, units
):
    task_admin = model_admin(Task)
    request = admin_request(field_officer)
    own = Task.objects.create(
        title="Tugas saya", assignee=field_officer, service_unit=units[0]
    )
    others = Task.objects.create(
        title="Tugas orang lain", assignee=officer, service_unit=units[0]
    )
    assert task_admin.has_change_permission(request, own)
    assert not task_admin.has_change_permission(request, others)
    readonly = set(task_admin.get_readonly_fields(request, own))
    assert {"assignee", "korwil", "service_unit", "legal_case"} <= readonly
    assert not {"status", "progress"} & readonly
    # Pengguna penuh tidak dibatasi.
    officer_request = admin_request(officer)
    assert task_admin.has_change_permission(officer_request, own)
    assert "assignee" not in task_admin.get_readonly_fields(officer_request, own)


def test_field_officer_list_edit_limited_to_own_tasks(
    client, field_officer, officer, units
):
    others = Task.objects.create(
        title="Tugas orang lain", assignee=officer, service_unit=units[0]
    )
    client.force_login(field_officer)
    client.post(
        reverse("admin:asetlahan_task_changelist"),
        {
            "form-TOTAL_FORMS": 1,
            "form-INITIAL_FORMS": 1,
            "form-0-id": others.pk,
            "form-0-status": enums.TaskStatus.DONE,
            "form-0-progress": 100,
            "_save": "Simpan",
        },
    )
    others.refresh_from_db()
    assert others.status != enums.TaskStatus.DONE


def test_korwil_coordinator_limited_to_own_korwil(korwil_user, officer, units):
    from operasi.models import Korwil

    mine = Korwil.objects.create(code="A", name="Wilayah A", coordinator=korwil_user)
    other = Korwil.objects.create(code="B", name="Wilayah B")
    task_admin = model_admin(Task)
    request = admin_request(korwil_user)
    own_task = Task.objects.create(title="T1", korwil=mine, service_unit=units[0])
    other_task = Task.objects.create(title="T2", korwil=other, service_unit=units[0])
    assert task_admin.has_change_permission(request, own_task)
    assert not task_admin.has_change_permission(request, other_task)
    form = task_admin.get_form(request, own_task)()
    assert set(form.fields["korwil"].queryset) == {mine}


# --------------------------------------------------------------------------
# L2 Izin Petugas Hukum
# --------------------------------------------------------------------------


def test_lawyer_permissions_match_documentation(lawyer):
    for perm in (
        "view_landtransaction",
        "view_taxobligation",
        "view_assetvaluation",
        "view_mapshare",
        "add_mapshare",
    ):
        assert not lawyer.has_perm(f"asetlahan.{perm}")
    for perm in ("change_legalcase", "change_grievance", "view_landasset"):
        assert lawyer.has_perm(f"asetlahan.{perm}")


def test_permission_sync_revokes_removed_permissions(seeded):
    group = Group.objects.get(pk=UserGroup.PETUGAS_HUKUM)
    group.permissions.add(Permission.objects.get(codename="view_landtransaction"))
    call_command("set_group_model_permissions", verbosity=0, stdout=io.StringIO())
    assert not group.permissions.filter(codename="view_landtransaction").exists()
    assert group.permissions.filter(codename="view_legalcase").exists()


# --------------------------------------------------------------------------
# L3 Tautan ke modul lain
# --------------------------------------------------------------------------


def test_foreign_module_fields_hidden_without_permission(
    client, officer, admin, make_asset, units
):
    asset = make_asset(service_unit=units[0])
    client.force_login(officer)
    page = client.get(
        reverse("admin:asetlahan_landasset_change", args=[asset.pk])
    ).content.decode()
    assert 'name="alokasi_plot"' not in page
    assert 'name="pengadaan_parcel"' not in page
    tender_page = client.get(reverse("admin:asetlahan_tender_add")).content.decode()
    assert 'name="alokasi_plot"' not in tender_page
    client.force_login(admin)
    page = client.get(
        reverse("admin:asetlahan_landasset_change", args=[asset.pk])
    ).content.decode()
    assert 'name="alokasi_plot"' in page


def test_raw_id_heir_and_objection_hidden(lawyer, officer):
    from asetlahan.admin import HeirMemberInline
    from asetlahan.models import Heirship

    inline = HeirMemberInline(Heirship, django_admin.site)
    fields = [
        f
        for _name, options in inline.get_fieldsets(admin_request(officer))
        for f in options["fields"]
    ]
    assert "entitled_party" not in fields
    legal_fields = [
        f
        for _name, options in model_admin(LegalCase).get_fieldsets(
            admin_request(lawyer)
        )
        for f in options["fields"]
    ]
    assert "pengadaan_objection" not in legal_fields


def test_external_overlaps_gated_by_module_permission(
    officer, admin, make_asset, project
):
    asset = make_asset(geometry=square(105.0))
    assert geo.external_overlaps(asset, officer) == {"parcels": [], "plots": []}
    assert geo.external_overlaps(asset, admin)["parcels"]
