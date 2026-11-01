"""Permohonan alokasi contoh untuk akun pemohon contoh (fiktif).

Dipanggil oleh ``pengguna_contoh`` setelah akun pemohon, investor, petugas
alokasi, dan tim verifikasi contoh ada, di lahan ``alokasi_contoh_rempang``.
Setiap langkah memakai layanan yang sama dengan portal dan panel petugas
(``alokasi.services``) sehingga nomor, tagihan, dokumen KPT/PPT/PL, dan
riwayatnya sama persis dengan pemakaian sungguhan. Surel ditampung di memori,
tidak pernah dikirim.

Hasilnya, satu per status:

* CONTOH-RMP-02 – alokasi aktif (KPT, PPT, PL terbit), dua laporan
  pembangunan, surat rekomendasi terbit, dan peralihan hak ke investor contoh
  yang menunggu persetujuan penerima.
* CONTOH-RMP-03 – disetujui, bukti bayar diunggah dan menunggu verifikasi.
* CONTOH-RMP-04 – verifikasi teknis, sebagian kriteria sudah dinilai.
* CONTOH-RMP-06 – satu permohonan ditolak, lalu permohonan baru yang
  diminta perbaikan.
* CONTOH-RMP-05 – draf yang belum diajukan.
"""

import datetime
from decimal import Decimal

from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone

from alokasi import enums, services
from alokasi.models import (
    Allocation,
    Application,
    ApplicationDocument,
    ApplicationEvent,
    DevelopmentReport,
    IssuedDocument,
    LandPlot,
    RequirementDocType,
    VerificationCriterion,
    VerificationScore,
)
from utils.sample_files import delete_files, jpeg_upload, pdf_upload

PLOT_PREFIX = "CONTOH-RMP-"
MARK = "[contoh]"
LOCMEM = "django.core.mail.backends.locmem.EmailBackend"
S = enums.ApplicationStatus


def _plot(code):
    plot = LandPlot.objects.filter(code=f"{PLOT_PREFIX}{code}").first()
    return plot if plot is not None and plot.is_open_for_application else None


def _documents(application, user):
    for doc_type in RequirementDocType.for_application(application):
        if application.documents.filter(doc_type=doc_type).exists():
            continue
        title = f"{doc_type.name} {application.number}"
        ApplicationDocument.objects.create(
            application=application,
            doc_type=doc_type,
            file=pdf_upload(title, (f"Pemohon: {application.applicant.name}",)),
            original_name=f"{doc_type.name[:60]} (contoh).pdf",
        )


def _allocation_application(applicant, plot, *, value, workforce, months, text):
    application = services.create_allocation_application(applicant, plot)
    application.activity = plot.intended_use or "Kegiatan usaha"
    application.investment_value = Decimal(value)
    application.workforce = workforce
    application.development_months = months
    application.description = f"{MARK} {text}"
    application.save()
    _documents(application, applicant.user)
    return services.submit(application, applicant.user)


def _score(application, verifier, value, limit=None):
    criteria = VerificationCriterion.objects.filter(is_active=True).order_by("pk")
    for criterion in criteria[:limit] if limit else criteria:
        VerificationScore.objects.update_or_create(
            application=application,
            criterion=criterion,
            verifier=verifier,
            defaults={"score": Decimal(value), "note": "Penilaian contoh."},
        )


def _pay_all(application, applicant, officer, verify=True):
    for invoice in application.invoices.all():
        services.upload_payment_proof(
            invoice,
            jpeg_upload(f"Bukti transfer {invoice.number}"),
            applicant.user,
        )
        if verify:
            services.verify_payment(invoice, officer, "Dana masuk (contoh).")
    application.refresh_from_db()
    return application


def _service(applicant, allocation, service_type, reason):
    application = services.create_service_application(
        applicant, allocation, service_type, f"{MARK} {reason}"
    )
    _documents(application, applicant.user)
    return services.submit(application, applicant.user)


def _spread_history(application, days):
    """Riwayat contoh dibuat dalam sekejap; sebar waktunya agar terbaca wajar."""
    events = list(application.events.order_by("pk"))
    step = max(days // max(len(events), 1), 1)
    now = timezone.now()
    for index, event in enumerate(events):
        moment = now - datetime.timedelta(days=days - index * step, hours=index)
        ApplicationEvent.objects.filter(pk=event.pk).update(created_at=moment)
    if application.submitted_at:
        Application.objects.filter(pk=application.pk).update(
            submitted_at=now - datetime.timedelta(days=days - step)
        )


def sample_applications(applicant):
    return Application.objects.filter(applicant=applicant)


@transaction.atomic
def permohonan_demo(applicant, investor, officer, verifier) -> int:
    """Buat permohonan contoh (sekali). Mengembalikan jumlah permohonan baru."""
    if applicant is None or officer is None or verifier is None:
        return 0
    if sample_applications(applicant).exists():
        return 0
    if not VerificationCriterion.objects.filter(is_active=True).exists():
        # Kriteria verifikasi dipasang oleh migrasi; tanpa itu permohonan tidak
        # bisa disetujui sehingga contoh permohonan dilewati.
        return 0
    with override_settings(EMAIL_BACKEND=LOCMEM):
        return _create(applicant, investor, officer, verifier)


def _create(applicant, investor, officer, verifier) -> int:  # noqa: C901
    created = 0
    # 1. Alokasi aktif lengkap dengan dokumen terbit dan laporan pembangunan.
    plot = _plot("02")
    if plot is not None:
        application = _allocation_application(
            applicant,
            plot,
            value="42000000000",
            workforce=120,
            months=24,
            text="Pabrik perakitan panel surya skala menengah.",
        )
        services.start_verification(application, officer)
        _score(application, verifier, 85)
        services.approve(application, officer, "Memenuhi syarat teknis (contoh).")
        application = _pay_all(application, applicant, officer)
        _spread_history(application, 90)
        created += 1
        allocation = Allocation.objects.filter(application=application).first()
        if allocation is not None:
            today = timezone.localdate()
            for days, stage, progress, value, workers, text in (
                (60, enums.DevelopmentStage.PREPARATION, 15, "3500000000", 25,
                 "Pematangan lahan dan pagar keliling."),
                (10, enums.DevelopmentStage.CONSTRUCTION, 40, "12500000000", 80,
                 "Pondasi dan rangka baja gedung produksi."),
            ):  # fmt: skip
                DevelopmentReport.objects.create(
                    allocation=allocation,
                    report_date=today - datetime.timedelta(days=days),
                    stage=stage,
                    progress_percent=progress,
                    realized_investment=Decimal(value),
                    workforce=workers,
                    description=f"{MARK} {text}",
                    photo=jpeg_upload(f"Progres {allocation.kpt_number} {progress}"),
                    reported_by=applicant.user,
                )
            recommendation = _service(
                applicant,
                allocation,
                enums.ServiceType.RECOMMENDATION,
                "Surat rekomendasi untuk pengajuan izin lingkungan.",
            )
            services.start_verification(recommendation, officer)
            services.approve(recommendation, officer, "Rekomendasi diterbitkan.")
            recommendation = _pay_all(recommendation, applicant, officer)
            _spread_history(recommendation, 30)
            created += 1
            if investor is not None:
                transfer = services.create_transfer_application(
                    applicant,
                    allocation,
                    investor,
                    f"{MARK} Pengalihan sebagian usaha kepada mitra investor.",
                )
                _documents(transfer, applicant.user)
                transfer = services.submit(transfer, applicant.user)
                _spread_history(transfer, 3)
                created += 1

    # 2. Disetujui; bukti bayar menunggu verifikasi petugas.
    plot = _plot("03")
    if plot is not None:
        application = _allocation_application(
            applicant,
            plot,
            value="65000000000",
            workforce=150,
            months=30,
            text="Resor pantai 80 kamar dan restoran.",
        )
        services.start_verification(application, officer)
        _score(application, verifier, 78)
        services.approve(application, officer, "Disetujui (contoh).")
        _pay_all(application, applicant, officer, verify=False)
        _spread_history(application, 21)
        created += 1

    # 3. Verifikasi teknis berjalan, sebagian kriteria sudah dinilai.
    plot = _plot("04")
    if plot is not None:
        application = _allocation_application(
            applicant,
            plot,
            value="18000000000",
            workforce=60,
            months=18,
            text="Gudang logistik berpendingin.",
        )
        services.start_verification(application, officer)
        _score(application, verifier, 72, limit=2)
        _spread_history(application, 7)
        created += 1

    # 4. Ditolak, lalu permohonan baru di lahan yang sama diminta perbaikan.
    plot = _plot("06")
    if plot is not None:
        rejected = _allocation_application(
            applicant,
            plot,
            value="900000000",
            workforce=5,
            months=6,
            text="Lapak dagang sementara.",
        )
        services.reject(
            rejected,
            officer,
            "Rencana usaha belum sesuai arahan kawasan perdagangan (contoh).",
        )
        _spread_history(rejected, 40)
        created += 1
        plot.refresh_from_db()
        if plot.is_open_for_application:
            revision = _allocation_application(
                applicant,
                plot,
                value="9500000000",
                workforce=45,
                months=12,
                text="Pusat perbelanjaan skala lingkungan.",
            )
            services.request_revision(
                revision,
                officer,
                "Lengkapi rencana tapak dan perhitungan kebutuhan parkir (contoh).",
            )
            _spread_history(revision, 5)
            created += 1

    # 5. Draf yang belum diajukan.
    plot = _plot("05")
    if plot is not None:
        draft = services.create_allocation_application(applicant, plot)
        draft.description = f"{MARK} Sekolah kejuruan maritim (draf)."
        draft.save()
        created += 1
    return created


@transaction.atomic
def delete_permohonan_demo(applicants) -> int:
    """Hapus permohonan akun contoh beserta tagihan, alokasi, dokumen terbit,
    laporan, dan pemanfaatan lahan yang terbentuk dari alokasinya."""
    from dokumen.management.commands.dokumen_contoh_rempang import delete_land_uses
    from dokumen.models import LandUse

    applications = Application.objects.filter(applicant__in=applicants)
    allocations = Allocation.objects.filter(application__in=applications)
    delete_land_uses(LandUse.objects.filter(allocation__in=allocations))
    for report in DevelopmentReport.objects.filter(allocation__in=allocations):
        delete_files(report.photo)
    DevelopmentReport.objects.filter(allocation__in=allocations).delete()
    issued = IssuedDocument.objects.filter(application__in=applications)
    delete_files(*(doc.file for doc in issued))
    issued.delete()
    for application in applications.prefetch_related("invoices", "documents"):
        delete_files(*(invoice.payment_proof for invoice in application.invoices.all()))
        delete_files(*(doc.file for doc in application.documents.all()))
    from alokasi.models import InvestmentRequest, Invoice

    Invoice.objects.filter(application__in=applications).delete()
    InvestmentRequest.objects.filter(application__in=applications).update(
        application=None
    )
    # Permohonan layanan/peralihan merujuk alokasi (PROTECT): hapus lebih dulu.
    count = applications.count()
    applications.filter(source_allocation__in=allocations).delete()
    Application.objects.filter(source_allocation__in=allocations).delete()
    plots = list(allocations.values_list("plot_id", flat=True))
    allocations.delete()
    applications.delete()
    # Lahan contoh yang sempat dialokasikan/dipesan kembali tersedia.
    LandPlot.objects.filter(pk__in=plots, code__startswith=PLOT_PREFIX).update(
        status=enums.PlotStatus.AVAILABLE
    )
    LandPlot.objects.filter(code__startswith=PLOT_PREFIX).exclude(
        applications__isnull=False
    ).filter(status=enums.PlotStatus.RESERVED).update(status=enums.PlotStatus.AVAILABLE)
    return count
