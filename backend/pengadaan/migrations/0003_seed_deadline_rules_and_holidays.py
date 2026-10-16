"""Data awal: aturan tenggat hukum dan libur nasional/cuti bersama 2025–2027.

Sumber libur: SKB 3 Menteri tentang Hari Libur Nasional dan Cuti Bersama
2025 (beserta perubahannya Agustus 2025), 2026 dan 2027. Perbarui setiap tahun
melalui menu admin "Hari libur".
"""

import datetime

from django.db import migrations

RULES = [
    # code, name, amount, unit, legal_basis, description
    (
        "penlok_validity",
        "Masa berlaku Penetapan Lokasi",
        3,
        "years",
        "UU 2/2012 Ps. 24; PP 19/2021",
        "Penetapan lokasi berlaku 3 tahun sejak ditetapkan.",
    ),
    (
        "penlok_extension",
        "Perpanjangan Penetapan Lokasi",
        1,
        "years",
        "UU 2/2012 Ps. 24; PP 19/2021",
        "Dapat diperpanjang 1 kali paling lama 1 tahun.",
    ),
    (
        "penlok_announcement",
        "Masa pengumuman Penetapan Lokasi",
        10,
        "workdays",
        "PP 19/2021",
        "Penetapan lokasi diumumkan selama 10 hari.",
    ),
    (
        "ptun_filing",
        "Batas gugatan Penetapan Lokasi ke PTUN",
        30,
        "workdays",
        "UU 2/2012 Ps. 23 ayat (1)",
        "Gugatan diajukan paling lambat 30 hari kerja sejak dikeluarkannya penetapan lokasi.",
    ),
    (
        "ptun_decision",
        "Batas putusan PTUN",
        30,
        "workdays",
        "UU 2/2012 Ps. 23 ayat (2)",
        "PTUN memutus paling lama 30 hari kerja sejak gugatan diterima.",
    ),
    (
        "location_objection_handling",
        "Penanganan keberatan rencana lokasi",
        14,
        "workdays",
        "PP 19/2021",
        "Penanganan keberatan paling lama 14 hari sejak keberatan diterima.",
    ),
    (
        "inventory_announcement",
        "Masa pengumuman hasil inventarisasi",
        14,
        "workdays",
        "UU 2/2012 Ps. 29; PP 19/2021",
        "Peta bidang dan daftar nominatif diumumkan selama 14 hari kerja.",
    ),
    (
        "inventory_objection",
        "Batas keberatan hasil inventarisasi",
        14,
        "workdays",
        "UU 2/2012 Ps. 30",
        "Keberatan atas hasil inventarisasi paling lama 14 hari kerja sejak diumumkan.",
    ),
    (
        "deliberation",
        "Batas pelaksanaan musyawarah",
        30,
        "workdays",
        "UU 2/2012 Ps. 37 ayat (1)",
        "Musyawarah paling lama 30 hari kerja sejak hasil penilaian disampaikan.",
    ),
    (
        "compensation_objection",
        "Batas keberatan ganti kerugian ke Pengadilan Negeri",
        14,
        "workdays",
        "UU 2/2012 Ps. 38 ayat (1); Perma 3/2016 jo. Perma 2/2021",
        "Keberatan diajukan paling lama 14 hari kerja setelah musyawarah.",
    ),
    (
        "district_court_decision",
        "Batas putusan Pengadilan Negeri",
        30,
        "workdays",
        "UU 2/2012 Ps. 38 ayat (2)",
        "Pengadilan Negeri memutus paling lama 30 hari kerja sejak keberatan diterima.",
    ),
    (
        "cassation_filing",
        "Batas pengajuan kasasi",
        14,
        "workdays",
        "UU 2/2012 Ps. 38 ayat (3)",
        "Kasasi diajukan paling lama 14 hari kerja sejak putusan PN.",
    ),
    (
        "supreme_court_decision",
        "Batas putusan Mahkamah Agung",
        30,
        "workdays",
        "UU 2/2012 Ps. 38 ayat (4)",
        "MA memutus paling lama 30 hari kerja sejak permohonan kasasi diterima.",
    ),
    (
        "consignment_acceptance",
        "Penerimaan penitipan oleh Pengadilan Negeri",
        14,
        "workdays",
        "PP 19/2021",
        "Pengadilan Negeri menerima penitipan ganti kerugian paling lama 14 hari.",
    ),
    (
        "handover",
        "Penyerahan hasil setelah pelepasan hak",
        14,
        "workdays",
        "PP 19/2021",
        "Ketua Pelaksana menyerahkan hasil kepada instansi paling lama 14 hari.",
    ),
    (
        "registration",
        "Pendaftaran hak setelah penyerahan hasil",
        30,
        "workdays",
        "PP 19/2021",
        "Instansi mengajukan pendaftaran/sertipikasi paling lama 30 hari.",
    ),
]

HOLIDAYS = {
    # 2025 (SKB 2024, diubah Agustus 2025)
    "2025-01-01": ("Tahun Baru Masehi", False),
    "2025-01-27": ("Isra Mikraj Nabi Muhammad SAW", False),
    "2025-01-28": ("Cuti bersama Tahun Baru Imlek", True),
    "2025-01-29": ("Tahun Baru Imlek", False),
    "2025-03-28": ("Cuti bersama Hari Suci Nyepi", True),
    "2025-03-29": ("Hari Suci Nyepi", False),
    "2025-03-31": ("Idulfitri 1446 H", False),
    "2025-04-01": ("Idulfitri 1446 H", False),
    "2025-04-02": ("Cuti bersama Idulfitri", True),
    "2025-04-03": ("Cuti bersama Idulfitri", True),
    "2025-04-04": ("Cuti bersama Idulfitri", True),
    "2025-04-07": ("Cuti bersama Idulfitri", True),
    "2025-04-18": ("Wafat Yesus Kristus", False),
    "2025-04-20": ("Kebangkitan Yesus Kristus (Paskah)", False),
    "2025-05-01": ("Hari Buruh Internasional", False),
    "2025-05-12": ("Hari Raya Waisak", False),
    "2025-05-13": ("Cuti bersama Waisak", True),
    "2025-05-29": ("Kenaikan Yesus Kristus", False),
    "2025-05-30": ("Cuti bersama Kenaikan Yesus Kristus", True),
    "2025-06-01": ("Hari Lahir Pancasila", False),
    "2025-06-06": ("Iduladha 1446 H", False),
    "2025-06-09": ("Cuti bersama Iduladha", True),
    "2025-06-27": ("1 Muharam Tahun Baru Islam", False),
    "2025-08-17": ("Proklamasi Kemerdekaan", False),
    "2025-08-18": ("Cuti bersama Proklamasi Kemerdekaan", True),
    "2025-09-05": ("Maulid Nabi Muhammad SAW", False),
    "2025-12-25": ("Kelahiran Yesus Kristus", False),
    "2025-12-26": ("Cuti bersama Kelahiran Yesus Kristus", True),
    # 2026
    "2026-01-01": ("Tahun Baru Masehi", False),
    "2026-01-16": ("Isra Mikraj Nabi Muhammad SAW", False),
    "2026-02-16": ("Cuti bersama Tahun Baru Imlek", True),
    "2026-02-17": ("Tahun Baru Imlek 2577 Kongzili", False),
    "2026-03-18": ("Cuti bersama Hari Suci Nyepi", True),
    "2026-03-19": ("Hari Suci Nyepi", False),
    "2026-03-20": ("Cuti bersama Idulfitri", True),
    "2026-03-21": ("Idulfitri 1447 H", False),
    "2026-03-22": ("Idulfitri 1447 H", False),
    "2026-03-23": ("Cuti bersama Idulfitri", True),
    "2026-03-24": ("Cuti bersama Idulfitri", True),
    "2026-04-03": ("Wafat Yesus Kristus", False),
    "2026-04-05": ("Kebangkitan Yesus Kristus (Paskah)", False),
    "2026-05-01": ("Hari Buruh Internasional", False),
    "2026-05-14": ("Kenaikan Yesus Kristus", False),
    "2026-05-15": ("Cuti bersama Kenaikan Yesus Kristus", True),
    "2026-05-27": ("Iduladha 1447 H", False),
    "2026-05-28": ("Cuti bersama Iduladha", True),
    "2026-05-31": ("Hari Raya Waisak", False),
    "2026-06-01": ("Hari Lahir Pancasila", False),
    "2026-06-16": ("1 Muharam Tahun Baru Islam", False),
    "2026-08-17": ("Proklamasi Kemerdekaan", False),
    "2026-08-25": ("Maulid Nabi Muhammad SAW", False),
    "2026-12-24": ("Cuti bersama Kelahiran Yesus Kristus", True),
    "2026-12-25": ("Kelahiran Yesus Kristus", False),
    # 2027
    "2027-01-01": ("Tahun Baru Masehi", False),
    "2027-01-05": ("Isra Mikraj Nabi Muhammad SAW", False),
    "2027-02-05": ("Cuti bersama Tahun Baru Imlek", True),
    "2027-02-06": ("Tahun Baru Imlek 2578 Kongzili", False),
    "2027-03-08": ("Hari Suci Nyepi", False),
    "2027-03-09": ("Cuti bersama Idulfitri", True),
    "2027-03-10": ("Idulfitri 1448 H", False),
    "2027-03-11": ("Idulfitri 1448 H", False),
    "2027-03-12": ("Cuti bersama Idulfitri", True),
    "2027-03-15": ("Cuti bersama Idulfitri", True),
    "2027-03-25": ("Cuti bersama Wafat Yesus Kristus", True),
    "2027-03-26": ("Wafat Yesus Kristus", False),
    "2027-03-28": ("Kebangkitan Yesus Kristus (Paskah)", False),
    "2027-05-01": ("Hari Buruh Internasional", False),
    "2027-05-06": ("Kenaikan Yesus Kristus", False),
    "2027-05-17": ("Iduladha 1448 H", False),
    "2027-05-18": ("Cuti bersama Iduladha", True),
    "2027-05-19": ("Cuti bersama Waisak", True),
    "2027-05-20": ("Hari Raya Waisak", False),
    "2027-06-01": ("Hari Lahir Pancasila", False),
    "2027-06-06": ("1 Muharam Tahun Baru Islam", False),
    "2027-08-15": ("Maulid Nabi Muhammad SAW", False),
    "2027-08-17": ("Proklamasi Kemerdekaan", False),
    "2027-12-24": ("Cuti bersama Kelahiran Yesus Kristus", True),
    "2027-12-25": ("Kelahiran Yesus Kristus", False),
    "2027-12-26": ("Isra Mikraj Nabi Muhammad SAW", False),
}


def seed(apps, schema_editor):
    DeadlineRule = apps.get_model("pengadaan", "DeadlineRule")
    Holiday = apps.get_model("pengadaan", "Holiday")
    for code, name, amount, unit, basis, description in RULES:
        DeadlineRule.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "amount": amount,
                "unit": unit,
                "legal_basis": basis,
                "description": description,
            },
        )
    for date_str, (name, collective) in HOLIDAYS.items():
        Holiday.objects.update_or_create(
            date=datetime.date.fromisoformat(date_str),
            defaults={"name": name, "is_collective_leave": collective},
        )


def unseed(apps, schema_editor):
    apps.get_model("pengadaan", "DeadlineRule").objects.filter(
        code__in=[r[0] for r in RULES]
    ).delete()
    apps.get_model("pengadaan", "Holiday").objects.filter(
        date__in=[datetime.date.fromisoformat(d) for d in HOLIDAYS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [("pengadaan", "0002_initial")]

    operations = [migrations.RunPython(seed, unseed)]
