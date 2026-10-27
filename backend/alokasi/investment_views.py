"""Portal investasi (/portal/investasi/): peta peluang, kawasan, perbandingan,
profil lahan, dan permintaan investasi/penggunaan lahan oleh investor."""

import json

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Prefetch, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from alokasi import documents, enums
from alokasi import investment_services as inv
from alokasi.investment_forms import (
    CancelRequestForm,
    DeclineOfferForm,
    InvestmentMessageForm,
    InvestmentRequestForm,
    available_plots,
)
from alokasi.models import (
    AllocationSettings,
    InfoPage,
    InvestmentRequest,
    InvestmentSector,
    InvestmentZone,
    LandPlot,
    SavedPlot,
)
from alokasi.views import (
    _form_errors,
    _throttled,
    _too_many,
    applicant_required,
    serve_file,
)

MAX_COMPARE = 4


def _map_context() -> dict:
    return {
        "map_center": [settings.MAP_CENTER_LAT, settings.MAP_CENTER_LNG],
        "map_zoom": settings.MAP_DEFAULT_ZOOM,
    }


def _current_applicant(request):
    if not request.user.is_authenticated:
        return None
    return getattr(request.user, "pemohon", None)


def _saved_codes(request) -> list[str]:
    applicant = _current_applicant(request)
    if applicant is None:
        return []
    return list(applicant.saved_plots.values_list("plot__code", flat=True))


def _public_plots():
    return (
        LandPlot.objects.filter(is_published=True)
        .exclude(status=enums.PlotStatus.CLOSED)
        .select_related("sector", "zone")
    )


def _investable(plots):
    return plots.filter(status=enums.PlotStatus.AVAILABLE).filter(
        Q(offer_allocation=True) | Q(offer_lease=True)
    )


# --------------------------------------------------------------------------
# Halaman publik
# --------------------------------------------------------------------------


def investment_home(request):
    plots = _investable(_public_plots())
    stats = plots.aggregate(total=Count("pk"), area=Sum("area_m2"))
    sector_counts = dict(
        plots.exclude(sector=None).values_list("sector").annotate(n=Count("pk"))
    )
    sectors = [
        (sector, sector_counts.get(sector.pk, 0))
        for sector in InvestmentSector.objects.filter(is_active=True)
    ]
    zones = (
        InvestmentZone.objects.filter(is_published=True)
        .annotate(
            plot_count=Count(
                "plots",
                filter=Q(
                    plots__is_published=True,
                    plots__status=enums.PlotStatus.AVAILABLE,
                ),
            )
        )
        .prefetch_related("sectors")
    )
    featured_zones = [z for z in zones if z.is_featured] or list(zones[:3])
    featured_plots = list(plots.filter(is_featured=True)[:6]) or list(
        plots.order_by("-created_at")[:6]
    )
    config = AllocationSettings.load()
    context = {
        "stats": stats,
        "lease_count": plots.filter(offer_lease=True).count(),
        "zone_count": len(zones),
        "sectors": sectors,
        "zones": featured_zones[:6],
        "featured_plots": featured_plots,
        "guides": InfoPage.objects.filter(
            is_published=True, category=enums.InfoCategory.INVESTMENT
        )[:8],
        "config": config,
        "contact": config.investment_contact or config.contact_info,
        "saved_codes": _saved_codes(request),
    }
    return render(request, "alokasi/portal/investasi/home.html", context)


def investment_map(request):
    plots = _public_plots()
    context = {
        "sectors": InvestmentSector.objects.filter(is_active=True),
        "zones": InvestmentZone.objects.filter(is_published=True),
        "districts": plots.exclude(district="")
        .values_list("district", flat=True)
        .distinct()
        .order_by("district"),
        "data_url": reverse("portal:investment_data"),
        "saved_codes": _saved_codes(request),
        "is_applicant": _current_applicant(request) is not None,
        **_map_context(),
    }
    return render(request, "alokasi/portal/investasi/map.html", context)


def _plot_feature(plot: LandPlot) -> dict:
    sector = plot.sector
    return {
        "type": "Feature",
        "geometry": json.loads(plot.geometry.geojson) if plot.geometry else None,
        "properties": {
            "code": plot.code,
            "name": plot.name,
            "status": plot.status,
            "status_label": plot.get_status_display(),
            "available": plot.is_available,
            "sector": sector.slug if sector and sector.is_active else "",
            "sector_name": sector.name if sector and sector.is_active else "",
            "sector_icon": sector.icon if sector and sector.is_active else "",
            "color": sector.color if sector and sector.is_active else "#64748b",
            "zone": plot.zone.slug if plot.zone and plot.zone.is_published else "",
            "zone_name": plot.zone.name if plot.zone and plot.zone.is_published else "",
            "district": plot.district,
            "village": plot.village,
            "area_m2": str(plot.area_m2),
            "intended_use": plot.intended_use,
            "zoning": plot.zoning,
            "lease": plot.offer_lease,
            "allocation": plot.offer_allocation,
            "lease_rate": str(plot.lease_rate_per_m2_year) if plot.offer_lease else "",
            "lease_min_years": plot.lease_min_years,
            "uwt_rate": (
                str(plot.uwt_rate_per_m2_year) if plot.offer_allocation else ""
            ),
            "uwt_total": str(plot.uwt_total) if plot.offer_allocation else "",
            "term_years": plot.effective_term_years,
            "ready": plot.land_preparation_done,
            "docs": plot.has_technical_documents,
            "featured": plot.is_featured,
            "utilities": plot.utilities,
            "url": reverse("portal:plot_detail", args=[plot.code]),
            "photo": (
                reverse("portal:plot_photo", args=[plot.code]) if plot.photo else ""
            ),
        },
    }


def investment_data(request):
    """Data peta investasi: semua lahan terbit (kecuali ditutup) + batas kawasan.

    Penyaringan dilakukan di peramban agar filter terasa instan; angka dikirim
    sebagai teks supaya nominal besar tidak kehilangan presisi."""
    plots = [_plot_feature(plot) for plot in _public_plots().order_by("code")]
    zones = []
    for zone in InvestmentZone.objects.filter(
        is_published=True, geometry__isnull=False
    ):
        zones.append(
            {
                "type": "Feature",
                "geometry": json.loads(zone.geometry.geojson),
                "properties": {
                    "slug": zone.slug,
                    "name": zone.name,
                    "summary": zone.summary,
                    "url": reverse("portal:investment_zone", args=[zone.slug]),
                },
            }
        )
    response = JsonResponse(
        {
            "plots": {"type": "FeatureCollection", "features": plots},
            "zones": {"type": "FeatureCollection", "features": zones},
        },
        json_dumps_params={"ensure_ascii": False},
    )
    response["Cache-Control"] = "public, max-age=60"
    return response


def zone_detail(request, slug):
    zone = get_object_or_404(
        InvestmentZone.objects.prefetch_related("sectors"), slug=slug, is_published=True
    )
    plots = _public_plots().filter(zone=zone).order_by("code")
    available = _investable(plots)
    context = {
        "zone": zone,
        "plots": plots,
        "stats": available.aggregate(total=Count("pk"), area=Sum("area_m2")),
        "geometry": zone.geometry.geojson if zone.geometry else "",
        "saved_codes": _saved_codes(request),
        **_map_context(),
    }
    return render(request, "alokasi/portal/investasi/zone.html", context)


def zone_photo(request, slug):
    zone = get_object_or_404(InvestmentZone, slug=slug, is_published=True)
    return serve_file(zone.photo, inline=True)


def compare(request):
    codes = []
    for code in request.GET.get("lahan", "").split(","):
        code = code.strip()
        if code and code not in codes:
            codes.append(code)
    codes = codes[:MAX_COMPARE]
    found = {p.code: p for p in _public_plots().filter(code__in=codes)}
    plots = [found[c] for c in codes if c in found]
    return render(
        request,
        "alokasi/portal/investasi/compare.html",
        {
            "plots": plots,
            "max_compare": MAX_COMPARE,
            "config": AllocationSettings.load(),
        },
    )


def plot_profile_pdf(request, code):
    plot = get_object_or_404(
        LandPlot.objects.select_related("sector", "zone"),
        code=code,
        is_published=True,
    )
    from alokasi.services import portal_url

    url = portal_url(f"lahan/{plot.code}/")
    context = {
        "plot": plot,
        "config": AllocationSettings.load(),
        "qr": documents.qr_data_uri(url),
        "url": url,
    }
    try:
        pdf = documents.render_pdf("alokasi/pdf/profil_lahan.html", context)
    except documents.PdfError:
        return HttpResponse(_("Profil lahan tidak dapat dibuat."), status=500)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="profil-{plot.code}.pdf"'
    return response


# --------------------------------------------------------------------------
# Investor (akun pemohon)
# --------------------------------------------------------------------------


def _own_request(request, number) -> InvestmentRequest:
    return get_object_or_404(
        InvestmentRequest.objects.select_related(
            "sector", "zone", "offer_plot", "application"
        ),
        number=number,
        applicant=request.applicant,
    )


def _initial_from_query(params) -> dict:
    """Isi awal formulir minat dari tautan peta/kartu lahan/kawasan."""
    initial = {}
    codes = [c for c in params.get("lahan", "").split(",") if c.strip()]
    if codes:
        chosen = list(available_plots().filter(code__in=codes[:10]))
        initial["plots"] = chosen
        sectors = {p.sector_id for p in chosen if p.sector_id}
        if len(sectors) == 1:
            initial["sector"] = sectors.pop()
        zones = {p.zone_id for p in chosen if p.zone_id}
        if len(zones) == 1:
            initial["zone"] = zones.pop()
        schemes = {s for p in chosen for s, _label in p.schemes}
        if len(schemes) == 1:
            initial["scheme"] = schemes.pop()
    zone = InvestmentZone.objects.filter(
        slug=params.get("kawasan") or None, is_published=True
    ).first()
    if zone:
        initial["zone"] = zone.pk
    if params.get("skema") in enums.InvestmentScheme.values:
        initial["scheme"] = params["skema"]
    sector = InvestmentSector.objects.filter(
        slug=params.get("sektor") or None, is_active=True
    ).first()
    if sector:
        initial["sector"] = sector.pk
    return initial


@applicant_required
def request_create(request):
    initial = _initial_from_query(request.GET)
    form = InvestmentRequestForm(
        request.POST or None, request.FILES or None, initial=initial
    )
    if request.method == "POST":
        if _throttled(request, "investasi-ajukan", limit=10, window=3600):
            return _too_many(request)
        if form.is_valid():
            investment = inv.submit_request(request.applicant, form)
            messages.success(
                request,
                _(
                    "Permintaan investasi %s terkirim. Petugas akan meninjau dan "
                    "menghubungi Anda lewat portal dan surel."
                )
                % investment.number,
            )
            return redirect("portal:investment_request", number=investment.number)
    plots = form.fields["plots"].queryset
    selected = {str(value) for value in (form["plots"].value() or [])}
    options = [
        {
            "pk": p.pk,
            "selected": str(p.pk) in selected,
            "code": p.code,
            "name": p.name,
            "area_m2": p.area_m2,
            "sector": p.sector.name if p.sector else "",
            "schemes": [label for _value, label in p.schemes],
        }
        for p in plots
    ]
    # Lahan yang sudah dipilih tampil paling atas.
    options.sort(key=lambda option: not option["selected"])
    context = {"form": form, "plot_options": options, **_map_context()}
    return render(request, "alokasi/portal/investasi/request_form.html", context)


@applicant_required
def request_list(request):
    requests = request.applicant.investment_requests.select_related(
        "sector", "offer_plot"
    ).prefetch_related("plots")
    return render(
        request,
        "alokasi/portal/investasi/request_list.html",
        {"requests": requests},
    )


@applicant_required
def request_detail(request, number):
    investment = _own_request(request, number)
    form = InvestmentMessageForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if _throttled(request, "investasi-pesan", limit=30, window=600):
            return _too_many(request)
        if form.is_valid():
            try:
                inv.post_message(
                    investment,
                    request.user,
                    form.cleaned_data["body"],
                    form.cleaned_data.get("attachment"),
                    officer=False,
                )
            except ValidationError as error:
                for message in _form_errors(error):
                    messages.error(request, message)
            else:
                messages.success(request, _("Pesan terkirim ke petugas."))
                return redirect(
                    reverse("portal:investment_request", args=[number]) + "#pesan"
                )
    context = {
        "investment": investment,
        "plots": investment.plots.select_related("sector"),
        "events": investment.events.all(),
        "thread": investment.messages.all(),
        "form": form,
        "decline_form": DeclineOfferForm(),
        "cancel_form": CancelRequestForm(),
        "area_geojson": (
            investment.requested_area.geojson if investment.requested_area else ""
        ),
        "can_cancel": not investment.is_final
        and investment.status != enums.InvestmentStatus.ACCEPTED,
    }
    return render(request, "alokasi/portal/investasi/request_detail.html", context)


def _run(request, func, success: str) -> None:
    try:
        func()
    except ValidationError as error:
        for message in _form_errors(error):
            messages.error(request, message)
    else:
        messages.success(request, success)


@applicant_required
@require_POST
def request_accept(request, number):
    investment = _own_request(request, number)
    _run(
        request,
        lambda: inv.accept_offer(investment, request.user),
        _("Penawaran diterima. Petugas akan meneruskan ke tahap berikutnya."),
    )
    return redirect("portal:investment_request", number=number)


@applicant_required
@require_POST
def request_decline(request, number):
    investment = _own_request(request, number)
    form = DeclineOfferForm(request.POST)
    if not form.is_valid():
        messages.error(request, _("Sebutkan alasan atau penyesuaian yang diinginkan."))
        return redirect("portal:investment_request", number=number)
    _run(
        request,
        lambda: inv.decline_offer(
            investment, request.user, form.cleaned_data["reason"]
        ),
        _("Penawaran ditolak. Petugas akan meninjau kembali permintaan Anda."),
    )
    return redirect("portal:investment_request", number=number)


@applicant_required
@require_POST
def request_cancel(request, number):
    investment = _own_request(request, number)
    form = CancelRequestForm(request.POST)
    note = form.cleaned_data["note"] if form.is_valid() else ""
    _run(
        request,
        lambda: inv.cancel(investment, request.user, note),
        _("Permintaan investasi dibatalkan."),
    )
    return redirect("portal:investment_request", number=number)


@applicant_required
def request_attachment(request, number):
    investment = _own_request(request, number)
    return serve_file(
        investment.attachment, filename=investment.attachment_name or None
    )


@applicant_required
def message_attachment(request, number, pk):
    investment = _own_request(request, number)
    message = get_object_or_404(investment.messages, pk=pk)
    return serve_file(message.attachment, filename=message.attachment_name or None)


@applicant_required
@require_POST
def save_toggle(request, code):
    plot = get_object_or_404(LandPlot, code=code, is_published=True)
    saved, created = SavedPlot.objects.get_or_create(
        applicant=request.applicant, plot=plot
    )
    if not created:
        saved.delete()
    is_saved = created
    if request.headers.get("x-requested-with") == "fetch":
        return JsonResponse({"saved": is_saved, "code": plot.code})
    messages.success(
        request,
        (
            _("Lahan %s disimpan.") % plot.code
            if is_saved
            else _("Lahan %s dihapus dari daftar simpan.") % plot.code
        ),
    )
    target = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        target = reverse("portal:plot_detail", args=[plot.code])
    return redirect(target)


@applicant_required
def saved_list(request):
    saved = request.applicant.saved_plots.select_related(
        "plot", "plot__sector", "plot__zone"
    ).filter(plot__is_published=True)
    return render(
        request,
        "alokasi/portal/investasi/saved.html",
        {"saved": saved, "saved_codes": [item.plot.code for item in saved]},
    )


def investment_summary(applicant):
    """Ringkasan untuk dasbor akun pemohon."""
    requests = list(
        applicant.investment_requests.select_related("sector").prefetch_related(
            Prefetch("plots", queryset=LandPlot.objects.only("code"))
        )[:20]
    )
    return {
        "investment_requests": requests,
        "pending_offers": [
            r for r in requests if r.status == enums.InvestmentStatus.OFFERED
        ],
        "saved_plots": list(
            applicant.saved_plots.select_related("plot", "plot__sector").filter(
                plot__is_published=True
            )[:12]
        ),
    }
