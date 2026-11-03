# Bab 3 – Sewa lahan (aplikasi utama)

Modul sewa dipakai untuk mencatat dan mengelola sewa/pemanfaatan lahan: data sewa, penyewa, area, besaran sewa, kontrak dan keputusan, tagihan, serta laporan. Modul ini dibuka di **aplikasi utama** (`/`).

**Siapa memakai bab ini:** Penelusur, Penyusun, Penyusun Kontrak, Operator Entri Data, Ahli Hukum Penagihan, Petugas Penagihan, dan Administrator. Setiap peran melihat halaman yang sama, tetapi tombol **Ubah**/**Buat** hanya aktif pada bagian yang menjadi tugasnya. Tabel di bawah merangkum siapa mengubah apa.

| Bagian | Bisa mengubah |
|---|---|
| Data sewa, penyewa, area sewa, inspeksi, kontak, catatan area | Penyusun, Operator Entri Data, Administrator |
| Kontrak, perubahan kontrak, jaminan | Penyusun Kontrak, Operator Entri Data, Administrator (jaminan juga Petugas Penagihan) |
| Keputusan dan syaratnya, besaran sewa & jatuh tempo, prinsip sewa | Operator Entri Data, Administrator (sebagian juga Penyusun/Penyusun Kontrak) |
| Tagihan, pembayaran, catatan tagihan | Petugas Penagihan, Administrator |
| Surat penagihan, putusan pengadilan penagihan, bunga denda | Ahli Hukum Penagihan, Administrator |
| Semua bagian (hanya melihat) | Penelusur |

## 3.1 Daftar sewa

Halaman **Sewa** adalah halaman awal peran sewa.

![Daftar sewa](gambar/sewa/daftar-sewa.png)

1. **Buat pengenal sewa**: membuat sewa baru (lihat 3.2).
2. **Cari dengan kata kunci**: ketik pengenal sewa, nama penyewa, alamat, atau pengenal objek, lalu tekan Enter.
3. **Saringan**: Unit layanan, Jenis, Penyiap, dan Persiapan belum selesai. Tautan **Objek**, **Masa berlaku**, **Keputusan dan kontrak**, dan **Kontak** di atas saringan membuka kolom pencarian tambahan.
4. **Tabel / Peta**: ganti tampilan daftar menjadi peta lokasi sewa.

Klik **pengenal sewa** (misalnya `L1217108-1`) untuk membuka datanya. Tanda **˅** di awal baris menampilkan sewa lain yang terkait. Angka bulat di kolom Penyewa menunjukkan jumlah penyewa.

**Kosongkan pencarian** menghapus semua kata kunci dan saringan.

Tampilan peta:

![Daftar sewa dalam tampilan peta](gambar/sewa/daftar-sewa-peta.png)

## 3.2 Membuat sewa baru

*Peran: Penyusun, Operator Entri Data, Administrator.*

![Buat pengenal sewa](gambar/sewa/buat-pengenal-sewa.png)

1. Di halaman Sewa, klik **Buat pengenal sewa**.
2. Pilih **Jenis** (jenis pemanfaatan) dan **Jenis sewa** (wajib).
3. Pilih **Kabupaten/Kota** dan **Kecamatan** (wajib). Unit layanan terisi otomatis dari unit aktif Anda.
4. Bila perlu isi **Nomor agenda**, **Tanggal permohonan diterima**, **Catatan**, dan **Terkait dengan sewa** (untuk perpanjangan atau pemecahan dari sewa lama).
5. Klik **Buat pengenal**. Sistem membuat pengenal sewa baru dan membuka halaman sewanya.
6. Lengkapi tab-tab sewa (lihat 3.3), lalu klik **Simpan**.

## 3.3 Halaman data sewa

Di bagian atas tampak ringkasan: pengenal sewa, jenis, tanggal mulai/akhir, kondisi, pengenal objek, dan alamat. Di bawahnya ada sembilan tab.

![Ringkasan sewa](gambar/sewa/sewa-tab-ringkasan.png)

1. **Tab**: klik untuk berpindah bagian.
2. **Ubah**: masuk mode ubah untuk tab yang sedang dibuka.

### Mengubah data sewa

![Mode ubah](gambar/sewa/sewa-mode-ubah.png)

1. Buka tab yang akan diubah, lalu klik **Ubah**.
2. Ubah isian. Kolom bertanda **\*** wajib diisi.
3. Klik **Simpan** (1). Klik **Batalkan perubahan** (2) bila tidak jadi.
4. Tombol **Hapus** menghapus seluruh sewa (hanya untuk sewa yang belum berjalan dan bila Anda berhak).

### Isi setiap tab

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

![Tab Area sewa dalam mode ubah](gambar/sewa/sewa-area-ubah.png)

![Tab Sewa dan perhitungan sewa](gambar/sewa/sewa-tab-sewa.png)

![Tab Keputusan dan kontrak](gambar/sewa/sewa-tab-keputusan-dan-kontrak.png)

## 3.4 Penagihan sewa

*Peran: Petugas Penagihan dan Administrator mengelola tagihan; Ahli Hukum Penagihan mengelola surat penagihan dan putusan pengadilan; peran lain hanya melihat.*

![Tab Penagihan](gambar/sewa/sewa-tab-penagihan.png)

**Melihat tagihan.** Tabel **Tagihan** menampilkan kelompok tagihan, penerima, jatuh tempo (merah = lewat), nomor, porsi, periode, jenis piutang, status, nilai ditagih, dan sisa belum dibayar. Klik baris untuk membuka rincian tagihan.

**Membuat tagihan manual**

1. Buka tab **Penagihan**, klik **Buat tagihan**.
2. Pilih penerima, periode, jenis piutang, dan nilai; klik **Simpan**.

**Mencatat pembayaran**: klik baris tagihan untuk membuka panel rinciannya, klik ubah, klik **Tambah pembayaran**, isi jumlah dan tanggal bayar, lalu **Simpan**.

**Mengkreditkan atau menghapus tagihan**: pilih tagihan (bulatan di kiri baris), lalu klik **Kreditkan tagihan** atau **Hapus tagihan** dan ikuti konfirmasinya.

**Menghentikan/menjalankan penagihan otomatis**: klik **Hentikan penagihan** (tulisan **Penagihan berjalan** berubah). Klik lagi untuk menjalankan kembali.

**Penagihan hukum** (Ahli Hukum Penagihan):

1. Di bagian penagihan hukum, klik **Buat surat penagihan**; pilih penyewa dan jenis tuntutan pembayaran.
2. Catat putusan dengan **Tambah putusan pengadilan**.
3. Tambahkan catatan dengan **Tambah catatan**. Bunga denda dihitung otomatis dari tagihan yang terlambat.

## 3.5 Kontak

Kontak adalah daftar orang, badan usaha, perkumpulan, atau unit yang menjadi penyewa, pemberi sewa, atau penagih.

![Daftar kontak](gambar/sewa/kontak-daftar.png)

- Saring dengan **Unit layanan**, **Pengenal sewa**, **Hanya penyewa**, atau **Hanya kontak aktif**.
- Klik nama kontak untuk melihat data dan **Sewa kontak** (daftar sewa yang melibatkan kontak itu, beserta tunggakan).

**Menambah kontak** (Penyusun, Operator, Penagihan, Administrator)

![Kontak baru](gambar/sewa/kontak-baru.png)

1. Klik **Buat kontak**.
2. Pilih **Jenis kontak** (perorangan, badan usaha, perkumpulan, unit). Kolom menyesuaikan jenisnya.
3. Isi nama, NPWP/NIK, alamat, telepon, surel, dan kolom lain yang diperlukan.
4. Klik **Simpan**.

![Detail kontak](gambar/sewa/kontak-detail.png)

## 3.6 Catatan area

Catatan area adalah catatan yang ditandai langsung di peta, misalnya "lahan rawan banjir".

![Catatan area](gambar/sewa/catatan-area.png)

1. Buka **Catatan area**.
2. Klik **Buat catatan area**, gambar area di peta (klik titik-titik batas, klik titik pertama untuk menutup).
3. Tulis catatannya, lalu simpan. Klik area di peta untuk membaca atau mengubah catatan.

## 3.7 Prinsip sewa (dasar sewa)

Prinsip sewa adalah dasar penentuan tarif untuk satu objek atau kawasan.

![Daftar prinsip sewa](gambar/sewa/prinsip-sewa-daftar.png)

1. Buka **Prinsip sewa**. Klik **Buat prinsip sewa** untuk menambah, atau klik pengenal objek untuk membuka.
2. Isi peruntukan utama, tanggal mulai/akhir, tarif dan keputusan terkait.
3. Klik **Simpan**.

![Detail prinsip sewa](gambar/sewa/prinsip-sewa-detail.png)

## 3.8 Statistik dan laporan

*Peran: Penyusun, Penyusun Kontrak, Operator, Ahli Hukum Penagihan, Petugas Penagihan, Administrator (Penelusur tidak).*

![Statistik dan laporan](gambar/sewa/laporan.png)

1. Buka **Statistik dan laporan**.
2. Pilih **Laporan**. Laporan yang tersedia: Tagihan terbuka, Tagihan dalam periode, Jaminan, Pembayaran tagihan, Tagihan yang dibayar kontak, Sewa dengan penagihan nonaktif, Sewa per jenis indeks, Sewa kontak, Persyaratan keputusan, Perbandingan sewa, Proyeksi sewa, Pencadangan, Laporan statistik sewa, Jumlah sewa, Penyesuaian sewa, Dasar sewa, dan Sewa per jenis sewa. Laporan tagihan hanya muncul untuk peran yang berhak.
3. Isi saringan laporan (periode, unit layanan, dsb.).
4. Klik tombol untuk menampilkan atau mengirim laporan. Laporan besar dibuat di latar belakang dan dikirim ke surel Anda.

## 3.9 Kompensasi pembangunan sisipan

Mencatat kompensasi atas pembangunan tambahan di lahan sewa (negosiasi dan keputusan).

![Daftar kompensasi](gambar/sewa/kompensasi-daftar.png)

1. Saring dengan **Berlangsung**, **Negosiasi**, atau **Keputusan**.
2. Klik **Buat kompensasi pembangunan sisipan** untuk data baru (Penyusun, Administrator).
3. Klik nama proyek untuk membuka, lalu **Ubah** dan **Simpan**.

![Detail kompensasi](gambar/sewa/kompensasi-detail.png)

## 3.10 Pencarian area (permohonan area)

Menampung permohonan pemakaian area dari pemohon (misalnya untuk kegiatan sementara).

![Daftar permohonan area](gambar/sewa/pencarian-area-daftar.png)

1. Saring per status: Diterima, Menunggu informasi tambahan, Diproses, Selesai, Dicabut, Ditolak.
2. Klik nomor permohonan untuk membuka: data **Permohonan**, **Dokumen yang diperiksa**, dan **Data pemrosesan**.
3. Klik **Ubah** untuk memproses: isi petugas, status, dan keputusan, lalu **Simpan**.
4. Centang beberapa baris lalu klik **Cetak** untuk mencetak.
5. **Buat permohonan area** untuk memasukkan permohonan yang datang lewat loket.

![Detail permohonan area](gambar/sewa/pencarian-area-detail.png)

Halaman **Pencarian kavling** dan **Permohonan kavling** (bila ditampilkan untuk peran Anda) bekerja dengan cara yang sama untuk seleksi kavling.

![Pencarian kavling](gambar/sewa/pencarian-kavling.png)

## 3.11 Menu "Lainnya"

| Menu | Kegunaan |
|---|---|
| **Indeks biaya hidup** | Tabel indeks per bulan dan tahun yang dipakai untuk penyesuaian sewa berindeks. Hanya dibaca. |
| **Tugas terjadwal** | Riwayat (**Eksekusi**) dan **Jadwal** proses otomatis, misalnya pembuatan tagihan dan pengingat. Hanya dibaca; mengubah jadwal hanya oleh superuser. |
| **Catatan tagihan** | Pengumuman yang dicetak pada tagihan per sewa dan periode. Klik **Buat pengumuman** untuk menambah. |
| **Kalkulator sewa** | Menghitung perkiraan sewa tanpa menyimpan ke data sewa. Klik **Tambah kalkulator sewa**, pilih jenis kalkulator, isi nilai, lihat hasilnya. |

![Indeks biaya hidup](gambar/sewa/indeks.png)

![Tugas terjadwal](gambar/sewa/tugas-terjadwal.png)

![Catatan tagihan](gambar/sewa/catatan-tagihan.png)

![Kalkulator sewa](gambar/sewa/kalkulator-sewa.png)

## 3.12 Pertanyaan umum

**Tombol Ubah abu-abu/tidak bisa diklik.** Bagian itu bukan tugas peran Anda, atau data sedang dikunci karena sudah final. Tanyakan kepada petugas yang berwenang.

**Sewa tidak ditemukan.** Periksa saringan **Unit layanan**; data sewa dibatasi per unit. Klik **Kosongkan pencarian** lalu cari lagi.

**Perubahan tidak tersimpan.** Pastikan Anda menekan **Simpan** sebelum pindah tab. Kolom wajib (tanda \*) yang kosong menyebabkan simpan gagal; periksa tulisan merah di bawah kolom.
