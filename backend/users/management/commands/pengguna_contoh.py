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
perintah data contoh itu lebih dahulu, lalu perintah ini sekali lagi). Di pusat
komando, Petugas Lapangan melapor ke Koordinator Wilayah dan Koordinator Wilayah
ke Administrator, lengkap dengan tugas berpoin dan laporan harian berjenjang contoh.

Investor contoh (``investor@contoh.simlahan.invalid``) mendapat lahan tersimpan
dan tiga permintaan investasi contoh (diajukan, konsultasi terjadwal, penawaran
menunggu jawaban) di lahan ``alokasi_contoh_rempang``. Data itu dibuat tanpa
mengirim surel dan ikut terhapus oleh --hapus.
"""

import datetime
import secrets
import string
from decimal import Decimal

from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, router, transaction
from django.db.models.deletion import Collector, ProtectedError, RestrictedError
from django.utils import timezone

from alokasi import enums as alokasi_enums
from alokasi.management.commands import alokasi_contoh_rempang as alokasi_samples
from alokasi.models import (
    Applicant,
    InvestmentEvent,
    InvestmentMessage,
    InvestmentRequest,
    InvestmentSector,
    InvestmentZone,
    LandPlot,
    SavedPlot,
)
from leasing.models import ServiceUnit
from operasi.management.commands.operasi_contoh_rempang import MARK as KORWIL_MARK
from operasi.management.commands.operasi_contoh_rempang import (
    delete_komando_demo,
    komando_demo,
)
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
INVESTOR_EMAIL = f"investor@{DOMAIN}"
INVESTOR_SECTORS = ("Industri", "Logistik & pergudangan")
SAVED_PLOTS = ("01", "04", "07")
SAMPLE_TAG = "(CONTOH)"

# Data yang ikut terhapus bersama akun tanpa kehilangan catatan kerja.
DISPOSABLE_MODELS = {
    "users.user",
    "users.loginotp",
    "authtoken.token",
    "token_blacklist.outstandingtoken",
    "token_blacklist.blacklistedtoken",
    "alokasi.applicant",
    "operasi.officerprofile",
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
        rows.append(self._investor(fixed, renew))
        return rows

    def _portal_user(self, email, last_name, fixed, renew):
        User = get_user_model()
        user = User.objects.filter(username=email).first()
        created = user is None
        if created:
            user = User(username=email)
        user.email = email
        user.first_name = "Contoh"
        user.last_name = last_name
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        password = self._password_for(user, fixed, renew, created)
        user.save()
        # Pemohon portal tidak pernah anggota grup petugas atau unit layanan.
        user.groups.clear()
        user.user_permissions.clear()
        user.service_units.clear()
        return user, password

    def _applicant(self, fixed, renew):
        user, password = self._portal_user(APPLICANT_EMAIL, "Pemohon", fixed, renew)
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
                "is_investor": False,
            },
        )
        return ("Pemohon portal", APPLICANT_EMAIL, password, "Portal (/portal/)")

    def _investor(self, fixed, renew):
        user, password = self._portal_user(INVESTOR_EMAIL, "Investor", fixed, renew)
        investor, _created = Applicant.objects.update_or_create(
            user=user,
            defaults={
                "applicant_type": alokasi_enums.ApplicantType.COMPANY,
                "name": "PT Contoh Investor Nusantara",
                "nib": "9120000000001",
                "pic_name": "Contoh Investor",
                "pic_position": "Direktur Pengembangan Usaha",
                "phone": "0778000001",
                "address": "Jl. Contoh No. 2, Batam",
                "city": "Batam",
                "is_investor": True,
                "capital_origin": alokasi_enums.CapitalOrigin.DOMESTIC,
                "origin_country": "",
                "website": "https://contoh.simlahan.invalid",
            },
        )
        investor.interest_sectors.set(
            InvestmentSector.objects.filter(name__in=INVESTOR_SECTORS)
        )
        self._investment_samples(investor)
        return (
            "Investor",
            INVESTOR_EMAIL,
            password,
            "Portal investasi (/portal/investasi/)",
        )

    # ------------------------------------------------------------------
    # Data investasi contoh (tanpa surel; status diatur langsung)
    # ------------------------------------------------------------------

    def _investment_samples(self, investor):
        plots = {
            plot.code.removeprefix(alokasi_samples.PREFIX): plot
            for plot in LandPlot.objects.filter(
                code__startswith=alokasi_samples.PREFIX, is_published=True
            ).select_related("sector", "zone")
        }
        if not plots:
            self.stdout.write(
                "Lahan contoh belum ada: investor contoh belum punya lahan tersimpan "
                "dan permintaan investasi (jalankan alokasi_contoh_rempang lalu "
                "perintah ini lagi)."
            )
            return
        for code in SAVED_PLOTS:
            if code in plots:
                SavedPlot.objects.get_or_create(applicant=investor, plot=plots[code])
        officer = sample_users().filter(username="contoh.alokasi").first()
        now = timezone.now()
        today = timezone.localdate()
        self._sample_request(
            investor,
            officer,
            plots.get("01"),
            project_name=f"Pabrik Pengolahan Rumput Laut {SAMPLE_TAG}",
            scheme=alokasi_enums.InvestmentScheme.LEASE,
            activity="Pabrik pengolahan rumput laut menjadi karagenan untuk pasar "
            "ekspor, dibangun dua tahap. Data fiktif untuk uji coba.",
            investment_value=Decimal("85000000000"),
            workforce=180,
            term_years=20,
            history=[
                (alokasi_enums.InvestmentStatus.SUBMITTED, 12, ""),
                (alokasi_enums.InvestmentStatus.REVIEW, 10, ""),
                (
                    alokasi_enums.InvestmentStatus.CONSULTATION,
                    8,
                    "Konsultasi di kantor pelayanan lahan.",
                ),
            ],
            extra={
                "meeting_at": timezone.localtime(
                    now + datetime.timedelta(days=7)
                ).replace(hour=10, minute=0, second=0, microsecond=0),
                "meeting_place": "Kantor pelayanan lahan, ruang rapat 2 (contoh)",
            },
            messages=[
                (
                    True,
                    9,
                    "Terima kasih atas minat Anda. Mohon kirim rencana tata letak "
                    "pabrik dan kebutuhan air untuk bahan konsultasi.",
                ),
                (
                    False,
                    8,
                    "Baik, rencana tata letak kami bawa saat konsultasi. Kebutuhan "
                    "air sekitar 300 m³/hari.",
                ),
            ],
        )
        lease_plot = plots.get("07")
        self._sample_request(
            investor,
            officer,
            lease_plot,
            project_name=f"Gudang Logistik Berpendingin {SAMPLE_TAG}",
            scheme=alokasi_enums.InvestmentScheme.LEASE,
            activity="Gudang berpendingin untuk distribusi hasil laut dan "
            "logistik pelabuhan. Data fiktif untuk uji coba.",
            investment_value=Decimal("12500000000"),
            workforce=40,
            term_years=5,
            history=[
                (alokasi_enums.InvestmentStatus.SUBMITTED, 20, ""),
                (alokasi_enums.InvestmentStatus.REVIEW, 18, ""),
                (
                    alokasi_enums.InvestmentStatus.OFFERED,
                    2,
                    "Penawaran sewa lahan contoh.",
                ),
            ],
            extra=(
                {
                    "offer_scheme": alokasi_enums.InvestmentScheme.LEASE,
                    "offer_plot": lease_plot,
                    "offer_area_m2": lease_plot.area_m2,
                    "offer_rate_per_m2_year": lease_plot.lease_rate_per_m2_year,
                    "offer_term_years": 5,
                    "offer_valid_until": today + datetime.timedelta(days=30),
                    "offer_note": "Tarif belum termasuk pajak. Data fiktif.",
                    "offered_at": now - datetime.timedelta(days=2),
                }
                if lease_plot is not None
                else {}
            ),
        )
        zone = InvestmentZone.objects.filter(slug=alokasi_samples.ZONE_TOURISM).first()
        self._sample_request(
            investor,
            officer,
            None,
            project_name=f"Resor Wisata Bahari {SAMPLE_TAG}",
            scheme=alokasi_enums.InvestmentScheme.UNDECIDED,
            sector_name="Pariwisata & perhotelan",
            activity="Resor 120 kamar dengan dermaga wisata. Minta saran skema "
            "dan lokasi dari petugas. Data fiktif untuk uji coba.",
            investment_value=Decimal("150000000000"),
            workforce=250,
            term_years=30,
            history=[(alokasi_enums.InvestmentStatus.SUBMITTED, 1, "")],
            extra={"zone": zone, "requested_area_m2": Decimal("50000")},
        )

    def _sample_request(  # noqa: C901
        self,
        investor,
        officer,
        plot,
        *,
        project_name,
        scheme,
        activity,
        investment_value,
        workforce,
        term_years,
        history,
        extra,
        messages=(),
        sector_name=None,
    ):
        existing = investor.investment_requests.filter(
            project_name=project_name
        ).first()
        if existing is not None:
            # Penawaran contoh yang kedaluwarsa diperpanjang agar tetap bisa dicoba.
            if (
                existing.status == alokasi_enums.InvestmentStatus.OFFERED
                and existing.offer_expired
            ):
                existing.offer_valid_until = timezone.localdate() + datetime.timedelta(
                    days=30
                )
                existing.save(update_fields=["offer_valid_until", "modified_at"])
            return
        needs_plot = "offer_plot" in extra or sector_name is None
        if needs_plot and (plot is None or not plot.is_available):
            return
        if sector_name:
            sector = InvestmentSector.objects.filter(name=sector_name).first()
        else:
            sector = plot.sector
        now = timezone.now()
        status = history[-1][0]
        investment = InvestmentRequest.objects.create(
            applicant=investor,
            status=status,
            scheme=scheme,
            sector=sector,
            project_name=project_name,
            activity=activity,
            investment_value=investment_value,
            workforce=workforce,
            term_years=term_years,
            capital_origin=investor.capital_origin,
            submitted_at=now - datetime.timedelta(days=history[0][1]),
            assigned_to=officer if len(history) > 1 else None,
            **extra,
        )
        if plot is not None:
            investment.plots.add(plot)
        for event_status, days_ago, note in history:
            InvestmentEvent.objects.create(
                request=investment,
                status=event_status,
                note=note,
                actor=(
                    investor.user
                    if event_status == alokasi_enums.InvestmentStatus.SUBMITTED
                    else officer
                ),
                created_at=now - datetime.timedelta(days=days_ago),
            )
        for from_officer, days_ago, body in messages:
            InvestmentMessage.objects.create(
                request=investment,
                author=officer if from_officer else investor.user,
                from_officer=from_officer,
                body=body,
                created_at=now - datetime.timedelta(days=days_ago),
            )

    def _assign_scopes(self, User):
        users = {
            u.username: u
            for u in sample_users().filter(
                username__in=[
                    "contoh.penilai",
                    "contoh.instansi",
                    "contoh.korwil",
                    "contoh.lapangan",
                    "contoh.administrator",
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
            komando_demo(
                users["contoh.administrator"],
                users["contoh.korwil"],
                users["contoh.lapangan"],
                korwil,
            )
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
        delete_komando_demo()
        removed = self._delete_investment_samples()
        if removed:
            self.stdout.write(f"{removed} permintaan investasi akun contoh dihapus.")
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

    @transaction.atomic
    def _delete_investment_samples(self) -> int:
        """Lahan tersimpan dan permintaan investasi akun contoh. Permintaan yang
        sudah diteruskan menjadi permohonan atau kontrak dibiarkan (akunnya lalu
        dinonaktifkan, bukan dihapus)."""
        applicants = Applicant.objects.filter(user__in=sample_users())
        SavedPlot.objects.filter(applicant__in=applicants).delete()
        requests = InvestmentRequest.objects.filter(
            applicant__in=applicants, application__isnull=True
        ).exclude(status=alokasi_enums.InvestmentStatus.COMPLETED)
        count = 0
        for investment in requests.prefetch_related("messages"):
            files = [investment.attachment] + [
                m.attachment for m in investment.messages.all()
            ]
            investment.delete()
            for field in files:
                if field:
                    field.delete(save=False)
            count += 1
        return count

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
