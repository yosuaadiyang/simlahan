from pathlib import Path

from django.db import migrations


def _sql(name):
    return (Path(__file__).resolve().parent / name).read_text(encoding="utf-8")


class Migration(migrations.Migration):

    dependencies = [
        ("forms", "0002_initial"),
        ("plotsearch", "0002_initial"),
        ("leasing", "0002_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=_sql("0003_create_form_view.sql"),
            reverse_sql=_sql("0003_reverse_create_form_view.sql"),
        ),
    ]
