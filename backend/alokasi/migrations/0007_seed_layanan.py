"""Data awal katalog layanan portal + dokumen persyaratan layanan baru.

Katalog layanan terstruktur (kelompok layanan pertanahan dan layanan
perubahan dokumen) dengan isian yang dapat diubah petugas di
/admin/alokasi/. Data hanya ditambahkan bila tabelnya masih kosong.
"""

from django.db import migrations
from django.utils.text import slugify

SERVICE_CATALOG = [
    # (kategori, service_type, nama, ringkasan, durasi, tarif, dokumen_terbit,
    #  dasar_hukum, alur)
    (
        "pertanahan",
        "alokasi",
        "Alokasi Tanah Reguler",
        "Pengajuan permohonan atas lokasi tanah yang sudah ditampilkan pada peta lahan tersedia.",
        "Sesuai ketentuan layanan",
        "UWT sesuai tarif per lahan + biaya administrasi alokasi (lihat Kalkulator UWT).",
        "KPT dan PPT",
        "UUPA 5/1960; PP 18/2021; PP 41/2021; peraturan instansi pengelola lahan.",
        "Pilih lahan di peta → lengkapi rencana usaha → unggah dokumen → verifikasi teknis "
        "→ tagihan → pembayaran → KPT & PPT terbit.",
    ),
    (
        "pertanahan",
        "alokasi",
        "Alokasi Tanah Langsung",
        "Pengajuan permohonan sesuai kriteria yang ditetapkan instansi pada lokasi tanah tertentu.",
        "Sesuai ketentuan layanan",
        "UWT sesuai tarif per lahan + biaya administrasi alokasi.",
        "KPT dan PPT",
        "UUPA 5/1960; PP 18/2021; peraturan instansi pengelola lahan.",
        "Pilih lahan (jenis langsung) → lengkapi rencana usaha → unggah dokumen dasar "
        "pengalokasian langsung → verifikasi teknis → tagihan → pembayaran → KPT & PPT.",
    ),
    (
        "pertanahan",
        "alokasi",
        "Alokasi Tanah Terbuka",
        "Pengalokasian lahan termatang yang dimulai dengan pengumuman terbuka; penawaran dilakukan melalui lelang.",
        "Sesuai jadwal lelang",
        "UWT sesuai tarif per lahan + biaya administrasi alokasi.",
        "KPT dan PPT",
        "UUPA 5/1960; PP 18/2021; peraturan instansi pengelola lahan.",
        "Ikuti pengumuman lelang di portal → menang penawaran → ajukan permohonan atas lahan "
        "tersebut → verifikasi → tagihan → pembayaran → KPT & PPT.",
    ),
    (
        "pertanahan",
        "perpanjangan",
        "Perpanjangan Hak Atas Tanah",
        "Penambahan jangka waktu berlaku hak atas tanah sebelum jangka waktu berakhir.",
        "Sesuai ketentuan layanan",
        "UWT periode baru + biaya administrasi perpanjangan.",
        "Surat Perpanjangan / Pembaruan Hak Atas Tanah",
        "PP 18/2021; peraturan instansi pengelola lahan.",
        "Buka alokasi Anda → ajukan layanan perpanjangan → unggah dokumen → verifikasi → "
        "tagihan → pembayaran → surat terbit, jangka waktu diperpanjang otomatis.",
    ),
    (
        "pertanahan",
        "pembaruan",
        "Pembaruan Hak Atas Tanah",
        "Penambahan jangka waktu berlaku hak atas tanah setelah jangka waktu sebelumnya berakhir.",
        "Sesuai ketentuan layanan",
        "UWT periode baru + biaya administrasi pembaruan.",
        "Surat Perpanjangan / Pembaruan Hak Atas Tanah",
        "PP 18/2021; peraturan instansi pengelola lahan.",
        "Buka alokasi Anda (berstatus berakhir) → ajukan pembaruan → unggah dokumen → "
        "verifikasi → tagihan → pembayaran → surat terbit, alokasi aktif kembali.",
    ),
    (
        "pertanahan",
        "peralihan",
        "Izin Peralihan Hak Atas Tanah",
        "Persetujuan peralihan hak atas tanah kepada pihak lain (jual beli, hibah, warisan, dsb.).",
        "Sesuai ketentuan layanan",
        "Biaya administrasi peralihan (tetap + per m²).",
        "Surat Izin Persetujuan Peralihan Hak Atas Tanah",
        "UUPA 5/1960; PP 18/2021; peraturan instansi pengelola lahan.",
        "Pemegang mengajukan → penerima hak menyetujui di portal → verifikasi petugas → "
        "tagihan → pembayaran → surat terbit, alokasi beralih.",
    ),
    (
        "perubahan_dokumen",
        "pecah_pl",
        "Pemecahan Penetapan Lokasi (PL)",
        "Pemecahan PL induk menjadi beberapa penetapan lokasi dengan luas lebih kecil.",
        "Sesuai ketentuan layanan",
        "Biaya administrasi layanan.",
        "Surat Persetujuan Layanan Tanah",
        "Peraturan instansi pengelola lahan.",
        "Buka alokasi → ajukan pemecahan PL dengan uraian rencana pemecahan → unggah dokumen "
        "→ verifikasi → tagihan → pembayaran → surat persetujuan terbit.",
    ),
    (
        "perubahan_dokumen",
        "ukur_ulang",
        "Pengukuran Ulang",
        "Layanan pengukuran ulang objek penetapan lokasi (mis. setelah perubahan fisik lahan).",
        "Sesuai ketentuan layanan",
        "Biaya administrasi layanan.",
        "Surat Persetujuan Layanan Tanah",
        "Peraturan instansi pengelola lahan.",
        "Buka alokasi → ajukan pengukuran ulang dengan alasannya → unggah dokumen → "
        "verifikasi → tagihan → pembayaran → surat persetujuan terbit.",
    ),
    (
        "pertanahan",
        "",
        "Persetujuan Lelang / Seleksi Pemanfaatan Lahan",
        "Persetujuan lelang atas tanah kawasan; pengumuman dan penawaran dilakukan melalui portal.",
        "Sesuai jadwal lelang",
        "Sesuai ketentuan lelang.",
        "Surat persetujuan lelang / dokumen hasil lelang",
        "Peraturan instansi pengelola lahan.",
        "Ikuti lelang/seleksi yang diumumkan di portal.",
    ),
]

SERVICE_DOCS = {
    "perpanjangan": [
        ("Surat permohonan perpanjangan/pembaruan hak", "", True),
        ("Fotokopi KPT dan PPT", "", True),
        ("Bukti pelunasan UWT periode berjalan", "", True),
        ("Pernyataan tidak sedang dalam sengketa", "", True),
    ],
    "pembaruan": [
        ("Surat permohonan pembaruan hak", "", True),
        ("Fotokopi KPT dan PPT yang telah berakhir", "", True),
        ("Bukti pelunasan seluruh UWT", "", True),
    ],
    "pecah_pl": [
        ("Surat permohonan pemecahan PL", "", True),
        ("Fotokopi KPT dan PPT", "", True),
        ("Peta rencana pemecahan (denah pembagian bidang)", "", True),
    ],
    "ukur_ulang": [
        ("Surat permohonan pengukuran ulang", "", True),
        ("Fotokopi KPT dan PPT", "", True),
        ("Dokumen pengukuran sebelumnya (bila ada)", "", False),
    ],
}


def seed(apps, schema_editor):
    alias = schema_editor.connection.alias if schema_editor else "default"
    Catalog = apps.get_model("alokasi", "ServiceCatalog")
    if not Catalog.objects.using(alias).exists():
        # Model historis tidak menjalankan ServiceCatalog.save(), jadi slug
        # (unik) diisi di sini.
        used = set()
        for order, entry in enumerate(SERVICE_CATALOG, 1):
            (
                category,
                service_type,
                name,
                summary,
                duration,
                tariff,
                issued,
                legal,
                flow,
            ) = entry
            base = slugify(name)[:200] or "layanan"
            slug, n = base, 2
            while slug in used:
                slug, n = f"{base}-{n}", n + 1
            used.add(slug)
            Catalog.objects.using(alias).create(
                slug=slug,
                category=category,
                service_type=service_type,
                name=name,
                summary=summary,
                description=summary,
                flow=flow,
                duration_note=duration,
                tariff_note=tariff,
                issued_note=issued,
                legal_basis=legal,
                order=order,
                is_active=True,
            )

    DocType = apps.get_model("alokasi", "RequirementDocType")
    if (
        not DocType.objects.using(alias)
        .exclude(service_type__in=("alokasi", "peralihan"))
        .exists()
    ):
        for service_type, docs in SERVICE_DOCS.items():
            for order, (name, description, required) in enumerate(docs, 1):
                DocType.objects.using(alias).create(
                    service_type=service_type,
                    name=name,
                    description=description,
                    is_required=required,
                    order=order,
                )


class Migration(migrations.Migration):
    dependencies = [
        ("alokasi", "0006_servicecatalog_and_more"),
    ]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
