"""Data contoh dokumen & perizinan (fiktif, untuk uji coba panel dan portal).

python manage.py dokumen_contoh_rempang          # buat/perbarui
python manage.py dokumen_contoh_rempang --hapus  # hapus data contoh

Membuat tiga pemanfaatan lahan contoh (sewa, kerja sama, lainnya) dengan dokumen
perizinan beragam status, satu dokumen tanda tangan yang menunggu tanda tangan
pemegang hak, dan satu permintaan unduh yang menunggu persetujuan. Juga satu
dokumen tanda tangan yang sudah selesai ditandatangani langsung di hadapan
petugas (dengan kolom isian penerima, PDF final, dan komentar), permintaan unduh
yang disetujui dan sudah diunduh (log unduhan), tanda tangan tersimpan pemohon,
serta dokumen berstatus kedaluwarsa dan tidak wajib. Pemegang hak
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
from django.db.models import Q
from django.test.utils import override_settings
from django.utils import timezone
from django.utils.text import slugify

from alokasi.models import Applicant, LandPlot
from dokumen import downloads, enums, merge, services, signing
from dokumen.models import (
    DocumentTemplate,
    DownloadLog,
    DownloadRequest,
    LandUse,
    PermitRecord,
    SavedSignature,
    SigningDocument,
)
from utils.sample_files import delete_files

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


def signature_png() -> str:
    """Coretan tanda tangan contoh (PNG transparan, data URI)."""
    import base64

    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (360, 120), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.line(
        [(20, 80), (60, 30), (90, 90), (130, 40), (170, 85), (220, 35), (330, 70)],
        fill=(20, 40, 120, 255),
        width=4,
    )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def upload(title: str) -> SimpleUploadedFile:
    name = slugify(title)[:60] + ".pdf"
    return SimpleUploadedFile(name, sample_pdf(title), content_type="application/pdf")


def sample_land_uses():
    return LandUse.objects.filter(reference__startswith=PREFIX)


def delete_land_uses(queryset) -> tuple[int, int]:
    """Hapus pemanfaatan lahan beserta dokumen, permintaan unduh, dan berkasnya.

    Dipakai juga untuk pemanfaatan lahan yang terbentuk otomatis dari alokasi
    contoh. Mengembalikan (jumlah pemanfaatan lahan, jumlah dokumen tanda tangan).
    """
    land_uses = list(queryset)
    DownloadLog.objects.filter(
        Q(version__record__land_use__in=land_uses)
        | Q(signing__land_use__in=land_uses)
        | Q(request__version__record__land_use__in=land_uses)
        | Q(request__signing__land_use__in=land_uses)
    ).delete()
    DownloadRequest.objects.filter(version__record__land_use__in=land_uses).delete()
    DownloadRequest.objects.filter(signing__land_use__in=land_uses).delete()
    documents = SigningDocument.objects.filter(land_use__in=land_uses)
    count_docs = documents.count()
    for document in documents:
        delete_files(document.source_file, document.final_file)
    documents.delete()
    for record in PermitRecord.objects.filter(land_use__in=land_uses).prefetch_related(
        "versions"
    ):
        delete_files(*(version.file for version in record.versions.all()))
    LandUse.objects.filter(pk__in=[lu.pk for lu in land_uses]).delete()
    return len(land_uses), count_docs


def delete_saved_signatures(users) -> int:
    return SavedSignature.objects.filter(user__in=users).delete()[0]


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
        count, count_docs = delete_land_uses(sample_land_uses())
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
            self._draft_signing(officer)
        with transaction.atomic():
            self._download(applicant)
        with transaction.atomic():
            self._extras(officer, applicant)

    # ------------------------------------------------------------------
    # Bagian tambahan (idempoten; melengkapi data contoh versi lama)
    # ------------------------------------------------------------------

    def _extras(self, officer, applicant):
        if officer is None:
            return
        today = timezone.localdate()
        records = {
            (r.land_use.reference, r.permit_type.code): r
            for r in PermitRecord.objects.filter(
                land_use__in=sample_land_uses()
            ).select_related("land_use", "permit_type")
        }
        waived = records.get((f"{PREFIX}03", "pkkprl"))
        if waived is not None and waived.status == enums.RecordStatus.NOT_STARTED:
            services.waive(
                waived, officer, "Contoh: lokasi tidak berada di ruang laut."
            )
        expired = records.get((f"{PREFIX}02", "slf"))
        if expired is not None and expired.status == enums.RecordStatus.NOT_STARTED:
            services.officer_upload(
                expired,
                officer,
                upload(f"SLF {expired.land_use.number}"),
                note="Contoh",
                number=f"SLF/CONTOH/{today.year - 6}",
                issued_date=today - datetime.timedelta(days=5 * 365),
                expiry_date=today - datetime.timedelta(days=10),
                verify_now=True,
            )
            # Seperti tugas harian expire_records, tetapi hanya untuk dokumen
            # contoh ini (tugas harian juga menyurati pemegang hak sungguhan).
            expired.refresh_from_db()
            expired.status = enums.RecordStatus.EXPIRED
            expired.save(update_fields=["status", "modified_at"])
            services.log(
                enums.Action.EXPIRED,
                record=expired,
                detail=f"Masa berlaku berakhir {expired.expiry_date}",
            )
        if applicant is None:
            return
        self._completed_signing(officer, applicant)
        self._approved_download(applicant)
        if not SavedSignature.objects.filter(user=applicant.user).exists():
            signing.save_signature(
                applicant.user, applicant.pic_name or applicant.name, signature_png()
            )

    def _completed_signing(self, officer, applicant):
        land_use = sample_land_uses().filter(reference=f"{PREFIX}02").first()
        template = DocumentTemplate.objects.filter(
            name__istartswith="Berita acara serah terima", is_active=True
        ).first()
        if land_use is None or template is None or land_use.signing_documents.exists():
            return
        document = signing.create(
            user=officer,
            title=f"Berita acara serah terima lahan – {land_use.holder_display}",
            template=template,
            land_use=land_use,
        )
        leftovers = {
            name
            for group, name in merge.FIELD_RE.findall(document.body)
            if group == "isian"
        }
        if leftovers:
            signing.fill_fields(document, {key: "Contoh" for key in leftovers}, officer)
        signing.update_body(
            document,
            document.body
            + "<p>Nomor telepon yang dapat dihubungi: {{ kolom.telepon }}</p>",
            officer,
        )
        holder = document.recipients.filter(order=1).first()
        if holder is None:
            holder = document.recipients.create(
                order=1,
                role="Pemegang hak",
                action=enums.RecipientAction.SIGN,
                name=land_use.holder_display,
                email=APPLICANT_EMAIL,
            )
        holder.in_person = True
        holder.save(update_fields=["in_person"])
        signing.sync_fields(document, default_recipient=holder)
        document.fields.update(recipient=holder)
        signing.add_comment(
            document,
            officer,
            "Contoh: penandatanganan dijadwalkan di kantor pelayanan.",
            internal=True,
        )
        signing.send(document, officer)
        holder.refresh_from_db()
        signing.start_hosted(holder, officer, "KTP contoh diperiksa petugas")
        holder.refresh_from_db()
        signing.act(
            holder,
            name=holder.name,
            signature=signature_png(),
            field_values={"telepon": "081200000000"},
            host=officer,
        )
        signing.add_comment(
            document,
            applicant.user,
            "Terima kasih, salinan sudah saya terima. (contoh)",
        )

    def _approved_download(self, applicant):
        approver = (
            get_user_model().objects.filter(username="contoh.administrator").first()
        )
        record = PermitRecord.objects.filter(
            land_use__reference=f"{PREFIX}02",
            permit_type__code="pkkpr",
            status=enums.RecordStatus.VERIFIED,
        ).first()
        version = record.latest_version if record else None
        if (
            approver is None
            or version is None
            or DownloadRequest.objects.filter(
                version=version, requester=applicant.user
            ).exists()
        ):
            return
        request = downloads.request_download(
            applicant.user,
            version=version,
            purpose=enums.DownloadPurpose.FINANCING,
            reason="Contoh: lampiran pengajuan izin usaha ke instansi lain.",
        )
        if request.status == enums.DownloadStatus.PENDING:
            downloads.approve(request, approver, note="Disetujui (contoh).")
        request.refresh_from_db()
        if request.status == enums.DownloadStatus.APPROVED:
            downloads.consume(request, applicant.user)

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

    def _draft_signing(self, officer):
        """Satu dokumen berstatus Draf, agar halaman penyusunan bisa dicoba."""
        land_use = sample_land_uses().filter(reference=f"{PREFIX}03").first()
        if land_use is None or officer is None or land_use.signing_documents.exists():
            return
        template = DocumentTemplate.objects.filter(
            name__istartswith="Perjanjian sewa", is_active=True
        ).first()
        if template is None:
            return
        document = signing.create(
            user=officer,
            title=f"Perjanjian sewa lahan – {land_use.holder_display}",
            template=template,
            land_use=land_use,
        )
        if not document.recipients.exists():
            document.recipients.create(
                order=1,
                role="Pemegang hak",
                action=enums.RecipientAction.SIGN,
                name=land_use.holder_display,
                email=APPLICANT_EMAIL,
            )

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
