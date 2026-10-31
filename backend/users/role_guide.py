"""Panduan pengguna per peran: satu sumber untuk halaman /akun/panduan/ dan
dokumen ``docs/panduan-peran.md`` (dibuat ulang dengan
``python manage.py panduan_peran > ../docs/panduan-peran.md``).

Setiap grup di ``UserGroup`` wajib punya panduan di sini (dijaga tes).
"""

from dataclasses import dataclass

from utils.group_permissions import UserGroup


@dataclass(frozen=True)
class RoleGuide:
    name: str
    sample: str
    summary: str
    login: str
    home: str
    menus: tuple[str, ...]
    can: tuple[str, ...]
    limits: tuple[str, ...]


SPA = "Alamat utama SimLahan (`/`), dengan nama pengguna dan sandi."
PANEL = (
    "Alamat utama SimLahan (`/`) atau langsung di panel admin (`/admin/`); "
    "satu kali masuk berlaku untuk keduanya."
)
COMMAND = (
    "Langsung di pusat komando (`/komando/masuk/`), atau di alamat utama "
    "SimLahan (`/`) lalu tombol **Pusat Komando**; satu kali masuk berlaku "
    "untuk keduanya."
)
ACQUISITION_MENU = (
    "Pengadaan Tanah: Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat"
)
LEASE_READ_MENUS = (
    "Sewa",
    ACQUISITION_MENU,
    "Kontak",
    "Catatan area",
    "Prinsip sewa",
)
LEASE_TAIL_MENUS = (
    "Kompensasi pembangunan sisipan",
    "Pencarian area",
)
NO_OTHER_MODULES = (
    "Tidak bisa membuka panel admin, alokasi lahan, manajemen aset lahan, pusat "
    "komando, atau aplikasi lapangan."
)
ACQUISITION_ONLY = (
    "Hanya modul pengadaan tanah; modul sewa, alokasi, aset, pusat komando, dan "
    "panel admin tidak terbuka."
)
DOCUMENTS_MENU = (
    "Dokumen & Perizinan: Dasbor dokumen, Pemanfaatan lahan, Dokumen perizinan, "
    "Dokumen tanda tangan, Templat dokumen, Permintaan unduh"
)
DOWNLOAD_RULE = (
    "Mengunduh dokumen selalu lewat permintaan unduh yang disetujui orang lain; "
    "setiap unduhan diberi tanda air dan tercatat."
)
COMMAND_TABS = (
    "Pusat komando (`/komando/`): Peta (termasuk lapisan Temuan ilegal dan "
    "Patroli SMART), Absen, Lapor (Komsos, Topografi, Temuan ilegal, Patroli "
    "Taman Buru dengan impor SMART, Kegiatan lainnya, jenis lain, uji tanah, "
    "laporan saya), Warga, Tugas (saya, tim, verifikasi, terlambat, semua; "
    "tombol Beri tugas bagi koordinator), Kinerja, Chat; Menu: Persetujuan, Laporan "
    "harian (buat, masuk, lacak, rekap Excel), Peringkat tim, Struktur tim, Feed "
    "aktivitas, Asisten AI, Aplikasi utama; tombol **⇄ Utama** di bilah atas"
)

ROLE_GUIDES: dict[UserGroup, RoleGuide] = {
    UserGroup.SELAILIJA: RoleGuide(
        name="Penelusur",
        sample="contoh.penelusur",
        summary="Menelusuri data sewa dan pengadaan tanah tanpa mengubahnya.",
        login=SPA,
        home="Sewa (daftar sewa).",
        menus=LEASE_READ_MENUS
        + LEASE_TAIL_MENUS
        + ("Lainnya: Indeks biaya hidup, Tugas terjadwal",),
        can=(
            "Mencari dan membuka semua data sewa, penyewa, kontrak, keputusan, "
            "kontak, catatan area, prinsip sewa, dan pencarian area.",
            "Melihat proyek pengadaan, bidang, dan tenggat (data pribadi tersamar).",
            "Melihat riwayat tugas terjadwal.",
        ),
        limits=(
            "Tidak bisa menambah, mengubah, atau menghapus data.",
            "Tidak melihat tagihan dan laporan statistik.",
            NO_OTHER_MODULES,
        ),
    ),
    UserGroup.VALMISTELIJA: RoleGuide(
        name="Penyusun",
        sample="contoh.penyusun",
        summary="Menyiapkan sewa: data sewa, penyewa, area, dasar sewa, dan inspeksi.",
        login=SPA,
        home="Sewa (daftar sewa).",
        menus=LEASE_READ_MENUS
        + ("Statistik dan laporan",)
        + LEASE_TAIL_MENUS
        + (
            "Lainnya: Indeks biaya hidup, Tugas terjadwal, Catatan tagihan, "
            "Kalkulator sewa",
        ),
        can=(
            "Membuat dan mengubah sewa, penyewa dan bagian sewanya, area sewa "
            "beserta alamat dan lampiran, dasar sewa dan subsidi, penyesuaian "
            "sewa, inspeksi, kontak, catatan area, dan komentar.",
            "Mengelola kompensasi pembangunan sisipan.",
            "Membuat laporan sewa dan tagihan di Statistik dan laporan.",
            "Mengelola pencarian kavling/area dan formulirnya.",
            "Melihat pengadaan tanah (data pribadi tersamar).",
        ),
        limits=(
            "Tidak mengubah kontrak, jaminan, keputusan, tagihan, atau pembayaran.",
            NO_OTHER_MODULES,
        ),
    ),
    UserGroup.SOPIMUSVALMISTELIJA: RoleGuide(
        name="Penyusun Kontrak",
        sample="contoh.kontrak",
        summary="Menyusun kontrak sewa dan perubahannya.",
        login=SPA,
        home="Sewa (daftar sewa).",
        menus=LEASE_READ_MENUS
        + ("Statistik dan laporan",)
        + LEASE_TAIL_MENUS
        + ("Lainnya: Indeks biaya hidup, Tugas terjadwal, Catatan tagihan",),
        can=(
            "Membuat dan mengubah kontrak, perubahan kontrak, jaminan, subsidi "
            "pengelolaan dan sementara, serta penyesuaian sewa.",
            "Membuat laporan sewa (laporan tagihan tidak termasuk).",
            "Membaca seluruh data sewa dan pengadaan (data pribadi tersamar).",
        ),
        limits=(
            "Tidak membuat sewa atau penyewa baru dan tidak mengelola tagihan.",
            NO_OTHER_MODULES,
        ),
    ),
    UserGroup.SYOTTAJA: RoleGuide(
        name="Operator Entri Data",
        sample="contoh.operator",
        summary="Memasukkan dan memperbarui data sewa secara lengkap.",
        login=SPA,
        home="Sewa (daftar sewa).",
        menus=LEASE_READ_MENUS
        + ("Statistik dan laporan",)
        + LEASE_TAIL_MENUS
        + (
            "Lainnya: Indeks biaya hidup, Tugas terjadwal, Catatan tagihan, "
            "Kalkulator sewa",
        ),
        can=(
            "Membuat dan mengubah sewa, penyewa, kontrak dan perubahannya, "
            "keputusan dan syaratnya, besaran sewa dan jatuh tempo, dasar sewa "
            "beserta tarif dan keputusannya, inspeksi, kontak, dan catatan area.",
            "Membuat laporan sewa.",
            "Mengelola pencarian kavling/area dan formulirnya.",
        ),
        limits=(
            "Tidak mengelola tagihan, pembayaran, atau penagihan hukum.",
            NO_OTHER_MODULES,
        ),
    ),
    UserGroup.PERINTALAKIMIES: RoleGuide(
        name="Ahli Hukum Penagihan",
        sample="contoh.ahlihukum",
        summary=(
            "Menangani penagihan hukum sewa serta keberatan dan konsinyasi "
            "pengadaan tanah."
        ),
        login=SPA,
        home="Sewa (daftar sewa).",
        menus=LEASE_READ_MENUS
        + ("Statistik dan laporan",)
        + LEASE_TAIL_MENUS
        + (
            "Lainnya: Indeks biaya hidup, Tugas terjadwal, Catatan tagihan, "
            "Kalkulator sewa",
        ),
        can=(
            "Membuat surat penagihan dan templatnya, putusan pengadilan "
            "penagihan, dan catatan penagihan; menghitung bunga denda.",
            "Mengubah data sewa yang terkait penagihan.",
            "Membuat laporan sewa, tagihan, dan jaminan.",
            "Mengelola pencarian kavling/area dan formulirnya.",
            "Pengadaan tanah: mencatat keberatan, konsinyasi, dan dokumen (data "
            "pribadi tersamar).",
        ),
        limits=(
            "Tidak membuat atau menghapus tagihan dan pembayaran.",
            NO_OTHER_MODULES,
        ),
    ),
    UserGroup.LASKUTTAJA: RoleGuide(
        name="Petugas Penagihan",
        sample="contoh.penagihan",
        summary=(
            "Mengelola tagihan sewa dan pembayaran ganti kerugian pengadaan tanah."
        ),
        login=SPA,
        home="Sewa (daftar sewa).",
        menus=LEASE_READ_MENUS
        + ("Statistik dan laporan",)
        + LEASE_TAIL_MENUS
        + ("Lainnya: Indeks biaya hidup, Tugas terjadwal, Catatan tagihan",),
        can=(
            "Membuat dan mengubah tagihan, baris dan set tagihan, pembayaran, "
            "catatan tagihan, jatuh tempo sewa, jaminan, dan kontak penyewa.",
            "Membuat laporan tagihan dan pembayaran.",
            "Pengadaan tanah: mencatat pembayaran dan penyerahan ganti kerugian "
            "yang sudah divalidasi (data pribadi tersamar).",
        ),
        limits=(
            "Tidak mengubah isi sewa, kontrak, atau keputusan.",
            NO_OTHER_MODULES,
        ),
    ),
    UserGroup.PAAKAYTTAJA: RoleGuide(
        name="Administrator",
        sample="contoh.administrator",
        summary="Mengelola seluruh modul dan data master SimLahan.",
        login=PANEL,
        home="Sewa (daftar sewa); semua modul lain ada di menu samping.",
        menus=(
            "Sewa",
            ACQUISITION_MENU,
            "Alokasi Lahan: Permohonan & verifikasi, Tagihan & pembayaran, "
            "Alokasi & lahan tidur, Data lahan, Portal investasi (permintaan "
            "investasi, sektor, kawasan), Portal publik",
            "Manajemen Aset Lahan: Dasbor aset, Data aset & peta, Perkara & "
            "sidang, Okupasi & perambahan, Pengaduan masyarakat, Lelang & seleksi "
            "lahan, Laporan & asisten AI, Aplikasi lapangan",
            "Pusat Komando: Buka Pusat Komando (aplikasi tersendiri, juga lewat "
            "tombol **Pusat Komando** di bilah atas), Korwil, warga & laporan, "
            "temuan ilegal, patroli Taman Buru, jejak patroli SMART (impor .json), "
            "pengaturan poin usaha, jabatan & atasan petugas, riwayat & poin "
            "tugas, laporan harian berjenjang",
            DOCUMENTS_MENU,
            "Kontak",
            "Catatan area",
            "Prinsip sewa",
            "Statistik dan laporan",
        )
        + LEASE_TAIL_MENUS
        + (
            "Lainnya: Indeks biaya hidup, Tugas terjadwal, Catatan tagihan, "
            "Kalkulator sewa",
            "Panel admin (`/admin/`): semua modul dan data master",
        ),
        can=(
            "Membuat, mengubah, dan menghapus data di semua modul, termasuk "
            "validasi ganti kerugian dan data pribadi (NIK/rekening).",
            "Melihat data semua unit layanan dan semua Korwil, termasuk NIK warga.",
            "Mengatur jabatan dan atasan langsung petugas pusat komando (menentukan "
            "ke mana laporan harian dikirim dan siapa boleh memberi tugas); "
            "memverifikasi tugas mana pun dan menandai laporan harian selesai "
            "ditinjau.",
            "Mengatur data master (jenis, kategori, tarif, aturan tenggat, konten "
            "portal) dan pengaturan modul di panel admin.",
            "Dokumen & perizinan: mengatur jenis dokumen wajib, templat, dan "
            "pengaturan modul; menyetujui dokumen tanda tangan sebelum dikirim; "
            "menyetujui permintaan unduh, termasuk dokumen rahasia.",
            "Melihat daftar pengguna.",
        ),
        limits=(
            "Menambah pengguna, mengatur grup, dan mengganti sandi orang lain hanya "
            "bisa dilakukan superuser.",
            "Tugas terjadwal hanya bisa dilihat; mengubahnya dan kunci sistem "
            "hanya untuk superuser.",
            "Tidak bisa menyetujui permintaan unduh miliknya sendiri.",
        ),
    ),
    UserGroup.PELAKSANA_PENGADAAN: RoleGuide(
        name="Pelaksana Pengadaan Tanah",
        sample="contoh.pelaksana",
        summary="Menjalankan seluruh tahapan pengadaan tanah (UU 2/2012).",
        login=SPA,
        home="Pengadaan Tanah → Dasbor & tenggat.",
        menus=(ACQUISITION_MENU,),
        can=(
            "Mengelola proyek, bidang, inventarisasi, pihak, penilaian, "
            "musyawarah, ganti kerugian, pembayaran, pelepasan hak, dan "
            "dokumen.",
            "Memvalidasi ganti kerugian (Ketua Pelaksana) dan mengatur kalender "
            "libur serta aturan tenggat.",
            "Melihat data pribadi pihak (NIK/rekening).",
        ),
        limits=(ACQUISITION_ONLY,),
    ),
    UserGroup.SATGAS_PENGADAAN: RoleGuide(
        name="Satgas Pengadaan Tanah",
        sample="contoh.satgas",
        summary="Melakukan pendataan lapangan pengadaan tanah.",
        login=SPA,
        home="Pengadaan Tanah → Dasbor & tenggat.",
        menus=(ACQUISITION_MENU,),
        can=(
            "Mencatat bidang, inventarisasi, pihak, pengumuman, musyawarah, "
            "pelepasan hak, dan rumah tangga terdampak.",
            "Memperbarui tonggak inventarisasi, musyawarah, dan pelepasan hak "
            "(status, tanggal realisasi, catatan).",
            "Melihat data pribadi pihak (NIK/rekening).",
        ),
        limits=(
            "Tidak memvalidasi ganti kerugian dan tidak mengubah kalender/aturan "
            "tenggat.",
            ACQUISITION_ONLY,
        ),
    ),
    UserGroup.PENILAI: RoleGuide(
        name="Penilai Pertanahan",
        sample="contoh.penilai",
        summary="Mengisi penilaian ganti kerugian pada proyek yang ditugaskan.",
        login=SPA,
        home="Pengadaan Tanah → Dasbor & tenggat.",
        menus=(ACQUISITION_MENU,),
        can=(
            "Mencatat penilaian dan mengunggah dokumen penilaian.",
            "Membaca data proyek yang ditugaskan.",
        ),
        limits=(
            "Hanya melihat proyek yang mencantumkan akunnya di **Pengguna yang "
            "ditugaskan**.",
            "Data pribadi pihak tersamar; penilaian final tidak bisa diubah.",
            ACQUISITION_ONLY,
        ),
    ),
    UserGroup.INSTANSI_PEMOHON: RoleGuide(
        name="Instansi Yang Memerlukan Tanah",
        sample="contoh.instansi",
        summary="Memantau proyek pengadaan milik instansinya.",
        login=SPA,
        home="Pengadaan Tanah → Dasbor & tenggat.",
        menus=(ACQUISITION_MENU,),
        can=(
            "Membaca proyek, bidang, pengumuman, musyawarah, dan penyerahan.",
            "Mengunggah dokumen perencanaan (DPPT, studi kelayakan), BAST, foto, "
            "dan dokumen lain.",
        ),
        limits=(
            "Hanya proyek yang mencantumkan akunnya di **Pengguna yang "
            "ditugaskan**; tanpa nilai uang dan tanpa data pihak.",
            ACQUISITION_ONLY,
        ),
    ),
    UserGroup.PETUGAS_ALOKASI: RoleGuide(
        name="Petugas Alokasi Lahan",
        sample="contoh.alokasi",
        summary="Memproses permohonan alokasi lahan dari portal sampai terbit.",
        login=PANEL,
        home="Panel admin → Permohonan alokasi.",
        menus=(
            "Panel admin, Alokasi lahan: Permohonan, Tagihan, Alokasi, Data lahan "
            "(termasuk impor peta dan profil investasi), Pemohon, Laporan "
            "pembangunan, konten portal",
            "Panel admin, Alokasi lahan: Permintaan investasi, Sektor investasi, "
            "Kawasan investasi",
            "Panel admin, " + DOCUMENTS_MENU + ", Jenis dokumen, Riwayat unduhan",
        ),
        can=(
            "Memeriksa kelengkapan, meminta perbaikan, menyetujui/menolak "
            "permohonan, memverifikasi pembayaran, dan mencabut alokasi.",
            "Memproses permintaan investasi: tinjau, jadwalkan konsultasi, kirim "
            "penawaran sewa/alokasi/kerja sama, balas pesan investor, lalu "
            "selesaikan (kontrak atau draf permohonan alokasi) atau tolak.",
            "Mengelola data lahan (termasuk tarif sewa, sektor, kawasan, insentif) "
            "dan konten portal.",
            "Mencatat pemanfaatan lahan, menentukan dokumen perizinan wajib, "
            "mengunggah/mengimpor templat (Word, PDF, HTML), memverifikasi atau "
            "meminta revisi dokumen, dan mengirim dokumen untuk ditandatangani "
            "(berurutan, OTP surel, sertifikat & kode QR verifikasi).",
            "Menyetujui atau menolak permintaan unduh dokumen biasa.",
            "Menerima ringkasan pemantauan mingguan lewat surel.",
        ),
        limits=(
            "Tidak membuka modul sewa, pengadaan, aset lahan, atau pusat komando.",
            "Tidak menyetujui unduhan dokumen rahasia, tidak menyetujui permintaan "
            "unduh miliknya sendiri, dan tidak mengubah pengaturan modul dokumen.",
            "Tidak bisa membuka data akun pengguna.",
        ),
    ),
    UserGroup.TIM_VERIFIKASI: RoleGuide(
        name="Tim Verifikasi Teknis",
        sample="contoh.verifikasi",
        summary="Memberi penilaian teknis atas permohonan alokasi lahan.",
        login=PANEL,
        home="Panel admin → Permohonan alokasi.",
        menus=(
            "Panel admin, Alokasi lahan: Permohonan, Tagihan, Alokasi, Data lahan, "
            "Pemohon, Laporan pembangunan, Permintaan investasi (baca)",
            "Panel admin, " + DOCUMENTS_MENU + " (baca dan verifikasi)",
        ),
        can=(
            "Membaca permohonan, tagihan, alokasi, dan permintaan investasi.",
            "Mengisi penilaian teknis per kriteria.",
            "Memverifikasi atau meminta revisi dokumen perizinan.",
            "Mengajukan permintaan unduh dokumen. " + DOWNLOAD_RULE,
        ),
        limits=(
            "Tidak memutuskan permohonan, tidak memproses permintaan investasi, "
            "dan tidak mengubah data lahan.",
            "Tidak membuat templat atau dokumen tanda tangan dan tidak menyetujui "
            "permintaan unduh.",
            "Tidak membuka modul lain.",
        ),
    ),
    UserGroup.PETUGAS_ASET: RoleGuide(
        name="Petugas Aset Lahan",
        sample="contoh.aset",
        summary="Mengelola seluruh data aset lahan unit layanannya.",
        login=PANEL,
        home="Panel admin → Dasbor aset.",
        menus=(
            "Panel admin, Manajemen aset lahan: dasbor, peta tematik, data aset, "
            "keuangan (penilaian, pajak, transaksi), okupasi, permukiman kembali, "
            "pengaduan, lelang, dokumen, peta berbagi, laporan & asisten AI",
            "Aplikasi lapangan (`/aset/lapangan/`)",
            "Pusat komando (`/komando/`, tombol **Pusat Komando** di panel "
            "admin) sebagai pengawas: Peta, Absen, Lapor (hanya Laporan "
            "saya/tim), Warga, Tugas, Kinerja, Chat; Menu: Persetujuan, Laporan "
            "harian (termasuk rekap Excel)",
        ),
        can=(
            "Membuat dan mengubah aset, penilaian, pajak, transaksi, okupasi, "
            "permukiman kembali, pengaduan, lelang, dokumen, dan tugas.",
            "Membaca perkara hukum.",
            "Memantau petugas dan Korwil di unit layanannya di pusat komando.",
        ),
        limits=(
            "Hanya data unit layanannya (data tanpa unit layanan terlihat semua).",
            "Tidak melapor kegiatan/uji tanah di pusat komando dan tidak melihat "
            "NIK warga.",
            "Tidak membuka modul sewa, pengadaan, atau alokasi.",
        ),
    ),
    UserGroup.PETUGAS_HUKUM: RoleGuide(
        name="Petugas Hukum",
        sample="contoh.hukum",
        summary="Menangani perkara dan sidang terkait aset lahan.",
        login=PANEL,
        home="Panel admin → Perkara.",
        menus=(
            "Panel admin, Manajemen aset lahan: perkara, advokat & jadwal sidang, "
            "dokumen, okupasi, pengaduan, urusan instansi, tugas, dasbor & peta",
            "Panel admin, " + DOCUMENTS_MENU,
        ),
        can=(
            "Mengelola perkara, advokat, jadwal sidang, dan dokumen perkara.",
            "Menindaklanjuti okupasi dan pengaduan; mengelola urusan instansi dan "
            "tugas.",
            "Membaca aset, kepemilikan, pemangku kepentingan, dan survei.",
            "Menyusun templat dan blok isi, membuat dan mengirim dokumen tanda "
            "tangan (kontrak, perjanjian), serta membaca dokumen perizinan.",
            "Mengajukan permintaan unduh dokumen. " + DOWNLOAD_RULE,
        ),
        limits=(
            "Tidak melihat penilaian, pajak, transaksi, dan peta berbagi.",
            "Tidak memverifikasi dokumen perizinan dan tidak menyetujui permintaan "
            "unduh.",
            "Tidak membuka pusat komando, aplikasi lapangan, atau modul lain.",
        ),
    ),
    UserGroup.PETUGAS_LAPANGAN: RoleGuide(
        name="Petugas Lapangan",
        sample="contoh.lapangan",
        summary="Bekerja di lapangan untuk Korwil tempatnya menjadi anggota.",
        login=COMMAND,
        home="Pusat komando (`/komando/`).",
        menus=(
            COMMAND_TABS,
            "Aplikasi lapangan (`/aset/lapangan/`): laporan & foto lapangan",
            "Panel admin: okupasi, pengaduan, survei, tugas, Korwil, warga, "
            "kegiatan, temuan ilegal, patroli Taman Buru, jejak patroli SMART, "
            "uji tanah, jabatan & atasan petugas, riwayat & poin tugas, laporan "
            "harian berjenjang (baca saja)",
        ),
        can=(
            "Absen, melapor kegiatan dan uji tanah, mendata warga, chat, dan SOS "
            "di pusat komando.",
            "Komsos dengan beberapa warga baru sekaligus; mencatat temuan ilegal "
            "(baru atau kunjungan berulang) dan patroli Taman Buru (temuan, bibit, "
            "impor berkas SMART); menilai dampak Kegiatan lainnya.",
            "Membuat laporan lapangan, okupasi dan tindakan teguran; "
            "menindaklanjuti pengaduan dan survei.",
            "Mengerjakan tugas: mulai, laporkan selesai (catatan, foto bukti, "
            "GPS), atau tandai ada kendala; poin tugas yang diverifikasi masuk KPI "
            "penerima, kontributor, dan pemberi tugas.",
            "Mengirim laporan harian ke atasan langsung (bisa disusun otomatis "
            "dari kegiatan yang belum dilaporkan, dengan lampiran), memperbaiki "
            "laporan yang dikembalikan, melacak posisinya, dan mengunduh rekap "
            "Excel.",
            "Bekerja luring; data terkirim otomatis saat ada sinyal.",
        ),
        limits=(
            "Hanya Korwil tempatnya menjadi anggota (diatur di data Korwil).",
            "Tidak memverifikasi laporan, tidak melihat NIK warga, dan tidak "
            "membuka modul lain.",
            "Klaim dampak Signifikan/Kritis dihitung 6 poin sampai dikonfirmasi "
            "atasan.",
            "Tidak bisa memverifikasi tugasnya sendiri; tugas yang dilaporkan "
            "selesai menunggu verifikasi pemberi tugas atau atasan.",
        ),
    ),
    UserGroup.KOORDINATOR_WILAYAH: RoleGuide(
        name="Koordinator Wilayah",
        sample="contoh.korwil",
        summary="Memimpin tim lapangan di Korwil yang dipimpinnya.",
        login=COMMAND,
        home="Pusat komando (`/komando/`).",
        menus=(
            COMMAND_TABS,
            "Panel admin: Korwil, warga, kegiatan, uji tanah, SOS, tugas, jabatan "
            "& atasan petugas, riwayat & poin tugas, laporan harian berjenjang "
            "(baca saja)",
        ),
        can=(
            "Semua hak petugas lapangan di pusat komando.",
            "Memverifikasi laporan, menangani SOS, menyetujui izin anggota, "
            "melihat KPI anggota, dan membuat tugas wilayah.",
            "Memberi tugas berpoin kepada anggota (penerima utama dan kontributor), "
            "lalu memverifikasi atau mengembalikan tugas yang dilaporkan selesai.",
            "Menerima laporan harian anggota: mengembalikannya untuk revisi, atau "
            "merangkumnya ke laporan sendiri untuk atasan. Semua yang menunggu "
            "keputusan ada di Menu → Persetujuan.",
            "Mengonfirmasi klaim dampak tinggi Kegiatan lainnya milik anggota "
            "(bukan milik sendiri).",
        ),
        limits=(
            "Hanya Korwil yang dipimpinnya dan tugas Korwil yang " "dipimpin/diikuti.",
            "Tidak membuka aplikasi lapangan aset atau modul lain; tidak melihat "
            "NIK warga.",
        ),
    ),
}

APPLICANT_GUIDE = RoleGuide(
    name="Pemohon portal",
    sample="pemohon@contoh.simlahan.invalid",
    summary=(
        "Badan usaha, instansi, atau perorangan yang mengajukan alokasi, sewa, "
        "atau layanan pertanahan lain."
    ),
    login=(
        "Portal (`/portal/masuk/`) dengan alamat surel; daftar sendiri di "
        "`/portal/daftar/`."
    ),
    home="Portal → Akun saya.",
    menus=(
        "Portal: Layanan, Lahan, Investasi (peta peluang, kawasan, bandingkan, "
        "ajukan minat), Lelang, Pengaduan, Lacak, Verifikasi dokumen, Bantuan, "
        "Akun saya (permohonan, permintaan investasi, lahan tersimpan, tagihan, "
        "profil, sandi)",
        "Akun saya → Dokumen & perizinan (`/portal/dokumen/`): pemanfaatan lahan, "
        "dokumen tanda tangan, permintaan unduh",
    ),
    can=(
        "Mengajukan dan melengkapi permohonan, membayar tagihan, melacak status, "
        "dan mengunduh dokumen terbit.",
        "Menjelajah peta investasi tanpa masuk; setelah masuk: menyimpan lahan, "
        "mengajukan minat sewa/alokasi/kerja sama (memilih lahan atau menggambar "
        "usulan lokasi), berkirim pesan dengan petugas, serta menerima atau "
        "menolak penawaran.",
        "Melihat status setiap dokumen perizinan pemanfaatan lahannya, mengunduh "
        "format templat, mengunggah dokumen atau revisi, serta menandatangani "
        "dokumen secara elektronik.",
        "Mengajukan permintaan unduh dokumen; unduhan terbuka setelah disetujui "
        "petugas, diberi tanda air, dan tercatat.",
        "Mengubah profil dan sandi; memakai Lupa sandi bila lupa.",
    ),
    limits=(
        "Tidak bisa masuk ke aplikasi petugas, panel admin, pusat komando, atau API.",
    ),
)

INVESTOR_GUIDE = RoleGuide(
    name="Investor",
    sample="investor@contoh.simlahan.invalid",
    summary=(
        "Akun pemohon portal dengan profil investor: mencari lahan, mengajukan "
        "minat sewa/alokasi/kerja sama, dan menanggapi penawaran petugas."
    ),
    login=(
        "Portal (`/portal/masuk/`) dengan alamat surel; daftar sendiri di "
        "`/portal/investasi/daftar/`. Pemohon yang mengajukan minat investasi "
        "pertamanya otomatis menjadi investor."
    ),
    home="Portal → Akun saya (dasbor investor).",
    menus=(
        "Portal: Investasi (beranda peluang, peta, kawasan, bandingkan, ajukan "
        "minat), Peta Lahan, Layanan, Informasi, Bantuan → Panduan investor",
        "Dasbor investor: penawaran menunggu jawaban, jadwal konsultasi, "
        "permintaan aktif dengan langkah berikutnya, lahan tersimpan, lahan "
        "sesuai sektor minat, dokumen & perizinan",
        "Akun saya → Ubah profil (profil investor: sektor minat, asal modal, "
        "negara asal, situs web), Ubah kata sandi",
    ),
    can=(
        "Semua yang bisa dilakukan pemohon portal.",
        "Menyimpan dan membandingkan hingga 4 lahan, mengunduh profil lahan "
        "(PDF), dan menghitung simulasi biaya.",
        "Mengajukan minat dengan memilih lahan atau menggambar usulan lokasi; "
        "formulir terisi otomatis dari profil investor.",
        "Berkirim pesan dan lampiran dengan petugas, menerima atau menolak "
        "penawaran, serta membatalkan permintaan sebelum penawaran diterima.",
        "Setelah selesai: melengkapi draf permohonan alokasi atau mengelola "
        "dokumen perizinan kontrak sewa/kerja sama.",
    ),
    limits=(
        "Hanya melihat permintaan, pesan, lampiran, dan lahan tersimpan miliknya "
        "sendiri; nomor milik investor lain tidak ditemukan.",
        "Tidak melihat catatan internal petugas dan tidak bisa mengubah status "
        "selain menerima/menolak penawaran atau membatalkan.",
        "Tidak bisa masuk ke aplikasi petugas, panel admin, pusat komando, atau API.",
    ),
)

PORTAL_GUIDES = (APPLICANT_GUIDE, INVESTOR_GUIDE)

GENERAL_STEPS = (
    (
        "Masuk",
        "Buka alamat SimLahan, isi nama pengguna dan sandi. Anda langsung dibawa "
        "ke halaman kerja peran Anda. Satu kali masuk berlaku juga untuk panel "
        "admin, pusat komando, dan aplikasi lapangan sesuai hak Anda.",
    ),
    (
        "Pusat komando",
        "Pusat komando adalah aplikasi tersendiri dengan halaman masuk sendiri di "
        "`/komando/masuk/` (seperti portal). Pindah tanpa masuk ulang: tombol "
        "**Pusat Komando** di bilah atas aplikasi utama dan panel admin, dan "
        "tombol **⇄ Utama** di bilah atas pusat komando. **Keluar** di salah "
        "satunya mengakhiri keduanya di perangkat itu.",
    ),
    (
        "Kode OTP",
        "Bila instansi mengaktifkan OTP, masukkan kode yang dikirim ke surel Anda "
        "setiap kali masuk.",
    ),
    (
        "Menu sesuai peran",
        "Menu hanya menampilkan halaman yang boleh Anda buka. Membuka alamat lain "
        "secara langsung akan ditolak.",
    ),
    (
        "Unit layanan",
        "Data sewa dan aset dibatasi per unit layanan. Bila Anda punya lebih dari "
        "satu unit, pilih unit aktif di bilah atas atau menu nama Anda.",
    ),
    (
        "Panduan dan ganti sandi",
        "Di aplikasi petugas: tombol nama Anda (kanan atas) → **Panduan peran** "
        "atau **Ganti sandi**. Di panel admin: tautan **Panduan peran** di kanan "
        "atas. Di pusat komando: **Menu** → **Panduan peran** atau **Ganti "
        "sandi**. Alamat langsung: `/akun/panduan/` dan `/akun/sandi/`.",
    ),
    (
        "Sandi awal",
        "Ganti sandi awal segera setelah pertama kali masuk. Setelah diganti, "
        "aplikasi lain yang masih terbuka dengan sandi lama meminta masuk ulang.",
    ),
    (
        "Lupa sandi",
        "Hubungi superuser SimLahan untuk dibuatkan sandi baru. Pemohon portal "
        "memakai **Lupa sandi** di halaman masuk portal.",
    ),
)

ADMIN_STEPS = (
    "Masuk sebagai superuser di `/admin/` → Pengguna → Tambah pengguna; isi nama "
    "pengguna dan sandi awal.",
    "Pilih grup sesuai tugasnya. Satu grup per orang membuat menunya jelas; bila "
    "merangkap, menu dan haknya adalah gabungan grup.",
    "Pilih unit layanan. Akses panel admin (status staf) diberikan otomatis untuk "
    "Administrator, petugas alokasi, aset lahan, dan pusat komando.",
    "Penilai dan Instansi: tambahkan akunnya di **Pengguna yang ditugaskan** pada "
    "proyek pengadaan.",
    "Koordinator Wilayah dan Petugas Lapangan: atur **Koordinator** dan "
    "**Anggota** pada data Korwil.",
    "Minta pengguna mengganti sandi saat pertama kali masuk.",
    "Untuk mencoba setiap peran, buat akun contoh: `python manage.py "
    "pengguna_contoh` (hapus dengan `--hapus`).",
)


def sees_all(user) -> bool:
    return user.is_superuser or user.groups.filter(pk=UserGroup.PAAKAYTTAJA).exists()


def guides_for(user) -> list[RoleGuide]:
    """Panduan yang ditampilkan: superuser dan Administrator melihat semua."""
    if sees_all(user):
        return list(ROLE_GUIDES.values()) + list(PORTAL_GUIDES)
    group_ids = set(user.groups.values_list("pk", flat=True))
    return [guide for group, guide in ROLE_GUIDES.items() if group in group_ids]


def render_markdown() -> str:
    lines = [
        "# Panduan peran SimLahan",
        "",
        "<!-- Dibuat dari backend/users/role_guide.py; jangan diubah manual. "
        "Buat ulang: cd backend && python manage.py panduan_peran > "
        "../docs/panduan-peran.md -->",
        "",
        "Panduan yang sama tersedia di aplikasi (`/akun/panduan/`) dan hanya "
        "menampilkan peran pengguna yang membukanya; Administrator melihat "
        "semua peran.",
        "",
        "## Ringkasan peran",
        "",
        "| Peran | Tugas | Masuk & halaman awal | Akun contoh |",
        "|---|---|---|---|",
    ]
    guides = list(ROLE_GUIDES.values()) + list(PORTAL_GUIDES)
    for guide in guides:
        lines.append(
            f"| {guide.name} | {guide.summary} | {guide.home} | `{guide.sample}` |"
        )
    lines += ["", "## Dasar penggunaan", ""]
    for title, text in GENERAL_STEPS:
        lines.append(f"- **{title}.** {text}")
    lines += ["", "## Menyiapkan akun petugas (superuser)", ""]
    lines += [f"{number}. {step}" for number, step in enumerate(ADMIN_STEPS, 1)]
    for guide in guides:
        lines += [
            "",
            f"## {guide.name}",
            "",
            guide.summary,
            "",
            f"- **Masuk:** {guide.login}",
            f"- **Halaman awal:** {guide.home}",
            f"- **Akun contoh:** `{guide.sample}`",
            "",
            "**Menu**",
            "",
        ]
        lines += [f"- {item}" for item in guide.menus]
        lines += ["", "**Yang bisa dilakukan**", ""]
        lines += [f"- {item}" for item in guide.can]
        lines += ["", "**Batas akses**", ""]
        lines += [f"- {item}" for item in guide.limits]
    return "\n".join(lines) + "\n"
