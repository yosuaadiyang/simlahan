"""PDF modul dokumen: hasil templat, dokumen bertanda tangan + sertifikat
penyelesaian, cap kaki halaman, dan tanda air unduhan."""

import hashlib
import io
import textwrap

from django.utils import timezone

from alokasi.documents import qr_data_uri, render_pdf
from alokasi.models import AllocationSettings
from dokumen import enums


class PdfReadError(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verification_url(document) -> str:
    from alokasi.services import portal_url

    return portal_url(f"dokumen/verifikasi/{document.verify_token}/")


def template_pdf(title: str, body_html: str, *, number: str = "") -> bytes:
    """PDF biasa dari isi templat yang sudah diisi (tanpa tanda tangan)."""
    return render_pdf(
        "dokumen/pdf/template.html",
        {
            "title": title,
            "body": body_html,
            "number": number,
            "config": AllocationSettings.load(),
            "generated_at": timezone.now(),
        },
    )


def _context(document, *, include_body: bool) -> dict:
    from dokumen.signing import render_body

    url = verification_url(document)
    recipients = list(document.recipients.order_by("order", "pk"))
    fields = list(document.fields.select_related("recipient").order_by("order", "pk"))
    events = list(
        document.activities.select_related("actor").order_by("created_at", "pk")
    )
    return {
        "doc": document,
        "body": render_body(document) if include_body else "",
        "fields": [f for f in fields if f.filled_at],
        "signers": [r for r in recipients if r.is_acting],
        "copies": [r for r in recipients if not r.is_acting],
        "events": events,
        "config": AllocationSettings.load(),
        "verification_url": url,
        "qr": qr_data_uri(url),
        "completed_at": document.completed_at or timezone.now(),
    }


def _merge(parts: list[bytes]) -> bytes:
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for data in parts:
        for page in PdfReader(io.BytesIO(data)).pages:
            writer.add_page(page)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _overlay(data: bytes, draw) -> bytes:
    """Tumpuk gambar reportlab (``draw(canvas, width, height)``) di tiap halaman."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.errors import PdfReadError as PypdfReadError
    from reportlab.pdfgen import canvas

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise PdfReadError("PDF terenkripsi.")
        pages = list(reader.pages)
    except (PypdfReadError, ValueError, KeyError, OSError) as error:
        raise PdfReadError(str(error)) from error
    writer = PdfWriter()
    for page in pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        buffer = io.BytesIO()
        sheet = canvas.Canvas(buffer, pagesize=(width, height))
        draw(sheet, width, height)
        sheet.save()
        stamp = PdfReader(io.BytesIO(buffer.getvalue())).pages[0]
        page.merge_page(stamp)
        writer.add_page(page)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def stamp_footer(data: bytes, text: str) -> bytes:
    text = str(text)

    def draw(sheet, width, height):
        sheet.setFont("Helvetica", 7)
        sheet.setFillGray(0.35)
        sheet.drawCentredString(width / 2, 14, text[:180])

    return _overlay(data, draw)


def watermark(data: bytes, lines: list[str]) -> bytes:
    """Tanda air diagonal + baris kaki berisi identitas pengunduh."""
    lines = [str(line) for line in lines]

    def draw(sheet, width, height):
        sheet.saveState()
        sheet.setFillColorRGB(0.75, 0.1, 0.1, alpha=0.13)
        sheet.setFont("Helvetica-Bold", 26)
        sheet.translate(width / 2, height / 2)
        sheet.rotate(35)
        for index, line in enumerate(lines[:2]):
            sheet.drawCentredString(0, 20 - index * 34, line[:70])
        sheet.restoreState()
        sheet.setFont("Helvetica", 6.5)
        sheet.setFillGray(0.3)
        footer = " · ".join(lines)
        for index, chunk in enumerate(textwrap.wrap(footer, 150)[:2]):
            sheet.drawString(18, height - 12 - index * 8, chunk)

    return _overlay(data, draw)


def _png(data_uri: str):
    import base64

    from reportlab.lib.utils import ImageReader

    if not data_uri or "," not in data_uri:
        return None
    try:
        return ImageReader(io.BytesIO(base64.b64decode(data_uri.split(",", 1)[1])))
    except (ValueError, OSError):
        return None


def stamp_signatures(data: bytes, recipients) -> bytes:
    """Cap tanda tangan penerima pada posisi yang ditetapkan di PDF unggahan.

    Posisi ``stamp_x``/``stamp_y``/``stamp_width`` dalam persen halaman;
    ``stamp_page`` 1 = halaman pertama, -1 = terakhir. Halaman di luar jangkauan
    diabaikan (tanda tangan tetap ada di lembar pengesahan).
    """
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas

    stamps = [r for r in recipients if r.stamp_page and r.completed_at]
    if not stamps:
        return data
    reader = PdfReader(io.BytesIO(data))
    pages = list(reader.pages)
    total = len(pages)
    by_page = {}
    for r in stamps:
        index = total - 1 if r.stamp_page < 0 else r.stamp_page - 1
        if 0 <= index < total:
            by_page.setdefault(index, []).append(r)
    writer = PdfWriter()
    for index, page in enumerate(pages):
        if index in by_page:
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            buffer = io.BytesIO()
            sheet = canvas.Canvas(buffer, pagesize=(width, height))
            for r in by_page[index]:
                box_w = width * r.stamp_width / 100
                box_h = box_w * 60 / 170
                left = width * r.stamp_x / 100
                top = height - height * r.stamp_y / 100
                left = min(left, width - box_w - 4)
                bottom = max(top - box_h, 22)
                image = _png(r.signature_image)
                if image is not None:
                    sheet.drawImage(
                        image,
                        left,
                        bottom,
                        width=box_w,
                        height=box_h,
                        mask="auto",
                        preserveAspectRatio=True,
                    )
                else:
                    sheet.setFont("Helvetica-Bold", 9)
                    sheet.setFillColorRGB(0.05, 0.37, 0.8)
                    sheet.drawString(left, bottom + box_h / 2, "DISETUJUI")
                sheet.setFillGray(0.2)
                sheet.setFont("Helvetica", 6.5)
                caption = f"{r.signature_name or r.name} · {timezone.localtime(r.completed_at):%d-%m-%Y %H.%M} WIB"
                sheet.drawString(left, bottom - 8, caption[:90])
            sheet.save()
            page.merge_page(PdfReader(io.BytesIO(buffer.getvalue())).pages[0])
        writer.add_page(page)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def signing_pdf(document) -> bytes:
    """PDF final dokumen tanda tangan beserta lembar pengesahan dan sertifikat."""
    if document.source == enums.SigningSource.HTML:
        return render_pdf(
            "dokumen/pdf/signed.html", _context(document, include_body=True)
        )
    with document.source_file.open("rb") as handle:
        original = handle.read()
    footer = (
        f"Ditandatangani elektronik {document.number} · periksa keaslian: "
        f"{verification_url(document)}"
    )
    recipients = list(document.recipients.order_by("order", "pk"))
    stamped = stamp_footer(stamp_signatures(original, recipients), footer)
    appendix = render_pdf(
        "dokumen/pdf/signed.html", _context(document, include_body=False)
    )
    return _merge([stamped, appendix])


def page_count(data: bytes) -> int:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError as PypdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise PdfReadError("PDF terenkripsi.")
        return len(reader.pages)
    except (PypdfReadError, ValueError, KeyError, OSError) as error:
        raise PdfReadError(str(error)) from error
