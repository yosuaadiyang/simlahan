# SimLahan – Sistem Informasi Manajemen Lahan & Pengadaan Tanah

SimLahan adalah aplikasi web untuk instansi pengelola lahan di Indonesia:

- **Pengadaan tanah untuk kepentingan umum** (UU 2/2012 jo. UU 6/2023, PP 19/2021
  jo. PP 39/2023, Perma 3/2016 jo. Perma 2/2021): proyek, tahapan & tonggak,
  bidang tanah + peta, pihak yang berhak, inventarisasi Satgas A/B, pengumuman,
  penilaian KJPP, musyawarah, keberatan/PTUN/kasasi, konsinyasi, ganti
  kerugian + validasi Ketua Pelaksana + pembayaran, pelepasan hak, penyerahan
  hasil, rumah tangga terdampak, dan arsip dokumen.
- **Pemantauan tenggat hukum** dalam hari kerja (libur nasional & cuti bersama
  2025–2027 sudah dimuat), dasbor, dan surel pengingat tiap hari kerja
  pukul 07.00 WIB.
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
| `/admin/` | Admin Django (pengguna, grup, unit layanan, data master) |
| `/docs/` | Dokumentasi API (Swagger) |
| `/healthz`, `/readiness` | Pemeriksaan kesehatan |

Layanan: `db` (PostGIS 16), `backend` (uWSGI), `qcluster` (laporan & surel
latar), `batchrun` (penjadwal), `frontend` (nginx + SPA, sekaligus reverse proxy).

### Produksi

1. Pasang di belakang HTTPS (mis. Caddy/Traefik/nginx di depan port `HTTP_PORT`),
   lalu set `SESSION_COOKIE_SECURE=1`, `CSRF_COOKIE_SECURE=1`, dan
   `CSRF_TRUSTED_ORIGINS=https://domain-anda`.
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
| Satgas Pengadaan Tanah | bidang, inventarisasi, pihak, pengumuman, musyawarah, pelepasan hak, rumah tangga terdampak | ya |
| Penilai Pertanahan | penilaian & dokumen | tidak (tersamar) |
| Instansi Yang Memerlukan Tanah | baca proyek, bidang, pengumuman, musyawarah, penyerahan; unggah dokumen | tidak (pihak tidak terlihat) |
| Ahli Hukum Penagihan | keberatan, konsinyasi, dokumen | tidak (tersamar) |
| Petugas Penagihan | ganti kerugian & pembayaran | tidak (tersamar) |
| Penelusur, Penyusun, Penyusun Kontrak, Operator Entri Data | baca | tidak (tersamar) |

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
| `MAP_CENTER_LAT/LNG`, `MAP_DEFAULT_ZOOM`, `PRIMARY_MUNICIPALITY` | Tampilan peta & pencarian (bawaan Pulau Rempang: `0.87`, `104.15`, `12`, `Kota Batam`; seluruh Indonesia: `-2.5`, `118`, `5`) |
| `MAP_WMS_URL`, `MAP_WMS_LAYERS` | Layer WMS instansi (peta bidang, RDTR) |
| `EMAIL_URL`, `DEFAULT_FROM_EMAIL` | Surel keluar |
| `JWT_ACCESS_TOKEN_MINUTES`, `JWT_REFRESH_TOKEN_HOURS` | Masa berlaku sesi |

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

## Pengembangan

- Backend: lihat [backend/README.md](backend/README.md) — `pytest`, `flake8`.
- Frontend: lihat [frontend/README.md](frontend/README.md) — `yarn test`, `yarn lint`, `yarn build`.

## Lisensi

MIT – lihat [LICENSE](LICENSE) dan [NOTICE.md](NOTICE.md).
