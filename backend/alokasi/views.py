"""Portal publik dan akun pemohon (/portal/)."""

import json
import mimetypes
import os
from decimal import Decimal
from functools import wraps
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from alokasi import documents, enums, services
from alokasi.forms import (
    AllocationApplicationForm,
    ApplicantProfileForm,
    DevelopmentReportForm,
    DocumentUploadForm,
    PaymentProofForm,
    PermitReportForm,
    PortalLoginForm,
    RegistrationForm,
    ResendActivationForm,
    ServiceApplicationForm,
    ServiceReasonEditForm,
    TrackApplicationForm,
    TransferApplicationForm,
    TransferEditForm,
    UwtCalculatorForm,
    VerifyCodeForm,
)
from alokasi.models import (
    Allocation,
    AllocationSettings,
    Application,
    ApplicationDocument,
    DevelopmentReport,
    InfoPage,
    Invoice,
    IssuedDocument,
    LandPlot,
    PermitReport,
    RequirementDocType,
    ServiceCatalog,
    VerificationCriterion,
)
from alokasi.monitoring import report_deadline
from file_operations.errors import FileScanError, FileScanPendingError, FileUnsafeError

User = get_user_model()
S = enums.ApplicationStatus


# --------------------------------------------------------------------------
# Utilitas
# --------------------------------------------------------------------------


class ActivationTokenGenerator(PasswordResetTokenGenerator):
    """Token aktivasi sekali pakai: tidak berlaku lagi setelah akun aktif."""

    key_salt = "alokasi.views.ActivationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.is_active}{user.password}{timestamp}{user.email}"


activation_token = ActivationTokenGenerator()


def _client_ip(request) -> str:
    # Di belakang reverse proxy, REMOTE_ADDR selalu alamat proxy sehingga semua
    # pengunjung berbagi satu kuota. Setiap proxy tepercaya menambahkan satu
    # alamat di ujung X-Forwarded-For, jadi alamat klien ada di posisi ke-N dari
    # belakang (N = TRUSTED_PROXY_COUNT). Entri di depannya bisa dipalsukan.
    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        hops = max(getattr(settings, "TRUSTED_PROXY_COUNT", 1), 1)
        forwarded = [
            part.strip()
            for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
            if part.strip()
        ]
        if forwarded:
            return forwarded[-min(hops, len(forwarded))]
    return request.META.get("REMOTE_ADDR", "")


def _absolute_url(request, path: str) -> str:
    """Tautan untuk surel: pakai OFFICER_UI_URL bila diisi (alamat publik)."""
    base = (getattr(settings, "OFFICER_UI_URL", "") or "").rstrip("/")
    return f"{base}{path}" if base else request.build_absolute_uri(path)


def _throttled(request, scope: str, limit: int = 10, window: int = 60) -> bool:
    """Batasi percobaan per alamat IP (masuk, daftar, lupa sandi)."""
    key = f"alokasi:throttle:{scope}:{_client_ip(request)}"
    try:
        count = cache.get_or_set(key, 0, window)
        if count >= limit:
            return True
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, window)
    return False


def _too_many(request):
    return render(request, "alokasi/portal/throttled.html", status=429)


def applicant_required(view):
    """Hanya untuk akun pemohon yang sedang masuk."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            login_url = reverse("portal:login")
            return redirect(f"{login_url}?next={request.get_full_path()}")
        applicant = getattr(request.user, "pemohon", None)
        if applicant is None:
            return render(request, "alokasi/portal/not_applicant.html", status=403)
        request.applicant = applicant
        return view(request, *args, **kwargs)

    return wrapper


# Tipe yang aman disajikan inline; lainnya (mis. .html/.svg hasil unggahan)
# dipaksa unduh agar tidak dieksekusi sebagai konten aktif di domain portal.
INLINE_SAFE_CONTENT_TYPES = {
    "image/avif",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
}


def serve_file(fieldfile, *, inline=False, filename=None):
    if not fieldfile:
        raise Http404
    try:
        handle = fieldfile.open("rb")
    except FileNotFoundError:
        raise Http404
    except FileScanPendingError:
        return HttpResponse(_("Berkas masih menunggu pemindaian virus."), status=403)
    except (FileUnsafeError, FileScanError):
        return HttpResponse(_("Berkas tidak aman untuk diunduh."), status=403)
    name = filename or os.path.basename(fieldfile.name)
    content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    inline = inline and content_type in INLINE_SAFE_CONTENT_TYPES
    response = FileResponse(
        handle, as_attachment=not inline, filename=name, content_type=content_type
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


def _paginate(request, queryset, per_page=20):
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))


def _form_errors(error: ValidationError) -> list[str]:
    return list(error.messages)


# --------------------------------------------------------------------------
# Halaman publik
# --------------------------------------------------------------------------


def home(request):
    plots = LandPlot.objects.filter(is_published=True)
    available = plots.filter(status=enums.PlotStatus.AVAILABLE)
    stats = available.aggregate(total=Count("pk"), area=Sum("area_m2"))
    by_type = {
        row["allocation_type"]: row["n"]
        for row in available.values("allocation_type").annotate(n=Count("pk"))
    }
    context = {
        "stats": stats,
        "allocated_count": plots.filter(status=enums.PlotStatus.ALLOCATED).count(),
        "allocation_types": [
            (value, label, by_type.get(value, 0))
            for value, label in enums.AllocationType.choices
        ],
        "announcements": InfoPage.objects.filter(
            is_published=True, category=enums.InfoCategory.ANNOUNCEMENT
        ).order_by("-published_at")[:5],
        "tutorials": InfoPage.objects.filter(
            is_published=True, category=enums.InfoCategory.TUTORIAL
        )[:3],
        "latest_plots": available.order_by("-created_at")[:6],
    }
    return render(request, "alokasi/portal/home.html", context)


def _plot_queryset(request):
    plots = LandPlot.objects.filter(is_published=True).exclude(
        status=enums.PlotStatus.CLOSED
    )
    filters = {
        "q": request.GET.get("q", "").strip(),
        "jenis": request.GET.get("jenis", ""),
        "status": request.GET.get("status", ""),
        "kecamatan": request.GET.get("kecamatan", ""),
    }
    if filters["q"]:
        q = filters["q"]
        plots = plots.filter(
            Q(code__icontains=q)
            | Q(name__icontains=q)
            | Q(village__icontains=q)
            | Q(intended_use__icontains=q)
            | Q(zoning__icontains=q)
        )
    if filters["jenis"] in enums.AllocationType.values:
        plots = plots.filter(allocation_type=filters["jenis"])
    if filters["status"] in enums.PlotStatus.values:
        plots = plots.filter(status=filters["status"])
    if filters["kecamatan"]:
        plots = plots.filter(district=filters["kecamatan"])
    return plots, filters


def plot_list(request):
    plots, filters = _plot_queryset(request)
    districts = (
        LandPlot.objects.filter(is_published=True)
        .exclude(district="")
        .values_list("district", flat=True)
        .distinct()
        .order_by("district")
    )
    query = request.GET.copy()
    query.pop("page", None)
    context = {
        "page": _paginate(request, plots.order_by("code")),
        "filters": filters,
        "districts": districts,
        "allocation_types": enums.AllocationType.choices,
        "statuses": [
            s for s in enums.PlotStatus.choices if s[0] != enums.PlotStatus.CLOSED
        ],
        "geojson_url": reverse("portal:plot_geojson")
        + (f"?{query.urlencode()}" if query else ""),
        "querystring": query.urlencode(),
    }
    return render(request, "alokasi/portal/plot_list.html", context)


def plot_geojson(request):
    plots, _filters = _plot_queryset(request)
    features = []
    for plot in plots.exclude(geometry__isnull=True):
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(plot.geometry.geojson),
                "properties": {
                    "code": plot.code,
                    "name": plot.name,
                    "status": plot.status,
                    "status_label": plot.get_status_display(),
                    "allocation_type": plot.get_allocation_type_display(),
                    "area_m2": float(plot.area_m2),
                    "intended_use": plot.intended_use,
                    "url": reverse("portal:plot_detail", args=[plot.code]),
                },
            }
        )
    response = JsonResponse({"type": "FeatureCollection", "features": features})
    response["Cache-Control"] = "public, max-age=60"
    return response


def plot_detail(request, code):
    plot = get_object_or_404(LandPlot, code=code, is_published=True)
    config = AllocationSettings.load()
    own_application = None
    applicant = (
        getattr(request.user, "pemohon", None)
        if request.user.is_authenticated
        else None
    )
    if applicant:
        own_application = (
            applicant.applications.filter(plot=plot)
            .exclude(status__in=enums.FINAL_STATUSES)
            .first()
        )
    context = {
        "plot": plot,
        "config": config,
        "geometry": plot.geometry.geojson if plot.geometry else "",
        "requirements": RequirementDocType.objects.filter(
            is_active=True, service_type=enums.ServiceType.ALLOCATION
        ).filter(Q(allocation_type="") | Q(allocation_type=plot.allocation_type)),
        "own_application": own_application,
        "is_applicant": applicant is not None,
    }
    return render(request, "alokasi/portal/plot_detail.html", context)


def plot_photo(request, code):
    plot = get_object_or_404(LandPlot, code=code, is_published=True)
    return serve_file(plot.photo, inline=True)


def services_page(request):
    requirements = RequirementDocType.objects.filter(is_active=True)
    grouped = []
    for service_value, service_label in enums.ServiceType.choices:
        docs = [d for d in requirements if d.service_type == service_value]
        grouped.append((service_value, service_label, docs))
    context = {
        "config": AllocationSettings.load(),
        "requirements": grouped,
        "allocation_types": enums.AllocationType.choices,
        "criteria": VerificationCriterion.objects.filter(is_active=True),
        "procedures": InfoPage.objects.filter(
            is_published=True, category=enums.InfoCategory.PROCEDURE
        ),
    }
    return render(request, "alokasi/portal/services.html", context)


def service_catalog(request):
    """Katalog layanan terstruktur (ala LMS): daftar per kelompok."""
    entries = ServiceCatalog.objects.filter(is_active=True)
    grouped = [
        (value, label, list(entries.filter(category=value)))
        for value, label in ServiceCatalog.Category.choices
        if entries.filter(category=value).exists()
    ]
    return render(
        request,
        "alokasi/portal/service_catalog.html",
        {"grouped": grouped},
    )


def service_catalog_detail(request, slug):
    entry = get_object_or_404(ServiceCatalog, slug=slug, is_active=True)
    return render(
        request,
        "alokasi/portal/service_catalog_detail.html",
        {
            "entry": entry,
            "requirements": entry.requirement_docs,
            "config": AllocationSettings.load(),
        },
    )


def uwt_calculator(request):
    """Simulasi biaya UWT lahan; murni hitungan, tidak menyimpan data."""
    config = AllocationSettings.load()
    form = UwtCalculatorForm(request.GET or None)
    result = None
    if form.is_valid():
        plot = form.cleaned_data["plot"]
        area = form.cleaned_data["area_m2"]
        years = form.cleaned_data["years"]
        total = (area * plot.uwt_rate_per_m2_year * years).quantize(Decimal("1"))
        result = {
            "plot": plot,
            "area_m2": area,
            "years": years,
            "rate": plot.uwt_rate_per_m2_year,
            "uwt_total": total,
            "admin_fee": config.allocation_admin_fee,
            "grand_total": (total + config.allocation_admin_fee).quantize(Decimal("1")),
        }
    elif form.is_bound:
        # Isian belum lengkap: prapisi luas/jangka dari lahan terpilih bila ada.
        plot_id = request.GET.get("plot")
        if plot_id:
            plot = LandPlot.objects.filter(pk=plot_id, is_published=True).first()
            if plot:
                form.fields["area_m2"].initial = plot.area_m2
                form.fields["years"].initial = plot.effective_term_years
    return render(
        request,
        "alokasi/portal/calculator.html",
        {"form": form, "result": result, "config": config},
    )


def track_application(request):
    """Lacak permohonan publik: nomor + PIN, tanpa login."""
    form = TrackApplicationForm(request.POST or None)
    application = None
    public_events = []
    if request.method == "POST" and form.is_valid():
        if _throttled(request, "lacak", limit=10, window=60):
            return _too_many(request)
        application = (
            Application.objects.filter(
                number__iexact=form.cleaned_data["number"].strip(),
                tracking_pin__iexact=form.cleaned_data["pin"].strip(),
            )
            .select_related("plot", "source_allocation__plot")
            .first()
        )
        if application is None:
            form.add_error(None, _("Nomor atau PIN pelacakan tidak ditemukan."))
        else:
            # Rincian hanya nomor, layanan, status, dan riwayat — tanpa data
            # pribadi pemohon.
            public_events = list(application.events.order_by("created_at", "pk"))
    return render(
        request,
        "alokasi/portal/track.html",
        {
            "form": form,
            "application": application,
            "public_events": public_events,
        },
    )


def help_page(request):
    """Halaman bantuan: tanya jawab, regulasi, tutorial, dan kontak."""
    return render(
        request,
        "alokasi/portal/help.html",
        {
            "faqs": InfoPage.objects.filter(
                is_published=True, category=enums.InfoCategory.FAQ
            ),
            "regulations": InfoPage.objects.filter(
                is_published=True, category=enums.InfoCategory.REGULATION
            ),
            "tutorials": InfoPage.objects.filter(
                is_published=True, category=enums.InfoCategory.TUTORIAL
            ),
            "config": AllocationSettings.load(),
        },
    )


def info_index(request, category=None):
    pages = InfoPage.objects.filter(is_published=True)
    if category is not None:
        if category not in enums.InfoCategory.values:
            raise Http404
        pages = pages.filter(category=category)
    q = request.GET.get("q", "").strip()
    if q:
        pages = pages.filter(
            Q(title__icontains=q) | Q(summary__icontains=q) | Q(body__icontains=q)
        )
    counts = dict(
        InfoPage.objects.filter(is_published=True)
        .values_list("category")
        .annotate(n=Count("pk"))
    )
    context = {
        "page": _paginate(request, pages),
        "category": category,
        "category_label": (
            enums.InfoCategory(category).label if category else _("Semua informasi")
        ),
        "categories": [
            (v, label, counts.get(v, 0)) for v, label in enums.InfoCategory.choices
        ],
        "q": q,
        "querystring": urlencode({"q": q}) if q else "",
    }
    return render(request, "alokasi/portal/info_list.html", context)


def info_detail(request, slug):
    page = get_object_or_404(InfoPage, slug=slug, is_published=True)
    related = InfoPage.objects.filter(
        is_published=True, category=page.category
    ).exclude(pk=page.pk)[:5]
    return render(
        request, "alokasi/portal/info_detail.html", {"item": page, "related": related}
    )


def info_attachment(request, slug):
    page = get_object_or_404(InfoPage, slug=slug, is_published=True)
    return serve_file(page.attachment)


def verify_document(request, token=None):
    document = None
    form = VerifyCodeForm(request.GET or None)
    if token is None and form.is_valid():
        token = form.cleaned_data["code"]
    searched = token is not None
    if token is not None:
        document = (
            IssuedDocument.objects.select_related(
                "allocation", "allocation__plot", "application"
            )
            .filter(token=token)
            .first()
        )
    # Setelah peralihan hak, KPT/PPT (atau IPH) sebelumnya tetap terdaftar
    # tetapi tidak lagi menunjukkan pemegang hak yang berlaku.
    transfer = None
    if document is not None:
        transfer = (
            IssuedDocument.objects.filter(
                allocation=document.allocation,
                kind="iph",
                issued_at__gt=document.issued_at,
            )
            .order_by("-issued_at")
            .first()
        )
    return render(
        request,
        "alokasi/portal/verify.html",
        {
            "form": form,
            "document": document,
            "searched": searched,
            "transfer": transfer,
        },
        status=404 if searched and document is None else 200,
    )


# --------------------------------------------------------------------------
# Akun
# --------------------------------------------------------------------------


def _send_activation(request, user) -> None:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    url = _absolute_url(
        request,
        reverse("portal:activate", args=[uid, activation_token.make_token(user)]),
    )
    services.send_email(
        [user.email],
        _("Aktivasi akun portal alokasi lahan"),
        _(
            "Terima kasih telah mendaftar.\n\nAktifkan akun Anda melalui tautan berikut "
            "(berlaku 3 hari):\n%(url)s\n\nAbaikan surel ini bila Anda tidak mendaftar."
        )
        % {"url": url},
    )


def register(request):
    if request.user.is_authenticated and hasattr(request.user, "pemohon"):
        return redirect("portal:dashboard")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST":
        if _throttled(request, "register", limit=5, window=300):
            return _too_many(request)
        if form.is_valid():
            with transaction.atomic():
                email = form.cleaned_data["email"]
                user = User(
                    username=email,
                    email=email,
                    first_name=form.cleaned_data["pic_name"][:150],
                    is_active=False,
                )
                user.set_password(form.cleaned_data["password1"])
                user.save()
                applicant = form.save(commit=False)
                applicant.user = user
                applicant.save()
            _send_activation(request, user)
            return render(
                request, "alokasi/portal/register_done.html", {"email": user.email}
            )
    return render(request, "alokasi/portal/register.html", {"form": form})


def activate(request, uidb64, token):
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if (
        user is not None
        and hasattr(user, "pemohon")
        and activation_token.check_token(user, token)
    ):
        user.is_active = True
        user.save(update_fields=["is_active"])
        messages.success(request, _("Akun berhasil diaktifkan. Silakan masuk."))
        return redirect("portal:login")
    return render(request, "alokasi/portal/activation_invalid.html", status=400)


def resend_activation(request):
    form = ResendActivationForm(request.POST or None)
    if request.method == "POST":
        if _throttled(request, "resend", limit=3, window=300):
            return _too_many(request)
        if form.is_valid():
            user = User.objects.filter(
                email__iexact=form.cleaned_data["email"],
                is_active=False,
                pemohon__isnull=False,
            ).first()
            if user:
                _send_activation(request, user)
            # Jawaban sama untuk surel terdaftar maupun tidak (cegah enumerasi akun).
            return render(
                request,
                "alokasi/portal/register_done.html",
                {"email": form.cleaned_data["email"]},
            )
    return render(request, "alokasi/portal/resend_activation.html", {"form": form})


class PortalLoginView(auth_views.LoginView):
    template_name = "alokasi/portal/login.html"
    authentication_form = PortalLoginForm
    redirect_authenticated_user = False

    def post(self, request, *args, **kwargs):
        if _throttled(request, "login", limit=10, window=60):
            return _too_many(request)
        return super().post(request, *args, **kwargs)

    def get_default_redirect_url(self):
        return reverse("portal:dashboard")


def logout_view(request):
    from django.contrib.auth import logout

    if request.method != "POST":
        # Keluar hanya lewat formulir (CSRF). Alamat yang diketik langsung
        # diarahkan kembali, bukan halaman 405 kosong.
        return redirect("portal:home")
    logout(request)
    messages.info(request, _("Anda sudah keluar."))
    return redirect("portal:home")


class ApplicantPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        return (user for user in super().get_users(email) if hasattr(user, "pemohon"))


class PortalPasswordResetView(auth_views.PasswordResetView):
    form_class = ApplicantPasswordResetForm
    template_name = "alokasi/portal/password_reset.html"
    email_template_name = "alokasi/portal/email/password_reset.txt"
    subject_template_name = "alokasi/portal/email/password_reset_subject.txt"
    success_url = reverse_lazy("portal:password_reset_done")

    def form_valid(self, form):
        self.extra_email_context = {
            "site_base": (getattr(settings, "OFFICER_UI_URL", "") or "").rstrip("/")
        }
        return super().form_valid(form)

    def post(self, request, *args, **kwargs):
        if _throttled(request, "reset", limit=5, window=300):
            return _too_many(request)
        return super().post(request, *args, **kwargs)


class PortalPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "alokasi/portal/password_reset_done.html"


class PortalPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "alokasi/portal/password_reset_confirm.html"
    success_url = reverse_lazy("portal:password_reset_complete")


class PortalPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "alokasi/portal/password_reset_complete.html"


class PortalPasswordChangeView(auth_views.PasswordChangeView):
    template_name = "alokasi/portal/password_change.html"
    success_url = reverse_lazy("portal:dashboard")

    def form_valid(self, form):
        messages.success(self.request, _("Kata sandi berhasil diubah."))
        return super().form_valid(form)


password_change = applicant_required(PortalPasswordChangeView.as_view())


# --------------------------------------------------------------------------
# Dasbor pemohon
# --------------------------------------------------------------------------


def _report_due(allocation: Allocation, config: AllocationSettings) -> bool:
    if allocation.status != enums.AllocationStatus.ACTIVE:
        return False
    last = allocation.last_report_date or allocation.start_date
    return timezone.localdate() >= report_deadline(last, config.report_interval_months)


@applicant_required
def dashboard(request):
    applicant = request.applicant
    config = AllocationSettings.load()
    allocations = list(
        applicant.allocations.select_related("plot").order_by("-issued_date")
    )
    for allocation in allocations:
        allocation.report_due = _report_due(allocation, config)
    context = {
        "applicant": applicant,
        "applications": applicant.applications.select_related(
            "plot", "source_allocation"
        )[:50],
        "incoming_transfers": applicant.incoming_transfers.exclude(
            status=S.DRAFT
        ).select_related("source_allocation"),
        "allocations": allocations,
        "open_invoices": Invoice.objects.filter(
            application__applicant=applicant,
            status__in=(enums.InvoiceStatus.UNPAID, enums.InvoiceStatus.PROOF_UPLOADED),
        ).select_related("application"),
        "config": config,
    }
    return render(request, "alokasi/portal/dashboard.html", context)


@applicant_required
def profile(request):
    form = ApplicantProfileForm(request.POST or None, instance=request.applicant)
    if request.method == "POST" and form.is_valid():
        applicant = form.save()
        user = applicant.user
        user.first_name = applicant.pic_name[:150]
        user.save(update_fields=["first_name"])
        messages.success(request, _("Profil disimpan."))
        return redirect("portal:dashboard")
    return render(request, "alokasi/portal/profile.html", {"form": form})


# --------------------------------------------------------------------------
# Permohonan
# --------------------------------------------------------------------------


def _own_application(request, number, *, allow_recipient=False) -> Application:
    application = get_object_or_404(
        Application.objects.select_related(
            "plot", "applicant", "recipient", "source_allocation"
        ),
        number=number,
    )
    applicant = request.applicant
    if application.applicant_id == applicant.pk:
        return application
    if (
        allow_recipient
        and application.recipient_id == applicant.pk
        and application.status != S.DRAFT
    ):
        return application
    raise Http404


@applicant_required
@require_POST
def application_create(request, code):
    plot = get_object_or_404(LandPlot, code=code, is_published=True)
    try:
        application = services.create_allocation_application(request.applicant, plot)
    except ValidationError as error:
        for message in _form_errors(error):
            messages.error(request, message)
        return redirect("portal:plot_detail", code=code)
    messages.success(
        request, _("Draf permohonan dibuat. Lengkapi data dan dokumen, lalu ajukan.")
    )
    return redirect("portal:application_detail", number=application.number)


@applicant_required
def application_detail(request, number):
    application = _own_application(request, number, allow_recipient=True)
    is_owner = application.applicant_id == request.applicant.pk
    upload_form = None
    if is_owner and application.is_editable:
        upload_form = DocumentUploadForm(application=application)
    invoices = list(application.invoices.all())
    context = {
        "application": application,
        "is_owner": is_owner,
        # Penerima hak hanya melihat ringkasan peralihan: dokumen persyaratan,
        # tagihan, dan catatan petugas milik pemegang hak tidak ditampilkan.
        "documents": (
            application.documents.select_related("doc_type") if is_owner else []
        ),
        "required_docs": RequirementDocType.for_application(application),
        "missing": (
            application.missing_required_documents() if application.is_editable else []
        ),
        "events": application.events.all(),
        "invoices": invoices if is_owner else [],
        "transfer_in_review": application.is_transfer
        and application.status in (S.SUBMITTED, S.VERIFYING),
        "can_accept": not is_owner
        and application.status in (S.SUBMITTED, S.VERIFYING)
        and application.recipient_accepted_at is None,
        "proof_forms": {
            invoice.pk: PaymentProofForm()
            for invoice in invoices
            if is_owner
            and invoice.status
            in (enums.InvoiceStatus.UNPAID, enums.InvoiceStatus.PROOF_UPLOADED)
        },
        "issued": application.issued_documents.all(),
        "upload_form": upload_form,
        "submission_errors": (
            services.validate_for_submission(application)
            if is_owner and application.is_editable
            else []
        ),
        "can_cancel": is_owner
        and application.status in (S.DRAFT, S.SUBMITTED, S.REVISION),
        "config": AllocationSettings.load(),
    }
    return render(request, "alokasi/portal/application_detail.html", context)


@applicant_required
def application_edit(request, number):
    application = _own_application(request, number)
    if not application.is_editable:
        messages.error(request, _("Permohonan ini tidak dapat diubah lagi."))
        return redirect("portal:application_detail", number=number)
    if application.is_allocation:
        form_class = AllocationApplicationForm
    elif application.is_transfer:
        form_class = TransferEditForm
    else:
        # Perpanjangan, pembaruan, pecah PL, pengukuran ulang: hanya uraian.
        form_class = ServiceReasonEditForm
    form = form_class(request.POST or None, instance=application)
    if request.method == "POST" and form.is_valid():
        if application.is_transfer and form.recipient.pk == request.applicant.pk:
            form.add_error(
                "recipient_email", _("Penerima hak tidak boleh pemohon sendiri.")
            )
        else:
            form.save()
            messages.success(request, _("Data permohonan disimpan."))
            return redirect("portal:application_detail", number=number)
    return render(
        request,
        "alokasi/portal/application_edit.html",
        {"application": application, "form": form},
    )


@applicant_required
@require_POST
def document_upload(request, number):
    application = _own_application(request, number)
    if not application.is_editable:
        messages.error(
            request, _("Dokumen hanya dapat diunggah pada draf atau saat perbaikan.")
        )
        return redirect("portal:application_detail", number=number)
    form = DocumentUploadForm(request.POST, request.FILES, application=application)
    if form.is_valid():
        form.save()
        messages.success(request, _("Dokumen diunggah."))
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
    return redirect(f"{reverse('portal:application_detail', args=[number])}#dokumen")


@applicant_required
@require_POST
def document_delete(request, number, pk):
    application = _own_application(request, number)
    document = get_object_or_404(ApplicationDocument, pk=pk, application=application)
    if not application.is_editable:
        messages.error(request, _("Dokumen tidak dapat dihapus pada tahap ini."))
    else:
        document.file.delete(save=False)
        document.delete()
        messages.success(request, _("Dokumen dihapus."))
    return redirect(f"{reverse('portal:application_detail', args=[number])}#dokumen")


@applicant_required
def document_download(request, number, pk):
    application = _own_application(request, number)
    document = get_object_or_404(ApplicationDocument, pk=pk, application=application)
    return serve_file(document.file, filename=document.original_name or None)


@applicant_required
@require_POST
def application_submit(request, number):
    application = _own_application(request, number)
    try:
        services.submit(application, request.user)
    except ValidationError as error:
        for message in _form_errors(error):
            messages.error(request, message)
    else:
        messages.success(
            request, _("Permohonan diajukan. Status akan dikabarkan melalui surel.")
        )
    return redirect("portal:application_detail", number=number)


@applicant_required
@require_POST
def application_accept_transfer(request, number):
    application = _own_application(request, number, allow_recipient=True)
    try:
        services.accept_transfer(application, request.applicant, request.user)
    except ValidationError as error:
        for message in _form_errors(error):
            messages.error(request, message)
    else:
        messages.success(
            request, _("Terima kasih. Persetujuan Anda atas peralihan ini tercatat.")
        )
    return redirect("portal:application_detail", number=number)


@applicant_required
@require_POST
def application_cancel(request, number):
    application = _own_application(request, number)
    try:
        services.cancel(
            application, request.user, note=request.POST.get("note", "").strip()
        )
    except ValidationError as error:
        for message in _form_errors(error):
            messages.error(request, message)
    else:
        messages.success(request, _("Permohonan dibatalkan."))
    return redirect("portal:application_detail", number=number)


# --------------------------------------------------------------------------
# Tagihan
# --------------------------------------------------------------------------


def _own_invoice(request, number) -> Invoice:
    return get_object_or_404(
        Invoice.objects.select_related("application", "application__applicant"),
        number=number,
        application__applicant=request.applicant,
    )


@applicant_required
def invoice_pdf(request, number):
    invoice = _own_invoice(request, number)
    pdf = documents.invoice_pdf(invoice)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="tagihan-{invoice.number}.pdf"'
    )
    response["Cache-Control"] = "private, no-store"
    return response


@applicant_required
@require_POST
def invoice_proof_upload(request, number):
    invoice = _own_invoice(request, number)
    form = PaymentProofForm(request.POST, request.FILES, instance=invoice)
    if form.is_valid():
        try:
            services.upload_payment_proof(
                invoice, form.cleaned_data["payment_proof"], request.user
            )
        except ValidationError as error:
            for message in _form_errors(error):
                messages.error(request, message)
        else:
            messages.success(
                request, _("Bukti bayar diunggah dan menunggu verifikasi petugas.")
            )
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
    return redirect(
        f"{reverse('portal:application_detail', args=[invoice.application.number])}#tagihan"
    )


@applicant_required
def invoice_proof(request, number):
    invoice = _own_invoice(request, number)
    return serve_file(invoice.payment_proof)


# --------------------------------------------------------------------------
# Dokumen terbit
# --------------------------------------------------------------------------


@applicant_required
def issued_download(request, token):
    document = get_object_or_404(
        IssuedDocument.objects.select_related("application", "allocation"), token=token
    )
    me = request.applicant.pk
    allowed = {
        document.application.applicant_id,
        document.allocation.holder_id,
        document.application.recipient_id,
    }
    if me not in allowed:
        raise Http404
    return serve_file(
        document.file, filename=f"{document.kind.upper()}-{document.number}.pdf"
    )


# --------------------------------------------------------------------------
# Alokasi, pelaporan, peralihan hak
# --------------------------------------------------------------------------


def _own_allocation(request, pk) -> Allocation:
    return get_object_or_404(
        Allocation.objects.select_related("plot", "application", "holder"),
        pk=pk,
        holder=request.applicant,
    )


@applicant_required
def allocation_detail(request, pk):
    return _render_allocation(request, _own_allocation(request, pk))


def _render_allocation(request, allocation, *, permit_form=None, development_form=None):
    config = AllocationSettings.load()
    reports = {r.permit_type: r for r in allocation.permit_reports.all()}
    permit_rows = [
        (value, label, reports.get(value)) for value, label in enums.PermitType.choices
    ]
    is_active = allocation.status == enums.AllocationStatus.ACTIVE
    open_transfer = allocation.transfer_applications.exclude(
        status__in=enums.FINAL_STATUSES
    ).first()
    today = timezone.localdate()
    context = {
        "allocation": allocation,
        "plot": allocation.plot,
        "config": config,
        "geometry": (
            allocation.plot.geometry.geojson if allocation.plot.geometry else ""
        ),
        "issued": allocation.issued_documents.all(),
        "permit_rows": permit_rows,
        "development_reports": allocation.development_reports.all(),
        "permit_form": (
            (permit_form or PermitReportForm(prefix="izin")) if is_active else None
        ),
        "development_form": (
            (
                development_form
                or DevelopmentReportForm(
                    prefix="progres", initial={"report_date": today}
                )
            )
            if is_active
            else None
        ),
        "is_active": is_active,
        "is_idle": allocation.is_idle,
        "has_started": allocation.has_started_development,
        "idle_days_left": (allocation.idle_deadline - today).days,
        "report_due": _report_due(allocation, config),
        "open_transfer": open_transfer,
    }
    return render(request, "alokasi/portal/allocation_detail.html", context)


@applicant_required
@require_POST
def permit_report_save(request, pk):
    allocation = _own_allocation(request, pk)
    if allocation.status != enums.AllocationStatus.ACTIVE:
        raise PermissionDenied
    permit_type = request.POST.get("izin-permit_type", "")
    instance = PermitReport.objects.filter(
        allocation=allocation, permit_type=permit_type
    ).first()
    old_document = instance.document.name if instance and instance.document else ""
    form = PermitReportForm(
        request.POST, request.FILES, prefix="izin", instance=instance
    )
    form.instance.allocation = allocation
    if form.is_valid():
        report = form.save()
        if old_document and report.document.name != old_document:
            report.document.storage.delete(old_document)
        messages.success(request, _("Laporan perizinan disimpan."))
    else:
        # Tampilkan ulang formulir beserta isian dan pesan galat per kolom.
        return _render_allocation(request, allocation, permit_form=form)
    return redirect(f"{reverse('portal:allocation_detail', args=[pk])}#perizinan")


@applicant_required
def permit_document(request, pk, report_pk):
    allocation = _own_allocation(request, pk)
    report = get_object_or_404(PermitReport, pk=report_pk, allocation=allocation)
    return serve_file(report.document)


@applicant_required
@require_POST
def development_report_create(request, pk):
    allocation = _own_allocation(request, pk)
    if allocation.status != enums.AllocationStatus.ACTIVE:
        raise PermissionDenied
    form = DevelopmentReportForm(request.POST, request.FILES, prefix="progres")
    if form.is_valid():
        report = form.save(commit=False)
        report.allocation = allocation
        report.reported_by = request.user
        report.save()
        messages.success(request, _("Laporan progres pembangunan disimpan."))
    else:
        return _render_allocation(request, allocation, development_form=form)
    return redirect(f"{reverse('portal:allocation_detail', args=[pk])}#pembangunan")


@applicant_required
def development_attachment(request, pk, report_pk):
    allocation = _own_allocation(request, pk)
    report = get_object_or_404(DevelopmentReport, pk=report_pk, allocation=allocation)
    return serve_file(report.photo)


@applicant_required
def transfer_create(request, pk):
    allocation = _own_allocation(request, pk)
    form = TransferApplicationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            application = services.create_transfer_application(
                request.applicant,
                allocation,
                form.recipient,
                form.cleaned_data["transfer_reason"],
            )
        except ValidationError as error:
            for message in _form_errors(error):
                form.add_error(None, message)
        else:
            messages.success(
                request,
                _("Draf permohonan peralihan hak dibuat. Unggah dokumen lalu ajukan."),
            )
            return redirect("portal:application_detail", number=application.number)
    return render(
        request,
        "alokasi/portal/transfer_form.html",
        {"allocation": allocation, "form": form},
    )


@applicant_required
def service_create(request, pk):
    """Ajukan layanan atas alokasi sendiri: perpanjangan, pembaruan, pecah
    PL, atau pengukuran ulang (alur permohonan sama dengan peralihan)."""
    allocation = _own_allocation(request, pk)
    form = ServiceApplicationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            application = services.create_service_application(
                request.applicant,
                allocation,
                form.cleaned_data["service_type"],
                form.cleaned_data["reason"],
            )
        except ValidationError as error:
            for message in _form_errors(error):
                form.add_error(None, message)
        else:
            messages.success(
                request,
                _("Draf permohonan %s dibuat. Unggah dokumen lalu ajukan.")
                % application.get_service_type_display(),
            )
            return redirect("portal:application_detail", number=application.number)
    return render(
        request,
        "alokasi/portal/service_form.html",
        {"allocation": allocation, "form": form},
    )
