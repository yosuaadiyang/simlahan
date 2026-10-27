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
| Pemohon portal | Badan usaha, investor, atau perorangan yang mengajukan alokasi, sewa, atau investasi lahan. | Portal → Akun saya. | `pemohon@contoh.simlahan.invalid` |

## Dasar penggunaan

- **Masuk.** Buka alamat SimLahan, isi nama pengguna dan sandi. Anda langsung dibawa ke halaman kerja peran Anda. Satu kali masuk berlaku juga untuk panel admin, pusat komando, dan aplikasi lapangan sesuai hak Anda.
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
- Pusat Komando: Peta operasi & PWA, Absen, Lapor kegiatan, Tugas, Kinerja (KPI), Korwil, warga & laporan
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
- Mengatur data master (jenis, kategori, tarif, aturan tenggat, konten portal) dan pengaturan modul di panel admin.
- Melihat daftar pengguna.

**Batas akses**

- Menambah pengguna, mengatur grup, dan mengganti sandi orang lain hanya bisa dilakukan superuser.
- Tugas terjadwal hanya bisa dilihat; mengubahnya dan kunci sistem hanya untuk superuser.

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

**Yang bisa dilakukan**

- Memeriksa kelengkapan, meminta perbaikan, menyetujui/menolak permohonan, memverifikasi pembayaran, dan mencabut alokasi.
- Memproses permintaan investasi: tinjau, jadwalkan konsultasi, kirim penawaran sewa/alokasi/kerja sama, balas pesan investor, lalu selesaikan (kontrak atau draf permohonan alokasi) atau tolak.
- Mengelola data lahan (termasuk tarif sewa, sektor, kawasan, insentif) dan konten portal.
- Menerima ringkasan pemantauan mingguan lewat surel.

**Batas akses**

- Tidak membuka modul sewa, pengadaan, aset lahan, atau pusat komando.
- Tidak bisa membuka data akun pengguna.

## Tim Verifikasi Teknis

Memberi penilaian teknis atas permohonan alokasi lahan.

- **Masuk:** Alamat utama SimLahan (`/`) atau langsung di panel admin (`/admin/`); satu kali masuk berlaku untuk keduanya.
- **Halaman awal:** Panel admin → Permohonan alokasi.
- **Akun contoh:** `contoh.verifikasi`

**Menu**

- Panel admin, Alokasi lahan: Permohonan, Tagihan, Alokasi, Data lahan, Pemohon, Laporan pembangunan, Permintaan investasi (baca)

**Yang bisa dilakukan**

- Membaca permohonan, tagihan, alokasi, dan permintaan investasi.
- Mengisi penilaian teknis per kriteria.

**Batas akses**

- Tidak memutuskan permohonan, tidak memproses permintaan investasi, dan tidak mengubah data lahan.
- Tidak membuka modul lain.

## Petugas Aset Lahan

Mengelola seluruh data aset lahan unit layanannya.

- **Masuk:** Alamat utama SimLahan (`/`) atau langsung di panel admin (`/admin/`); satu kali masuk berlaku untuk keduanya.
- **Halaman awal:** Panel admin → Dasbor aset.
- **Akun contoh:** `contoh.aset`

**Menu**

- Panel admin, Manajemen aset lahan: dasbor, peta tematik, data aset, keuangan (penilaian, pajak, transaksi), okupasi, permukiman kembali, pengaduan, lelang, dokumen, peta berbagi, laporan & asisten AI
- Aplikasi lapangan (`/aset/lapangan/`)
- Pusat komando sebagai pengawas: Peta, Absen, Lapor (hanya Laporan saya/tim), Warga, Tugas, Kinerja, Chat

**Yang bisa dilakukan**

- Membuat dan mengubah aset, penilaian, pajak, transaksi, okupasi, permukiman kembali, pengaduan, lelang, dokumen, dan tugas.
- Membaca perkara hukum.
- Memantau petugas dan Korwil di unit layanannya di pusat komando.

**Batas akses**

- Hanya data unit layanannya (data tanpa unit layanan terlihat semua).
- Tidak melapor kegiatan/uji tanah di pusat komando dan tidak melihat NIK warga.
- Tidak membuka modul sewa, pengadaan, atau alokasi.

## Petugas Hukum

Menangani perkara dan sidang terkait aset lahan.

- **Masuk:** Alamat utama SimLahan (`/`) atau langsung di panel admin (`/admin/`); satu kali masuk berlaku untuk keduanya.
- **Halaman awal:** Panel admin → Perkara.
- **Akun contoh:** `contoh.hukum`

**Menu**

- Panel admin, Manajemen aset lahan: perkara, advokat & jadwal sidang, dokumen, okupasi, pengaduan, urusan instansi, tugas, dasbor & peta

**Yang bisa dilakukan**

- Mengelola perkara, advokat, jadwal sidang, dan dokumen perkara.
- Menindaklanjuti okupasi dan pengaduan; mengelola urusan instansi dan tugas.
- Membaca aset, kepemilikan, pemangku kepentingan, dan survei.

**Batas akses**

- Tidak melihat penilaian, pajak, transaksi, dan peta berbagi.
- Tidak membuka pusat komando, aplikasi lapangan, atau modul lain.

## Petugas Lapangan

Bekerja di lapangan untuk Korwil tempatnya menjadi anggota.

- **Masuk:** Alamat utama SimLahan (`/`) atau langsung di panel admin (`/admin/`); satu kali masuk berlaku untuk keduanya.
- **Halaman awal:** Pusat komando (`/komando/`).
- **Akun contoh:** `contoh.lapangan`

**Menu**

- Pusat komando (`/komando/`): Peta, Absen, Lapor (kegiatan, uji tanah, laporan saya), Warga, Tugas, Kinerja, Chat; Menu: Peringkat tim, Struktur tim, Feed aktivitas, Asisten AI
- Aplikasi lapangan (`/aset/lapangan/`): laporan & foto lapangan
- Panel admin: okupasi, pengaduan, survei, tugas, Korwil, warga, kegiatan, uji tanah

**Yang bisa dilakukan**

- Absen, melapor kegiatan dan uji tanah, mendata warga, chat, dan SOS di pusat komando.
- Membuat laporan lapangan, okupasi dan tindakan teguran; menindaklanjuti pengaduan dan survei; memperbarui status tugas sendiri.
- Bekerja luring; data terkirim otomatis saat ada sinyal.

**Batas akses**

- Hanya Korwil tempatnya menjadi anggota (diatur di data Korwil).
- Tidak memverifikasi laporan, tidak melihat NIK warga, dan tidak membuka modul lain.

## Koordinator Wilayah

Memimpin tim lapangan di Korwil yang dipimpinnya.

- **Masuk:** Alamat utama SimLahan (`/`) atau langsung di panel admin (`/admin/`); satu kali masuk berlaku untuk keduanya.
- **Halaman awal:** Pusat komando (`/komando/`).
- **Akun contoh:** `contoh.korwil`

**Menu**

- Pusat komando (`/komando/`): Peta, Absen, Lapor (kegiatan, uji tanah, laporan saya), Warga, Tugas, Kinerja, Chat; Menu: Peringkat tim, Struktur tim, Feed aktivitas, Asisten AI
- Panel admin: Korwil, warga, kegiatan, uji tanah, SOS, tugas

**Yang bisa dilakukan**

- Semua hak petugas lapangan di pusat komando.
- Memverifikasi laporan, menangani SOS, menyetujui izin anggota, melihat KPI anggota, dan membuat tugas wilayah.

**Batas akses**

- Hanya Korwil yang dipimpinnya dan tugas Korwil yang dipimpin/diikuti.
- Tidak membuka aplikasi lapangan aset atau modul lain; tidak melihat NIK warga.

## Pemohon portal

Badan usaha, investor, atau perorangan yang mengajukan alokasi, sewa, atau investasi lahan.

- **Masuk:** Portal (`/portal/masuk/`) dengan alamat surel; daftar sendiri di `/portal/daftar/`.
- **Halaman awal:** Portal → Akun saya.
- **Akun contoh:** `pemohon@contoh.simlahan.invalid`

**Menu**

- Portal: Layanan, Lahan, Investasi (peta peluang, kawasan, bandingkan, ajukan minat), Lelang, Pengaduan, Lacak, Verifikasi dokumen, Bantuan, Akun saya (permohonan, permintaan investasi, lahan tersimpan, tagihan, profil, sandi)

**Yang bisa dilakukan**

- Mengajukan dan melengkapi permohonan, membayar tagihan, melacak status, dan mengunduh dokumen terbit.
- Menjelajah peta investasi tanpa masuk; setelah masuk: menyimpan lahan, mengajukan minat sewa/alokasi/kerja sama (memilih lahan atau menggambar usulan lokasi), berkirim pesan dengan petugas, serta menerima atau menolak penawaran.
- Mengubah profil dan sandi; memakai Lupa sandi bila lupa.

**Batas akses**

- Tidak bisa masuk ke aplikasi petugas, panel admin, pusat komando, atau API.
