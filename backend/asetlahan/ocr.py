"""Pembacaan teks dokumen (OCR) dan pengenalan isian penting.

Urutan: lapisan teks PDF (pypdf) → Tesseract untuk gambar → Claude untuk PDF
hasil pindai/gambar bila Tesseract tidak tersedia. Isian (nomor hak, NIB,
luas, pemegang hak, lokasi, tanggal, nomor perkara, NOP) dikenali dengan pola
teks, dilengkapi Claude bila ``ANTHROPIC_API_KEY`` diisi.
"""

import datetime
import io
import logging
import re
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from asetlahan import ai, enums

LOG = logging.getLogger(__name__)

FIELD_LABELS = {
    "jenis_hak": _("Jenis hak"),
    "nomor_hak": _("Nomor hak / sertipikat"),
    "nib": _("NIB"),
    "pemegang_hak": _("Pemegang hak"),
    "luas_m2": _("Luas (m²)"),
    "kelurahan": _("Kelurahan / desa"),
    "kecamatan": _("Kecamatan"),
    "tanggal_terbit": _("Tanggal terbit"),
    "tanggal_berakhir": _("Tanggal berakhir"),
    "nomor_perkara": _("Nomor perkara"),
    "nop": _("NOP PBB"),
    "ringkasan": _("Ringkasan"),
}

MONTHS = {
    "januari": 1, "februari": 2, "pebruari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6, "juli": 7,
    "agustus": 8, "september": 9, "oktober": 10, "november": 11, "nopember": 11, "desember": 12,
}
DATE = r"(\d{1,2}[-/.]\d{1,2}[-/.]\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})"
TITLE_TYPES = {
    "hak milik": "shm", "shm": "shm", "hak guna bangunan": "hgb", "hgb": "hgb", "hak guna usaha": "hgu",
    "hgu": "hgu", "hak pakai": "hp", "hp": "hp", "hak pengelolaan": "hpl", "hpl": "hpl",
}
PATTERNS = {
    "hak": re.compile(
        r"\b(hak\s+milik|hak\s+guna\s+bangunan|hak\s+guna\s+usaha|hak\s+pakai|hak\s+pengelolaan|SHM|HGB|HGU|HPL|HP)"
        r"\s*(?:no(?:mor)?\.?)?\s*[:.]?\s*(\d[\d./\-]*\d|\d)",
        re.IGNORECASE,
    ),
    "nib": re.compile(r"\bNIB\s*[:.]?\s*(\d[\d.\s]{6,22}\d)", re.IGNORECASE),
    "luas": re.compile(r"\bluas(?:\s+tanah)?\s*[:=]?\s*(?:±\s*)?([\d.,]+)\s*(m2|m²|meter\s+persegi|ha|hektar)",
                       re.IGNORECASE),
    "pemegang": re.compile(r"\bpemegang\s+hak\s*[:.]?\s*([^\n\r]{3,120})", re.IGNORECASE),
    "kelurahan": re.compile(r"\b(?:desa|kelurahan)\s*[:/]?\s*([A-Za-z][A-Za-z .'\-]{1,60})", re.IGNORECASE),
    "kecamatan": re.compile(r"\bkecamatan\s*[:/]?\s*([A-Za-z][A-Za-z .'\-]{1,60})", re.IGNORECASE),
    "berakhir": re.compile(r"\bberakhir(?:nya)?(?:\s+hak)?(?:\s+(?:pada|tanggal|tgl\.?))?\s*[:.]?\s*" + DATE,
                           re.IGNORECASE),
    "terbit": re.compile(r"\b(?:diterbitkan|tanggal\s+terbit|tgl\.?\s+terbit)(?:\s+tanggal)?\s*[:.]?\s*" + DATE,
                         re.IGNORECASE),
    "perkara": re.compile(r"\b(\d{1,5}/(?:Pdt|Pid)\.[A-Za-z.]+/\d{4}/[A-Za-z]+(?:\.[A-Za-z]+)?(?:\s[A-Z][a-z]+)?"
                          r"|\d{1,5}/G/\d{4}/PTUN\.[A-Za-z]+)"),
    "nop": re.compile(r"\bNOP\s*[:.]?\s*(\d{2}[.\s]?\d{2}[.\s]?\d{3}[.\s]?\d{3}[.\s]?\d{3}[\-.\s]?\d{4}[.\s]?\d)",
                      re.IGNORECASE),
}


def parse_date(value: str) -> str:
    value = (value or "").strip()
    match = re.match(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$", value)
    try:
        if match:
            return datetime.date(int(match[3]), int(match[2]), int(match[1])).isoformat()
        match = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$", value)
        if match and match[2].lower() in MONTHS:
            return datetime.date(int(match[3]), MONTHS[match[2].lower()], int(match[1])).isoformat()
    except ValueError:
        return ""
    return ""


def _area(number: str, unit: str) -> str:
    raw = number.strip(".,")
    # Format Indonesia: titik pemisah ribuan, koma desimal.
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(".") >= 1 and len(raw.rsplit(".", 1)[1]) == 3:
        raw = raw.replace(".", "")
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return ""
    if unit.lower().startswith(("ha", "hektar")):
        value *= 10000
    return str(value.quantize(Decimal("0.01")))


SIMPLE_FIELDS = (
    ("nib", "nib", lambda m: re.sub(r"[.\s]", "", m[1])),
    ("luas", "luas_m2", lambda m: _area(m[1], m[2])),
    ("pemegang", "pemegang_hak", lambda m: m[1].strip(" :.,")),
    ("kelurahan", "kelurahan", lambda m: m[1].strip(" .,").title()),
    ("kecamatan", "kecamatan", lambda m: m[1].strip(" .,").title()),
    ("berakhir", "tanggal_berakhir", lambda m: parse_date(m[1])),
    ("terbit", "tanggal_terbit", lambda m: parse_date(m[1])),
    ("perkara", "nomor_perkara", lambda m: m[1].strip()),
    ("nop", "nop", lambda m: re.sub(r"\s", "", m[1])),
)


def parse_fields(text: str) -> dict:
    """Isian penting dari teks dokumen dengan pola (tanpa layanan luar)."""
    found = {}
    if match := PATTERNS["hak"].search(text):
        found["jenis_hak"] = TITLE_TYPES.get(re.sub(r"\s+", " ", match[1].lower()), "")
        found["nomor_hak"] = match[2]
    for pattern, key, transform in SIMPLE_FIELDS:
        if match := PATTERNS[pattern].search(text):
            found[key] = transform(match)
    return {k: v for k, v in found.items() if v}


def _extension(name: str) -> str:
    return (name or "").lower().rsplit(".", 1)[-1]


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages[:200])


def _docx_text(data: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs)


def tesseract_available() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
    except Exception:  # noqa: BLE001 - biner tesseract tidak terpasang
        return False
    return True


def _image_text(data: bytes) -> str:
    import pytesseract
    from PIL import Image

    with Image.open(io.BytesIO(data)) as image:
        return pytesseract.image_to_string(image, lang=settings.OCR_LANGUAGES)


def read_text(name: str, data: bytes) -> str:
    extension = _extension(name)
    if extension == "pdf":
        return _pdf_text(data)
    if extension == "docx":
        return _docx_text(data)
    if extension in ("jpg", "jpeg", "png", "tif", "tiff") and tesseract_available():
        return _image_text(data)
    return ""


MEDIA_TYPES = {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}


def _ai_fields(name: str, data: bytes, text: str) -> dict:
    if not ai.enabled():
        return {}
    try:
        if len(text.strip()) >= 40:
            result = ai.extract_document(text=text)
        else:
            media_type = MEDIA_TYPES.get(_extension(name), "")
            if not media_type or len(data) > 20 * 1024 * 1024:
                return {}
            result = ai.extract_document(data=data, media_type=media_type)
    except ai.AIError as error:
        LOG.warning("Ekstraksi AI dokumen gagal: %s", error)
        return {}
    return {k: str(v).strip() for k, v in result.items() if k in FIELD_LABELS and str(v).strip()}


def process_document(document) -> bool:
    """Baca teks & isian dokumen, simpan ke dokumen. True bila ada teks/isian."""
    try:
        with document.file.open("rb") as handle:
            data = handle.read()
    except Exception:  # noqa: BLE001 - berkas hilang / belum lolos pindai virus
        LOG.exception("Berkas dokumen %s tidak dapat dibaca", document.pk)
        document.ocr_status = enums.OcrStatus.FAILED
        document.save(update_fields=["ocr_status", "modified_at"])
        return False
    try:
        text = read_text(document.file.name, data)
    except Exception:  # noqa: BLE001 - PDF/gambar rusak
        LOG.exception("OCR dokumen %s gagal", document.pk)
        text = ""
    fields = parse_fields(text)
    for key, value in _ai_fields(document.file.name, data, text).items():
        fields.setdefault(key, value)
    for key in ("tanggal_terbit", "tanggal_berakhir"):
        if key in fields and not re.match(r"\d{4}-\d{2}-\d{2}$", fields[key]):
            fields[key] = parse_date(fields[key])
    fields = {k: v for k, v in fields.items() if v}
    document.extracted_text = text.strip()[:500000]
    document.extracted_fields = fields
    document.ocr_status = enums.OcrStatus.DONE if (text.strip() or fields) else enums.OcrStatus.EMPTY
    document.save(update_fields=["extracted_text", "extracted_fields", "ocr_status", "modified_at"])
    return document.ocr_status == enums.OcrStatus.DONE


ASSET_FIELD_MAP = {
    "nomor_hak": "title_number",
    "nib": "nib",
    "pemegang_hak": "registered_owner",
    "kelurahan": "village",
    "kecamatan": "district",
}


def _asset_values(fields: dict) -> dict:
    values = {target: str(fields[key])[:128] for key, target in ASSET_FIELD_MAP.items() if fields.get(key)}
    if fields.get("jenis_hak") in enums.TitleType.values:
        values["title_type"] = fields["jenis_hak"]
    for key, target in (("tanggal_terbit", "title_date"), ("tanggal_berakhir", "title_expiry")):
        if fields.get(key):
            try:
                values[target] = datetime.date.fromisoformat(fields[key])
            except ValueError:
                pass
    if fields.get("luas_m2"):
        try:
            values["area_m2"] = Decimal(str(fields["luas_m2"]))
        except InvalidOperation:
            pass
    return values


def apply_to_asset(document) -> list:
    """Isi kolom aset yang masih kosong dari hasil baca dokumen. Mengembalikan label kolom yang diisi."""
    asset = document.asset
    changed = []
    for field, value in _asset_values(document.extracted_fields or {}).items():
        current = getattr(asset, field)
        empty = current in (None, "") or (field == "title_type" and current == enums.TitleType.UNREGISTERED)
        if empty:
            setattr(asset, field, value)
            changed.append(asset._meta.get_field(field).verbose_name)
    if changed:
        asset.save()
    return changed
