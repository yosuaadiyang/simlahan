"""Unduhan berkas privat untuk petugas (berkas tidak punya URL publik)."""

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.html import format_html

from alokasi.models import (
    ApplicationDocument,
    DevelopmentReport,
    InfoPage,
    Invoice,
    IssuedDocument,
    LandPlot,
    PermitReport,
)

FILE_KINDS = {
    "dokumen": (ApplicationDocument, "file"),
    "bukti": (Invoice, "payment_proof"),
    "terbit": (IssuedDocument, "file"),
    "izin": (PermitReport, "document"),
    "progres": (DevelopmentReport, "photo"),
    "lahan": (LandPlot, "photo"),
    "informasi": (InfoPage, "attachment"),
}


def file_url(kind: str, obj) -> str:
    return reverse("alokasi-officer-file", args=[kind, obj.pk])


def file_link(kind: str, obj, label: str = "") -> str:
    _model, field = FILE_KINDS[kind]
    fieldfile = getattr(obj, field)
    if not fieldfile:
        return "–"
    return format_html(
        '<a href="{}" target="_blank" rel="noopener">{}</a>',
        file_url(kind, obj),
        label or fieldfile.name.rsplit("/", 1)[-1],
    )


@staff_member_required
def officer_file(request, kind, pk):
    from alokasi.views import serve_file

    if kind not in FILE_KINDS:
        raise Http404
    model, field = FILE_KINDS[kind]
    if not request.user.has_perm(f"alokasi.view_{model._meta.model_name}"):
        raise PermissionDenied
    obj = get_object_or_404(model, pk=pk)
    filename = getattr(obj, "original_name", "") or None
    inline = request.GET.get("lihat") == "1"
    return serve_file(getattr(obj, field), inline=inline, filename=filename)
