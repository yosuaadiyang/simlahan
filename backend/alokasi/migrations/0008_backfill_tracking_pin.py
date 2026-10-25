"""Isi PIN pelacakan untuk permohonan yang dibuat sebelum fitur lacak ada.

Tanpa ini halaman permohonan lama menampilkan PIN kosong dan permohonan
tersebut tidak dapat dilacak tanpa login.
"""

import secrets

from django.db import migrations


def backfill(apps, schema_editor):
    Application = apps.get_model("alokasi", "Application")
    alias = schema_editor.connection.alias
    rows = Application.objects.using(alias).filter(tracking_pin="").only("pk")
    for application in rows.iterator():
        Application.objects.using(alias).filter(pk=application.pk).update(
            tracking_pin=secrets.token_hex(4).upper()
        )


class Migration(migrations.Migration):
    dependencies = [
        ("alokasi", "0007_seed_layanan"),
    ]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
