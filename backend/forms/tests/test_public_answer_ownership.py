"""POST /v1/pub/answer/: pengirim hanya boleh mengaitkan lampiran unggahannya
sendiri dan pencarian area miliknya sendiri yang belum berjawaban."""

import datetime
import io
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from forms.models import Answer
from forms.models.form import Attachment
from leasing.models.land_area import PlanUnitState, PlanUnitType, PlotDivisionState
from mvj.tests.test_urls import set_plotsearch_flag_reload_urlconf  # noqa: F401
from plotsearch.models import AreaSearch

pytestmark = pytest.mark.django_db


def _field(form):
    return form.sections.get(identifier="application-target").fields.get(
        identifier="reference-attachments"
    )


def _attachment(attachment_factory, user, form):
    return attachment_factory(
        user=user,
        field=_field(form),
        name="lampiran.txt",
        attachment=SimpleUploadedFile(name="lampiran.txt", content=b"isi"),
    )


def _payload(form, target, upload_ids=None, **extra):
    sections = {
        "company-information": [
            {
                "sections": {},
                "fields": {"company-name": {"value": "", "extraValue": ""}},
            },
            {
                "sections": {},
                "fields": {
                    "business-id": {"value": "", "extraValue": ""},
                    "hallintaosuus": {"value": "1/1", "extraValue": ""},
                },
            },
        ],
        "contact-person": {
            "sections": {},
            "fields": {
                "first-name": {"value": "Uji", "extraValue": ""},
                "last-name": {"value": "Pemohon", "extraValue": ""},
            },
        },
    }
    if upload_ids is not None:
        sections["application-target"] = {
            "sections": {},
            "fields": {
                "reference-attachments": {"value": upload_ids, "extraValue": ""}
            },
        }
    payload = {
        "form": form.id,
        "targets": [target.pk],
        "entries": {"sections": sections, "fields": {}},
        "ready": True,
    }
    payload.update(extra)
    return payload


def _post(client, payload):
    return client.post(
        reverse("v1:pub_answer-list"), data=payload, content_type="application/json"
    )


def test_own_attachment_is_bound(
    admin_client, admin_user, plot_search_target, basic_form, attachment_factory
):
    own = _attachment(attachment_factory, admin_user, basic_form)
    response = _post(
        admin_client,
        _payload(basic_form, plot_search_target, [own.id], attachments=[own.id]),
    )
    assert response.status_code == 201, response.content
    own.refresh_from_db()
    assert own.answer_id == response.json()["id"]
    assert own.path


def test_foreign_attachment_rejected(
    admin_client,
    plot_search_target,
    basic_form,
    attachment_factory,
    user_factory,
):
    foreign = _attachment(attachment_factory, user_factory(username="lain"), basic_form)
    response = _post(
        admin_client, _payload(basic_form, plot_search_target, attachments=[foreign.id])
    )
    assert response.status_code == 400
    foreign.refresh_from_db()
    assert foreign.answer_id is None
    assert not Answer.objects.exists()


def test_attachment_already_bound_to_another_answer_rejected(
    admin_client,
    admin_user,
    plot_search_target,
    basic_form,
    attachment_factory,
    answer_factory,
):
    bound = _attachment(attachment_factory, admin_user, basic_form)
    earlier = answer_factory(form=basic_form, user=admin_user)
    Attachment.objects.filter(pk=bound.pk).update(answer=earlier)
    response = _post(
        admin_client, _payload(basic_form, plot_search_target, attachments=[bound.id])
    )
    assert response.status_code == 400
    bound.refresh_from_db()
    assert bound.answer_id == earlier.id


def test_foreign_attachment_in_upload_field_rejected(
    admin_client, plot_search_target, basic_form, attachment_factory, user_factory
):
    foreign = _attachment(attachment_factory, user_factory(username="lain"), basic_form)
    response = _post(
        admin_client, _payload(basic_form, plot_search_target, [foreign.id])
    )
    assert response.status_code == 400
    foreign.refresh_from_db()
    assert foreign.path is None


def test_foreign_area_search_rejected(
    admin_client,
    plot_search_target,
    basic_form,
    area_search_factory,
    user_factory,
):
    foreign = area_search_factory(
        user=user_factory(username="lain"), description_area="Area orang lain"
    )
    response = _post(
        admin_client,
        _payload(basic_form, plot_search_target, area_search=foreign.id),
    )
    assert response.status_code == 400
    assert AreaSearch.objects.get(pk=foreign.pk).answer_id is None


def test_own_area_search_without_answer_is_linked(
    admin_client, admin_user, plot_search_target, basic_form, area_search_factory
):
    mine = area_search_factory(user=admin_user, description_area="Area sendiri")
    response = _post(
        admin_client, _payload(basic_form, plot_search_target, area_search=mine.id)
    )
    assert response.status_code == 201, response.content
    assert AreaSearch.objects.get(pk=mine.pk).answer_id == response.json()["id"]


@override_settings(FLAG_PLOTSEARCH=True)
def test_public_attachment_upload_rejects_foreign_answer(
    set_plotsearch_flag_reload_urlconf,  # noqa: F811
    admin_client,
    basic_form,
    answer_factory,
    user_factory,
):
    foreign_answer = answer_factory(form=basic_form, user=user_factory(username="lain"))
    response = admin_client.post(
        reverse("v1:pub_attachment-list"),
        data={
            "field": _field(basic_form).id,
            "name": "x",
            "answer": foreign_answer.id,
            "attachment": SimpleUploadedFile(name="x.txt", content=b"isi"),
        },
    )
    assert response.status_code == 400
    assert not Attachment.objects.filter(answer=foreign_answer).exists()


def test_answers_xlsx_writes_answer_text_as_text(
    admin_client, plot_search_target, basic_form
):
    plot_search = plot_search_target.plot_search
    plot_search.form = basic_form
    plot_search.save()
    plan_unit = plot_search_target.plan_unit
    plan_unit.plot_division_date_of_approval = datetime.date(2026, 1, 1)
    plan_unit.plot_division_effective_date = datetime.date(2026, 1, 1)
    plan_unit.plot_division_state = PlotDivisionState.objects.create(name="Uji")
    plan_unit.plan_unit_type = PlanUnitType.objects.create(name="Uji")
    plan_unit.plan_unit_state = PlanUnitState.objects.create(name="Uji")
    plan_unit.save()
    payload = _payload(basic_form, plot_search_target)
    payload["entries"]["sections"]["contact-person"]["fields"]["first-name"][
        "value"
    ] = "=1+1"
    assert _post(admin_client, payload).status_code == 201
    response = admin_client.get(
        reverse("v1:plotsearch-get-answers-xlsx", kwargs={"pk": plot_search.pk})
    )
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as book:
        names = [n for n in book.namelist() if n.startswith("xl/worksheets/")]
        sheets = "".join(book.read(n).decode() for n in names)
        strings = book.read("xl/sharedStrings.xml").decode()
    assert "<f>" not in sheets
    assert "=1+1" in strings
