"""Hak akses per peran modul pengadaan (temuan audit izin)."""

import datetime
import io
import itertools
import zipfile
from decimal import Decimal

import pytest
from django.contrib.admin.sites import site as admin_site
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import RequestFactory
from rest_framework.test import APIClient

from pengadaan import enums
from pengadaan.admin import PartyInline
from pengadaan.models import (
    AcquisitionDocument,
    AcquisitionMilestone,
    AcquisitionParcel,
    AcquisitionProject,
    AffectedHousehold,
    Announcement,
    Compensation,
    CompensationPayment,
    Consignment,
    Deliberation,
    DeliberationResult,
    EntitledParty,
    Handover,
    Objection,
    RightsRelease,
    Valuation,
)
from utils.group_permissions import UserGroup

API = "/v1/pengadaan"
D = datetime.date
_counter = itertools.count()


@pytest.fixture
def groups(db):
    for group in UserGroup:
        Group.objects.get_or_create(id=group.value, defaults={"name": group.name})
    call_command("set_group_model_permissions", stdout=io.StringIO())


@pytest.fixture
def user_in(groups, django_user_model):
    def _make(*group_ids, projects=()):
        user = django_user_model.objects.create_user(
            username=f"peran{next(_counter)}", password="RahasiaKuat123!"
        )
        for gid in group_ids:
            user.groups.add(Group.objects.get(id=gid))
        for project in projects:
            project.assigned_users.add(user)
        return user

    return _make


@pytest.fixture
def client_in(user_in):
    def _make(*group_ids, projects=()):
        client = APIClient()
        client.force_authenticate(user_in(*group_ids, projects=projects))
        return client

    return _make


@pytest.fixture
def other_project(project):
    return AcquisitionProject.objects.create(
        name="Proyek Lain",
        requiring_agency="Dinas Lain",
        municipality=project.municipality,
    )


@pytest.fixture
def other_parcel(other_project):
    return AcquisitionParcel.objects.create(project=other_project, parcel_number="X1")


def _ids(response):
    assert response.status_code == 200, response.content
    data = response.json()
    rows = data["results"] if isinstance(data, dict) else data
    return {row["id"] for row in rows}


def _validated(parcel, party, amount="1000", **kwargs):
    return Compensation.objects.create(
        parcel=parcel,
        party=party,
        amount=Decimal(amount),
        status=enums.CompensationStatus.VALIDATED,
        validated_on=D(2026, 1, 5),
        **kwargs,
    )


def _status(parcel):
    return AcquisitionParcel.all_objects.get(pk=parcel.pk).status


# 1. Status ganti kerugian hanya berubah lewat aksi


@pytest.mark.django_db
def test_billing_cannot_validate_or_settle_compensation_itself(
    client_in, parcel, party
):
    compensation = Compensation.objects.create(
        parcel=parcel, party=party, amount=Decimal("1000")
    )
    billing = client_in(UserGroup.LASKUTTAJA)
    url = f"{API}/compensation/{compensation.id}/"

    assert billing.post(f"{url}validate/").status_code == 403
    response = billing.patch(url, {"status": "validated"}, format="json")
    assert response.status_code == 200
    assert response.json()["status"] == enums.CompensationStatus.DETERMINED
    response = billing.post(
        f"{API}/payment/",
        {"compensation": compensation.id, "paid_on": "2026-01-01", "amount": "1000"},
        format="json",
    )
    assert response.status_code == 400
    compensation.refresh_from_db()
    assert compensation.status == enums.CompensationStatus.DETERMINED
    assert not compensation.payments.exists()

    in_kind = Compensation.objects.create(
        parcel=parcel, party=party, form=enums.CompensationForm.REPLACEMENT_LAND
    )
    billing.patch(
        f"{API}/compensation/{in_kind.id}/", {"status": "paid"}, format="json"
    )
    in_kind.refresh_from_db()
    assert in_kind.status == enums.CompensationStatus.DETERMINED
    assert _status(parcel) != enums.ParcelStatus.PAID


@pytest.mark.django_db
def test_new_compensation_always_starts_determined(client_in, parcel, party):
    response = client_in(UserGroup.PELAKSANA_PENGADAAN).post(
        f"{API}/compensation/",
        {
            "parcel": parcel.id,
            "party": party.id,
            "amount": "1000",
            "status": "validated",
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    compensation = Compensation.objects.get(pk=response.json()["id"])
    assert compensation.status == enums.CompensationStatus.DETERMINED
    assert compensation.validated_by is None


@pytest.mark.django_db
def test_editing_validated_compensation_resets_validation(client_in, parcel, party):
    pelaksana = client_in(UserGroup.PELAKSANA_PENGADAAN)
    compensation = Compensation.objects.create(
        parcel=parcel, party=party, amount=Decimal("1000")
    )
    url = f"{API}/compensation/{compensation.id}/"
    assert pelaksana.post(f"{url}validate/").status_code == 200

    response = pelaksana.patch(url, {"note": "catatan"}, format="json")
    assert response.json()["status"] == enums.CompensationStatus.VALIDATED
    assert "notice" not in response.json()

    response = pelaksana.patch(url, {"amount": "2000"}, format="json")
    assert response.status_code == 200, response.content
    assert response.json()["status"] == enums.CompensationStatus.DETERMINED
    assert response.json()["notice"]
    compensation.refresh_from_db()
    assert compensation.validated_by is None
    assert compensation.validated_on is None


@pytest.mark.django_db
def test_paid_compensation_cannot_be_edited(client_in, parcel, party):
    compensation = _validated(parcel, party)
    CompensationPayment.objects.create(
        compensation=compensation, paid_on=D(2026, 1, 6), amount=Decimal("1000")
    )
    pelaksana = client_in(UserGroup.PELAKSANA_PENGADAAN)
    url = f"{API}/compensation/{compensation.id}/"
    assert pelaksana.patch(url, {"amount": "5000"}, format="json").status_code == 400
    assert pelaksana.patch(url, {"note": "lunas"}, format="json").status_code == 200
    compensation.refresh_from_db()
    assert compensation.amount == Decimal("1000")
    assert compensation.status == enums.CompensationStatus.PAID


@pytest.mark.django_db
def test_cancel_and_deliver_actions(client_in, parcel, party):
    money = Compensation.objects.create(
        parcel=parcel, party=party, amount=Decimal("1000")
    )
    assert (
        client_in(UserGroup.LASKUTTAJA)
        .post(f"{API}/compensation/{money.id}/cancel/")
        .status_code
        == 403
    )
    pelaksana = client_in(UserGroup.PELAKSANA_PENGADAAN)
    response = pelaksana.post(f"{API}/compensation/{money.id}/cancel/")
    assert response.status_code == 200, response.content
    assert response.json()["status"] == enums.CompensationStatus.CANCELLED

    in_kind = Compensation.objects.create(
        parcel=parcel, party=party, form=enums.CompensationForm.REPLACEMENT_LAND
    )
    deliver = f"{API}/compensation/{in_kind.id}/deliver/"
    billing = client_in(UserGroup.LASKUTTAJA)
    # Belum divalidasi Ketua Pelaksana.
    assert billing.post(deliver).status_code == 400
    assert pelaksana.post(f"{API}/compensation/{in_kind.id}/validate/").status_code
    assert client_in(UserGroup.SATGAS_PENGADAAN).post(deliver).status_code == 403
    response = billing.post(deliver)
    assert response.status_code == 200, response.content
    assert response.json()["status"] == enums.CompensationStatus.PAID
    assert _status(parcel) == enums.ParcelStatus.PAID

    other = _validated(parcel, party)
    response = billing.post(f"{API}/compensation/{other.id}/deliver/")
    assert response.status_code == 400


@pytest.mark.django_db
def test_consignment_marks_compensation_consigned(parcel, party):
    compensation = _validated(parcel, party)
    consignment = Consignment.objects.create(
        parcel=parcel,
        party=party,
        status=enums.ConsignmentStatus.DEPOSITED,
        amount=Decimal("1000"),
    )
    compensation.refresh_from_db()
    assert compensation.status == enums.CompensationStatus.CONSIGNED
    consignment.delete()
    compensation.refresh_from_db()
    assert compensation.status == enums.CompensationStatus.VALIDATED


# 2. Instansi pemohon tidak melihat pihak dan nilai uang


@pytest.mark.django_db
def test_requesting_agency_sees_no_parties_or_money(client_in, project, parcel, party):
    AcquisitionParcel.objects.filter(pk=parcel.pk).update(
        geometry="SRID=4326;MULTIPOLYGON(((104 1,104.001 1,104.001 1.001,104 1)))"
    )
    _validated(parcel, party)
    agency = client_in(UserGroup.INSTANSI_PEMOHON, projects=[project])
    pelaksana = client_in(UserGroup.PELAKSANA_PENGADAAN)
    money_keys = {
        "party_count",
        "valuation_total",
        "compensation_total",
        "paid_total",
        "consigned_total",
    }

    summary_url = f"{API}/project/{project.id}/summary/"
    assert not money_keys & agency.get(summary_url).json().keys()
    assert money_keys <= pelaksana.get(summary_url).json().keys()

    geojson_url = f"{API}/project/{project.id}/geojson/"
    properties = agency.get(geojson_url).json()["features"][0]["properties"]
    assert "parties" not in properties
    properties = pelaksana.get(geojson_url).json()["features"][0]["properties"]
    assert properties["parties"] == "Budi Santoso"

    parcel_url = f"{API}/parcel/{parcel.id}/"
    assert "party_names" not in agency.get(parcel_url).json()
    assert agency.get(f"{API}/parcel/", {"search": "Budi"}).json()["count"] == 0
    assert pelaksana.get(parcel_url).json()["party_names"] == "Budi Santoso"

    nominative_url = f"{API}/project/{project.id}/nominative_list/"
    assert agency.get(nominative_url).status_code == 403
    response = pelaksana.get(nominative_url)
    assert response.status_code == 200
    strings = zipfile.ZipFile(io.BytesIO(response.content)).read("xl/sharedStrings.xml")
    assert b"Budi" in strings

    dashboard = agency.get(f"{API}/dashboard/").json()
    assert not {"compensation_total", "paid_total"} & dashboard.keys()
    assert "compensation_total" in pelaksana.get(f"{API}/dashboard/").json()


# 3. Dokumen berisi data pribadi


@pytest.mark.django_db
def test_sensitive_documents_hidden_without_personal_data_permission(
    client_in, project, parcel, party
):
    def _doc(document_type, **kwargs):
        return AcquisitionDocument.objects.create(
            project=project,
            document_type=document_type,
            title=document_type,
            file=SimpleUploadedFile(f"{document_type}.pdf", b"%PDF-1.4 rahasia"),
            **kwargs,
        )

    public = _doc(enums.DocumentType.LOCATION_DECREE)
    sensitive = [
        _doc(enums.DocumentType.ID_CARD),
        _doc(enums.DocumentType.CERTIFICATE, parcel=parcel),
        _doc(enums.DocumentType.PAYMENT_PROOF),
        _doc(enums.DocumentType.OTHER, parcel=parcel, party=party),
    ]
    for group in (
        UserGroup.SELAILIJA,
        UserGroup.LASKUTTAJA,
        UserGroup.PENILAI,
        UserGroup.INSTANSI_PEMOHON,
    ):
        client = client_in(group, projects=[project])
        assert _ids(client.get(f"{API}/document/")) == {public.id}, group
        for doc in sensitive:
            assert client.get(f"{API}/document/{doc.id}/").status_code == 404
            response = client.get(f"{API}/document/{doc.id}/download/")
            assert response.status_code == 404, group
        assert client.get(f"{API}/document/{public.id}/download/").status_code == 200

    for group in (UserGroup.PELAKSANA_PENGADAAN, UserGroup.SATGAS_PENGADAAN):
        client = client_in(group)
        assert len(_ids(client.get(f"{API}/document/"))) == 5
        response = client.get(f"{API}/document/{sensitive[0].id}/download/")
        assert response.status_code == 200


# 4. Penilai dan instansi pemohon hanya melihat proyek yang ditugaskan


@pytest.mark.django_db
def test_external_roles_only_see_assigned_projects(  # noqa: C901
    client_in, project, parcel, party, other_project, other_parcel
):
    for target in (project, other_project):
        Announcement.objects.create(
            project=target,
            announcement_type=enums.AnnouncementType.OTHER,
            announced_on=D(2026, 1, 5),
        )
        Deliberation.objects.create(project=target, held_on=D(2026, 1, 5))
        Handover.objects.create(project=target, handed_over_on=D(2026, 1, 5))
        AcquisitionDocument.objects.create(
            project=target,
            title="SK",
            document_type=enums.DocumentType.LOCATION_DECREE,
            file=SimpleUploadedFile("sk.pdf", b"%PDF-1.4"),
        )
    other_party = EntitledParty.objects.create(parcel=other_parcel, name="Lain")
    Valuation.objects.create(parcel=parcel)
    Valuation.objects.create(parcel=other_parcel)
    _validated(parcel, party)
    _validated(other_parcel, other_party)

    endpoints = {
        "project": AcquisitionProject,
        "milestone": AcquisitionMilestone,
        "parcel": AcquisitionParcel,
        "announcement": Announcement,
        "deliberation": Deliberation,
        "handover": Handover,
        "document": AcquisitionDocument,
        "party": EntitledParty,
        "valuation": Valuation,
        "compensation": Compensation,
    }
    lookups = {
        AcquisitionProject: "pk",
        EntitledParty: "parcel__project",
        Valuation: "parcel__project",
        Compensation: "parcel__project",
    }
    appraiser = client_in(UserGroup.PENILAI, projects=[project])
    agency = client_in(UserGroup.INSTANSI_PEMOHON, projects=[project])
    for client, name in ((appraiser, "penilai"), (agency, "instansi")):
        for endpoint, model in endpoints.items():
            response = client.get(f"{API}/{endpoint}/")
            if response.status_code == 403:
                continue
            lookup = lookups.get(model, "project")
            expected = set(
                model.objects.filter(**{lookup: project.pk}).values_list(
                    "id", flat=True
                )
            )
            assert _ids(response) == expected, (name, endpoint)
            assert expected, (name, endpoint)
        for action in ("summary", "geojson"):
            url = f"{API}/project/{other_project.id}/{action}/"
            assert client.get(url).status_code == 404
        deadlines = client.get(f"{API}/deadlines/").json()
        assert all(d["project_id"] == project.id for d in deadlines)
        dashboard = client.get(f"{API}/dashboard/").json()
        assert sum(dashboard["projects_by_status"].values()) == 1
        assert sum(dashboard["parcels_by_status"].values()) == 1

    other_nominative = f"{API}/project/{other_project.id}/nominative_list/"
    assert appraiser.get(other_nominative).status_code == 404
    assert (
        appraiser.get(f"{API}/project/{project.id}/nominative_list/").status_code == 200
    )
    total = appraiser.get(f"{API}/dashboard/").json()["compensation_total"]
    assert Decimal(str(total)) == Decimal("1000")

    # Relasi ke proyek yang tidak ditugaskan ditolak.
    response = appraiser.post(
        f"{API}/valuation/", {"parcel": other_parcel.id}, format="json"
    )
    assert response.status_code == 400
    assert "parcel" in response.json()
    assert (
        appraiser.post(
            f"{API}/valuation/", {"parcel": parcel.id}, format="json"
        ).status_code
        == 201
    )
    response = agency.post(
        f"{API}/document/",
        {
            "project": other_project.id,
            "document_type": enums.DocumentType.DPPT,
            "title": "DPPT",
            "file": SimpleUploadedFile("dppt.pdf", b"%PDF-1.4"),
        },
        format="multipart",
    )
    assert response.status_code == 400
    assert "project" in response.json()

    # Peran internal (juga bila digabung dengan peran eksternal) melihat semua.
    for client in (
        client_in(UserGroup.PELAKSANA_PENGADAAN),
        client_in(UserGroup.PAAKAYTTAJA),
        client_in(UserGroup.SELAILIJA, UserGroup.PENILAI),
    ):
        assert _ids(client.get(f"{API}/project/")) == {project.id, other_project.id}
        assert "assigned_users" in client.get(f"{API}/project/{project.id}/").json()
    assert "assigned_users" not in appraiser.get(f"{API}/project/{project.id}/").json()


@pytest.mark.django_db
def test_project_assignment_is_editable_by_implementer(
    client_in, user_in, other_project
):
    appraiser_user = user_in(UserGroup.PENILAI)
    response = client_in(UserGroup.PELAKSANA_PENGADAAN).patch(
        f"{API}/project/{other_project.id}/",
        {"assigned_users": [appraiser_user.id]},
        format="json",
    )
    assert response.status_code == 200, response.content
    assert response.json()["assigned_users"] == [appraiser_user.id]
    appraiser = APIClient()
    appraiser.force_authenticate(appraiser_user)
    assert _ids(appraiser.get(f"{API}/project/")) == {other_project.id}


# 5 & 14. Pelepasan hak


@pytest.mark.django_db
def test_rights_release_parcel_cannot_be_moved(client_in, project, parcel, party):
    unpaid = AcquisitionParcel.objects.create(project=project, parcel_number="002")
    compensation = _validated(parcel, party)
    CompensationPayment.objects.create(
        compensation=compensation, paid_on=D(2026, 1, 6), amount=Decimal("1000")
    )
    satgas = client_in(UserGroup.SATGAS_PENGADAAN)
    response = satgas.post(
        f"{API}/rights_release/",
        {"parcel": parcel.id, "released_on": "2026-01-07"},
        format="json",
    )
    assert response.status_code == 201, response.content
    url = f"{API}/rights_release/{response.json()['id']}/"
    response = satgas.patch(url, {"parcel": unpaid.id}, format="json")
    assert response.status_code == 400
    assert "parcel" in response.json()
    assert _status(unpaid) != enums.ParcelStatus.RELEASED
    assert _status(parcel) == enums.ParcelStatus.RELEASED
    # Mengirim ulang bidang yang sama (formulir) tetap boleh.
    response = satgas.patch(url, {"parcel": parcel.id, "note": "ok"}, format="json")
    assert response.status_code == 200, response.content


@pytest.mark.django_db
def test_rights_release_requires_all_compensation_settled(client_in, parcel, party):
    second = EntitledParty.objects.create(parcel=parcel, name="Siti")
    paid = _validated(parcel, party)
    CompensationPayment.objects.create(
        compensation=paid, paid_on=D(2026, 1, 6), amount=Decimal("1000")
    )
    _validated(parcel, second, amount="500")
    satgas = client_in(UserGroup.SATGAS_PENGADAAN)
    payload = {"parcel": parcel.id, "released_on": "2026-01-07"}
    response = satgas.post(f"{API}/rights_release/", payload, format="json")
    assert response.status_code == 400

    Consignment.objects.create(
        parcel=parcel,
        party=second,
        status=enums.ConsignmentStatus.DEPOSITED,
        amount=Decimal("500"),
    )
    response = satgas.post(f"{API}/rights_release/", payload, format="json")
    assert response.status_code == 201, response.content


# 6. Rekening bank pihak setelah validasi


@pytest.mark.django_db
def test_bank_change_returns_validated_compensation_to_determined(
    client_in, parcel, party
):
    compensation = _validated(parcel, party)
    satgas = client_in(UserGroup.SATGAS_PENGADAAN)
    url = f"{API}/party/{party.id}/"

    # Nilai tersamar dari UI = tidak berubah: validasi tetap.
    masked = satgas.get(url).json()["bank_account_number"]
    response = satgas.patch(
        url, {"bank_account_number": masked, "phone": "0812"}, format="json"
    )
    assert response.status_code == 200, response.content
    assert "notice" not in response.json()
    compensation.refresh_from_db()
    assert compensation.status == enums.CompensationStatus.VALIDATED

    response = satgas.patch(url, {"bank_account_number": "999999999"}, format="json")
    assert response.status_code == 200, response.content
    assert response.json()["notice"]
    compensation.refresh_from_db()
    assert compensation.status == enums.CompensationStatus.DETERMINED
    assert compensation.validated_on is None


# 7. Penilaian final


@pytest.mark.django_db
def test_final_valuation_is_read_only(client_in, project, parcel):
    appraiser = client_in(UserGroup.PENILAI, projects=[project])
    draft = Valuation.objects.create(parcel=parcel, value_land=Decimal("100"))
    url = f"{API}/valuation/{draft.id}/"
    assert appraiser.patch(url, {"value_land": "150"}, format="json").status_code == 200
    assert appraiser.patch(url, {"status": "final"}, format="json").status_code == 200

    response = appraiser.patch(url, {"value_land": "999"}, format="json")
    assert response.status_code == 400
    assert appraiser.patch(url, {"status": "draft"}, format="json").status_code == 400
    response = appraiser.patch(
        url, {"status": "revised", "note": "diganti laporan baru"}, format="json"
    )
    assert response.status_code == 200, response.content
    assert appraiser.patch(url, {"status": "final"}, format="json").status_code == 400
    draft.refresh_from_db()
    assert draft.value_land == Decimal("150")


# 8. Pencarian NIK


@pytest.mark.django_db
def test_nik_filter_requires_personal_data_permission(client_in, parcel, party):
    EntitledParty.objects.create(parcel=parcel, name="Siti", nik="2171010101900002")
    params = {"nik": "2171010101900001"}
    reader = client_in(UserGroup.SELAILIJA)
    assert len(_ids(reader.get(f"{API}/party/", params))) == 2
    satgas = client_in(UserGroup.SATGAS_PENGADAAN)
    assert _ids(satgas.get(f"{API}/party/", params)) == {party.id}


# 9. Tonggak


@pytest.mark.django_db
def test_task_force_milestone_updates_are_limited(client_in, project):
    inventory = AcquisitionMilestone.objects.get(project=project, code="inventory")
    penlok = AcquisitionMilestone.objects.get(project=project, code="penlok")
    satgas = client_in(UserGroup.SATGAS_PENGADAAN)

    url = f"{API}/milestone/{inventory.id}/"
    response = satgas.patch(
        url, {"status": "done", "actual_date": "2026-01-05"}, format="json"
    )
    assert response.status_code == 200, response.content
    assert (
        satgas.patch(url, {"planned_date": "2026-02-01"}, format="json").status_code
        == 400
    )
    response = satgas.patch(
        f"{API}/milestone/{penlok.id}/", {"status": "done"}, format="json"
    )
    assert response.status_code == 403

    pelaksana = client_in(UserGroup.PELAKSANA_PENGADAAN)
    url = f"{API}/milestone/{penlok.id}/"
    other = AcquisitionProject.objects.create(name="B", requiring_agency="X")
    for field, value in (
        ("project", other.id),
        ("stage", enums.ProjectStage.HANDOVER),
        ("code", "lain"),
    ):
        response = pelaksana.patch(url, {field: value}, format="json")
        assert response.status_code == 400, field
        assert field in response.json()
    response = pelaksana.patch(url, {"planned_date": "2026-03-01"}, format="json")
    assert response.status_code == 200
    penlok.refresh_from_db()
    assert penlok.project_id == project.id
    assert penlok.code == "penlok"


# 10. Dokumen: konsistensi relasi dan jenis dokumen instansi


@pytest.mark.django_db
def test_document_relations_and_agency_document_types(
    client_in, project, parcel, party, other_parcel
):
    def _post(client, **data):
        payload = {
            "project": project.id,
            "document_type": enums.DocumentType.OTHER,
            "title": "Dokumen",
            "file": SimpleUploadedFile("a.pdf", b"%PDF-1.4"),
        }
        payload.update(data)
        return client.post(f"{API}/document/", payload, format="multipart")

    pelaksana = client_in(UserGroup.PELAKSANA_PENGADAAN)
    response = _post(pelaksana, parcel=other_parcel.id)
    assert response.status_code == 400 and "parcel" in response.json()
    second = AcquisitionParcel.objects.create(project=project, parcel_number="002")
    response = _post(pelaksana, parcel=second.id, party=party.id)
    assert response.status_code == 400 and "party" in response.json()
    assert _post(pelaksana, parcel=parcel.id, party=party.id).status_code == 201

    agency = client_in(UserGroup.INSTANSI_PEMOHON, projects=[project])
    response = _post(agency, document_type=enums.DocumentType.COURT_DECISION)
    assert response.status_code == 400 and "document_type" in response.json()
    response = _post(agency, party=party.id)
    assert response.status_code == 400
    response = _post(agency, document_type=enums.DocumentType.DPPT)
    assert response.status_code == 201, response.content


# 11. Konsistensi relasi ganti kerugian, konsinyasi dan pelepasan hak


@pytest.mark.django_db
def test_related_records_must_belong_to_same_parcel(
    client_in, project, parcel, party, other_parcel, other_project
):
    other_party = EntitledParty.objects.create(parcel=other_parcel, name="Lain")
    valuation = Valuation.objects.create(parcel=other_parcel)
    deliberation = Deliberation.objects.create(
        project=other_project, held_on=D(2026, 1, 5)
    )
    result = DeliberationResult.objects.create(
        deliberation=deliberation, parcel=other_parcel
    )
    decision = Objection.objects.create(
        project=other_project, objection_type=enums.ObjectionType.COMPENSATION
    )
    pelaksana = client_in(UserGroup.PELAKSANA_PENGADAAN)
    base = {"parcel": parcel.id, "party": party.id, "amount": "1000"}
    for field, value in (
        ("valuation", valuation.id),
        ("deliberation_result", result.id),
        ("court_decision", decision.id),
    ):
        response = pelaksana.post(
            f"{API}/compensation/", {**base, field: value}, format="json"
        )
        assert response.status_code == 400, field
        assert field in response.json()

    response = pelaksana.post(
        f"{API}/consignment/",
        {"parcel": parcel.id, "party": other_party.id, "reason": "refused"},
        format="json",
    )
    assert response.status_code == 400 and "party" in response.json()

    paid = _validated(parcel, party)
    CompensationPayment.objects.create(
        compensation=paid, paid_on=D(2026, 1, 6), amount=Decimal("1000")
    )
    response = pelaksana.post(
        f"{API}/rights_release/",
        {"parcel": parcel.id, "party": other_party.id, "released_on": "2026-01-07"},
        format="json",
    )
    assert response.status_code == 400 and "party" in response.json()
    assert not RightsRelease.objects.exists()


# 13. Panel admin


@pytest.mark.django_db
def test_admin_hides_personal_data_and_compensation_status(django_user_model):
    staff = django_user_model.objects.create_user(
        username="staf", password="RahasiaKuat123!", is_staff=True
    )
    request = RequestFactory().get("/admin/")
    request.user = staff

    party_inline = PartyInline(AcquisitionParcel, admin_site)
    household_admin = admin_site._registry[AffectedHousehold]
    assert {"nik", "bank_account_number"} <= set(party_inline.get_exclude(request))
    assert {"nik", "family_card_number"} <= set(household_admin.get_exclude(request))

    staff.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="pengadaan",
            codename="view_sensitive_personal_data",
        )
    )
    staff = django_user_model.objects.get(pk=staff.pk)
    request.user = staff
    assert "nik" not in party_inline.get_exclude(request)
    assert "nik" not in household_admin.get_exclude(request)

    compensation_admin = admin_site._registry[Compensation]
    assert {"status", "validated_by", "validated_on"} <= set(
        compensation_admin.get_readonly_fields(request)
    )


def test_admin_follows_document_and_project_scoping(user_in, project, parcel, party):
    def _doc(document_type, **kwargs):
        return AcquisitionDocument.objects.create(
            project=project,
            document_type=document_type,
            title=document_type,
            file=SimpleUploadedFile(f"{document_type}.pdf", b"%PDF-1.4 rahasia"),
            **kwargs,
        )

    public = _doc(enums.DocumentType.LOCATION_DECREE)
    _doc(enums.DocumentType.ID_CARD)
    _doc(enums.DocumentType.OTHER, parcel=parcel, party=party)
    document_admin = admin_site._registry[AcquisitionDocument]
    request = RequestFactory().get("/admin/")

    request.user = user_in(UserGroup.LASKUTTAJA)
    assert list(document_admin.get_queryset(request)) == [public]
    request.user = user_in(UserGroup.PAAKAYTTAJA)
    assert document_admin.get_queryset(request).count() == 3

    # Peran eksternal hanya melihat proyek yang ditugaskan, juga di admin.
    request.user = user_in(UserGroup.PENILAI)
    project_admin = admin_site._registry[AcquisitionProject]
    parcel_admin = admin_site._registry[AcquisitionParcel]
    assert not project_admin.get_queryset(request).exists()
    assert not parcel_admin.get_queryset(request).exists()
    request.user = user_in(UserGroup.PENILAI, projects=[project])
    assert list(project_admin.get_queryset(request)) == [project]
    assert list(parcel_admin.get_queryset(request)) == [parcel]
