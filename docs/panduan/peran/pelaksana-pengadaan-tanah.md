# Buku peran: Pelaksana Pengadaan Tanah

Buku ini untuk **Pelaksana Pengadaan Tanah**: pelaksana yang menjalankan seluruh tahapan pengadaan tanah. Buku ini berisi semua langkah kerja peran Anda, lengkap dengan gambar, sehingga cukup dibaca sendiri. Dasar penggunaan yang berlaku untuk semua peran (mengenal layar, ganti sandi, memakai di HP) ada di [Bab 2](../02-dasar-penggunaan.md).

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

![Halaman awal Pelaksana](../gambar/peran/pelaksana-beranda.png)

Nomor pada gambar:

1. **☰ Menu**: membuka menu **Pengadaan Tanah** (Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat).
2. **Lihat proyek**: membuka daftar proyek pengadaan.
3. **Tenggat hukum**: kewajiban yang batas waktunya dekat. Klik nama proyek di baris itu untuk membukanya.
4. **Nama Anda**: membuka menu akun (**Panduan peran**, **Ganti sandi**).
5. **Keluar**: mengakhiri sesi di perangkat ini.

### Menu Anda

Klik **☰** (nomor 1 pada gambar halaman awal) untuk membuka menu:

![Menu Pelaksana](../gambar/peran/pelaksana-menu.png)

Menu **Pengadaan Tanah** berisi **Dasbor & tenggat**, **Proyek pengadaan**, dan **Kalender & aturan tenggat**.

<!-- awal: dibuat dari backend/users/role_guide.py; perbarui dengan: cd backend && python manage.py panduan_buku -->

## Ringkasan peran

Menjalankan seluruh tahapan pengadaan tanah (UU 2/2012).

- **Cara masuk:** Alamat utama SimLahan (`/`), dengan nama pengguna dan sandi.
- **Halaman awal:** Pengadaan Tanah → Dasbor & tenggat.
- **Akun latihan** (hanya di sistem latihan berisi data contoh): `contoh.pelaksana`

### Menu yang Anda lihat

- Pengadaan Tanah: Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat

### Yang bisa Anda lakukan

- Mengelola proyek, bidang, inventarisasi, pihak, penilaian, musyawarah, ganti kerugian, pembayaran, pelepasan hak, dan dokumen.
- Memvalidasi ganti kerugian (Ketua Pelaksana) dan mengatur kalender libur serta aturan tenggat.
- Melihat data pribadi pihak (NIK/rekening).

### Batas akses

- Hanya modul pengadaan tanah; modul sewa, alokasi, aset, pusat komando, dan panel admin tidak terbuka.

<!-- akhir: blok role_guide.py -->

## Urutan kerja Anda

Pekerjaan Anda mengikuti tahapan UU 2/2012. Urutan umumnya:

1. Setiap pagi, periksa tenggat di dasbor ([4.1 Dasbor & tenggat](#41-dasbor--tenggat)).
2. Buat proyek dan cantumkan Penilai serta Instansi di **Pengguna yang ditugaskan** ([4.2 Daftar proyek](#42-daftar-proyek)); isi tonggak tahapan ([4.3 Halaman proyek](#43-halaman-proyek)).
3. Tambah atau impor bidang ([4.4 Bidang & peta](#44-bidang--peta)), lalu pihak yang berhak dan inventarisasi ([4.5 Pihak & inventarisasi](#45-pihak--inventarisasi)).
4. Catat pengumuman ([4.6 Pengumuman](#46-pengumuman)), penilaian KJPP ([4.7 Penilaian (KJPP)](#47-penilaian-kjpp)), dan musyawarah ([4.8 Musyawarah](#48-musyawarah)).
5. Catat keberatan atau konsinyasi bila ada ([4.9 Keberatan & konsinyasi](#49-keberatan--konsinyasi)).
6. Tetapkan dan **validasi** ganti kerugian sebagai Ketua Pelaksana ([4.10 Ganti kerugian dan pembayaran](#410-ganti-kerugian-dan-pembayaran)). Pembayaran dicatat Petugas Penagihan setelah validasi.
7. Catat pelepasan hak dan penyerahan hasil ([4.11 Pelepasan hak & penyerahan hasil](#411-pelepasan-hak--penyerahan-hasil)), relokasi ([4.12 Relokasi (rumah tangga terdampak)](#412-relokasi-rumah-tangga-terdampak)), dan dokumen ([4.13 Dokumen proyek](#413-dokumen-proyek)).
8. Atur hari libur dan aturan tenggat ([4.15 Kalender & aturan tenggat](#415-kalender--aturan-tenggat)).

## Langkah kerja pengadaan tanah

<!-- sisip: 11-pengadaan-tanah.md#41-dasbor--tenggat -->

### 4.1 Dasbor & tenggat

Halaman awal peran pengadaan tanah. Menampilkan jumlah proyek per tahap, bidang per status, dan daftar **tenggat hukum** yang dihitung dalam **hari kerja** (libur nasional dan cuti bersama sudah diperhitungkan).

![Dasbor pengadaan tanah](../gambar/pengadaan/dasbor.png)

- Kolom **Status** berwarna: merah = terlambat, kuning = segera jatuh tempo, hijau = aman.
- **Sisa hari kerja** menunjukkan berapa hari kerja lagi sampai batas waktu.
- Klik nama proyek atau bidang untuk langsung membukanya.

Setiap hari kerja pukul 07.00 WIB sistem mengirim surel pengingat tenggat kepada petugas terkait.

<!-- akhir sisip -->

<!-- sisip: 11-pengadaan-tanah.md#42-daftar-proyek -->

### 4.2 Daftar proyek

Klik **☰ → Pengadaan Tanah → Proyek pengadaan**.

![Daftar proyek pengadaan](../gambar/pengadaan/daftar-proyek.png)

- Tombol **+ Proyek baru** (nomor 1) membuat proyek baru. Hanya Pelaksana dan Administrator yang melihat tombol ini.
- Tombol **Saring** (nomor 2) membuka kotak pencarian. Isi nomor atau nama proyek, tahap, status, atau kabupaten/kota, lalu klik **Cari**.
- Klik nama proyek di tabel untuk membuka halaman proyek.

Penilai dan Instansi hanya melihat proyek yang mencantumkan akunnya di **Pengguna yang ditugaskan**.

#### Membuat proyek baru

![Formulir proyek baru](../gambar/pengadaan/proyek-baru.png)

1. Klik **+ Proyek baru**. Jendela **Proyek pengadaan baru** terbuka.
2. Isi **Nama** proyek (nomor 1). Wajib.
3. Isi **Instansi yang memerlukan tanah** (nomor 2). Wajib.
4. Isi **Perkiraan kebutuhan lahan (m²)** (nomor 3) dan **Tanggal mulai** (nomor 4).
5. Lengkapi kolom lain bila datanya ada: jenis pengadaan, kategori peruntukan, narahubung instansi, sumber dana, prioritas, kabupaten/kota, kantor pertanahan pelaksana, perkiraan anggaran, target tanggal selesai, uraian lokasi, dan uraian.
6. Klik **Buat proyek** (nomor 5).

Hasilnya: nomor proyek (misalnya `PT-2026-0001`) dibuat otomatis, dan halaman proyek langsung terbuka dengan daftar tonggak tahapan standar.

<!-- akhir sisip -->

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

<!-- sisip: 11-pengadaan-tanah.md#44-bidang--peta -->

### 4.4 Bidang & peta

![Tab Bidang & peta](../gambar/pengadaan/tab-02.png)

Peta menampilkan batas setiap bidang dengan warna sesuai status (teridentifikasi, terinventarisasi, keberatan di pengadilan, ganti kerugian, diserahkan, dikeluarkan dari pengadaan). Tabel di bawah peta berisi nomor bidang, NIB, desa/kelurahan, jenis hak, pihak yang berhak, luas terkena, dan status.

#### Menambah bidang

![Tambah bidang](../gambar/pengadaan/form-bidang.png)

1. Klik **+ Tambah bidang**.
2. Isi **Nomor bidang** (nomor 1). Wajib, dan tidak boleh sama dengan bidang lain di proyek ini.
3. Pilih **Jenis hak** (nomor 2), misalnya Hak Milik (SHM) atau HGB.
4. Isi **Luas terkena (m²)** (nomor 3), yaitu bagian bidang yang terkena proyek.
5. Uraikan **Bangunan** (nomor 4) yang berdiri di atas tanah. Dengan cara yang sama, uraikan **Tanaman** dan **Benda lain yang berkaitan dengan tanah** di kolom bawahnya.
6. Centang **Bersengketa** (nomor 5) bila kepemilikan bidang sedang disengketakan. Centang **Dikeluarkan dari pengadaan** bila bidang batal dibebaskan.
7. Bila datanya ada, lengkapi NIB, kecamatan, desa/kelurahan, alamat, nomor sertipikat, penggunaan tanah, luas ukur, dan luas bangunan.
8. Klik **Simpan** (nomor 6).

Batas bidang di peta diisi dengan mengimpor berkas peta (lihat di bawah).

#### Mengimpor batas bidang dari berkas peta

![Impor peta bidang](../gambar/pengadaan/form-impor-bidang.png)

1. Klik **Impor GeoJSON/SHP** di atas tabel bidang.
2. Klik **Pilih File** pada **Berkas** (nomor 1), lalu pilih berkas peta hasil ukur. Jenis yang diterima: GeoJSON, KML/KMZ (dari Google Earth), atau shapefile yang dikemas dalam satu berkas .zip beserta berkas .prj-nya.
3. Di **Atribut nomor bidang** (nomor 2), tulis nama kolom pada berkas yang berisi nomor bidang. Isian awalnya `parcel_number`; ubah bila nama kolom di berkas Anda berbeda.
4. Bila berkas punya kolom luas, tulis namanya di **Atribut luas (opsional)** (nomor 3).
5. Klik **Impor** (nomor 4).

Hasilnya: bidang yang nomornya sudah ada diperbarui batasnya, sedangkan nomor baru ditambahkan sebagai bidang baru. Koordinat diubah otomatis ke WGS84.

#### Halaman bidang

Klik nomor bidang di tabel untuk membuka halaman bidang. Halaman ini memuat data bidang, peta, pihak yang berhak, inventarisasi, **objek inventarisasi** (rincian bangunan, tanaman, kolam, dan lain-lain beserta pemiliknya), penilaian, dan ganti kerugian khusus bidang itu.

![Halaman bidang](../gambar/pengadaan/bidang-detail.png)

Dari halaman ini Anda bisa langsung memakai tombol **Ubah data bidang**, **+ Tambah pihak**, **+ Tambah survei**, **+ Tambah objek**, dan **+ Tambah penilaian**. Formulirnya sama dengan formulir di tab proyek, dengan **Bidang tanah** yang sudah terisi.

<!-- akhir sisip -->

<!-- sisip: 11-pengadaan-tanah.md#45-pihak--inventarisasi -->

### 4.5 Pihak & inventarisasi

![Tab Pihak & inventarisasi](../gambar/pengadaan/tab-03.png)

#### Menambah pihak yang berhak

![Tambah pihak](../gambar/pengadaan/form-pihak.png)

1. Klik **+ Tambah pihak**.
2. Pilih **Bidang tanah** (nomor 1) milik pihak ini. Wajib.
3. Pilih **Peran** (nomor 2): pemilik, ahli waris, penggarap, dan sebagainya. Di sebelahnya, pilih **Jenis pihak**: perorangan, badan hukum, instansi pemerintah, masyarakat hukum adat, atau pengelola wakaf (nazhir).
4. Isi **Nama** lengkap (nomor 3). Wajib.
5. Isi **Nomor Induk Kependudukan (NIK)** (nomor 4) sesuai KTP.
6. Isi **Porsi (%)** (nomor 5), yaitu bagian hak pihak ini atas bidang. Contoh: dua ahli waris dengan bagian sama masing-masing 50.
7. Isi **Nama bank** (nomor 6), lalu nomor rekening bank dan nama pemilik rekening di sebelahnya. Data ini dipakai saat pembayaran ganti kerugian.
8. Bila ada, lengkapi NPWP, telepon, surel, alamat, dan catatan.
9. Klik **Simpan** (nomor 7).

> NIK dan nomor rekening disimpan terenkripsi. Peran yang tidak berhak melihatnya (misalnya Penilai, Penelusur, dan peran sewa) melihat data ini tersamar.

#### Mencatat inventarisasi (Satgas A/B)

![Tambah survei inventarisasi](../gambar/pengadaan/form-survei.png)

1. Klik **+ Tambah survei**.
2. Pilih **Bidang tanah** (nomor 1) yang disurvei.
3. Pilih **Jenis survei** (nomor 2): inventarisasi fisik (Satgas A) atau identifikasi yuridis (Satgas B).
4. Pilih **Status** (nomor 3): dijadwalkan, selesai, atau perlu verifikasi.
5. Isi koordinat lokasi: **Lintang** (nomor 4) dan **Bujur** di sebelahnya, dalam derajat desimal (contoh: lintang `0.9876`, bujur `104.1234`).
6. Tulis hasil pemeriksaan di **Temuan** (nomor 5).
7. Bila ada, isi tanggal survei, nama Satgas, dan petugas survei.
8. Klik **Simpan** (nomor 6).

<!-- akhir sisip -->

<!-- sisip: 11-pengadaan-tanah.md#46-pengumuman -->

### 4.6 Pengumuman

![Tambah pengumuman](../gambar/pengadaan/form-pengumuman.png)

1. Buka tab **Pengumuman**, lalu klik **+ Tambah pengumuman**.
2. Pilih **Jenis pengumuman** (nomor 1): pemberitahuan rencana pembangunan, penetapan lokasi, hasil inventarisasi (peta bidang dan daftar nominatif), hasil penilaian, atau lainnya.
3. Isi **Diumumkan pada** (nomor 2), yaitu tanggal pengumuman ditempel atau diterbitkan.
4. Bila ada, isi tempat pengumuman, nomor dokumen, dan catatan.
5. Klik **Simpan** (nomor 3).

Hasilnya: sistem menghitung **masa pengumuman** dan **batas keberatan** dalam hari kerja, lalu menambahkannya ke tab **Tenggat**.

<!-- akhir sisip -->

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

<!-- sisip: 11-pengadaan-tanah.md#48-musyawarah -->

### 4.8 Musyawarah

![Tab Musyawarah](../gambar/pengadaan/tab-06.png)

**Langkah 1: catat pelaksanaan musyawarah**

![Tambah musyawarah](../gambar/pengadaan/form-musyawarah.png)

1. Klik **+ Tambah musyawarah**.
2. Isi **Dilaksanakan pada** (nomor 1), yaitu tanggal musyawarah. Wajib.
3. Isi **Nomor berita acara** (nomor 2). Bila ada, isi juga lokasi, pemimpin musyawarah (**Dipimpin oleh**), dan catatan.
4. Klik **Simpan** (nomor 3).

**Langkah 2: catat hasil untuk setiap pihak**

Ulangi langkah ini untuk setiap pihak yang ikut musyawarah.

![Tambah hasil musyawarah](../gambar/pengadaan/form-hasil-musyawarah.png)

1. Klik **+ Tambah hasil musyawarah**.
2. Pilih **Musyawarah** (nomor 1) yang dicatat pada langkah 1.
3. Pilih **Bidang tanah** (nomor 2) dan **Pihak yang berhak** (nomor 3).
4. Pilih **Hasil** (nomor 4): sepakat, menolak, tidak hadir, atau ditunda.
5. Bila sepakat, isi **Nilai disepakati (Rp)** (nomor 5) dan pilih **Bentuk ganti kerugian** di sebelahnya: uang, tanah pengganti, permukiman kembali, kepemilikan saham, atau bentuk lain yang disepakati.
6. Isi tanggal **Berita acara ditandatangani pada**.
7. Klik **Simpan** (nomor 6).

Bila hasilnya **menolak**, sistem menghitung **batas keberatan ke Pengadilan Negeri** dan menambahkannya ke tab **Tenggat**.

<!-- akhir sisip -->

<!-- sisip: 11-pengadaan-tanah.md#49-keberatan--konsinyasi -->

### 4.9 Keberatan & konsinyasi

*Peran: Ahli Hukum Penagihan, Pelaksana, Administrator.*

![Tab Keberatan & konsinyasi](../gambar/pengadaan/tab-07.png)

**Mencatat keberatan, gugatan, atau kasasi**

![Tambah keberatan](../gambar/pengadaan/form-keberatan.png)

1. Klik **+ Tambah keberatan**.
2. Pilih **Jenis** (nomor 1): keberatan rencana lokasi, gugatan PTUN, keberatan hasil inventarisasi, keberatan ganti kerugian ke Pengadilan Negeri, kasasi ke Mahkamah Agung, sengketa kepemilikan, atau perkara lain.
3. Pilih **Status** (nomor 2): diajukan, diproses, dikabulkan, atau ditolak.
4. Pilih **Bidang tanah** (nomor 3), lalu **Pihak yang berhak** di bawahnya.
5. Isi **Nomor perkara** (nomor 4) beserta nama pengadilan, tanggal diajukan, tanggal diterima pengadilan, dan tanggal diputus.
6. Bila sudah diputus, isi **Nilai ganti kerugian yang diputus (Rp)** (nomor 5) dan **Ringkasan putusan**.
7. Untuk kasasi, pilih perkara tingkat sebelumnya di **Instansi sebelumnya**.
8. Klik **Simpan** (nomor 6).

Batas putusan dan batas kasasi dihitung otomatis dan masuk ke tab **Tenggat**.

**Mencatat penitipan ganti kerugian di pengadilan (konsinyasi)**

![Tambah konsinyasi](../gambar/pengadaan/form-konsinyasi.png)

1. Klik **+ Tambah konsinyasi**.
2. Pilih **Bidang tanah** (nomor 1), lalu pihak yang berhak di sebelahnya.
3. Pilih **Alasan** (nomor 2): pihak menolak, keberadaan tidak diketahui, sengketa kepemilikan, sedang berperkara, disita, atau menjadi jaminan bank.
4. Pilih **Status** (nomor 3): diajukan ke pengadilan, dititipkan, atau diambil pihak yang berhak.
5. Isi **Jumlah (Rp)** (nomor 4) yang dititipkan.
6. Bila ada, isi Pengadilan Negeri, tanggal permohonan, nomor dan tanggal penetapan, tanggal dititipkan, dan tanggal diambil pihak yang berhak.
7. Klik **Simpan** (nomor 5).

<!-- akhir sisip -->

<!-- sisip: 11-pengadaan-tanah.md#410-ganti-kerugian-dan-pembayaran -->

### 4.10 Ganti kerugian dan pembayaran

Urutannya selalu: **tetapkan** ganti kerugian, lalu **validasi**, lalu **catat pembayaran**.

![Tab Ganti kerugian](../gambar/pengadaan/tab-08.png)

**Langkah 1: tetapkan ganti kerugian** (Pelaksana, Administrator)

![Tambah ganti kerugian](../gambar/pengadaan/form-ganti-kerugian.png)

1. Klik **+ Tambah ganti kerugian**.
2. Pilih **Bidang tanah** (nomor 1) dan **Pihak yang berhak** (nomor 2).
3. Pilih **Bentuk ganti kerugian** (nomor 3), misalnya uang.
4. Isi **Jumlah (Rp)** (nomor 4).
5. Pilih dasar penetapannya: **Penilaian** (nomor 5), atau **Hasil musyawarah**, atau **Putusan pengadilan** di sebelahnya.
6. Untuk bentuk selain uang, uraikan di **Uraian ganti kerugian nonuang**.
7. Klik **Simpan** (nomor 6). Status baris menjadi **Ditetapkan**.

**Langkah 2: validasi** (Ketua Pelaksana dengan peran Pelaksana Pengadaan, Administrator)

![Validasi ganti kerugian](../gambar/pengadaan/validasi.png)

1. Cari baris berstatus **Ditetapkan**, lalu klik **Validasi** (nomor 1) pada baris itu.
2. Klik **OK** pada pertanyaan konfirmasi. Status menjadi **Divalidasi Ketua Pelaksana** dan nama Anda tercatat di kolom **Divalidasi oleh**.
3. Bila penetapan salah dan harus dibatalkan, klik **Batalkan** (nomor 2) pada barisnya. Tombol ini hanya tampil selama belum ada pembayaran untuk baris itu.

**Langkah 3: catat pembayaran** (Petugas Penagihan, Pelaksana, Administrator). Hanya bisa untuk ganti kerugian yang sudah divalidasi.

![Tambah pembayaran](../gambar/pengadaan/form-pembayaran.png)

1. Gulir ke bagian **Pembayaran**, lalu klik **+ Tambah pembayaran** (nomor 3 pada gambar validasi).
2. Pilih **Ganti kerugian** (nomor 1) yang dibayar.
3. Isi **Dibayar pada** (nomor 2), yaitu tanggal transfer atau penyerahan uang.
4. Isi **Jumlah (Rp)** (nomor 3) yang dibayar kali ini. Pembayaran boleh dicicil; setiap cicilan dicatat sebagai satu pembayaran.
5. Pilih **Metode pembayaran** (nomor 4), lalu bila ada isi referensi bank, penerima, dan catatan.
6. Klik **Simpan** (nomor 5).

Hasilnya: kolom **Dibayar** dan **Sisa** di tabel ganti kerugian diperbarui. Bila sisa menjadi Rp 0, status berubah menjadi **Dibayar**.

<!-- akhir sisip -->

<!-- sisip: 11-pengadaan-tanah.md#411-pelepasan-hak--penyerahan-hasil -->

### 4.11 Pelepasan hak & penyerahan hasil

![Tab Pelepasan & penyerahan](../gambar/pengadaan/tab-09.png)

**Mencatat pelepasan hak**

![Tambah pelepasan hak](../gambar/pengadaan/form-pelepasan.png)

1. Klik **+ Tambah pelepasan hak**.
2. Pilih **Bidang tanah** (nomor 1) dan **Pihak yang berhak** (nomor 2), lalu isi nomor berita acara di sebelahnya.
3. Isi **Dilepaskan pada** (nomor 3), yaitu tanggal berita acara pelepasan. Wajib.
4. Centang **Asli sertipikat/alas hak diserahkan** (nomor 4) bila dokumen asli sudah diterima.
5. Klik **Simpan** (nomor 5). Sistem menghitung **batas penyerahan hasil**.

**Menyerahkan hasil pengadaan kepada instansi**

![Tambah penyerahan hasil](../gambar/pengadaan/form-penyerahan.png)

1. Klik **+ Tambah penyerahan hasil**.
2. Isi **Nomor berita acara serah terima (BAST)** (nomor 1).
3. Isi **Diserahkan pada** (nomor 2) dan **Penerima** (nomor 3). Keduanya wajib.
4. Di **Bidang tanah** (nomor 4), klik bidang yang diserahkan. Untuk memilih lebih dari satu, tahan tombol **Ctrl** (atau **Cmd** di Mac) sambil mengklik.
5. Bila ada, isi tanggal pendaftaran tanah diajukan dan nomor pendaftaran/sertipikat.
6. Klik **Simpan** (nomor 5).

<!-- akhir sisip -->

<!-- sisip: 11-pengadaan-tanah.md#412-relokasi-rumah-tangga-terdampak -->

### 4.12 Relokasi (rumah tangga terdampak)

![Tambah rumah tangga terdampak](../gambar/pengadaan/form-rumah-tangga.png)

1. Buka tab **Relokasi**, lalu klik **+ Tambah rumah tangga**.
2. Pilih **Bidang tanah** (nomor 1) tempat rumah tangga itu tinggal.
3. Isi nama **Kepala keluarga** (nomor 2). Wajib.
4. Isi **Nomor Induk Kependudukan (NIK)** (nomor 3) kepala keluarga, lalu nomor KK dan jumlah anggota keluarga.
5. Pilih **Dampak relokasi** (nomor 4): tidak terdampak, terdampak sebagian, atau terdampak penuh. Lalu pilih **Tahap** relokasinya.
6. Isi **Kemajuan (%)** (nomor 5): angka 0 sampai 100 yang menunjukkan sejauh mana relokasi sudah berjalan.
7. Bila ada, isi bantuan uang (Rp), bantuan yang diberikan, dan catatan.
8. Klik **Simpan** (nomor 6).

<!-- akhir sisip -->

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

<!-- sisip: 11-pengadaan-tanah.md#414-tenggat-proyek -->

### 4.14 Tenggat proyek

Tab **Tenggat** berisi semua tenggat hukum proyek ini: kewajiban, batas waktu, sisa hari kerja, bidang, dan referensi dasar hukumnya.

![Tab Tenggat](../gambar/pengadaan/tab-12.png)

<!-- akhir sisip -->

<!-- sisip: 11-pengadaan-tanah.md#415-kalender--aturan-tenggat -->

### 4.15 Kalender & aturan tenggat

*Mengubah: Pelaksana Pengadaan, Administrator. Peran lain hanya melihat.*

![Kalender & aturan tenggat](../gambar/pengadaan/pengaturan.png)

- **Kalkulator hari kerja**: isi tanggal awal dan jumlah hari kerja, lalu klik **Hitung** (nomor 1). Tanggal jatuh tempo tampil di sebelahnya.
- **Aturan tenggat**: jangka waktu setiap kewajiban beserta dasar hukumnya. Klik **Ubah** pada baris untuk menyesuaikan.
- **Hari libur & cuti bersama**: daftar libur yang tidak dihitung sebagai hari kerja.

![Hari libur](../gambar/pengadaan/pengaturan-libur.png)

**Menambah hari libur** (lakukan setiap tahun sesuai SKB 3 Menteri):

1. Gulir ke bagian **Hari libur & cuti bersama**, lalu klik **+ Tambah hari libur** (nomor 1).
2. Isi **Tanggal** dan **Nama** liburnya (misalnya "Hari Raya Idulfitri"). Centang **Cuti bersama** bila tanggal itu cuti bersama, bukan libur nasional.
3. Klik **Simpan**.
4. Ulangi untuk setiap tanggal libur.
5. Untuk menghapus libur yang salah, klik **Hapus** pada barisnya.

<!-- akhir sisip -->

<!-- sisip: 11-pengadaan-tanah.md#416-perbedaan-tampilan-per-peran -->

### 4.16 Perbedaan tampilan per peran

**Penilai** melihat tombol **+ Tambah penilaian** dan **Ubah** di tab Penilaian, tetapi data pihak (NIK, rekening) tersamar dan tidak ada tombol ubah di tab lain:

![Tab Penilaian bagi Penilai](../gambar/pengadaan/penilai-penilaian.png)

**Instansi** melihat ringkasan proyek, bidang, pengumuman, musyawarah, penyerahan hasil, dan tenggat. Tab berisi data pihak, penilaian, dan ganti kerugian menampilkan "Anda tidak berwenang melihat data ini". Instansi bisa menambah dokumen:

![Dokumen bagi Instansi](../gambar/pengadaan/instansi-dokumen.png)

**Petugas Penagihan** hanya bisa menambah pembayaran di tab Ganti kerugian:

![Ganti kerugian bagi Petugas Penagihan](../gambar/pengadaan/penagihan-ganti-kerugian.png)

**Ahli Hukum Penagihan** menambah keberatan dan konsinyasi:

![Keberatan bagi Ahli Hukum](../gambar/pengadaan/ahlihukum-keberatan.png)

**Satgas** menambah pihak dan survei, tetapi tidak memvalidasi ganti kerugian:

![Pihak bagi Satgas](../gambar/pengadaan/satgas-pihak.png)

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
