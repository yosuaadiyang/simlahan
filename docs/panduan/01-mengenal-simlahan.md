# Bab 1 – Mengenal SimLahan

SimLahan (Sistem Informasi Manajemen Lahan) adalah satu sistem untuk mengelola lahan: dari pengadaan tanah, alokasi lahan kepada badan usaha, sewa lahan, pengelolaan aset, sampai operasi petugas di lapangan. Semua data tersimpan di satu tempat dan terhubung dengan peta.

Bab ini menjelaskan bagian-bagian SimLahan dan istilah yang sering muncul. Anda tidak perlu menghafalnya; cukup baca sekali agar tahu "di mana mengerjakan apa".

## 1.1 Enam "pintu" SimLahan

SimLahan terdiri dari beberapa aplikasi yang dibuka lewat peramban (Chrome, Edge, Firefox, Safari). Satu kali masuk berlaku untuk semua aplikasi petugas yang boleh Anda buka.

| Aplikasi | Alamat | Dipakai oleh | Isinya |
|---|---|---|---|
| **Aplikasi utama** | `/` | Petugas sewa, pengadaan tanah, Administrator | Sewa lahan, pengadaan tanah (UU 2/2012), kontak, laporan |
| **Panel admin** | `/admin/` | Petugas alokasi, verifikasi, aset, hukum, pusat komando, Administrator | Alokasi lahan, investasi, dokumen & perizinan, aset lahan, data master |
| **Pusat Komando** | `/komando/` | Petugas Lapangan, Koordinator Wilayah, Petugas Aset, Administrator | Peta operasi, absen, laporan kegiatan, warga, tugas, kinerja, chat (bisa dipasang di HP) |
| **Aplikasi lapangan** | `/aset/lapangan/` | Petugas Lapangan, Petugas Aset | Laporan & foto lapangan aset, bisa tanpa sinyal |
| **Portal** | `/portal/` | Masyarakat, pemohon, investor | Informasi layanan, peta lahan, permohonan alokasi, minat investasi, pengaduan, cek keaslian dokumen |
| **Halaman akun** | `/akun/panduan/`, `/akun/sandi/` | Semua petugas | Panduan peran singkat dan ganti kata sandi |

> **Catatan alamat.** Di buku ini alamat ditulis singkat, misalnya `/portal/`. Artinya: alamat SimLahan instansi Anda ditambah tulisan itu, misalnya `https://simlahan.instansi-anda.go.id/portal/`.

## 1.2 Peran (role) pengguna

Setiap akun petugas punya **peran**. Peran menentukan menu yang tampil dan tombol yang bisa dipakai. Bila sebuah menu atau tombol tidak tampil di layar Anda, berarti peran Anda memang tidak memerlukannya.

| Kelompok | Peran |
|---|---|
| Sewa lahan | Penelusur, Penyusun, Penyusun Kontrak, Operator Entri Data, Ahli Hukum Penagihan, Petugas Penagihan |
| Pengadaan tanah | Pelaksana Pengadaan Tanah, Satgas Pengadaan Tanah, Penilai Pertanahan, Instansi Yang Memerlukan Tanah |
| Alokasi & dokumen | Petugas Alokasi Lahan, Tim Verifikasi Teknis |
| Aset lahan | Petugas Aset Lahan, Petugas Hukum |
| Lapangan | Petugas Lapangan, Koordinator Wilayah |
| Pengelola | Administrator (semua modul), Superuser (akun & pengaturan sistem) |
| Masyarakat | Pemohon portal, Investor |

Buku khusus untuk setiap peran ada di folder [peran](peran/). Daftar lengkapnya ada di [halaman depan](README.md).

## 1.3 Istilah yang sering muncul

| Istilah | Arti |
|---|---|
| **Unit layanan** | Bagian/kantor yang memiliki data. Data sewa dan aset dibatasi per unit layanan. |
| **Korwil** | Koordinator wilayah: satu wilayah kerja lapangan beserta koordinator dan anggotanya. |
| **Komsos** | Komunikasi sosial: kunjungan dan percakapan petugas dengan warga. |
| **Sikap warga** | Mendukung (pro), netral, menolak (kontra), atau belum diketahui terhadap program; dicatat petugas saat komsos. |
| **RTRW** | Rencana Tata Ruang Wilayah; dipakai untuk mencocokkan lokasi warga/bidang dengan zona tata ruang. |
| **Bidang** | Sebidang tanah yang dipetakan (punya batas di peta). |
| **Pihak yang berhak** | Pemilik atau penggarap bidang yang berhak atas ganti kerugian pengadaan tanah. |
| **KJPP / Penilai** | Penilai pertanahan yang menghitung nilai ganti kerugian. |
| **Musyawarah** | Pertemuan penetapan bentuk dan nilai ganti kerugian dengan pihak yang berhak. |
| **Konsinyasi** | Penitipan ganti kerugian di pengadilan negeri bila pihak menolak atau tidak diketahui. |
| **UWT** | Uang Wajib Tahunan: biaya pemanfaatan lahan alokasi per m² per tahun. |
| **KPT / PPT / PL** | Dokumen keputusan alokasi: Keputusan Pengalokasian Tanah, Perjanjian Pemanfaatan Tanah, dan Penetapan Lokasi (berisi sketsa bidang). |
| **Pemanfaatan lahan** | Satu kegiatan usaha di atas lahan (sewa/alokasi/kerja sama) yang wajib punya dokumen perizinan. |
| **Dokumen tanda tangan** | Dokumen yang dikirim untuk ditandatangani secara elektronik secara berurutan. |
| **Permintaan unduh** | Permintaan untuk mengunduh dokumen; harus disetujui orang lain, lalu berkas diberi tanda air. |
| **Okupasi / perambahan** | Penguasaan atau pemakaian lahan tanpa hak. |
| **Poin / KPI** | Nilai kinerja petugas lapangan dari absen, kegiatan, dan tugas. |
| **Luring (offline)** | Bekerja tanpa sinyal; data disimpan di HP lalu terkirim otomatis saat ada sinyal. |

## 1.4 Tentang gambar di buku ini

- Semua gambar diambil dari SimLahan yang berisi **data contoh fiktif** (bertanda "CONTOH" atau "[contoh]"). Nama orang, perusahaan, NIK, dan angka di gambar bukan data sebenarnya.
- **Latar peta di gambar tampil polos** (abu-abu/kosong) karena gambar dibuat di komputer uji tanpa sambungan ke penyedia peta dasar. Di sistem Anda, latar peta jalan atau citra satelit tampil normal di bawah titik dan batas bidang.
- Lingkaran merah bernomor di gambar menunjuk tombol yang disebut di langkah-langkah. Nomor di gambar sama dengan nomor langkah atau nomor penjelasan di bawahnya.
- Gambar tampilan HP diambil dengan ukuran layar ponsel biasa. Di HP Anda, letak tombol sama, hanya ukurannya bisa sedikit berbeda.
