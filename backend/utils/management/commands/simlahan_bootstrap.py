"""Inisialisasi instalasi SimLahan (idempoten, aman dijalankan setiap start).

1. Memuat data master (fixture) bila basis data masih kosong.
2. Memastikan grup, jadwal pemantauan alokasi lahan, dan pengingat aset lahan ada.
3. Menyetel ulang izin grup (model, kolom, laporan).
4. Membuat akun admin awal dari variabel lingkungan bila belum ada.
"""

import io
import os
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from alokasi.setup import ensure_groups, ensure_monitoring_job
from asetlahan.setup import ensure_reminder_job
from leasing.models import Municipality, ServiceUnit
from utils.group_permissions import UserGroup

FIXTURE_DIRS = ("users/fixtures", "leasing/fixtures", "plotsearch/fixtures")


class Command(BaseCommand):
    help = "Inisialisasi data master, izin grup, dan admin awal SimLahan"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-fixtures",
            action="store_true",
            help="Muat ulang fixture walaupun data master sudah ada.",
        )

    def handle(self, *args, **options):
        root = Path(__file__).resolve().parents[3]

        if options["force_fixtures"] or not Municipality.objects.exists():
            files = []
            for directory in FIXTURE_DIRS:
                files.extend(sorted(str(p) for p in (root / directory).glob("*.json")))
            self.stdout.write(f"Memuat {len(files)} fixture data master…")
            with transaction.atomic():
                call_command("loaddata", *files, verbosity=0)
        else:
            self.stdout.write("Data master sudah ada, fixture dilewati.")

        if ensure_groups():
            self.stdout.write("Grup alokasi lahan dibuat.")
        if ensure_monitoring_job():
            self.stdout.write("Jadwal pemantauan alokasi lahan dibuat.")
        if ensure_reminder_job():
            self.stdout.write("Jadwal pengingat aset lahan dibuat.")

        for command in (
            "set_group_model_permissions",
            "set_group_field_permissions",
            "set_report_permissions",
        ):
            self.stdout.write(f"Menjalankan {command}…")
            call_command(command, verbosity=0, stdout=io.StringIO())

        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        if username and password:
            User = get_user_model()
            if not User.objects.filter(username=username).exists():
                admin = User.objects.create_superuser(
                    username=username,
                    email=os.environ.get("DJANGO_SUPERUSER_EMAIL", ""),
                    password=password,
                    first_name="Administrator",
                )
                # Admin awal mendapat semua unit layanan & grup Administrator
                # agar seluruh menu dapat dipakai sejak login pertama.
                admin.service_units.set(ServiceUnit.objects.all())
                Group = admin.groups.model
                administrator = Group.objects.filter(pk=UserGroup.PAAKAYTTAJA).first()
                if administrator:
                    admin.groups.add(administrator)
                self.stdout.write(f"Admin awal '{username}' dibuat.")
        self.stdout.write(self.style.SUCCESS("Bootstrap SimLahan selesai."))
