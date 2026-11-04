# Buku peran: Instansi Yang Memerlukan Tanah

Buku ini untuk **Instansi Yang Memerlukan Tanah**: instansi pemilik kebutuhan tanah yang memantau proyeknya. Baca dulu [Bab 1](../01-mengenal-simlahan.md) dan [Bab 2](../02-dasar-penggunaan.md) bila baru pertama kali memakai SimLahan.

## Masuk

Buka alamat SimLahan, isi nama pengguna dan kata sandi, lalu klik **Masuk** ([Bab 2.2](../02-dasar-penggunaan.md#a-aplikasi-utama-petugas-kantor)).

![Halaman awal Instansi](../gambar/peran/instansi-beranda.png)

<!-- awal: dibuat dari backend/users/role_guide.py; perbarui dengan: cd backend && python manage.py panduan_buku -->

## Ringkasan peran

Memantau proyek pengadaan milik instansinya.

- **Cara masuk:** Alamat utama SimLahan (`/`), dengan nama pengguna dan sandi.
- **Halaman awal:** Pengadaan Tanah → Dasbor & tenggat.
- **Akun latihan** (hanya di sistem latihan berisi data contoh): `contoh.instansi`

### Menu yang Anda lihat

- Pengadaan Tanah: Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat

### Yang bisa Anda lakukan

- Membaca proyek, bidang, pengumuman, musyawarah, dan penyerahan.
- Mengunggah dokumen perencanaan (DPPT, studi kelayakan), BAST, foto, dan dokumen lain.

### Batas akses

- Hanya proyek yang mencantumkan akunnya di **Pengguna yang ditugaskan**; tanpa nilai uang dan tanpa data pihak.
- Hanya modul pengadaan tanah; modul sewa, alokasi, aset, pusat komando, dan panel admin tidak terbuka.

<!-- akhir: blok role_guide.py -->

![Menu Instansi](../gambar/peran/instansi-menu.png)

## Pekerjaan sehari-hari

### 1. Memantau proyek

1. Buka **Proyek pengadaan**. Anda hanya melihat proyek yang menugaskan instansi Anda ([Bab 4.2](../11-pengadaan-tanah.md#42-daftar-proyek)).
2. Ringkasan tampil tanpa nilai uang dan tanpa data pihak.

![Ringkasan proyek untuk Instansi](../gambar/pengadaan/instansi-ringkasan.png)

### 2. Mengunggah dokumen

1. Di tab **Dokumen**, klik **+ Tambah**, pilih jenis (DPPT, studi kelayakan, BAST, foto, dsb.), unggah berkas, lalu simpan ([Bab 4.13](../11-pengadaan-tanah.md#413-dokumen-proyek)).

![Formulir Tambah dokumen](../gambar/pengadaan/instansi-form-dokumen.png)

## Bab yang perlu dibaca

- [Bab 1 – Mengenal SimLahan](../01-mengenal-simlahan.md)
- [Bab 2 – Dasar penggunaan](../02-dasar-penggunaan.md)
- [Bab 4 – Pengadaan tanah](../11-pengadaan-tanah.md)

## Bila ada kendala

- Menu atau tombol tidak ada: peran Anda memang tidak memerlukannya ([Bab 2.10](../02-dasar-penggunaan.md#210-batas-akses-dan-pesan-tidak-berhak)). Hubungi Administrator bila Anda memerlukannya untuk pekerjaan.
- Lupa kata sandi: hubungi Administrator atau superuser untuk menyetel ulang sandi.
- Ringkasan peran yang sama bisa dibuka di dalam aplikasi lewat **Panduan peran** (`/akun/panduan/`).
