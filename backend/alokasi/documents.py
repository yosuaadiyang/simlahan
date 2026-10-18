"""Pembuatan PDF: KPT, PPT, izin peralihan hak, dan tagihan.

PDF dirender dari templat HTML dengan xhtml2pdf. Setiap dokumen terbit memuat
kode QR menuju halaman verifikasi publik /portal/verifikasi/<kode>/.
"""

import base64
import io

import qrcode
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa

from alokasi.models import AllocationSettings, IssuedDocument

TEMPLATES = {
    "kpt": "alokasi/pdf/kpt.html",
    "ppt": "alokasi/pdf/ppt.html",
    "iph": "alokasi/pdf/iph.html",
}


class PdfError(RuntimeError):
    pass


def render_pdf(template: str, context: dict) -> bytes:
    html = render_to_string(template, context)
    output = io.BytesIO()
    result = pisa.CreatePDF(html, dest=output, encoding="utf-8")
    if result.err:
        raise PdfError(f"Gagal membuat PDF dari {template}")
    return output.getvalue()


def qr_data_uri(text: str) -> str:
    image = qrcode.make(text, box_size=4, border=2)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def verification_url(token) -> str:
    from alokasi.services import portal_url

    return portal_url(f"verifikasi/{token}/")


def issue(
    application, allocation, kind: str, number: str, previous_holder=None
) -> IssuedDocument:
    holder = allocation.holder
    document = IssuedDocument(
        kind=kind,
        number=number,
        application=application,
        allocation=allocation,
        holder_name=holder.name,
        issued_at=timezone.now(),
    )
    url = verification_url(document.token)
    context = {
        "doc": document,
        "application": application,
        "allocation": allocation,
        "plot": allocation.plot,
        "holder": holder,
        "previous_holder": previous_holder,
        "config": AllocationSettings.load(),
        "verification_url": url,
        "qr": qr_data_uri(url),
        "today": timezone.localdate(),
    }
    pdf = render_pdf(TEMPLATES[kind], context)
    document.file.save(f"{kind}-{number}.pdf", ContentFile(pdf), save=False)
    document.save()
    return document


def invoice_pdf(invoice) -> bytes:
    return render_pdf(
        "alokasi/pdf/invoice.html",
        {
            "invoice": invoice,
            "application": invoice.application,
            "applicant": invoice.application.applicant,
            "config": AllocationSettings.load(),
            "today": timezone.localdate(),
        },
    )
