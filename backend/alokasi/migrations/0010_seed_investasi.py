"""Data awal portal investasi: sektor usaha dan panduan investasi.

Data hanya ditambahkan bila tabel/kategorinya masih kosong, sehingga isian yang
sudah diubah petugas di /admin/alokasi/ tidak ditimpa.
"""

import datetime

from django.db import migrations
from django.utils.text import slugify

SECTORS = [
    # (nama, ikon, warna, keterangan)
    (
        "Industri",
        "🏭",
        "#2563eb",
        "Manufaktur, pengolahan, dan industri penunjang.",
    ),
    (
        "Pariwisata & perhotelan",
        "🏝️",
        "#0891b2",
        "Resor, hotel, wisata bahari, dan fasilitas rekreasi.",
    ),
    (
        "Perdagangan & jasa",
        "🛍️",
        "#d97706",
        "Pusat perbelanjaan, perkantoran, dan jasa komersial.",
    ),
    (
        "Logistik & pergudangan",
        "📦",
        "#7c3aed",
        "Gudang, pusat distribusi, dan penunjang pelabuhan.",
    ),
    (
        "Perumahan & permukiman",
        "🏘️",
        "#db2777",
        "Perumahan, apartemen, dan kawasan hunian terpadu.",
    ),
    (
        "Pertanian & perikanan",
        "🌾",
        "#65a30d",
        "Agribisnis, budi daya perikanan, dan pengolahan hasilnya.",
    ),
    (
        "Energi & utilitas",
        "⚡",
        "#ca8a04",
        "Pembangkit, energi terbarukan, air bersih, dan telekomunikasi.",
    ),
    (
        "Fasilitas umum & sosial",
        "🏛️",
        "#475569",
        "Pendidikan, kesehatan, ibadah, dan fasilitas publik.",
    ),
]

GUIDES = [
    (
        "Siapa yang dapat mengajukan minat investasi?",
        "Badan usaha, perorangan, dan instansi pemerintah yang memiliki akun pemohon.",
        "Daftar akun pemohon di portal, aktifkan lewat surel, lalu ajukan minat dari "
        "peta investasi atau halaman lahan. Badan usaha melampirkan NIB pada profil.",
    ),
    (
        "Apa beda skema sewa dan alokasi lahan?",
        "Sewa untuk jangka pendek–menengah; alokasi (UWT) untuk hak pemanfaatan jangka panjang.",
        "Sewa lahan: tarif per m² per tahun selama masa sewa yang disepakati, cocok untuk "
        "usaha yang membutuhkan lahan sementara atau ingin memulai lebih cepat.\n"
        "Alokasi lahan: Uang Wajib Tahunan (UWT) dibayar untuk seluruh jangka waktu alokasi, "
        "lalu Keputusan Pengalokasian Tanah (KPT) dan Perjanjian Pemanfaatan Tanah (PPT) "
        "terbit setelah verifikasi teknis dan pembayaran.\n"
        "Kerja sama pemanfaatan: untuk proyek besar dengan bagi hasil atau skema khusus yang "
        "dirundingkan bersama petugas.",
    ),
    (
        "Bagaimana jika lahan yang saya butuhkan tidak ada di peta?",
        "Gambar usulan lokasi di peta dan sebutkan kebutuhan luasnya.",
        "Pada formulir minat investasi, gambar batas lokasi yang diusulkan atau isi "
        "kebutuhan luas saja. Petugas meninjau kesesuaian tata ruang dan status lahannya, "
        "lalu menawarkan lokasi yang sesuai.",
    ),
    (
        "Berapa lama minat investasi diproses?",
        "Petugas meninjau setiap permintaan dan menghubungi investor lewat portal dan surel.",
        "Setiap perubahan status, jadwal konsultasi, dan penawaran dikirim ke surel akun dan "
        "tampil di halaman permintaan. Investor dapat membalas pesan petugas langsung dari "
        "halaman tersebut.",
    ),
    (
        "Apakah penawaran sudah mengikat?",
        "Belum. Penawaran diteruskan ke permohonan alokasi atau kontrak setelah diterima.",
        "Setelah penawaran diterima, skema alokasi diteruskan menjadi draf permohonan "
        "alokasi yang dilengkapi dokumen persyaratan; skema sewa atau kerja sama "
        "dilanjutkan dengan penandatanganan kontrak. Hak atas lahan berlaku sesuai dokumen "
        "yang terbit.",
    ),
]


def seed(apps, schema_editor):
    Sector = apps.get_model("alokasi", "InvestmentSector")
    InfoPage = apps.get_model("alokasi", "InfoPage")
    if not Sector.objects.exists():
        for order, (name, icon, color, description) in enumerate(SECTORS, start=1):
            Sector.objects.create(
                name=name,
                slug=slugify(name),
                icon=icon,
                color=color,
                description=description,
                order=order,
            )
    if not InfoPage.objects.filter(category="investasi").exists():
        for order, (title, summary, body) in enumerate(GUIDES, start=1):
            base = slugify(title)[:200]
            slug = base
            n = 2
            while InfoPage.objects.filter(slug=slug).exists():
                slug = f"{base}-{n}"
                n += 1
            InfoPage.objects.create(
                category="investasi",
                title=title,
                slug=slug,
                summary=summary,
                body=body,
                order=order,
                published_at=datetime.date.today(),
            )


class Migration(migrations.Migration):

    dependencies = [
        ("alokasi", "0009_investasi"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
