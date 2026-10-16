from pathlib import Path

from django.db import migrations


def _sql(name):
    return (Path(__file__).resolve().parent / name).read_text(encoding="utf-8")


class Migration(migrations.Migration):

    dependencies = [("batchrun", "0001_initial")]

    operations = [
        migrations.RunSQL(
            sql=_sql("0002_log_compact_function.sql"),
            reverse_sql=_sql("0002_drop_log_compact_function.sql"),
        ),
    ]
