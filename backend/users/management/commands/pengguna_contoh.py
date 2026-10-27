"""Akun contoh untuk setiap peran (uji coba menu dan batas hak akses).

python manage.py pengguna_contoh                    # buat akun yang belum ada
python manage.py pengguna_contoh --sandi-baru       # buat ulang sandi semua akun contoh
python manage.py pengguna_contoh --sandi 'Rahasia…' # pakai satu sandi untuk semua
python manage.py pengguna_contoh --hapus            # hapus semua akun contoh

Satu akun per grup peran ditambah satu pemohon portal. Sandi dibuat acak (kuat)
dan hanya ditampilkan saat dibuat atau diganti; akun yang sudah ada tetap memakai
sandinya. Semua akun memakai surel ``@contoh.simlahan.invalid`` (tidak bisa
menerima surel) sehingga --hapus hanya mengenai akun contoh.

Agar pembatasan data terlihat, Penilai dan Instansi ditugaskan ke proyek contoh
``pengadaan_contoh_rempang``, Koordinator Wilayah memimpin Korwil A dan Petugas
Lapangan menjadi anggota Korwil A dari ``operasi_contoh_rempang`` (jalankan
perintah data contoh itu lebih dahulu, lalu perintah ini sekali lagi).
"""

import secrets
import string

from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, router, transaction
from django.db.models.deletion import Collector, ProtectedError, RestrictedError

from alokasi import enums as alokasi_enums
from alokasi.models import Applicant
from leasing.models import ServiceUnit
from operasi.management.commands.operasi_contoh_rempang import MARK as KORWIL_MARK
from operasi.models import Korwil
from pengadaan.management.commands.pengadaan_contoh_rempang import (
    SAMPLE_PROJECT_NAME,
)
from pengadaan.models import AcquisitionProject
from utils.group_permissions import ADMIN_PANEL_GROUPS, UserGroup

DOMAIN = "contoh.simlahan.invalid"
SAMPLE_KORWIL_CODE = "A"

SPA = "Aplikasi petugas (/)"
ADMIN = "Panel admin (/admin/)"

# (username, grup, nama belakang, tempat masuk)
OFFICERS = [
    ("contoh.penelusur", UserGroup.SELAILIJA, "Penelusur", SPA),
    ("contoh.penyusun", UserGroup.VALMISTELIJA, "Penyusun", SPA),
    ("contoh.kontrak", UserGroup.SOPIMUSVALMISTELIJA, "Penyusun Kontrak", SPA),
    ("contoh.operator", UserGroup.SYOTTAJA, "Operator Entri Data", SPA),
    ("contoh.ahlihukum", UserGroup.PERINTALAKIMIES, "Ahli Hukum Penagihan", SPA),
    ("contoh.penagihan", UserGroup.LASKUTTAJA, "Petugas Penagihan", SPA),
    ("contoh.administrator", UserGroup.PAAKAYTTAJA, "Administrator", SPA),
    ("contoh.pelaksana", UserGroup.PELAKSANA_PENGADAAN, "Pelaksana Pengadaan", SPA),
    ("contoh.satgas", UserGroup.SATGAS_PENGADAAN, "Satgas Pengadaan", SPA),
    ("contoh.penilai", UserGroup.PENILAI, "Penilai Pertanahan", SPA),
    ("contoh.instansi", UserGroup.INSTANSI_PEMOHON, "Instansi Pemohon", SPA),
    ("contoh.alokasi", UserGroup.PETUGAS_ALOKASI, "Petugas Alokasi", ADMIN),
    ("contoh.verifikasi", UserGroup.TIM_VERIFIKASI, "Tim Verifikasi", ADMIN),
    ("contoh.aset", UserGroup.PETUGAS_ASET, "Petugas Aset", ADMIN),
    ("contoh.hukum", UserGroup.PETUGAS_HUKUM, "Petugas Hukum", ADMIN),
    (
        "contoh.lapangan",
        UserGroup.PETUGAS_LAPANGAN,
        "Petugas Lapangan",
        "/aset/lapangan/",
    ),
    (
        "contoh.korwil",
        UserGroup.KOORDINATOR_WILAYAH,
        "Koordinator Wilayah",
        "/komando/",
    ),
]
APPLICANT_EMAIL = f"pemohon@{DOMAIN}"

# Data yang ikut terhapus bersama akun tanpa kehilangan catatan kerja.
DISPOSABLE_MODELS = {
    "users.user",
    "users.loginotp",
    "authtoken.token",
    "token_blacklist.outstandingtoken",
    "token_blacklist.blacklistedtoken",
    "alokasi.applicant",
}


def sample_users():
    return get_user_model().objects.filter(email__iendswith=f"@{DOMAIN}")


def _generate_password() -> str:
    # Huruf dan angka saja agar mudah disalin dari terminal ke formulir login.
    alphabet = string.ascii_letters + string.digits
    while True:
        password = "".join(secrets.choice(alphabet) for _i in range(16))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
        ):
            return password


class Command(BaseCommand):
    help = "Buat atau hapus akun contoh untuk setiap peran"

    def add_arguments(self, parser):
        parser.add_argument("--hapus", action="store_true", help="Hapus akun contoh")
        parser.add_argument(
            "--sandi",
            help="Satu sandi untuk semua akun contoh (harus lolos aturan sandi).",
        )
        parser.add_argument(
            "--sandi-baru",
            action="store_true",
            help="Buat sandi acak baru untuk akun contoh yang sudah ada.",
        )

    def handle(self, *args, **options):
        if options["hapus"]:
            self._delete()
            return
        groups = Group.objects.in_bulk([row[1] for row in OFFICERS])
        missing = [group for _u, group, _n, _w in OFFICERS if group not in groups]
        if missing:
            raise CommandError(
                "Grup peran belum lengkap. Jalankan dahulu: "
                "python manage.py simlahan_bootstrap"
            )
        rows = self._create(groups, options["sandi"], options["sandi_baru"])
        self._print(rows)

    # ------------------------------------------------------------------
    # Pembuatan
    # ------------------------------------------------------------------

    def _password_for(self, user, fixed, renew, created) -> str | None:
        # Akun yang dinonaktifkan oleh --hapus tidak punya sandi lagi.
        if not (created or renew or fixed or not user.has_usable_password()):
            return None
        password = fixed or _generate_password()
        try:
            password_validation.validate_password(password, user)
        except ValidationError as error:
            raise CommandError(
                f"Sandi ditolak untuk {user.username}: " + " ".join(error.messages)
            )
        user.set_password(password)
        return password

    @transaction.atomic
    def _create(self, groups, fixed, renew):
        User = get_user_model()
        units = list(ServiceUnit.objects.order_by("pk"))
        rows = []
        for username, group_id, role, where in OFFICERS:
            user = User.objects.filter(username=username).first()
            created = user is None
            if created:
                user = User(username=username)
            elif not user.email.lower().endswith(f"@{DOMAIN}"):
                raise CommandError(
                    f"Nama pengguna {username} sudah dipakai akun lain; "
                    "akun itu tidak diubah."
                )
            user.first_name = "Contoh"
            user.last_name = role
            user.email = f"{username.split('.', 1)[1]}@{DOMAIN}"
            user.department_name = "Akun contoh"
            user.is_active = True
            user.is_superuser = False
            user.is_staff = group_id in ADMIN_PANEL_GROUPS
            password = self._password_for(user, fixed, renew, created)
            user.save()
            # Satu peran per akun agar menu yang tampil mencerminkan peran itu saja.
            user.groups.set([groups[group_id]])
            user.user_permissions.clear()
            user.service_units.set(units)
            rows.append((role, username, password, where))

        self._assign_scopes(User)
        rows.append(self._applicant(fixed, renew))
        return rows

    def _applicant(self, fixed, renew):
        User = get_user_model()
        user = User.objects.filter(username=APPLICANT_EMAIL).first()
        created = user is None
        if created:
            user = User(username=APPLICANT_EMAIL)
        user.email = APPLICANT_EMAIL
        user.first_name = "Contoh"
        user.last_name = "Pemohon"
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        password = self._password_for(user, fixed, renew, created)
        user.save()
        # Pemohon portal tidak pernah anggota grup petugas atau unit layanan.
        user.groups.clear()
        user.user_permissions.clear()
        user.service_units.clear()
        Applicant.objects.update_or_create(
            user=user,
            defaults={
                "applicant_type": alokasi_enums.ApplicantType.COMPANY,
                "name": "PT Contoh Investasi Rempang",
                "pic_name": "Contoh Pemohon",
                "pic_position": "Direktur",
                "phone": "0778000000",
                "address": "Jl. Contoh No. 1, Batam",
                "city": "Batam",
            },
        )
        return ("Pemohon portal", APPLICANT_EMAIL, password, "Portal (/portal/)")

    def _assign_scopes(self, User):
        users = {
            u.username: u
            for u in sample_users().filter(
                username__in=[
                    "contoh.penilai",
                    "contoh.instansi",
                    "contoh.korwil",
                    "contoh.lapangan",
                ]
            )
        }
        project = AcquisitionProject.objects.filter(name=SAMPLE_PROJECT_NAME).first()
        if project:
            project.assigned_users.add(
                users["contoh.penilai"], users["contoh.instansi"]
            )
        else:
            self.stdout.write(
                "Proyek contoh pengadaan belum ada: Penilai dan Instansi belum "
                "ditugaskan (jalankan pengadaan_contoh_rempang lalu perintah ini lagi)."
            )
        korwil = Korwil.objects.filter(
            code=SAMPLE_KORWIL_CODE, note__startswith=KORWIL_MARK
        ).first()
        if korwil:
            coordinator = korwil.coordinator
            if coordinator is None or coordinator.email.lower().endswith(f"@{DOMAIN}"):
                korwil.coordinator = users["contoh.korwil"]
                korwil.save(update_fields=["coordinator"])
            korwil.members.add(users["contoh.lapangan"])
        else:
            self.stdout.write(
                "Korwil contoh belum ada: Koordinator Wilayah dan Petugas Lapangan "
                "belum punya wilayah (jalankan operasi_contoh_rempang lalu perintah "
                "ini lagi)."
            )

    def _print(self, rows):
        self.stdout.write(self.style.SUCCESS("Akun contoh siap:"))
        width = max(len(row[1]) for row in rows)
        for role, username, password, where in rows:
            shown = password if password else "(sandi tidak diubah)"
            self.stdout.write(f"  {username:<{width}}  {shown:<20}  {role} – {where}")
        if any(row[2] for row in rows):
            self.stdout.write(
                "Simpan sandi di atas sekarang; sandi tidak ditampilkan lagi. "
                "Ganti dengan --sandi-baru bila lupa."
            )

    # ------------------------------------------------------------------
    # Penghapusan
    # ------------------------------------------------------------------

    def _delete(self):
        deleted, kept = [], []
        for user in sample_users().order_by("username"):
            with transaction.atomic():
                if self._can_delete(user):
                    user.delete()
                    deleted.append(user.username)
                else:
                    # Akun pernah dipakai bekerja: catatan kerjanya tidak ikut
                    # dihapus, akun dinonaktifkan dan dicabut semua aksesnya.
                    user.is_active = False
                    user.is_staff = False
                    user.set_unusable_password()
                    user.save()
                    user.groups.clear()
                    user.user_permissions.clear()
                    kept.append(user.username)
        self.stdout.write(self.style.SUCCESS(f"{len(deleted)} akun contoh dihapus."))
        if kept:
            self.stdout.write(
                f"{len(kept)} akun dinonaktifkan karena masih tercatat pada data "
                "kerja: " + ", ".join(kept)
            )

    def _can_delete(self, user) -> bool:
        collector = Collector(using=router.db_for_write(type(user)) or DEFAULT_DB_ALIAS)
        try:
            collector.collect([user])
        except (ProtectedError, RestrictedError):
            return False
        for model, objects in collector.data.items():
            if objects and not self._disposable(model):
                return False
        for queryset in collector.fast_deletes:
            if not self._disposable(queryset.model) and queryset.exists():
                return False
        return True

    @staticmethod
    def _disposable(model) -> bool:
        # Tabel penghubung many-to-many (grup, unit layanan, anggota Korwil, ...).
        return model._meta.auto_created or model._meta.label_lower in DISPOSABLE_MODELS
