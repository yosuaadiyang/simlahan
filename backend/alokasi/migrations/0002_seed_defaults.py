"""Data awal modul alokasi: grup petugas, pengaturan, persyaratan, kriteria, konten portal.

Semua isian dapat diubah petugas di /admin/alokasi/. Data hanya ditambahkan bila
tabelnya masih kosong, sehingga perubahan petugas tidak tertimpa.
"""

import datetime
from decimal import Decimal

from django.db import migrations

ALLOCATION_DOCS = [
    ("KTP penanggung jawab / direktur", "", True, ""),
    ("NPWP pemohon", "", True, ""),
    (
        "NIB dan izin berusaha (OSS)",
        "Wajib bagi badan usaha; perorangan dapat mengunggah surat keterangan usaha.",
        False,
        "",
    ),
    (
        "Akta pendirian dan perubahan terakhir beserta pengesahan Kemenkumham",
        "Khusus badan usaha.",
        False,
        "",
    ),
    (
        "Proposal rencana usaha",
        "Uraian kegiatan, nilai investasi, tenaga kerja, dan manfaat.",
        True,
        "",
    ),
    ("Rencana tapak (site plan) awal", "", True, ""),
    ("Jadwal pelaksanaan pembangunan", "", True, ""),
    (
        "Bukti kemampuan keuangan",
        "Laporan keuangan terakhir atau rekening koran 3 bulan.",
        True,
        "",
    ),
    (
        "Surat pernyataan kesanggupan",
        "Kesanggupan membayar UWT, membangun sesuai jadwal, dan mematuhi ketentuan alokasi.",
        True,
        "",
    ),
    (
        "Surat rekomendasi / dasar pengalokasian langsung",
        "Dokumen yang menjadi dasar pengalokasian tanah secara langsung.",
        True,
        "langsung",
    ),
]

TRANSFER_DOCS = [
    ("Surat permohonan peralihan hak", "", True),
    ("KTP para pihak (pemegang dan penerima hak)", "", True),
    ("Dasar peralihan (perjanjian jual beli, hibah, atau putusan)", "", True),
    ("Bukti pelunasan UWT", "", True),
    (
        "Akta pendirian / NIB penerima hak",
        "Bila penerima hak berupa badan usaha.",
        False,
    ),
    ("Sertipikat hak atas tanah", "Bila sudah terbit.", False),
]

CRITERIA = [
    (
        "Kesesuaian kegiatan dengan peruntukan ruang",
        "Kesesuaian rencana kegiatan dengan RTRW/RDTR dan arahan pemanfaatan lahan.",
        Decimal("25"),
    ),
    (
        "Kelayakan rencana usaha dan investasi",
        "Kejelasan rencana usaha, nilai investasi, dan jadwal pembangunan.",
        Decimal("25"),
    ),
    (
        "Kemampuan finansial pemohon",
        "Bukti kemampuan keuangan untuk membiayai UWT dan pembangunan.",
        Decimal("20"),
    ),
    (
        "Dampak ekonomi dan tenaga kerja",
        "Penyerapan tenaga kerja dan manfaat bagi perekonomian daerah.",
        Decimal("15"),
    ),
    (
        "Kelengkapan dan keabsahan dokumen",
        "Dokumen persyaratan lengkap, sah, dan konsisten.",
        Decimal("15"),
    ),
]

INFO_PAGES = [
    (
        "prosedur",
        "tahapan-permohonan-alokasi-tanah",
        "Tahapan permohonan alokasi tanah",
        "Alur dari pendaftaran akun sampai KPT dan PPT terbit.",
        "1. Daftar akun pemohon di portal dan aktifkan melalui surel.\n"
        "2. Pilih lahan yang tersedia di menu Peta Lahan, lalu klik Ajukan permohonan alokasi.\n"
        "3. Lengkapi rencana usaha (kegiatan, nilai investasi, tenaga kerja, jangka pembangunan).\n"
        "4. Unggah seluruh dokumen persyaratan, kemudian ajukan permohonan.\n"
        "5. Petugas memeriksa kelengkapan dan meneruskan ke Tim Verifikasi Teknis.\n"
        "6. Tim Verifikasi Teknis menilai permohonan berdasarkan kriteria berbobot.\n"
        "7. Bila memenuhi nilai minimum, permohonan disetujui dan tagihan UWT serta biaya "
        "administrasi terbit.\n"
        "8. Bayar tagihan dan unggah bukti bayar. Setelah petugas memverifikasi, Keputusan "
        "Pengalokasian Tanah (KPT) dan Perjanjian Pemanfaatan Tanah (PPT) terbit otomatis.\n"
        "9. Pemegang alokasi wajib melaporkan progres perizinan dan pembangunan secara berkala.",
    ),
    (
        "prosedur",
        "tahapan-izin-peralihan-hak",
        "Tahapan izin peralihan hak atas tanah",
        "Alur persetujuan peralihan hak kepada pihak lain.",
        "1. Penerima hak mendaftar akun pemohon di portal.\n"
        "2. Pemegang alokasi membuka menu Akun Saya, memilih alokasi, lalu Ajukan peralihan hak "
        "dengan surel akun penerima hak.\n"
        "3. Unggah dokumen persyaratan peralihan dan ajukan permohonan.\n"
        "4. Petugas memverifikasi permohonan, lalu menyetujui atau menolak.\n"
        "5. Bayar biaya administrasi peralihan hak dan unggah bukti bayar.\n"
        "6. Surat Izin Persetujuan Peralihan Hak Atas Tanah terbit otomatis dan alokasi "
        "beralih ke penerima hak.",
    ),
    (
        "persyaratan",
        "persyaratan-umum-pemohon",
        "Persyaratan umum pemohon",
        "Siapa yang dapat mengajukan dan dokumen yang perlu disiapkan.",
        "Pemohon dapat berupa perorangan, badan usaha, atau instansi pemerintah. Badan usaha wajib "
        "memiliki Nomor Induk Berusaha (NIB). Daftar dokumen persyaratan lengkap per layanan dapat "
        "dilihat di menu Layanan. Berkas diunggah dalam format PDF, JPG, atau PNG dengan ukuran "
        "maksimal 10 MB per berkas.",
    ),
    (
        "regulasi",
        "dasar-hukum-pengelolaan-lahan",
        "Dasar hukum pengelolaan dan alokasi lahan",
        "Peraturan yang menjadi dasar layanan alokasi lahan.",
        "- Undang-Undang Nomor 5 Tahun 1960 tentang Peraturan Dasar Pokok-Pokok Agraria.\n"
        "- Peraturan Pemerintah Nomor 18 Tahun 2021 tentang Hak Pengelolaan, Hak Atas Tanah, "
        "Satuan Rumah Susun, dan Pendaftaran Tanah.\n"
        "- Peraturan Pemerintah Nomor 41 Tahun 2021 tentang Penyelenggaraan Kawasan Perdagangan "
        "Bebas dan Pelabuhan Bebas.\n"
        "- Peraturan Badan Pengusahaan Batam tentang penyelenggaraan pengelolaan lahan yang berlaku.\n\n"
        "Petugas dapat memperbarui daftar ini dan melampirkan salinan peraturan.",
    ),
    (
        "faq",
        "apa-itu-uwt",
        "Apa itu Uang Wajib Tahunan (UWT)?",
        "",
        "UWT adalah kewajiban pembayaran atas pemanfaatan tanah selama jangka waktu alokasi. "
        "Besarnya dihitung dari tarif per m² per tahun × luas lahan × jangka waktu alokasi, dan "
        "ditagihkan setelah permohonan disetujui.",
    ),
    (
        "faq",
        "apa-itu-lahan-tidur",
        "Apa yang dimaksud lahan tidur?",
        "",
        "Lahan tidur adalah lahan yang sudah dialokasikan tetapi tidak dibangun atau tidak "
        "dimanfaatkan dalam batas waktu yang ditetapkan sejak KPT terbit. Alokasi atas lahan tidur "
        "dapat dicabut. Laporkan progres pembangunan secara berkala melalui portal.",
    ),
    (
        "faq",
        "cara-cek-keaslian-dokumen",
        "Bagaimana memeriksa keaslian KPT/PPT?",
        "",
        "Pindai kode QR pada dokumen atau buka menu Cek Dokumen dan masukkan kode verifikasi yang "
        "tercetak di bawah kode QR.",
    ),
    (
        "pengumuman",
        "layanan-alokasi-lahan-daring",
        "Layanan alokasi lahan kini sepenuhnya daring",
        "Pendaftaran, permohonan, pembayaran, dan penerbitan dokumen melalui portal.",
        "Seluruh layanan permohonan alokasi tanah dan izin peralihan hak kini dilayani melalui "
        "portal ini. Waspadai pihak yang mengatasnamakan petugas dan meminta pembayaran di luar "
        "tagihan resmi.",
    ),
]


def seed(apps, schema_editor):
    from alokasi.setup import ensure_groups

    alias = schema_editor.connection.alias if schema_editor else "default"
    ensure_groups(apps.get_model("auth", "Group"), using=alias)

    Settings = apps.get_model("alokasi", "AllocationSettings")
    if not Settings.objects.using(alias).filter(pk=1).exists():
        Settings.objects.using(alias).create(pk=1)

    DocType = apps.get_model("alokasi", "RequirementDocType")
    if not DocType.objects.using(alias).exists():
        for order, (name, description, required, allocation_type) in enumerate(
            ALLOCATION_DOCS, 1
        ):
            DocType.objects.using(alias).create(
                service_type="alokasi",
                allocation_type=allocation_type,
                name=name,
                description=description,
                is_required=required,
                order=order,
            )
        for order, (name, description, required) in enumerate(TRANSFER_DOCS, 1):
            DocType.objects.using(alias).create(
                service_type="peralihan",
                name=name,
                description=description,
                is_required=required,
                order=order,
            )

    Criterion = apps.get_model("alokasi", "VerificationCriterion")
    if not Criterion.objects.using(alias).exists():
        for order, (name, description, weight) in enumerate(CRITERIA, 1):
            Criterion.objects.using(alias).create(
                name=name, description=description, weight=weight, order=order
            )

    InfoPage = apps.get_model("alokasi", "InfoPage")
    if not InfoPage.objects.using(alias).exists():
        today = datetime.date.today()
        for order, (category, slug, title, summary, body) in enumerate(INFO_PAGES, 1):
            InfoPage.objects.using(alias).create(
                category=category,
                slug=slug,
                title=title,
                summary=summary,
                body=body,
                order=order,
                published_at=today,
                is_published=True,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("alokasi", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
