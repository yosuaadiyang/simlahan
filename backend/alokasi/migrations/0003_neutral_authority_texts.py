"""Ganti teks bawaan lama yang menyebut instansi tertentu dengan teks netral.

Hanya baris yang masih memuat teks bawaan lama yang diubah: kolom otoritas
yang menyebut "Batam" (bukan kolom kota) dan halaman regulasi bawaan.
Isian lain yang sudah diubah petugas tidak tersentuh.
"""

import re

from django.db import migrations

NEUTRAL = {
    "authority_name": "Instansi Pengelola Lahan",
    "authority_short_name": "Pengelola Lahan",
    "signatory_title": "Kepala Instansi Pengelola Lahan",
    "payment_instructions": "Pembayaran melalui rekening resmi instansi sesuai nomor tagihan.",
}

OLD_REGULATION = re.compile(r"Peraturan Badan \w+ Batam tentang")
NEW_REGULATION = "Peraturan instansi pengelola lahan tentang"


def forwards(apps, schema_editor):
    alias = schema_editor.connection.alias
    Settings = apps.get_model("alokasi", "AllocationSettings")
    for field, value in NEUTRAL.items():
        Settings.objects.using(alias).filter(**{f"{field}__icontains": "batam"}).update(
            **{field: value}
        )

    InfoPage = apps.get_model("alokasi", "InfoPage")
    for page in InfoPage.objects.using(alias).filter(body__icontains="batam"):
        body = OLD_REGULATION.sub(NEW_REGULATION, page.body)
        if body != page.body:
            page.body = body
            page.save(update_fields=["body"])

    # Data master pengambil keputusan (fixture lama, pk 8).
    DecisionMaker = apps.get_model("leasing", "DecisionMaker")
    DecisionMaker.objects.using(alias).filter(
        pk=8, name__startswith="Kepala Badan P"
    ).exclude(name="Kepala Badan Pengelola Kawasan").update(
        name="Kepala Badan Pengelola Kawasan"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("alokasi", "0002_seed_defaults"),
        ("leasing", "0003_permissions_view"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
