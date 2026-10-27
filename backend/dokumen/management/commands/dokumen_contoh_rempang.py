"""Data contoh dokumen & perizinan (fiktif, untuk uji coba panel dan portal).

python manage.py dokumen_contoh_rempang          # buat/perbarui
python manage.py dokumen_contoh_rempang --hapus  # hapus data contoh

Membuat tiga pemanfaatan lahan contoh (sewa, kerja sama, lainnya) dengan dokumen
perizinan beragam status, satu dokumen tanda tangan yang menunggu tanda tangan
pemegang hak, dan satu permintaan unduh yang menunggu persetujuan. Pemegang hak
memakai akun pemohon contoh dari ``pengguna_contoh`` bila ada (jalankan perintah
itu lebih dahulu agar data terlihat di portal). Tidak ada surel yang dikirim.
"""

import datetime
import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone
from django.utils.text import slugify

from alokasi.models import Applicant, LandPlot
from dokumen import downloads, enums, services, signing
from dokumen.models import (
    DocumentTemplate,
    DownloadRequest,
    LandUse,
    PermitRecord,
    SigningDocument,
)

PREFIX = "CONTOH-DOK-"
APPLICANT_EMAIL = "pemohon@contoh.simlahan.invalid"
OFFICER_USERNAME = "contoh.alokasi"
LOCMEM = "django.core.mail.backends.locmem.EmailBackend"

# (kode, judul, skema, kode lahan contoh, luas m²)
LAND_USES = [
    (
        "01",
        "Pabrik pengolahan hasil laut (contoh)",
        enums.Scheme.LEASE,
        "CONTOH-RMP-01",
        Decimal("25000"),
    ),
    (
        "02",
        "Resor wisata bahari (contoh)",
        enums.Scheme.PARTNERSHIP,
        "CONTOH-RMP-03",
        Decimal("40000"),
    ),
    (
        "03",
        "Gudang logistik (contoh)",
        enums.Scheme.OTHER,
        "CONTOH-RMP-02",
        Decimal("12000"),
    ),
]


def sample_pdf(title: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    page = canvas.Canvas(buffer, pagesize=A4)
    page.setFont("Helvetica-Bold", 16)
    page.drawString(72, 770, title)
    page.setFont("Helvetica", 11)
    page.drawString(72, 745, "DOKUMEN CONTOH - FIKTIF - BUKAN DOKUMEN SAH")
    page.drawString(
        72, 725, "Dibuat oleh perintah dokumen_contoh_rempang untuk uji coba SimLahan."
    )
    page.showPage()
    page.save()
    return buffer.getvalue()


def upload(title: str) -> SimpleUploadedFile:
    name = slugify(title)[:60] + ".pdf"
    return SimpleUploadedFile(name, sample_pdf(title), content_type="application/pdf")


def sample_land_uses():
    return LandUse.objects.filter(reference__startswith=PREFIX)


class Command(BaseCommand):
    help = "Buat atau hapus data contoh dokumen & perizinan"

    def add_arguments(self, parser):
        parser.add_argument("--hapus", action="store_true", help="Hapus data contoh")

    def handle(self, *args, **options):
        # Surel ditampung di memori: data contoh tidak pernah mengirim surel sungguhan.
        with override_settings(EMAIL_BACKEND=LOCMEM):
            if options["hapus"]:
                self._delete()
            else:
                self._create()

    @transaction.atomic
    def _delete(self):
        land_uses = list(sample_land_uses())
        DownloadRequest.objects.filter(version__record__land_use__in=land_uses).delete()
        DownloadRequest.objects.filter(signing__land_use__in=land_uses).delete()
        documents = SigningDocument.objects.filter(land_use__in=land_uses)
        count_docs = documents.count()
        for document in documents:
            for field in (document.source_file, document.final_file):
                if field:
                    field.delete(save=False)
        documents.delete()
        for record in PermitRecord.objects.filter(
            land_use__in=land_uses
        ).prefetch_related("versions"):
            for version in record.versions.all():
                version.file.delete(save=False)
        count = len(land_uses)
        LandUse.objects.filter(pk__in=[lu.pk for lu in land_uses]).delete()
        self.stdout.write(
            f"{count} pemanfaatan lahan contoh dan {count_docs} dokumen tanda tangan contoh dihapus."
        )

    def _create(self):
        User = get_user_model()
        officer = User.objects.filter(username=OFFICER_USERNAME).first()
        applicant = (
            Applicant.objects.filter(user__email__iexact=APPLICANT_EMAIL)
            .select_related("user")
            .first()
        )
        if applicant is None:
            self.stdout.write(
                "Akun pemohon contoh belum ada: pemanfaatan lahan dibuat tanpa akun portal "
                "(jalankan pengguna_contoh lalu perintah ini lagi agar terlihat di portal)."
            )
        created = 0
        for code, title, scheme, plot_code, area in LAND_USES:
            with transaction.atomic():
                land_use, is_new = self._land_use(
                    code, title, scheme, plot_code, area, applicant
                )
                created += is_new
                services.ensure_records(land_use)
                if is_new:
                    self._fill(land_use, officer, applicant)
        self.stdout.write(
            f"{created} pemanfaatan lahan contoh dibuat, {len(LAND_USES) - created} sudah ada."
        )
        with transaction.atomic():
            self._signing(officer, applicant)
        with transaction.atomic():
            self._download(applicant)

    def _land_use(self, code, title, scheme, plot_code, area, applicant):
        today = timezone.localdate()
        defaults = {
            "title": title,
            "scheme": scheme,
            "holder": applicant,
            "holder_name": (
                applicant.name if applicant else "PT Contoh Investasi Rempang"
            ),
            "plot": LandPlot.objects.filter(code=plot_code).first(),
            "area_m2": area,
            "start_date": today.replace(month=1, day=1),
            "end_date": today.replace(month=1, day=1, year=today.year + 30),
        }
        land_use = sample_land_uses().filter(reference=f"{PREFIX}{code}").first()
        if land_use is None:
            return LandUse.objects.create(reference=f"{PREFIX}{code}", **defaults), True
        if applicant is not None and land_use.holder_id is None:
            land_use.holder = applicant
            land_use.holder_name = applicant.name
            land_use.save(update_fields=["holder", "holder_name", "modified_at"])
        return land_use, False

    def _fill(self, land_use, officer, applicant):
        """Beragam status agar dasbor, antrean verifikasi, dan portal terisi."""
        today = timezone.localdate()
        holder_user = applicant.user if applicant else None
        records = {
            r.permit_type.code: r
            for r in land_use.records.select_related("permit_type")
        }
        plan = {
            "nib": ("verified", today - datetime.timedelta(days=400), None),
            "pkkpr": (
                "verified",
                today - datetime.timedelta(days=200),
                today + datetime.timedelta(days=25),
            ),
            "lingkungan": ("submitted", None, None),
            "pbg": ("revision", None, None),
            "andalalin": ("progress", None, None),
        }
        for code, (state, issued, expiry) in plan.items():
            record = records.get(code)
            if record is None:
                continue
            name = f"{record.permit_type.name} {land_use.number}"
            if state == "verified" and officer is not None:
                services.officer_upload(
                    record,
                    officer,
                    upload(name),
                    note="Contoh",
                    number=f"{code.upper()}/CONTOH/{today.year}",
                    issued_date=issued,
                    expiry_date=expiry,
                    verify_now=True,
                )
            elif state in ("submitted", "revision"):
                services.holder_update(
                    record,
                    holder_user,
                    upload=upload(name),
                    number=f"{code.upper()}/CONTOH/{today.year}",
                    note="Unggahan contoh",
                )
                if state == "revision" and officer is not None:
                    services.request_revision(
                        record,
                        officer,
                        "Contoh: halaman tanda tangan pejabat belum terbaca, unggah ulang hasil pindai yang jelas.",
                    )
            elif state == "progress":
                services.holder_update(
                    record, holder_user, status=enums.RecordStatus.IN_PROGRESS
                )

    def _signing(self, officer, applicant):
        land_use = sample_land_uses().filter(reference=f"{PREFIX}01").first()
        if land_use is None or officer is None:
            return
        if land_use.signing_documents.exists():
            return
        template = DocumentTemplate.objects.filter(
            name__istartswith="Surat pernyataan", is_active=True
        ).first()
        if template is None:
            return
        document = signing.create(
            user=officer,
            title=f"Surat pernyataan kesanggupan – {land_use.holder_display}",
            template=template,
            land_use=land_use,
            extra={"batas_waktu": "6 (enam) bulan"},
        )
        if not document.recipients.exists():
            document.recipients.create(
                order=1,
                role="Pemegang hak",
                action=enums.RecipientAction.SIGN,
                name=land_use.holder_display,
                email=APPLICANT_EMAIL,
            )
        document.recipients.create(
            order=2,
            role="Petugas alokasi",
            action=enums.RecipientAction.APPROVE,
            user=officer,
            name=officer.get_full_name() or officer.get_username(),
            email=officer.email or f"{officer.get_username()}@contoh.simlahan.invalid",
        )
        if document.needs_approval:
            return
        signing.send(document, officer)

    def _download(self, applicant):
        if applicant is None:
            return
        record = PermitRecord.objects.filter(
            land_use__reference=f"{PREFIX}01",
            permit_type__code="nib",
            status=enums.RecordStatus.VERIFIED,
        ).first()
        version = record.latest_version if record else None
        if (
            version is None
            or DownloadRequest.objects.filter(
                version=version, requester=applicant.user
            ).exists()
        ):
            return
        downloads.request_download(
            applicant.user,
            version=version,
            purpose=enums.DownloadPurpose.FINANCING,
            reason="Contoh: lampiran pengajuan kredit modal kerja ke bank.",
        )
