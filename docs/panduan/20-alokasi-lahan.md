# Bab 5 – Alokasi lahan (panel admin)

Modul alokasi lahan memproses permohonan yang diajukan pemohon lewat portal: dari pemeriksaan kelengkapan, verifikasi teknis, persetujuan, tagihan, sampai terbitnya dokumen keputusan (KPT, PPT, PL) dan pemantauan setelah alokasi. Modul ini dibuka di **panel admin** (`/admin/alokasi/`).

**Siapa memakai bab ini:**

| Peran | Yang dikerjakan |
|---|---|
| **Petugas Alokasi Lahan** | Memeriksa, meminta perbaikan, meneruskan ke verifikasi, menyetujui/menolak, memverifikasi pembayaran, memblokir/mencabut alokasi, mengelola data lahan dan konten portal. |
| **Tim Verifikasi Teknis** | Membaca permohonan dan memberi **nilai verifikasi teknis** per kriteria. |
| **Administrator** | Semua, termasuk pengaturan layanan. |

Alur status permohonan:

```
Draf → Diajukan → Verifikasi teknis → Disetujui, menunggu pembayaran → Pembayaran terverifikasi → Dokumen terbit
            ↘ Perlu perbaikan (pemohon memperbaiki lalu mengajukan ulang) ↗
            ↘ Ditolak                         Pemohon dapat membatalkan → Dibatalkan pemohon
```

## 5.1 Daftar permohonan

Halaman awal Petugas Alokasi dan Tim Verifikasi: **Panel admin → Alokasi lahan → Permohonan**.

![Daftar permohonan](gambar/alokasi/permohonan-daftar.png)

1. **Filter**: saring per **Status**, **Layanan**, **Jenis alokasi**, atau (bagi verifikator) **penilaian saya** (sudah/belum saya nilai).
2. **Kotak cari**: nomor permohonan, nama pemohon, atau kode lahan.

Di atas tabel tampil jumlah permohonan per status; klik angka status untuk menyaring.

## 5.2 Memproses permohonan (Petugas Alokasi)

Klik nomor permohonan untuk membuka. Bagian atas menampilkan status dan, bila ada, **daftar dokumen wajib yang belum lengkap** (tulisan merah). Di bawahnya: data permohonan, data alokasi tanah (lahan, rencana kegiatan, nilai investasi, tenaga kerja, jangka waktu pembangunan), peralihan hak (bila layanan peralihan), keputusan, dokumen persyaratan, nilai verifikasi teknis, tagihan, dokumen terbit, dan riwayat.

### Langkah 1 – Periksa kelengkapan (status *Diajukan*)

![Permohonan berstatus Diajukan](gambar/alokasi/permohonan-diajukan.png)

1. Buka permohonan berstatus **Diajukan**.
2. Periksa data dan setiap **dokumen persyaratan** (klik nama berkas untuk membuka).
3. Pilih tindakan di kanan atas:
   - **Mulai verifikasi teknis** (1): data lengkap, teruskan ke Tim Verifikasi.
   - **Minta perbaikan** (2): ada yang kurang/salah. Tulis catatan untuk pemohon (wajib); pemohon menerima surel dan dapat memperbaiki.
   - **Tolak** (3): tulis alasan (wajib). Lahan kembali tersedia dan alasan dikirim ke pemohon.

![Konfirmasi mulai verifikasi](gambar/alokasi/proses-verifikasi.png)

4. Di halaman konfirmasi, isi catatan bila perlu, lalu klik tombol tindakan untuk menegaskan.

### Langkah 2 – Verifikasi teknis (Tim Verifikasi)

Lihat 5.3. Petugas Alokasi menunggu sampai semua kriteria dinilai.

### Langkah 3 – Putuskan (status *Verifikasi teknis*)

![Permohonan dalam verifikasi teknis](gambar/alokasi/permohonan-verifikasi.png)

1. Buka permohonan berstatus **Verifikasi teknis**. Bagian **Nilai verifikasi teknis** menunjukkan nilai per kriteria dan nilai akhir.
2. Pilih **Setujui** (1), **Minta perbaikan** (2), atau **Tolak** (3).

![Konfirmasi persetujuan](gambar/alokasi/proses-setujui.png)

Saat **Setujui**, sistem otomatis membuat **tagihan UWT** dan **biaya administrasi**. Persetujuan ditolak sistem bila:

- belum semua kriteria verifikasi teknis dinilai;
- nilai akhir di bawah **nilai minimum** (diatur di Pengaturan layanan alokasi);
- untuk peralihan hak: penerima hak belum menyetujui peralihan di portal.

![Formulir minta perbaikan](gambar/alokasi/proses-perbaikan.png)

### Langkah 4 – Verifikasi pembayaran

Lihat 5.4. Setelah **semua tagihan lunas**, dokumen keputusan (KPT dan PPT, PL dengan sketsa bidang, izin peralihan hak, atau surat layanan) **terbit otomatis** lengkap dengan kode QR verifikasi, dan pemohon bisa mengunduhnya di portal.

## 5.3 Menilai verifikasi teknis (Tim Verifikasi)

![Permohonan bagi verifikator](gambar/alokasi/verifikasi-permohonan.png)

1. Saring daftar dengan **Status: Verifikasi teknis** dan **Berdasarkan penilaian saya: belum dinilai**.
2. Buka permohonan, klik **Nilai verifikasi** (1).
3. Di halaman penilaian, baca ringkasan lahan dan rencana usaha; buka dokumen pemohon dari tautan **Dokumen**.

![Formulir penilaian verifikasi teknis](gambar/alokasi/verifikasi-form-nilai.png)

4. Isi **nilai 0–100** untuk setiap kriteria (bobot tertulis di samping nama kriteria) dan **Catatan** alasan penilaian.
5. Klik **Simpan** di bagian bawah. Nilai akhir = rata-rata nilai semua verifikator per kriteria, dikalikan bobot.

Anda dapat membuka lagi halaman penilaian untuk memperbaiki nilai selama permohonan masih dalam verifikasi teknis.

## 5.4 Tagihan dan pembayaran

**Panel admin → Alokasi lahan → Tagihan.**

![Daftar tagihan](gambar/alokasi/tagihan-daftar.png)

Saring per **Status** (Belum dibayar, Bukti bayar menunggu verifikasi, Lunas, Dibatalkan) dan **Jenis** (UWT, biaya administrasi alokasi, biaya administrasi peralihan hak, dll.).

**Memverifikasi satu tagihan**

![Detail tagihan](gambar/alokasi/tagihan-detail.png)

1. Buka tagihan berstatus **Bukti bayar menunggu verifikasi**.
2. Buka **bukti bayar** yang diunggah pemohon dan cocokkan dengan rekening penerimaan.
3. Klik **Nyatakan lunas** (1) bila sesuai, atau **Tolak bukti bayar** (2) dengan alasan agar pemohon mengunggah ulang.
4. **Unduh tagihan PDF** (3) untuk mencetak tagihan.

**Memverifikasi banyak tagihan sekaligus**: centang tagihan di daftar (1 pada gambar daftar), pilih aksi **Verifikasi lunas (bukti bayar sudah diunggah)**, lalu klik **Jalankan**.

## 5.5 Alokasi & lahan tidur

**Panel admin → Alokasi lahan → Alokasi lahan.** Berisi semua alokasi yang sudah terbit (nomor KPT, pemegang hak, lahan, masa berlaku, progres pembangunan).

![Daftar alokasi](gambar/alokasi/alokasi-daftar.png)

Filter penting:

- **PL diblokir**: alokasi yang penetapan lokasinya diblokir.
- **Lahan tidur**: alokasi aktif yang sudah lewat batas waktu (diatur di pengaturan) dan belum mulai konstruksi.
- **Kepatuhan lapor**: pemegang hak yang terlambat mengirim laporan progres pembangunan.

![Detail alokasi](gambar/alokasi/alokasi-detail.png)

Tindakan di halaman alokasi:

1. **Blokir PL**: memblokir penetapan lokasi (misalnya karena sengketa). Selama diblokir, pemegang hak hanya bisa mengajukan layanan **pembukaan blokir**. Tombol berubah menjadi **Buka blokir PL**.
2. **Cabut alokasi**: mencabut alokasi (misalnya lahan tidur atau pelanggaran). Tulis alasan; lahan kembali tersedia.

![Konfirmasi blokir PL](gambar/alokasi/alokasi-blokir.png)

Bagian **Dokumen terbit** dan **Progres pembangunan** menampilkan dokumen keputusan dan laporan pembangunan dari pemegang hak. Tautan **Permohonan asal** membuka permohonan yang menghasilkan alokasi ini.

Setiap Senin pukul 07.30 WIB sistem menjalankan **pemantauan mingguan**: alokasi yang berakhir, peringatan lahan tidur, laporan progres terlambat, dan tagihan yang segera atau sudah lewat jatuh tempo. Pengingat dikirim ke pemegang hak dan ringkasannya ke surel petugas alokasi.

## 5.6 Data lahan

**Panel admin → Alokasi lahan → Lahan.** Lahan yang tampil di peta portal dan dapat dimohon.

![Daftar lahan](gambar/alokasi/lahan-daftar.png)

1. **Impor GeoJSON/KML/KMZ**: menambah atau memperbarui banyak lahan dari berkas peta.
2. **Tambahkan Lahan**: menambah satu lahan.
3. **Aksi** untuk lahan terpilih: Tampilkan di portal, Sembunyikan dari portal, Tutup lahan (tidak menerima permohonan), Buka kembali lahan yang ditutup, Tandai sebagai lahan unggulan portal investasi, Akhiri sewa (lahan kembali tersedia).

### Menambah atau mengubah lahan

![Formulir lahan](gambar/alokasi/lahan-detail.png)

1. Isi kode, nama/lokasi, jenis alokasi, status, kecamatan, luas, dan arahan pemanfaatan.
2. Bagian **Lokasi**: gambar batas lahan di peta.
3. Bagian **Data teknis**: utilitas, akses, jarak ke fasilitas, kesiapan.
4. Bagian **Tarif**: tarif UWT per m² per tahun, tarif sewa, masa sewa minimum; skema yang ditawarkan (sewa dan/atau alokasi).
5. Bagian **Profil investasi**: sektor, kawasan, keunggulan lokasi, insentif, foto; centang tampil di portal dan unggulan.
6. Klik **Simpan**.

> Lahan yang sudah terikat permohonan, alokasi, atau sewa dikunci ukuran dan tarifnya; impor tidak menimpanya.

### Mengimpor lahan dari berkas peta

![Impor lahan](gambar/alokasi/lahan-impor.png)

1. Klik **Impor GeoJSON/KML/KMZ**.
2. Pilih **Berkas GeoJSON atau KML/KMZ** (misalnya dari Google Earth) berisi poligon dalam WGS84. Pada KML/KMZ, nama *placemark* dipakai sebagai kode lahan bila tidak ada atribut kode; impor ulang dengan kode yang sama memperbarui lahan itu. Luas dihitung dari geometri bila tidak diisi.
3. Pilih **Jenis alokasi bawaan** dan centang **Langsung tampil di portal** bila perlu, lalu klik impor. Pesan "Impor selesai: … lahan baru, … diperbarui" menandakan berhasil.

## 5.7 Pemohon

**Panel admin → Alokasi lahan → Pemohon.** Daftar akun pemohon portal (badan usaha, instansi, perorangan, investor).

![Daftar pemohon](gambar/alokasi/pemohon-daftar.png)

- Saring per **Akun investor**, **Jenis pemohon**, **Asal modal**, atau **aktif**.
- Aksi **Aktifkan akun** / **Nonaktifkan akun** untuk pemohon terpilih (misalnya bila surel aktivasi tidak sampai).
- Klik nama pemohon untuk melihat profil, permohonan, dan permintaan investasinya.

## 5.8 Laporan pembangunan dan dokumen terbit

- **Laporan pembangunan**: laporan progres yang dikirim pemegang hak dari portal (tahap, progres %, nilai investasi, tenaga kerja, foto/lampiran). Saring per **Tahap**.
- **Dokumen terbit**: semua KPT, PPT, PL, izin peralihan, dan surat layanan yang terbit, beserta PDF dan **halaman verifikasi** QR-nya. Dokumen yang diganti (karena layanan revisi/pengganti) ditandai **Diganti pada**.

![Laporan pembangunan](gambar/alokasi/laporan-pembangunan.png)

![Dokumen terbit](gambar/alokasi/dokumen-terbit.png)

## 5.9 Konten portal dan data master

| Menu | Kegunaan |
|---|---|
| **Katalog layanan** | Daftar layanan yang tampil di portal (deskripsi, syarat, alur, durasi, tarif, dasar hukum) dan jenis permohonan daringnya. |
| **Jenis dokumen persyaratan** | Dokumen yang wajib/opsional diunggah per layanan dan jenis alokasi. |
| **Kriteria verifikasi teknis** | Kriteria dan bobot penilaian verifikasi teknis. |
| **Konten informasi** | Halaman informasi portal: regulasi, persyaratan, prosedur, pengumuman, video tutorial, buku panduan, unduhan, tanya jawab, panduan investasi. Centang **Sematkan di beranda** dan **Terbit**. |
| **Wilayah tarif UWT** dan **Tarif UWT** | Tarif UWT per wilayah dan jenis pengurusan, dipakai di **Simulasi biaya UWT** portal (termasuk denda per bulan keterlambatan dan batas maksimumnya). |
| **Pesan Kontak Kami** | Pesan yang dikirim masyarakat dari portal; ubah status setelah dijawab. |
| **Pengaturan layanan alokasi** *(Administrator)* | Otoritas & penandatangan, tarif & tagihan, ketentuan alokasi (nilai minimum, batas lahan tidur, interval lapor), kop surat, portal & Kontak Kami, simulasi UWT, portal investasi. |

![Katalog layanan](gambar/alokasi/katalog-layanan.png)

![Konten informasi](gambar/alokasi/konten-informasi.png)

![Wilayah tarif UWT](gambar/alokasi/wilayah-uwt-detail.png)

![Pesan Kontak Kami](gambar/alokasi/pesan-kontak.png)

![Pengaturan layanan alokasi](gambar/alokasi/pengaturan-alokasi.png)

## 5.10 Pertanyaan umum

**Tombol Setujui tidak muncul.** Permohonan belum berstatus *Verifikasi teknis*. Untuk permohonan *Diajukan*, klik **Mulai verifikasi teknis** dulu.

**Muncul pesan "Semua kriteria verifikasi teknis harus dinilai".** Minta Tim Verifikasi melengkapi nilai di halaman **Nilai verifikasi**.

**Dokumen keputusan belum terbit padahal sudah disetujui.** Dokumen terbit otomatis setelah **semua** tagihan berstatus **Lunas**. Periksa tagihan yang masih menunggu verifikasi.

**Pemohon tidak menerima surel aktivasi.** Aktifkan akunnya lewat **Pemohon → aksi Aktifkan akun**, dan minta pengelola memeriksa pengaturan surel (SMTP).
