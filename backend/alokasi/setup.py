"""Inisialisasi idempoten modul alokasi (dipanggil simlahan_bootstrap)."""

from django.contrib.auth.models import Group
from django.core.management.color import no_style
from django.db import DEFAULT_DB_ALIAS, connections, transaction

from utils.group_permissions import UserGroup

GROUP_NAMES = {
    UserGroup.SELAILIJA: "Penelusur",
    UserGroup.VALMISTELIJA: "Penyusun",
    UserGroup.SOPIMUSVALMISTELIJA: "Penyusun Kontrak",
    UserGroup.SYOTTAJA: "Operator Entri Data",
    UserGroup.PERINTALAKIMIES: "Ahli Hukum Penagihan",
    UserGroup.LASKUTTAJA: "Petugas Penagihan",
    UserGroup.PAAKAYTTAJA: "Administrator",
    UserGroup.PELAKSANA_PENGADAAN: "Pelaksana Pengadaan Tanah",
    UserGroup.SATGAS_PENGADAAN: "Satgas Pengadaan Tanah",
    UserGroup.PENILAI: "Penilai Pertanahan",
    UserGroup.INSTANSI_PEMOHON: "Instansi Yang Memerlukan Tanah",
    UserGroup.PETUGAS_ALOKASI: "Petugas Alokasi Lahan",
    UserGroup.TIM_VERIFIKASI: "Tim Verifikasi Teknis",
    UserGroup.PETUGAS_ASET: "Petugas Aset Lahan",
    UserGroup.PETUGAS_HUKUM: "Petugas Hukum",
    UserGroup.PETUGAS_LAPANGAN: "Petugas Lapangan",
    UserGroup.KOORDINATOR_WILAYAH: "Koordinator Wilayah",
}

MONITORING_COMMAND = "alokasi_pemantauan"
MONITORING_JOB = "Pemantauan alokasi lahan"


def ensure_groups(group_model=Group, using=DEFAULT_DB_ALIAS) -> list[int]:
    """Buat setiap grup peran SimLahan yang belum ada.

    Instalasi lama tidak memuat ulang fixture; tanpa grup ini pengaturan izin
    grup (set_group_model_permissions) gagal sehingga peran tidak punya izin.
    """
    created = []
    for group_id, name in GROUP_NAMES.items():
        if not group_model.objects.using(using).filter(pk=group_id).exists():
            group_model.objects.using(using).create(pk=group_id, name=name)
            created.append(group_id)
    if created:
        conn = connections[using]
        with conn.cursor() as cursor:
            for sql in conn.ops.sequence_reset_sql(no_style(), [group_model]):
                cursor.execute(sql)
    return created


@transaction.atomic
def ensure_monitoring_job() -> bool:
    """Jadwalkan pemantauan mingguan (Senin 07.30 WIB) lewat batchrun bila belum ada."""
    from batchrun.enums import CommandType
    from batchrun.models import Command, Job, ScheduledJob, Timezone

    command, _ = Command.objects.get_or_create(
        name=MONITORING_COMMAND,
        type=CommandType.DJANGO_MANAGE,
        defaults={"parameters": {}, "parameter_format_string": "--email"},
    )
    job, _ = Job.objects.get_or_create(
        name=MONITORING_JOB,
        defaults={
            "command": command,
            "comment": "Lahan tidur, laporan progres terlambat, tagihan jatuh tempo, alokasi berakhir",
            "arguments": {},
        },
    )
    if ScheduledJob.objects.filter(job=job).exists():
        return False
    timezone, _ = Timezone.objects.get_or_create(name="Asia/Jakarta")
    ScheduledJob.objects.create(
        job=job,
        comment="Setiap Senin pukul 07.30 WIB",
        enabled=True,
        timezone=timezone,
        years="*",
        months="*",
        days_of_month="*",
        weekdays="1",
        hours="7",
        minutes="30",
    )
    return True
