# Bab 6 – Permintaan investasi (panel admin)

Investor mengajukan minat sewa, alokasi, atau kerja sama pemanfaatan lahan lewat portal investasi (`/portal/investasi/`). Petugas menindaklanjutinya di **Panel admin → Alokasi lahan → Permintaan investasi**: meninjau, menjadwalkan konsultasi, mengirim penawaran, berkirim pesan, lalu menyelesaikan (menjadi kontrak atau permohonan alokasi) atau menolak.

**Siapa memakai bab ini:** Petugas Alokasi Lahan dan Administrator memproses; Tim Verifikasi Teknis hanya membaca.

Alur status:

```
Diajukan → Sedang ditinjau → Konsultasi / kunjungan lapangan → Penawaran dikirim → Penawaran diterima → Selesai, diteruskan
                        ↘ Ditolak (oleh petugas)                 ↘ Dibatalkan investor
```

## 6.1 Daftar permintaan

![Daftar permintaan investasi](gambar/alokasi/investasi-daftar.png)

Saring per **Tahap**, **Status**, **Skema yang diminati** (sewa, alokasi/UWT, kerja sama, belum ditentukan), **Sektor usaha**, **Kawasan**, atau **Asal modal**. Klik nomor (misalnya `INV-2026-00003`) untuk membuka.

## 6.2 Halaman permintaan

![Permintaan berstatus Diajukan](gambar/alokasi/investasi-diajukan.png)

Bagian halaman:

- **Status** dan ringkasan (skema, sektor, nilai investasi).
- **Pesan dengan investor**: percakapan dua arah beserta lampiran.
- **Penanganan**: petugas penanggung jawab dan **catatan internal** (tidak terlihat investor).
- **Rencana investasi**: nama proyek, kegiatan, nilai, tenaga kerja, jadwal.
- **Lokasi**: lahan yang dipilih investor atau area yang digambar investor di peta.
- **Konsultasi**, **Penawaran**, **Penutupan**, dan **Riwayat status**.

Tombol tindakan (kanan atas) muncul sesuai status:

1. **Mulai tinjau**: menandai sedang ditinjau dan menugaskan Anda (bila belum ada petugas). Investor diberi tahu lewat surel.
2. **Jadwalkan konsultasi**: undangan konsultasi atau kunjungan lapangan.
3. **Kirim penawaran** (atau **Perbarui penawaran**): penawaran sewa/alokasi/kerja sama.
4. **Tolak**: menutup permintaan dengan alasan yang dikirim ke investor.

Setelah investor menerima penawaran, tombol **Selesaikan** muncul.

## 6.3 Membalas pesan investor

![Pesan dengan investor](gambar/alokasi/investasi-pesan.png)

1. Di bagian **Pesan dengan investor**, tulis balasan di **Balas investor**.
2. Lampirkan berkas bila perlu (PDF/JPG/PNG, maksimal 10 MB).
3. Klik **Kirim pesan**. Investor menerima pemberitahuan dan bisa membalas dari portal.

## 6.4 Menjadwalkan konsultasi

![Formulir jadwal konsultasi](gambar/alokasi/investasi-form-konsultasi.png)

1. Klik **Jadwalkan konsultasi**.
2. Isi **Jadwal konsultasi / kunjungan** (tanggal dan jam), **Tempat / tautan pertemuan**, dan **Catatan untuk investor**.
3. Klik tombol simpan. Investor menerima undangan di portal dan surel.

## 6.5 Mengirim penawaran

![Formulir penawaran](gambar/alokasi/investasi-form-penawaran.png)

1. Klik **Kirim penawaran**.
2. Pilih **Skema ditawarkan** (sewa, alokasi, atau kerja sama) dan **Lahan ditawarkan**. Skema alokasi wajib memakai lahan yang membuka alokasi.
3. Isi **Luas ditawarkan (m²)**, **Tarif per m² per tahun (Rp)**, **Jangka waktu (tahun)**, **Penawaran berlaku s.d.**, dan **Ketentuan penawaran**. Luas dan tarif terisi dari data lahan bila dikosongkan.
4. Klik tombol kirim. Investor dapat **menerima** atau **menolak** penawaran di portal sampai tanggal berlaku. Lahan belum dipesan sampai permintaan diselesaikan.

![Permintaan berstatus Penawaran dikirim](gambar/alokasi/investasi-ditawarkan.png)

## 6.6 Menyelesaikan permintaan

Hanya untuk penawaran yang sudah **diterima** investor.

1. Klik **Selesaikan**.
2. **Skema alokasi**: sistem membuat **draf permohonan alokasi** atas nama investor dengan rencana usaha terisi. Investor melengkapi dokumen lalu mengajukannya di portal; prosesnya berlanjut seperti [Bab 5](20-alokasi-lahan.md).
3. **Skema sewa/kerja sama**: isi **nomor kontrak** sewa atau perjanjian kerja sama. Lahan yang ditawarkan ditandai **Sudah disewakan**.
4. Status menjadi **Selesai, diteruskan**. Investor dapat mengelola dokumen perizinan kontraknya di portal (lihat [Bab 15](53-portal-dokumen.md)).

## 6.7 Sektor dan kawasan investasi

- **Sektor investasi**: daftar sektor (industri, pariwisata, logistik, dsb.) beserta ikon yang dipakai sebagai saringan di peta investasi.
- **Kawasan investasi**: kawasan yang ditampilkan di portal (deskripsi, insentif, infrastruktur, foto, sektor unggulan). Centang **Tampil di portal** dan **Unggulan** sesuai kebutuhan.

![Sektor investasi](gambar/alokasi/sektor-investasi.png)

![Kawasan investasi](gambar/alokasi/kawasan-investasi.png)

## 6.8 Pertanyaan umum

**Tombol Selesaikan tidak muncul.** Investor belum menerima penawaran. Tunggu jawaban investor atau perbarui penawarannya.

**Investor tidak melihat catatan saya.** Catatan di bagian **Penanganan** memang internal. Gunakan **Pesan dengan investor** untuk berkomunikasi.
