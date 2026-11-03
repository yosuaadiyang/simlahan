# Bab 16 – Superuser dan pemeliharaan sistem

Bab ini untuk **superuser** (pengelola sistem) dan petugas TI yang memasang SimLahan. Superuser memegang semua hak, termasuk hal yang tidak bisa dilakukan Administrator: mengelola akun dan peran, unit layanan, kunci sistem, dan tugas terjadwal.

> Jumlah superuser sebaiknya sedikit (1–2 orang). Pekerjaan harian dilakukan dengan akun ber-peran biasa.

![Panel admin superuser](gambar/peran/superuser-panel.png)

## 16.1 Mengelola pengguna

![Daftar pengguna](gambar/peran/superuser-pengguna.png)

Buka **Panel admin → Pengguna → Pengguna**. Saring dengan **status staf**, **status superuser**, **aktif**, dan **grup**.

**Membuat akun petugas:**

![Tambah pengguna](gambar/peran/superuser-pengguna-tambah.png)

1. Klik **Tambahkan pengguna**.
2. Isi **Nama pengguna** (misalnya `budi.santoso`) dan kata sandi awal dua kali. Kata sandi minimal 10 karakter, tidak mirip nama, tidak umum, dan tidak hanya angka.
3. Klik **Simpan dan terus mengedit**.
4. Di halaman berikutnya, isi **Nama depan**, **Nama belakang**, dan **Alamat surel** (dipakai untuk OTP, pemberitahuan, dan atur ulang sandi).
5. Di **Hak akses**: centang **Aktif** dan **Status staf** (wajib untuk petugas). Jangan centang **Status superuser** kecuali untuk pengelola sistem.
6. Pindahkan satu **grup** (peran) dari kotak kiri ke kanan, misalnya **Petugas Alokasi Lahan** atau **Koordinator Wilayah**. Peran menentukan menu dan hak akses; isinya dijelaskan di buku peran masing-masing.
7. Pilih **Unit layanan** petugas. Petugas hanya melihat data unit layanannya (data tanpa unit layanan terlihat semua).
8. Klik **Simpan**. Sampaikan nama pengguna dan kata sandi awal secara pribadi, lalu minta petugas segera mengganti sandi ([Bab 2.8](02-dasar-penggunaan.md#28-mengganti-kata-sandi)).

![Ubah pengguna](gambar/peran/superuser-pengguna-ubah.png)

**Tugas lain:**

- **Lupa sandi petugas:** buka akunnya, klik **Setel kembali sandi**, isi sandi baru dua kali. Mengganti sandi mencabut sesi aplikasi yang sedang aktif.
- **Petugas pindah tugas:** ganti grup dan unit layanannya. Untuk petugas lapangan, pindahkan juga keanggotaannya di data Korwil ([Bab 11.1](41-panel-pusat-komando.md#111-korwil-koordinator-wilayah)) dan atasan langsungnya ([Bab 11.8](41-panel-pusat-komando.md#118-jabatan-tugas-dan-laporan-harian)).
- **Petugas berhenti:** hapus centang **Aktif** (jangan hapus akunnya agar jejak audit tetap utuh).
- **Akun pemohon dan investor** dibuat sendiri oleh mereka di portal. Data pemohonnya ada di **Alokasi lahan → Pemohon**.

## 16.2 Grup (peran)

![Daftar grup](gambar/peran/superuser-grup.png)

**Panel admin → Autentikasi dan otorisasi → Grup.** Setiap grup adalah satu peran (Penelusur, Penyusun, …, Koordinator Wilayah). Hak akses tiap grup sudah diatur sistem. **Jangan mengubah hak akses grup secara manual**; bila tidak sengaja berubah, kembalikan dengan menjalankan `simlahan_bootstrap` (16.7). Daftar lengkap menu dan batas tiap peran ada di **Panduan peran** di dalam aplikasi dan di [buku peran](README.md#buku-per-peran).

## 16.3 Unit layanan

![Unit layanan](gambar/peran/superuser-unit-layanan.png)

**Panel admin → Sewa lahan → Unit layanan** mencatat unit/kantor layanan (misalnya "Unit Layanan Utama"). Unit layanan dipakai untuk membatasi data per kantor: setiap aset, Korwil, dan data lain punya kolom **Unit layanan / lokasi**, dan setiap petugas diberi unit layanannya di akun pengguna.

## 16.4 OTP surel untuk petugas

Bila diaktifkan, petugas harus memasukkan kode 6 angka yang dikirim ke surelnya setiap kali masuk (aplikasi utama, panel admin, pusat komando, aplikasi lapangan). Pengaturan ini dilakukan petugas TI di berkas `.env` server:

```
OFFICER_OTP_REQUIRED=True
```

Pastikan pengiriman surel (`EMAIL_URL`) sudah berfungsi dan setiap akun petugas punya **Alamat surel** sebelum menyalakannya.

## 16.5 Kunci hidup sistem

![Kunci hidup sistem](gambar/peran/superuser-kunci-sistem.png)

Fitur darurat untuk menghentikan seluruh aplikasi pada waktu tertentu (misalnya bila terjadi pelanggaran keamanan atau sengketa operasional). Buka **Panel admin → Pusat komando operasi lapangan → Kunci hidup sistem**.

**Mengaktifkan:**

1. Isi **Kode rahasia baru** (minimal 6 karakter) dan **Ulangi kode rahasia baru**. Simpan kode ini di tempat aman.
2. Centang **Aktif**, isi **Sistem dimatikan pada** (tanggal dan waktu), dan **Pesan untuk pengguna**.
3. Klik **Simpan**. Hitung mundur "KUNCI SISTEM AKTIF" tampil di pusat komando dan panel. Saat waktunya tiba, seluruh aplikasi berhenti melayani pengguna selain superuser.

**Menonaktifkan:** buka halaman yang sama, isi **Kode rahasia saat ini**, hapus centang **Aktif**, lalu simpan. Di pusat komando, superuser juga bisa menekan **🛡 Nonaktifkan** pada bilah hitung mundur dan memasukkan kode rahasia. Siapa dan kapan kunci diaktifkan atau dinonaktifkan tercatat di halaman ini.

> Kunci tidak aktif secara bawaan. Hanya superuser yang dapat membuka halaman ini.

## 16.6 Tugas terjadwal

![Tugas terjadwal](gambar/peran/superuser-batchrun.png)

**Panel admin → Tugas batch** menjalankan pekerjaan otomatis. Menu terpenting: **Tugas terjadwal** (jadwal) dan **Eksekusi tugas** (riwayat jalan). Jadwal bawaan SimLahan:

| Jadwal | Pekerjaan |
|---|---|
| Setiap hari kerja pukul 07.00 WIB | Pemeriksaan tenggat pengadaan tanah (surel pengingat). |
| Setiap Senin pukul 07.30 WIB | Pemantauan alokasi lahan (lahan tidur, laporan pembangunan). |
| Setiap hari pukul 06.30 WIB | Pengingat tenggat aset lahan. |
| Setiap hari pukul 06.45 WIB | Pengingat dokumen & perizinan (izin hampir habis, tanda tangan tertunda). |
| Setiap hari pukul 00.30 WIB | Rekap harian pusat komando. |

![Jadwal tugas](gambar/peran/superuser-batchrun-jadwal.png)

- **Tugas terjadwal**: centang atau hapus centang **aktif** untuk menyalakan/mematikan jadwal; ubah jam/menit/hari bila perlu. Jadwal lain (pembuatan tagihan sewa, rotasi log) mati secara bawaan.
- **Eksekusi tugas**: setiap eksekusi dengan waktu mulai, tugas, dan **kode keluar** (0 = berhasil). Buka baris untuk melihat log.

![Riwayat tugas terjadwal](gambar/peran/superuser-batchrun-riwayat.png)

## 16.7 Perintah pemeliharaan (petugas TI)

Perintah dijalankan di server dari folder SimLahan:

```
docker compose exec backend python manage.py <perintah>
```

| Perintah | Kegunaan |
|---|---|
| `simlahan_bootstrap` | Membuat atau memulihkan data master, hak akses grup, jadwal bawaan, dan admin awal. Aman dijalankan ulang. |
| `data_contoh` | Membuat seluruh data contoh fiktif di semua modul (untuk pelatihan). `--cek` memeriksa cakupan, `--hapus` menghapusnya. |
| `pengguna_contoh` | Membuat akun contoh untuk setiap peran (`contoh.<peran>`, `pemohon@contoh.simlahan.invalid`, `investor@contoh.simlahan.invalid`). `--sandi` menetapkan satu sandi untuk semua, `--sandi-baru` membuat sandi acak baru, `--hapus` menghapus akun contoh. |
| `hapus_data_contoh` | Menghapus **semua** data contoh dan akun contoh sebelum dibuka untuk publik. Data kerja nyata tidak disentuh. |
| `cek_produksi` | Memeriksa kesiapan publik (pengaturan, surel, alamat publik, akun & data contoh, sandi admin awal). Harus mencetak "Siap dibuka untuk publik". |
| `panduan_peran` | Mencetak panduan peran dalam format Markdown (sumber `docs/panduan-peran.md`). |
| `impor_komando` | Mengimpor data pusat komando lama (berkas cadangan). `--coba` untuk uji coba tanpa menyimpan. Jalankan `hapus_data_contoh` lebih dulu. |

> Sebelum SimLahan dibuka untuk publik: jalankan `hapus_data_contoh`, lalu `cek_produksi`. Jangan membagikan sandi akun contoh.

## 16.8 Membuat ulang buku panduan ini

Buku panduan disimpan di folder `docs/panduan/` repositori. Cara membuat ulang gambar dan PDF dijelaskan di `docs/panduan/alat/README.md`.
