# Buku peran: Administrator

Buku ini untuk **Administrator**: pengelola semua modul dan data master SimLahan. Baca dulu [Bab 1](../01-mengenal-simlahan.md) dan [Bab 2](../02-dasar-penggunaan.md) bila baru pertama kali memakai SimLahan.

## Masuk

Buka alamat SimLahan atau `/admin/`, isi nama pengguna dan kata sandi, lalu klik **Masuk** ([Bab 2.2](../02-dasar-penggunaan.md#b-panel-admin)).

![Halaman awal Administrator](../gambar/peran/administrator-beranda.png)

<!-- awal: dibuat dari backend/users/role_guide.py; perbarui dengan: cd backend && python manage.py panduan_buku -->

## Ringkasan peran

Mengelola seluruh modul dan data master SimLahan.

- **Cara masuk:** Alamat utama SimLahan (`/`) atau langsung di panel admin (`/admin/`); satu kali masuk berlaku untuk keduanya.
- **Halaman awal:** Sewa (daftar sewa); semua modul lain ada di menu samping.
- **Akun latihan** (hanya di sistem latihan berisi data contoh): `contoh.administrator`

### Menu yang Anda lihat

- Sewa
- Pengadaan Tanah: Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat
- Alokasi Lahan: Permohonan & verifikasi, Tagihan & pembayaran, Alokasi & lahan tidur, Data lahan, Portal investasi (permintaan investasi, sektor, kawasan), Portal publik (termasuk tarif UWT per wilayah dan pesan Kontak Kami)
- Manajemen Aset Lahan: Dasbor aset, Data aset & peta, Perkara & sidang, Okupasi & perambahan, Pengaduan masyarakat, Lelang & seleksi lahan, Laporan & asisten AI, Aplikasi lapangan
- Pusat Komando: Buka Pusat Komando (aplikasi tersendiri, juga lewat tombol **Pusat Komando** di bilah atas), Korwil, warga & laporan, temuan ilegal, patroli Taman Buru, jejak patroli SMART (impor .json), pengaturan poin usaha, jabatan & atasan petugas, riwayat & poin tugas, laporan harian berjenjang, bidang penguasaan lahan, zona ancaman, foto situs 360°, jejak GPS petugas, tiket & masukan (arsip), uji tanah PLTS (titik, foto, riwayat, unduh Excel)
- Dokumen & Perizinan: Dasbor dokumen, Pemanfaatan lahan, Dokumen perizinan, Dokumen tanda tangan, Templat dokumen, Permintaan unduh
- Kontak
- Catatan area
- Prinsip sewa
- Statistik dan laporan
- Kompensasi pembangunan sisipan
- Pencarian area
- Lainnya: Indeks biaya hidup, Tugas terjadwal, Catatan tagihan, Kalkulator sewa
- Panel admin (`/admin/`): semua modul dan data master

### Yang bisa Anda lakukan

- Membuat, mengubah, dan menghapus data di semua modul, termasuk validasi ganti kerugian dan data pribadi (NIK/rekening).
- Melihat data semua unit layanan dan semua Korwil, termasuk NIK warga.
- Mengatur jabatan dan atasan langsung petugas pusat komando (menentukan ke mana laporan harian dikirim dan siapa boleh memberi tugas); memverifikasi tugas mana pun dan menandai laporan harian selesai ditinjau.
- Mengatur data master (jenis, kategori, tarif, aturan tenggat, konten portal) dan pengaturan modul di panel admin.
- Dokumen & perizinan: mengatur jenis dokumen wajib, templat, dan pengaturan modul; menyetujui dokumen tanda tangan sebelum dikirim; menyetujui permintaan unduh, termasuk dokumen rahasia.
- Dokumen tanda tangan: kolom isian penerima (`{{ kolom.<kunci> }}`: teks, tanggal, angka, centang, pilihan, paraf, lampiran), kode akses tambahan, tanda tangan langsung di hadapan petugas (bukti identitas tercatat), ganti penerima yang belum bertindak, cap tanda tangan pada posisi PDF, dan kirim massal dari daftar Pemanfaatan lahan (aksi **Kirim dokumen tanda tangan massal**).
- Memblokir dan membuka blokir penetapan lokasi alokasi.
- Melihat daftar pengguna.
- Menangani tiket & masukan di pusat komando (Menu → Alat & tiket): memproses, menyelesaikan (poin untuk pengirim), atau menolak dengan alasan; menjalankan audit data seluruh wilayah.

### Batas akses

- Menambah pengguna, mengatur grup, dan mengganti sandi orang lain hanya bisa dilakukan superuser.
- Tugas terjadwal hanya bisa dilihat; mengubahnya dan kunci sistem hanya untuk superuser.
- Tidak bisa menyetujui permintaan unduh miliknya sendiri.

<!-- akhir: blok role_guide.py -->

![Menu Administrator](../gambar/peran/administrator-menu.png)

## Pekerjaan sehari-hari

### 1. Memahami cakupan Anda

1. Anda melihat data semua unit layanan dan semua Korwil, termasuk NIK warga, dan bisa mengubah semua modul.
2. Gunakan tombol ⇄ di bilah atas untuk berpindah antara aplikasi utama, panel admin, pusat komando, aplikasi lapangan, dan portal ([Bab 2.6](../02-dasar-penggunaan.md#26-pindah-antaraplikasi)).

### 2. Pekerjaan per modul

1. Sewa: [Bab 3](../10-sewa.md). Pengadaan tanah (termasuk validasi ganti kerugian): [Bab 4](../11-pengadaan-tanah.md).
2. Alokasi lahan dan portal: [Bab 5](../20-alokasi-lahan.md); permintaan investasi: [Bab 6](../21-investasi-petugas.md); dokumen & perizinan: [Bab 7](../22-dokumen-perizinan.md).
3. Aset lahan: [Bab 8](../30-aset-lahan.md); pusat komando: [Bab 10](../40-pusat-komando.md) dan [Bab 11](../41-panel-pusat-komando.md).

### 3. Menyiapkan pusat komando

1. Buat Korwil dan anggotanya ([Bab 11.1](../41-panel-pusat-komando.md#111-korwil-koordinator-wilayah)).
2. Atur jabatan dan atasan langsung setiap petugas ([Bab 11.8](../41-panel-pusat-komando.md#118-jabatan-tugas-dan-laporan-harian)).
3. Atur absensi, bobot KPI, dan poin usaha di **Pengaturan pusat komando** ([Bab 11.10](../41-panel-pusat-komando.md#1110-pengaturan-pusat-komando-administrator)).
4. Tangani tiket di **Menu → Alat & tiket** pusat komando ([Bab 10.9](../40-pusat-komando.md#alat--tiket)).

### 4. Data master dan pengaturan

1. Konten portal, katalog layanan, tarif UWT, kriteria verifikasi: [Bab 5.9](../20-alokasi-lahan.md#59-konten-portal-dan-data-master).
2. Jenis dokumen wajib, templat, dan pengaturan dokumen: [Bab 7.6](../22-dokumen-perizinan.md#76-jenis-dokumen-perizinan) dan [7.9](../22-dokumen-perizinan.md#79-pengaturan-dokumen-administrator).
3. Pengaturan modul aset: [Bab 8.14](../30-aset-lahan.md#814-kategori-dan-pengaturan-modul). Kalender libur dan aturan tenggat: [Bab 4.15](../11-pengadaan-tanah.md#415-kalender--aturan-tenggat).

![Tarif UWT](../gambar/alokasi/tarif-uwt.png)

![Wilayah tarif UWT](../gambar/alokasi/wilayah-uwt.png)

![Jenis dokumen persyaratan](../gambar/alokasi/jenis-persyaratan.png)

![Kriteria verifikasi teknis](../gambar/alokasi/verifikasi-kriteria.png)

### 5. Persetujuan khusus Administrator

1. Menyetujui dokumen tanda tangan sebelum dikirim dan permintaan unduh dokumen **rahasia** ([Bab 7.4](../22-dokumen-perizinan.md#mengirim-dan-memantau), [7.7](../22-dokumen-perizinan.md#77-permintaan-unduh)).
2. Memblokir dan membuka blokir penetapan lokasi alokasi ([Bab 5.5](../20-alokasi-lahan.md#55-alokasi--lahan-tidur)).

## Bab yang perlu dibaca

- [Bab 1](../01-mengenal-simlahan.md)
- [Bab 2](../02-dasar-penggunaan.md)
- [Bab 3–16 (semua bab)](../README.md#daftar-isi)

## Bila ada kendala

- Menu atau tombol tidak ada: peran Anda memang tidak memerlukannya ([Bab 2.10](../02-dasar-penggunaan.md#210-batas-akses-dan-pesan-tidak-berhak)). Hubungi Administrator bila Anda memerlukannya untuk pekerjaan.
- Lupa kata sandi: hubungi Administrator atau superuser untuk menyetel ulang sandi.
- Ringkasan peran yang sama bisa dibuka di dalam aplikasi lewat **Panduan peran** (`/akun/panduan/`).
