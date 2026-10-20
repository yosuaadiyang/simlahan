"""Pemeriksaan statis atas semua model yang terdaftar di panel admin."""

from django.contrib import admin
from django.core.exceptions import FieldDoesNotExist
from django.utils import translation
from enumfields.fields import EnumFieldMixin

# Aplikasi yang teks sumbernya sudah berbahasa Indonesia (msgid = teks tampil).
INDONESIAN_SOURCE_APPS = {"alokasi", "asetlahan", "operasi", "pengadaan"}
# Kata yang sama dalam bahasa Inggris dan Indonesia.
SAME_IN_BOTH = {"Area", "log", "Token"}


def test_enum_list_filters_use_enumfield_filter():
    # Filter bawaan Django untuk EnumField membuat tautan ?field=Enum.MEMBER yang
    # ditolak admin (302 ke ?e=1); EnumField harus memakai EnumFieldListFilter.
    offenders = []
    for model, model_admin in admin.site._registry.items():
        for item in model_admin.list_filter:
            if not isinstance(item, str) or "__" in item:
                continue
            try:
                field = model._meta.get_field(item)
            except FieldDoesNotExist:
                continue
            if isinstance(field, EnumFieldMixin):
                offenders.append(f"{model._meta.label}.{item}")
    assert offenders == []


def test_admin_app_and_model_names_are_translated():
    untranslated = set()
    for model in admin.site._registry:
        options = model._meta
        if options.app_label in INDONESIAN_SOURCE_APPS:
            continue
        for text in (
            options.app_config.verbose_name,
            options.verbose_name,
            options.verbose_name_plural,
        ):
            with translation.override("en"):
                english = str(text)
            with translation.override("id"):
                indonesian = str(text)
            if english == indonesian and english not in SAME_IN_BOTH:
                untranslated.add(f"{options.label}: {english}")
    assert sorted(untranslated) == []


def _models_shown_in_admin():
    """(model, model induk bila tampil sebagai inline); FK ke induk disembunyikan."""
    shown = [(model, None) for model in admin.site._registry]
    pending = [(ma.inlines, model) for model, ma in admin.site._registry.items()]
    while pending:
        inlines, parent = pending.pop()
        for inline in inlines:
            shown.append((inline.model, parent))
            pending.append((getattr(inline, "inlines", []), inline.model))
    return shown


def test_admin_model_fields_have_explicit_labels():
    # Tanpa verbose_name, label diturunkan dari nama kolom (bahasa Inggris) dan tidak
    # bisa diterjemahkan.
    project_apps = INDONESIAN_SOURCE_APPS | {
        "batchrun",
        "file_operations",
        "forms",
        "leasing",
        "plotsearch",
        "users",
    }
    missing = set()
    for model, parent in _models_shown_in_admin():
        options = model._meta
        if options.app_label not in project_apps:
            continue
        if "verbose_name" not in options.original_attrs:
            missing.add(f"{options.label} (nama model)")
        for field in [*options.concrete_fields, *options.many_to_many]:
            if field.auto_created or not field.editable:
                continue
            if parent is not None and field.related_model is parent:
                continue
            if field.name == "passcode_hash":
                # Hanya diisi lewat formulir khusus; tidak pernah tampil di admin.
                continue
            if "verbose_name" not in field.deconstruct()[3]:
                missing.add(f"{options.label}.{field.name}")
    assert sorted(missing) == []


def test_contact_country_and_language_choices_are_translated():
    from django_countries import countries

    from leasing.models import Contact

    with translation.override("id"):
        languages = dict(Contact._meta.get_field("language").choices)
        assert str(languages["de"]) == "Jerman"
        assert countries.name("DE") == "Jerman"
        assert str(Contact._meta.get_field("language").verbose_name) == "Bahasa"
