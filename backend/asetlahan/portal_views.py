"""Halaman portal publik modul aset lahan: pengaduan masyarakat dan lelang lahan."""

import hmac

from django.conf import settings
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from alokasi.templatetags.alokasi_tags import angka
from alokasi.views import _throttled, _too_many, applicant_required
from asetlahan import enums, services
from asetlahan.forms import BidForm, GrievanceCheckForm, GrievanceForm
from asetlahan.models import Bid, Grievance, ModuleSettings, Tender
from utils.group_permissions import UserGroup

SESSION_GRIEVANCE = "asetlahan_pengaduan_terakhir"
PUBLIC_TENDER_STATUSES = (
    enums.TenderStatus.ANNOUNCED,
    enums.TenderStatus.CLOSED,
    enums.TenderStatus.AWARDED,
    enums.TenderStatus.CANCELLED,
)


def _require_flag(flag: str) -> None:
    if not getattr(ModuleSettings.load(), flag):
        raise Http404


# --------------------------------------------------------------------------
# Pengaduan masyarakat
# --------------------------------------------------------------------------


def _check_url() -> str:
    return services.app_url(reverse("aset_portal:grievance_check"))


def _notify_new_grievance(grievance: Grievance) -> None:
    body = _(
        "Pengaduan Anda telah kami terima.\n\nNomor: %(number)s\nKode akses: %(code)s\nPerihal: %(subject)s\n"
        "Batas penyelesaian: %(due)s\n\nCek perkembangannya di %(url)s"
    ) % {
        "number": grievance.number,
        "code": grievance.access_code,
        "subject": grievance.subject,
        "due": grievance.due_date.strftime("%d-%m-%Y") if grievance.due_date else "-",
        "url": _check_url(),
    }
    services.notify_contact(
        email=grievance.email,
        phone=grievance.phone,
        subject=_("Pengaduan %s diterima") % grievance.number,
        body=body,
    )
    officers = services.group_emails(UserGroup.PETUGAS_ASET, UserGroup.PAAKAYTTAJA)
    services.send_email(
        officers,
        _("Pengaduan baru %s") % grievance.number,
        _(
            "Pengaduan baru dari %(name)s: %(subject)s\n\n%(description)s\n\nTangani di %(url)s"
        )
        % {
            "name": grievance.complainant_name,
            "subject": grievance.subject,
            "description": grievance.description,
            "url": services.admin_url(f"grievance/{grievance.pk}/change/"),
        },
    )


def notify_grievance_update(grievance: Grievance) -> bool:
    """Kabari pelapor saat status atau tanggapan pengaduan berubah."""
    body = _("Status pengaduan %(number)s: %(status)s.") % {
        "number": grievance.number,
        "status": grievance.get_status_display(),
    }
    if grievance.response:
        body += "\n\n" + _("Tanggapan petugas:") + "\n" + grievance.response
    body += "\n\n" + _("Cek perkembangannya di %s") % _check_url()
    return services.notify_contact(
        email=grievance.email,
        phone=grievance.phone,
        subject=_("Perkembangan pengaduan %s") % grievance.number,
        body=body,
    )


def grievance_create(request):
    _require_flag("enable_grievance")
    form = GrievanceForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if _throttled(request, "aset-pengaduan", limit=5, window=3600):
            return _too_many(request)
        if form.is_valid():
            grievance = form.save(commit=False)
            grievance.channel = enums.GrievanceChannel.PORTAL
            if grievance.location is not None:
                from asetlahan.geo import asset_at

                grievance.asset = asset_at(grievance.location)
                if grievance.asset is not None:
                    grievance.service_unit_id = grievance.asset.service_unit_id
            grievance.save()
            transaction.on_commit(lambda: _notify_new_grievance(grievance))
            request.session[SESSION_GRIEVANCE] = grievance.pk
            return redirect("aset_portal:grievance_done")
    return render(
        request,
        "asetlahan/portal/grievance_form.html",
        {
            "form": form,
            "map_center": [settings.MAP_CENTER_LAT, settings.MAP_CENTER_LNG],
            "map_zoom": settings.MAP_DEFAULT_ZOOM,
        },
    )


def grievance_done(request):
    _require_flag("enable_grievance")
    pk = request.session.get(SESSION_GRIEVANCE)
    grievance = Grievance.objects.filter(pk=pk).first() if pk else None
    if grievance is None:
        return redirect("aset_portal:grievance_create")
    return render(
        request, "asetlahan/portal/grievance_done.html", {"grievance": grievance}
    )


def grievance_check(request):
    _require_flag("enable_grievance")
    form = GrievanceCheckForm(request.GET or None)
    grievance = None
    searched = False
    if form.is_bound:
        if _throttled(request, "aset-cek-pengaduan", limit=20, window=600):
            return _too_many(request)
        if form.is_valid():
            searched = True
            found = Grievance.objects.filter(number=form.cleaned_data["number"]).first()
            if found and hmac.compare_digest(
                found.access_code, form.cleaned_data["access_code"]
            ):
                grievance = found
    return render(
        request,
        "asetlahan/portal/grievance_check.html",
        {"form": form, "grievance": grievance, "searched": searched},
    )


# --------------------------------------------------------------------------
# Lelang / seleksi lahan
# --------------------------------------------------------------------------


def _public_tender(number: str) -> Tender:
    return get_object_or_404(
        Tender.objects.select_related("asset", "alokasi_plot", "winner"),
        number=number,
        status__in=PUBLIC_TENDER_STATUSES,
    )


def tender_list(request):
    _require_flag("enable_tender")
    tenders = Tender.objects.filter(status__in=PUBLIC_TENDER_STATUSES).select_related(
        "asset", "alokasi_plot"
    )
    return render(request, "asetlahan/portal/tender_list.html", {"tenders": tenders})


def _own_bid(request, tender):
    applicant = (
        getattr(request.user, "pemohon", None)
        if request.user.is_authenticated
        else None
    )
    if applicant is None:
        return None
    return Bid.objects.filter(tender=tender, applicant=applicant).first()


def tender_detail(request, number):
    _require_flag("enable_tender")
    tender = _public_tender(number)
    return render(
        request,
        "asetlahan/portal/tender_detail.html",
        {
            "tender": tender,
            "own_bid": _own_bid(request, tender),
            "bid_count": tender.bids.exclude(
                status=enums.BidStatus.DISQUALIFIED
            ).count(),
        },
    )


@applicant_required
def bid_submit(request, number):
    _require_flag("enable_tender")
    tender = _public_tender(number)
    if not tender.is_accepting_bids:
        messages.error(request, _("Lelang ini tidak sedang menerima penawaran."))
        return redirect("aset_portal:tender_detail", number=number)
    applicant = request.applicant
    bid = Bid.objects.filter(tender=tender, applicant=applicant).first()
    initial = (
        {}
        if bid
        else {
            "bidder_name": applicant.name,
            "email": request.user.email,
            "phone": applicant.phone,
        }
    )
    form = BidForm(
        request.POST or None,
        request.FILES or None,
        instance=bid,
        initial=initial,
        tender=tender,
    )
    if request.method == "POST" and form.is_valid():
        new = form.instance.pk is None
        bid = form.save(commit=False)
        bid.tender = tender
        bid.applicant = applicant
        bid.status = enums.BidStatus.SUBMITTED
        try:
            with transaction.atomic():
                bid.save()
        except IntegrityError:
            messages.error(
                request, _("Anda sudah mengajukan penawaran untuk lelang ini.")
            )
            return redirect("aset_portal:tender_detail", number=number)
        services.notify_contact(
            email=bid.email,
            phone=bid.phone,
            subject=_("Penawaran %s diterima") % tender.number,
            body=_(
                "Penawaran Anda untuk %(title)s sebesar Rp %(amount)s telah %(action)s."
            )
            % {
                "title": tender.title,
                "amount": angka(bid.amount),
                "action": _("diterima") if new else _("diperbarui"),
            },
        )
        messages.success(
            request,
            _("Penawaran tersimpan. Anda dapat mengubahnya sampai lelang ditutup."),
        )
        return redirect("aset_portal:tender_detail", number=number)
    return render(
        request,
        "asetlahan/portal/bid_form.html",
        {"tender": tender, "form": form, "bid": bid},
    )
