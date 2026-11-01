"""Pembuatan PDF: KPT, PPT, PL, izin peralihan hak, surat layanan, dan tagihan.

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
    "sph": "alokasi/pdf/sph.html",
    "spt": "alokasi/pdf/spt.html",
    "pl": "alokasi/pdf/pl.html",
}

# Ukuran gambar bidang pada dokumen Penetapan Lokasi (piksel).
SKETCH_SIZE = (900, 620)
SKETCH_MARGIN = 60
MAX_VERTICES_LISTED = 200


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


def plot_sketch(geometry) -> tuple[str, list[dict]]:
    """Gambar bidang (PNG data URI) dan daftar titik sudut dari MultiPolygon.

    Koordinat geografis diproyeksikan sederhana (equirectangular di lintang
    tengah bidang) sehingga bentuk bidang tidak terdistorsi pada skala persil.
    Mengembalikan ("", []) bila geometri kosong.
    """
    import math

    from PIL import Image, ImageDraw

    if geometry is None or geometry.empty:
        return "", []
    rings = _sketch_rings(geometry)
    if not rings:
        return "", []
    lat0 = math.radians(geometry.centroid.y)
    kx = 111320.0 * math.cos(lat0)
    ky = 110540.0
    xs = [x * kx for ring in rings for x, _y in ring]
    ys = [y * ky for ring in rings for _x, y in ring]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    width, height = SKETCH_SIZE
    span = max(max_x - min_x, max_y - min_y, 1e-6)
    scale = min(
        (width - 2 * SKETCH_MARGIN) / max(max_x - min_x, span * 0.05),
        (height - 2 * SKETCH_MARGIN) / max(max_y - min_y, span * 0.05),
    )
    off_x = (width - (max_x - min_x) * scale) / 2
    off_y = (height - (max_y - min_y) * scale) / 2

    def to_px(lon, lat):
        return (
            off_x + (lon * kx - min_x) * scale,
            height - (off_y + (lat * ky - min_y) * scale),
        )

    image = Image.new("RGB", SKETCH_SIZE, "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, width - 1, height - 1], outline=(120, 120, 120))
    vertices = _draw_rings(draw, rings, to_px)
    # Panah utara dan skala batang.
    draw.polygon([(width - 34, 46), (width - 24, 16), (width - 14, 46)], fill=(0, 0, 0))
    draw.text((width - 28, 50), "U", fill=(0, 0, 0))
    meters = _nice_length((width - 2 * SKETCH_MARGIN) / scale / 4)
    bar = meters * scale
    draw.rectangle([20, height - 26, 20 + bar, height - 20], fill=(0, 0, 0))
    draw.text((20, height - 44), f"{meters:g} m", fill=(0, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    data_uri = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    return data_uri, vertices


def _sketch_rings(geometry) -> list[list[tuple]]:
    """Cincin poligon tanpa titik penutup berulang."""
    rings = []
    for polygon in geometry:
        for ring in polygon:
            points = list(ring.coords)
            if len(points) > 1 and points[0] == points[-1]:
                points = points[:-1]
            if points:
                rings.append(points)
    return rings


def _draw_rings(draw, rings, to_px) -> list[dict]:
    """Gambar bidang + titik sudut bernomor; kembalikan daftar titik sudut."""
    vertices = []
    number = 0
    for index, ring in enumerate(rings):
        pixels = [to_px(x, y) for x, y in ring]
        if len(pixels) >= 3:
            draw.polygon(
                pixels,
                fill=(221, 236, 253) if index == 0 else None,
                outline=(11, 95, 204),
            )
        for (lon, lat), (px, py) in zip(ring, pixels):
            number += 1
            draw.ellipse([px - 4, py - 4, px + 4, py + 4], fill=(200, 30, 30))
            draw.text((px + 6, py - 14), str(number), fill=(0, 0, 0))
            if len(vertices) < MAX_VERTICES_LISTED:
                vertices.append({"no": number, "lat": lat, "lon": lon})
    return vertices


def _nice_length(value: float) -> float:
    """Bulatkan panjang skala batang ke 1, 2, atau 5 × 10^n meter."""
    import math

    if value <= 0:
        return 1.0
    power = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 5, 10):
        if value <= step * power:
            return step * power
    return 10 * power


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
    if kind == "pl":
        context["sketch"], context["vertices"] = plot_sketch(allocation.plot.geometry)
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
