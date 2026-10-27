from django.db import migrations

ADMINISTRATOR_GROUP_ID = 7


def grant_staff_to_administrators(apps, schema_editor):
    """Anggota grup Administrator kini otomatis berstatus staf (lihat
    alokasi.signals). Samakan akun Administrator yang sudah ada agar tautan menu
    ke panel admin, pusat komando dan aplikasi lapangan tidak meminta login."""
    User = apps.get_model("users", "User")
    User.objects.filter(groups__pk=ADMINISTRATOR_GROUP_ID, is_staff=False).update(
        is_staff=True
    )


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_default_service_unit"),
    ]

    operations = [
        migrations.RunPython(grant_staff_to_administrators, migrations.RunPython.noop),
    ]
