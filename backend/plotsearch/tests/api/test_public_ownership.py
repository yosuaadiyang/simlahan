"""API publik /v1/pub/: pengirim hanya boleh memakai datanya sendiri dan tidak
boleh mengisi kolom yang menjadi wewenang petugas."""

import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse

from plotsearch.enums import AreaSearchState
from plotsearch.models import AreaSearch, AreaSearchAttachment

pytestmark = pytest.mark.django_db


def _file():
    return SimpleUploadedFile(content=b"Lorem Impsum", name="test.txt")


def _create_payload(area_search_test_data, **extra):
    data = {
        "description_area": "Area uji",
        "description_intended_use": "Penggunaan uji",
        "intended_use": area_search_test_data.intended_use.pk,
        "geometry": area_search_test_data.geometry.geojson,
    }
    data.update(extra)
    return json.dumps(data, cls=DjangoJSONEncoder)


def test_public_area_search_rejects_foreign_attachment(
    admin_client, user_factory, area_search_test_data, area_search_attachment_factory
):
    other = user_factory(username="pemohon-lain")
    foreign = area_search_attachment_factory(user=other, attachment=_file(), name="a")
    response = admin_client.post(
        reverse("v1:pub_area_search-list"),
        _create_payload(area_search_test_data, area_search_attachments=[foreign.id]),
        content_type="application/json",
    )
    assert response.status_code == 400
    foreign.refresh_from_db()
    assert foreign.area_search_id is None


def test_public_area_search_rejects_attachment_of_another_area_search(
    admin_client,
    admin_user,
    area_search_factory,
    area_search_test_data,
    area_search_attachment_factory,
):
    mine = area_search_factory(user=admin_user, description_area="Area milik sendiri")
    linked = area_search_attachment_factory(
        user=admin_user, area_search=mine, attachment=_file(), name="a"
    )
    response = admin_client.post(
        reverse("v1:pub_area_search-list"),
        _create_payload(area_search_test_data, area_search_attachments=[linked.id]),
        content_type="application/json",
    )
    assert response.status_code == 400
    linked.refresh_from_db()
    assert linked.area_search_id == mine.id


def test_public_area_search_ignores_officer_fields(
    admin_client, user_factory, service_unit_factory, area_search_test_data
):
    officer = user_factory(username="petugas-lain")
    unit = service_unit_factory(name="Unit uji")
    response = admin_client.post(
        reverse("v1:pub_area_search-list"),
        _create_payload(
            area_search_test_data,
            preparer=officer.pk,
            service_unit=unit.pk,
            identifier="MH-PALSU",
            state=AreaSearchState.SETTLED,
        ),
        content_type="application/json",
    )
    assert response.status_code == 201, response.content
    area_search = AreaSearch.objects.get(pk=response.json()["id"])
    assert area_search.preparer_id is None
    assert area_search.service_unit_id is None
    assert area_search.identifier != "MH-PALSU"
    assert area_search.state != AreaSearchState.SETTLED
    assert area_search.settled_date is None


def test_public_area_search_update_ignores_officer_fields(
    admin_client, admin_user, area_search_factory, user_factory
):
    mine = area_search_factory(user=admin_user, description_area="Area milik sendiri")
    officer = user_factory(username="petugas-lain")
    response = admin_client.patch(
        reverse("v1:pub_area_search-detail", kwargs={"pk": mine.pk}),
        json.dumps(
            {
                "description_area": "Diperbarui",
                "preparer": officer.pk,
                "state": AreaSearchState.SETTLED,
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
    mine.refresh_from_db()
    assert mine.description_area == "Diperbarui"
    assert mine.preparer_id is None
    assert mine.state != AreaSearchState.SETTLED
    assert mine.settled_date is None


def test_public_attachment_upload_rejects_foreign_area_search(
    admin_client, user_factory, area_search_factory
):
    other = user_factory(username="pemohon-lain")
    foreign = area_search_factory(user=other, description_area="Area orang lain")
    response = admin_client.post(
        reverse("v1:pub_area_search_attachment-list"),
        data={"area_search": foreign.id, "attachment": _file(), "name": "x"},
    )
    assert response.status_code == 400
    assert not AreaSearchAttachment.objects.filter(area_search=foreign).exists()


def test_public_attachment_upload_rejects_submitted_area_search(
    admin_client, admin_user, area_search_factory, answer_factory, form_factory
):
    submitted = area_search_factory(
        user=admin_user,
        description_area="Sudah diajukan",
        answer=answer_factory(form=form_factory(), user=admin_user),
    )
    response = admin_client.post(
        reverse("v1:pub_area_search_attachment-list"),
        data={"area_search": submitted.id, "attachment": _file(), "name": "x"},
    )
    assert response.status_code == 400
