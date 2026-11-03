# Buku peran: Investor

Buku ini untuk **Investor**: investor atau pelaku usaha yang mencari lahan untuk disewa, dialokasikan, atau dikerjasamakan. Baca dulu [Bab 1](../01-mengenal-simlahan.md) dan [Bab 2](../02-dasar-penggunaan.md) bila baru pertama kali memakai SimLahan.

## Masuk

Buka `/portal/masuk/`, isi alamat surel dan kata sandi, lalu klik **Masuk** ([Bab 13.1](../51-portal-pemohon.md#131-masuk-ke-portal)).

![Dasbor investor](../gambar/portal/investor-akun.png)

<!-- awal: dibuat dari backend/users/role_guide.py; perbarui dengan: cd backend && python manage.py panduan_buku -->

## Ringkasan peran

Akun pemohon portal dengan profil investor: mencari lahan, mengajukan minat sewa/alokasi/kerja sama, dan menanggapi penawaran petugas.

- **Cara masuk:** Portal (`/portal/masuk/`) dengan alamat surel; daftar sendiri di `/portal/investasi/daftar/`. Pemohon yang mengajukan minat investasi pertamanya otomatis menjadi investor.
- **Halaman awal:** Portal → Akun saya (dasbor investor).
- **Akun latihan** (hanya di sistem latihan berisi data contoh): `investor@contoh.simlahan.invalid`

### Menu yang Anda lihat

- Portal: Investasi (beranda peluang, peta, kawasan, bandingkan, ajukan minat), Peta Lahan, Layanan, Informasi, Bantuan → Panduan investor
- Dasbor investor: penawaran menunggu jawaban, jadwal konsultasi, permintaan aktif dengan langkah berikutnya, lahan tersimpan, lahan sesuai sektor minat, dokumen & perizinan
- Akun saya → Ubah profil (profil investor: sektor minat, asal modal, negara asal, situs web), Ubah kata sandi

### Yang bisa Anda lakukan

- Semua yang bisa dilakukan pemohon portal.
- Menyimpan dan membandingkan hingga 4 lahan, mengunduh profil lahan (PDF), dan menghitung simulasi biaya.
- Mengajukan minat dengan memilih lahan atau menggambar usulan lokasi; formulir terisi otomatis dari profil investor.
- Berkirim pesan dan lampiran dengan petugas, menerima atau menolak penawaran, serta membatalkan permintaan sebelum penawaran diterima.
- Setelah selesai: melengkapi draf permohonan alokasi atau mengelola dokumen perizinan kontrak sewa/kerja sama.

### Batas akses

- Hanya melihat permintaan, pesan, lampiran, dan lahan tersimpan miliknya sendiri; nomor milik investor lain tidak ditemukan.
- Tidak melihat catatan internal petugas dan tidak bisa mengubah status selain menerima/menolak penawaran atau membatalkan.
- Tidak bisa masuk ke aplikasi petugas, panel admin, pusat komando, atau API.

<!-- akhir: blok role_guide.py -->

## Pekerjaan sehari-hari

### 1. Mendaftar

1. **Investasi → Daftar sebagai investor** ([Bab 14.1](../52-portal-investor.md#141-mendaftar-sebagai-investor)).

### 2. Mencari dan membandingkan lahan

1. Jelajahi peta investasi, simpan, dan bandingkan lahan ([Bab 14.3](../52-portal-investor.md#143-mencari-menyimpan-dan-membandingkan-lahan)).

### 3. Mengajukan minat

1. **Ajukan minat investasi**: skema, sektor, rencana usaha, dan lokasi (pilih lahan atau gambar usulan) ([Bab 14.4](../52-portal-investor.md#144-mengajukan-minat-investasi)).

### 4. Konsultasi dan penawaran

1. Pantau jadwal konsultasi dan pesan ([Bab 14.5](../52-portal-investor.md#145-memantau-permintaan)); terima atau minta penyesuaian penawaran ([Bab 14.6](../52-portal-investor.md#146-menjawab-penawaran)).

### 5. Setelah penawaran diterima

1. Lanjutkan ke kontrak atau permohonan alokasi ([Bab 14.7](../52-portal-investor.md#147-setelah-penawaran-diterima)); kelola dokumen perizinan ([Bab 15](../53-portal-dokumen.md)).

## Bab yang perlu dibaca

- [Bab 12 – Portal publik](../50-portal-publik.md)
- [Bab 14 – Portal untuk investor](../52-portal-investor.md)
- [Bab 13 – Portal untuk pemohon](../51-portal-pemohon.md)
- [Bab 15 – Dokumen & perizinan di portal](../53-portal-dokumen.md)

## Bila ada kendala

- Menu atau tombol tidak ada: peran Anda memang tidak memerlukannya ([Bab 2.10](../02-dasar-penggunaan.md#210-batas-akses-dan-pesan-tidak-berhak)). Hubungi Administrator bila Anda memerlukannya untuk pekerjaan.
- Lupa kata sandi: gunakan **Lupa kata sandi?** di halaman masuk portal ([Bab 13.1](../51-portal-pemohon.md#lupa-kata-sandi)).
- Pertanyaan lain: buka **Bantuan** di portal atau kirim pesan lewat **Kontak** ([Bab 12.10](../50-portal-publik.md#1210-bantuan-dan-kontak)).
