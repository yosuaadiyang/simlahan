# Buku peran: Penilai Pertanahan

Buku ini untuk **Penilai Pertanahan**: penilai (KJPP) yang mengisi nilai ganti kerugian pada proyek yang ditugaskan. Buku ini berisi semua langkah kerja peran Anda, lengkap dengan gambar, sehingga cukup dibaca sendiri. Dasar penggunaan yang berlaku untuk semua peran (mengenal layar, ganti sandi, memakai di HP) ada di [Bab 2](../02-dasar-penggunaan.md).

**Cara membaca buku ini.** Kotak merah bernomor pada gambar menunjuk tombol atau kolom yang disebut di langkah. Tulisan *(nomor 2)* berarti: lihat kotak merah bernomor 2 pada gambar tepat di atas langkah itu. Semua gambar memakai data contoh fiktif; isi di layar Anda berbeda, tetapi letak tombolnya sama. Judul bagian bernomor (misalnya *3.4*) sama dengan nomor bagian di buku lengkap.

## Masuk dan halaman awal

<!-- sisip: 02-dasar-penggunaan.md#a-aplikasi-utama-petugas-kantor -->

### A. Aplikasi utama (petugas kantor)

![Halaman masuk aplikasi utama](../gambar/dasar/masuk-aplikasi-utama.png)

1. Buka alamat SimLahan, misalnya `https://simlahan.instansi-anda.go.id/`.
2. Ketik nama pengguna Anda di kotak **Nama pengguna** (nomor 1 di gambar).
3. Ketik kata sandi di kotak **Kata sandi** (nomor 2).
4. Klik tombol biru **Masuk** (nomor 3).
5. Anda langsung dibawa ke halaman kerja peran Anda (lihat bagian "Halaman awal" di buku peran Anda).

Tautan di bawah kotak masuk (nomor 4: **⇄ Pusat Komando**, **⇄ Panel admin**, **⇄ Portal**) membawa Anda ke halaman masuk aplikasi lain.

<!-- akhir sisip -->

### Halaman awal

Setelah masuk, Anda langsung melihat **Dasbor pengadaan tanah**:

![Halaman awal Penilai](../gambar/peran/penilai-beranda.png)

Nomor pada gambar:

1. **☰ Menu**: membuka menu **Pengadaan Tanah** (Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat).
2. **Lihat proyek**: membuka daftar proyek pengadaan.
3. **Tenggat hukum**: kewajiban yang batas waktunya dekat. Klik nama proyek di baris itu untuk membukanya.
4. **Nama Anda**: membuka menu akun (**Panduan peran**, **Ganti sandi**).
5. **Keluar**: mengakhiri sesi di perangkat ini.

### Menu Anda

Klik **☰** (nomor 1 pada gambar halaman awal) untuk membuka menu:

![Menu Penilai](../gambar/peran/penilai-menu.png)

Menu **Pengadaan Tanah** berisi **Dasbor & tenggat**, **Proyek pengadaan**, dan **Kalender & aturan tenggat** (hanya membaca).

<!-- awal: dibuat dari backend/users/role_guide.py; perbarui dengan: cd backend && python manage.py panduan_buku -->

## Ringkasan peran

Mengisi penilaian ganti kerugian pada proyek yang ditugaskan.

- **Cara masuk:** Alamat utama SimLahan (`/`), dengan nama pengguna dan sandi.
- **Halaman awal:** Pengadaan Tanah → Dasbor & tenggat.
- **Akun latihan** (hanya di sistem latihan berisi data contoh): `contoh.penilai`

### Menu yang Anda lihat

- Pengadaan Tanah: Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat

### Yang bisa Anda lakukan

- Mencatat penilaian dan mengunggah dokumen penilaian.
- Membaca data proyek yang ditugaskan.

### Batas akses

- Hanya melihat proyek yang mencantumkan akunnya di **Pengguna yang ditugaskan**.
- Data pribadi pihak tersamar; penilaian final tidak bisa diubah.
- Hanya modul pengadaan tanah; modul sewa, alokasi, aset, pusat komando, dan panel admin tidak terbuka.

<!-- akhir: blok role_guide.py -->

## Urutan kerja Anda

1. Buka **Proyek pengadaan**. Anda hanya melihat proyek yang mencantumkan akun Anda di **Pengguna yang ditugaskan** ([Proyek yang ditugaskan kepada Anda](#proyek-yang-ditugaskan-kepada-anda)).
2. Buka tab **Penilaian**, tambah penilaian per bidang, unggah laporannya, lalu simpan ([4.7 Penilaian (KJPP)](#47-penilaian-kjpp)).
3. Unggah dokumen penilaian lain di tab **Dokumen** ([4.13 Dokumen proyek](#413-dokumen-proyek)).

## Langkah kerja Penilai

<!-- sisip: 11-pengadaan-tanah.md#41-dasbor--tenggat -->

### 4.1 Dasbor & tenggat

Halaman awal peran pengadaan tanah. Menampilkan jumlah proyek per tahap, bidang per status, dan daftar **tenggat hukum** yang dihitung dalam **hari kerja** (libur nasional dan cuti bersama sudah diperhitungkan).

![Dasbor pengadaan tanah](../gambar/pengadaan/dasbor.png)

- Kolom **Status** berwarna: merah = terlambat, kuning = segera jatuh tempo, hijau = aman.
- **Sisa hari kerja** menunjukkan berapa hari kerja lagi sampai batas waktu.
- Klik nama proyek atau bidang untuk langsung membukanya.

Setiap hari kerja pukul 07.00 WIB sistem mengirim surel pengingat tenggat kepada petugas terkait.

<!-- akhir sisip -->

### Proyek yang ditugaskan kepada Anda

![Daftar proyek Penilai](../gambar/pengadaan/penilai-daftar.png)

Daftar hanya berisi proyek yang mencantumkan akun Anda. Klik baris proyek untuk membukanya. Bila proyek yang Anda tangani tidak muncul, minta Pelaksana menambahkan akun Anda di **Pengguna yang ditugaskan** (tombol **Ubah data** proyek).

<!-- sisip: 11-pengadaan-tanah.md#43-halaman-proyek -->

### 4.3 Halaman proyek

![Ringkasan proyek](../gambar/pengadaan/proyek-ringkasan.png)

Bagian atas menampilkan nomor, nama, status, tahap, dasar hukum, instansi, dan lokasi proyek. Kartu angka di bawahnya menampilkan jumlah bidang, luas terkena, persentase hak dilepaskan, nilai penilaian final, ganti kerugian dibayar, dan keberatan berjalan.

- **Unduh daftar nominatif (.xlsx)** (nomor 1): mengunduh daftar bidang dan pihak yang berhak sebagai berkas Excel.
- **Ubah data** (nomor 2): mengubah data proyek, termasuk **Pengguna yang ditugaskan** (akun Penilai dan Instansi yang boleh melihat proyek ini).
- **+ Tambah tonggak** (nomor 3): menambah tonggak tahapan.

Deretan tab di bawah judul membagi pekerjaan per tahap: **Ringkasan**, **Bidang & peta**, **Pihak & inventarisasi**, **Pengumuman**, **Penilaian**, **Musyawarah**, **Keberatan & konsinyasi**, **Ganti kerugian**, **Pelepasan & penyerahan**, **Relokasi**, **Dokumen**, dan **Tenggat**. Angka di samping **Tenggat** adalah jumlah tenggat yang perlu perhatian.

> **Cara kerja yang sama di semua tab:**
> - Tombol **+ Tambah …** membuka jendela formulir. Isi formulir, lalu klik **Simpan**. Klik **Batal** atau **×** untuk menutup tanpa menyimpan.
> - Kolom yang labelnya diberi tanda **\*** wajib diisi. Bila ada yang kosong, formulir tidak tersimpan dan kolom itu diberi pesan merah.
> - Setiap baris tabel punya tautan **Ubah** (membuka formulir yang sama, sudah terisi) dan **Hapus** (meminta konfirmasi dulu).
> - Bila sebuah tombol atau tautan tidak tampil, peran Anda tidak berhak memakainya.
>
> Nomor merah pada gambar formulir di bawah menandai kolom terpenting. Kolom lain boleh diisi bila datanya ada.

#### Tonggak tahapan (tab Ringkasan)

Tonggak adalah kegiatan per tahap (perencanaan, persiapan, pelaksanaan, penyerahan) dengan tanggal rencana dan tanggal realisasi. Bilah **Kemajuan tahapan** menunjukkan berapa tonggak sudah selesai.

![Tambah tonggak](../gambar/pengadaan/form-tonggak.png)

1. Klik **+ Tambah tonggak**. Untuk mengubah tonggak yang ada, klik **Ubah** pada barisnya.
2. Pilih **Tahap** (nomor 1) dan isi **Judul** kegiatan (nomor 2). Keduanya wajib.
3. Isi **Tanggal rencana** (nomor 3). Bila kegiatan sudah terlaksana, isi juga **Tanggal realisasi**.
4. Pilih **Status** (nomor 4): tertunda, sedang berjalan, selesai, atau tidak berlaku.
5. Bila perlu, isi dasar hukum, penanggung jawab, dan catatan.
6. Klik **Simpan** (nomor 5).

Satgas boleh memperbarui tonggak inventarisasi, musyawarah, dan pelepasan hak (status, tanggal realisasi, catatan).

<!-- akhir sisip -->

> Dari semua tab, yang bisa Anda ubah hanya **Penilaian** dan **Dokumen**. Tab lain hanya bisa dibaca.

<!-- sisip: 11-pengadaan-tanah.md#47-penilaian-kjpp -->

### 4.7 Penilaian (KJPP)

*Peran: Penilai Pertanahan (hanya proyek yang ditugaskan), Pelaksana, Administrator.*

![Tab Penilaian](../gambar/pengadaan/tab-05.png)

![Tambah penilaian](../gambar/pengadaan/form-penilaian.png)

1. Buka tab **Penilaian**, lalu klik **+ Tambah penilaian**. Untuk melengkapi penilaian yang ada, klik **Ubah** pada barisnya.
2. Pilih **Bidang tanah** (nomor 1) yang dinilai.
3. Pilih **Status** (nomor 2). Pakai **Draf** selama penilaian belum selesai, dan **Final** bila laporan sudah ditandatangani.
4. Isi **Kantor Jasa Penilai Publik (KJPP)** (nomor 3), lalu nama penilai, nomor izin penilai, nomor laporan, tanggal penilaian, dan tanggal hasil disampaikan.
5. Isi nilai per komponen dalam rupiah, mulai dari **Nilai tanah** (nomor 4), lalu nilai ruang atas dan bawah tanah, bangunan, tanaman, benda lain, dan kerugian nonfisik. Kosongkan komponen yang tidak ada. **Nilai total** dihitung otomatis dan tampil di tabel.
6. Klik **Simpan** (nomor 5).
7. Unggah berkas laporan penilaian di tab **Dokumen** (lihat 4.13).

> Penilaian berstatus **Final** tidak bisa diubah lagi oleh Penilai. Setelah tanggal hasil disampaikan diisi, sistem menghitung **batas musyawarah**.

<!-- akhir sisip -->

### Data pribadi pihak tampil tersamar

![Data pihak tersamar untuk Penilai](../gambar/pengadaan/penilai-pihak.png)

Di tab **Pihak & inventarisasi**, NIK (nomor 1) dan nomor rekening (nomor 2) tampil tersamar, misalnya `9900********0001`. Untuk penilaian, cukup cocokkan **Bidang** dan **Nama** pihak.

<!-- sisip: 11-pengadaan-tanah.md#413-dokumen-proyek -->

### 4.13 Dokumen proyek

*Semua peran pengadaan bisa mengunggah dokumen sesuai haknya. Instansi mengunggah dokumen perencanaan, BAST, foto, dan dokumen lain.*

![Tambah dokumen](../gambar/pengadaan/form-dokumen.png)

1. Buka tab **Dokumen**, lalu klik **+ Tambah dokumen**.
2. Pilih **Jenis dokumen** (nomor 1), misalnya DPPT, laporan penilaian, berita acara musyawarah, atau bukti pembayaran.
3. Isi **Judul** (nomor 2). Wajib.
4. Bila dokumen khusus untuk satu bidang, pilih **Bidang tanah** (nomor 3), dan bila perlu pihak yang berhak. Isi juga nomor dan tanggal dokumen bila ada.
5. Klik **Pilih File** pada **Berkas** (nomor 4), lalu pilih berkas dari komputer. Wajib.
6. Klik **Simpan** (nomor 5).
7. Untuk membuka dokumen yang sudah diunggah, klik **Unduh** pada barisnya.

Jenis berkas diperiksa saat diunggah. Berkas yang isinya tidak sesuai ekstensinya (misalnya program yang diberi nama .pdf) ditolak.

<!-- akhir sisip -->

<!-- sisip: 11-pengadaan-tanah.md#417-pertanyaan-umum -->

### 4.17 Pertanyaan umum

**Proyek tidak muncul di daftar (Penilai/Instansi).** Akun Anda belum dicantumkan di **Pengguna yang ditugaskan**. Minta Pelaksana menambahkannya lewat **Ubah data** proyek.

**Tombol Validasi tidak ada.** Hanya Pelaksana Pengadaan (Ketua Pelaksana) dan Administrator yang memvalidasi, dan hanya untuk baris berstatus **Ditetapkan**.

**Tanggal tenggat jatuh di hari libur.** Periksa daftar hari libur tahun berjalan di **Kalender & aturan tenggat**; tambahkan libur yang belum ada.

<!-- akhir sisip -->

## Bila ada kendala

- **Menu atau tombol yang disebut di buku ini tidak ada di layar Anda.** Peran Anda memang tidak memerlukannya (lihat **Batas akses** di atas). Bila Anda membutuhkannya untuk pekerjaan, minta Administrator menambahkan peran yang sesuai.
- **Pesan "Tidak berhak" atau "Anda tidak berwenang melihat data ini".** Data itu di luar hak peran Anda, bukan kerusakan sistem.
- **Lupa kata sandi.** Hubungi superuser SimLahan untuk dibuatkan sandi baru, lalu ganti sandi itu setelah masuk (klik nama Anda → **Ganti sandi**, atau buka `/akun/sandi/`).
- **Terlalu banyak percobaan masuk.** Tunggu beberapa menit, lalu coba lagi dengan sandi yang benar.
- **Ringkasan peran di dalam aplikasi.** Isi bagian *Ringkasan peran* di atas juga bisa dibuka kapan saja lewat **Panduan peran** (`/akun/panduan/`).
