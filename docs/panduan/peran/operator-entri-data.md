# Buku peran: Operator Entri Data

Buku ini untuk **Operator Entri Data**: petugas yang memasukkan dan memperbarui hampir semua data sewa, termasuk keputusan dan besaran sewa. Baca dulu [Bab 1](../01-mengenal-simlahan.md) dan [Bab 2](../02-dasar-penggunaan.md) bila baru pertama kali memakai SimLahan.

## Masuk

Buka alamat SimLahan, isi nama pengguna dan kata sandi, lalu klik **Masuk** ([Bab 2.2](../02-dasar-penggunaan.md#a-aplikasi-utama-petugas-kantor)).

![Halaman awal Operator Entri Data](../gambar/peran/operator-beranda.png)

<!-- awal: dibuat dari backend/users/role_guide.py; perbarui dengan: cd backend && python manage.py panduan_buku -->

## Ringkasan peran

Memasukkan dan memperbarui data sewa secara lengkap.

- **Cara masuk:** Alamat utama SimLahan (`/`), dengan nama pengguna dan sandi.
- **Halaman awal:** Sewa (daftar sewa).
- **Akun latihan** (hanya di sistem latihan berisi data contoh): `contoh.operator`

### Menu yang Anda lihat

- Sewa
- Pengadaan Tanah: Dasbor & tenggat, Proyek pengadaan, Kalender & aturan tenggat
- Kontak
- Catatan area
- Prinsip sewa
- Statistik dan laporan
- Kompensasi pembangunan sisipan
- Pencarian area
- Lainnya: Indeks biaya hidup, Tugas terjadwal, Catatan tagihan, Kalkulator sewa

### Yang bisa Anda lakukan

- Membuat dan mengubah sewa, penyewa, kontrak dan perubahannya, keputusan dan syaratnya, besaran sewa dan jatuh tempo, dasar sewa beserta tarif dan keputusannya, inspeksi, kontak, dan catatan area.
- Membuat laporan sewa.
- Mengelola pencarian kavling/area dan formulirnya.

### Batas akses

- Tidak mengelola tagihan, pembayaran, atau penagihan hukum.
- Tidak bisa membuka panel admin, alokasi lahan, manajemen aset lahan, pusat komando, atau aplikasi lapangan.

<!-- akhir: blok role_guide.py -->

![Menu Operator Entri Data](../gambar/peran/operator-menu.png)

## Pekerjaan sehari-hari

### 1. Mencari dan membuka data sewa

1. Halaman awal Anda adalah daftar **Sewa** ([Bab 3.1](../10-sewa.md#31-daftar-sewa)).
2. Ketik pengenal sewa, nama penyewa, atau alamat di kotak cari, lalu tekan Enter. Gunakan saringan bila hasilnya banyak.
3. Klik baris sewa untuk membuka halamannya, lalu pindah antar-tab ([Bab 3.3](../10-sewa.md#33-halaman-data-sewa)).

### 2. Membuat dan melengkapi sewa

1. Buat sewa dengan **Buat pengenal sewa** ([Bab 3.2](../10-sewa.md#32-membuat-sewa-baru)).
2. Lengkapi semua tab: Ringkasan, Area sewa, Penyewa, Sewa, Keputusan dan kontrak ([Bab 3.3](../10-sewa.md#isi-setiap-tab)).

### 3. Mengisi besaran sewa dan menghitungnya

1. Di tab **Sewa**, klik **Ubah**, isi jenis sewa, jatuh tempo, sewa kontrak per peruntukan, potongan dan kenaikan, lalu simpan.
2. Di **Perhitungan sewa**, pilih tahun atau periode lalu klik **Hitung** untuk memeriksa total terutang.

### 4. Mencatat keputusan

1. Di tab **Keputusan dan kontrak**, tambah keputusan beserta syaratnya, lalu simpan ([Bab 3.3](../10-sewa.md#isi-setiap-tab)).

### 5. Mengelola prinsip sewa dan kompensasi

1. Ubah **Prinsip sewa** ([Bab 3.7](../10-sewa.md#37-prinsip-sewa-dasar-sewa)) dan **Kompensasi pembangunan sisipan** ([Bab 3.9](../10-sewa.md#39-kompensasi-pembangunan-sisipan)) sesuai kebutuhan.

## Bab yang perlu dibaca

- [Bab 1 – Mengenal SimLahan](../01-mengenal-simlahan.md)
- [Bab 2 – Dasar penggunaan](../02-dasar-penggunaan.md)
- [Bab 3 – Sewa lahan](../10-sewa.md)
- [Bab 4 – Pengadaan tanah](../11-pengadaan-tanah.md)

## Bila ada kendala

- Menu atau tombol tidak ada: peran Anda memang tidak memerlukannya ([Bab 2.10](../02-dasar-penggunaan.md#210-batas-akses-dan-pesan-tidak-berhak)). Hubungi Administrator bila Anda memerlukannya untuk pekerjaan.
- Lupa kata sandi: hubungi Administrator atau superuser untuk menyetel ulang sandi.
- Ringkasan peran yang sama bisa dibuka di dalam aplikasi lewat **Panduan peran** (`/akun/panduan/`).
