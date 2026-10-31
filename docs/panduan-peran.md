# Panduan peran SimLahan

<!-- Dibuat dari backend/users/role_guide.py; jangan diubah manual. Buat ulang: cd backend && python manage.py panduan_peran > ../docs/panduan-peran.md -->

Panduan yang sama tersedia di aplikasi (`/akun/panduan/`) dan hanya menampilkan peran pengguna yang membukanya; Administrator melihat semua peran.

## Ringkasan peran

| Peran | Tugas | Masuk & halaman awal | Akun contoh |
|---|---|---|---|
| Penelusur | Menelusuri data sewa dan pengadaan tanah tanpa mengubahnya. | Sewa (daftar sewa). | `contoh.penelusur` |
| Penyusun | Menyiapkan sewa: data sewa, penyewa, area, dasar sewa, dan inspeksi. | Sewa (daftar sewa). | `contoh.penyusun` |
| Penyusun Kontrak | Menyusun kontrak sewa dan perubahannya. | Sewa (daftar sewa). | `contoh.kontrak` |
| Operator Entri Data | Memasukkan dan memperbarui data sewa secara lengkap. | Sewa (daftar sewa). | `contoh.operator` |
| Ahli Hukum Penagihan | Menangani penagihan hukum sewa serta keberatan dan konsinyasi pengadaan tanah. | Sewa (daftar sewa). | `contoh.ahlihukum` |
| Petugas Penagihan | Mengelola tagihan sewa dan pembayaran ganti kerugian pengadaan tanah. | Sewa (daftar sewa). | `contoh.penagihan` |
| Administrator | Mengelola seluruh modul dan data master SimLahan. | Sewa (daftar sewa); semua modul lain ada di menu samping. | `contoh.administrator` |
| Pelaksana Pengadaan Tanah | Menjalankan seluruh tahapan pengadaan tanah (UU 2/2012). | Pengadaan Tanah → Dasbor & tenggat. | `contoh.pelaksana` |
| Satgas Pengadaan Tanah | Melakukan pendataan lapangan pengadaan tanah. | Pengadaan Tanah → Dasbor & tenggat. | `contoh.satgas` |
| Penilai Pertanahan | Mengisi penilaian ganti kerugian pada proyek yang ditugaskan. | Pengadaan Tanah → Dasbor & tenggat. | `contoh.penilai` |
| Instansi Yang Memerlukan Tanah | Memantau proyek pengadaan milik instansinya. | Pengadaan Tanah → Dasbor & tenggat. | `contoh.instansi` |
| Petugas Alokasi Lahan | Memproses permohonan alokasi lahan dari portal sampai terbit. | Panel admin → Permohonan alokasi. | `contoh.alokasi` |
| Tim Verifikasi Teknis | Memberi penilaian teknis atas permohonan alokasi lahan. | Panel admin → Permohonan alokasi. | `contoh.verifikasi` |
| Petugas Aset Lahan | Mengelola seluruh data aset lahan unit layanannya. | Panel admin → Dasbor aset. | `contoh.aset` |
| Petugas Hukum | Menangani perkara dan sidang terkait aset lahan. | Panel admin → Perkara. | `contoh.hukum` |
| Petugas Lapangan | Bekerja di lapangan untuk Korwil tempatnya menjadi anggota. | Pusat komando (`/komando/`). | `contoh.lapangan` |
| Koordinator Wilayah | Memimpin tim lapangan di Korwil yang dipimpinnya. | Pusat komando (`/komando/`). | `contoh.korwil` |
| Pemohon portal | Badan usaha, instansi, atau perorangan yang mengajukan alokasi, sewa, atau layanan pertanahan lain. | Portal → Akun saya. | `pemohon@contoh.simlahan.invalid` |
| Investor | Akun pemohon portal dengan profil investor: mencari lahan, mengajukan minat sewa/alokasi/kerja sama, dan menanggapi penawaran petugas. | Portal → Akun saya (dasbor investor). | `investor@contoh.simlahan.invalid` |

## Dasar penggunaan

- **Masuk.** Buka alamat SimLahan, isi nama pengguna dan sandi. Anda langsung dibawa ke halaman kerja peran Anda. Satu kali masuk berlaku juga untuk panel admin, pusat komando, dan aplikasi lapangan sesuai hak Anda.
- **Pusat komando.** Pusat komando adalah aplikasi tersendiri dengan halaman masuk sendiri di `/komando/masuk/` (seperti portal). Pindah tanpa masuk ulang: tombol **Pusat Komando** di bilah atas aplikasi utama dan panel admin, dan tombol **⇄ Utama** di bilah atas pusat komando. **Keluar** di salah satunya mengakhiri keduanya di perangkat itu.
- **Pindah aplikasi.** Setiap halaman (aplikasi utama, panel admin, pusat komando, aplikasi lapangan, portal, dan halaman akun) punya tombol **⇄** ke aplikasi lain yang boleh Anda buka. Halaman masuk dan halaman galat menautkan ke halaman masuk aplikasi lain.
- **Kode OTP.** Bila instansi mengaktifkan OTP, masukkan kode yang dikirim ke surel Anda setiap kali masuk.
- **Menu sesuai peran.** Menu hanya menampilkan halaman yang boleh Anda buka. Membuka alamat lain secara langsung akan ditolak.
- **Unit layanan.** Data sewa dan aset dibatasi per unit layanan. Bila Anda punya lebih dari satu unit, pilih unit aktif di bilah atas atau menu nama Anda.
- **Panduan dan ganti sandi.** Di aplikasi petugas: tombol nama Anda (kanan atas) → **Panduan peran** atau **Ganti sandi**. Di panel admin: tautan **Panduan peran** di kanan atas. Di pusat komando: **Menu** → **Panduan peran** atau **Ganti sandi**. Alamat langsung: `/akun/panduan/` dan `/akun/sandi/`.
- **Sandi awal.** Ganti sandi awal segera setelah pertama kali masuk. Setelah diganti, aplikasi lain yang masih terbuka dengan sandi lama meminta masuk ulang.
- **Lupa sandi.** Hubungi superuser SimLahan untuk dibuatkan sandi baru. Pemohon portal memakai **Lupa sandi** di halaman masuk portal.

## Menyiapkan akun petugas (superuser)

1. Masuk sebagai superuser di `/admin/` → Pengguna → Tambah pengguna; isi nama pengguna dan sandi awal.
2. Pilih grup sesuai tugasnya. Satu grup per orang membuat menunya jelas; bila merangkap, menu dan haknya adalah gabungan grup.
3. Pilih unit layanan. Akses panel admin (status staf) diberikan otomatis untuk Administrator, petugas alokasi, aset lahan, dan pusat komando.
4. Penilai dan Instansi: tambahkan akunnya di **Pengguna yang ditugaskan** pada proyek pengadaan.
5. Koordinator Wilayah dan Petugas Lapangan: atur **Koordinator** dan **Anggota** pada data Korwil.
6. Minta pengguna mengganti sandi saat pertama kali masuk.
7. Untuk mencoba setiap peran, buat akun contoh: `python manage.py pengguna_contoh` (hapus dengan `--hapus`).

## Penelusur

Menelusuri data sewa dan pengadaan tanah tanpa mengubahnya.

- **Masuk:** Alamat utama SimLahan (`/`), dengan nama pengguna dan sandi.
- **Halaman awal:** Sewa (daftar sewa).
- **Akun contoh:** `contoh.penelusur`

**Menu**

- Sewa
- Pengadaan Tanah: Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat
- Kontak
- Catatan area
- Prinsip sewa
- Kompensasi pembangunan sisipan
- Pencarian area
- Lainnya: Indeks biaya hidup, Tugas terjadwal

**Yang bisa dilakukan**

- Mencari dan membuka semua data sewa, penyewa, kontrak, keputusan, kontak, catatan area, prinsip sewa, dan pencarian area.
- Melihat proyek pengadaan, bidang, dan tenggat (data pribadi tersamar).
- Melihat riwayat tugas terjadwal.

**Batas akses**

- Tidak bisa menambah, mengubah, atau menghapus data.
- Tidak melihat tagihan dan laporan statistik.
- Tidak bisa membuka panel admin, alokasi lahan, manajemen aset lahan, pusat komando, atau aplikasi lapangan.

## Penyusun

Menyiapkan sewa: data sewa, penyewa, area, dasar sewa, dan inspeksi.

- **Masuk:** Alamat utama SimLahan (`/`), dengan nama pengguna dan sandi.
- **Halaman awal:** Sewa (daftar sewa).
- **Akun contoh:** `contoh.penyusun`

**Menu**

- Sewa
- Pengadaan Tanah: Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat
- Kontak
- Catatan area
- Prinsip sewa
- Statistik dan laporan
- Kompensasi pembangunan sisipan
- Pencarian area
- Lainnya: Indeks biaya hidup, Tugas terjadwal, Catatan tagihan, Kalkulator sewa

**Yang bisa dilakukan**

- Membuat dan mengubah sewa, penyewa dan bagian sewanya, area sewa beserta alamat dan lampiran, dasar sewa dan subsidi, penyesuaian sewa, inspeksi, kontak, catatan area, dan komentar.
- Mengelola kompensasi pembangunan sisipan.
- Membuat laporan sewa dan tagihan di Statistik dan laporan.
- Mengelola pencarian kavling/area dan formulirnya.
- Melihat pengadaan tanah (data pribadi tersamar).

**Batas akses**

- Tidak mengubah kontrak, jaminan, keputusan, tagihan, atau pembayaran.
- Tidak bisa membuka panel admin, alokasi lahan, manajemen aset lahan, pusat komando, atau aplikasi lapangan.

## Penyusun Kontrak

Menyusun kontrak sewa dan perubahannya.

- **Masuk:** Alamat utama SimLahan (`/`), dengan nama pengguna dan sandi.
- **Halaman awal:** Sewa (daftar sewa).
- **Akun contoh:** `contoh.kontrak`

**Menu**

- Sewa
- Pengadaan Tanah: Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat
- Kontak
- Catatan area
- Prinsip sewa
- Statistik dan laporan
- Kompensasi pembangunan sisipan
- Pencarian area
- Lainnya: Indeks biaya hidup, Tugas terjadwal, Catatan tagihan

**Yang bisa dilakukan**

- Membuat dan mengubah kontrak, perubahan kontrak, jaminan, subsidi pengelolaan dan sementara, serta penyesuaian sewa.
- Membuat laporan sewa (laporan tagihan tidak termasuk).
- Membaca seluruh data sewa dan pengadaan (data pribadi tersamar).

**Batas akses**

- Tidak membuat sewa atau penyewa baru dan tidak mengelola tagihan.
- Tidak bisa membuka panel admin, alokasi lahan, manajemen aset lahan, pusat komando, atau aplikasi lapangan.

## Operator Entri Data

Memasukkan dan memperbarui data sewa secara lengkap.

- **Masuk:** Alamat utama SimLahan (`/`), dengan nama pengguna dan sandi.
- **Halaman awal:** Sewa (daftar sewa).
- **Akun contoh:** `contoh.operator`

**Menu**

- Sewa
- Pengadaan Tanah: Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat
- Kontak
- Catatan area
- Prinsip sewa
- Statistik dan laporan
- Kompensasi pembangunan sisipan
- Pencarian area
- Lainnya: Indeks biaya hidup, Tugas terjadwal, Catatan tagihan, Kalkulator sewa

**Yang bisa dilakukan**

- Membuat dan mengubah sewa, penyewa, kontrak dan perubahannya, keputusan dan syaratnya, besaran sewa dan jatuh tempo, dasar sewa beserta tarif dan keputusannya, inspeksi, kontak, dan catatan area.
- Membuat laporan sewa.
- Mengelola pencarian kavling/area dan formulirnya.

**Batas akses**

- Tidak mengelola tagihan, pembayaran, atau penagihan hukum.
- Tidak bisa membuka panel admin, alokasi lahan, manajemen aset lahan, pusat komando, atau aplikasi lapangan.

## Ahli Hukum Penagihan

Menangani penagihan hukum sewa serta keberatan dan konsinyasi pengadaan tanah.

- **Masuk:** Alamat utama SimLahan (`/`), dengan nama pengguna dan sandi.
- **Halaman awal:** Sewa (daftar sewa).
- **Akun contoh:** `contoh.ahlihukum`

**Menu**

- Sewa
- Pengadaan Tanah: Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat
- Kontak
- Catatan area
- Prinsip sewa
- Statistik dan laporan
- Kompensasi pembangunan sisipan
- Pencarian area
- Lainnya: Indeks biaya hidup, Tugas terjadwal, Catatan tagihan, Kalkulator sewa

**Yang bisa dilakukan**

- Membuat surat penagihan dan templatnya, putusan pengadilan penagihan, dan catatan penagihan; menghitung bunga denda.
- Mengubah data sewa yang terkait penagihan.
- Membuat laporan sewa, tagihan, dan jaminan.
- Mengelola pencarian kavling/area dan formulirnya.
- Pengadaan tanah: mencatat keberatan, konsinyasi, dan dokumen (data pribadi tersamar).

**Batas akses**

- Tidak membuat atau menghapus tagihan dan pembayaran.
- Tidak bisa membuka panel admin, alokasi lahan, manajemen aset lahan, pusat komando, atau aplikasi lapangan.

## Petugas Penagihan

Mengelola tagihan sewa dan pembayaran ganti kerugian pengadaan tanah.

- **Masuk:** Alamat utama SimLahan (`/`), dengan nama pengguna dan sandi.
- **Halaman awal:** Sewa (daftar sewa).
- **Akun contoh:** `contoh.penagihan`

**Menu**

- Sewa
- Pengadaan Tanah: Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat
- Kontak
- Catatan area
- Prinsip sewa
- Statistik dan laporan
- Kompensasi pembangunan sisipan
- Pencarian area
- Lainnya: Indeks biaya hidup, Tugas terjadwal, Catatan tagihan

**Yang bisa dilakukan**

- Membuat dan mengubah tagihan, baris dan set tagihan, pembayaran, catatan tagihan, jatuh tempo sewa, jaminan, dan kontak penyewa.
- Membuat laporan tagihan dan pembayaran.
- Pengadaan tanah: mencatat pembayaran dan penyerahan ganti kerugian yang sudah divalidasi (data pribadi tersamar).

**Batas akses**

- Tidak mengubah isi sewa, kontrak, atau keputusan.
- Tidak bisa membuka panel admin, alokasi lahan, manajemen aset lahan, pusat komando, atau aplikasi lapangan.

## Administrator

Mengelola seluruh modul dan data master SimLahan.

- **Masuk:** Alamat utama SimLahan (`/`) atau langsung di panel admin (`/admin/`); satu kali masuk berlaku untuk keduanya.
- **Halaman awal:** Sewa (daftar sewa); semua modul lain ada di menu samping.
- **Akun contoh:** `contoh.administrator`

**Menu**

- Sewa
- Pengadaan Tanah: Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat
- Alokasi Lahan: Permohonan & verifikasi, Tagihan & pembayaran, Alokasi & lahan tidur, Data lahan, Portal investasi (permintaan investasi, sektor, kawasan), Portal publik
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

**Yang bisa dilakukan**

- Membuat, mengubah, dan menghapus data di semua modul, termasuk validasi ganti kerugian dan data pribadi (NIK/rekening).
- Melihat data semua unit layanan dan semua Korwil, termasuk NIK warga.
- Mengatur jabatan dan atasan langsung petugas pusat komando (menentukan ke mana laporan harian dikirim dan siapa boleh memberi tugas); memverifikasi tugas mana pun dan menandai laporan harian selesai ditinjau.
- Mengatur data master (jenis, kategori, tarif, aturan tenggat, konten portal) dan pengaturan modul di panel admin.
- Dokumen & perizinan: mengatur jenis dokumen wajib, templat, dan pengaturan modul; menyetujui dokumen tanda tangan sebelum dikirim; menyetujui permintaan unduh, termasuk dokumen rahasia.
- Melihat daftar pengguna.
- Menangani tiket & masukan di pusat komando (Menu → Alat & tiket): memproses, menyelesaikan (poin untuk pengirim), atau menolak dengan alasan; menjalankan audit data seluruh wilayah.

**Batas akses**

- Menambah pengguna, mengatur grup, dan mengganti sandi orang lain hanya bisa dilakukan superuser.
- Tugas terjadwal hanya bisa dilihat; mengubahnya dan kunci sistem hanya untuk superuser.
- Tidak bisa menyetujui permintaan unduh miliknya sendiri.

## Pelaksana Pengadaan Tanah

Menjalankan seluruh tahapan pengadaan tanah (UU 2/2012).

- **Masuk:** Alamat utama SimLahan (`/`), dengan nama pengguna dan sandi.
- **Halaman awal:** Pengadaan Tanah → Dasbor & tenggat.
- **Akun contoh:** `contoh.pelaksana`

**Menu**

- Pengadaan Tanah: Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat

**Yang bisa dilakukan**

- Mengelola proyek, bidang, inventarisasi, pihak, penilaian, musyawarah, ganti kerugian, pembayaran, pelepasan hak, dan dokumen.
- Memvalidasi ganti kerugian (Ketua Pelaksana) dan mengatur kalender libur serta aturan tenggat.
- Melihat data pribadi pihak (NIK/rekening).

**Batas akses**

- Hanya modul pengadaan tanah; modul sewa, alokasi, aset, pusat komando, dan panel admin tidak terbuka.

## Satgas Pengadaan Tanah

Melakukan pendataan lapangan pengadaan tanah.

- **Masuk:** Alamat utama SimLahan (`/`), dengan nama pengguna dan sandi.
- **Halaman awal:** Pengadaan Tanah → Dasbor & tenggat.
- **Akun contoh:** `contoh.satgas`

**Menu**

- Pengadaan Tanah: Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat

**Yang bisa dilakukan**

- Mencatat bidang, inventarisasi, pihak, pengumuman, musyawarah, pelepasan hak, dan rumah tangga terdampak.
- Memperbarui tonggak inventarisasi, musyawarah, dan pelepasan hak (status, tanggal realisasi, catatan).
- Melihat data pribadi pihak (NIK/rekening).

**Batas akses**

- Tidak memvalidasi ganti kerugian dan tidak mengubah kalender/aturan tenggat.
- Hanya modul pengadaan tanah; modul sewa, alokasi, aset, pusat komando, dan panel admin tidak terbuka.

## Penilai Pertanahan

Mengisi penilaian ganti kerugian pada proyek yang ditugaskan.

- **Masuk:** Alamat utama SimLahan (`/`), dengan nama pengguna dan sandi.
- **Halaman awal:** Pengadaan Tanah → Dasbor & tenggat.
- **Akun contoh:** `contoh.penilai`

**Menu**

- Pengadaan Tanah: Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat

**Yang bisa dilakukan**

- Mencatat penilaian dan mengunggah dokumen penilaian.
- Membaca data proyek yang ditugaskan.

**Batas akses**

- Hanya melihat proyek yang mencantumkan akunnya di **Pengguna yang ditugaskan**.
- Data pribadi pihak tersamar; penilaian final tidak bisa diubah.
- Hanya modul pengadaan tanah; modul sewa, alokasi, aset, pusat komando, dan panel admin tidak terbuka.

## Instansi Yang Memerlukan Tanah

Memantau proyek pengadaan milik instansinya.

- **Masuk:** Alamat utama SimLahan (`/`), dengan nama pengguna dan sandi.
- **Halaman awal:** Pengadaan Tanah → Dasbor & tenggat.
- **Akun contoh:** `contoh.instansi`

**Menu**

- Pengadaan Tanah: Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat

**Yang bisa dilakukan**

- Membaca proyek, bidang, pengumuman, musyawarah, dan penyerahan.
- Mengunggah dokumen perencanaan (DPPT, studi kelayakan), BAST, foto, dan dokumen lain.

**Batas akses**

- Hanya proyek yang mencantumkan akunnya di **Pengguna yang ditugaskan**; tanpa nilai uang dan tanpa data pihak.
- Hanya modul pengadaan tanah; modul sewa, alokasi, aset, pusat komando, dan panel admin tidak terbuka.

## Petugas Alokasi Lahan

Memproses permohonan alokasi lahan dari portal sampai terbit.

- **Masuk:** Alamat utama SimLahan (`/`) atau langsung di panel admin (`/admin/`); satu kali masuk berlaku untuk keduanya.
- **Halaman awal:** Panel admin → Permohonan alokasi.
- **Akun contoh:** `contoh.alokasi`

**Menu**

- Panel admin, Alokasi lahan: Permohonan, Tagihan, Alokasi, Data lahan (termasuk impor peta dan profil investasi), Pemohon, Laporan pembangunan, konten portal
- Panel admin, Alokasi lahan: Permintaan investasi, Sektor investasi, Kawasan investasi
- Panel admin, Dokumen & Perizinan: Dasbor dokumen, Pemanfaatan lahan, Dokumen perizinan, Dokumen tanda tangan, Templat dokumen, Permintaan unduh, Jenis dokumen, Riwayat unduhan

**Yang bisa dilakukan**

- Memeriksa kelengkapan, meminta perbaikan, menyetujui/menolak permohonan, memverifikasi pembayaran, dan mencabut alokasi.
- Memproses permintaan investasi: tinjau, jadwalkan konsultasi, kirim penawaran sewa/alokasi/kerja sama, balas pesan investor, lalu selesaikan (kontrak atau draf permohonan alokasi) atau tolak.
- Mengelola data lahan (termasuk tarif sewa, sektor, kawasan, insentif) dan konten portal.
- Mencatat pemanfaatan lahan, menentukan dokumen perizinan wajib, mengunggah/mengimpor templat (Word, PDF, HTML), memverifikasi atau meminta revisi dokumen, dan mengirim dokumen untuk ditandatangani (berurutan, OTP surel, sertifikat & kode QR verifikasi).
- Menyetujui atau menolak permintaan unduh dokumen biasa.
- Menerima ringkasan pemantauan mingguan lewat surel.

**Batas akses**

- Tidak membuka modul sewa, pengadaan, aset lahan, atau pusat komando.
- Tidak menyetujui unduhan dokumen rahasia, tidak menyetujui permintaan unduh miliknya sendiri, dan tidak mengubah pengaturan modul dokumen.
- Tidak bisa membuka data akun pengguna.

## Tim Verifikasi Teknis

Memberi penilaian teknis atas permohonan alokasi lahan.

- **Masuk:** Alamat utama SimLahan (`/`) atau langsung di panel admin (`/admin/`); satu kali masuk berlaku untuk keduanya.
- **Halaman awal:** Panel admin → Permohonan alokasi.
- **Akun contoh:** `contoh.verifikasi`

**Menu**

- Panel admin, Alokasi lahan: Permohonan, Tagihan, Alokasi, Data lahan, Pemohon, Laporan pembangunan, Permintaan investasi (baca)
- Panel admin, Dokumen & Perizinan: Dasbor dokumen, Pemanfaatan lahan, Dokumen perizinan, Dokumen tanda tangan, Templat dokumen, Permintaan unduh (baca dan verifikasi)

**Yang bisa dilakukan**

- Membaca permohonan, tagihan, alokasi, dan permintaan investasi.
- Mengisi penilaian teknis per kriteria.
- Memverifikasi atau meminta revisi dokumen perizinan.
- Mengajukan permintaan unduh dokumen. Mengunduh dokumen selalu lewat permintaan unduh yang disetujui orang lain; setiap unduhan diberi tanda air dan tercatat.

**Batas akses**

- Tidak memutuskan permohonan, tidak memproses permintaan investasi, dan tidak mengubah data lahan.
- Tidak membuat templat atau dokumen tanda tangan dan tidak menyetujui permintaan unduh.
- Tidak membuka modul lain.

## Petugas Aset Lahan

Mengelola seluruh data aset lahan unit layanannya.

- **Masuk:** Alamat utama SimLahan (`/`) atau langsung di panel admin (`/admin/`); satu kali masuk berlaku untuk keduanya.
- **Halaman awal:** Panel admin → Dasbor aset.
- **Akun contoh:** `contoh.aset`

**Menu**

- Panel admin, Manajemen aset lahan: dasbor, peta tematik, data aset, keuangan (penilaian, pajak, transaksi), okupasi, permukiman kembali, pengaduan, lelang, dokumen, peta berbagi, laporan & asisten AI
- Aplikasi lapangan (`/aset/lapangan/`)
- Pusat komando (`/komando/`, tombol **Pusat Komando** di panel admin) sebagai pengawas: Peta, Absen, Lapor (hanya Laporan saya/tim), Warga, Tugas, Kinerja, Chat; Menu: Beranda, Peta & spasial, Persetujuan, Laporan harian (termasuk rekap Excel), Peringkat tim, Historis, Uji tanah PLTS (baca & unduh Excel), Alat & tiket

**Yang bisa dilakukan**

- Membuat dan mengubah aset, penilaian, pajak, transaksi, okupasi, permukiman kembali, pengaduan, lelang, dokumen, dan tugas.
- Membaca perkara hukum.
- Memantau petugas dan Korwil di unit layanannya di pusat komando.
- Menandai zona ancaman; membaca bidang penguasaan lahan, foto 360°, tumpang tindih lapisan, dan audit RTRW (tidak mengubah status bidang).
- Mengirim tiket & masukan; memakai OCR, AI dokumen → laporan, AI foto lapangan, dan sinkron Excel.

**Batas akses**

- Hanya data unit layanannya (data tanpa unit layanan terlihat semua).
- Tidak melapor kegiatan/uji tanah di pusat komando dan tidak melihat NIK warga.
- Tidak mengubah titik uji tanah PLTS dan tidak menjalankan audit data.
- Tidak membuka modul sewa, pengadaan, atau alokasi.

## Petugas Hukum

Menangani perkara dan sidang terkait aset lahan.

- **Masuk:** Alamat utama SimLahan (`/`) atau langsung di panel admin (`/admin/`); satu kali masuk berlaku untuk keduanya.
- **Halaman awal:** Panel admin → Perkara.
- **Akun contoh:** `contoh.hukum`

**Menu**

- Panel admin, Manajemen aset lahan: perkara, advokat & jadwal sidang, dokumen, okupasi, pengaduan, urusan instansi, tugas, dasbor & peta
- Panel admin, Dokumen & Perizinan: Dasbor dokumen, Pemanfaatan lahan, Dokumen perizinan, Dokumen tanda tangan, Templat dokumen, Permintaan unduh

**Yang bisa dilakukan**

- Mengelola perkara, advokat, jadwal sidang, dan dokumen perkara.
- Menindaklanjuti okupasi dan pengaduan; mengelola urusan instansi dan tugas.
- Membaca aset, kepemilikan, pemangku kepentingan, dan survei.
- Menyusun templat dan blok isi, membuat dan mengirim dokumen tanda tangan (kontrak, perjanjian), serta membaca dokumen perizinan.
- Mengajukan permintaan unduh dokumen. Mengunduh dokumen selalu lewat permintaan unduh yang disetujui orang lain; setiap unduhan diberi tanda air dan tercatat.

**Batas akses**

- Tidak melihat penilaian, pajak, transaksi, dan peta berbagi.
- Tidak memverifikasi dokumen perizinan dan tidak menyetujui permintaan unduh.
- Tidak membuka pusat komando, aplikasi lapangan, atau modul lain.

## Petugas Lapangan

Bekerja di lapangan untuk Korwil tempatnya menjadi anggota.

- **Masuk:** Langsung di pusat komando (`/komando/masuk/`), atau di alamat utama SimLahan (`/`) lalu tombol **Pusat Komando**; satu kali masuk berlaku untuk keduanya.
- **Halaman awal:** Pusat komando (`/komando/`).
- **Akun contoh:** `contoh.lapangan`

**Menu**

- Pusat komando (`/komando/`): Peta (termasuk lapisan Temuan ilegal, Patroli SMART, Penguasaan lahan, Zona ancaman, Foto situs 360°, lapisan referensi seperti RTRW/hutan/kawasan proyek, dan gaya peta taktis), Absen, Lapor (Komsos, Topografi, Temuan ilegal, Patroli Taman Buru dengan impor SMART, Kegiatan lainnya, jenis lain, uji tanah, laporan saya), Warga, Tugas (saya, tim, verifikasi, terlambat, semua; tombol Beri tugas bagi koordinator), Kinerja (grafik harian/mingguan, radar, kalender 90 hari, sebaran titik kerja di peta, wawasan), Chat; Menu: Beranda (anomali & peringatan, skor risiko Korwil, ringkasan sikap, tren dukungan, detail Korwil), Peta & spasial (penguasaan lahan dengan skor prioritas dan impor KML/KMZ, tumpang tindih lapisan, audit RTRW, peta panas, jejak GPS bagi pimpinan, zona ancaman, foto 360°), Persetujuan, Laporan harian (buat, masuk, lacak, rekap Excel), Peringkat tim (periode, Korwil, tingkat, 10 teratas/terbawah, lencana, Excel, wawasan), Struktur tim, Historis (bagi koordinator dan atasan: komsos, perubahan sikap, luas lahan), Feed aktivitas, Asisten AI, Uji tanah PLTS (progres titik bor/sumur uji/resistivitas/sondir/termal, aksi cepat, foto, riwayat, impor & unduh Excel), Alat & tiket (tiket & masukan, OCR dokumen, AI dokumen → laporan, AI foto lapangan, audit data bagi koordinator, cek perangkat, sinkron Excel), pindah ke aplikasi lain (utama, panel admin, aplikasi lapangan, portal) sesuai hak; tombol **⇄ Utama** di bilah atas
- Aplikasi lapangan (`/aset/lapangan/`): laporan & foto lapangan
- Panel admin: okupasi, pengaduan, survei, tugas, Korwil, warga, kegiatan, temuan ilegal, patroli Taman Buru, jejak patroli SMART, uji tanah, uji tanah PLTS, jabatan & atasan petugas, riwayat & poin tugas, laporan harian berjenjang (baca saja), tiket saya

**Yang bisa dilakukan**

- Absen, melapor kegiatan dan uji tanah, mendata warga, chat, dan SOS di pusat komando.
- Komsos dengan beberapa warga baru sekaligus; mencatat temuan ilegal (baru atau kunjungan berulang) dan patroli Taman Buru (temuan, bibit, impor berkas SMART); menilai dampak Kegiatan lainnya.
- Membuat laporan lapangan, okupasi dan tindakan teguran; menindaklanjuti pengaduan dan survei.
- Mengerjakan tugas: mulai, laporkan selesai (catatan, foto bukti, GPS), atau tandai ada kendala; poin tugas yang diverifikasi masuk KPI penerima, kontributor, dan pemberi tugas.
- Mengirim laporan harian ke atasan langsung (bisa disusun otomatis dari kegiatan yang belum dilaporkan, dengan lampiran), memperbaiki laporan yang dikembalikan, melacak posisinya, dan mengunduh rekap Excel.
- Mengimpor bidang dari KML/KMZ/GeoJSON (bidang baru atau hasil penguasaan yang dicocokkan otomatis) dan memperbarui status penguasaan bidang di Korwilnya; mengunggah foto situs 360°.
- Melihat zona ancaman, tumpang tindih lapisan, audit RTRW, dan peta panas di Menu → Peta & spasial.
- Memperbarui progres titik uji tanah PLTS di Korwilnya (aksi cepat, formulir, foto, impor Excel untuk titik terdaftar).
- Mengirim tiket & masukan (poin bila selesai ditangani); memakai OCR, AI dokumen → laporan, AI foto lapangan, cek perangkat, dan sinkron Excel.
- Bekerja luring; data terkirim otomatis saat ada sinyal.

**Batas akses**

- Hanya Korwil tempatnya menjadi anggota (diatur di data Korwil).
- Tidak memverifikasi laporan, tidak melihat NIK warga, dan tidak membuka modul lain.
- Klaim dampak Signifikan/Kritis dihitung 6 poin sampai dikonfirmasi atasan.
- Tidak bisa memverifikasi tugasnya sendiri; tugas yang dilaporkan selesai menunggu verifikasi pemberi tugas atau atasan.
- Peringkat dan detail Korwil hanya menampilkan skor dirinya sendiri; Historis tidak tersedia kecuali ia menjadi atasan petugas lain.
- Tidak menandai zona ancaman, tidak menghapus foto 360°, dan tidak melihat jejak GPS petugas.
- Tidak menambah titik uji tanah PLTS baru dan tidak menjalankan audit data; hanya melihat tiket miliknya.

## Koordinator Wilayah

Memimpin tim lapangan di Korwil yang dipimpinnya.

- **Masuk:** Langsung di pusat komando (`/komando/masuk/`), atau di alamat utama SimLahan (`/`) lalu tombol **Pusat Komando**; satu kali masuk berlaku untuk keduanya.
- **Halaman awal:** Pusat komando (`/komando/`).
- **Akun contoh:** `contoh.korwil`

**Menu**

- Pusat komando (`/komando/`): Peta (termasuk lapisan Temuan ilegal, Patroli SMART, Penguasaan lahan, Zona ancaman, Foto situs 360°, lapisan referensi seperti RTRW/hutan/kawasan proyek, dan gaya peta taktis), Absen, Lapor (Komsos, Topografi, Temuan ilegal, Patroli Taman Buru dengan impor SMART, Kegiatan lainnya, jenis lain, uji tanah, laporan saya), Warga, Tugas (saya, tim, verifikasi, terlambat, semua; tombol Beri tugas bagi koordinator), Kinerja (grafik harian/mingguan, radar, kalender 90 hari, sebaran titik kerja di peta, wawasan), Chat; Menu: Beranda (anomali & peringatan, skor risiko Korwil, ringkasan sikap, tren dukungan, detail Korwil), Peta & spasial (penguasaan lahan dengan skor prioritas dan impor KML/KMZ, tumpang tindih lapisan, audit RTRW, peta panas, jejak GPS bagi pimpinan, zona ancaman, foto 360°), Persetujuan, Laporan harian (buat, masuk, lacak, rekap Excel), Peringkat tim (periode, Korwil, tingkat, 10 teratas/terbawah, lencana, Excel, wawasan), Struktur tim, Historis (bagi koordinator dan atasan: komsos, perubahan sikap, luas lahan), Feed aktivitas, Asisten AI, Uji tanah PLTS (progres titik bor/sumur uji/resistivitas/sondir/termal, aksi cepat, foto, riwayat, impor & unduh Excel), Alat & tiket (tiket & masukan, OCR dokumen, AI dokumen → laporan, AI foto lapangan, audit data bagi koordinator, cek perangkat, sinkron Excel), pindah ke aplikasi lain (utama, panel admin, aplikasi lapangan, portal) sesuai hak; tombol **⇄ Utama** di bilah atas
- Panel admin: Korwil, warga, kegiatan, uji tanah, uji tanah PLTS, SOS, tugas, jabatan & atasan petugas, riwayat & poin tugas, laporan harian berjenjang (baca saja), tiket saya

**Yang bisa dilakukan**

- Semua hak petugas lapangan di pusat komando.
- Memverifikasi laporan, menangani SOS, menyetujui izin anggota, melihat KPI anggota, dan membuat tugas wilayah.
- Memberi tugas berpoin kepada anggota (penerima utama dan kontributor), lalu memverifikasi atau mengembalikan tugas yang dilaporkan selesai.
- Menerima laporan harian anggota: mengembalikannya untuk revisi, atau merangkumnya ke laporan sendiri untuk atasan. Semua yang menunggu keputusan ada di Menu → Persetujuan.
- Mengonfirmasi klaim dampak tinggi Kegiatan lainnya milik anggota (bukan milik sendiri).
- Melihat Historis wilayahnya: komsos per petugas (warga baru dan kunjungan berulang), perubahan sikap warga, dan perubahan luas lahan.
- Menandai dan menonaktifkan zona ancaman di wilayahnya, menghapus foto 360° wilayahnya, dan melihat jejak GPS anggota (disimpan 60 hari).
- Menambah titik uji tanah PLTS (formulir atau impor Excel), menghapus foto titik, dan menjalankan audit data wilayahnya (bisa diringkas AI).

**Batas akses**

- Hanya Korwil yang dipimpinnya dan tugas Korwil yang dipimpin/diikuti.
- Tidak membuka aplikasi lapangan aset atau modul lain; tidak melihat NIK warga.
- Tidak menangani tiket orang lain (hanya melihat tiket miliknya).

## Pemohon portal

Badan usaha, instansi, atau perorangan yang mengajukan alokasi, sewa, atau layanan pertanahan lain.

- **Masuk:** Portal (`/portal/masuk/`) dengan alamat surel; daftar sendiri di `/portal/daftar/`.
- **Halaman awal:** Portal → Akun saya.
- **Akun contoh:** `pemohon@contoh.simlahan.invalid`

**Menu**

- Portal: Layanan, Lahan, Investasi (peta peluang, kawasan, bandingkan, ajukan minat), Lelang, Pengaduan, Lacak, Verifikasi dokumen, Bantuan, Akun saya (permohonan, permintaan investasi, lahan tersimpan, tagihan, profil, sandi)
- Akun saya → Dokumen & perizinan (`/portal/dokumen/`): pemanfaatan lahan, dokumen tanda tangan, permintaan unduh

**Yang bisa dilakukan**

- Mengajukan dan melengkapi permohonan, membayar tagihan, melacak status, dan mengunduh dokumen terbit.
- Menjelajah peta investasi tanpa masuk; setelah masuk: menyimpan lahan, mengajukan minat sewa/alokasi/kerja sama (memilih lahan atau menggambar usulan lokasi), berkirim pesan dengan petugas, serta menerima atau menolak penawaran.
- Melihat status setiap dokumen perizinan pemanfaatan lahannya, mengunduh format templat, mengunggah dokumen atau revisi, serta menandatangani dokumen secara elektronik.
- Mengajukan permintaan unduh dokumen; unduhan terbuka setelah disetujui petugas, diberi tanda air, dan tercatat.
- Mengubah profil dan sandi; memakai Lupa sandi bila lupa.

**Batas akses**

- Tidak bisa masuk ke aplikasi petugas, panel admin, pusat komando, atau API.

## Investor

Akun pemohon portal dengan profil investor: mencari lahan, mengajukan minat sewa/alokasi/kerja sama, dan menanggapi penawaran petugas.

- **Masuk:** Portal (`/portal/masuk/`) dengan alamat surel; daftar sendiri di `/portal/investasi/daftar/`. Pemohon yang mengajukan minat investasi pertamanya otomatis menjadi investor.
- **Halaman awal:** Portal → Akun saya (dasbor investor).
- **Akun contoh:** `investor@contoh.simlahan.invalid`

**Menu**

- Portal: Investasi (beranda peluang, peta, kawasan, bandingkan, ajukan minat), Peta Lahan, Layanan, Informasi, Bantuan → Panduan investor
- Dasbor investor: penawaran menunggu jawaban, jadwal konsultasi, permintaan aktif dengan langkah berikutnya, lahan tersimpan, lahan sesuai sektor minat, dokumen & perizinan
- Akun saya → Ubah profil (profil investor: sektor minat, asal modal, negara asal, situs web), Ubah kata sandi

**Yang bisa dilakukan**

- Semua yang bisa dilakukan pemohon portal.
- Menyimpan dan membandingkan hingga 4 lahan, mengunduh profil lahan (PDF), dan menghitung simulasi biaya.
- Mengajukan minat dengan memilih lahan atau menggambar usulan lokasi; formulir terisi otomatis dari profil investor.
- Berkirim pesan dan lampiran dengan petugas, menerima atau menolak penawaran, serta membatalkan permintaan sebelum penawaran diterima.
- Setelah selesai: melengkapi draf permohonan alokasi atau mengelola dokumen perizinan kontrak sewa/kerja sama.

**Batas akses**

- Hanya melihat permintaan, pesan, lampiran, dan lahan tersimpan miliknya sendiri; nomor milik investor lain tidak ditemukan.
- Tidak melihat catatan internal petugas dan tidak bisa mengubah status selain menerima/menolak penawaran atau membatalkan.
- Tidak bisa masuk ke aplikasi petugas, panel admin, pusat komando, atau API.
