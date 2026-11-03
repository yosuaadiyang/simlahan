# Bab 7 – Dokumen & perizinan (panel admin)

Modul ini mencatat **pemanfaatan lahan** (alokasi, sewa, kerja sama), memantau **dokumen perizinan** yang wajib dimiliki pemegang hak, menyusun **templat**, mengirim **dokumen untuk ditandatangani elektronik**, dan mengatur **permintaan unduh** dokumen. Semua menu ada di **Panel admin → Dokumen & perizinan**.

**Siapa memakai bab ini:**

| Peran | Yang boleh dilakukan |
|---|---|
| Administrator | Semua, termasuk mengatur jenis dokumen wajib, templat, pengaturan modul, menyetujui dokumen tanda tangan sebelum dikirim, dan menyetujui unduhan dokumen **rahasia**. |
| Petugas Alokasi Lahan | Mencatat pemanfaatan lahan, menentukan dokumen wajib, memverifikasi atau meminta revisi dokumen, membuat dan mengirim dokumen tanda tangan, menyetujui unduhan dokumen **biasa**. Tidak mengubah pengaturan modul. |
| Tim Verifikasi Teknis | Memverifikasi atau meminta revisi dokumen perizinan; mengajukan permintaan unduh. Tidak membuat templat atau dokumen tanda tangan. |
| Petugas Hukum | Menyusun templat dan blok isi, membuat dan mengirim dokumen tanda tangan (kontrak, perjanjian), membaca dokumen perizinan; mengajukan permintaan unduh. Tidak memverifikasi dokumen perizinan. |

> **Aturan unduh:** mengunduh berkas asli selalu lewat **permintaan unduh** yang disetujui orang lain. Setiap unduhan diberi tanda air (nama pengunduh, waktu, nomor permintaan) dan tercatat. Melihat **pratinjau** boleh langsung, juga dengan tanda air.

## 7.1 Dasbor dokumen & perizinan

![Dasbor dokumen & perizinan](gambar/dokumen/dasbor.png)

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

![Dasbor lengkap](gambar/dokumen/dasbor-full.png)

## 7.2 Pemanfaatan lahan

Satu **pemanfaatan lahan** mewakili satu hak pakai lahan: alokasi, sewa, kerja sama, atau lainnya. Nomornya berformat `PML-2026-00001`. Pemanfaatan dari alokasi dan permintaan investasi dibuat otomatis oleh sistem; pemanfaatan lain bisa dibuat manual.

![Daftar pemanfaatan lahan](gambar/dokumen/pemanfaatan-daftar.png)

Saringan di kanan: **Status** (Aktif, Berakhir, Dicabut), **Skema**, **Kelengkapan** dokumen, dan **Sektor**.

### Menambah pemanfaatan lahan

1. Klik **Tambahkan Pemanfaatan lahan**.
2. Isi **Nama kegiatan / proyek**, **Skema**, dan **Status**.
3. Isi pemegang hak: pilih **Pemegang hak (akun portal)** bila ia punya akun portal (ia lalu bisa melihat dan mengunggah dokumennya sendiri), atau isi **Nama pemegang hak** secara manual.
4. Isi **Lahan**, **Sektor**, **Nomor dasar hak / kontrak**, **Luas (m²)**, **Mulai**, **Berakhir**, dan **Petugas penanggung jawab**. Bila berasal dari alokasi atau permintaan investasi, isi juga kolom **Alokasi** atau **Permintaan investasi**.
5. Klik **Simpan**. Sistem otomatis membuat daftar **dokumen perizinan wajib** sesuai skema dan sektor (lihat 7.6).

### Halaman pemanfaatan lahan

![Halaman pemanfaatan lahan](gambar/dokumen/pemanfaatan-detail.png)

Bagian atas menampilkan progres kelengkapan dan daftar dokumen beserta statusnya. Tombol:

- **Tambah dokumen ke daftar**: menambah dokumen yang tidak otomatis masuk daftar (misalnya izin khusus).
- **Buat dokumen tanda tangan**: membuat dokumen tanda tangan dengan data pemanfaatan ini terisi otomatis (lihat 7.4).
- Tautan **Lihat alokasi** atau **Lihat permintaan investasi** bila ada.

![Halaman pemanfaatan lahan lengkap](gambar/dokumen/pemanfaatan-detail-full.png)

### Kirim dokumen tanda tangan massal

Untuk mengirim dokumen yang sama (misalnya surat pernyataan) ke banyak pemegang hak sekaligus:

1. Di daftar pemanfaatan lahan, centang pemanfaatan yang dituju (maksimal 200).
2. Pilih aksi **Kirim dokumen tanda tangan massal (satu per pemanfaatan)**, lalu klik **Jalankan**.
3. Pilih **Templat**, isi **Judul dokumen** dan **Pesan untuk penerima**.
4. Bila perlu, pilih **Penanda tangan kedua (petugas)** dan isi **Peran penanda tangan kedua**. Ia menandatangani setelah pemegang hak.
5. Kirim. Sistem membuat satu dokumen per pemanfaatan dan mengirimkannya ke masing-masing pemegang hak.

## 7.3 Dokumen perizinan

Setiap baris adalah satu dokumen wajib untuk satu pemanfaatan lahan, misalnya PKKPR atau persetujuan lingkungan.

![Daftar dokumen perizinan](gambar/dokumen/perizinan-daftar.png)

Saringan: **Status**, **Masa berlaku**, **Kategori**, **Jenis dokumen**, **Skema**.

Arti status:

| Status | Arti |
|---|---|
| Belum diurus | Pemegang hak belum mulai. |
| Sedang diurus | Pemegang hak sedang mengurus ke instansi penerbit. |
| Menunggu verifikasi | Berkas sudah diunggah, menunggu diperiksa petugas. |
| Perlu perbaikan | Petugas meminta revisi; pemegang hak mengunggah ulang. |
| Terverifikasi | Berkas sah dan diterima. |
| Kedaluwarsa | Tanggal **Berlaku sampai** sudah lewat. |
| Tidak wajib | Dikecualikan untuk pemanfaatan ini. |

### Memeriksa dokumen

![Halaman dokumen perizinan](gambar/dokumen/perizinan-detail.png)

1. Buka dokumen dari **Antrean verifikasi** di dasbor atau dari daftar.
2. Lihat bagian **Versi berkas**. Klik **Pratinjau** untuk melihat berkas (bertanda air, tercatat).
3. Pilih tindakan:
   - **Verifikasi**: isi **Nomor dokumen / izin**, **Tanggal terbit**, dan **Berlaku sampai**, lalu klik **Nyatakan terverifikasi**. Bila **Berlaku sampai** kosong, sistem menghitungnya dari masa berlaku bawaan jenis dokumen.
   - **Minta perbaikan**: tulis apa yang harus diperbaiki, lalu **Kirim permintaan perbaikan**. Pemegang hak diberi tahu.
4. Tindakan lain:
   - **Unggah versi**: petugas mengunggah berkas atas nama pemegang hak (misalnya berkas dikirim lewat surel).
   - **Buat dari templat**: membuat berkas dari templat jenis dokumen ini.
   - **Minta tanda tangan**: membuat dokumen tanda tangan untuk dokumen ini. Setelah selesai, PDF bertanda tangan otomatis menjadi versi baru dokumen.
   - **Tidak wajib**: mengecualikan dokumen ini, dengan alasan.
   - **Buka kembali**: membuka lagi dokumen yang sudah terverifikasi atau tidak wajib, dengan alasan.

Setiap tindakan tercatat di **Riwayat** dan **Jejak aktivitas**. Sistem mengirim peringatan otomatis sebelum izin kedaluwarsa (jumlah harinya diatur di **Pengaturan dokumen**).

## 7.4 Dokumen tanda tangan elektronik

Dokumen tanda tangan dipakai untuk kontrak, berita acara, surat pernyataan, dan dokumen lain yang perlu ditandatangani atau disetujui pihak lain. Nomornya berformat `DOK-2026-00001`.

![Daftar dokumen tanda tangan](gambar/dokumen/ttd-daftar.png)

Alur status:

```
Draf → (Menunggu persetujuan internal → Disetujui, siap dikirim) → Dikirim → Dilihat penerima → Selesai
                                                                  ↘ Ditolak penerima / Kedaluwarsa / Dibatalkan
```

Tahap persetujuan internal hanya ada bila **Wajib persetujuan internal sebelum dikirim** dicentang.

### Membuat dokumen tanda tangan

![Formulir dokumen tanda tangan baru](gambar/dokumen/ttd-tambah.png)

1. Klik **Tambahkan Dokumen tanda tangan**, atau klik **Buat dokumen tanda tangan** dari halaman pemanfaatan lahan atau templat.
2. Isi **Judul dokumen** dan pilih **Pemanfaatan lahan** (opsional). Bila dokumen ini untuk memenuhi dokumen perizinan, pilih **Untuk dokumen perizinan**.
3. Pilih **Sumber isi**:
   - **Isi dari templat / editor**: pilih **Templat**, lalu sunting **Isi dokumen** bila perlu. Isian otomatis (misalnya nama pemegang hak dan kode lahan) terisi sendiri.
   - **Berkas PDF unggahan**: unggah **Berkas PDF**.
4. Di bagian **Pengiriman**, isi **Pesan untuk penerima**, **Batas tanda tangan**, **Pengingat setiap (hari)** (0 = tanpa pengingat), **Sifat dokumen** (Biasa/Rahasia), dan centang **Wajib persetujuan internal sebelum dikirim** bila perlu.
5. Isi tabel **Penerima** (satu baris per orang):
   - **Urutan**: urutan yang sama berarti bertindak bersamaan; urutan berikutnya menunggu yang sebelumnya selesai.
   - **Peran** (misalnya "Pemegang hak", "Pejabat penandatangan") dan **Tindakan**: **Menandatangani**, **Menyetujui**, atau **Menerima salinan**.
   - **Akun** (bila penerima punya akun, ia wajib masuk sebelum menandatangani), **Nama**, dan **Surel**.
   - **Kode akses** (opsional): kode tambahan yang Anda sampaikan lewat telepon. Isi `-` untuk menghapus.
   - **Tanda tangan langsung**: centang bila penerima menandatangani di perangkat petugas setelah identitasnya diperiksa (misalnya warga tanpa surel). Surel tidak dikirim.
   - Khusus PDF unggahan: **Halaman cap TTD** (1 = pertama, -1 = terakhir), **Posisi kiri (%)**, **Posisi atas (%)**, dan **Lebar cap (%)** menentukan letak gambar tanda tangan di PDF.
6. Bila penerima perlu mengisi sesuatu, isi tabel **Kolom isian penerima**: **Kunci**, **Label**, **Jenis** (Teks singkat, Teks panjang, Tanggal, Angka, Kotak centang, Pilihan, Paraf, Lampiran berkas), **Diisi oleh**, dan **Wajib**. Di isi dokumen, tulis `{{ kolom.<kunci> }}` di tempat isian itu harus muncul.
7. Klik **Simpan dan terus mengedit**. Klik **Pratinjau PDF** untuk memeriksa hasilnya.

### Mengirim dan memantau

![Halaman dokumen tanda tangan](gambar/dokumen/ttd-detail.png)

1. Bila wajib persetujuan internal, klik **Minta persetujuan**. Pejabat lain (bukan pembuat) membuka dokumen lalu klik **Setujui**, atau **Kembalikan ke draf** dengan alasan.
2. Klik **Kirim untuk ditandatangani**. Penerima urutan pertama menerima surel berisi tautan.
3. Pantau tabel **Penerima & urutan**: status tiap penerima (Menunggu, Sudah melihat, Selesai, Menolak) dan waktunya.
4. Tindakan per penerima yang belum bertindak:
   - **Kirim ulang**: mengirim ulang surel undangan.
   - **Ganti**: mengganti penerima (misalnya pejabat berganti).
   - **TTD langsung**: membuka sesi tanda tangan di perangkat Anda untuk penerima yang hadir. Catat bukti identitasnya (misalnya KTP diperiksa).
5. **Kirim pengingat** mengirim pengingat ke semua penerima yang belum bertindak. **Batalkan dokumen** menghentikan proses dengan alasan.
6. Gunakan **Komentar** untuk catatan bersama, termasuk komentar **Internal (hanya petugas)**.

Setelah semua penerima selesai, status menjadi **Selesai** dan bagian **Dokumen final** menampilkan waktu selesai, **Sidik SHA-256**, tautan **Halaman verifikasi keaslian**, dan **Minta unduh PDF final**.

![Dokumen tanda tangan selesai](gambar/dokumen/ttd-detail-full.png)

**Salin jadi draf baru** membuat salinan dokumen (misalnya untuk penerima lain atau setelah ditolak).

### Yang dialami penerima

Penerima membuka tautan di surel. Penerima dengan akun portal cukup masuk dengan akunnya; penerima tanpa akun memasukkan **kode verifikasi 6 angka** yang dikirim ke surelnya (berlaku 10 menit) dan, bila diatur, **kode akses** dari petugas. Ia lalu membaca dokumen, mengisi kolom isian, mencentang persetujuan, menggambar atau mengetik tanda tangan (atau memakai tanda tangan tersimpan), dan klik **Tanda tangani** atau **Setujui**. Ia juga bisa **Tolak dokumen** dengan alasan. Alamat IP dan perangkat tercatat. Rinciannya untuk pemegang hak ada di [Bab 15](53-portal-dokumen.md).

Siapa pun yang memegang PDF final bisa memeriksa keasliannya di portal (**Verifikasi dokumen**, lihat [Bab 12](50-portal-publik.md)).

## 7.5 Templat dokumen dan pustaka konten

![Daftar templat](gambar/dokumen/templat-daftar.png)

Jenis templat:

- **Dokumen isian (bisa ditandatangani elektronik)**: disusun di editor SimLahan.
- **Word dengan isian otomatis**: berkas .docx yang isiannya diganti otomatis.
- **Format / formulir siap unduh**: berkas apa adanya, untuk diunduh pemegang hak.

### Menyusun templat di editor

![Editor templat](gambar/dokumen/templat-detail.png)

1. Klik **Tambahkan Templat dokumen**. Isi **Nama templat**, **Kategori**, **Jenis templat**, dan **Keterangan**.
2. Tulis **Isi dokumen** dengan bilah alat editor (**B**, **I**, **U**, **H2**, **H3**, **¶**, **• Daftar**, **1. Daftar**, **Kiri**, **Tengah**, **Rata**, **Tabel**, **—** garis, **HTML** untuk melihat kode).
3. Sisipkan isian otomatis, misalnya `{{ pemohon.nama }}` atau `{{ lahan.kode }}`. Sisipkan blok dari pustaka konten dengan `{{ blok.<kode> }}`.
4. Isi **Peran penerima bawaan** (satu peran per baris, berurutan, misalnya "Pemegang hak" lalu "Pejabat penandatangan"), **Sifat dokumen**, **Wajib persetujuan internal sebelum dikirim**, dan **Batas waktu tanda tangan (hari)** (kosong = pengaturan umum).
5. Klik **Simpan dan terus mengedit**. Gunakan **Pratinjau** atau **Unduh contoh** untuk melihat hasil dengan data contoh. Setiap perubahan isi menaikkan **Versi**.
6. Dari templat yang siap, klik **Buat dokumen tanda tangan**.

### Mengimpor templat

![Impor templat](gambar/dokumen/templat-impor.png)

1. Di daftar templat, klik **Impor templat**.
2. Pilih satu atau beberapa berkas (DOCX, HTML, PDF, atau ZIP berisi berkas-berkas itu) dan **Kategori**.
3. Pilih **Berkas Word dijadikan**: **Templat Word dengan isian otomatis** (hasil .docx) atau **Dokumen isian yang dapat diedit & ditandatangani elektronik**.
4. Klik impor. Sistem melaporkan berapa templat diimpor dan berkas mana yang dilewati.

### Pustaka konten

![Pustaka konten](gambar/dokumen/pustaka-konten.png)

**Pustaka konten** berisi blok teks yang dipakai ulang (misalnya pasal sanksi, kop surat). Isi **Kode** (huruf kecil, angka, garis bawah), **Nama**, dan **Isi**. Di templat, tulis `{{ blok.<kode> }}`. Kolom **Isian** menunjukkan isian otomatis yang dipakai blok itu.

## 7.6 Jenis dokumen perizinan

![Jenis dokumen perizinan](gambar/dokumen/jenis-perizinan.png)

Menentukan dokumen apa saja yang wajib untuk setiap pemanfaatan lahan:

1. Klik **Tambahkan Jenis dokumen perizinan**.
2. Isi **Kode**, **Nama dokumen / izin**, **Kategori**, **Instansi penerbit**, dan **Persyaratan & cara mengurus** (tampil ke pemegang hak di portal).
3. Centang skema yang berlaku: **Berlaku untuk alokasi**, **sewa**, **kerja sama**, **pemanfaatan lainnya**. Batasi ke sektor tertentu di **Hanya untuk sektor** (kosong = semua sektor).
4. Isi **Wajib**, **Masa berlaku bawaan (bulan)** (kosong = tidak kedaluwarsa), **Sifat dokumen**, **Templat / format** (format yang bisa diunduh pemegang hak), dan **Urutan**.
5. Simpan. Untuk menambahkannya ke pemanfaatan lahan yang sudah ada, centang jenis dokumen di daftar, pilih aksi **Terapkan ke pemanfaatan lahan aktif**, lalu klik **Jalankan**.

## 7.7 Permintaan unduh

![Daftar permintaan unduh](gambar/dokumen/unduh-daftar.png)

Saringan **Tindakan saya** menampilkan permintaan yang menunggu keputusan Anda.

**Mengajukan permintaan unduh:**

1. Di halaman dokumen perizinan atau dokumen tanda tangan, klik **Minta unduh** (atau **Minta unduh PDF final**).
2. Pilih **Keperluan**: Arsip / administrasi, Pengurusan izin ke instansi lain, Pengajuan pembiayaan / bank, Keperluan hukum / pengadilan, Pemeriksaan / audit, atau Lainnya. Tulis **Alasan**.
3. Kirim, lalu tunggu keputusan. Lihat statusnya di **Permintaan unduh saya**.
4. Setelah **Disetujui**, klik **Unduh sekarang** sebelum masa berlakunya habis. Permintaan yang belum diputuskan bisa dibatalkan dengan **Batalkan permintaan**.

**Memutuskan permintaan unduh:**

![Halaman permintaan unduh](gambar/dokumen/unduh-detail.png)

1. Buka permintaan dari saringan **Tindakan saya** atau kartu di dasbor.
2. Periksa keperluan, alasan, dan **Riwayat permintaan pemohon ini**.
3. Klik **Setujui** (boleh mengubah **Berlaku (jam)**; kosong = pengaturan) atau **Tolak** (wajib isi **Catatan keputusan**).

Permintaan Anda sendiri harus diputuskan pejabat lain. Dokumen **rahasia** hanya dapat disetujui Administrator.

**Riwayat unduhan** mencatat setiap pratinjau dan unduhan (saringan **Pratinjau** dan **Bertanda air**).

![Riwayat unduhan](gambar/dokumen/riwayat-unduh.png)

## 7.8 Jejak aktivitas

![Jejak aktivitas](gambar/dokumen/jejak-aktivitas.png)

Catatan lengkap semua kejadian di modul ini: dibuat, diubah, berkas diunggah, diverifikasi, diminta perbaikan, dikirim, dilihat, ditandatangani, ditolak, unduhan diminta/disetujui/ditolak, diunduh, dan lainnya. Saring per **Aktivitas**. Catatan ini tidak bisa diubah atau dihapus.

## 7.9 Pengaturan dokumen (Administrator)

![Pengaturan dokumen](gambar/dokumen/pengaturan.png)

| Bagian | Isian |
|---|---|
| Unduhan | **Masa berlaku izin unduh (jam)**, **Batas unduh per persetujuan**, **Pemegang hak wajib minta persetujuan unduh** (bila dimatikan, unduhan pemegang hak atas dokumen biasanya sendiri langsung disetujui sistem, tetap tercatat), **Izinkan menyetujui permintaan sendiri** (sebaiknya tetap mati), **Beri tanda air pada PDF yang diunduh**. |
| Tanda tangan elektronik | **Batas waktu tanda tangan bawaan (hari)**, **Pengingat penanda tangan setiap (hari)**. |
| Masa berlaku izin | **Peringatan izin akan kedaluwarsa (hari sebelumnya)**. |

## 7.10 Pertanyaan umum

**Tombol Kirim untuk ditandatangani tidak muncul.** Dokumen wajib persetujuan internal dan belum disetujui. Klik **Minta persetujuan** dan minta pejabat lain menyetujuinya.

**Saya tidak bisa menyetujui permintaan unduh.** Permintaan itu milik Anda sendiri, dokumennya rahasia (hanya Administrator), atau peran Anda tidak berhak menyetujui.

**Penerima tidak menerima surel.** Periksa alamat **Surel**, lalu klik **Kirim ulang**. Bila penerima hadir di kantor, gunakan **TTD langsung**.

**Dokumen baru wajib tidak muncul di pemanfaatan lama.** Jalankan aksi **Terapkan ke pemanfaatan lahan aktif** pada jenis dokumen itu.
