"""Data awal modul dokumen: pengaturan, jenis dokumen perizinan, pustaka
konten, dan contoh templat.

Hanya ditambahkan bila belum ada (dicari per kode/nama), sehingga isian yang
sudah diubah petugas tidak ditimpa.
"""

from django.db import migrations

PERMIT_TYPES = [
    # kode, nama, kategori, penerbit, wajib, masa berlaku (bulan), sifat,
    # (alokasi, sewa, kerja sama, lainnya), keterangan
    (
        "nib",
        "Nomor Induk Berusaha (NIB)",
        "perizinan",
        "Sistem OSS RBA",
        True,
        None,
        "biasa",
        (True, True, True, True),
        "Identitas berusaha dari sistem OSS. Unggah cetakan NIB terbaru.",
    ),
    (
        "pkkpr",
        "Persetujuan Kesesuaian Kegiatan Pemanfaatan Ruang (PKKPR)",
        "perizinan",
        "Kementerian ATR/BPN melalui OSS RBA",
        True,
        36,
        "biasa",
        (True, True, True, True),
        "Kesesuaian rencana kegiatan dengan rencana tata ruang. Diajukan lewat OSS.",
    ),
    (
        "pkkprl",
        "Persetujuan Kesesuaian Kegiatan Pemanfaatan Ruang Laut (PKKPRL)",
        "perizinan",
        "Kementerian Kelautan dan Perikanan",
        False,
        None,
        "biasa",
        (True, True, True, True),
        "Wajib bila kegiatan memanfaatkan ruang laut/pesisir (dermaga, reklamasi, budi daya).",
    ),
    (
        "lingkungan",
        "Persetujuan Lingkungan (AMDAL / UKL-UPL / SPPL)",
        "perizinan",
        "Dinas Lingkungan Hidup / Kementerian Lingkungan Hidup",
        True,
        None,
        "biasa",
        (True, True, True, True),
        "Dokumen lingkungan sesuai skala usaha beserta surat keputusan persetujuannya.",
    ),
    (
        "andalalin",
        "Persetujuan Analisis Dampak Lalu Lintas (Andalalin)",
        "perizinan",
        "Dinas Perhubungan",
        False,
        None,
        "biasa",
        (True, True, True, True),
        "Wajib untuk kegiatan yang membangkitkan lalu lintas besar.",
    ),
    (
        "pbg",
        "Persetujuan Bangunan Gedung (PBG)",
        "perizinan",
        "Pemerintah Kabupaten/Kota melalui SIMBG",
        True,
        None,
        "biasa",
        (True, True, True, True),
        "Persetujuan teknis sebelum membangun. Unggah PBG beserta lampiran gambar.",
    ),
    (
        "slf",
        "Sertifikat Laik Fungsi (SLF)",
        "perizinan",
        "Pemerintah Kabupaten/Kota melalui SIMBG",
        True,
        60,
        "biasa",
        (True, True, True, True),
        "Diterbitkan setelah bangunan selesai dan dinyatakan laik fungsi; perpanjang sebelum habis.",
    ),
    (
        "perjanjian",
        "Perjanjian sewa / kerja sama pemanfaatan lahan",
        "kontrak",
        "Pengelola lahan",
        True,
        None,
        "rahasia",
        (False, True, True, False),
        "Perjanjian yang ditandatangani para pihak. Dapat dibuat dan ditandatangani elektronik.",
    ),
    (
        "bast",
        "Berita acara serah terima lahan",
        "kontrak",
        "Pengelola lahan",
        True,
        None,
        "biasa",
        (True, True, True, True),
        "Serah terima fisik lahan kepada pemegang hak. Dapat ditandatangani elektronik.",
    ),
    (
        "lainnya",
        "Dokumen pendukung lainnya",
        "lainnya",
        "",
        False,
        None,
        "biasa",
        (True, True, True, True),
        "Dokumen lain yang diminta petugas.",
    ),
]

BLOCKS = [
    (
        "ketentuan_umum",
        "Ketentuan umum pemanfaatan lahan",
        "<ol><li>Pemegang hak wajib memanfaatkan lahan sesuai peruntukan dan rencana "
        "tata ruang.</li><li>Pemegang hak wajib mengurus seluruh perizinan yang "
        "dipersyaratkan dan melaporkannya melalui portal.</li><li>Pemegang hak wajib "
        "menjaga batas lahan serta kelestarian lingkungan sekitarnya.</li></ol>",
    ),
    (
        "sanksi",
        "Sanksi",
        "<p>Pelanggaran atas ketentuan ini dapat dikenai sanksi administratif berupa "
        "teguran tertulis, penghentian sementara kegiatan, hingga pencabutan hak "
        "pemanfaatan lahan sesuai peraturan yang berlaku.</p>",
    ),
]

TEMPLATES = [
    {
        "name": "Berita acara serah terima lahan",
        "category": "kontrak",
        "permit": "bast",
        "roles": "Pemegang hak\nPejabat penandatangan",
        "needs_approval": False,
        "confidentiality": "biasa",
        "body": (
            '<h2 style="text-align: center">BERITA ACARA SERAH TERIMA LAHAN</h2>'
            '<p style="text-align: center">Nomor: {{ dokumen.nomor }}</p>'
            "<p>Pada hari ini, {{ tanggal.hari_ini }}, bertempat di {{ instansi.kota }}, "
            "kami yang bertanda tangan di bawah ini:</p>"
            "<ol><li><strong>{{ instansi.pejabat }}</strong>, {{ instansi.jabatan }}, "
            "bertindak untuk dan atas nama {{ instansi.nama }} (PIHAK PERTAMA);</li>"
            "<li><strong>{{ pemohon.penanggung_jawab }}</strong>, {{ pemohon.jabatan }}, "
            "bertindak untuk dan atas nama {{ pemohon.nama }} (PIHAK KEDUA).</li></ol>"
            "<p>PIHAK PERTAMA menyerahkan kepada PIHAK KEDUA, dan PIHAK KEDUA menerima "
            "dari PIHAK PERTAMA, lahan dengan rincian:</p>"
            '<table style="width: 100%" border="1" cellpadding="4">'
            "<tr><td>Kode lahan</td><td>{{ lahan.kode }}</td></tr>"
            "<tr><td>Lokasi</td><td>{{ lahan.nama }}, Kel. {{ lahan.kelurahan }}, Kec. {{ lahan.kecamatan }}</td></tr>"
            "<tr><td>Luas</td><td>{{ pemanfaatan.luas }} m²</td></tr>"
            "<tr><td>Peruntukan</td><td>{{ pemanfaatan.nama }}</td></tr>"
            "<tr><td>Dasar hak</td><td>{{ pemanfaatan.skema }} nomor {{ pemanfaatan.referensi }}</td></tr>"
            "</table>"
            "<p>Lahan diserahkan dalam keadaan sebagaimana adanya dengan batas yang telah "
            "ditunjukkan di lapangan.</p>{{ blok.ketentuan_umum }}"
            "<p>Demikian berita acara ini dibuat untuk dipergunakan sebagaimana mestinya.</p>"
        ),
    },
    {
        "name": "Surat pernyataan kesanggupan mengurus perizinan",
        "category": "perizinan",
        "permit": None,
        "roles": "Pemegang hak",
        "needs_approval": False,
        "confidentiality": "biasa",
        "body": (
            '<h2 style="text-align: center">SURAT PERNYATAAN</h2>'
            "<p>Yang bertanda tangan di bawah ini:</p>"
            '<table style="width: 100%">'
            "<tr><td>Nama</td><td>: {{ pemohon.penanggung_jawab }}</td></tr>"
            "<tr><td>Jabatan</td><td>: {{ pemohon.jabatan }}</td></tr>"
            "<tr><td>Bertindak untuk</td><td>: {{ pemohon.nama }}</td></tr>"
            "<tr><td>Alamat</td><td>: {{ pemohon.alamat }}</td></tr></table>"
            "<p>menyatakan sanggup mengurus dan melaporkan seluruh perizinan yang "
            "dipersyaratkan atas pemanfaatan lahan {{ pemanfaatan.nomor }} "
            "({{ lahan.kode }} – {{ lahan.nama }}) paling lambat "
            "{{ isian.batas_waktu }}.</p>{{ blok.sanksi }}"
            "<p>{{ instansi.kota }}, {{ tanggal.hari_ini }}</p>"
        ),
    },
    {
        "name": "Perjanjian sewa lahan",
        "category": "kontrak",
        "permit": "perjanjian",
        "roles": "Penyewa\nPejabat penandatangan",
        "needs_approval": True,
        "confidentiality": "rahasia",
        "body": (
            '<h2 style="text-align: center">PERJANJIAN SEWA LAHAN</h2>'
            '<p style="text-align: center">Nomor: {{ dokumen.nomor }}</p>'
            "<p>Perjanjian ini dibuat pada {{ tanggal.hari_ini }} antara "
            "<strong>{{ instansi.nama }}</strong> yang diwakili {{ instansi.pejabat }} "
            "({{ instansi.jabatan }}) sebagai PEMBERI SEWA, dan "
            "<strong>{{ pemohon.nama }}</strong> yang diwakili {{ pemohon.penanggung_jawab }} "
            "({{ pemohon.jabatan }}) sebagai PENYEWA.</p>"
            '<h3 style="text-align: center">Pasal 1 – Objek sewa</h3>'
            "<p>Lahan {{ lahan.kode }} ({{ lahan.nama }}) seluas {{ pemanfaatan.luas }} m² "
            "untuk kegiatan {{ pemanfaatan.nama }}.</p>"
            '<h3 style="text-align: center">Pasal 2 – Jangka waktu dan nilai sewa</h3>'
            "<p>Sewa berlaku {{ investasi.jangka }} tahun sejak {{ pemanfaatan.mulai }} "
            "sampai {{ pemanfaatan.berakhir }} dengan tarif {{ investasi.tarif }} per m² per "
            "tahun (total {{ investasi.total }}).</p>"
            '<h3 style="text-align: center">Pasal 3 – Kewajiban penyewa</h3>'
            "{{ blok.ketentuan_umum }}"
            '<h3 style="text-align: center">Pasal 4 – Sanksi</h3>{{ blok.sanksi }}'
        ),
    },
]


def seed(apps, schema_editor):
    DocumentSettings = apps.get_model("dokumen", "DocumentSettings")
    PermitType = apps.get_model("dokumen", "PermitType")
    ContentBlock = apps.get_model("dokumen", "ContentBlock")
    DocumentTemplate = apps.get_model("dokumen", "DocumentTemplate")
    DocumentSettings.objects.get_or_create(pk=1)
    for order, row in enumerate(PERMIT_TYPES, start=1):
        code, name, category, issuer, required, months, level, schemes, description = row
        PermitType.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "category": category,
                "issuer": issuer,
                "is_required": required,
                "validity_months": months,
                "confidentiality": level,
                "applies_allocation": schemes[0],
                "applies_lease": schemes[1],
                "applies_partnership": schemes[2],
                "applies_other": schemes[3],
                "description": description,
                "order": order * 10,
            },
        )
    for code, name, body in BLOCKS:
        ContentBlock.objects.get_or_create(code=code, defaults={"name": name, "body": body})
    for item in TEMPLATES:
        template, created = DocumentTemplate.objects.get_or_create(
            name=item["name"],
            defaults={
                "category": item["category"],
                "kind": "html",
                "body": item["body"],
                "signer_roles": item["roles"],
                "needs_approval": item["needs_approval"],
                "confidentiality": item["confidentiality"],
            },
        )
        if created and item["permit"]:
            PermitType.objects.filter(code=item["permit"], template__isnull=True).update(
                template=template
            )


class Migration(migrations.Migration):
    dependencies = [("dokumen", "0001_initial")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
