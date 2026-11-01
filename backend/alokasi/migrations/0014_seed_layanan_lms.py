"""Data awal layanan portal yang menyamai portal LMS.

Menambah katalog layanan baru (penataan, KSB, KPT & PPT baru/perubahan,
layanan perubahan dokumen, pelaporan) dan dokumen persyaratannya. Hanya
menambah yang belum ada (berdasarkan nama layanan / jenis permohonan), jadi
isian yang sudah diubah petugas tidak ditimpa dan aman dijalankan ulang.
"""

from django.db import migrations
from django.utils.text import slugify

ADMIN = "Biaya administrasi layanan."
LEGAL = "Peraturan instansi pengelola lahan."
SERVICE_FLOW = (
    "Buka alokasi Anda → pilih layanan → isi uraian → unggah dokumen → "
    "verifikasi petugas → tagihan → pembayaran → dokumen terbit."
)

# (kategori, service_type, allocation_type, nama, ringkasan, dokumen_terbit, alur)
CATALOG = [
    (
        "pertanahan",
        "alokasi",
        "penataan",
        "Pengalokasian Penataan",
        "Pengalokasian tanah dalam rangka penataan permukiman bagi warga yang "
        "menguasai fisik bidang tanah di lokasi penataan.",
        "KPT, PPT dan Penetapan Lokasi",
        "Pilih kavling penataan di peta lahan → isi rencana pemanfaatan → unggah "
        "surat permohonan & pernyataan penguasaan fisik → verifikasi lapangan → "
        "tagihan → pembayaran → KPT, PPT dan PL terbit.",
    ),
    (
        "pertanahan",
        "alokasi",
        "ksb",
        "Pengalokasian Kavling Siap Bangun (KSB)",
        "Pengalokasian kavling siap bangun untuk penyelesaian permukiman yang "
        "belum tertata.",
        "KPT, PPT dan Penetapan Lokasi",
        "Pilih KSB di peta lahan → isi rencana pemanfaatan → unggah surat permohonan "
        "& pernyataan penguasaan fisik → verifikasi → tagihan → pembayaran → "
        "KPT, PPT dan PL terbit.",
    ),
    (
        "pertanahan",
        "kpt_perubahan",
        "",
        "Penerbitan KPT dan PPT Perubahan",
        "Permintaan penggantian KPT dan PPT karena perubahan data (mis. nama "
        "pemegang, peruntukan, atau luas hasil pengukuran).",
        "KPT, PPT dan Penetapan Lokasi bernomor baru; dokumen lama tidak berlaku",
        SERVICE_FLOW,
    ),
    (
        "pertanahan",
        "kpt_baru",
        "",
        "Penerbitan KPT dan PPT Baru",
        "Permintaan keputusan dan perjanjian alokasi baru menggantikan dokumen "
        "alokasi lama atas lahan yang sama.",
        "KPT, PPT dan Penetapan Lokasi bernomor baru; dokumen lama tidak berlaku",
        SERVICE_FLOW,
    ),
    (
        "perubahan_dokumen",
        "revisi_pl",
        "",
        "Revisi Penetapan Lokasi (PL)",
        "Pemeriksaan ulang dan perbaikan penetapan lokasi agar sesuai data "
        "sebenarnya.",
        "Surat Persetujuan Layanan Tanah",
        SERVICE_FLOW,
    ),
    (
        "perubahan_dokumen",
        "gabung_pl",
        "",
        "Gabung Penetapan Lokasi (PL)",
        "Penggabungan beberapa penetapan lokasi milik pemegang yang sama menjadi "
        "satu.",
        "Surat Persetujuan Layanan Tanah",
        SERVICE_FLOW,
    ),
    (
        "perubahan_dokumen",
        "penyesuaian",
        "",
        "Penyesuaian Dokumen Alokasi Tanah",
        "Penyesuaian dokumen alokasi tanah terhadap Kesesuaian Kegiatan "
        "Pemanfaatan Ruang (KKPR).",
        "Surat Persetujuan Layanan Tanah",
        SERVICE_FLOW,
    ),
    (
        "perubahan_dokumen",
        "rekomendasi",
        "",
        "Rekomendasi",
        "Surat rekomendasi untuk pengurusan sertipikat hak atas tanah.",
        "Surat Persetujuan Layanan Tanah (rekomendasi)",
        SERVICE_FLOW,
    ),
    (
        "perubahan_dokumen",
        "buka_blokir",
        "",
        "Permohonan Pembukaan Blokir PL",
        "Pembukaan blokir penetapan lokasi setelah penyebab pemblokiran "
        "diselesaikan.",
        "Surat Persetujuan Layanan Tanah; blokir PL dibuka",
        SERVICE_FLOW,
    ),
    (
        "perubahan_dokumen",
        "dok_pengganti",
        "",
        "Dokumen Pengganti",
        "Penggantian KPT, PPT, atau PL yang hilang atau rusak.",
        "KPT, PPT dan Penetapan Lokasi pengganti bernomor baru; dokumen lama "
        "tidak berlaku",
        SERVICE_FLOW,
    ),
    (
        "perubahan_dokumen",
        "hak_tanggungan",
        "",
        "Persetujuan Hak Tanggungan",
        "Persetujuan pembebanan hak tanggungan atas hak tanah (mis. untuk "
        "pembiayaan bank).",
        "Surat Persetujuan Layanan Tanah",
        SERVICE_FLOW,
    ),
    (
        "perubahan_dokumen",
        "lelang",
        "",
        "Persetujuan Lelang Hak Atas Tanah",
        "Persetujuan pelaksanaan lelang atas hak tanah (mis. lelang eksekusi "
        "hak tanggungan).",
        "Surat Persetujuan Layanan Tanah",
        SERVICE_FLOW,
    ),
    (
        "pelaporan",
        "",
        "",
        "Laporan Alokasi",
        "Pelaporan progres perizinan dan pembangunan bagi penerima alokasi tanah.",
        "Tanda terima laporan di riwayat alokasi",
        "Buka alokasi Anda → isi laporan progres (tahap, persentase, investasi, "
        "tenaga kerja, foto) → kirim. Dokumen perizinan wajib dilengkapi di menu "
        "Dokumen & perizinan.",
    ),
]

KTP = ("KTP pemohon", "", True)
KPT = ("Fotokopi KPT dan PPT", "", True)
DOCS = {
    "revisi_pl": [
        ("Surat permohonan revisi dokumen lahan", "", True),
        KPT,
        ("Data pendukung revisi (gambar/hasil ukur)", "", True),
    ],
    "gabung_pl": [
        ("Surat permohonan penggabungan gambar PL", "", True),
        ("Fotokopi KPT dan PPT seluruh PL yang digabung", "", True),
    ],
    "penyesuaian": [
        ("Surat permohonan penyesuaian dokumen", "", True),
        KPT,
        ("Dokumen KKPR / PKKPR", "", True),
    ],
    "rekomendasi": [
        ("Formulir rekomendasi", "", True),
        KPT,
        ("Bukti pelunasan UWT", "", True),
    ],
    "buka_blokir": [
        ("Surat permohonan pembukaan blokir", "", True),
        ("Bukti penyelesaian penyebab blokir", "", True),
    ],
    "dok_pengganti": [
        ("Formulir permohonan penerbitan dokumen pengganti", "", True),
        ("Surat pernyataan dokumen pengganti yang hilang", "", True),
        (
            "Surat keterangan kehilangan dari kepolisian",
            "Wajib bila dokumen hilang.",
            False,
        ),
    ],
    "hak_tanggungan": [
        ("Surat permohonan hak tanggungan dan pernyataan perpanjangan UWT", "", True),
        KPT,
        ("Surat pernyataan dana kredit untuk membangun", "", True),
        ("Surat dari bank/kreditur", "", True),
    ],
    "lelang": [
        ("Surat permohonan persetujuan lelang", "", True),
        KPT,
        ("Dokumen dasar lelang (penetapan/pengumuman lelang)", "", True),
    ],
    "kpt_perubahan": [
        ("Surat permohonan penerbitan KPT dan PPT perubahan", "", True),
        ("Asli KPT dan PPT lama", "", True),
        ("Dokumen dasar perubahan", "", True),
    ],
    "kpt_baru": [
        ("Surat permohonan penerbitan KPT dan PPT baru", "", True),
        ("Dokumen alokasi lama", "", True),
    ],
}
SETTLEMENT_DOCS = [
    KTP,
    ("Kartu keluarga", "", True),
    ("Surat permohonan dan pernyataan penguasaan fisik bidang tanah", "", True),
    ("Surat pernyataan batas maksimum tanah", "", True),
    ("Foto bangunan / bukti penguasaan saat ini", "", False),
]
# Jenis alokasi untuk entri katalog lama (dari 0007), agar daftar dokumen
# persyaratan di halaman layanan mengikuti jenisnya.
OLD_ALLOCATION_TYPES = {
    "Alokasi Tanah Reguler": "reguler",
    "Alokasi Tanah Langsung": "langsung",
    "Alokasi Tanah Terbuka": "terbuka",
}


def seed(apps, schema_editor):
    alias = schema_editor.connection.alias if schema_editor else "default"
    Catalog = apps.get_model("alokasi", "ServiceCatalog")
    DocType = apps.get_model("alokasi", "RequirementDocType")
    catalog = Catalog.objects.using(alias)
    for name, allocation_type in OLD_ALLOCATION_TYPES.items():
        catalog.filter(name=name, service_type="alokasi", allocation_type="").update(
            allocation_type=allocation_type
        )
    used = set(catalog.values_list("slug", flat=True))
    next_order = {}
    for category, service_type, allocation_type, name, summary, issued, flow in CATALOG:
        exists = catalog.filter(name=name).exists() or (
            service_type
            and service_type != "alokasi"
            and catalog.filter(service_type=service_type).exists()
        )
        if exists:
            continue
        if category not in next_order:
            last = (
                catalog.filter(category=category)
                .order_by("-order")
                .values_list("order", flat=True)
                .first()
            )
            next_order[category] = (last or 0) + 1
        base = slugify(name)[:200] or "layanan"
        slug, n = base, 2
        while slug in used:
            slug, n = f"{base}-{n}", n + 1
        used.add(slug)
        catalog.create(
            slug=slug,
            category=category,
            service_type=service_type,
            allocation_type=allocation_type,
            name=name,
            summary=summary,
            description=summary,
            flow=flow,
            duration_note="Sesuai ketentuan layanan",
            tariff_note=(
                "UWT sesuai tarif lahan + biaya administrasi alokasi."
                if service_type == "alokasi"
                else ("–" if not service_type else ADMIN)
            ),
            issued_note=issued,
            legal_basis=LEGAL,
            order=next_order[category],
            is_active=True,
        )
        next_order[category] += 1

    docs = DocType.objects.using(alias)
    for service_type, items in DOCS.items():
        if docs.filter(service_type=service_type).exists():
            continue
        for order, (name, description, required) in enumerate(items, 1):
            docs.create(
                service_type=service_type,
                name=name,
                description=description,
                is_required=required,
                order=order,
            )
    for allocation_type in ("penataan", "ksb"):
        if docs.filter(
            service_type="alokasi", allocation_type=allocation_type
        ).exists():
            continue
        for order, (name, description, required) in enumerate(SETTLEMENT_DOCS, 1):
            docs.create(
                service_type="alokasi",
                allocation_type=allocation_type,
                name=name,
                description=description,
                is_required=required,
                order=100 + order,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("alokasi", "0013_layanan_lms"),
    ]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
