# SimLahan – Frontend

Antarmuka petugas SimLahan (React 18 + TypeScript + Vite), turunan
[City-of-Helsinki/mvj-ui](https://github.com/City-of-Helsinki/mvj-ui) (MIT).
Panduan lengkap instalasi ada di [README utama](../README.md).

## Pengembangan

```bash
corepack enable
yarn install
cp apps/leasing/.env.example apps/leasing/.env   # sesuaikan VITE_API_URL
yarn start          # http://localhost:3000
yarn test           # vitest
yarn lint
yarn build          # hasil di dist/
```

Struktur penting:

- `apps/leasing/src/acquisition/` – modul **Pengadaan Tanah** (dasbor, proyek,
  bidang & peta, pihak, penilaian, musyawarah, keberatan, ganti kerugian,
  pelepasan & penyerahan, relokasi, dokumen, kalender hari kerja).
- `apps/leasing/src/auth/` – login lokal JWT (access token di memori, refresh
  token di localStorage, diperbarui otomatis).
- `apps/leasing/src/root/routes.tsx` – rute berbahasa Indonesia.
