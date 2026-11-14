from django.db import migrations, models


def close_for_accounts_that_were_active(apps, schema_editor):
    """Akun yang sedang aktif, atau pernah masuk (last_login terisi) tetapi kini
    nonaktif (dinonaktifkan petugas), tidak lagi bisa diaktifkan lewat surel.
    Akun nonaktif yang belum pernah masuk dibiarkan: kemungkinan besar masih
    menunggu aktivasi."""
    Applicant = apps.get_model("alokasi", "Applicant")
    Applicant.objects.filter(
        models.Q(user__is_active=True) | models.Q(user__last_login__isnull=False)
    ).update(email_activation_closed=True)


class Migration(migrations.Migration):

    dependencies = [
        ("alokasi", "0015_alter_application_tracking_pin"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicant",
            name="email_activation_closed",
            field=models.BooleanField(
                default=False,
                editable=False,
                verbose_name="Aktivasi lewat surel ditutup",
            ),
        ),
        migrations.RunPython(
            close_for_accounts_that_were_active, migrations.RunPython.noop
        ),
    ]
