"""Pulihkan identifier bagian formulir pencarian area.

``Section.save()`` menurunkan identifier dari judul. Setelah judul formulir
pencarian area diterjemahkan, formulir yang terbentuk otomatis mendapat
identifier seperti ``data-pemohon``, padahal backend dan SPA mencari
``hakijan-tiedot`` dkk. Akibatnya halaman pencarian area gagal menampilkan data
pemohon dan cek informasi pemohon tidak pernah dibuat.

Migrasi ini memperbaiki formulir yang sudah ada (bagian, bagian jawaban, jalur
isian) dan membuat cek informasi yang belum ada. Formulir yang sudah benar
tidak tersentuh.
"""

import re

from django.db import migrations

# (judul bagian, judul induk) -> identifier baku.
EXPECTED = {
    ("Data pemohon", None): "hakijan-tiedot",
    ("Data badan usaha", "Data pemohon"): "yrityksen-tiedot",
    ("Narahubung", "Data badan usaha"): "yhteyshenkilo-company",
    ("Data penagihan", "Narahubung"): "laskutustiedot",
    ("Data penagihan lain", "Data penagihan"): "muut-laskutustiedot",
    ("Data perorangan", "Data pemohon"): "henkilon-tiedot",
    ("Narahubung", "Data perorangan"): "yhteyshenkilo-1",
    ("Penerima tagihan", "Data perorangan"): "laskunsaaja",
    ("Saya setuju", None): "päätöksen-toimitus",
}
INFORMATION_CHECKS = (
    "trade_register",
    "creditworthiness",
    "pension_contributions",
    "vat_register",
    "advance_payment",
    "tax_debt",
    "employer_register",
)
SEGMENT = re.compile(r"^(?P<name>[^\[]+)(?P<index>(\[\d+])*)$")


def _rename_path(path, renames):
    parts = []
    for part in path.split("."):
        match = SEGMENT.match(part)
        if match and match.group("name") in renames:
            part = renames[match.group("name")] + match.group("index")
        parts.append(part)
    return ".".join(parts)


def forwards(apps, schema_editor):  # noqa: C901
    Form = apps.get_model("forms", "Form")
    Section = apps.get_model("forms", "Section")
    EntrySection = apps.get_model("forms", "EntrySection")
    Entry = apps.get_model("forms", "Entry")
    InformationCheck = apps.get_model("plotsearch", "InformationCheck")

    for form in Form.objects.filter(is_area_form=True):
        sections = list(Section.objects.filter(form=form).select_related("parent"))
        renames = {}
        for section in sections:
            parent_title = section.parent.title if section.parent_id else None
            expected = EXPECTED.get((section.title, parent_title))
            if expected and section.identifier != expected:
                renames[section.identifier] = expected
        if not renames:
            continue
        taken = {section.identifier for section in sections} - set(renames)
        if taken & set(renames.values()):
            # Identifier tujuan sudah dipakai bagian lain: biarkan apa adanya.
            continue
        for section in sections:
            if section.identifier in renames:
                Section.objects.filter(pk=section.pk).update(
                    identifier=renames[section.identifier]
                )
        entry_sections = EntrySection.objects.filter(answer__form=form)
        for entry_section in entry_sections:
            identifier = _rename_path(entry_section.identifier, renames)
            if identifier != entry_section.identifier:
                EntrySection.objects.filter(pk=entry_section.pk).update(
                    identifier=identifier
                )
        for entry in Entry.objects.filter(entry_section__answer__form=form):
            path = _rename_path(entry.path, renames)
            if path != entry.path:
                Entry.objects.filter(pk=entry.pk).update(path=path)
        for entry_section in EntrySection.objects.filter(
            answer__form=form, identifier__startswith="hakijan-tiedot"
        ):
            if InformationCheck.objects.filter(entry_section=entry_section).exists():
                continue
            InformationCheck.objects.bulk_create(
                InformationCheck(name=name, entry_section=entry_section)
                for name in INFORMATION_CHECKS
            )


class Migration(migrations.Migration):

    dependencies = [
        ("forms", "0004_verbose_names"),
        ("plotsearch", "0003_verbose_names"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
