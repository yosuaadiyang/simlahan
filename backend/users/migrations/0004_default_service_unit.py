from django.db import migrations

DEFAULT_NAME = "Unit Layanan Utama"


def create_default_service_unit(apps, schema_editor):
    """Instalasi baru belum punya unit layanan, sehingga aplikasi petugas
    menampilkan galat "Pengguna belum memiliki unit layanan" di setiap halaman.
    Buat satu unit bawaan dan pasangkan ke akun petugas (bukan pemohon portal)
    yang belum punya unit. Akun baru mendapatkannya saat masuk
    (``User.update_service_units``)."""
    ServiceUnit = apps.get_model("leasing", "ServiceUnit")
    User = apps.get_model("users", "User")
    unit = ServiceUnit.objects.order_by("pk").first()
    if unit is None:
        unit = ServiceUnit.objects.create(name=DEFAULT_NAME)
    for user in User.objects.filter(service_units__isnull=True, pemohon__isnull=True):
        user.service_units.add(unit)


class Migration(migrations.Migration):

    dependencies = [
        ("alokasi", "0003_neutral_authority_texts"),
        ("leasing", "0004_verbose_names"),
        ("users", "0003_verbose_names"),
    ]

    operations = [
        migrations.RunPython(create_default_service_unit, migrations.RunPython.noop),
    ]
