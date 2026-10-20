"""Validasi isi berkas unggahan: tanda tangan biner harus cocok dengan ekstensi.

Mencegah berkas lain yang sekadar diganti namanya (mis. ``program.exe`` menjadi
``surat.pdf``). Ekstensi yang tidak dikenal (csv, txt, doc lama, dll.) dilewati.
"""

import os

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy as _

ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")


def _is_pdf(head: bytes) -> bool:
    # Spesifikasi PDF mengizinkan header di 1024 bita pertama.
    return b"%PDF-" in head


def _is_webp(head: bytes) -> bool:
    return head[:4] == b"RIFF" and head[8:12] == b"WEBP"


SIGNATURE_CHECKS = {
    "pdf": _is_pdf,
    "png": lambda head: head.startswith(b"\x89PNG\r\n\x1a\n"),
    "jpg": lambda head: head.startswith(b"\xff\xd8\xff"),
    "jpeg": lambda head: head.startswith(b"\xff\xd8\xff"),
    "gif": lambda head: head.startswith((b"GIF87a", b"GIF89a")),
    "webp": _is_webp,
    "tif": lambda head: head.startswith((b"II*\x00", b"MM\x00*")),
    "tiff": lambda head: head.startswith((b"II*\x00", b"MM\x00*")),
}
for _extension in ("zip", "docx", "xlsx", "pptx", "odt", "ods", "odp", "kmz"):
    SIGNATURE_CHECKS[_extension] = lambda head: head.startswith(ZIP_SIGNATURES)


def _new_upload(value):
    """Berkas yang baru diunggah, atau None untuk berkas yang sudah tersimpan."""
    if isinstance(value, UploadedFile):
        return value
    if getattr(value, "_committed", True) is False:
        upload = getattr(value, "file", None)
        if isinstance(upload, UploadedFile):
            return upload
    return None


def validate_file_signature(value) -> None:
    upload = _new_upload(value)
    if upload is None:
        return
    extension = os.path.splitext(upload.name or "")[1].lower().lstrip(".")
    check = SIGNATURE_CHECKS.get(extension)
    if check is None:
        return
    position = upload.tell()
    try:
        upload.seek(0)
        head = upload.read(1024)
    finally:
        upload.seek(position)
    if not check(head or b""):
        raise ValidationError(
            _(
                "Isi berkas tidak sesuai dengan jenisnya (.%(extension)s). "
                "Pastikan berkas tidak rusak dan ekstensinya benar."
            ),
            code="invalid_file_signature",
            params={"extension": extension},
        )
