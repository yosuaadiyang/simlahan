# Buku peran: Petugas Penagihan

Buku ini untuk **Petugas Penagihan**: petugas yang mengelola tagihan dan pembayaran sewa, serta mencatat pembayaran ganti kerugian pengadaan tanah. Buku ini berisi semua langkah kerja peran Anda, lengkap dengan gambar, sehingga cukup dibaca sendiri. Dasar penggunaan yang berlaku untuk semua peran (mengenal layar, ganti sandi, memakai di HP) ada di [Bab 2](../02-dasar-penggunaan.md).

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

Setelah masuk, Anda langsung melihat daftar **Sewa**:

![Halaman awal Petugas Penagihan](../gambar/peran/penagihan-beranda.png)

Nomor pada gambar:

1. **☰ Menu**: membuka menu samping berisi semua halaman yang boleh Anda buka.
2. **Cari dengan kata kunci**: ketik pengenal sewa, nama penyewa, atau alamat, lalu tekan Enter.
3. **Tabel** / **Peta**: ganti tampilan hasil menjadi tabel atau peta.
4. **Pengenal sewa** (misalnya *L1217108-1*): klik untuk membuka halaman sewa itu.
5. **Nama Anda**: membuka menu akun (**Panduan peran**, **Ganti sandi**, unit layanan).
6. **Keluar**: mengakhiri sesi di perangkat ini.

### Menu Anda

Klik **☰** (nomor 1 pada gambar halaman awal) untuk membuka menu:

![Menu Petugas Penagihan](../gambar/peran/penagihan-menu.png)

Menu Anda: **Sewa**, **Pengadaan Tanah ›**, **Kontak**, **Catatan area**, **Prinsip sewa**, **Statistik dan laporan**, **Kompensasi pembangunan sisipan**, **Pencarian area**, dan **Lainnya ›** (termasuk **Catatan tagihan**).

<!-- awal: dibuat dari backend/users/role_guide.py; perbarui dengan: cd backend && python manage.py panduan_buku -->

## Ringkasan peran

Mengelola tagihan sewa dan pembayaran ganti kerugian pengadaan tanah.

- **Cara masuk:** Alamat utama SimLahan (`/`), dengan nama pengguna dan sandi.
- **Halaman awal:** Sewa (daftar sewa).
- **Akun latihan** (hanya di sistem latihan berisi data contoh): `contoh.penagihan`

### Menu yang Anda lihat

- Sewa
- Pengadaan Tanah: Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat
- Kontak
- Catatan area
- Prinsip sewa
- Statistik dan laporan
- Kompensasi pembangunan sisipan
- Pencarian area
- Lainnya: Indeks biaya hidup, Tugas terjadwal, Catatan tagihan

### Yang bisa Anda lakukan

- Membuat dan mengubah tagihan, baris dan set tagihan, pembayaran, catatan tagihan, jatuh tempo sewa, jaminan, dan kontak penyewa.
- Membuat laporan tagihan dan pembayaran.
- Pengadaan tanah: mencatat pembayaran dan penyerahan ganti kerugian yang sudah divalidasi (data pribadi tersamar).

### Batas akses

- Tidak mengubah isi sewa, kontrak, atau keputusan.
- Tidak bisa membuka panel admin, alokasi lahan, manajemen aset lahan, pusat komando, atau aplikasi lapangan.

<!-- akhir: blok role_guide.py -->

## Urutan kerja Anda

1. Buka sewa, lalu tab **Penagihan** ([3.4 Penagihan sewa](#34-penagihan-sewa)): buat tagihan manual, catat pembayaran, kreditkan atau hapus tagihan yang salah, dan hentikan atau jalankan penagihan otomatis.
2. Perbarui jatuh tempo sewa (tab **Sewa**) dan jaminan (tab **Keputusan dan kontrak**) bila perlu ([3.3 Halaman data sewa](#33-halaman-data-sewa)).
3. Isi **Catatan tagihan** di menu **Lainnya** ([3.11 Menu "Lainnya"](#311-menu-lainnya)).
4. Untuk pengadaan tanah, catat pembayaran ganti kerugian yang sudah divalidasi ([4.10 Ganti kerugian dan pembayaran](#410-ganti-kerugian-dan-pembayaran)).
5. Buat laporan tagihan dan pembayaran di **Statistik dan laporan** ([3.8 Statistik dan laporan](#38-statistik-dan-laporan)).

## Bagian A – Tagihan dan pembayaran sewa

<!-- sisip: 10-sewa.md#31-daftar-sewa -->

### 3.1 Daftar sewa

Halaman **Sewa** adalah halaman awal peran sewa.

![Daftar sewa](../gambar/sewa/daftar-sewa.png)

Nomor pada gambar:

1. **Buat pengenal sewa**: membuat sewa baru (lihat 3.2).
2. **Cari dengan kata kunci**: ketik pengenal sewa, nama penyewa, alamat, atau pengenal objek, lalu tekan Enter.
3. **Objek**, **Masa berlaku**, **Keputusan dan kontrak**, **Kontak**: klik salah satu untuk membuka kolom pencarian tambahan.
4. **Saringan**: Unit layanan, Jenis, Penyiap, dan Persiapan belum selesai. Klik kotak lalu pilih isinya.
5. **Peta**: mengganti tampilan daftar menjadi peta lokasi sewa. Klik **Tabel** untuk kembali.
6. **Kosongkan pencarian**: menghapus semua kata kunci dan saringan.

Klik **pengenal sewa** (misalnya `L1217108-1`) untuk membuka datanya. Tanda **˅** di awal baris menampilkan sewa lain yang terkait. Angka bulat di kolom Penyewa menunjukkan jumlah penyewa.

Tampilan peta:

![Daftar sewa dalam tampilan peta](../gambar/sewa/daftar-sewa-peta.png)

<!-- akhir sisip -->

<!-- sisip: 10-sewa.md#33-halaman-data-sewa -->

### 3.3 Halaman data sewa

Di bagian atas tampak ringkasan: pengenal sewa, jenis, tanggal mulai/akhir, kondisi, pengenal objek, dan alamat. Di bawahnya ada sembilan tab.

![Ringkasan sewa](../gambar/sewa/sewa-tab-ringkasan.png)

1. **Tab** (nomor 1): klik untuk berpindah bagian.
2. **Ubah** (nomor 2): masuk mode ubah untuk tab yang sedang dibuka.

#### Mengubah data sewa

![Mode ubah](../gambar/sewa/sewa-mode-ubah.png)

1. Buka tab yang akan diubah, lalu klik **Ubah** di kanan atas.
2. Ubah isian. Kolom bertanda **\*** wajib diisi.
3. Klik **Simpan** (nomor 1). Klik **Batalkan perubahan** (nomor 2) bila tidak jadi.
4. Tombol merah **Hapus** menghapus seluruh sewa (hanya untuk sewa yang belum berjalan dan bila Anda berhak).

#### Isi setiap tab

| Tab | Isi dan kegunaan |
|---|---|
| **Ringkasan** | Data dasar: jenis, tanggal, pemberi sewa, penyiap, peruntukan, bentuk pembiayaan/pengelolaan, masa pemberitahuan, nomor kontrak, wajib PPN, catatan. Kolom kanan **Pohon riwayat** menunjukkan sewa sebelumnya/berikutnya; tautkan sewa lain di **Kaitkan ke pengenal sewa**. |
| **Area sewa** | Objek yang disewa: pengenal objek, definisi, luas, lokasi, alamat, bidang tanah, unit rencana, rencana detail. Tombol **Tambah objek**, **Tambah alamat**, **Tambah bidang tanah**, **Tambah unit rencana**, dan **Salin ke kontrak**. |
| **Penyewa** | Siapa penyewanya, porsi bagian sewa (misalnya 1/2), penagih/kontak lain, dan masa berlakunya. Penyewa dipilih dari data **Kontak**. |
| **Sewa** | Jenis sewa (tetap/indeks), tanggal, pembagian tagihan, jatuh tempo, sewa kontrak per peruntukan, potongan dan kenaikan. **Perhitungan sewa**: pilih tahun atau periode tagihan lalu klik **Hitung** untuk melihat total terutang. Ada juga **Kalkulator sewa** di bawahnya. |
| **Keputusan dan kontrak** | Keputusan beserta syarat-syaratnya, kontrak dan perubahannya, jaminan, serta **Pemeriksaan dan catatan** (inspeksi). |
| **Kelayakan bangun** | Status kelayakan bangun/konstruksi lahan; tombol **Kirim email** untuk mengirim informasi kepada pihak terkait. |
| **Penagihan** | Daftar tagihan per periode, pembayaran, dan penagihan hukum (lihat 3.4). |
| **Peta** | Lokasi area sewa di peta. |
| **Riwayat perubahan** | Siapa mengubah apa: tanggal, nama, jenis perubahan, nilai lama dan baru. |

![Tab Area sewa dalam mode ubah](../gambar/sewa/sewa-area-ubah.png)

![Tab Sewa dan perhitungan sewa](../gambar/sewa/sewa-tab-sewa.png)

![Tab Keputusan dan kontrak](../gambar/sewa/sewa-tab-keputusan-dan-kontrak.png)

<!-- akhir sisip -->

<!-- sisip: 10-sewa.md#34-penagihan-sewa -->

### 3.4 Penagihan sewa

*Peran: Petugas Penagihan dan Administrator mengelola tagihan; Ahli Hukum Penagihan mengelola surat penagihan dan putusan pengadilan; peran lain hanya melihat.*

![Tab Penagihan](../gambar/sewa/sewa-tab-penagihan.png)

**Melihat tagihan.** Tabel **Tagihan** menampilkan kelompok tagihan, penerima, jatuh tempo (merah = sudah lewat), nomor, porsi, periode, jenis piutang, status, nilai ditagih, dan sisa belum dibayar. Klik baris untuk membuka rincian tagihan di sebelah kanan.

**Membuat tagihan manual**

1. Buka tab **Penagihan**, lalu klik **Buat tagihan** (nomor 2) di bawah tabel.
2. Pilih penerima, periode, jenis piutang, dan isi nilainya.
3. Klik **Simpan**. Tagihan baru muncul di tabel.

**Mencatat pembayaran**

1. Klik baris tagihan. Panel rincian tagihan terbuka.
2. Klik ikon pensil (ubah) di panel itu, lalu klik **Tambah pembayaran**.
3. Isi jumlah dan tanggal bayar, lalu klik **Simpan**. Sisa tagihan berkurang otomatis.

**Mengkreditkan atau menghapus tagihan**

1. Klik bulatan di awal baris tagihan yang salah.
2. Klik **Kreditkan tagihan** (nomor 3) atau **Hapus tagihan** (nomor 4). Kedua tombol abu-abu sampai ada tagihan yang dipilih.
3. Ikuti jendela konfirmasinya.

**Menghentikan atau menjalankan penagihan otomatis**: klik **Hentikan penagihan** (nomor 1). Tulisan **Penagihan berjalan** di sebelahnya berubah menjadi penagihan berhenti. Klik lagi tombolnya untuk menjalankan kembali.

**Penagihan hukum** (Ahli Hukum Penagihan), di bagian **Penagihan** paling bawah:

1. Di **Pembuatan surat penagihan**, pilih **Penyewa** dan **Jenis tuntutan pembayaran**, tambahkan tagihan yang dituntut dengan **Tambah tagihan**, lalu klik **Buat surat penagihan** (nomor 5).
2. Catat putusan dengan **Tambah putusan pengadilan** (nomor 6).
3. Tambahkan catatan dengan **Tambah catatan**. Bunga denda dihitung otomatis dari tagihan yang terlambat.

<!-- akhir sisip -->

> Peran Anda **tidak** mengubah isi sewa, kontrak, atau keputusan. Yang Anda ubah: tagihan, pembayaran, catatan tagihan, jatuh tempo, jaminan, dan kontak penyewa.

<!-- sisip: 10-sewa.md#35-kontak -->

### 3.5 Kontak

Kontak adalah daftar orang, badan usaha, perkumpulan, atau unit yang menjadi penyewa, pemberi sewa, atau penagih.

![Daftar kontak](../gambar/sewa/kontak-daftar.png)

- **Buat kontak** (nomor 1): menambah kontak baru.
- **Cari dengan kata kunci** (nomor 2): ketik nama, NPWP, atau nomor pelanggan.
- Saringan **Unit layanan** (nomor 3), **Pengenal sewa**, **Hanya penyewa**, atau **Hanya kontak aktif**.
- Klik baris kontak untuk melihat datanya dan **Sewa kontak** (daftar sewa yang melibatkan kontak itu, beserta tunggakan).

**Menambah kontak** (Penyusun, Operator, Penagihan, Administrator)

![Kontak baru](../gambar/sewa/kontak-baru.png)

1. Di daftar kontak, klik **Buat kontak**.
2. Pilih **Jenis kontak** (nomor 1): perorangan, badan usaha, perkumpulan, atau unit. Kolom nama dan NIK/NPWP muncul sesuai jenisnya.
3. Isi nama dan NIK/NPWP, lalu **Alamat** (nomor 2), **Nomor telepon** (nomor 3), **Email** (nomor 4), dan kolom lain yang diperlukan.
4. Klik **Simpan** (nomor 5) di kanan atas. Klik **Batalkan perubahan** (nomor 6) bila tidak jadi.

![Detail kontak](../gambar/sewa/kontak-detail.png)

<!-- akhir sisip -->

<!-- sisip: 10-sewa.md#36-catatan-area -->

### 3.6 Catatan area

Catatan area adalah catatan yang ditandai langsung di peta, misalnya "lahan rawan banjir".

![Catatan area](../gambar/sewa/catatan-area.png)

1. Buka **☰ → Catatan area**.
2. Klik **Buat catatan area** (nomor 1). Panel isian terbuka di kiri peta.
3. Gambar area di peta: klik ikon segi lima di kolom alat kanan peta, klik titik-titik batas area, lalu klik titik pertama untuk menutup bentuknya.
4. Tulis catatannya di kotak **Tulis catatan** (nomor 2).
5. Klik **Buat catatan area** (nomor 3) di bawah panel. Klik area di peta kapan saja untuk membaca atau mengubah catatannya.

<!-- akhir sisip -->

<!-- sisip: 10-sewa.md#37-prinsip-sewa-dasar-sewa -->

### 3.7 Prinsip sewa (dasar sewa)

Prinsip sewa adalah dasar penentuan tarif untuk satu objek atau kawasan.

![Daftar prinsip sewa](../gambar/sewa/prinsip-sewa-daftar.png)

1. Buka **☰ → Prinsip sewa**. Klik **Buat prinsip sewa** (nomor 1) untuk menambah, atau cari di kotak cari (nomor 2) lalu klik pengenal objek untuk membuka.
2. Isi peruntukan utama, tanggal mulai/akhir, tarif dan keputusan terkait.
3. Klik **Simpan**.

![Detail prinsip sewa](../gambar/sewa/prinsip-sewa-detail.png)

<!-- akhir sisip -->

<!-- sisip: 10-sewa.md#38-statistik-dan-laporan -->

### 3.8 Statistik dan laporan

*Peran: Penyusun, Penyusun Kontrak, Operator, Ahli Hukum Penagihan, Petugas Penagihan, Administrator (Penelusur tidak).*

![Statistik dan laporan](../gambar/sewa/laporan.png)

1. Buka **☰ → Statistik dan laporan**.
2. Pilih jenis laporan di kotak **Laporan** (nomor 1). Pada gambar dipilih **Tagihan terbuka**. Laporan yang tersedia: Tagihan terbuka, Tagihan dalam periode, Jaminan, Pembayaran tagihan, Tagihan yang dibayar kontak, Sewa dengan penagihan nonaktif, Sewa per jenis indeks, Sewa kontak, Persyaratan keputusan, Perbandingan sewa, Proyeksi sewa, Pencadangan, Laporan statistik sewa, Jumlah sewa, Penyesuaian sewa, Dasar sewa, dan Sewa per jenis sewa. Laporan tagihan hanya muncul untuk peran yang berhak.
3. Isi saringan laporan yang muncul (misalnya **Unit layanan**, **Tanggal mulai**, **Tanggal berakhir**).
4. Klik **Buat laporan** (nomor 2). Laporan kecil langsung tampil dan bisa diunduh; laporan besar dibuat di latar belakang dan dikirim ke surel Anda.

<!-- akhir sisip -->

<!-- sisip: 10-sewa.md#311-menu-lainnya -->

### 3.11 Menu "Lainnya"

Klik **☰ → Lainnya** untuk membuka empat halaman berikut. Peran yang tidak memerlukannya tidak melihat menunya.

> Di sistem latihan, tabel **Indeks biaya hidup**, **Tugas terjadwal**, dan **Pencarian kavling** tampak kosong karena data contoh belum berisi indeks, riwayat proses otomatis, atau seleksi kavling. Di sistem yang sudah berjalan, tabelnya terisi dengan kolom seperti pada gambar.

**Indeks biaya hidup**

![Indeks biaya hidup](../gambar/sewa/indeks.png)

Tabel indeks per bulan dan tahun yang dipakai untuk penyesuaian sewa berindeks. Hanya dibaca.

**Tugas terjadwal**

![Tugas terjadwal](../gambar/sewa/tugas-terjadwal.png)

Riwayat (**Eksekusi**) dan **Jadwal** proses otomatis, misalnya pembuatan tagihan dan pengingat. Hanya dibaca; mengubah jadwal hanya oleh superuser.

**Catatan tagihan**

![Catatan tagihan](../gambar/sewa/catatan-tagihan.png)

Pengumuman yang dicetak pada tagihan per sewa dan periode. Klik **Buat pengumuman** (nomor 1) untuk menambah, isi teks dan periodenya, lalu simpan.

**Kalkulator sewa**

![Kalkulator sewa](../gambar/sewa/kalkulator-sewa.png)

Menghitung perkiraan sewa tanpa menyimpan ke data sewa.

1. Pilih **Jenis kalkulator** (nomor 1).
2. Isi nilai yang muncul. Hasilnya langsung tampil.
3. Klik **Tambah kalkulator sewa** (nomor 2) bila ingin menambah perhitungan kedua untuk dibandingkan.

<!-- akhir sisip -->

<!-- sisip: 10-sewa.md#312-pertanyaan-umum -->

### 3.12 Pertanyaan umum

**Tombol Ubah abu-abu/tidak bisa diklik.** Bagian itu bukan tugas peran Anda, atau data sedang dikunci karena sudah final. Tanyakan kepada petugas yang berwenang.

**Sewa tidak ditemukan.** Periksa saringan **Unit layanan**; data sewa dibatasi per unit. Klik **Kosongkan pencarian** lalu cari lagi.

**Perubahan tidak tersimpan.** Pastikan Anda menekan **Simpan** sebelum pindah tab. Kolom wajib (tanda \*) yang kosong menyebabkan simpan gagal; periksa tulisan merah di bawah kolom.

<!-- akhir sisip -->

## Bagian B – Pembayaran ganti kerugian pengadaan tanah

Anda mencatat pembayaran setelah ganti kerugian **divalidasi** Ketua Pelaksana. Data pribadi pihak tampil tersamar.

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

## Bila ada kendala

- **Menu atau tombol yang disebut di buku ini tidak ada di layar Anda.** Peran Anda memang tidak memerlukannya (lihat **Batas akses** di atas). Bila Anda membutuhkannya untuk pekerjaan, minta Administrator menambahkan peran yang sesuai.
- **Pesan "Tidak berhak" atau "Anda tidak berwenang melihat data ini".** Data itu di luar hak peran Anda, bukan kerusakan sistem.
- **Lupa kata sandi.** Hubungi superuser SimLahan untuk dibuatkan sandi baru, lalu ganti sandi itu setelah masuk (klik nama Anda → **Ganti sandi**, atau buka `/akun/sandi/`).
- **Terlalu banyak percobaan masuk.** Tunggu beberapa menit, lalu coba lagi dengan sandi yang benar.
- **Ringkasan peran di dalam aplikasi.** Isi bagian *Ringkasan peran* di atas juga bisa dibuka kapan saja lewat **Panduan peran** (`/akun/panduan/`).
