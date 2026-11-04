# Alat buku panduan

Folder ini berisi alat untuk memperbarui buku panduan di `docs/panduan/`. Pakai sistem latihan, bukan server produksi, karena gambar diambil dari data contoh.

## 1. Ringkasan peran (wajib setelah menu atau hak akses berubah)

Bagian **Ringkasan peran** di setiap buku `peran/*.md` dibuat dari `backend/users/role_guide.py`, sumber yang sama dengan halaman **Panduan peran** di aplikasi.

```
cd backend
python manage.py panduan_buku          # perbarui buku peran
python manage.py panduan_buku --cek    # hanya periksa
python manage.py panduan_peran > ../docs/panduan-peran.md
```

Tes `backend/users/tests/test_user_manual.py` gagal bila buku peran belum diperbarui, ada gambar atau tautan yang rusak, ada gambar yang tidak dipakai, atau ada kata terlarang.

Buku peran baru: tambahkan berkasnya di `BOOK_FILES` (`backend/users/role_books.py`), buat berkas di `peran/` dengan penanda blok (salin dari buku lain), lalu jalankan `panduan_buku` dan tambahkan baris di tabel README buku.

## 2. Menyiapkan sistem latihan

Di sistem latihan (bukan produksi):

```
python manage.py data_contoh
python manage.py pengguna_contoh --sandi '<sandi latihan>'
```

Butuh Node.js 18+ dan Playwright dengan Chromium (`npm install playwright && npx playwright install chromium` bila belum ada).

Variabel lingkungan:

| Variabel | Isi |
|---|---|
| `PANDUAN_SANDI` | Sandi akun contoh (wajib). Jangan ditulis ke berkas di repositori. |
| `PANDUAN_URL` | Alamat sistem latihan. Bawaan `http://localhost:8080`. |
| `PANDUAN_BERSIHKAN_CACHE` | Perintah pengosong cache sebelum setiap masuk, agar tidak terkena batas percobaan masuk. Contoh: `psql -h localhost -U simlahan simlahan -qc "delete from simlahan_cache"` |
| `PANDUAN_CHROMIUM` | Lokasi Chromium bila tidak memakai bawaan Playwright. |
| `PANDUAN_GAMBAR_KE` | Simpan gambar ke folder lain dulu (untuk dibandingkan) alih-alih menimpa `gambar/`. |

## 3. Mengambil ulang gambar

```
cd docs/panduan/alat
node ambil-gambar.js                          # semua
node ambil-gambar.js spesifikasi/sewa.json    # satu folder gambar
```

Setiap berkas `spesifikasi/<folder>.json` menulis ke `gambar/<folder>/`. Isinya kelompok per akun (`login`: `spa`, `admin`, `komando`, `portal`, atau `none`; `user`; `phone` untuk tampilan HP) dan daftar gambar.

Isi setiap gambar:

| Kunci | Arti |
|---|---|
| `name`, `url` | Nama berkas dan alamat halaman. |
| `mark` | Daftar `[selektor, nomor]`. Kotak merah bernomor digambar di sekitar elemennya; nomornya dipakai di teks sebagai "(nomor N)". Elemen yang tidak ada atau di luar layar membuat gambar gagal, jadi gambar tidak pernah salah nomor diam-diam. |
| `actions` | Langkah sebelum memotret: `click`, `fill`/`value`, `select`/`value`, `wait`, `scroll`, `js`. |
| `js` | Skrip yang dijalankan setelah halaman terbuka (misalnya menggulir atau membuka `<details>`). |
| `tinggi` | Tinggi layar khusus (px) untuk formulir panjang. |
| `full` / `el` | Satu halaman penuh / satu bagian saja. |
| `tanpa_gambar` | Langkah navigasi saja. |

Kelompok boleh punya `tautan`: alamat yang baru diketahui setelah masuk sebagai pengguna lain, misalnya `{"KPT": {"login": "admin", "user": "admin", "url": "...", "ambil": "td.field-verify a"}}`. `{KPT}` di `url` gambar diganti dengan alamat tautan itu (dipakai untuk halaman verifikasi dan halaman tanda tangan).

`PANDUAN_HANYA=nama1,nama2` hanya mengambil gambar tertentu (nama berkas tanpa `.png`).

Setelah itu perkecil dan kompres gambar (butuh Pillow dan `pngquant`):

```
./rapikan-gambar.sh
```

## 4. Membuat PDF

```
cd docs/panduan/alat
npm install
node buat-pdf.js            # hasil di alat/keluaran/
```

Hasilnya `panduan-simlahan-lengkap.pdf` dan `peran/<peran>.pdf` (buku peran + Bab 1, Bab 2, dan bab yang ditautkan buku itu). Folder `keluaran/` tidak disimpan di repositori.
