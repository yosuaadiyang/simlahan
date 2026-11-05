# Buku peran: Petugas Hukum

Buku ini untuk **Petugas Hukum**: petugas yang menangani perkara, sidang, okupasi, pengaduan, dan dokumen hukum terkait aset lahan. Buku ini berisi semua langkah kerja peran Anda, lengkap dengan gambar, sehingga cukup dibaca sendiri. Dasar penggunaan yang berlaku untuk semua peran (mengenal layar, ganti sandi, memakai di HP) ada di [Bab 2](../02-dasar-penggunaan.md).

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

Setelah masuk, Anda langsung melihat daftar **Perkara & litigasi** di panel admin:

![Halaman awal Petugas Hukum](../gambar/peran/hukum-beranda.png)

Nomor pada gambar:

1. **Saring menu**: ketik sebagian nama menu (misalnya *tagihan*) untuk menemukannya cepat di menu samping.
2. **Tambahkan Perkara**: mencatat perkara baru.
3. **Kotak cari**: ketik nomor perkara atau pokok perkara, lalu klik **Cari**. Panel **Filter** di kanan menyaring berdasarkan status dan jenis perkara.
4. **Nomor internal perkara** (misalnya *PRK-2026-0001*): klik untuk membuka perkara.
5. **Panduan peran**: ringkasan peran Anda.
6. **Keluar**: mengakhiri sesi di semua aplikasi petugas pada perangkat ini.

### Beranda panel admin

Klik **Administrasi SimLahan** di kiri atas untuk membuka beranda panel admin. Isinya kotak per modul yang boleh Anda buka:

![Beranda panel admin Petugas Hukum](../gambar/peran/hukum-panel.png)

Anda melihat modul **Dokumen & perizinan** dan **Manajemen aset lahan**. Tautan **Lihat** hanya membaca; **Ubah** dan **Tambah** berarti Anda boleh mengubah atau menambah data itu. Cara memakai halaman daftar dan formulir panel admin dijelaskan di [Bab 2.4](../02-dasar-penggunaan.md#24-mengenal-layar-panel-admin).

<!-- awal: dibuat dari backend/users/role_guide.py; perbarui dengan: cd backend && python manage.py panduan_buku -->

## Ringkasan peran

Menangani perkara dan sidang terkait aset lahan.

- **Cara masuk:** Alamat utama SimLahan (`/`) atau langsung di panel admin (`/admin/`); satu kali masuk berlaku untuk keduanya.
- **Halaman awal:** Panel admin → Perkara.
- **Akun latihan** (hanya di sistem latihan berisi data contoh): `contoh.hukum`

### Menu yang Anda lihat

- Panel admin, Manajemen aset lahan: perkara, advokat & jadwal sidang, dokumen, okupasi, pengaduan, urusan instansi, tugas, dasbor & peta
- Panel admin, Dokumen & Perizinan: Dasbor dokumen, Pemanfaatan lahan, Dokumen perizinan, Dokumen tanda tangan, Templat dokumen, Permintaan unduh

### Yang bisa Anda lakukan

- Mengelola perkara, advokat, jadwal sidang, dan dokumen perkara.
- Menindaklanjuti okupasi dan pengaduan; mengelola urusan instansi dan tugas.
- Membaca aset, kepemilikan, pemangku kepentingan, dan survei.
- Menyusun templat dan blok isi, membuat dan mengirim dokumen tanda tangan (kontrak, perjanjian), serta membaca dokumen perizinan.
- Dokumen tanda tangan: kolom isian penerima (`{{ kolom.<kunci> }}`: teks, tanggal, angka, centang, pilihan, paraf, lampiran), kode akses tambahan, tanda tangan langsung di hadapan petugas (bukti identitas tercatat), ganti penerima yang belum bertindak, cap tanda tangan pada posisi PDF, dan kirim massal dari daftar Pemanfaatan lahan (aksi **Kirim dokumen tanda tangan massal**).
- Mengajukan permintaan unduh dokumen. Mengunduh dokumen selalu lewat permintaan unduh yang disetujui orang lain; setiap unduhan diberi tanda air dan tercatat.

### Batas akses

- Tidak melihat penilaian, pajak, transaksi, dan peta berbagi.
- Tidak memverifikasi dokumen perizinan dan tidak menyetujui permintaan unduh.
- Tidak membuka pusat komando, aplikasi lapangan, atau modul lain.

<!-- akhir: blok role_guide.py -->

## Urutan kerja Anda

1. Kelola perkara, para pihak, jadwal sidang, dan dokumen perkara ([8.5 Perkara & litigasi](#85-perkara--litigasi)). Sistem mengingatkan sebelum sidang.
2. Tindak lanjuti okupasi (limpahkan ke perkara bila perlu) dan pengaduan ([8.6 Okupasi & perambahan](#86-okupasi--perambahan), [8.7 Pengaduan masyarakat](#87-pengaduan-masyarakat)).
3. Kelola urusan instansi pemerintah dan tugas ([8.11 Survei, citra, lapisan peta, fasilitator, urusan instansi](#811-survei-citra-lapisan-peta-fasilitator-urusan-instansi), [8.12 Dokumen & arsip, tugas, tim, laporan lapangan](#812-dokumen--arsip-tugas-tim-laporan-lapangan)).
4. Susun templat, lalu buat dan kirim dokumen tanda tangan kontrak atau perjanjian ([7.5 Templat dokumen dan pustaka konten](#75-templat-dokumen-dan-pustaka-konten), [7.4 Dokumen tanda tangan elektronik](#74-dokumen-tanda-tangan-elektronik)).
5. Untuk mengunduh berkas asli, ajukan permintaan unduh ([7.7 Permintaan unduh](#77-permintaan-unduh)).

## Bagian A – Perkara, okupasi, dan pengaduan

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

> Survei, citra, dan lapisan peta hanya bisa Anda baca. Yang Anda kelola di bagian ini: **Urusan instansi pemerintah**.

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

### Halaman tugas

![Halaman tugas / perintah kerja](../gambar/aset/tugas-detail.png)

> Penilaian, pajak, transaksi, dan peta berbagi tidak tersedia untuk peran Anda.

## Bagian B – Templat dan dokumen tanda tangan

<!-- sisip: 22-dokumen-perizinan.md#71-dasbor-dokumen--perizinan -->

### 7.1 Dasbor dokumen & perizinan

![Dasbor dokumen & perizinan](../gambar/dokumen/dasbor.png)

Buka **Dokumen & perizinan → Dasbor dokumen & perizinan**. Baris tombol di atas (**Dasbor, Pemanfaatan lahan, Dokumen perizinan, Tanda tangan elektronik, Templat, Permintaan unduh, Jejak aktivitas**) adalah jalan pintas ke tiap daftar.

Kartu angka di atas:

- **Pemanfaatan lahan aktif**, **Dokumen wajib belum lengkap**, **Menunggu verifikasi**.
- **Izin habis ≤ 30 hari · ≤ 90 hari** dan **Izin kedaluwarsa**.
- **Menunggu tanda tangan** (beserta jumlah selesai bulan ini dan rata-rata hari penyelesaian).
- **Permintaan unduh menunggu keputusan Anda** dan **Unduhan 30 hari**.

Panel di bawahnya:

- **Dokumen perizinan per status**: Belum diurus, Sedang diurus, Menunggu verifikasi, Perlu perbaikan, Terverifikasi, Kedaluwarsa, Tidak wajib.
- **Antrean verifikasi**: dokumen yang sudah diunggah pemegang hak dan menunggu diperiksa. Klik judulnya untuk langsung memeriksa.
- **Izin segera habis (≤ 60 hari)**: tanggal merah berarti perlu segera diperpanjang.
- **Pemanfaatan aktif per skema**, **Dokumen tanda tangan per status**, dan **Aktivitas terbaru** (gulir ke bawah).

Gulir sedikit ke bawah untuk melihat panel-panel itu:

![Panel antrean dan izin segera habis](../gambar/dokumen/dasbor-antrean.png)

- **Antrean verifikasi** (nomor 1): klik judul dokumen untuk langsung memeriksanya (lihat 7.3).
- **Izin segera habis** (nomor 2): tanggal merah di kanan adalah tanggal izin berakhir. Hubungi pemegang hak agar segera memperpanjang.

<!-- akhir sisip -->

<!-- sisip: 22-dokumen-perizinan.md#74-dokumen-tanda-tangan-elektronik -->

### 7.4 Dokumen tanda tangan elektronik

Dokumen tanda tangan dipakai untuk kontrak, berita acara, surat pernyataan, dan dokumen lain yang perlu ditandatangani atau disetujui pihak lain. Nomornya berformat `DOK-2026-00001`.

![Daftar dokumen tanda tangan](../gambar/dokumen/ttd-daftar.png)

Alur status:

```
Draf → (Menunggu persetujuan internal → Disetujui, siap dikirim) → Dikirim → Dilihat penerima → Selesai
                                                                  ↘ Ditolak penerima / Kedaluwarsa / Dibatalkan
```

Tahap persetujuan internal hanya ada bila **Wajib persetujuan internal sebelum dikirim** dicentang.

#### Langkah 1 – Buat draf

![Formulir dokumen tanda tangan baru](../gambar/dokumen/ttd-tambah.png)

1. Buka **Dokumen tanda tangan**, lalu klik **Tambahkan Dokumen tanda tangan**. Cara lain: klik **Buat dokumen tanda tangan** di halaman pemanfaatan lahan atau di halaman templat.
2. Isi **Judul dokumen** (nomor 1).
3. Pilih isi dokumen, salah satu saja:
   - **Templat isian** (nomor 2): isi disusun dari templat dan masih bisa disunting.
   - **Atau unggah PDF** (nomor 3): klik **Pilih File** dan pilih PDF yang sudah jadi (maksimal 20 MB).
4. Pilih **Pemanfaatan lahan** (nomor 4): ketik nomor atau nama kegiatan, lalu klik pilihannya. Data pemegang hak dan lahan dipakai untuk isian otomatis, dan pemegang hak langsung ditambahkan sebagai penanda tangan.
5. Klik **Buat draf** (nomor 5). Halaman draf terbuka.

#### Langkah 2 – Lengkapi draf

![Halaman draf dokumen tanda tangan](../gambar/dokumen/ttd-draf.png)

Bagian atas halaman draf menampilkan status **Draf** dan ringkasan penerima. Periksa dan lengkapi:

1. **Judul dokumen** (nomor 2) dan **Pemanfaatan lahan** (nomor 3).
2. Bila dokumen ini untuk memenuhi satu dokumen perizinan, pilih di **Untuk dokumen perizinan** (nomor 4). Setelah selesai ditandatangani, PDF-nya otomatis menjadi versi baru dokumen perizinan itu.
3. Gulir ke bagian **Isi**. Sunting **Isi dokumen** dengan bilah alat editor bila perlu. Isian otomatis seperti nama pemegang hak dan kode lahan sudah terisi sendiri.
4. Gulir ke bagian **Pengiriman**:

![Bagian Pengiriman](../gambar/dokumen/ttd-draf-pengiriman.png)

5. Tulis **Pesan untuk penerima** (nomor 1). Pesan ini ikut di surel undangan.
6. Atur **Batas tanda tangan** (nomor 2), yaitu tanggal terakhir penerima boleh bertindak.
7. Atur **Pengingat setiap (hari)** (nomor 3). Isi 0 bila tidak perlu pengingat otomatis.
8. Centang **Wajib persetujuan internal sebelum dikirim** (nomor 4) bila dokumen harus disetujui pejabat lain sebelum dikirim.
9. Pilih **Sifat dokumen** (nomor 5): **Biasa** atau **Rahasia**. Unduhan dokumen rahasia hanya dapat disetujui Administrator.
10. Gulir ke bagian **Penerima (urutan tanda tangan)**. Isi satu baris per orang. Tabelnya lebar; geser ke kanan untuk melihat semua kolom.

![Kolom penerima: urutan, peran, tindakan](../gambar/dokumen/ttd-draf-penerima.png)

11. **Urutan** (nomor 1): penerima dengan urutan sama bertindak bersamaan; urutan berikutnya menunggu yang sebelumnya selesai.
12. **Peran** (nomor 2), misalnya "Pemegang hak" atau "Pejabat penandatangan".
13. **Tindakan** (nomor 3): **Menandatangani**, **Menyetujui**, atau **Menerima salinan**.

![Kolom penerima: akun dan nama](../gambar/dokumen/ttd-draf-penerima-2.png)

14. **Akun** (nomor 4): pilih akun bila penerima punya akun SimLahan atau portal. Penerima berakun wajib masuk dulu sebelum menandatangani.
15. **Nama** (nomor 5) penerima.

![Kolom penerima: surel, tanda tangan langsung, kode akses](../gambar/dokumen/ttd-draf-penerima-3.png)

16. **Surel** (nomor 6): alamat tujuan undangan.
17. **Tanda tangan langsung** (nomor 7): centang bila penerima menandatangani di perangkat petugas setelah identitasnya diperiksa, misalnya warga tanpa surel. Surel undangan tidak dikirim.
18. **Kode akses** (nomor 8, opsional): kode tambahan yang Anda sampaikan lewat telepon. Isi `-` untuk menghapus kode yang ada.
19. Khusus PDF unggahan, kolom di kanannya menentukan letak gambar tanda tangan di PDF: **Halaman cap TTD** (1 = halaman pertama, -1 = terakhir), **Posisi kiri (%)**, **Posisi atas (%)**, dan **Lebar cap (%)**.
20. Untuk penerima berikutnya, klik **Tambahkan Penerima dokumen lagi**.
21. Bila penerima perlu mengisi sesuatu, isi tabel **Kolom isian penerima** di bawahnya: **Kunci**, **Label**, **Jenis** (Teks singkat, Teks panjang, Tanggal, Angka, Kotak centang, Pilihan, Paraf, Lampiran berkas), **Diisi oleh**, dan **Wajib**. Di isi dokumen, tulis `{{ kolom.<kunci> }}` di tempat isian itu harus muncul.
22. Klik **Simpan dan terus mengedit** di bagian bawah, lalu klik **Pratinjau PDF** di kanan atas untuk memeriksa hasilnya.

#### Langkah 3 – Kirim dan pantau

1. Bila **Wajib persetujuan internal** dicentang, klik **Minta persetujuan** (nomor 1 pada gambar draf). Pejabat lain (bukan pembuat) membuka dokumen lalu klik **Setujui**, atau **Kembalikan ke draf** dengan alasan.
2. Klik **Kirim untuk ditandatangani** di kanan atas. Tombol ini muncul setelah draf disetujui (atau langsung, bila tidak wajib persetujuan). Penerima urutan pertama menerima surel berisi tautan.

![Dokumen yang sudah dikirim](../gambar/dokumen/ttd-detail.png)

3. Pantau tabel **Penerima & urutan**: status tiap penerima (Menunggu, Sudah melihat, Selesai, Menolak) dan waktunya.
4. Untuk penerima yang belum bertindak:
   - **Kirim ulang** (nomor 3): mengirim ulang surel undangan.
   - **TTD langsung** (nomor 4): membuka sesi tanda tangan di perangkat Anda untuk penerima yang hadir. Catat bukti identitasnya, misalnya "KTP diperiksa".
   - **Ganti** (nomor 5): mengganti penerima, misalnya karena pejabatnya berganti.
5. **Kirim pengingat** (nomor 1) mengirim pengingat ke semua penerima yang belum bertindak.
6. **Batalkan** (nomor 2) menghentikan proses. Alasan wajib ditulis.
7. Gulir ke bawah ke **Komentar** untuk catatan bersama. Centang **Internal (hanya petugas)** bila komentar tidak boleh dilihat penerima.

Setelah semua penerima selesai, status menjadi **Selesai**:

![Dokumen tanda tangan selesai](../gambar/dokumen/ttd-selesai.png)

- Bagian **Dokumen final** menampilkan waktu selesai dan **Sidik SHA-256** (sidik digital PDF final).
- **Halaman verifikasi keaslian** (nomor 1): halaman publik untuk memeriksa keaslian PDF.
- **Minta unduh PDF final** (nomor 2): mengajukan permintaan unduh PDF final (lihat 7.7).
- **Salin jadi draf baru** (nomor 3): membuat salinan dokumen, misalnya untuk penerima lain atau setelah ditolak.

#### Yang dialami penerima

Penerima membuka tautan di surel. Penerima dengan akun portal cukup masuk dengan akunnya; penerima tanpa akun memasukkan **kode verifikasi 6 angka** yang dikirim ke surelnya (berlaku 10 menit) dan, bila diatur, **kode akses** dari petugas. Ia lalu membaca dokumen, mengisi kolom isian, mencentang persetujuan, menggambar atau mengetik tanda tangan (atau memakai tanda tangan tersimpan), dan klik **Tanda tangani** atau **Setujui**. Ia juga bisa **Tolak dokumen** dengan alasan. Alamat IP dan perangkat tercatat. Rinciannya untuk pemegang hak ada di [Bab 15](../53-portal-dokumen.md).

Siapa pun yang memegang PDF final bisa memeriksa keasliannya di portal (**Verifikasi dokumen**, lihat [Bab 12](../50-portal-publik.md)).

<!-- akhir sisip -->

<!-- sisip: 22-dokumen-perizinan.md#75-templat-dokumen-dan-pustaka-konten -->

### 7.5 Templat dokumen dan pustaka konten

![Daftar templat](../gambar/dokumen/templat-daftar.png)

Jenis templat:

- **Dokumen isian (bisa ditandatangani elektronik)**: disusun di editor SimLahan.
- **Word dengan isian otomatis**: berkas .docx yang isiannya diganti otomatis.
- **Format / formulir siap unduh**: berkas apa adanya, untuk diunduh pemegang hak.

#### Menyusun templat di editor

![Editor templat](../gambar/dokumen/templat-detail.png)

1. Klik **Tambahkan Templat dokumen**. Isi **Nama templat**, **Kategori**, **Jenis templat**, dan **Keterangan**.
2. Tulis **Isi dokumen** dengan bilah alat editor (**B**, **I**, **U**, **H2**, **H3**, **¶**, **• Daftar**, **1. Daftar**, **Kiri**, **Tengah**, **Rata**, **Tabel**, **—** garis, **HTML** untuk melihat kode).
3. Sisipkan isian otomatis, misalnya `{{ pemohon.nama }}` atau `{{ lahan.kode }}`. Sisipkan blok dari pustaka konten dengan `{{ blok.<kode> }}`.
4. Isi **Peran penerima bawaan** (satu peran per baris, berurutan, misalnya "Pemegang hak" lalu "Pejabat penandatangan"), **Sifat dokumen**, **Wajib persetujuan internal sebelum dikirim**, dan **Batas waktu tanda tangan (hari)** (kosong = pengaturan umum).
5. Klik **Simpan dan terus mengedit**. Gunakan **Pratinjau** atau **Unduh contoh** untuk melihat hasil dengan data contoh. Setiap perubahan isi menaikkan **Versi**.
6. Dari templat yang siap, klik **Buat dokumen tanda tangan**.

#### Mengimpor templat

![Impor templat](../gambar/dokumen/templat-impor.png)

1. Di daftar templat, klik **Impor templat**.
2. Pilih satu atau beberapa berkas (DOCX, HTML, PDF, atau ZIP berisi berkas-berkas itu) dan **Kategori**.
3. Pilih **Berkas Word dijadikan**: **Templat Word dengan isian otomatis** (hasil .docx) atau **Dokumen isian yang dapat diedit & ditandatangani elektronik**.
4. Klik impor. Sistem melaporkan berapa templat diimpor dan berkas mana yang dilewati.

#### Pustaka konten

![Pustaka konten](../gambar/dokumen/pustaka-konten.png)

**Pustaka konten** berisi blok teks yang dipakai ulang (misalnya pasal sanksi, kop surat). Isi **Kode** (huruf kecil, angka, garis bawah), **Nama**, dan **Isi**. Di templat, tulis `{{ blok.<kode> }}`. Kolom **Isian** menunjukkan isian otomatis yang dipakai blok itu.

<!-- akhir sisip -->

<!-- sisip: 22-dokumen-perizinan.md#77-permintaan-unduh -->

### 7.7 Permintaan unduh

![Daftar permintaan unduh](../gambar/dokumen/unduh-daftar.png)

Saringan **Tindakan saya** menampilkan permintaan yang menunggu keputusan Anda.

**Mengajukan permintaan unduh:**

1. Di halaman dokumen perizinan atau dokumen tanda tangan, klik **Minta unduh** (atau **Minta unduh PDF final**).
2. Pilih **Keperluan**: Arsip / administrasi, Pengurusan izin ke instansi lain, Pengajuan pembiayaan / bank, Keperluan hukum / pengadilan, Pemeriksaan / audit, atau Lainnya. Tulis **Alasan**.
3. Kirim, lalu tunggu keputusan. Lihat statusnya di **Permintaan unduh saya**.
4. Setelah **Disetujui**, klik **Unduh sekarang** sebelum masa berlakunya habis. Permintaan yang belum diputuskan bisa dibatalkan dengan **Batalkan permintaan**.

**Memutuskan permintaan unduh:**

![Halaman permintaan unduh](../gambar/dokumen/unduh-detail.png)

1. Buka permintaan berstatus **Menunggu persetujuan** dari saringan **Tindakan saya** atau dari kartu di dasbor.
2. Di bagian **Keputusan**, baca keperluan dan alasan pemohon. Periksa juga **Riwayat permintaan pemohon ini** di bawahnya.
3. Bila perlu, tulis **Catatan keputusan** (nomor 1). Catatan wajib diisi bila Anda menolak.
4. Bila perlu, ubah **Berlaku (jam)** (nomor 2), yaitu berapa jam izin unduh berlaku, dan **Batas unduh** (nomor 3), yaitu berapa kali berkas boleh diunduh. Kosongkan untuk memakai pengaturan umum.
5. Klik **Setujui** (nomor 4) atau **Tolak** (nomor 5). Pemohon diberi tahu.

Permintaan Anda sendiri harus diputuskan pejabat lain. Dokumen **rahasia** hanya dapat disetujui Administrator.

**Riwayat unduhan** mencatat setiap pratinjau dan unduhan (saringan **Pratinjau** dan **Bertanda air**).

![Riwayat unduhan](../gambar/dokumen/riwayat-unduh.png)

<!-- akhir sisip -->

> Anda membaca dokumen perizinan tetapi tidak memverifikasinya, dan tidak menyetujui permintaan unduh (termasuk milik sendiri).

<!-- sisip: 22-dokumen-perizinan.md#710-pertanyaan-umum -->

### 7.10 Pertanyaan umum

**Tombol Kirim untuk ditandatangani tidak muncul.** Dokumen wajib persetujuan internal dan belum disetujui. Klik **Minta persetujuan** dan minta pejabat lain menyetujuinya.

**Saya tidak bisa menyetujui permintaan unduh.** Permintaan itu milik Anda sendiri, dokumennya rahasia (hanya Administrator), atau peran Anda tidak berhak menyetujui.

**Penerima tidak menerima surel.** Periksa alamat **Surel**, lalu klik **Kirim ulang**. Bila penerima hadir di kantor, gunakan **TTD langsung**.

**Dokumen baru wajib tidak muncul di pemanfaatan lama.** Jalankan aksi **Terapkan ke pemanfaatan lahan aktif** pada jenis dokumen itu.

<!-- akhir sisip -->

## Bila ada kendala

- **Menu atau tombol yang disebut di buku ini tidak ada di layar Anda.** Peran Anda memang tidak memerlukannya (lihat **Batas akses** di atas). Bila Anda membutuhkannya untuk pekerjaan, minta Administrator menambahkan peran yang sesuai.
- **Pesan "Tidak berhak" atau "Anda tidak berwenang melihat data ini".** Data itu di luar hak peran Anda, bukan kerusakan sistem.
- **Lupa kata sandi.** Hubungi superuser SimLahan untuk dibuatkan sandi baru, lalu ganti sandi itu setelah masuk (klik nama Anda → **Ganti sandi**, atau buka `/akun/sandi/`).
- **Terlalu banyak percobaan masuk.** Tunggu beberapa menit, lalu coba lagi dengan sandi yang benar.
- **Ringkasan peran di dalam aplikasi.** Isi bagian *Ringkasan peran* di atas juga bisa dibuka kapan saja lewat **Panduan peran** (`/akun/panduan/`).
