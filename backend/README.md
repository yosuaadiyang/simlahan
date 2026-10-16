# SimLahan – Backend

API Django 5.2 + GeoDjango (PostGIS) untuk SimLahan, turunan
[City-of-Helsinki/mvj](https://github.com/City-of-Helsinki/mvj) (MIT).
Panduan instalasi lengkap (Docker) ada di [README utama](../README.md).

## Pengembangan lokal (tanpa Docker)

Prasyarat: Python 3.12, PostgreSQL 16 + PostGIS 3, GDAL/GEOS/PROJ, gettext.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
createdb simlahan && psql simlahan -c "CREATE EXTENSION postgis"
cat > .env <<'ENV'
DEBUG=1
SECRET_KEY=dev-saja
DATABASE_URL=postgis://postgres:postgres@localhost/simlahan
ALLOWED_HOSTS=*
ENV
python manage.py migrate
DJANGO_SUPERUSER_USERNAME=admin DJANGO_SUPERUSER_PASSWORD=admin12345 \
  python manage.py simlahan_bootstrap      # data master, izin grup, admin awal
python manage.py compilemessages -l id
python manage.py runserver                 # http://localhost:8000/docs/
```

## Perintah penting

| Perintah | Fungsi |
|---|---|
| `simlahan_bootstrap [--force-fixtures]` | Muat data master (wilayah, jenis sewa, PPN, grup), setel izin grup, buat admin awal. Idempoten. |
| `pengadaan_cek_tenggat [--email] [--days N]` | Laporan tenggat pengadaan; dijadwalkan batchrun setiap hari kerja 07.00 WIB. |
| `set_group_model_permissions`, `set_group_field_permissions`, `set_report_permissions` | Terapkan ulang matriks izin. |
| `app_makemessages -l id` + `compilemessages` | Perbarui terjemahan. |

## Pengujian

```bash
pytest            # ±1.600 tes, memakai --nomigrations
flake8 && black --check . && isort --check .
```

## Struktur

- `pengadaan/` – modul pengadaan tanah (UU 2/2012 jo. UU 6/2023, PP 19/2021 jo.
  PP 39/2023): model, aturan tenggat hari kerja, status bidang otomatis,
  impor GeoJSON/SHP, ekspor daftar nominatif, enkripsi NIK/rekening (UU PDP).
- `leasing/` – manajemen sewa/pemanfaatan lahan (warisan MVJ).
- `plotsearch/`, `forms/` – pencarian kavling & formulir permohonan.
- `users/auth_views.py` – login JWT (`/v1/auth/login|refresh|logout|me|password`).
- `batchrun/` – penjadwal tugas berkala.
