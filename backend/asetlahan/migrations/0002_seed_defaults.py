"""Data awal modul aset lahan: pengaturan modul, kategori aset, kategori pengaduan.

Data hanya ditambahkan bila tabelnya masih kosong, sehingga perubahan petugas
di /admin/asetlahan/ tidak tertimpa.
"""

from django.db import migrations

ASSET_CATEGORIES = [
    (
        "Kantor & fasilitas pemerintah",
        "#0969da",
        "Tanah gedung kantor, sekolah, puskesmas, dan fasilitas umum.",
    ),
    (
        "Tanah cadangan / kosong",
        "#8c959f",
        "Tanah yang belum dimanfaatkan dan dicadangkan untuk kebutuhan mendatang.",
    ),
    (
        "Lahan disewakan / kerja sama",
        "#1a7f37",
        "Tanah yang dimanfaatkan pihak lain melalui sewa atau kerja sama.",
    ),
    (
        "Permukiman kembali",
        "#8250df",
        "Kawasan relokasi warga terdampak pengadaan tanah.",
    ),
    (
        "Jalan & infrastruktur",
        "#57606a",
        "Jalan, saluran, jaringan utilitas, dan prasarana lain.",
    ),
    (
        "Ruang terbuka hijau & konservasi",
        "#2da44e",
        "Taman, hutan kota, sempadan pantai/sungai, dan kawasan lindung.",
    ),
    (
        "Lahan hasil pengadaan tanah",
        "#bf8700",
        "Tanah yang diperoleh melalui pengadaan tanah untuk kepentingan umum.",
    ),
]

GRIEVANCE_CATEGORIES = [
    ("Penyerobotan / okupasi lahan", 14),
    ("Sengketa batas atau kepemilikan", 30),
    ("Ganti kerugian pengadaan tanah", 14),
    ("Permukiman kembali / relokasi", 14),
    ("Sewa & pemanfaatan lahan", 14),
    ("Pelayanan petugas", 7),
    ("Lainnya", None),
]


def seed(apps, schema_editor):
    alias = schema_editor.connection.alias
    ModuleSettings = apps.get_model("asetlahan", "ModuleSettings")
    AssetCategory = apps.get_model("asetlahan", "AssetCategory")
    GrievanceCategory = apps.get_model("asetlahan", "GrievanceCategory")
    if not ModuleSettings.objects.using(alias).filter(pk=1).exists():
        ModuleSettings.objects.using(alias).create(pk=1)
    if not AssetCategory.objects.using(alias).exists():
        AssetCategory.objects.using(alias).bulk_create(
            AssetCategory(name=name, color=color, description=description)
            for name, color, description in ASSET_CATEGORIES
        )
    if not GrievanceCategory.objects.using(alias).exists():
        GrievanceCategory.objects.using(alias).bulk_create(
            GrievanceCategory(name=name, sla_days=days)
            for name, days in GRIEVANCE_CATEGORIES
        )


class Migration(migrations.Migration):
    dependencies = [
        ("asetlahan", "0001_initial"),
    ]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
