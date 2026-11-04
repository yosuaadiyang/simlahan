# Bab 11 – Data pusat komando di panel admin

Semua data pusat komando juga bisa dikelola dalam bentuk tabel di **Panel admin → Pusat komando operasi lapangan**. Di sini Administrator menyiapkan Korwil, anggota, atasan, bobot poin, dan pengaturan; petugas dan koordinator bisa membaca, menyaring, dan mengekspor data dalam cakupannya.

**Siapa memakai bab ini:** Administrator (semua), Koordinator Wilayah dan Petugas Lapangan (data Korwilnya, sesuai hak di [Bab 10](40-pusat-komando.md)), Petugas Aset Lahan (membaca untuk unit layanannya).

![Menu pusat komando di panel admin](gambar/lapangan/panel-operasi.png)

## 11.1 Korwil (koordinator wilayah)

![Daftar Korwil](gambar/lapangan/op-korwil.png)

Tombol di atas daftar: **Buka pusat komando**, **Impor batas SHP/KML/KMZ/GeoJSON**, dan **Tambahkan Korwil (koordinator wilayah)**.

**Menambah atau mengubah Korwil:**

![Halaman Korwil](gambar/lapangan/op-korwil-detail.png)

1. Isi **Kode** (misalnya A, B, … K), **Nama wilayah**, **Warna peta** (#RRGGBB), centang **Aktif**, dan **Unit layanan / lokasi**.
2. Di bagian **Petugas**, pilih **Koordinator**, lalu pindahkan nama petugas dari kotak **Petugas yang tersedia** ke **Petugas terpilih** dengan tombol panah. Hanya anggota ini yang bisa melapor untuk Korwil tersebut.
3. Di bagian **Wilayah**, gambar batas Korwil di peta (atau impor dari berkas).
4. Klik **Simpan**.

**Mengimpor batas:** klik **Impor batas SHP/KML/KMZ/GeoJSON**, pilih berkas GeoJSON, KML/KMZ, GeoPackage, atau Shapefile dalam ZIP berisi poligon. Atribut yang dikenali: `kode` (wajib), `nama`, `warna`, `kampung`. Korwil dengan kode yang sudah ada diperbarui batasnya.

## 11.2 Warga terdata

![Daftar warga](gambar/lapangan/op-resident.png)

Saringan: **Korwil**, **Sikap terhadap program**, **Status lahan**, **Kesesuaian RTRW**, **Pilihan penyelesaian**, **Kampung**. Tombol **Buka di pusat komando** membuka peta warga. Kolom NIK dan KK hanya tampil untuk Administrator. Setiap perubahan sikap tercatat di riwayat warga.

**Mengimpor warga:** klik **Impor CSV / SHP**. Berkas CSV (pemisah koma atau titik koma) atau berkas titik (GeoJSON, KML/KMZ, GeoPackage, Shapefile ZIP). Kolom yang dikenali:

`nama` (wajib), `nik`, `kk`, `jiwa`, `telepon`, `kampung`, `alamat`, `korwil`, `lat`, `lng`, `sikap` (pro/netral/kontra), `status_lahan` (sudah/belum), `rtrw` (sesuai/tidak), `pilihan` (relokasi/uang/geser), `catatan`, `zona` (lindung/budi daya/khusus/lainnya), `jenis_kelamin` (L/P), `umur`, `pekerjaan`, `asal`, `lama_menetap`, `pasangan`, `anak`, `luas_lahan` (m²), `penggarapan` (digarapi/disewakan/tidak), `kondisi_lahan`.

Warga dengan NIK yang sudah ada diperbarui; baris dengan NIK yang tidak dapat dipakai dilewati. Untuk mengunduh data, centang baris, pilih aksi **Ekspor CSV**, klik **Jalankan**.

## 11.3 Laporan kegiatan

![Laporan kegiatan](gambar/lapangan/op-activity.png)

Saringan: **Jenis kegiatan**, **Korwil**, **Diverifikasi koordinator**, **Dampak tinggi dikonfirmasi atasan**, **Waktu kegiatan**. Aksi:

- **Tandai sudah diverifikasi** (koordinator): memverifikasi laporan anggota.
- **Konfirmasi dampak tinggi (Kegiatan lainnya)** (atasan): mengakui klaim dampak Signifikan/Kritis sehingga poin penuh dihitung.
- **Ekspor CSV**.

## 11.4 Absensi

![Absensi](gambar/lapangan/op-attendance.png)

Saringan: **Status**, **Persetujuan izin**, **Korwil**, **Lupa absen pulang**, **Masuk di wilayah**, **Tanggal**. Aksi **Setujui pengajuan izin** dan **Tolak pengajuan izin** (koordinator), serta **Ekspor CSV**.

## 11.5 SOS

![Tanda darurat SOS](gambar/lapangan/op-sosalert.png)

Daftar tanda darurat dengan status **Aktif – butuh bantuan**, **Sedang ditangani**, **Selesai**, atau **Alarm palsu**. Koordinator atau Administrator memilih aksi **Tandai sedang ditangani**, **Tandai selesai**, atau **Tandai alarm palsu**.

## 11.6 Temuan, patroli, dan uji tanah

| Menu | Isi dan tindakan |
|---|---|
| Temuan ilegal | Temuan pembalakan, tambang, perambahan, pembukaan lahan, pembangunan liar beserta kunjungan berulangnya. Saringan **Aktivitas**, **Korwil**. Aksi **Ekspor CSV**. |
| Laporan patroli Taman Buru | Patroli beserta temuan dan bibit. Saringan **Situasi**, **Korwil**, **Waktu kegiatan**. |
| Jejak patroli SMART | Jalur patroli dari SMART Mobile / CyberTracker. Klik **Impor patroli SMART (.json)** untuk mengunggah berkas GeoJSON (maks. 15 MB); jalur, observasi, dan foto tampil di lapisan **Patroli SMART** pusat komando. |
| Uji tanah | Hasil uji tanah lapangan. Saringan **Kelayakan**, **Jenis / tekstur tanah**, **Korwil**, **Waktu pengambilan**. Aksi **Ekspor CSV**. |
| Titik uji tanah PLTS | Titik penyelidikan tanah PLTS. Saringan **Status pekerjaan**, **Status survei**, **Kondisi sosial**, **Bagian proyek**, **Metode**, **Batch**, **Korwil**. Aksi **Unduh Excel**. |

![Temuan ilegal](gambar/lapangan/op-illegalfinding.png)

![Patroli Taman Buru](gambar/lapangan/op-huntingparkpatrol.png)

![Jejak patroli SMART](gambar/lapangan/op-patrolsession.png)

![Uji tanah](gambar/lapangan/op-soiltest.png)

![Titik uji tanah PLTS](gambar/lapangan/op-geotechpoint.png)

## 11.7 Data spasial

| Menu | Isi |
|---|---|
| Bidang lahan (penguasaan) | Bidang yang dikuasai atau belum, dengan **Urgensi** (rendah–mendesak) dan skor prioritas. Aksi **Ekspor CSV**. |
| Zona ancaman | Zona dengan **Tingkat ancaman** dan radius; hapus centang **Aktif** untuk menonaktifkan. |
| Foto situs 360° | Foto panorama per lokasi dan tanggal pengambilan. |
| Analisis AI Satelit | Riwayat analisis area dari tombol 🤖 di peta. |
| Posisi petugas (Live) dan Jejak GPS petugas | Posisi terakhir dan jejak dari mode Live (disimpan 60 hari). |

![Bidang lahan](gambar/lapangan/op-landplot.png)

![Zona ancaman](gambar/lapangan/op-threatzone.png)

![Foto situs 360°](gambar/lapangan/op-sitephoto360.png)

![Analisis AI Satelit](gambar/lapangan/op-areaanalysis.png)

![Posisi petugas](gambar/lapangan/op-officerposition.png)

![Jejak GPS petugas](gambar/lapangan/op-officertrackpoint.png)

## 11.8 Jabatan, tugas, dan laporan harian

**Jabatan & atasan petugas** (Administrator) menentukan ke mana laporan harian setiap petugas dikirim dan siapa boleh memberi tugas kepadanya:

1. Klik **Tambahkan Jabatan & atasan petugas**.
2. Pilih **Petugas**, isi jabatan (misalnya Koordinator Korwil A, Staf manajemen, Penyelia, Pimpinan), dan pilih **Atasan langsung**.
3. Simpan. Ulangi untuk setiap petugas sampai pimpinan puncak (tanpa atasan).

![Jabatan & atasan petugas](gambar/lapangan/op-officerprofile.png)

Menu lain (baca saja untuk sebagian besar peran):

- **Riwayat tugas**: setiap peristiwa tugas (ditugaskan, mulai, dilaporkan selesai, terkendala, dilanjutkan, diverifikasi, dikembalikan, dibatalkan).
- **Poin tugas**: poin per peran (penerima utama, kontributor lapangan, pemberi tugas).
- **Laporan harian berjenjang**: saringan **Status**, **Korwil**, **Tanggal laporan**, **Disusun dengan AI**.

![Riwayat tugas](gambar/lapangan/op-taskevent.png)

![Poin tugas](gambar/lapangan/op-taskpoint.png)

![Laporan harian berjenjang](gambar/lapangan/op-dailyreport.png)

## 11.9 Tiket dan chat

- **Tiket & masukan**: arsip tiket dari pusat komando. Saringan **Status**, **Kategori**, **Prioritas**, **Waktu dibuat**. Petugas hanya melihat tiket miliknya. Administrator memproses tiket di pusat komando (**Menu → Alat & tiket**): Diproses, Selesai (memberi poin untuk pengirim), atau Ditolak dengan alasan.
- **Chat internal**: arsip pesan. Saringan **Pesan sistem**, **Kanal Korwil**, **Dikirim**.

![Tiket](gambar/lapangan/op-ticket.png)

![Chat internal](gambar/lapangan/op-chatmessage.png)

## 11.10 Pengaturan pusat komando (Administrator)

![Pengaturan pusat komando](gambar/lapangan/op-commandsettings.png)

| Bagian | Isian |
|---|---|
| Absensi | **Jam masuk**, **Toleransi terlambat (menit)**, **Jam pulang**, **Wajib swafoto saat absen**, **Tolak absen di luar wilayah Korwil**, **Toleransi jarak dari batas Korwil (m)**. |
| Kinerja (KPI) | **Target kegiatan per petugas per minggu**, **Bobot kehadiran / kegiatan / tugas pada skor kinerja (%)**, **Cara menghitung kegiatan pada KPI** (poin usaha, atau jumlah kegiatan × bobot jenis). |
| Poin usaha kegiatan | **Target poin usaha**, **Poin dasar jenis yang belum diberi bobot**, **Bonus per temuan / maksimal**, **Bonus per foto / maksimal**, **Bonus narasi lengkap** dan panjang minimalnya, **Bonus per km jarak tempuh / maksimal**, **Bonus lokasi GPS (geotag)**. |
| Peta | **Sumber ubin citra satelit untuk AI Satelit** (templat XYZ dengan `{z}`, `{x}`, `{y}`). |
| Live & SOS | **Petugas dianggap daring bila lokasi terakhir dalam (menit)**, **Surel penerima tanda darurat (SOS)**. |

Bobot poin per jenis kegiatan diatur di menu **Bobot kegiatan (KPI)**.

![Pengaturan lengkap](gambar/lapangan/op-pengaturan-full.png)

**Kunci sistem** hanya bisa diatur superuser (lihat [Bab 16](60-superuser.md)).
