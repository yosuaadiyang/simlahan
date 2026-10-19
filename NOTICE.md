# Atribusi pihak ketiga

SimLahan merupakan karya turunan dan memakai komponen berikut. Seluruh lisensi
di bawah ini mengizinkan penggunaan, modifikasi, dan distribusi (termasuk
komersial) selama pemberitahuan hak cipta dipertahankan.

| Komponen | Sumber | Lisensi | Pemakaian |
|---|---|---|---|
| mvj (backend Maanvuokrausjärjestelmä) | City of Helsinki – github.com/City-of-Helsinki/mvj @162250ad | MIT | Basis backend. Integrasi khusus Helsinki dihapus. |
| mvj-ui | City of Helsinki – github.com/City-of-Helsinki/mvj-ui @3369a436 | MIT | Basis frontend (React). |
| land-acquisition-management-system (NLAMS) | AtulTejaswi – github.com/AtulTejaswi/land-acquisition-management-system | MIT | Rujukan domain model modul pengadaan tanah (proyek, bidang, pihak, survei, penilaian, musyawarah, keberatan, ganti kerugian, dokumen). Kode ditulis ulang untuk SimLahan & regulasi Indonesia; tidak ada kode yang disalin langsung. |
| wilayah | Cahya DSN – github.com/cahyadsn/wilayah | MIT | Data kode & nama provinsi, kabupaten/kota, kecamatan (Kepmendagri 300.2.2-2430/2025). |
| hds-react / hds-design-tokens | City of Helsinki | MIT | Komponen UI. Font Helsinki Grotesk **tidak** dipakai. |
| Leaflet, react-leaflet, leaflet-draw, leaflet-geosearch | masing-masing | BSD-2 / MIT | Peta. |

Layanan eksternal bawaan (dapat diganti lewat konfigurasi):

- Ubin peta & geocoding **OpenStreetMap** (© kontributor OpenStreetMap, ODbL).
  Untuk pemakaian berat ikuti kebijakan penggunaan tile/Nominatim atau gunakan
  server sendiri (`VITE_GEOCODER_URL`, `VITE_MAP_WMS_URL`).
- Citra satelit **Esri World Imagery** – tunduk pada ketentuan Esri.

Logo dan nama SimLahan adalah aset baru, bukan milik Kota Helsinki.
