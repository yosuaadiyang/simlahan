# Buku peran: Pemohon portal

Buku ini untuk **Pemohon portal**: pemohon alokasi lahan (perorangan, badan usaha, atau instansi). Baca dulu [Bab 1](../01-mengenal-simlahan.md) dan [Bab 2](../02-dasar-penggunaan.md) bila baru pertama kali memakai SimLahan.

## Masuk

Buka `/portal/masuk/`, isi alamat surel dan kata sandi, lalu klik **Masuk** ([Bab 13.1](../51-portal-pemohon.md#131-masuk-ke-portal)).

![Akun saya (pemohon)](../gambar/portal/pemohon-akun.png)

<!-- awal: dibuat dari backend/users/role_guide.py; perbarui dengan: cd backend && python manage.py panduan_buku -->

## Ringkasan peran

Badan usaha, instansi, atau perorangan yang mengajukan alokasi, sewa, atau layanan pertanahan lain.

- **Cara masuk:** Portal (`/portal/masuk/`) dengan alamat surel; daftar sendiri di `/portal/daftar/`.
- **Halaman awal:** Portal → Akun saya.
- **Akun latihan** (hanya di sistem latihan berisi data contoh): `pemohon@contoh.simlahan.invalid`

### Menu yang Anda lihat

- Portal: Layanan, Lahan, Investasi (peta peluang, kawasan, bandingkan, ajukan minat), Lelang, Pengaduan, Lacak, Verifikasi dokumen, Bantuan, Akun saya (permohonan, permintaan investasi, lahan tersimpan, tagihan, profil, sandi)
- Layanan & informasi: Formulir permohonan, Pemenang alokasi terbuka, Simulasi biaya UWT (per lahan atau per wilayah dengan denda), Buku panduan; Bantuan → Kontak kami
- Akun saya → Dokumen & perizinan (`/portal/dokumen/`): pemanfaatan lahan, dokumen tanda tangan, permintaan unduh, tanda tangan saya

### Yang bisa Anda lakukan

- Mengajukan dan melengkapi permohonan, membayar tagihan, melacak status, dan mengunduh dokumen terbit (KPT, PPT, Penetapan Lokasi + sketsa bidang).
- Mengajukan layanan atas alokasinya: perpanjangan/pembaruan, pecah/gabung/revisi PL, pengukuran ulang, penyesuaian, rekomendasi, hak tanggungan, lelang, dokumen pengganti, KPT & PPT baru/perubahan, dan buka blokir (bila penetapan lokasi diblokir hanya buka blokir yang bisa diajukan).
- Menjelajah peta investasi tanpa masuk; setelah masuk: menyimpan lahan, mengajukan minat sewa/alokasi/kerja sama (memilih lahan atau menggambar usulan lokasi), berkirim pesan dengan petugas, serta menerima atau menolak penawaran.
- Melihat status setiap dokumen perizinan pemanfaatan lahannya, mengunduh format templat, mengunggah dokumen atau revisi, serta menandatangani dokumen secara elektronik (mengisi kolom isian, melampirkan berkas, dan memakai tanda tangan tersimpan yang diaktifkan dengan kata sandi).
- Mengajukan permintaan unduh dokumen; unduhan terbuka setelah disetujui petugas, diberi tanda air, dan tercatat.
- Mengubah profil dan sandi; memakai Lupa sandi bila lupa.

### Batas akses

- Tidak bisa masuk ke aplikasi petugas, panel admin, pusat komando, atau API.

<!-- akhir: blok role_guide.py -->

## Pekerjaan sehari-hari

### 1. Mendaftar dan masuk

1. Daftar akun dan aktifkan lewat surel ([Bab 12.11](../50-portal-publik.md#1211-mendaftar-akun)).
2. Masuk di `/portal/masuk/` ([Bab 13.1](../51-portal-pemohon.md#131-masuk-ke-portal)).

### 2. Mengajukan permohonan alokasi

1. Pilih lahan → **Langsung ajukan permohonan alokasi** → **Ubah data** → **Unggah** dokumen → **Ajukan** ([Bab 13.3](../51-portal-pemohon.md#133-mengajukan-permohonan-alokasi)).

### 3. Menanggapi perbaikan dan membayar

1. Perbaiki bila diminta ([Bab 13.4](../51-portal-pemohon.md#134-memperbaiki-permohonan)); bayar tagihan dan unggah bukti ([Bab 13.5](../51-portal-pemohon.md#135-membayar-tagihan)).

### 4. Setelah dokumen terbit

1. Unduh KPT dan PPT ([Bab 13.6](../51-portal-pemohon.md#136-mengunduh-kpt-dan-ppt)). Laporkan progres pembangunan, ajukan layanan alokasi, atau alihkan hak ([Bab 13.7](../51-portal-pemohon.md#137-alokasi-saya-progres-layanan-peralihan-hak)).
2. Lengkapi dokumen perizinan dan tanda tangani dokumen elektronik ([Bab 15](../53-portal-dokumen.md)).

### 5. Lainnya

1. Lacak tanpa masuk ([Bab 12.8](../50-portal-publik.md#128-lacak-permohonan)), ikut lelang ([Bab 13.9](../51-portal-pemohon.md#139-mengikuti-lelang)), kirim pengaduan ([Bab 12.7](../50-portal-publik.md#127-pengaduan-masyarakat)).

## Bab yang perlu dibaca

- [Bab 12 – Portal publik](../50-portal-publik.md)
- [Bab 13 – Portal untuk pemohon](../51-portal-pemohon.md)
- [Bab 15 – Dokumen & perizinan di portal](../53-portal-dokumen.md)

## Bila ada kendala

- Menu atau tombol tidak ada: peran Anda memang tidak memerlukannya ([Bab 2.10](../02-dasar-penggunaan.md#210-batas-akses-dan-pesan-tidak-berhak)). Hubungi Administrator bila Anda memerlukannya untuk pekerjaan.
- Lupa kata sandi: gunakan **Lupa kata sandi?** di halaman masuk portal ([Bab 13.1](../51-portal-pemohon.md#lupa-kata-sandi)).
- Pertanyaan lain: buka **Bantuan** di portal atau kirim pesan lewat **Kontak** ([Bab 12.10](../50-portal-publik.md#1210-bantuan-dan-kontak)).
