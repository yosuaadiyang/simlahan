"""Jalur baca pengadaan di luar API (alat admin aset lahan, tenggat, dokumen)
mengikuti pembatasan proyek & izin per model yang sama dengan API."""

import datetime
import io
import itertools
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import RequestFactory
from rest_framework.test import APIClient

from pengadaan import enums
from pengadaan.models import (
    AcquisitionDocument,
    AcquisitionMilestone,
    AcquisitionParcel,
    AcquisitionProject,
    Compensation,
    CompensationPayment,
    Objection,
    Valuation,
)
from utils.group_permissions import UserGroup

API = "/v1/pengadaan"
D = datetime.date
_counter = itertools.count()

pytestmark = pytest.mark.django_db


@pytest.fixture
def user_in(db, django_user_model):
    for group in UserGroup:
        Group.objects.get_or_create(id=group.value, defaults={"name": group.name})
    call_command("set_group_model_permissions", stdout=io.StringIO())

    def _make(*group_ids, projects=()):
        user = django_user_model.objects.create_user(
            username=f"lingkup{next(_counter)}", password="RahasiaKuat123!"
        )
        for gid in group_ids:
            user.groups.add(Group.objects.get(id=gid))
        for project in projects:
            project.assigned_users.add(user)
        return user

    return _make


@pytest.fixture
def other_project(project):
    return AcquisitionProject.objects.create(
        name="Proyek Rahasia Lain",
        requiring_agency="Dinas Lain",
        municipality=project.municipality,
    )


@pytest.fixture
def other_parcel(other_project):
    parcel = AcquisitionParcel.objects.create(
        project=other_project, parcel_number="RAHASIA-9", is_disputed=True
    )
    AcquisitionParcel.objects.filter(pk=parcel.pk).update(
        geometry="SRID=4326;MULTIPOLYGON(((104 1,104.001 1,104.001 1.001,104 1)))"
    )
    return parcel


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _document(project, document_type, title):
    return AcquisitionDocument.objects.create(
        project=project,
        document_type=document_type,
        title=title,
        file=SimpleUploadedFile(f"{document_type}.pdf", b"%PDF-1.4"),
    )


# NV-15: alat admin aset lahan


def test_asetlahan_tools_apply_pengadaan_project_scope(
    user_in, project, parcel, other_project, other_parcel
):
    from asetlahan import admin_views, finance, reports

    valuer = user_in(UserGroup.PENILAI, projects=[project])
    compensation = Compensation.objects.create(
        parcel=other_parcel,
        amount=Decimal("1000"),
        status=enums.CompensationStatus.VALIDATED,
    )
    CompensationPayment.objects.create(
        compensation=compensation,
        paid_on=D(2026, 1, 6),
        amount=Decimal("1000"),
        recipient_name="Penerima Rahasia",
    )
    AcquisitionMilestone.objects.create(
        project=other_project,
        stage=enums.ProjectStage.PREPARATION,
        code="rahasia",
        title="Tonggak rahasia",
        planned_date=D(2026, 1, 10),
    )
    _document(other_project, enums.DocumentType.PHOTO, "RAHASIA foto")
    request = RequestFactory().get("/")
    request.user = valuer

    found = admin_views.search_all(valuer, "RAHASIA")
    assert found == [], found
    assert list(admin_views._pengadaan_features(request)) == []
    assert admin_views._gantt_milestones(request, D(2026, 1, 1), D(2026, 1, 31)) == []
    ledger = finance.ledger(valuer)
    assert not [e for e in ledger["entries"] if e.source == "Pengadaan tanah"]
    dataset = reports.DATASETS["pengadaan"]
    assert set(dataset.queryset(valuer)) == {parcel}
    counts = {row["label"]: row["value"] for row in admin_views._other_modules(valuer)}
    assert counts[next(k for k in counts if "bersengketa" in str(k))] == 0


def test_asetlahan_search_hides_withheld_document_types(user_in, project):
    agency = user_in(UserGroup.INSTANSI_PEMOHON, projects=[project])
    _document(project, enums.DocumentType.VALUATION_REPORT, "Laporan nilai XYZ")
    _document(project, enums.DocumentType.DPPT, "DPPT XYZ")
    from asetlahan import admin_views

    found = admin_views.search_all(agency, "XYZ")
    titles = [item["text"] for group in found for item in group["items"]]
    assert titles == ["DPPT XYZ"], titles


# NV-30: dokumen pengadaan mengikuti izin lihat model sumbernya


def test_requesting_agency_cannot_read_valuation_or_court_documents(user_in, project):
    agency = _client(user_in(UserGroup.INSTANSI_PEMOHON, projects=[project]))
    satgas = _client(user_in(UserGroup.SATGAS_PENGADAAN))
    withheld = {
        doc_type: _document(project, doc_type, f"Dokumen {doc_type}")
        for doc_type in (
            enums.DocumentType.NOMINATIVE_LIST,
            enums.DocumentType.VALUATION_REPORT,
            enums.DocumentType.DELIBERATION_MINUTES,
            enums.DocumentType.COURT_DECISION,
            enums.DocumentType.CONSIGNMENT_DECREE,
            enums.DocumentType.RELEASE_MINUTES,
        )
    }
    dppt = _document(project, enums.DocumentType.DPPT, "DPPT")

    listed = agency.get(f"{API}/document/").json()
    rows = listed["results"] if isinstance(listed, dict) else listed
    assert {row["id"] for row in rows} == {dppt.id}
    for document in withheld.values():
        assert agency.get(f"{API}/document/{document.id}/").status_code == 404
        response = agency.get(f"{API}/document/{document.id}/download/")
        assert response.status_code == 404
    assert agency.get(f"{API}/document/{dppt.id}/").status_code == 200

    # Peran yang boleh melihat data sumbernya tetap melihat dokumennya.
    listed = satgas.get(f"{API}/document/").json()
    rows = listed["results"] if isinstance(listed, dict) else listed
    seen = {row["id"] for row in rows}
    assert withheld[enums.DocumentType.RELEASE_MINUTES].id in seen
    assert withheld[enums.DocumentType.DELIBERATION_MINUTES].id in seen


# NV-29: nomor rujukan tenggat mengikuti izin lihat model sumbernya


def test_deadline_references_need_source_model_permission(user_in, project, parcel):
    Valuation.objects.create(
        parcel=parcel,
        status=enums.ValuationStatus.FINAL,
        submitted_on=D.today(),
        report_number="RPT-RAHASIA",
    )
    Objection.objects.create(
        project=project,
        parcel=parcel,
        objection_type=enums.ObjectionType.COMPENSATION,
        status=enums.ObjectionStatus.IN_PROCESS,
        filed_on=D.today(),
        received_on=D.today(),
        case_number="CASE-RAHASIA",
    )
    agency = _client(user_in(UserGroup.INSTANSI_PEMOHON, projects=[project]))
    pelaksana = _client(user_in(UserGroup.PELAKSANA_PENGADAAN))

    def references(client):
        responses = [
            client.get(f"{API}/deadlines/").json(),
            client.get(f"{API}/dashboard/").json()["upcoming_deadlines"],
            client.get(f"{API}/project/{project.id}/summary/").json()["deadlines"],
        ]
        return [{(d["kind"], d["reference"]) for d in items} for items in responses]

    for seen in references(pelaksana):
        assert ("deliberation", "RPT-RAHASIA") in seen
        assert ("court_decision", "CASE-RAHASIA") in seen
    for seen in references(agency):
        # Tenggatnya tetap tampil untuk pemantauan, tanpa nomor rujukan.
        assert ("deliberation", "") in seen
        assert ("court_decision", "") in seen
        assert not {ref for _, ref in seen} & {"RPT-RAHASIA", "CASE-RAHASIA"}
