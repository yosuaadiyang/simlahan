from pathlib import Path

from django.db import migrations


def _sql(name):
    return (Path(__file__).resolve().parent / name).read_text(encoding="utf-8")


class Migration(migrations.Migration):

    dependencies = [("leasing", "0002_initial")]

    operations = [
        migrations.RunSQL(
            sql=_sql("0003_permissions_view.sql"),
            reverse_sql="DROP VIEW IF EXISTS public.view_permissions;",
        ),
    ]
