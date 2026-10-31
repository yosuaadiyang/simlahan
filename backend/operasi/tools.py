"""Alat pusat komando: tiket & masukan, OCR, analisis dokumen & foto lapangan
dengan AI, audit data mandiri, dan sinkron Excel lengkap.

Fitur AI memakai Claude (``ANTHROPIC_API_KEY``) dan dibatasi kuota per jam per
pengguna. Tanpa kunci AI, OCR memakai Tesseract, analisis dokumen memberi profil
data apa adanya, dan audit data tetap berjalan (hanya ringkasan AI yang absen).
"""

import base64
import io
import json
import logging
from collections import Counter
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.db.models import Extent
from django.contrib.gis.geos import Polygon
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from asetlahan import ai
from asetlahan import ocr as aset_ocr
from operasi import enums, geo, geotech, services, spatial, tabular
from operasi.models import (
    Activity,
    Korwil,
    Resident,
    Ticket,
)
from utils.group_permissions import UserGroup

LOG = logging.getLogger(__name__)

AI_LIMIT_PER_HOUR = 30
MAX_TEXT_CHARS = 60_000
MAX_IMAGE_SIDE = 1568
WORK_AREA_MARGIN_DEG = 0.02  # ±2 km di sekitar seluruh Korwil
IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "webp", "heic", "heif")


def _name(user) -> str:
    if user is None:
        return ""
    return user.get_full_name() or user.get_username()


def extension(name: str) -> str:
    return (name or "").lower().rsplit(".", 1)[-1]


# --------------------------------------------------------------------------
# Kuota AI
# --------------------------------------------------------------------------


def use_ai_quota(user):
    """Satu pemakaian AI; galat bila kuota jam ini habis."""
    hour = timezone.now().strftime("%Y%m%d%H")
    key = f"operasi:alat-ai:{user.pk}:{hour}"
    cache.add(key, 0, 3700)
    try:
        used = cache.incr(key)
    except ValueError:
        cache.set(key, 1, 3700)
        used = 1
    if used > AI_LIMIT_PER_HOUR:
        raise ValidationError(
            {
                "ai": [
                    _("Batas %(n)s permintaan AI per jam tercapai. Coba lagi nanti.")
                    % {"n": AI_LIMIT_PER_HOUR}
                ]
            }
        )


def _ai_json(content: list, schema: dict, max_tokens: int = 3000) -> dict:
    response = ai.create(
        max_tokens=max_tokens,
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": schema},
        },
        messages=[{"role": "user", "content": content}],
    )
    try:
        return json.loads(ai.text_of(response))
    except json.JSONDecodeError:
        raise ai.AIError(_("Jawaban layanan AI tidak dapat dibaca."))


# --------------------------------------------------------------------------
# Tiket & masukan
# --------------------------------------------------------------------------


def can_handle_tickets(user) -> bool:
    return user.has_perm("operasi.change_ticket")


def visible_tickets(user):
    queryset = Ticket.objects.select_related("created_by", "resolved_by")
    if can_handle_tickets(user):
        return queryset
    return queryset.filter(created_by=user)


def ticket_points(ticket, status: str, note: str, now) -> tuple[int, Decimal | None]:
    """Poin untuk pengirim: tiket selesai dihargai menurut jenis, prioritas, dan
    kecepatan penanganan; tiket ditolak dengan alasan tertulis mendapat 1 poin."""
    C, P = enums.TicketCategory, enums.TicketPriority
    hours = Decimal(str(round((now - ticket.created_at).total_seconds() / 3600, 1)))
    if status == enums.TicketStatus.DONE:
        points = 10
        if ticket.category in (C.BUG, C.OUTAGE):
            points += 5
        elif ticket.category in (C.SUGGESTION, C.REVIEW):
            points += 2
        points += {P.CRITICAL: 8, P.HIGH: 4}.get(ticket.priority, 0)
        if hours < 24:
            points += 5
        elif hours < 72:
            points += 2
        return points, hours
    if status == enums.TicketStatus.REJECTED:
        return (1 if note.strip() else 0), hours
    return 0, None


def set_ticket_status(ticket, user, status: str, note: str = "", priority: str = ""):
    if not can_handle_tickets(user):
        raise PermissionDenied
    if status not in enums.TicketStatus.values:
        raise ValidationError({"status": [_("Status tidak dikenal.")]})
    if priority:
        if priority not in enums.TicketPriority.values:
            raise ValidationError({"prioritas": [_("Prioritas tidak dikenal.")]})
        ticket.priority = priority
    note = note.strip()[:5000]
    if note:
        ticket.handler_note = note
    if status == enums.TicketStatus.REJECTED and not ticket.handler_note:
        raise ValidationError({"catatan": [_("Tuliskan alasan penolakan.")]})
    now = timezone.now()
    ticket.status = status
    final = status in (enums.TicketStatus.DONE, enums.TicketStatus.REJECTED)
    ticket.points, ticket.resolution_hours = ticket_points(
        ticket, status, ticket.handler_note, now
    )
    ticket.resolved_by = user if final else None
    ticket.resolved_at = now if final else None
    ticket.save()
    return ticket


def ticket_row(ticket, user) -> dict:
    from operasi.views import file_url

    return {
        "id": ticket.pk,
        "number": ticket.number,
        "category": ticket.category,
        "category_label": ticket.get_category_display(),
        "priority": ticket.priority,
        "priority_label": ticket.get_priority_display(),
        "status": ticket.status,
        "status_label": ticket.get_status_display(),
        "color": enums.TICKET_COLORS.get(ticket.status, "#57606a"),
        "title": ticket.title,
        "description": ticket.description,
        "attachment": (file_url("tiket", ticket) if ticket.attachment else ""),
        "sender": _name(ticket.created_by),
        "mine": ticket.created_by_id == user.pk,
        "note": ticket.handler_note,
        "handler": _name(ticket.resolved_by),
        "points": ticket.points,
        "hours": float(ticket.resolution_hours) if ticket.resolution_hours else None,
        "created_at": timezone.localtime(ticket.created_at).isoformat(),
        "resolved_at": (
            timezone.localtime(ticket.resolved_at).isoformat()
            if ticket.resolved_at
            else ""
        ),
    }


def ticket_leaderboard(user, limit: int = 20) -> list[dict]:
    """Pengirim masukan teratas (poin tiket yang selesai/ditolak)."""
    queryset = visible_tickets(user).filter(created_by__isnull=False)
    rows = (
        queryset.values("created_by")
        .annotate(
            points=Sum("points"),
            sent=Count("pk"),
            done=Count("pk", filter=Q(status=enums.TicketStatus.DONE)),
        )
        .order_by("-points", "-done", "created_by")[:limit]
    )
    users = get_user_model().objects.in_bulk([r["created_by"] for r in rows])
    return [
        {
            "name": _name(users.get(r["created_by"])),
            "points": r["points"] or 0,
            "sent": r["sent"],
            "done": r["done"],
        }
        for r in rows
    ]


def ticket_summary(queryset) -> dict:
    counts = Counter(queryset.values_list("status", flat=True))
    return {
        "status": [
            {
                "value": str(value),
                "label": str(label),
                "count": counts.get(value, 0),
                "color": enums.TICKET_COLORS[value],
            }
            for value, label in enums.TicketStatus.choices
        ],
        "total": sum(counts.values()),
    }


def ticket_sheet_rows(tickets):
    for t in tickets:
        yield [
            t.number,
            t.get_category_display(),
            t.title,
            t.description,
            t.get_status_display(),
            t.get_priority_display(),
            t.points,
            float(t.resolution_hours) if t.resolution_hours is not None else "",
            _name(t.created_by),
            timezone.localtime(t.created_at).strftime("%Y-%m-%d %H:%M"),
            _name(t.resolved_by),
            t.handler_note,
        ]


TICKET_HEADERS = [
    "Nomor",
    "Kategori",
    "Judul",
    "Deskripsi",
    "Status",
    "Prioritas",
    "Poin",
    "Lama (jam)",
    "Pengirim",
    "Dikirim",
    "Ditangani",
    "Catatan pengelola",
]


def tickets_workbook(tickets) -> bytes:
    from operasi.recap import _Book

    book = _Book()
    book.table(
        "Tiket", TICKET_HEADERS, ticket_sheet_rows(tickets), {2: 30, 3: 50, 11: 40}
    )
    return book.close()


# --------------------------------------------------------------------------
# Pembacaan berkas: teks & tabel
# --------------------------------------------------------------------------


def _table_text(rows: list[list], limit_rows: int = 300) -> str:
    lines = []
    for row in rows[:limit_rows]:
        cells = [tabular.cell_text(c) for c in row]
        if any(cells):
            lines.append(" | ".join(cells))
    if len(rows) > limit_rows:
        lines.append(_("… (%(n)s baris total)") % {"n": len(rows)})
    return "\n".join(lines)


def read_document(name: str, data: bytes) -> dict:
    """Isi berkas sebagai teks (dan tabel bila Excel/CSV)."""
    ext = extension(name)
    if ext in ("xlsx", "xlsm", "csv", "tsv"):
        sheet, rows = tabular.read_table(name, data)
        return {
            "kind": "tabel",
            "sheet": sheet,
            "rows": rows,
            "text": _table_text(rows),
        }
    if ext in ("txt", "md"):
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                return {"kind": "teks", "text": data.decode(encoding)}
            except UnicodeDecodeError:
                continue
    if ext in ("pdf", "docx"):
        try:
            return {"kind": "teks", "text": aset_ocr.read_text(name, data)}
        except Exception:  # noqa: BLE001 - berkas rusak/terenkripsi
            raise ValidationError({"berkas": [_("Berkas tidak dapat dibaca.")]})
    if ext in IMAGE_EXTENSIONS:
        return {"kind": "gambar", "text": ""}
    raise ValidationError(
        {
            "berkas": [
                _(
                    "Format didukung: PDF, Word (.docx), Excel (.xlsx), CSV, TXT, atau foto."
                )
            ]
        }
    )


def prepare_image(data: bytes) -> tuple[bytes, str]:
    """Foto diperkecil (sisi terpanjang ≤ 1568 px) dan dijadikan JPEG untuk AI."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            out = io.BytesIO()
            image.save(out, "JPEG", quality=85)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValidationError({"berkas": [_("Foto tidak dapat dibaca.")]})
    return out.getvalue(), "image/jpeg"


def _image_block(data: bytes) -> dict:
    image, media_type = prepare_image(data)
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.standard_b64encode(image).decode(),
        },
    }


def _document_block(name: str, data: bytes, document: dict) -> dict:
    if document["kind"] == "gambar":
        return _image_block(data)
    if extension(name) == "pdf" and len(document["text"].strip()) < 40:
        # PDF hasil pindai: kirim berkasnya agar AI membaca langsung.
        return {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.standard_b64encode(data).decode(),
            },
        }
    return {
        "type": "text",
        "text": f"<dokumen nama=\"{name[:100]}\">\n{document['text'][:MAX_TEXT_CHARS]}\n</dokumen>",
    }


# --------------------------------------------------------------------------
# OCR
# --------------------------------------------------------------------------

OCR_SCHEMA = {
    "type": "object",
    "properties": {
        "jenis_dokumen": {"type": "string"},
        "teks": {"type": "string"},
        "isian": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "nilai": {"type": "string"},
                },
                "required": ["label", "nilai"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["jenis_dokumen", "teks", "isian"],
    "additionalProperties": False,
}

OCR_PROMPT = (
    "Baca seluruh teks pada dokumen ini apa adanya (pertahankan baris & urutan). "
    "Sebutkan jenis dokumennya (mis. nota/kuitansi, surat, KTP disamarkan, formulir, "
    "papan nama). Di 'isian', ambil data penting: untuk nota/kuitansi tanggal, item, "
    "jumlah, total; untuk surat nomor, tanggal, perihal, pengirim. Jangan menebak "
    "bagian yang tidak terbaca; tulis [tidak terbaca]. Bahasa Indonesia."
)


def ocr(user, name: str, data: bytes) -> dict:
    ext = extension(name)
    if ext not in IMAGE_EXTENSIONS + ("pdf",):
        raise ValidationError({"berkas": [_("OCR menerima foto atau PDF.")]})
    if ai.enabled():
        use_ai_quota(user)
        document = {"kind": "gambar" if ext != "pdf" else "teks", "text": ""}
        if ext == "pdf":
            document["text"] = read_document(name, data)["text"]
        try:
            result = _ai_json(
                [
                    _document_block(name, data, document),
                    {"type": "text", "text": OCR_PROMPT},
                ],
                OCR_SCHEMA,
                max_tokens=6000,
            )
            return {
                "source": "ai",
                "type": result.get("jenis_dokumen", ""),
                "text": result.get("teks", ""),
                "fields": result.get("isian", [])[:50],
            }
        except ai.AIError as error:
            LOG.warning("OCR AI gagal: %s", error)
    if ext == "pdf":
        text = read_document(name, data)["text"]
    elif aset_ocr.tesseract_available():
        image, _media = prepare_image(data)
        text = aset_ocr._image_text(image)
    else:
        raise ValidationError(
            {
                "berkas": [
                    _(
                        "OCR belum tersedia: AI belum dikonfigurasi dan Tesseract tidak terpasang."
                    )
                ]
            }
        )
    fields = [
        {"label": str(aset_ocr.FIELD_LABELS.get(k, k)), "nilai": v}
        for k, v in aset_ocr.parse_fields(text).items()
    ]
    return {"source": "ocr", "type": "", "text": text.strip(), "fields": fields}


# --------------------------------------------------------------------------
# Analisis dokumen → laporan
# --------------------------------------------------------------------------

REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "judul": {"type": "string"},
        "ringkasan": {"type": "string"},
        "temuan_utama": {"type": "array", "items": {"type": "string"}},
        "data_kunci": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "nilai": {"type": "string"},
                },
                "required": ["label", "nilai"],
                "additionalProperties": False,
            },
        },
        "rekomendasi": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["judul", "ringkasan", "temuan_utama", "data_kunci", "rekomendasi"],
    "additionalProperties": False,
}

REPORT_PROMPT = (
    "Anda analis data tim pengelolaan lahan. Analisis dokumen di atas lalu susun "
    "laporan singkat untuk pimpinan: judul, ringkasan 3–5 kalimat, temuan utama, "
    "data kunci (angka, statistik, nama penting — hanya yang tertulis di dokumen), "
    "dan rekomendasi tindak lanjut. {fokus}Jangan mengarang angka. Bahasa Indonesia."
)


def table_profile(rows: list[list]) -> dict:
    """Profil tabel tanpa AI: jumlah baris/kolom, kolom angka (jumlah, rata-rata),
    dan nilai terbanyak untuk kolom teks."""
    header_index = 0
    for index, row in enumerate(rows[:15]):
        if sum(1 for c in row if tabular.cell_text(c)) >= 2:
            header_index = index
            break
    header = [
        tabular.cell_text(c) or f"Kolom {i + 1}"
        for i, c in enumerate(rows[header_index] if rows else [])
    ]
    body = [r for r in rows[header_index + 1 :] if any(tabular.cell_text(c) for c in r)]
    columns = []
    for i, title in enumerate(header[:40]):
        values = [r[i] for r in body if i < len(r) and tabular.cell_text(r[i])]
        numbers = [tabular.number(v) for v in values]
        numbers = [n for n in numbers if n is not None]
        info = {"name": title, "filled": len(values)}
        if values and len(numbers) >= len(values) * 0.8:
            info.update(
                kind="angka",
                total=round(sum(numbers), 2),
                mean=round(sum(numbers) / len(numbers), 2),
                min=min(numbers),
                max=max(numbers),
            )
        else:
            top = Counter(tabular.cell_text(v) for v in values).most_common(3)
            info.update(
                kind="teks", top=[{"value": v[:60], "count": n} for v, n in top]
            )
        columns.append(info)
    return {"rows": len(body), "columns": columns}


def document_report(user, name: str, data: bytes, focus: str = "") -> dict:
    document = read_document(name, data)
    result = {"file": name, "kind": document["kind"], "ai": False}
    if document["kind"] == "tabel":
        result["profile"] = table_profile(document["rows"])
    elif document["text"]:
        words = document["text"].split()
        result["profile"] = {
            "words": len(words),
            "preview": document["text"].strip()[:1500],
        }
    if not ai.enabled():
        result["message"] = _(
            "AI belum dikonfigurasi (ANTHROPIC_API_KEY). Ditampilkan profil data saja."
        )
        return result
    if (
        document["kind"] != "gambar"
        and not document["text"].strip()
        and extension(name) != "pdf"
    ):
        raise ValidationError({"berkas": [_("Dokumen kosong.")]})
    use_ai_quota(user)
    focus = focus.strip()[:300]
    prompt = REPORT_PROMPT.format(fokus=f"Fokus pengguna: {focus}. " if focus else "")
    try:
        result["report"] = _ai_json(
            [_document_block(name, data, document), {"type": "text", "text": prompt}],
            REPORT_SCHEMA,
            max_tokens=4000,
        )
        result["ai"] = True
        result["model"] = ai.model()
    except ai.AIError as error:
        result["message"] = str(error)
    return result


# --------------------------------------------------------------------------
# AI foto lapangan
# --------------------------------------------------------------------------

PHOTO_CATEGORIES = {
    "pembukaan": "#ef4444",
    "bangunan": "#f59e0b",
    "kebun": "#10b981",
    "air": "#3b82f6",
    "akses": "#a855f7",
    "lain": "#64748b",
}

PHOTO_SCHEMA = {
    "type": "object",
    "properties": {
        "ringkasan": {"type": "string"},
        "temuan": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "kategori": {"type": "string", "enum": list(PHOTO_CATEGORIES)},
                    "keyakinan": {
                        "type": "string",
                        "enum": ["tinggi", "sedang", "rendah"],
                    },
                    "x0": {"type": "number"},
                    "y0": {"type": "number"},
                    "x1": {"type": "number"},
                    "y1": {"type": "number"},
                    "catatan": {"type": "string"},
                },
                "required": [
                    "label",
                    "kategori",
                    "keyakinan",
                    "x0",
                    "y0",
                    "x1",
                    "y1",
                    "catatan",
                ],
                "additionalProperties": False,
            },
        },
        "rekomendasi": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["ringkasan", "temuan", "rekomendasi"],
    "additionalProperties": False,
}

PHOTO_PROMPT = (
    "Anda analis pemantauan lapangan untuk pengelolaan lahan. Amati foto lapangan "
    "ini (foto darat atau drone). Ringkas apa yang terlihat (1–2 kalimat), lalu "
    "daftar maksimal 10 temuan terpenting: pembukaan lahan, bangunan/struktur, "
    "kebun/vegetasi tertata, air/kolam/tambak, akses/jalan, atau lain (kendaraan, "
    "alat berat). Untuk tiap temuan beri kotak pembatas relatif foto (x0,y0 kiri-"
    "atas sampai x1,y1 kanan-bawah, 0–1). Beri rekomendasi tindak lanjut untuk tim. "
    "{konteks}Jangan mengenali atau menyebut identitas orang. Jujur bila foto kurang "
    "jelas. Bahasa Indonesia."
)


def _unit(value) -> float:
    try:
        return min(max(float(value), 0.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


def field_photo(user, name: str, data: bytes, context: str = "") -> dict:
    if extension(name) not in IMAGE_EXTENSIONS:
        raise ValidationError({"berkas": [_("Pilih berkas foto (JPG/PNG/WebP).")]})
    if not ai.enabled():
        raise ValidationError(
            {"ai": [_("AI belum dikonfigurasi (ANTHROPIC_API_KEY kosong).")]}
        )
    block = _image_block(data)
    use_ai_quota(user)
    context = context.strip()[:300]
    prompt = PHOTO_PROMPT.format(
        konteks=f"Konteks dari petugas: {context}. " if context else ""
    )
    try:
        result = _ai_json([block, {"type": "text", "text": prompt}], PHOTO_SCHEMA)
    except ai.AIError as error:
        raise ValidationError({"ai": [str(error)]})
    findings = []
    for item in result.get("temuan", [])[:10]:
        x0, x1 = sorted((_unit(item.get("x0")), _unit(item.get("x1"))))
        y0, y1 = sorted((_unit(item.get("y0")), _unit(item.get("y1"))))
        category = (
            item.get("kategori") if item.get("kategori") in PHOTO_CATEGORIES else "lain"
        )
        findings.append(
            {
                "label": str(item.get("label", ""))[:120],
                "category": category,
                "color": PHOTO_CATEGORIES[category],
                "confidence": item.get("keyakinan", "sedang"),
                "box": [x0, y0, x1, y1],
                "note": str(item.get("catatan", ""))[:300],
            }
        )
    return {
        "summary": result.get("ringkasan", ""),
        "findings": findings,
        "recommendations": [str(r)[:500] for r in result.get("rekomendasi", [])[:10]],
        "model": ai.model(),
    }


# --------------------------------------------------------------------------
# Audit data mandiri
# --------------------------------------------------------------------------

CRITICAL, ATTENTION = "kritis", "perhatian"
SAMPLE = 6


def work_area():
    """Batas kerja: kotak seluruh Korwil aktif ± ~2 km; None bila Korwil belum berpeta."""
    extent = (
        Korwil.objects.filter(is_active=True, geometry__isnull=False)
        .aggregate(e=Extent("geometry"))
        .get("e")
    )
    if not extent:
        return None
    west, south, east, north = extent
    m = WORK_AREA_MARGIN_DEG
    polygon = Polygon.from_bbox((west - m, south - m, east + m, north + m))
    polygon.srid = 4326
    return polygon


def _group(groups, label, severity, queryset, sample_of, link=""):
    count = queryset.count()
    if count:
        groups.append(
            {
                "label": str(label),
                "severity": severity,
                "count": count,
                "sample": [sample_of(obj) for obj in queryset[:SAMPLE]],
                "link": link,
            }
        )


def _user_admin() -> str:
    from django.urls import NoReverseMatch, reverse

    try:
        return reverse("admin:users_user_changelist")
    except NoReverseMatch:
        return ""


def _admin(name: str) -> str:
    from django.urls import NoReverseMatch, reverse

    try:
        return reverse(f"admin:operasi_{name}_changelist")
    except NoReverseMatch:
        return ""


class _Audit:
    def __init__(self, user):
        self.user = user
        self.groups: list[dict] = []
        self.area = work_area()
        self.links = user.has_perm("operasi.change_korwil")

    def link(self, name: str) -> str:
        if not self.links:
            return ""
        return _user_admin() if name == "user" else _admin(name)

    def add(self, label, severity, queryset, sample_of=str, link=""):
        _group(self.groups, label, severity, queryset, sample_of, self.link(link))

    def geotech(self):
        points = geotech.visible_points(self.user)
        self.add(
            _("Titik uji PLTS tanpa koordinat"),
            CRITICAL,
            points.filter(location__isnull=True),
            link="geotechpoint",
        )
        if self.area is not None:
            self.add(
                _("Titik uji PLTS di luar wilayah kerja"),
                CRITICAL,
                points.filter(location__isnull=False).exclude(
                    location__within=self.area
                ),
                link="geotechpoint",
            )
        self.add(
            _("Titik uji PLTS terhenti / kondisi sosial bermasalah"),
            ATTENTION,
            points.filter(
                Q(work_status=enums.GeotechWorkStatus.STOPPED)
                | Q(
                    social_condition__in=[
                        enums.SocialCondition.PROBLEM,
                        enums.SocialCondition.NOT_CONDUCIVE,
                    ]
                )
            ),
            lambda p: f"{p.code} ({p.obstacle or p.get_social_condition_display()})",
            "geotechpoint",
        )
        self.add(
            _("Titik uji PLTS tanpa area / paket"),
            ATTENTION,
            points.filter(area_name=""),
            link="geotechpoint",
        )

    def plots(self):
        plots = spatial.visible_plots(self.user)
        duplicates = list(
            plots.exclude(name="")
            .values("korwil", "name")
            .annotate(n=Count("pk"))
            .filter(n__gt=1)
            .order_by("-n", "name")[:500]
        )
        if duplicates:
            self.groups.append(
                {
                    "label": str(
                        _("Nama bidang ganda dalam satu Korwil (kemungkinan duplikat)")
                    ),
                    "severity": ATTENTION,
                    "count": len(duplicates),
                    "sample": [f"{d['name']} ({d['n']}×)" for d in duplicates[:SAMPLE]],
                    "link": self.link("landplot"),
                }
            )
        if self.area is not None:
            self.add(
                _("Bidang lahan di luar wilayah kerja"),
                CRITICAL,
                plots.exclude(geometry__intersects=self.area),
                link="landplot",
            )
        self.add(
            _("Bidang lahan tanpa Korwil"),
            ATTENTION,
            plots.filter(korwil__isnull=True),
            link="landplot",
        )
        self.add(
            _('Bidang "sudah dikuasai" tanpa tanggal penguasaan'),
            ATTENTION,
            plots.filter(
                control_status=enums.ControlStatus.CONTROLLED,
                controlled_on__isnull=True,
            ),
            link="landplot",
        )

    def residents(self):
        if not self.user.has_perm("operasi.view_resident"):
            return
        residents = geo.scoped(Resident.objects.all(), self.user)
        self.add(
            _("Warga tanpa titik lokasi rumah"),
            ATTENTION,
            residents.filter(location__isnull=True),
            lambda r: r.head_name,
            "resident",
        )
        self.add(
            _("Warga tanpa Korwil"),
            ATTENTION,
            residents.filter(korwil__isnull=True),
            lambda r: r.head_name,
            "resident",
        )
        if self.area is not None:
            self.add(
                _("Warga dengan lokasi di luar wilayah kerja"),
                CRITICAL,
                residents.filter(location__isnull=False).exclude(
                    location__within=self.area
                ),
                lambda r: r.head_name,
                "resident",
            )

    def activities(self):
        since = timezone.now() - timezone.timedelta(days=30)
        activities = geo.scoped(
            Activity.objects.filter(started_at__gte=since), self.user
        )
        self.add(
            _("Kegiatan 30 hari terakhir tanpa titik GPS"),
            ATTENTION,
            activities.filter(location__isnull=True),
            lambda a: f"{a.number} – {a.title}"[:80],
            "activity",
        )

    def officers(self):
        active = Korwil.objects.filter(is_active=True)
        member_ids = set(active.values_list("members", flat=True)) | set(
            active.values_list("coordinator", flat=True)
        )
        member_ids.discard(None)
        officers = (
            services.visible_officers(self.user)
            .filter(
                is_active=True,
                groups__pk__in=[
                    UserGroup.PETUGAS_LAPANGAN,
                    UserGroup.KOORDINATOR_WILAYAH,
                ],
            )
            .exclude(pk__in=member_ids)
            .distinct()
            .order_by("first_name", "last_name", "username")
        )
        self.add(
            _("Petugas lapangan/koordinator tanpa Korwil"),
            ATTENTION,
            officers,
            _name,
            "user",
        )

    def result(self) -> dict:
        groups = self.groups
        critical = sum(g["count"] for g in groups if g["severity"] == CRITICAL)
        attention = sum(g["count"] for g in groups if g["severity"] == ATTENTION)
        if critical:
            status, label = "tindakan", _("Perlu tindakan")
        elif attention > 8:
            status, label = "perhatian", _("Perlu perhatian")
        elif groups:
            status, label = "cek", _("Sebagian perlu dicek")
        else:
            status, label = "sehat", _("Sehat")
        groups.sort(key=lambda g: (g["severity"] != CRITICAL, -g["count"]))
        return {
            "groups": groups,
            "critical": critical,
            "attention": attention,
            "status": status,
            "status_label": str(label),
            "work_area": self.area is not None,
            "checked_at": timezone.localtime().isoformat(),
            "ai_available": ai.enabled(),
        }


def data_audit(user) -> dict:
    """Pemeriksaan kelengkapan & kewajaran data dalam cakupan pengguna."""
    if not user.has_perm("operasi.run_data_audit"):
        raise PermissionDenied
    audit = _Audit(user)
    audit.geotech()
    audit.plots()
    audit.residents()
    audit.activities()
    audit.officers()
    return audit.result()


AUDIT_PROMPT = (
    "Anda auditor data internal tim pengelolaan lahan. Berdasarkan TEMUAN hasil "
    "pemeriksaan sistem berikut (fakta, bukan dugaan), tulis ringkasan kesehatan "
    "data dan urutan prioritas tindakan. Hanya bahas temuan yang diberikan, jangan "
    "menambah angka atau temuan baru. Bahasa Indonesia, ringkas, maksimal 8 poin.\n\n"
    "STATUS: {status}. Kritis={critical}, perhatian={attention}.\nTEMUAN:\n{lines}"
)


def audit_summary(user, result: dict) -> str:
    """Ringkasan AI dari temuan audit (deterministik) — tidak menambah data baru."""
    if not ai.enabled():
        raise ValidationError(
            {"ai": [_("AI belum dikonfigurasi (ANTHROPIC_API_KEY kosong).")]}
        )
    use_ai_quota(user)
    lines = (
        "\n".join(
            f"- [{g['severity'].upper()}] {g['label']}: {g['count']}"
            + (f" (contoh: {', '.join(g['sample'])})" if g["sample"] else "")
            for g in result["groups"]
        )
        or "(tidak ada temuan)"
    )
    response = ai.create(
        max_tokens=1500,
        messages=[
            {
                "role": "user",
                "content": AUDIT_PROMPT.format(
                    status=result["status_label"],
                    critical=result["critical"],
                    attention=result["attention"],
                    lines=lines,
                ),
            }
        ],
    )
    return ai.text_of(response).strip()


# --------------------------------------------------------------------------
# Sinkron Excel lengkap
# --------------------------------------------------------------------------

KORWIL_HEADERS = [
    "Korwil",
    "Nama",
    "Warga",
    "Mendukung",
    "Menolak",
    "Netral / belum tahu",
    "Bidang",
    "Bidang dikuasai",
    "Luas bidang (ha)",
    "Luas dikuasai (ha)",
    "Titik uji PLTS",
    "Titik uji selesai",
]


def _resident_counts(user) -> Counter:
    counts = Counter()
    if user.has_perm("operasi.view_resident"):
        for row in (
            geo.scoped(Resident.objects.all(), user)
            .values("korwil", "stance")
            .annotate(n=Count("pk"))
        ):
            counts[(row["korwil"], row["stance"])] += row["n"]
    return counts


def _plot_counts(user) -> Counter:
    counts = Counter()
    if not user.has_perm("operasi.view_landplot"):
        return counts
    for row in spatial.visible_plots(user).values(
        "korwil", "control_status", "official_area_ha", "measured_area_ha"
    ):
        key = row["korwil"]
        area = row["official_area_ha"]
        if area is None:
            area = row["measured_area_ha"]
        area = float(area or 0)
        counts[(key, "n")] += 1
        counts[(key, "ha")] += area
        if row["control_status"] == enums.ControlStatus.CONTROLLED:
            counts[(key, "ok")] += 1
            counts[(key, "ok_ha")] += area
    return counts


def _point_counts(user) -> Counter:
    counts = Counter()
    if user.has_perm("operasi.view_geotechpoint"):
        for row in geotech.visible_points(user).values("korwil", "work_status"):
            counts[(row["korwil"], "n")] += 1
            if row["work_status"] == enums.GeotechWorkStatus.DONE:
                counts[(row["korwil"], "ok")] += 1
    return counts


def _korwil_rows(user):
    from asetlahan.enums import Stance

    korwils = list(geo.visible_korwils(user).order_by("code"))
    residents = _resident_counts(user)
    plots = _plot_counts(user)
    points = _point_counts(user)
    for k in korwils:
        total = sum(n for (kid, _s), n in residents.items() if kid == k.pk)
        yield [
            k.code,
            k.name,
            total,
            residents[(k.pk, Stance.SUPPORT)],
            residents[(k.pk, Stance.OPPOSE)],
            total
            - residents[(k.pk, Stance.SUPPORT)]
            - residents[(k.pk, Stance.OPPOSE)],
            plots[(k.pk, "n")],
            plots[(k.pk, "ok")],
            round(plots[(k.pk, "ha")], 4),
            round(plots[(k.pk, "ok_ha")], 4),
            points[(k.pk, "n")],
            points[(k.pk, "ok")],
        ]


PLOT_HEADERS = [
    "Nomor",
    "Nama bidang",
    "Korwil",
    "Pemilik",
    "Penjaga",
    "Status",
    "Urgensi",
    "Luas (ha)",
    "Zona",
    "Skor prioritas",
    "Tanggal dikuasai",
    "Tim",
]


def _plot_rows(user):
    for r in spatial.plot_rows(
        spatial.visible_plots(user)
        .select_related("korwil", "resident")
        .order_by("number")[:20000]
    ):
        yield [
            r["number"],
            r["name"],
            r["korwil"],
            r["owner"],
            r["guard"],
            r["status_label"],
            r["urgency_label"],
            r["area_ha"],
            r["zone_label"],
            r["score"],
            r["controlled_on"],
            r["team"],
        ]


def full_workbook(user) -> bytes:
    """Satu berkas Excel berisi ringkasan Korwil, bidang lahan, titik uji PLTS,
    dan (untuk pengelola) tiket — semuanya terbatas pada cakupan pengguna."""
    from operasi.recap import _Book

    book = _Book()
    book.table("Ringkasan Korwil", KORWIL_HEADERS, _korwil_rows(user), {1: 24})
    if user.has_perm("operasi.view_landplot"):
        book.table("Bidang lahan", PLOT_HEADERS, _plot_rows(user), {1: 26, 3: 22})
    if user.has_perm("operasi.view_geotechpoint"):
        geotech.add_sheet(book, geotech.visible_points(user).order_by("batch", "code"))
    if can_handle_tickets(user):
        book.table(
            "Tiket",
            TICKET_HEADERS,
            ticket_sheet_rows(visible_tickets(user)[:20000]),
            {2: 30, 3: 50, 11: 40},
        )
    return book.close()
