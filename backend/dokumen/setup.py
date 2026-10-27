"""Inisialisasi idempoten modul dokumen (dipanggil simlahan_bootstrap)."""

from django.db import transaction

REMINDER_COMMAND = "dokumen_pengingat"
REMINDER_JOB = "Pengingat dokumen & perizinan"


@transaction.atomic
def ensure_reminder_job() -> bool:
    """Jadwalkan pengingat harian (06.45 WIB) lewat batchrun bila belum ada."""
    from batchrun.enums import CommandType
    from batchrun.models import Command, Job, ScheduledJob, Timezone

    command, _ = Command.objects.get_or_create(
        name=REMINDER_COMMAND,
        type=CommandType.DJANGO_MANAGE,
        defaults={"parameters": {}, "parameter_format_string": "--email"},
    )
    job, _ = Job.objects.get_or_create(
        name=REMINDER_JOB,
        defaults={
            "command": command,
            "comment": "Izin kedaluwarsa, peringatan masa berlaku, pengingat & batas tanda tangan",
            "arguments": {},
        },
    )
    if ScheduledJob.objects.filter(job=job).exists():
        return False
    timezone, _ = Timezone.objects.get_or_create(name="Asia/Jakarta")
    ScheduledJob.objects.create(
        job=job,
        comment="Setiap hari pukul 06.45 WIB",
        enabled=True,
        timezone=timezone,
        years="*",
        months="*",
        days_of_month="*",
        weekdays="*",
        hours="6",
        minutes="45",
    )
    return True
