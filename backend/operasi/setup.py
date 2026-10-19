"""Inisialisasi idempoten pusat komando (dipanggil simlahan_bootstrap)."""

from django.db import transaction

DAILY_COMMAND = "operasi_harian"
DAILY_JOB = "Rekap harian pusat komando"


@transaction.atomic
def ensure_daily_job() -> bool:
    """Jadwalkan rekap harian (00.30 WIB) lewat batchrun bila belum ada."""
    from batchrun.enums import CommandType
    from batchrun.models import Command, Job, ScheduledJob, Timezone

    command, _ = Command.objects.get_or_create(
        name=DAILY_COMMAND,
        type=CommandType.DJANGO_MANAGE,
        defaults={"parameters": {}, "parameter_format_string": ""},
    )
    job, _ = Job.objects.get_or_create(
        name=DAILY_JOB,
        defaults={
            "command": command,
            "comment": "Tandai lupa absen pulang, hapus posisi Live yang usang",
            "arguments": {},
        },
    )
    if ScheduledJob.objects.filter(job=job).exists():
        return False
    timezone, _ = Timezone.objects.get_or_create(name="Asia/Jakarta")
    ScheduledJob.objects.create(
        job=job,
        comment="Setiap hari pukul 00.30 WIB",
        enabled=True,
        timezone=timezone,
        years="*",
        months="*",
        days_of_month="*",
        weekdays="*",
        hours="0",
        minutes="30",
    )
    return True
