# SimLahan – Sistem Informasi Manajemen Lahan & Pengadaan Tanah

SimLahan adalah aplikasi web untuk instansi pengelola lahan di Indonesia:

- **Pengadaan tanah untuk kepentingan umum** (UU 2/2012 jo. UU 6/2023, PP 19/2021
  jo. PP 39/2023, Perma 3/2016 jo. Perma 2/2021): proyek, tahapan & tonggak,
  bidang tanah + peta, pihak yang berhak, inventarisasi Satgas A/B beserta
  rincian objek (bangunan, tanaman, kolam, dll.) dan pemiliknya, pengumuman,
  penilaian KJPP, musyawarah, keberatan/PTUN/kasasi, konsinyasi, ganti
  kerugian + validasi Ketua Pelaksana + pembayaran, pelepasan hak, penyerahan
  hasil, rumah tangga terdampak, dan arsip dokumen.
- **Pemantauan tenggat hukum** dalam hari kerja (libur nasional & cuti bersama
  2025–2027 sudah dimuat), dasbor, dan surel pengingat tiap hari kerja
  pukul 07.00 WIB.
- **Alokasi lahan & portal pemohon**: peta lahan tersedia, pendaftaran akun
  pemohon, permohonan alokasi tanah dan izin peralihan hak secara daring,
  verifikasi kelengkapan & penilaian teknis berbobot, tagihan UWT dan biaya
  administrasi, penerbitan KPT/PPT/izin peralihan ber-QR, cek keaslian
  dokumen, pelaporan izin & progres pembangunan, pemantauan lahan tidur, dan
  pencabutan alokasi.
- **Manajemen aset lahan**: inventaris aset + batas bidang, rantai kepemilikan,
  silsilah ahli waris, pemangku kepentingan, penilaian, pajak, transaksi &
  ekspor jurnal ERP, perkara & jadwal sidang, okupasi/perambahan + citra
  satelit/drone/LiDAR, jadwal pemantauan lapangan, permukiman kembali, survei,
  fasilitator & urusan instansi, tugas & Gantt, pengaduan masyarakat,
  lelang/seleksi lahan, dokumen ber-OCR, peta tematik + lapisan referensi,
  peta berbagi, pembuat laporan, asisten AI dengan unduhan laporan, aplikasi
  lapangan luring (PWA), OTP surel, OAuth2 untuk integrasi, dan pengingat
  otomatis surel/WhatsApp.
- **Pusat komando operasi lapangan** (`/komando/`, PWA): peta operasi per
  Korwil dengan statistik warga/sikap/RTRW/status lahan/uji tanah, ukur jarak &
  luas, cetak peta PNG A3–A0, perintah suara, pencarian & Power Mode, AI Satelit
  (analisis kotak area), kompas & posisi Live tim, SOS, chat internal, absensi
  GPS + izin/sakit/cuti, laporan kegiatan & uji tanah, pendataan sikap warga,
  tugas wilayah, KPI petugas, antrean luring, dan kunci hidup sistem.
- **Manajemen sewa/pemanfaatan lahan** warisan MVJ: kontrak, penyewa, tarif,
  tagihan, jaminan, penagihan, laporan, peta, catatan area.

Dibangun di atas [City-of-Helsinki/mvj](https://github.com/City-of-Helsinki/mvj)
dan [mvj-ui](https://github.com/City-of-Helsinki/mvj-ui) (MIT) yang telah
dilokalkan ke Bahasa Indonesia, diganti login lokalnya, dan dicabut seluruh
integrasi khusus Kota Helsinki. Lihat [NOTICE.md](NOTICE.md).

## Menjalankan (Docker Compose)

Prasyarat: Docker 24+ dengan Compose v2, akses internet saat build.

```bash
./scripts/setup-env.sh          # membuat .env + rahasia acak, menampilkan sandi admin
# sesuaikan .env: ORGANIZATION_NAME, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, peta, SMTP
docker compose up -d --build
```

Buka `http://localhost:8080` lalu masuk dengan akun `admin` dan sandi yang
ditampilkan skrip. Pada start pertama backend otomatis menjalankan migrasi,
memuat data master (514 kabupaten/kota, 7.285 kecamatan, tarif PPN, aturan
tenggat, hari libur, dsb.), menyetel izin grup, dan membuat admin awal.

| Alamat | Isi |
|---|---|
| `/` | Aplikasi petugas |
| `/portal/` | Portal publik & pemohon alokasi lahan |
| `/admin/alokasi/` | Panel petugas alokasi lahan |
| `/admin/` | Panel admin SimLahan (pengguna, grup, unit layanan, data master) |
| `/docs/` | Dokumentasi API (Swagger), perlu masuk |
| `/healthz`, `/readiness` | Pemeriksaan kesehatan |

Layanan: `db` (PostGIS 16), `backend` (uWSGI), `qcluster` (laporan & surel
latar), `batchrun` (penjadwal), `frontend` (nginx + SPA, sekaligus reverse proxy).

### Produksi

1. Pasang di belakang HTTPS (mis. Caddy/Traefik/nginx di depan port `HTTP_PORT`),
   lalu set `SESSION_COOKIE_SECURE=1`, `CSRF_COOKIE_SECURE=1`,
   `CSRF_TRUSTED_ORIGINS=https://domain-anda`, `OFFICER_UI_URL=https://domain-anda`,
   dan `TRUSTED_PROXY_COUNT=2`.
2. **Cadangkan `FIELD_ENCRYPTION_KEY`** di tempat aman. NIK, nomor rekening,
   dan nomor KK dienkripsi di basis data; tanpa kunci ini data tersebut tidak
   dapat dibaca kembali.
3. Isi `EMAIL_URL` (SMTP) agar pengingat tenggat & laporan terkirim.
4. Cadangkan volume `db_data` dan `private_files` secara berkala, mis.
   `docker compose exec db pg_dump -U simlahan simlahan > cadangan.sql`.
5. Perbarui daftar hari libur setiap tahun di **Pengadaan Tanah → Kalender &
   aturan tenggat** sesuai SKB 3 Menteri.

## Pengguna & hak akses

Grup bawaan (atur di `/admin/` → Pengguna):

| Grup | Pengadaan tanah | Data pribadi (NIK/rekening) |
|---|---|---|
| Administrator | penuh | ya |
| Pelaksana Pengadaan Tanah | penuh, termasuk validasi ganti kerugian, kalender & aturan tenggat | ya |
| Satgas Pengadaan Tanah | bidang, inventarisasi, pihak, pengumuman, musyawarah, pelepasan hak, rumah tangga terdampak; tonggak inventarisasi, musyawarah & pelepasan hak (status, tanggal realisasi, catatan) | ya |
| Penilai Pertanahan | penilaian & dokumen, hanya pada proyek yang ditugaskan | tidak (tersamar) |
| Instansi Yang Memerlukan Tanah | baca proyek, bidang, pengumuman, musyawarah, penyerahan; unggah dokumen perencanaan (DPPT, studi kelayakan), BAST, foto & lainnya; hanya proyek yang ditugaskan, tanpa nilai uang | tidak (pihak tidak terlihat) |
| Ahli Hukum Penagihan | keberatan, konsinyasi, dokumen | tidak (tersamar) |
| Petugas Penagihan | pembayaran & penyerahan ganti kerugian yang sudah divalidasi | tidak (tersamar) |
| Penelusur, Penyusun, Penyusun Kontrak, Operator Entri Data | baca | tidak (tersamar) |

Catatan pengadaan tanah:

- Penilai dan Instansi Pemohon hanya melihat proyek yang ditugaskan kepadanya
  (isian **Pengguna yang ditugaskan** pada data proyek, di aplikasi atau
  `/admin/`). Grup lain melihat semua proyek.
- Status ganti kerugian tidak diisi manual: Ketua Pelaksana memvalidasi atau
  membatalkan, pembayaran/penyerahan dan konsinyasi memperbaruinya otomatis.
  Mengubah nilai, pihak, bentuk ganti kerugian atau rekening pihak setelah
  validasi mengembalikannya ke status ditetapkan (perlu validasi ulang).
- Penilaian berstatus final tidak dapat diubah; catat penilaian baru lalu
  tandai yang lama sebagai direvisi.
- Pindaian KTP, sertipikat, bukti bayar dan dokumen yang dikaitkan ke pihak
  hanya terlihat oleh pemegang izin data pribadi.

Grup alokasi lahan (anggotanya otomatis diberi akses `/admin/`):

| Grup | Alokasi lahan |
|---|---|
| Petugas Alokasi Lahan | data lahan & konten portal, pemeriksaan kelengkapan, perbaikan, persetujuan/penolakan, verifikasi pembayaran, pencabutan alokasi; menerima ringkasan pemantauan mingguan |
| Tim Verifikasi Teknis | baca permohonan, tagihan & alokasi, penilaian teknis per kriteria |

Grup manajemen aset lahan (anggotanya otomatis diberi akses `/admin/`):

| Grup | Manajemen aset lahan |
|---|---|
| Petugas Aset Lahan | seluruh data aset, keuangan, okupasi, permukiman kembali, pengaduan, lelang, dokumen, peta berbagi; baca perkara |
| Petugas Hukum | perkara, advokat & jadwal sidang, dokumen perkara; tindak lanjut okupasi & pengaduan, urusan instansi, tugas; baca aset, kepemilikan, pemangku kepentingan & survei (tanpa penilaian, pajak, transaksi, dan peta berbagi) |
| Petugas Lapangan | aplikasi lapangan, laporan & foto lapangan, okupasi & tindakan teguran, survei, tindak lanjut pengaduan, pembaruan status & progres tugas sendiri; di pusat komando: absen, lapor kegiatan & uji tanah, data warga, chat, SOS |
| Koordinator Wilayah | semua hak petugas lapangan di pusat komando untuk Korwil yang dipimpin, ditambah verifikasi laporan, penanganan SOS, KPI anggota, dan tugas wilayah (hanya tugas Korwil yang dipimpin/diikuti) |

Petugas hanya melihat data unit layanannya (data tanpa unit layanan terlihat
semua); grup Administrator melihat seluruh lokasi. Dokumen hanya terlihat bila
objek yang ditautkan (perkara, lelang, okupasi, dll.) juga boleh dilihat, dan
mengubah/menghapusnya memerlukan izin ubah/hapus atas objek tersebut. Tautan ke
modul lain (bidang pengadaan, lahan alokasi, sewa, Korwil) hanya tampil bagi
yang berhak melihat modul itu. Peta berbagi hanya boleh memuat data yang boleh
dilihat pembuatnya dan terlihat oleh petugas unit layanannya.

Pemohon mendaftar sendiri di `/portal/daftar/` dan tidak bisa masuk ke
aplikasi petugas atau API. Akun petugas tidak bisa masuk ke portal.

Setiap pengguna juga perlu minimal satu **unit layanan** (untuk modul sewa).
Ganti kerugian wajib divalidasi Ketua Pelaksana (izin *validasi ganti
kerugian*, dimiliki grup Administrator dan Pelaksana) sebelum dapat dibayar;
pelepasan hak hanya bisa dicatat setelah ganti kerugian lunas atau dititipkan.

## Konfigurasi utama (`.env`)

| Variabel | Keterangan |
|---|---|
| `SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `POSTGRES_PASSWORD` | Rahasia (dibuat `setup-env.sh`) |
| `ORGANIZATION_NAME`, `APP_NAME` | Nama instansi/aplikasi di layar & surel |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Domain akses |
| `TRUST_PROXY_HEADERS`, `TRUSTED_PROXY_COUNT` | Backend di belakang reverse proxy (aktif di compose). `TRUSTED_PROXY_COUNT` = jumlah proxy yang menambah `X-Forwarded-For`: `1` untuk compose saja, `2` bila ada nginx/Caddy HTTPS di depan `HTTP_PORT`; dipakai untuk pembatasan percobaan per pengunjung di portal |
| `MAP_CENTER_LAT/LNG`, `MAP_DEFAULT_ZOOM`, `PRIMARY_MUNICIPALITY` | Tampilan peta & pencarian (bawaan Pulau Rempang: `0.87`, `104.15`, `12`, `Kota Batam`; seluruh Indonesia: `-2.5`, `118`, `5`) |
| `MAP_WMS_URL`, `MAP_WMS_LAYERS` | Layer WMS instansi (peta bidang, RDTR) |
| `EMAIL_URL`, `DEFAULT_FROM_EMAIL` | Surel keluar (wajib untuk aktivasi akun pemohon) |
| `OFFICER_UI_URL` | Alamat publik, mis. `https://domain-anda`; dipakai untuk tautan surel portal dan kode QR KPT/PPT |
| `JWT_ACCESS_TOKEN_MINUTES`, `JWT_REFRESH_TOKEN_HOURS` | Masa berlaku sesi |
| `OFFICER_OTP_REQUIRED` | `1` = petugas wajib memasukkan kode OTP surel setiap masuk |
| `MAP_EXTRA_BASEMAPS` | Peta dasar tambahan (JSON), mis. citra berlisensi milik instansi |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Asisten AI & pembacaan dokumen pindaian (opsional) |
| `OCR_LANGUAGES` | Bahasa Tesseract, bawaan `ind+eng` |
| `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` | Notifikasi WhatsApp Cloud API (opsional) |

Variabel peta/aplikasi dibaca saat build frontend; setelah mengubahnya jalankan
`docker compose up -d --build frontend`.

## Impor peta bidang

Di tab **Bidang & peta** sebuah proyek, unggah GeoJSON atau shapefile (.zip
berisi .shp/.shx/.dbf/.prj). Koordinat otomatis diubah ke WGS84; atribut nomor
bidang (default `parcel_number`) dan luas dapat dipilih. Bidang bernomor sama
diperbarui, bukan digandakan. Daftar nominatif dapat diunduh sebagai .xlsx.

## Data contoh Rempang

Untuk uji coba, buat proyek contoh `[CONTOH] Pengadaan Tanah Pulau Rempang`
berisi 6 bidang fiktif di Kel. Rempang Cate & Sembulang (Kec. Galang):

```sh
docker compose exec backend python manage.py pengadaan_contoh_rempang          # buat
docker compose exec backend python manage.py pengadaan_contoh_rempang --hapus  # hapus
```

Nama pihak, luas, dan batas bidang bukan data resmi atau hasil ukur. `--hapus`
menghapus permanen proyek contoh beserta **semua** data di bawahnya, termasuk
yang ditambahkan manual ke proyek itu.

## Alokasi lahan

1. Atur nama otoritas, pejabat penanda tangan, biaya administrasi, jangka
   waktu bawaan, nilai minimum verifikasi, dan batas lahan tidur di
   `/admin/alokasi/allocationsettings/`. Tarif UWT diisi per lahan.
   Persyaratan dokumen, kriteria penilaian, dan halaman informasi portal
   sudah terisi contoh dan dapat diubah.
2. Masukkan lahan lewat `/admin/alokasi/landplot/` (gambar di peta atau
   **Impor GeoJSON**), lalu terbitkan agar tampil di portal. Dari baris
   perintah:

   ```sh
   docker compose exec backend python manage.py alokasi_impor_lahan lahan.geojson --tampilkan
   ```

3. Alur: pemohon mengajukan → petugas memeriksa kelengkapan → Tim Verifikasi
   Teknis menilai → petugas menyetujui → tagihan terbit → pemohon mengunggah
   bukti bayar → petugas memverifikasi → KPT dan PPT terbit otomatis.
   Peralihan hak mengikuti alur yang sama dan menerbitkan izin peralihan.
4. Pemantauan otomatis tiap Senin 07.30 WIB (`alokasi_pemantauan --email`):
   alokasi kedaluwarsa, lahan tidur, laporan progres terlambat, dan tagihan
   belum dibayar. Jalankan manual tanpa surel dengan
   `docker compose exec backend python manage.py alokasi_pemantauan`.

Data contoh 6 lahan fiktif di Pulau Rempang:

```sh
docker compose exec backend python manage.py alokasi_contoh_rempang          # buat
docker compose exec backend python manage.py alokasi_contoh_rempang --hapus  # hapus
```

## Manajemen aset lahan

Panel petugas di `/admin/asetlahan/` (juga dari menu **Manajemen Aset Lahan**
di aplikasi petugas). Aktifkan/nonaktifkan submodul dan atur batas pengingat
di **Pengaturan modul**.

| Kebutuhan | Tempat |
|---|---|
| Inventaris aset, batas bidang, impor SHP/KML/GPKG/GeoJSON, ekspor Excel | Aset lahan → **Impor peta** / aksi ekspor |
| Kepemilikan, silsilah ahli waris (pohon), pemangku kepentingan & matriks pengaruh | Aset lahan, Silsilah ahli waris, Pemangku kepentingan |
| Penilaian, pajak (PBB/BPHTB/UWT), transaksi, jurnal ERP (CSV/Excel), buku besar gabungan | Penilaian aset, Pajak & retribusi, Transaksi, **Buku besar** |
| Perkara, advokat, jadwal sidang + pengingat | Perkara & advokat |
| Okupasi/perambahan, tindakan teguran, citra & data udara (satelit, drone, pesawat; optik, multispektral, inframerah, radar, ortofoto, DEM, LiDAR) & pembanding sebelum–sesudah | Okupasi & perambahan, Citra satelit, **Pembanding citra** |
| Jadwal pemantauan lapangan berkala per aset (bawaan di Pengaturan modul, 0 = nonaktif); laporan lapangan memperbarui tanggal pantau terakhir | Aset lahan → Pemantauan lapangan |
| Tumpang tindih batas antar-aset dan dengan bidang pengadaan/alokasi | **Tumpang tindih** |
| Permukiman kembali (kawasan, kavling, penghuni) | Kawasan & unit permukiman kembali |
| Survei & pengukuran, fasilitator, urusan instansi (balik nama, cek sertipikat, pengukuran, penlok, KKPR, PBG, lingkungan, penilaian, pajak, dll.) | Survei & pemetaan, Fasilitator, Urusan instansi |
| Tugas, tim, ketergantungan, Gantt | Tugas, **Jadwal (Gantt)** |
| Dokumen + OCR (PDF, foto, DOCX) dan pengisian otomatis data aset | Dokumen & arsip |
| Peta tematik semua modul, peta berbagi baca-saja bertautan | **Peta tematik**, Peta berbagi |
| Lapisan referensi (batas administrasi, kadaster, sungai, jalan, hutan, tata ruang, utilitas) dari GeoJSON/KML/SHP/GPKG | Lapisan peta referensi → tampil di **Peta tematik** |
| Pembuat laporan (pilih data/kolom/filter → Excel, CSV, PDF) | **Pembuat laporan** |
| Pencarian lintas modul termasuk isi dokumen | **Pencarian** |
| Asisten AI (tanya data dengan bahasa sehari-hari; tiap tabel jawaban dapat diunduh Excel/PDF/CSV) | **Asisten AI** |
| Pengaduan masyarakat (nomor + kode akses, cek status) | Portal `/portal/pengaduan/` |
| Lelang/seleksi pemanfaatan lahan dan penawaran daring | Portal `/portal/lelang/` |
| Aplikasi petugas lapangan (GPS, foto, luring, dapat dipasang di ponsel) | `/aset/lapangan/` |
| API baca-saja untuk sistem lain (JWT atau OAuth2) | `/v1/aset/asset/`, `tax/`, `transaction/`, `legal_case/`, `encroachment/`, `task/`, `grievance/`, `tender/` |

Pengingat harian 06.30 WIB (`asetlahan_pengingat --email`): sewa dan hak atas
tanah yang segera berakhir, pajak jatuh tempo, sidang mendatang (juga ke kuasa
hukum, surel/WhatsApp), tugas dan pengaduan lewat tenggat, okupasi tanpa tindak
lanjut, aset yang belum dipantau sesuai jadwal, dan urusan instansi. Ringkasan
dikirim per petugas, hanya berisi data unit layanan dan jenis data yang boleh
ia lihat. Jalankan manual tanpa mengirim:
`docker compose exec backend python manage.py asetlahan_pengingat`.

Asisten AI tetap menjawab pertanyaan umum (sewa berakhir, okupasi per zona,
alokasi per bulan/tahun, pemantauan, sidang, pajak, tugas, pengaduan,
ringkasan, keuangan, pencarian) tanpa
`ANTHROPIC_API_KEY`; dengan kunci, pertanyaan bebas dijawab Claude memakai
data yang boleh dilihat penanya. Peta dasar Google/Bing memerlukan lisensi;
tambahkan lewat `MAP_EXTRA_BASEMAPS`.

Data contoh 5 aset fiktif di Pulau Rempang beserta perkara, okupasi,
permukiman kembali, pengaduan, dan lelang:

```sh
docker compose exec backend python manage.py asetlahan_contoh_rempang          # buat
docker compose exec backend python manage.py asetlahan_contoh_rempang --hapus  # hapus
```

## Pusat komando operasi lapangan

Buka `/komando/` (juga menu **Pusat Komando** di aplikasi petugas); dapat
dipasang di ponsel dan tetap bisa mencatat saat luring (data dikirim otomatis
ketika sinyal kembali). Pintasan: `/komando/?tab=absen`, `?tab=korwil` (lapor),
`?tab=perf` (kinerja), `?tab=tasks` (tugas). Tekan `Ctrl+K` atau `/` untuk
pencarian & Power Mode.

Pemisahan data: Administrator, superuser, dan Petugas Aset Lahan melihat data
per unit layanan. Petugas Lapangan dan Koordinator Wilayah hanya melihat Korwil
tempat mereka menjadi anggota atau koordinator (warga, kegiatan, uji tanah,
SOS, chat, berkas, lapisan peta, posisi Live, ringkasan, dan panel); data tanpa
Korwil hanya terlihat oleh pembuatnya. Data baru yang lokasinya di Korwil lain
masuk ke satu-satunya Korwil petugas, atau ditolak bila petugas memegang lebih
dari satu Korwil (SOS tidak pernah ditolak). NIK & nomor KK warga hanya tampil
bagi pemegang izin "Dapat melihat NIK dan nomor KK warga" (Administrator).
Izin, sakit, cuti, dan dinas luar baru dihitung pada KPI setelah disetujui
koordinator Korwil (tab Absen → Persetujuan izin tim) atau Administrator
(panel Absensi → tindakan Setujui/Tolak); penerima tugas tidak dapat
membatalkan tugasnya sendiri. Tombol **Keluar** di pusat komando menghapus
lapisan peta tersimpan dan antrean luring dari perangkat.

| Kebutuhan | Tempat |
|---|---|
| Korwil (kode, nama, warna, batas wilayah, koordinator, anggota), impor batas dari GeoJSON/KML/SHP/GPKG | `/admin/operasi/` → Korwil (koordinator wilayah) → **Impor batas SHP/KML/GeoJSON** |
| Data warga (KK, NIK terenkripsi, sikap, status lahan, kesesuaian RTRW, pilihan penyelesaian, riwayat sikap), impor CSV/GeoJSON, ekspor CSV tanpa NIK | Warga terdata → **Impor CSV / SHP** |
| Laporan kegiatan + foto, verifikasi koordinator, ekspor CSV | Laporan kegiatan |
| Uji tanah (pH, kadar air, C-organik, daya dukung, CBR, kelayakan, laporan lab) | Uji tanah |
| Absensi (jam kerja, toleransi terlambat, swafoto & geofence opsional), koreksi oleh Administrator | Absensi, **Pengaturan pusat komando** |
| Bobot KPI (kehadiran, kegiatan, tugas), target kegiatan mingguan, penerima surel SOS, server citra AI Satelit | **Pengaturan pusat komando** |
| SOS (ditangani / selesai / alarm palsu), chat, posisi Live, riwayat AI Satelit | Tanda darurat (SOS), Chat internal, Posisi petugas (Live), Analisis AI Satelit |
| Tugas per Korwil | Manajemen aset lahan → Tugas (kolom Korwil) |

Kolom impor warga (CSV, pemisah `,` `;` atau tab; atau GeoJSON/KML/SHP/GPKG):
`nama` (wajib), `nik`, `kk`, `jiwa`, `telepon`, `kampung`, `alamat`, `korwil`
(kode), `lat`, `lng`, `sikap` (pro/netral/kontra), `status_lahan`
(sudah/belum), `rtrw` (sesuai/tidak), `pilihan` (relokasi/kompensasi/geser/lainnya),
`catatan`. NIK yang sama memperbarui warga di wilayah kerja pengimpor (perlu hak
ubah warga; catatan ditambahkan, tidak ditimpa); baris dengan NIK yang tidak
dapat dipakai dilewati. Atribut impor batas Korwil:
`kode` (wajib), `nama`, `warna`.

AI Satelit menganalisis citra kotak area dengan Claude bila `ANTHROPIC_API_KEY`
diisi; tanpa kunci tetap menampilkan mosaik citra dan ringkasan data SimLahan di
area itu. Rekap harian 00.30 WIB (`operasi_harian`) menandai absen tanpa
pulang dan menghapus posisi Live yang lebih dari 24 jam.

**Kunci hidup sistem** (`/admin/operasi/systemlock/`, hanya superuser, mati
secara bawaan): tetapkan kode rahasia dan waktu kunci. Selama hitung mundur
semua pengguna melihat peringatan; bila waktu habis, seluruh aplikasi (kecuali
superuser, halaman masuk, dan pemeriksaan kesehatan) terkunci sampai superuser
memasukkan kode rahasia di pusat komando atau panel admin.

Data contoh 11 Korwil (A–K) fiktif di Pulau Rempang beserta warga, kegiatan,
uji tanah, dan tugas:

```sh
docker compose exec backend python manage.py operasi_contoh_rempang          # buat
docker compose exec backend python manage.py operasi_contoh_rempang --hapus  # hapus
```

## Integrasi OAuth2

Sistem lain (ERP, GIS, dasbor) dapat memakai API `/v1/` dengan OAuth2:

1. Buat akun layanan (pengguna biasa) dengan grup dan unit layanan sesuai data
   yang boleh diakses.
2. Di `/admin/oauth2_provider/application/` tambahkan aplikasi: *Client type*
   `Confidential`, *Authorization grant type* `Client credentials`, *User*
   akun layanan tadi. **Salin *Client secret* sebelum menyimpan**; setelah
   disimpan hanya hash-nya yang tersimpan.
3. Minta token lalu panggil API:

   ```sh
   curl -X POST https://domain-anda/oauth/token/ -u "CLIENT_ID:CLIENT_SECRET" \
     -d grant_type=client_credentials -d scope=read
   curl https://domain-anda/v1/aset/asset/ -H "Authorization: Bearer TOKEN"
   ```

Scope `read` hanya membaca; perubahan data memerlukan `write`. Token berlaku
1 jam. Grant *Authorization code* (dengan PKCE, redirect `https`) juga tersedia
lewat `/oauth/authorize/` memakai login panel petugas.

## Pengembangan

- Backend: lihat [backend/README.md](backend/README.md) — `pytest`, `flake8`.
- Frontend: lihat [frontend/README.md](frontend/README.md) — `yarn test`, `yarn lint`, `yarn build`.

## Lisensi

MIT – lihat [LICENSE](LICENSE) dan [NOTICE.md](NOTICE.md).
