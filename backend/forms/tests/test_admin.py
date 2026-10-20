import pytest
from django.utils import translation


@pytest.mark.django_db
def test_section_admin_parent_is_optional_and_labels_translated(admin_client):
    with translation.override("id"):
        response = admin_client.get("/admin/forms/section/add/")
    assert response.status_code == 200
    form = response.context["adminform"].form
    # Bagian tingkat atas tidak punya induk; kolom ini tidak boleh wajib.
    assert form.fields["parent"].required is False
    assert form.fields["form"].required is True
    with translation.override("id"):
        assert str(form.fields["form"].label) == "Formulir"
        assert str(form.fields["parent"].label) == "Bagian induk"


@pytest.mark.django_db
def test_field_and_choice_admin_labels_translated(admin_client):
    with translation.override("id"):
        field_form = (
            admin_client.get("/admin/forms/field/add/").context["adminform"].form
        )
        choice_form = (
            admin_client.get("/admin/forms/choice/add/").context["adminform"].form
        )
        assert str(field_form.fields["section"].label) == "Bagian formulir"
        assert str(choice_form.fields["field"].label) == "Isian formulir"
