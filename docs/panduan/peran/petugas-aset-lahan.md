# Buku peran: Petugas Aset Lahan

Buku ini untuk **Petugas Aset Lahan**: pengelola data aset lahan (bank tanah) unit layanannya. Buku ini berisi semua langkah kerja peran Anda, lengkap dengan gambar, sehingga cukup dibaca sendiri. Dasar penggunaan yang berlaku untuk semua peran (mengenal layar, ganti sandi, memakai di HP) ada di [Bab 2](../02-dasar-penggunaan.md).

**Cara membaca buku ini.** Kotak merah bernomor pada gambar menunjuk tombol atau kolom yang disebut di langkah. Tulisan *(nomor 2)* berarti: lihat kotak merah bernomor 2 pada gambar tepat di atas langkah itu. Semua gambar memakai data contoh fiktif; isi di layar Anda berbeda, tetapi letak tombolnya sama. Judul bagian bernomor (misalnya *3.4*) sama dengan nomor bagian di buku lengkap.

## Masuk dan halaman awal

<!-- sisip: 02-dasar-penggunaan.md#b-panel-admin -->

### B. Panel admin

![Halaman masuk panel admin](../gambar/dasar/masuk-panel-admin.png)

1. Buka alamat SimLahan diikuti `/admin/`, misalnya `https://simlahan.instansi-anda.go.id/admin/`.
2. Isi **Nama pengguna** (nomor 1) dan **Sandi** (nomor 2).
3. Klik **Masuk** (nomor 3).

Bila Anda sudah masuk di aplikasi utama, panel admin langsung terbuka tanpa masuk ulang.

<!-- akhir sisip -->

### Halaman awal

Setelah masuk, Anda langsung melihat **Dasbor manajemen aset lahan** di panel admin:

![Halaman awal Petugas Aset](../gambar/peran/aset-beranda.png)

Nomor pada gambar:

1. **Saring menu**: ketik sebagian nama menu (misalnya *tagihan*) untuk menemukannya cepat di menu samping.
2. **Dasbor**: halaman ini. Deretan tombol di sebelahnya membuka alat lain.
3. **Peta tematik** dan alat lain di deretan yang sama: Jadwal (Gantt), Pembuat laporan, Buku besar gabungan, Tumpang tindih, Pembanding citra, Matriks pemangku kepentingan, Pencarian, Asisten AI.
4. **Peringatan & tenggat**: hak atas tanah yang akan berakhir, pajak jatuh tempo, sidang terdekat. Tangani baris ini lebih dulu setiap hari.
5. **Panduan peran**: ringkasan peran Anda.
6. **Keluar**: mengakhiri sesi di semua aplikasi petugas pada perangkat ini.
7. **⇄ Pusat Komando**: memantau tim lapangan.
8. **⇄ Aplikasi lapangan**: mengirim laporan dari lapangan.

### Beranda panel admin

Klik **Administrasi SimLahan** di kiri atas untuk membuka beranda panel admin. Isinya kotak per modul yang boleh Anda buka:

![Beranda panel admin Petugas Aset](../gambar/peran/aset-panel.png)

Anda melihat modul **Manajemen aset lahan** dan **Pusat komando operasi lapangan** (hanya membaca). Tautan **Lihat** hanya membaca; **Ubah** dan **Tambah** berarti Anda boleh mengubah atau menambah data itu. Cara memakai halaman daftar dan formulir panel admin dijelaskan di [Bab 2.4](../02-dasar-penggunaan.md#24-mengenal-layar-panel-admin).

<!-- awal: dibuat dari backend/users/role_guide.py; perbarui dengan: cd backend && python manage.py panduan_buku -->

## Ringkasan peran

Mengelola seluruh data aset lahan unit layanannya.

- **Cara masuk:** Alamat utama SimLahan (`/`) atau langsung di panel admin (`/admin/`); satu kali masuk berlaku untuk keduanya.
- **Halaman awal:** Panel admin → Dasbor aset.
- **Akun latihan** (hanya di sistem latihan berisi data contoh): `contoh.aset`

### Menu yang Anda lihat

- Panel admin, Manajemen aset lahan: dasbor, peta tematik, data aset, keuangan (penilaian, pajak, transaksi), okupasi, permukiman kembali, pengaduan, lelang, dokumen, peta berbagi, laporan & asisten AI
- Aplikasi lapangan (`/aset/lapangan/`)
- Pusat komando (`/komando/`, tombol **Pusat Komando** di panel admin) sebagai pengawas: Peta, Absen, Lapor (hanya Laporan saya/tim), Warga, Tugas, Kinerja, Chat; Menu: Beranda, Peta & spasial, Persetujuan, Laporan harian (termasuk rekap Excel), Peringkat tim, Historis, Uji tanah PLTS (baca & unduh Excel), Alat & tiket

### Yang bisa Anda lakukan

- Membuat dan mengubah aset, penilaian, pajak, transaksi, okupasi, permukiman kembali, pengaduan, lelang, dokumen, dan tugas.
- Membaca perkara hukum.
- Memantau petugas dan Korwil di unit layanannya di pusat komando.
- Menandai zona ancaman; membaca bidang penguasaan lahan, foto 360°, tumpang tindih lapisan, dan audit RTRW (tidak mengubah status bidang).
- Mengirim tiket & masukan; memakai OCR, AI dokumen → laporan, AI foto lapangan, dan sinkron Excel.

### Batas akses

- Hanya data unit layanannya (data tanpa unit layanan terlihat semua).
- Tidak melapor kegiatan/uji tanah di pusat komando dan tidak melihat NIK warga.
- Tidak mengubah titik uji tanah PLTS dan tidak menjalankan audit data.
- Tidak membuka modul sewa, pengadaan, atau alokasi.

<!-- akhir: blok role_guide.py -->

## Urutan kerja Anda

1. Mulai dari **Peringatan & tenggat** di dasbor ([8.1 Dasbor aset lahan](#81-dasbor-aset-lahan)).
2. Tambah, ubah, atau impor aset ([8.2 Data aset lahan](#82-data-aset-lahan)); catat penilaian, pajak, dan transaksi ([8.4 Keuangan: penilaian, pajak, transaksi, buku besar](#84-keuangan-penilaian-pajak-transaksi-buku-besar)).
3. Tangani okupasi, pengaduan, lelang, dan permukiman kembali ([8.6 Okupasi & perambahan](#86-okupasi--perambahan), [8.7 Pengaduan masyarakat](#87-pengaduan-masyarakat), [8.8 Lelang & seleksi lahan](#88-lelang--seleksi-lahan), [8.9 Permukiman kembali](#89-permukiman-kembali)).
4. Kelola dokumen, tugas, dan laporan lapangan ([8.12 Dokumen & arsip, tugas, tim, laporan lapangan](#812-dokumen--arsip-tugas-tim-laporan-lapangan)); pakai alat analisis ([8.13 Alat analisis](#813-alat-analisis)).
5. Di lapangan, kirim laporan lewat aplikasi lapangan ([9.1 Aplikasi lapangan (`/aset/lapangan/`)](#91-aplikasi-lapangan-asetlapangan)).
6. Pantau tim di Pusat Komando sebagai pengawas (Bagian C). Anda tidak melapor kegiatan sendiri.

## Bagian A – Manajemen aset lahan

<!-- sisip: 30-aset-lahan.md#81-dasbor-aset-lahan -->

### 8.1 Dasbor aset lahan

![Dasbor manajemen aset lahan](../gambar/aset/dasbor.png)

Buka **Manajemen aset lahan → Dasbor**. Baris tombol di atas adalah jalan pintas ke alat analisis: **Dasbor, Peta tematik, Jadwal (Gantt), Pembuat laporan, Buku besar gabungan, Tumpang tindih, Pembanding citra, Matriks pemangku kepentingan, Pencarian, Asisten AI**.

Kartu angka: jumlah **Aset lahan**, **Total luas (m²)**, **Nilai portofolio (penilaian terakhir)**, **Nilai perolehan**, **Perkara aktif** (dan nilai gugatan), **Okupasi terbuka** (dan luasnya), **Tugas terbuka** (terlambat dan milik saya), **Pengaduan terbuka** (lewat batas), **Lelang menerima penawaran**, serta ringkasan modul lain: **Proyek pengadaan tanah aktif**, **Bidang pengadaan bersengketa**, **Permohonan alokasi diproses**, **Alokasi lahan aktif**, dan **Kontrak sewa berlaku**.

Panel **Peringatan & tenggat** mengumpulkan yang perlu segera ditangani. Klik baris untuk membuka daftarnya:

- Sewa berakhir ≤ N hari, Hak atas tanah berakhir ≤ N hari, Pajak jatuh tempo ≤ N hari / terlambat, Sidang ≤ N hari.
- Tugas lewat tenggat, Pengaduan lewat batas, Okupasi tanpa tindak lanjut > N hari.
- Aset belum dipantau sesuai jadwal, Urusan instansi perlu ditindaklanjuti.

Angka N diatur di **Pengaturan modul aset lahan** (8.14).

![Panel Peringatan & tenggat](../gambar/aset/dasbor-peringatan.png)

Di bawahnya ada grafik **Aset per status (jumlah/luas)**, **Aset per kategori**, **Perkara per status**, **Hasil putusan**, **Okupasi per status**, **Tugas per status**, **Pengaduan per status**, **Lelang per status**, dan ringkasan keuangan (**Penerimaan · Pengeluaran · Bersih**).

<!-- akhir sisip -->

<!-- sisip: 30-aset-lahan.md#82-data-aset-lahan -->

### 8.2 Data aset lahan

Buka **Manajemen aset lahan → Aset lahan**.

![Daftar aset lahan](../gambar/aset/aset-daftar.png)

- **Tambahkan Aset lahan** (nomor 1): menambah satu aset.
- **Impor SHP/KML/KMZ/GeoJSON** (nomor 2): menambah atau memperbarui banyak aset dari berkas peta.
- **Peta tematik** (nomor 3): menampilkan semua aset di peta (lihat 8.3).
- **Kotak cari** (nomor 4): cari kode, nama, nomor hak, atau NIB, lalu klik **Cari**.
- **Filter** (nomor 5) di kanan: saring per **Status penguasaan**, **Kategori**, **Jenis alas hak**, **Cara perolehan**, **Unit layanan / lokasi**, atau **Kabupaten / kota**.
- **Aksi** (nomor 6): tindakan untuk aset yang dicentang, misalnya **Ekspor ke Excel**.

Kolom **Irisan dengan bidang lain** memberi tanda bila batas aset bertumpang tindih.

Status penguasaan: Dikuasai, belum dimanfaatkan · Dimanfaatkan sendiri · Disewakan · Dialokasikan · Dalam proses pengadaan · Sengketa · Terokupasi · Dilepas / dijual.

#### Menambah atau mengubah aset

Klik **Tambahkan Aset lahan**, atau klik kode aset di daftar untuk mengubahnya.

![Halaman aset lahan](../gambar/aset/aset-detail.png)

Tombol di kanan atas halaman aset (muncul setelah aset disimpan) mempercepat pekerjaan terkait aset itu:

- **Tambah penilaian** (nomor 1): membuka formulir penilaian dengan aset ini sudah terpilih.
- **Buat tugas** (nomor 2): membuat tugas atau perintah kerja untuk aset ini.
- **Ajukan survei** (nomor 3): mengajukan survei atau pengukuran.
- **Catat okupasi** (nomor 4): mencatat temuan okupasi di aset ini.

Mengisi data aset:

1. Isi **Kode aset** (nomor 5) dan **Nama / lokasi aset** (nomor 6).
2. Pilih **Kategori** (nomor 7) dan **Status penguasaan** (nomor 8). Di bawahnya, pilih **Unit layanan / lokasi** dan **Penanggung jawab**.
3. Bagian **Pemantauan lapangan**: isi **Pemantauan tiap (hari)**. Kosongkan untuk memakai jadwal bawaan modul; isi 0 bila aset tidak perlu dipantau.
4. Gulir ke bagian **Lokasi & batas**:

![Bagian Lokasi & batas](../gambar/aset/aset-detail-lokasi.png)

5. Pilih **Kabupaten / kota** (nomor 1), lalu isi **Kecamatan** (nomor 2), **Kelurahan / desa** (nomor 3), dan **Alamat** (nomor 4).
6. Di peta di bawahnya, gambar batas aset: klik titik-titik sudut satu per satu, lalu klik dua kali di titik terakhir untuk selesai. Isi **Luas (m²)** bila tidak ingin dihitung dari gambar.
7. Bagian **Alas hak**: pilih jenis (SHM, HGB, HGU, Hak Pakai, HPL, girik, belum bersertipikat, lainnya), lalu isi nomor hak, NIB, dan tanggal berakhir hak.
8. Bagian **Perolehan & nilai** dan **Pemanfaatan**: isi cara perolehan, nilai perolehan, dan penggunaan aset saat ini.
9. Gulir ke bagian paling bawah:

![Tabel di bagian bawah halaman aset](../gambar/aset/aset-detail-bawah.png)

   Tambah baris **Riwayat kepemilikan** (nomor 1), **Pajak & retribusi** (nomor 2), dan **Dokumen & arsip** (nomor 3) bila ada. Klik **Tambahkan … lagi** di bawah tiap tabel untuk baris berikutnya.

10. Klik **Simpan**.

Kolom ringkasan di halaman aset menampilkan **Penilaian terakhir** dan jumlah **Perkara, okupasi, tugas, survei** yang terkait.

#### Mengimpor aset dari peta

![Impor aset](../gambar/aset/aset-impor.png)

1. Di daftar aset, klik **Impor SHP/KML/KMZ/GeoJSON**.
2. Klik **Pilih File** (nomor 1) dan pilih berkas hasil ekspor QGIS/ArcGIS: GeoJSON, KML/KMZ (juga dari Google Earth), GeoPackage, atau Shapefile (berkas .shp/.shx/.dbf/.prj dalam satu ZIP). Atribut yang dikenali: `kode`, `nama`, `alamat`, `kecamatan`, `kelurahan`, `nib`, `njop`, `nomor_hak`, `pemegang_hak`, `penggunaan`, `peruntukan`.
3. Pilih **Kategori** (nomor 2) dan **Status penguasaan** (nomor 3) untuk aset yang tidak menyebutkannya di berkas.
4. Klik **Impor** (nomor 4). Aset dengan kode yang sudah ada **diperbarui**; aset tanpa kode dibuat baru dengan nomor otomatis.

**Ekspor ke Excel:** centang aset di daftar, pilih aksi **Ekspor ke Excel**, klik **Jalankan**.

<!-- akhir sisip -->

<!-- sisip: 30-aset-lahan.md#83-peta-tematik -->

### 8.3 Peta tematik

![Peta tematik](../gambar/aset/peta-tematik.png)

1. Klik **Peta tematik** (di dasbor atau daftar aset).
2. Pilih **Warna aset** (nomor 1): warnai bidang menurut **Status penguasaan** atau **Kategori**.
3. Saring dengan **Status** (nomor 2) dan **Kategori** (nomor 3). Centang **Termasuk okupasi selesai** bila kasus yang sudah selesai juga ingin ditampilkan.
4. Klik **Terapkan** (nomor 4).
5. Arahkan tetikus ke kotak lapisan di kanan atas peta (nomor 5) untuk memilih peta dasar, citra, dan lapisan yang tampil: aset, okupasi, bidang pengadaan, lahan alokasi, permukiman kembali, survei, laporan lapangan, dan lapisan peta referensi.
6. Klik bidang di peta untuk melihat rincian dan tautannya.

> Di sistem latihan, peta dasar bisa tampak abu-abu bila komputer tidak terhubung ke internet. Batas bidang tetap tampil.

<!-- akhir sisip -->

<!-- sisip: 30-aset-lahan.md#84-keuangan-penilaian-pajak-transaksi-buku-besar -->

### 8.4 Keuangan: penilaian, pajak, transaksi, buku besar

**Penilaian aset**

![Penilaian aset](../gambar/aset/penilaian.png)

Penilaian mencatat nilai tanah, bangunan & benda, dan total. Metode: NJOP, Penilai publik (KJPP), Penilai internal, Data pasar / pembanding. Rincian benda (bangunan, tanaman, sarana pelengkap) diisi di tabel di bawah formulir. Klik **Tambahkan Penilaian aset** untuk mencatat penilaian baru.

**Pajak & retribusi**

![Pajak & retribusi](../gambar/aset/pajak.png)

Jenisnya: PBB-P2, BPHTB, Uang Wajib Tahunan, Retribusi daerah, Sewa tanah, Lainnya. Kolom **Status bayar** menunjukkan lunas, belum, atau terlambat. Untuk mencatat pembayaran sekaligus: centang baris, pilih aksi **Tandai lunas hari ini & catat transaksi** di kotak **Aksi** (nomor 1), lalu klik **Jalankan**. Sistem membuat transaksi pengeluaran otomatis.

**Transaksi keuangan lahan**

![Transaksi keuangan lahan](../gambar/aset/transaksi.png)

Jenisnya: pembelian, penjualan/pelepasan, penerimaan dan pembayaran sewa, ganti kerugian, biaya permukiman kembali, pajak, biaya survei, biaya hukum, biaya lain. Untuk sistem akuntansi, centang transaksi, pilih aksi **Ekspor jurnal ERP (CSV)** atau **Ekspor jurnal ERP (Excel)** di kotak **Aksi** (nomor 1), lalu klik **Jalankan**. Kode akun kas/bank diatur di pengaturan modul.

**Buku besar gabungan** menggabungkan transaksi aset, pembayaran ganti kerugian pengadaan tanah, dan tagihan alokasi yang lunas.

![Buku besar gabungan](../gambar/aset/buku-besar.png)

1. Isi tanggal **Dari** (nomor 1) dan **Sampai** (nomor 2).
2. Klik **Tampilkan** (nomor 3). Layar menampilkan 1.000 baris pertama.
3. Klik **Ekspor Excel** (nomor 4) atau **Ekspor CSV** (nomor 5) untuk mengunduh semua baris.

> Jangan mencatat ulang pembayaran ganti kerugian sebagai transaksi aset, karena sudah otomatis masuk buku besar.

<!-- akhir sisip -->

<!-- sisip: 30-aset-lahan.md#85-perkara--litigasi -->

### 8.5 Perkara & litigasi

![Daftar perkara](../gambar/aset/perkara-daftar.png)

Saringan: **Status**, **Jenis perkara**, **Forum**, **Hasil**, **Unit layanan / lokasi**. Kolom **Sidang berikutnya** dan **Kasus okupasi terkait** membantu memantau.

**Menambah perkara** (Petugas Hukum): klik **Tambahkan Perkara**, atau klik judul perkara di daftar untuk mengubahnya.

![Halaman perkara](../gambar/aset/perkara-detail.png)

1. Isi **Pokok perkara** (nomor 1).
2. Pilih **Jenis perkara** (nomor 2): perdata, TUN, pidana, sengketa batas, eksekusi, keberatan ganti kerugian, atau lainnya.
3. Pilih **Forum** (nomor 3): Pengadilan Negeri, PTUN, Pengadilan Tinggi, Mahkamah Agung, Arbitrase, Mediasi, atau Kepolisian. Isi nama pengadilannya di kolom berikutnya.
4. Isi **Nomor perkara pengadilan** (nomor 4), lalu pilih unit layanan dan penanggung jawab.
5. Gulir ke bagian **Para pihak**:

![Bagian Para pihak](../gambar/aset/perkara-pihak.png)

6. Pilih **Kedudukan instansi** (nomor 1): penggugat, tergugat, turut tergugat, pemohon, atau termohon. Isi **Pihak lawan** (nomor 2).
7. Pilih **Kuasa hukum**. Kotak kiri (nomor 3) berisi advokat yang belum dipilih: klik namanya, lalu klik panah ke kanan (nomor 4). Nama pindah ke kotak kanan **Kuasa hukum terpilih** (nomor 5). Pada contoh, satu-satunya advokat sudah terpilih sehingga kotak kiri kosong. Untuk melepas, klik nama di kotak kanan lalu klik panah ke kiri.
8. Bagian **Objek**: pilih **Aset terkait** dengan cara yang sama, lalu isi nilai gugatan.
9. Bagian **Perkembangan**:

![Bagian Perkembangan](../gambar/aset/perkara-jadwal.png)

10. Pilih **Status** (nomor 1): Persiapan, Persidangan berjalan, Putusan tingkat pertama, Banding, Kasasi, Peninjauan kembali, Berkekuatan hukum tetap, Eksekusi, atau Selesai.
11. Pilih **Hasil** (nomor 2): Belum ada, Menang, Kalah, Damai, atau Gugur.
12. Di bawahnya, tambah baris **Jadwal sidang** (tanggal dan agenda) dan **Dokumen** perkara. Sistem mengingatkan petugas sebelum tanggal sidang.
13. Klik **Simpan**.

**Advokat / kuasa hukum** dicatat di menunya sendiri (saringan **Biro hukum internal** dan **Aktif**).

![Advokat](../gambar/aset/advokat.png)

<!-- akhir sisip -->

> Perkara hanya bisa Anda baca; perkara dikelola Petugas Hukum.

<!-- sisip: 30-aset-lahan.md#86-okupasi--perambahan -->

### 8.6 Okupasi & perambahan

![Daftar okupasi](../gambar/aset/okupasi-daftar.png)

Kotak **Aksi** (nomor 1) menjalankan perintah untuk baris yang dicentang, misalnya **Limpahkan ke perkara baru** (lihat langkah 8 di bawah).

Saringan: **Status**, **Cara ditemukan**, **Bentuk okupasi**, **Tingkat**, **Unit layanan / lokasi**. Kolom **Tanpa tindak lanjut** menandai kasus yang terlalu lama tidak ditangani.

Klik **Tambahkan Kasus okupasi / perambahan** (atau **Catat okupasi** dari halaman aset).

![Halaman okupasi](../gambar/aset/okupasi-detail.png)

1. Isi **Judul** kasus (nomor 1) dan pilih **Aset** yang diokupasi (nomor 2).
2. Pilih **Status** (nomor 3) dan **Tingkat** keparahan (nomor 4), lalu unit layanan dan penanggung jawab.
3. Bagian **Temuan**: isi tanggal ditemukan, **Cara ditemukan** (patroli, laporan masyarakat, perbandingan citra, drone, survei, analisis tumpang tindih), **Bentuk okupasi** (bangunan permanen/semi permanen, kebun, pagar/patok, galian/timbunan), nama pelaku, dan jumlah penghuni.
4. Bagian **Lokasi**: tandai titik dan gambar area di peta, lalu isi luas yang diokupasi.
5. Bagian **Bukti citra**: pilih citra sebelum dan sesudah, serta tautan pembanding.
6. Gulir ke **Tindakan penanganan** (nomor 1 pada gambar di bawah). Tambah satu baris untuk setiap langkah yang sudah dilakukan, berurutan: Verifikasi lapangan → Surat teguran I → II → III → Mediasi → Penertiban → Laporan polisi → Lahan kembali dikuasai.

![Tindakan penanganan](../gambar/aset/okupasi-tindakan.png)

7. Klik **Simpan**. Status kasus ikut berubah sesuai tindakan terakhir (Dilaporkan, Terverifikasi, Teguran I–III, Penertiban, Dilimpahkan ke perkara, Selesai / lahan kembali, Tidak terbukti).
8. Bila kasus harus dibawa ke pengadilan: di daftar okupasi, centang kasusnya, pilih aksi (nomor 1 pada gambar daftar) **Limpahkan ke perkara baru**, lalu klik **Jalankan**. Perkara baru dibuat dan ditautkan.

<!-- akhir sisip -->

<!-- sisip: 30-aset-lahan.md#87-pengaduan-masyarakat -->

### 8.7 Pengaduan masyarakat

Pengaduan masuk dari portal (`/portal/pengaduan/`), telepon/WhatsApp, surat, datang langsung, atau petugas lapangan. Pelapor menerima nomor pengaduan untuk dicek di portal.

![Daftar pengaduan](../gambar/aset/pengaduan-daftar.png)

Kotak **Aksi** (nomor 1) menjalankan perintah untuk baris yang dicentang, misalnya **Jadikan kasus okupasi** (lihat langkah 8 di bawah).

Klik nomor pengaduan untuk membukanya.

![Halaman pengaduan](../gambar/aset/pengaduan-detail.png)

1. Periksa **Saluran** masuknya (nomor 1) dan pilih **Kategori** (nomor 2).
2. Ubah **Status** (nomor 3) sesuai kemajuan: Diterima → Diverifikasi → Ditindaklanjuti → Selesai (atau Tidak dapat ditindaklanjuti).
3. Pilih petugas di **Ditugaskan kepada** (nomor 4). **Batas penyelesaian** (nomor 5) terisi otomatis dari kategori; ubah bila perlu.
4. Gulir ke bawah dan baca bagian **Pelapor** (nama, telepon, surel) dan **Pengaduan** (judul, uraian, lokasi, lampiran).
5. Di bagian **Terkait** (nomor 1 pada gambar di bawah), hubungkan pengaduan ke aset, proyek pengadaan, atau kasus okupasi.
6. Di bagian **Tindak lanjut** (nomor 2), isi **tanggapan** (terlihat oleh pelapor saat cek status di portal), **catatan internal**, dan tanggal selesai.

![Bagian Terkait dan Tindak lanjut](../gambar/aset/pengaduan-tindak-lanjut.png)

7. Klik **Simpan**.
8. Bila pengaduan berisi laporan penyerobotan lahan: di daftar pengaduan, centang pengaduannya, pilih aksi (nomor 1 pada gambar daftar) **Jadikan kasus okupasi**, lalu klik **Jalankan**.

Kolom **Lewat batas** di daftar menyala bila pengaduan melewati batas penyelesaian (diatur per **Kategori pengaduan** atau di pengaturan modul).

<!-- akhir sisip -->

<!-- sisip: 30-aset-lahan.md#88-lelang--seleksi-lahan -->

### 8.8 Lelang & seleksi lahan

![Daftar lelang](../gambar/aset/lelang-daftar.png)

Kotak **Aksi** (nomor 1) menjalankan perintah lelang (umumkan, tutup penawaran, tetapkan pemenang) untuk baris yang dicentang; caranya di **Menjalankan lelang** di bawah.

**Membuat lelang:** klik **Tambahkan Lelang / seleksi lahan**.

![Halaman lelang](../gambar/aset/lelang-detail.png)

1. Isi **Judul** (nomor 1).
2. Pilih **Metode** (nomor 2): **Lelang harga tertinggi** atau **Seleksi proposal (beauty contest)**.
3. Pilih objeknya: **Aset** (nomor 3), atau lahan alokasi di kolom berikutnya.
4. Tulis **Uraian** (nomor 4) dan syarat peserta di kolom di bawahnya.
5. Gulir ke bawah: isi **Nilai limit**, uang jaminan, **Penawaran dibuka** dan **Penawaran ditutup** (tanggal dan jam), serta status dan unit layanan. Lampirkan dokumen di bagian **Dokumen & arsip**.
6. Klik **Simpan**.

**Menjalankan lelang** dari daftar lelang (centang lelangnya, pilih aksi di nomor 1, lalu klik **Jalankan**):

1. Aksi **Umumkan di portal**: lelang tampil di `/portal/lelang/` dan peminat bisa mengirim penawaran.
2. Setelah batas waktu, aksi **Tutup penerimaan penawaran**.
3. Buka menu **Penawaran**. Ubah status tiap penawaran menjadi **Lolos evaluasi** atau **Gugur**.
4. Kembali ke daftar lelang, pilih aksi **Tetapkan pemenang (penawaran lolos tertinggi)**. Nama pemenang tampil di halaman lelang di portal.

![Daftar penawaran](../gambar/aset/penawaran.png)

<!-- akhir sisip -->

<!-- sisip: 30-aset-lahan.md#89-permukiman-kembali -->

### 8.9 Permukiman kembali

**Kawasan permukiman kembali** mencatat lokasi relokasi; kolom **Unit**, **Dihuni**, dan **Kosong** dihitung otomatis. **Unit / kavling permukiman kembali** mencatat setiap rumah/kavling dengan status hunian: Kosong, Dalam pembangunan, Dialokasikan (belum dihuni), Dihuni, serta **Rumah tangga terdampak** yang menempatinya.

![Kawasan permukiman kembali](../gambar/aset/permukiman-kawasan.png)

![Unit permukiman kembali](../gambar/aset/permukiman-unit.png)

<!-- akhir sisip -->

<!-- sisip: 30-aset-lahan.md#810-kepemilikan-pemangku-kepentingan-ahli-waris -->

### 8.10 Kepemilikan, pemangku kepentingan, ahli waris

**Pemangku kepentingan** mencatat instansi, tokoh masyarakat/adat, warga/pemilik, LSM, perusahaan, dan media, beserta **Pengaruh**, **Kepentingan**, **Sikap** (mendukung, netral, menolak, belum diketahui), dan riwayat pertemuan (rapat, sosialisasi, kunjungan, surat, telepon). Tombol **Matriks pengaruh × kepentingan** menampilkan peta strategi pendekatan.

![Pemangku kepentingan](../gambar/aset/pemangku.png)

![Matriks pengaruh × kepentingan](../gambar/aset/matriks-pemangku.png)

**Silsilah ahli waris** mencatat pewaris dan ahli warisnya (anak, suami/istri, cucu, saudara kandung, orang tua, lainnya). Klik tautan di kolom **Silsilah** untuk melihat pohon keluarga.

![Silsilah ahli waris](../gambar/aset/ahli-waris.png)

<!-- akhir sisip -->

<!-- sisip: 30-aset-lahan.md#811-survei-citra-lapisan-peta-fasilitator-urusan-instansi -->

### 8.11 Survei, citra, lapisan peta, fasilitator, urusan instansi

**Survei & pemetaan**

![Survei & pemetaan](../gambar/aset/survei.png)

Jenis survei: pengukuran batas, topografi, drone, inventarisasi, identifikasi pemilik, objek ganti kerugian, digitalisasi warkah. Status: Diajukan → Dijadwalkan → Berlangsung → Selesai. Setelah hasil ukur diunggah, centang surveinya dan pilih aksi **Terapkan batas hasil ukur ke aset** agar batas aset diperbarui.

**Citra satelit & foto udara**

![Daftar citra](../gambar/aset/citra-daftar.png)

Daftar ini mencatat pengadaan citra (diminta, dipesan, tersedia, batal), wahana (satelit, drone, pesawat), jenis data, dan penyedia. Isi URL ubin/WMS agar citra muncul di peta.

**Pembanding citra** menampilkan dua citra di satu peta:

![Pembanding citra](../gambar/aset/citra.png)

1. Pilih citra **Kiri (sebelum)** (nomor 1) dan **Kanan (sesudah)** (nomor 2).
2. Klik **Bandingkan** (nomor 3).
3. Geser penggeser (nomor 4) ke kiri dan kanan untuk membandingkan. Area kasus dan batas aset ditandai kuning.

**Lapisan peta referensi** (batas administrasi, kadaster, sungai, jalan, kawasan hutan, RTRW/RDTR, utilitas, dsb.) diunggah sekali lalu tampil di peta tematik. Centang **Tampil di pusat komando** agar muncul juga di peta komando.

![Lapisan peta referensi](../gambar/aset/lapisan-peta.png)

**Fasilitator & pendamping** (pendamping masyarakat, mediator, konsultan, penghubung instansi, penilai, surveyor berlisensi) dan **Urusan instansi pemerintah** (mutasi hak, cek sertipikat, pengukuran BPN, KKPR, PBG, persetujuan lingkungan, urusan pajak, dsb.; status Persiapan berkas → Diajukan → Diproses instansi → Selesai/Ditolak).

![Fasilitator](../gambar/aset/fasilitator.png)

![Urusan instansi pemerintah](../gambar/aset/urusan-instansi.png)

<!-- akhir sisip -->

<!-- sisip: 30-aset-lahan.md#812-dokumen--arsip-tugas-tim-laporan-lapangan -->

### 8.12 Dokumen & arsip, tugas, tim, laporan lapangan

**Dokumen & arsip**

![Dokumen & arsip](../gambar/aset/dokumen.png)

Unggah sertipikat, akta, putusan, surat, peta, foto, laporan, perjanjian, izin, dan bukti pajak. Untuk membaca teks pindaian, centang dokumen dan pilih aksi **Baca teks dokumen (OCR)**. Setelah terbaca, buka dokumen dan klik **Terapkan data ke aset** untuk mengisi kolom aset yang masih kosong. Teks hasil OCR juga ikut dicari di **Pencarian**.

**Tugas & perintah kerja**

![Daftar tugas](../gambar/aset/tugas.png)

Isi tugas: judul, jenis (survei, verifikasi, administrasi, hukum, patroli, pemeliharaan aset), **Prioritas** (Rendah, Normal, Tinggi, Mendesak), penerima, **Kontributor lapangan**, tenggat, Korwil, dan objek terkait. Status: Baru → Dikerjakan → Menunggu verifikasi / Menunggu pihak lain → Selesai (atau Batal). Tugas untuk petugas lapangan juga muncul di tab **Tugas** pusat komando.

**Tampilan Gantt** menampilkan tugas dan tonggak pengadaan pada garis waktu:

![Jadwal Gantt](../gambar/aset/gantt.png)

1. Isi **Dari** (nomor 1) dan **Sampai** (nomor 2).
2. Pilih **Tim** (nomor 3). Centang **Tugas saya saja** bila perlu.
3. Klik **Terapkan** (nomor 4).

**Tim internal** mengelompokkan petugas; kolom **Anggota** dan **Tugas terbuka** dihitung otomatis.

![Tim internal](../gambar/aset/tim.png)

**Laporan lapangan** dikirim petugas dari aplikasi lapangan (patroli rutin, temuan okupasi, kondisi aset, catatan survei, patok batas) beserta foto dan titik GPS. Bila berisi temuan penyerobotan, centang laporan dan pilih aksi **Jadikan kasus okupasi**.

![Laporan lapangan](../gambar/aset/laporan-lapangan.png)

<!-- akhir sisip -->

<!-- sisip: 30-aset-lahan.md#813-alat-analisis -->

### 8.13 Alat analisis

**Pembuat laporan:**

![Pembuat laporan](../gambar/aset/laporan.png)

1. Pilih **Data** (nomor 1): aset, pajak, transaksi, perkara, jadwal sidang, okupasi, survei, tugas, pengaduan, urusan instansi, lelang, hunian permukiman kembali, pemangku kepentingan, kontrak sewa, atau bidang pengadaan tanah. Dataset yang tidak boleh Anda lihat tidak muncul.
2. Saring dengan **Kata kunci** (nomor 2), **Status** (nomor 3), dan rentang tanggal **Dari** (nomor 4) sampai **Sampai** (nomor 5).
3. Centang **Kolom** yang ingin dimuat di laporan.
4. Klik **Tampilkan** (nomor 6) untuk melihat hasilnya di layar.
5. Klik **Ekspor Excel** (nomor 7), **Ekspor CSV**, atau **Ekspor PDF** untuk mengunduh.

**Tumpang tindih:** daftar aset yang batasnya saling beririsan (≥ 1 m²) dan aset yang beririsan dengan bidang pengadaan atau lahan alokasi. Irisan menandakan klaim ganda atau kesalahan ukur; perbaiki batas atau ajukan survei ulang.

![Tumpang tindih](../gambar/aset/tumpang-tindih.png)

**Pencarian:** ketik kata kunci lalu klik **Cari**. Sistem mencari kode, nama, nomor hak, NIB, pihak, dan isi teks dokumen hasil OCR di semua modul yang boleh Anda akses.

![Pencarian](../gambar/aset/cari.png)

**Asisten AI:**

![Asisten AI](../gambar/aset/asisten.png)

1. Ketik pertanyaan biasa di kotak pertanyaan (nomor 1), misalnya "sewa yang berakhir 90 hari lagi" atau "okupasi terbuka".
2. Klik **Tanya** (nomor 2).
3. Jawaban tampil di atas kotak pertanyaan, seperti gambar berikut.

![Jawaban asisten](../gambar/aset/asisten-jawab.png)

4. Baca ringkasan jawaban (nomor 1) dan tabel datanya. Klik **Buka** di ujung baris untuk membuka datanya.
5. Untuk mengunduh tabel, klik **Excel**, **PDF**, atau **CSV** di baris **Unduh laporan** (nomor 2).
6. Ketik pertanyaan lanjutan di kotak di bawahnya, atau klik **Mulai percakapan baru** (nomor 3) untuk topik lain.

Bila layanan AI belum diaktifkan Administrator, asisten tetap menjawab pertanyaan umum dengan pencocokan pola (sewa, okupasi, alokasi, pemantauan, sidang, pajak, tugas, pengaduan, perkara, keuangan, lokasi).

**Peta berbagi (tautan publik):** membuat tautan peta untuk pihak luar tanpa akun. Isi **Judul peta**, pilih **Aset ditampilkan**, **Bidang proyek pengadaan**, atau **Kawasan permukiman kembali**, centang **Tampilkan nama pemegang hak** bila boleh, isi **Berlaku sampai**, lalu simpan. Salin **Tautan publik** dan bagikan. Hapus centang **Aktif** untuk mematikan tautan. Kolom **Dilihat** menghitung kunjungan. Contoh tampilannya ada di [Bab 9](../31-aplikasi-lapangan.md#92-peta-berbagi).

![Peta berbagi](../gambar/aset/peta-berbagi.png)

<!-- akhir sisip -->

<!-- sisip: 30-aset-lahan.md#815-pertanyaan-umum -->

### 8.15 Pertanyaan umum

**Saya tidak melihat aset yang dibuat rekan.** Aset itu milik unit layanan lain. Minta Administrator memeriksa **Unit layanan / lokasi** aset atau akun Anda.

**Menu Penilaian/Pajak tidak ada.** Peran Anda (misalnya Petugas Hukum) tidak berhak, atau modulnya dimatikan di pengaturan.

**Citra tidak muncul di pembanding.** Citra belum punya URL ubin/WMS. Lengkapi di **Citra satelit & foto udara**.

<!-- akhir sisip -->

## Bagian B – Aplikasi lapangan dan peta berbagi

<!-- sisip: 31-aplikasi-lapangan.md#91-aplikasi-lapangan-asetlapangan -->

### 9.1 Aplikasi lapangan (`/aset/lapangan/`)

Aplikasi ringan di HP untuk mengirim **laporan lapangan** (patroli, temuan okupasi, kondisi aset, catatan survei, patok batas) lengkap dengan titik GPS dan foto. Aplikasi tetap bisa dipakai **tanpa sinyal**: laporan disimpan di HP dan dikirim otomatis saat sinyal kembali.

**Siapa memakai:** Petugas Lapangan dan Petugas Aset Lahan. Peran lain yang membuka alamat ini melihat pesan "tidak berhak".

#### Membuka dan memasang aplikasi

1. Di HP, buka `https://<alamat-simlahan>/aset/lapangan/`. Bila belum masuk, Anda diarahkan ke halaman masuk panel admin; masuk dengan nama pengguna dan kata sandi Anda.
2. Izinkan akses **lokasi** saat diminta browser. Titik biru di peta adalah posisi Anda.
3. Klik **Pasang** (bila muncul) agar aplikasi punya ikon sendiri di layar HP. Buka aplikasi sekali saat ada sinyal agar batas bidang tersimpan untuk dipakai luring.

Di komputer, formulir tampil di sebelah kanan peta:

![Aplikasi lapangan di komputer](../gambar/lapangan/aset-lapangan.png)

Bagian layar di HP:

![Aplikasi lapangan di HP](../gambar/lapangan/hp-lapangan.png)

Nomor pada gambar:

1. **Daring** / **Luring**: status sinyal. Saat **Luring**, laporan disimpan di HP dulu.
2. **Panduan**: membuka panduan peran Anda.
3. **Tombol lapisan**: pilih **Peta jalan**, **Citra satelit**, dan **Batas aset & okupasi**. Titik biru di peta adalah posisi Anda.
4. **GPS:** koordinat posisi Anda dan ketelitiannya (misalnya `±5 m`).
5. **Jenis laporan**.
6. **Catatan**.

#### Mengirim laporan

1. Tunggu sampai baris **GPS:** (nomor 4 pada gambar HP di atas) menampilkan koordinat dan ketelitian. Bila GPS tidak tersedia, ketuk peta untuk menandai titik.
2. Pilih **Jenis laporan** (nomor 5 pada gambar HP di atas): Patroli rutin, Temuan okupasi / perambahan, Kondisi aset, Catatan survei, atau Patok batas.
3. Tulis **Catatan** (nomor 6 pada gambar HP di atas): uraian temuan, kondisi patok, pihak yang ditemui.
4. Geser formulir ke atas untuk melihat bagian bawahnya:

![Bagian bawah formulir laporan](../gambar/lapangan/hp-lapangan-form.png)

5. Ketuk **Foto (opsional)** (nomor 1) untuk memotret atau memilih foto.
6. Bila lokasi laporan bukan posisi Anda sekarang, ketuk titik yang benar di peta, lalu centang **Pakai titik yang saya ketuk di peta** (nomor 2).
7. Ketuk **Simpan laporan** (nomor 3).
   - Saat daring: muncul "Laporan tersimpan, mengirim…" lalu "laporan terkirim".
   - Saat luring: muncul "Laporan tersimpan di perangkat; akan dikirim saat daring".
8. **Antrean kirim** (nomor 4) menunjukkan jumlah laporan yang belum terkirim. Setelah sinyal ada, ketuk **Kirim sekarang** (nomor 5). Laporan di antrean bisa dihapus dengan tombol hapus di barisnya.

Laporan yang terkirim masuk ke **Panel admin → Manajemen aset lahan → Laporan lapangan** (lihat [Bab 8.12](../30-aset-lahan.md#812-dokumen--arsip-tugas-tim-laporan-lapangan)). Petugas Aset dapat menjadikannya kasus okupasi.

#### Bila ada masalah

| Pesan | Yang harus dilakukan |
|---|---|
| Lokasi belum ada. Tunggu sinyal GPS atau ketuk titik di peta. | Tunggu beberapa detik di tempat terbuka, atau ketuk peta. |
| GPS tidak tersedia (izin lokasi ditolak) | Izinkan lokasi di pengaturan browser HP, lalu muat ulang. |
| Sesi masuk berakhir. Masuk lagi | Ketuk **Masuk lagi**. Laporan tetap tersimpan di HP. |
| Pengiriman tertunda; akan dicoba lagi saat sinyal stabil. | Tidak perlu apa-apa; laporan dikirim otomatis. |
| Batas bidang belum tersedia luring. | Buka aplikasi sekali saat ada sinyal. |

> Batas bidang di peta bersifat informatif dan bukan pengganti dokumen resmi pertanahan.

Tautan di bawah formulir (**⇄ Panel admin**, **⇄ Pusat Komando**, **⇄ Portal**) berpindah ke aplikasi lain tanpa masuk ulang. Laporan kegiatan harian, absen, dan tugas Korwil dikerjakan di **Pusat komando** ([Bab 10](../40-pusat-komando.md)), bukan di aplikasi ini.

<!-- akhir sisip -->

<!-- sisip: 31-aplikasi-lapangan.md#92-peta-berbagi -->

### 9.2 Peta berbagi

Peta berbagi adalah tautan peta **baca-saja** untuk pihak luar (misalnya peserta rapat koordinasi) tanpa akun. Tautan dibuat Petugas Aset Lahan di **Panel admin → Manajemen aset lahan → Peta berbagi (tautan publik)** (lihat [Bab 8.13](../30-aset-lahan.md#813-alat-analisis)).

![Peta berbagi](../gambar/portal/peta-berbagi.png)

Yang dilihat penerima tautan:

- Judul peta dan tanggal **Tautan berlaku sampai**.
- Batas aset berwarna sesuai status penguasaan (legenda di bawah peta), bidang pengadaan, atau kawasan permukiman kembali yang dipilih petugas.
- Klik bidang untuk melihat kode dan nama aset, status, luas, dan alas hak. Nama pemegang hak hanya tampil bila petugas mengizinkannya.
- Tombol lapisan di kanan atas untuk memilih **Peta jalan** atau **Citra satelit**.

Setelah lewat tanggal berlaku atau dimatikan petugas, tautan tidak bisa dibuka lagi.

<!-- akhir sisip -->

## Bagian C – Mengawasi tim di Pusat Komando

Klik **⇄ Pusat Komando** (nomor 7 pada gambar halaman awal). Anda melihat petugas dan Korwil di unit layanan Anda, tetapi tidak absen, tidak melapor kegiatan, dan tidak melihat NIK warga.

### Peta dan laporan tim

![Peta pusat komando untuk Petugas Aset](../gambar/komando/aset-peta.png)

Tab **Peta** menampilkan semua titik kegiatan, warga, dan temuan di wilayah unit layanan Anda.

![Tab Lapor untuk Petugas Aset (melihat laporan tim)](../gambar/komando/aset-lapor.png)

Tab **Lapor** untuk peran Anda hanya berisi **Laporan saya/tim**: daftar laporan petugas. Ketuk laporan untuk membaca isinya.

<!-- sisip: 40-pusat-komando.md#102-peta -->

### 10.2 Peta

Di komputer, peta tampil lebih lebar:

![Peta di komputer](../gambar/komando/peta-desktop.png)

Nomor pada gambar: (1) tombol alat peta, (2) kartu ringkasan, (3) tombol **Live**, (4) tombol **SOS**, (5) bilah tab.

Tombol alat di kanan peta (nomor 1), dari atas:

| Tombol | Fungsi |
|---|---|
| + / − | Perbesar / perkecil. |
| ⛶ Layar penuh | Peta memenuhi layar. |
| 📍 Lokasi saya | Memusatkan peta ke posisi Anda. |
| 📏 Ukur jarak | Ketuk titik awal, lalu titik berikutnya; jarak tampil di bawah. **Ulang** untuk mulai lagi. |
| 🛰️ Citra satelit | Mengganti peta dasar ke citra satelit. |
| 🎯 Gaya peta taktis | Tampilan peta gelap untuk operasi. |
| 🤖 AI Satelit | Tahan lalu seret untuk menggambar kotak area; AI menganalisis tutupan lahan dan bangunan di kotak itu (hanya bila layanan AI aktif). |
| 🖨️ Cetak / export peta | Lihat 10.2.2. |
| 🎙️ Perintah suara | Ucapkan perintah, misalnya "korwil A" untuk memusatkan peta ke Korwil A, atau nama warga/tempat untuk mencarinya. Perlu izin mikrofon (paling baik di Chrome). |
| 💬 Chat internal | Membuka chat. |
| 📜 Legenda & lapisan | Lihat 10.2.1. |
| 🔍 Cari (Ctrl+K) | Mencari warga, Korwil, tugas, atau perintah. Awali dengan `>` untuk perintah. |

Ketuk titik atau wilayah di peta untuk membuka rinciannya (warga, Korwil, bidang, titik uji, foto 360°).

#### 10.2.1 Legenda dan lapisan

1. Ketuk 📜 di tombol alat peta. Panel **Legenda** terbuka.

![Legenda](../gambar/komando/legenda-desktop.png)

2. Pilih **Warna titik warga** (nomor 1): Sikap (Pro / Kontra), Status lahan (sudah / belum dibebaskan), atau Kesesuaian RTRW.
3. Pilih **Warna wilayah Korwil** (nomor 2): warna Korwil, persentase Pro, persentase RTRW sesuai, atau persentase lahan sudah. Arti setiap warna tampil di bawahnya.
4. Gulir panel ke bawah sampai bagian **Lapisan**:

![Lapisan peta](../gambar/komando/legenda-lapisan.png)

5. Centang lapisan yang ingin ditampilkan (nomor 1), misalnya Batas Korwil, Warga terdata, Kegiatan (90 hari), Uji tanah, Petugas Live, SOS aktif, Temuan ilegal, Patroli SMART, Penguasaan lahan, Zona ancaman, Foto situs 360°, Uji tanah PLTS, serta lapisan dari modul lain (RTRW, aset lahan, okupasi, bidang pengadaan, lahan alokasi, hunian permukiman kembali, hasil survei, laporan lapangan). Hapus centang untuk menyembunyikannya.
6. Di bagian paling bawah, pilih **Peta dasar**: OpenStreetMap, Citra satelit (Esri), atau Topografi.
7. Ketuk ✕ untuk menutup panel.

#### 10.2.2 Cetak peta

1. Nyalakan dulu lapisan yang ingin dicetak (10.2.1).
2. Ketuk 🖨️ di tombol alat peta.

![Cetak peta](../gambar/komando/cetak-desktop.png)

3. Pilih **Korwil** (nomor 1), atau **Semua Korwil (wilayah kerja)**.
4. Pilih **Ukuran kertas** (nomor 2): A3, A2, A1, atau A0.
5. Pilih **Orientasi** (nomor 3): Lanskap atau Potret.
6. Ketuk **⬇ Export PNG** (nomor 4). Berkas gambar resolusi tinggi siap cetak terunduh.

#### 10.2.3 Mode Live dan SOS

**Live:** ketuk **🧭 Live** (nomor 2 pada gambar 10.1) untuk membagikan posisi Anda ke pusat komando selama bertugas. Jejaknya tersimpan (titik tiap ±1 menit atau 25 m) selama 60 hari dan bisa dilihat koordinator. Ketuk lagi untuk mematikan.

**SOS** (keadaan darurat):

1. Ketuk tombol **SOS** merah (nomor 3 pada gambar 10.1).

![Kirim SOS](../gambar/komando/hp-sos.png)

2. Tulis keadaan Anda di **Pesan (opsional)** (nomor 1), misalnya "dihadang massa" atau "butuh evakuasi".
3. Ketuk **KIRIM SOS** (nomor 2). Lokasi Anda dikirim ke koordinator, Administrator, dan petugas Korwil Anda lewat chat. Ketuk **Batal** (nomor 3) bila tidak jadi.
4. Tetap di lokasi aman bila memungkinkan. Koordinator menandai SOS sebagai ditangani atau selesai ([Bab 11.5](../41-panel-pusat-komando.md#115-sos)).

<!-- akhir sisip -->

<!-- sisip: 40-pusat-komando.md#106-tugas -->

### 10.6 Tugas

1. Ketuk tab **Tugas**.

![Tab Tugas](../gambar/komando/hp-tugas.png)

2. Saring daftar dengan tombol di nomor 1: **Saya** (tugas untuk Anda), **Tim**, **Verifikasi** (menunggu diverifikasi), **Terlambat**, atau **Semua**.
3. Setiap kartu tugas (nomor 2) menampilkan judul, status, nomor, prioritas, jenis, tenggat, Korwil, pemberi tugas, poin, dan garis progres.
4. Ketuk **📝 Lapor kegiatan** (nomor 3) untuk langsung membuat laporan kegiatan yang terkait dengan tugas itu (10.4).

**Mengerjakan tugas (petugas):**

1. Ketuk judul tugas. Rincian tugas terbuka:

![Rincian tugas](../gambar/komando/hp-tugas-detail.png)

2. Untuk tugas baru, ketuk **▶ Mulai kerjakan**. Status berubah menjadi **Dikerjakan**.
3. Geser **Progres** (nomor 1) sesuai kemajuan pekerjaan, lalu ketuk **Simpan** (nomor 2).
4. Setelah selesai, tulis **Catatan / ringkasan hasil** (nomor 3), lampirkan **Foto bukti** (nomor 4), biarkan **Sertakan lokasi GPS saat ini** tercentang (nomor 5), lalu ketuk **📤 Laporkan selesai** (nomor 6).
5. Bila terhambat, tulis kendalanya di catatan (wajib), lalu ketuk **⚠ Ada kendala** (nomor 7). Setelah kendala teratasi, ketuk **▶ Mulai / lanjut**.
6. Tugas yang dilaporkan selesai menunggu verifikasi pemberi tugas atau atasan. Anda tidak bisa memverifikasi tugas sendiri. **Riwayat** di bagian bawah mencatat setiap langkah.

**Tab Tugas bagi koordinator:**

![Tugas bagi koordinator](../gambar/komando/korwil-tugas.png)

Koordinator melihat dua tombol tambahan: **＋ Beri tugas** (nomor 1) untuk memberi tugas baru, dan saringan **Verifikasi** (nomor 2) untuk tugas yang menunggu verifikasi. Angka merah di **Verifikasi** adalah jumlah tugas yang menunggu.

**Memberi tugas (koordinator):**

1. Di tab **Tugas**, ketuk **＋ Beri tugas**. Formulir terbuka:

![Beri tugas](../gambar/komando/korwil-beri-tugas.png)

2. Isi **Judul tugas** (nomor 1) dan **Uraian / instruksi** (nomor 2).
3. Pilih **Penerima utama** (nomor 3).
4. Centang **Kontributor** (nomor 4) bila ada petugas lain yang membantu; mereka ikut mendapat poin.
5. Pilih **Jenis kegiatan** (nomor 5) dan **Prioritas** (nomor 6), lalu isi **Tenggat** (nomor 7).
6. Isi **Nilai poin (0–1.000.000)** (nomor 8).
7. Pilih **Korwil** (nomor 9), atau biarkan **Ikuti Korwil penerima**.
8. Ketuk **Kirim tugas** (nomor 10). Penerima mendapat pemberitahuan.

**Memverifikasi tugas (koordinator):**

1. Di tab **Tugas**, ketuk saringan **Verifikasi**.
2. Ketuk judul tugas yang dilaporkan selesai. Rincian tugas terbuka:

![Verifikasi tugas](../gambar/komando/korwil-tugas-verifikasi.png)

3. Periksa catatan, foto bukti, dan riwayatnya. Tulis **Catatan** bila perlu (nomor 1).
4. Ketuk **✔ Verifikasi selesai** (nomor 2). Poin tugas masuk KPI penerima, kontributor, dan pemberi tugas.
5. Bila belum sesuai, tulis catatan (wajib), lalu ketuk **↩ Kembalikan untuk revisi** (nomor 3). Untuk membatalkan tugas, ketuk **✕ Batalkan tugas** (nomor 4).

<!-- akhir sisip -->

<!-- sisip: 40-pusat-komando.md#107-kinerja-kpi -->

### 10.7 Kinerja (KPI)

1. Ketuk tab **Kinerja**.

![Tab Kinerja](../gambar/komando/hp-kinerja.png)

2. Pilih periode (nomor 1): Hari ini, Minggu ini, Bulan ini, Bulan lalu, Kuartal ini, atau Tahun ini.
3. Baca skor Anda di lingkaran (nilai A–D dan angkanya). Skor adalah gabungan kehadiran, kegiatan, dan tugas sesuai bobot di pengaturan. Kartu di bawahnya merinci kehadiran, tepat waktu, kegiatan dibanding target, warga dikunjungi, tugas tepat waktu, dan tugas terlambat.
4. Gulir ke bawah untuk **Kalender** aktivitas (nomor 2), grafik **Kegiatan harian**, **Poin usaha harian**, **Profil kinerja**, **Aktivitas 90 hari**, dan tombol **🗺️ Lihat sebaran di peta**.
5. Gulir sampai paling bawah:

![Bagian bawah Kinerja](../gambar/komando/hp-kinerja-bawah.png)

6. **Tugas terbuka** (nomor 1) dan **Kegiatan terakhir** (nomor 2) merangkum pekerjaan Anda.
7. Ketuk **Susun wawasan** (nomor 3) untuk ringkasan kekuatan, kelemahan, dan saran.

Koordinator dan atasan punya kotak tambahan di tab Kinerja:

![Kinerja bagi koordinator](../gambar/komando/korwil-kinerja.png)

Pilih periode (nomor 1), lalu pilih petugas lain di kotak kedua (nomor 2) untuk melihat kinerjanya.

<!-- akhir sisip -->

<!-- sisip: 40-pusat-komando.md#beranda -->

### Beranda

![Beranda](../gambar/komando/hp-beranda.png)

1. Ketuk **↻ Muat ulang** (nomor 1) untuk data terbaru. Angka hanya dari wilayah yang boleh Anda lihat.
2. Kartu atas: warga terdata, persentase mendukung, lahan dilepas, dan persentase sesuai RTRW.
3. **Anomali & peringatan** (nomor 2): hal yang perlu ditindaklanjuti, misalnya Korwil dengan warga kontra tinggi, tugas lewat tenggat, atau laporan harian belum ditinjau. Ketuk baris untuk melihat rinciannya.
4. **Skor risiko Korwil** (nomor 3): dari persentase warga kontra (minimal 5 warga bersikap): ≥60% kritis, ≥40% tinggi, ≥20% sedang.
5. Gulir ke bawah untuk **Sikap warga**, **Tren dukungan (12 pekan)**, **Per Korwil** (Warga/target, Sikap, Pro, Lepas, Kegiatan 7 hari; ketuk baris untuk detail Korwil), **Kegiatan 7 hari**, dan **Uji tanah**.

Di komputer, Beranda tampil di panel kanan peta:

![Beranda di komputer](../gambar/komando/beranda-desktop.png)

<!-- akhir sisip -->

<!-- sisip: 40-pusat-komando.md#peta--spasial -->

### Peta & spasial

![Peta & spasial](../gambar/komando/hp-spasial.png)

Pilih bagian di nomor 1: **Penguasaan lahan**, **Tumpang tindih**, **Audit RTRW**, **Peta panas**, **Jejak GPS** (koordinator), **Zona ancaman**, atau **Foto 360°**.

**Penguasaan lahan** (tampil pertama):

1. Saring per Korwil (nomor 2) dan status (nomor 3: belum atau sudah dikuasai), lalu pilih urutan (nomor 4): Prioritas tertinggi, Terluas, atau Nomor.
2. Cari bidang dengan nomor, nama, atau pemilik (nomor 5).
3. Kartu ringkasan menampilkan jumlah bidang, luas yang sudah dan belum dikuasai. **Skor prioritas** = 10 poin/ha × luas efektif × bobot zona × bobot urgensi.
4. Ketuk bidang di daftar untuk **Perbarui penguasaan**.
5. Untuk menambah bidang atau hasil penguasaan dari berkas, ketuk **⬆ Impor KML/KMZ** (nomor 6). Bidang dicocokkan otomatis dari namanya.

Di komputer, panel ini tampil di kanan peta:

![Peta & spasial di komputer](../gambar/komando/spasial-desktop.png)

**Tumpang tindih:**

![Tumpang tindih](../gambar/komando/spasial-tumpang.png)

1. Ketuk **Tumpang tindih**.
2. Pilih **Lapisan A** (nomor 1) dan **Lapisan B** (nomor 2), misalnya RTRW dan bidang penguasaan. Pilih lapisan yang sama untuk mencari bidang yang saling tumpang tindih.
3. Ketuk **Analisis** (nomor 3). Luas irisan dan daftar pasangan tampil di bawah.
4. Ketuk **⬇ CSV** (nomor 4) untuk mengunduh hasilnya, atau **🗺️ Tampilkan irisan di peta** (nomor 5).

**Audit RTRW:**

![Audit RTRW](../gambar/komando/spasial-audit.png)

1. Ketuk **Audit RTRW**. Audit mencocokkan titik warga dengan lapisan tata ruang, hutan, dan kawasan proyek.
2. Pilih Korwil (nomor 1), lalu ketuk **Jalankan audit** (nomor 2).
3. Hasil tampil per kategori dan **Per Korwil** (nomor 4), lalu daftar **Perlu ditindaklanjuti**. Ketuk **⬇ CSV** (nomor 3) untuk mengunduh, atau **🗺️ Tampilkan hasil di peta**.

**Peta panas:**

![Peta panas](../gambar/komando/spasial-panas.png)

1. Ketuk **Peta panas**.
2. Pilih sumber data (nomor 1): Sebaran kegiatan, Jejak GPS petugas, atau Sebaran warga terdata.
3. Pilih periode (nomor 2).
4. Ketuk **Tampilkan di peta** (nomor 3). Peta diwarnai per sel ±250 m; makin pekat makin banyak data.

**Jejak GPS** (koordinator dan pimpinan):

![Jejak GPS](../gambar/komando/korwil-spasial-jejak.png)

1. Ketuk **Jejak GPS**.
2. Pilih tanggal (nomor 1). Kotak petugas (nomor 2) berisi petugas yang punya jejak pada tanggal itu; pilih salah satu.
3. Ketuk **Tampilkan** (nomor 3). Peta menampilkan jalurnya: titik hijau awal, titik merah akhir.

![Jejak GPS di peta](../gambar/komando/korwil-spasial-jejak-peta.png)

**Zona ancaman** (koordinator):

![Zona ancaman](../gambar/komando/korwil-spasial-ancaman.png)

1. Ketuk **Zona ancaman**.
2. Isi **Nama zona** (nomor 1), pilih **Tingkat** (nomor 2: rendah, sedang, tinggi, kritis), dan isi **Radius (m)** (nomor 3).
3. Pilih **Korwil** (nomor 4), atau biarkan otomatis dari lokasi.
4. Titik pusat zona memakai GPS Anda. Untuk titik lain, ketuk titiknya di peta lalu centang **Pakai titik yang diketuk di peta** (nomor 5).
5. Isi **Keterangan** (nomor 6), lalu ketuk **Simpan zona** (nomor 7).

**Foto 360°:**

![Foto 360°](../gambar/komando/spasial-foto.png)

1. Ketuk **Foto 360°**.
2. Isi **Judul** (nomor 1) dan **Tanggal pengambilan** (nomor 2).
3. Pilih foto panorama equirectangular, JPG/PNG maks. 20 MB (nomor 3).
4. Lokasi foto memakai GPS Anda, atau centang **Pakai titik yang diketuk di peta** (nomor 4) setelah mengetuk titiknya.
5. Isi **Keterangan** bila perlu, lalu ketuk **Unggah** (nomor 5).
6. Pada daftar foto, ketuk **◉ Lihat 360°** (nomor 6) untuk memutar foto, atau **📍 Fokus** untuk melihat lokasinya.

<!-- akhir sisip -->

<!-- sisip: 40-pusat-komando.md#persetujuan -->

### Persetujuan

Semua yang menunggu keputusan Anda ada di satu tempat. Petugas biasa melihat halaman ini kosong.

![Persetujuan](../gambar/komando/korwil-persetujuan.png)

1. Buka **Menu → Persetujuan**.
2. **Izin / cuti** anggota: ketuk **Setujui** (nomor 1) atau **Tolak** (nomor 2).
3. **Verifikasi tugas**: ketuk **Periksa & verifikasi** (nomor 3) untuk membuka rincian tugas, lalu verifikasi seperti di 10.6.
4. **Laporan harian masuk**: ketuk **Tinjau** (nomor 4) untuk membukanya.
5. Konfirmasi dampak tinggi (Kegiatan lainnya) juga muncul di sini dengan tombol **Konfirmasi dampak**.
6. **Riwayat keputusan (30 hari)** tampil di bawah.

<!-- akhir sisip -->

<!-- sisip: 40-pusat-komando.md#laporan-harian-berjenjang -->

### Laporan harian berjenjang

Laporan harian dikirim ke **atasan langsung** (diatur di **Jabatan & atasan petugas**, [Bab 11.8](../41-panel-pusat-komando.md#118-jabatan-tugas-dan-laporan-harian)), lalu dirangkum ke atas sampai pimpinan. Baris **Posisi Anda** di atas menunjukkan jabatan Anda dan ke mana laporan dikirim.

**Membuat dan mengirim laporan harian:**

1. Buka **Menu → Laporan harian**.

![Laporan harian](../gambar/komando/hp-laporan-harian.png)

2. Pastikan bagian **Buat** aktif (nomor 1). Bagian lain: **Masuk** (laporan dari bawahan), **Lacak** (posisi laporan 14 hari terakhir), dan **Rekap Excel**.
3. Pilih rentang kegiatan (nomor 2): Hari ini sampai 31 hari. Kegiatan yang belum pernah dilaporkan tampil tercentang di bawahnya; hapus centang yang tidak ingin dimasukkan.
4. Ketuk **✨ Susun otomatis** (nomor 3). **Isi laporan** (nomor 4) terisi dari kegiatan yang dicentang.
5. Periksa dan sunting **Isi laporan**: kegiatan, temuan, kendala, dan rencana besok.
6. Tambah **Lampiran (maks. 10 berkas)** bila perlu (nomor 5).
7. Ketuk **📤 Kirim ke atasan** (nomor 6). Laporan yang dikembalikan atasan tampil di **Perlu revisi dari Anda**; perbaiki lalu kirim lagi.

**Merangkum laporan bawahan (koordinator dan atasan):**

![Laporan harian koordinator](../gambar/komando/korwil-laporan-harian.png)

1. Angka merah pada **Masuk** (nomor 1) menunjukkan laporan bawahan yang belum ditinjau. Ketuk **Masuk** untuk membacanya. Dari sana, laporan bisa dikembalikan dengan **↩ Kembalikan untuk revisi** (catatan wajib).
2. Di bagian **Buat**, laporan bawahan yang belum dirangkum tampil di **Laporan bawahan yang dirangkum** (nomor 2), sudah tercentang. Ketuk **Buka** untuk membaca isinya.
3. Ketuk **✨ Susun otomatis** (nomor 3) agar kegiatan Anda dan laporan bawahan tersusun menjadi satu laporan, sunting, lalu **📤 Kirim ke atasan**.
4. Pimpinan puncak (tanpa atasan) menandai laporan dengan **✔ Tandai terpilih selesai ditinjau** di bagian **Masuk**.

**Rekap Excel:** ketuk **Rekap Excel**, pilih **Periode**, **Korwil**, dan **Jenis kegiatan**, lalu **⬇ Unduh Excel** (rekap kegiatan, ringkasan per Korwil/jenis/petugas, absensi, dan tugas).

<!-- akhir sisip -->

<!-- sisip: 40-pusat-komando.md#alat--tiket -->

### Alat & tiket

![Alat & tiket](../gambar/komando/hp-alat.png)

Pilih alat di nomor 1: **Tiket & masukan**, **OCR dokumen**, **AI dokumen → laporan**, **Sinkron Excel**, dan bagi koordinator **Audit data**. Bila layanan AI aktif, ada juga **AI foto lapangan**.

**Mengirim tiket (laporan galat, gangguan, atau usulan):**

1. Pilih **Kategori** (nomor 2): galat aplikasi, gangguan layanan, saran fitur, ulasan, atau lainnya.
2. Pilih **Prioritas** (nomor 3): Normal, Tinggi, atau Kritis.
3. Isi **Judul** (nomor 4) dan **Deskripsi** (nomor 5): apa yang terjadi, di menu mana, dan langkah untuk mengulanginya.
4. Lampirkan tangkapan layar bila ada (nomor 6).
5. Ketuk **Kirim tiket** (nomor 7). Daftar tiket Anda dan statusnya tampil di bawah. Tiket yang selesai memberi poin untuk pengirim.

**OCR dokumen** (membaca teks dari foto atau PDF):

![OCR dokumen](../gambar/komando/alat-ocr.png)

1. Ketuk **OCR dokumen**.
2. Pilih foto atau PDF, maks. 20 MB (nomor 1).
3. Ketuk **Baca teks** (nomor 2). Teks hasil bacaan tampil dan bisa disalin.

**AI dokumen → laporan:**

![AI dokumen](../gambar/komando/alat-dokumen.png)

1. Ketuk **AI dokumen → laporan**.
2. Pilih dokumen: PDF, Word, Excel, CSV, TXT, atau foto (nomor 1).
3. Isi **Fokus analisis** bila perlu (nomor 2), misalnya "capaian per Korwil".
4. Ketuk **Analisis** (nomor 3). Hasilnya berupa ringkasan, temuan utama, data kunci, dan rekomendasi. Tanpa layanan AI, yang tampil hanya profil data dokumen.

**AI foto lapangan** (bila AI aktif): unggah foto lapangan atau drone, isi **Konteks**, lalu ketuk **Analisis foto**. AI menandai pembukaan lahan, bangunan, kebun, air, akses, dan alat berat. Wajah orang tidak dianalisis.

**Sinkron Excel:**

![Sinkron Excel](../gambar/komando/alat-sinkron.png)

1. Ketuk **Sinkron Excel**.
2. Ketuk **⬇ Unduh Excel lengkap** (nomor 1): ringkasan Korwil, bidang lahan, titik uji PLTS, dan tiket.
3. Setelah lembar "Uji tanah PLTS" diedit, ketuk **⬆ Impor progres uji PLTS** (nomor 2) dan pilih berkasnya.

**Audit data** (koordinator):

![Audit data](../gambar/komando/korwil-alat-audit.png)

1. Ketuk **Audit data**, lalu **Jalankan audit data** (nomor 1).
2. Hasilnya tampil di bawah: titik tanpa koordinat atau di luar wilayah, bidang ganda, warga tanpa lokasi, kegiatan tanpa GPS, dan petugas tanpa Korwil, masing-masing dengan contoh datanya.

**Cek perangkat:** di bagian bawah **Alat & tiket**, ketuk **Periksa perangkat** untuk memeriksa koneksi internet, antrean luring, penyimpanan luring, mode aplikasi luring, izin lokasi GPS, dan ruang penyimpanan terpakai di HP Anda.

<!-- akhir sisip -->

> Anda bisa mengirim tiket & masukan serta memakai OCR, AI dokumen, AI foto, dan sinkron Excel. Audit data dan perubahan titik uji tanah PLTS tidak tersedia untuk peran Anda.

<!-- sisip: 40-pusat-komando.md#peringkat-tim -->

### Peringkat tim

![Peringkat tim](../gambar/komando/hp-peringkat.png)

1. Pilih periode (nomor 1). Koordinator dan atasan juga bisa memilih Korwil dan tingkat, serta tombol **Semua**, **10 teratas**, atau **10 terbawah**.
2. Kartu menampilkan jumlah petugas dinilai, rata-rata skor, dan sebaran nilai A–D. Setiap baris berisi peringkat, nama, skor, dan lencana (misalnya Hadir penuh, Selalu tepat waktu). Kolom tren membandingkan posisi dengan periode sebelumnya.
3. Ketuk **⬇ Excel** (nomor 2) untuk mengunduh.
4. Ketuk **Susun wawasan** di bagian **Wawasan tim** untuk ringkasan siapa yang menonjol dan siapa yang perlu didampingi.

![Peringkat di komputer](../gambar/komando/peringkat-desktop.png)

<!-- akhir sisip -->

## Bila ada kendala

- **Menu atau tombol yang disebut di buku ini tidak ada di layar Anda.** Peran Anda memang tidak memerlukannya (lihat **Batas akses** di atas). Bila Anda membutuhkannya untuk pekerjaan, minta Administrator menambahkan peran yang sesuai.
- **Pesan "Tidak berhak" atau "Anda tidak berwenang melihat data ini".** Data itu di luar hak peran Anda, bukan kerusakan sistem.
- **Lupa kata sandi.** Hubungi superuser SimLahan untuk dibuatkan sandi baru, lalu ganti sandi itu setelah masuk (klik nama Anda → **Ganti sandi**, atau buka `/akun/sandi/`).
- **Terlalu banyak percobaan masuk.** Tunggu beberapa menit, lalu coba lagi dengan sandi yang benar.
- **Ringkasan peran di dalam aplikasi.** Isi bagian *Ringkasan peran* di atas juga bisa dibuka kapan saja lewat **Panduan peran** (`/akun/panduan/`).
