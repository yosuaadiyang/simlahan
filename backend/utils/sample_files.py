"""Berkas kecil yang sah (PDF, PNG, JPEG) untuk data contoh SimLahan.

Dipakai perintah ``*_contoh_rempang`` / ``data_contoh`` agar setiap kolom
berkas punya isi yang benar-benar bisa dibuka, dengan tanda jelas bahwa
berkas itu fiktif. Tidak ada berkas nyata atau data pribadi di sini.
"""

import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.text import slugify

NOTICE = "DOKUMEN CONTOH - FIKTIF - BUKAN DOKUMEN SAH"


def pdf_bytes(title: str, lines: tuple[str, ...] = ()) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    page = canvas.Canvas(buffer, pagesize=A4)
    page.setTitle(title)
    page.setFont("Helvetica-Bold", 16)
    page.drawString(72, 770, title[:70])
    page.setFont("Helvetica", 11)
    page.drawString(72, 745, NOTICE)
    y = 720
    for line in lines or ("Dibuat otomatis untuk uji coba SimLahan.",):
        page.drawString(72, y, line[:95])
        y -= 18
    page.showPage()
    page.save()
    return buffer.getvalue()


def image_bytes(title: str, fmt: str = "PNG", size=(640, 400), color="#1d82f5"):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, size[0] - 16, size[1] - 16), outline="white", width=4)
    draw.text((32, 32), title[:60], fill="white")
    draw.text((32, 56), NOTICE, fill="white")
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def _name(title: str, ext: str) -> str:
    return (slugify(title)[:60] or "contoh") + f".{ext}"


def pdf_upload(title: str, lines: tuple[str, ...] = ()) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        _name(title, "pdf"), pdf_bytes(title, lines), content_type="application/pdf"
    )


def png_upload(title: str, **kwargs) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        _name(title, "png"), image_bytes(title, "PNG", **kwargs), "image/png"
    )


def jpeg_upload(title: str, **kwargs) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        _name(title, "jpg"), image_bytes(title, "JPEG", **kwargs), "image/jpeg"
    )


def delete_files(*fields) -> None:
    """Hapus berkas di penyimpanan (bukan barisnya). Kolom kosong dilewati."""
    for field in fields:
        if field:
            field.delete(save=False)


def hard_delete(objects) -> int:
    """Hapus permanen objek beserta seluruh turunannya (termasuk yang terhapus
    lunak dan yang dilindungi PROTECT), anak lebih dahulu. Hanya untuk pohon data
    contoh: setiap turunan dari objek contoh dianggap bagian dari data contoh.
    Berkas pada kolom berkas ikut dihapus dari penyimpanan."""
    seen: set = set()
    for obj in objects:
        _hard_delete(obj, seen)
    return len(seen)


def _hard_delete(obj, seen: set) -> None:
    from django.db import models
    from safedelete.config import HARD_DELETE
    from safedelete.models import SafeDeleteModel

    key = (obj._meta.label, obj.pk)
    if obj.pk is None or key in seen:
        return
    seen.add(key)
    relations = [
        field
        for field in obj._meta.get_fields(include_hidden=True)
        if (field.one_to_many or field.one_to_one)
        and field.auto_created
        and not field.concrete
    ]
    for relation in relations:
        if relation.on_delete not in (
            models.CASCADE,
            models.PROTECT,
            models.RESTRICT,
        ):
            continue
        model = relation.related_model
        manager = getattr(model, "all_objects", model._base_manager)
        for child in manager.filter(**{relation.field.name: obj}):
            _hard_delete(child, seen)
    delete_files(
        *(
            getattr(obj, field.name)
            for field in obj._meta.concrete_fields
            if isinstance(field, models.FileField)
        )
    )
    if isinstance(obj, SafeDeleteModel):
        obj.delete(force_policy=HARD_DELETE)
    else:
        obj.delete()
