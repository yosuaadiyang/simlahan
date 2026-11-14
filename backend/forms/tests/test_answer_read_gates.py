"""Isi jawaban pemohon hanya terbaca lewat aturan API jawaban: izin lihat
jawaban (atau penyiap plot search) dan berita acara pembukaan untuk subtipe
yang mewajibkannya. Berita acara pembukaan tidak bisa dipindah ke jawaban
lain."""

import datetime
import io
import zipfile

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from forms.models import Answer
from forms.models.form import AnswerOpeningRecord
from forms.tests.test_public_answer_ownership import _payload, _post
from leasing.models.land_area import PlanUnitState, PlanUnitType, PlotDivisionState
from mvj.tests.test_urls import set_plotsearch_flag_reload_urlconf  # noqa: F401

pytestmark = pytest.mark.django_db

SECRET = "IsianRahasiaPemohon"


def _browser(user_factory, client):
    """Peran peramban (Selailija): lihat plot search & area search saja."""
    user = user_factory(username="peramban")
    user.user_permissions.add(
        *Permission.objects.filter(codename__in=("view_plotsearch", "view_areasearch"))
    )
    assert not user.has_perm("forms.view_answer")
    client.force_login(user)
    return user


def _ready_target(plot_search_target, basic_form):
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
    return plot_search


def _xlsx_strings(response):
    with zipfile.ZipFile(io.BytesIO(response.content)) as book:
        try:
            return book.read("xl/sharedStrings.xml").decode()
        except KeyError:
            return ""


def _submit(admin_client, basic_form, plot_search_target):
    payload = _payload(basic_form, plot_search_target)
    payload["entries"]["sections"]["contact-person"]["fields"]["first-name"][
        "value"
    ] = SECRET
    response = _post(admin_client, payload)
    assert response.status_code == 201, response.content
    return Answer.objects.get(pk=response.json()["id"])


# NV-32


def test_plot_search_answers_xlsx_needs_answer_permission(
    admin_client, client, user_factory, plot_search_target, basic_form
):
    plot_search = _ready_target(plot_search_target, basic_form)
    _submit(admin_client, basic_form, plot_search_target)
    url = reverse("v1:plotsearch-get-answers-xlsx", kwargs={"pk": plot_search.pk})

    _browser(user_factory, client)
    assert client.get(url).status_code == 403
    response = admin_client.get(url)
    assert response.status_code == 200
    assert SECRET in _xlsx_strings(response)


def test_sealed_answers_stay_out_of_xlsx_until_opened(
    admin_client, plot_search_target, basic_form
):
    plot_search = _ready_target(plot_search_target, basic_form)
    answer = _submit(admin_client, basic_form, plot_search_target)
    subtype = plot_search.subtype
    subtype.require_opening_record = True
    subtype.save()
    url = reverse("v1:plotsearch-get-answers-xlsx", kwargs={"pk": plot_search.pk})

    response = admin_client.get(url)
    assert response.status_code == 200
    assert SECRET not in _xlsx_strings(response)

    AnswerOpeningRecord.objects.create(answer=answer)
    assert SECRET in _xlsx_strings(admin_client.get(url))


def test_area_search_answer_hidden_without_answer_permission(
    admin_client, client, user_factory, area_search_test_data
):
    detail = reverse("v1:areasearch-detail", kwargs={"pk": area_search_test_data.pk})
    export = reverse("v1:areasearch-get-answers-xlsx")

    _browser(user_factory, client)
    response = client.get(detail)
    assert response.status_code == 200
    assert "answer" not in response.json()
    assert client.get(export).status_code == 403

    response = admin_client.get(detail)
    assert response.status_code == 200
    assert response.json()["answer"]["id"] == area_search_test_data.answer_id


# NV-17


def test_opening_record_cannot_be_moved_to_another_answer(
    client,
    user_factory,
    answer_factory,
    plot_search_target,
    plot_search_factory,
    plan_unit_factory,
    plot_search_target_factory_with_sub_factories,
    basic_template_form,
):
    preparer = plot_search_target.plot_search.preparers.first()
    own_answer = answer_factory(form=basic_template_form, user=user_factory())
    plot_search_target.answers.add(own_answer)
    other_target = plot_search_target_factory_with_sub_factories(
        plot_search=plot_search_factory(),
        plan_unit=plan_unit_factory(
            identifier="PU2",
            area=1000,
            lease_area=plot_search_target.plan_unit.lease_area,
            is_master=True,
        ),
    )
    assert not other_target.plot_search.preparers.filter(pk=preparer.pk).exists()
    foreign_answer = answer_factory(form=basic_template_form, user=user_factory())
    other_target.answers.add(foreign_answer)
    record = AnswerOpeningRecord.objects.create(answer=own_answer)

    client.force_login(preparer)
    response = client.patch(
        reverse("v1:answer_opening_record-detail", kwargs={"pk": record.pk}),
        data={"answer": foreign_answer.pk},
        content_type="application/json",
    )
    assert response.status_code == 400, response.content
    record.refresh_from_db()
    assert record.answer_id == own_answer.pk
    assert not AnswerOpeningRecord.objects.filter(answer=foreign_answer).exists()

    # Mengubah catatan pada berita acara sendiri tetap bisa.
    response = client.patch(
        reverse("v1:answer_opening_record-detail", kwargs={"pk": record.pk}),
        data={"note": "Dibuka di rapat"},
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
