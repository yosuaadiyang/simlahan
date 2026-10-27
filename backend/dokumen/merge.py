"""Isian otomatis templat dan impor templat dari Word/HTML.

Isian ditulis ``{{ grup.nama }}`` (mis. ``{{ pemohon.nama }}``). Pada templat
HTML nilai di-escape lalu disisipkan; ``{{ blok.<kode> }}`` menyisipkan blok
dari pustaka konten; ``{{ isian.<kunci> }}`` diisi petugas saat membuat
dokumen. Templat Word dirender dengan docxtpl di lingkungan Jinja tersandbox
(tanpa akses atribut Python) memakai nama isian yang sama.
"""

import io
import re
from html import escape

from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from alokasi.templatetags.alokasi_tags import angka, rupiah, tanggal
from dokumen.sanitizer import sanitize_html

FIELD_RE = re.compile(r"\{\{\s*([a-z_]+)\.([a-z0-9_]+)\s*\}\}")
CUSTOM_KEY_RE = re.compile(r"^[a-z0-9_]{1,40}$")
MAX_DOCX_BYTES = 20 * 1024 * 1024

# Katalog isian untuk editor, dokumentasi, dan pratinjau.
FIELD_GROUPS = (
    (
        "pemohon",
        gettext_lazy("Pemegang hak / pemohon"),
        (
            ("nama", "Nama pemegang hak"),
            ("jenis", "Jenis pemohon"),
            ("nib", "NIB"),
            ("npwp", "NPWP"),
            ("penanggung_jawab", "Nama penanggung jawab"),
            ("jabatan", "Jabatan penanggung jawab"),
            ("alamat", "Alamat"),
            ("kota", "Kota"),
            ("telepon", "Telepon"),
            ("email", "Surel"),
        ),
    ),
    (
        "pemanfaatan",
        gettext_lazy("Pemanfaatan lahan"),
        (
            ("nomor", "Nomor pemanfaatan"),
            ("nama", "Nama kegiatan / proyek"),
            ("skema", "Skema"),
            ("referensi", "Nomor dasar hak / kontrak"),
            ("luas", "Luas (m²)"),
            ("sektor", "Sektor"),
            ("mulai", "Tanggal mulai"),
            ("berakhir", "Tanggal berakhir"),
        ),
    ),
    (
        "lahan",
        gettext_lazy("Lahan"),
        (
            ("kode", "Kode lahan"),
            ("nama", "Nama / lokasi"),
            ("kecamatan", "Kecamatan"),
            ("kelurahan", "Kelurahan"),
            ("alamat", "Alamat"),
            ("luas", "Luas lahan (m²)"),
            ("peruntukan", "Peruntukan"),
            ("zonasi", "Zonasi"),
        ),
    ),
    (
        "alokasi",
        gettext_lazy("Alokasi"),
        (
            ("kpt", "Nomor KPT"),
            ("ppt", "Nomor PPT"),
            ("terbit", "Tanggal terbit"),
            ("berakhir", "Berlaku sampai"),
        ),
    ),
    (
        "investasi",
        gettext_lazy("Investasi / sewa"),
        (
            ("nomor", "Nomor permintaan"),
            ("proyek", "Nama proyek"),
            ("nilai", "Nilai investasi"),
            ("tenaga_kerja", "Tenaga kerja"),
            ("tarif", "Tarif per m² per tahun"),
            ("jangka", "Jangka waktu (tahun)"),
            ("total", "Total nilai penawaran"),
        ),
    ),
    (
        "izin",
        gettext_lazy("Dokumen perizinan"),
        (
            ("jenis", "Jenis dokumen"),
            ("nomor", "Nomor dokumen"),
            ("terbit", "Tanggal terbit"),
            ("berlaku", "Berlaku sampai"),
            ("penerbit", "Instansi penerbit"),
        ),
    ),
    (
        "instansi",
        gettext_lazy("Instansi"),
        (
            ("nama", "Nama instansi"),
            ("singkatan", "Nama singkat"),
            ("kota", "Kota"),
            ("pejabat", "Nama pejabat penandatangan"),
            ("jabatan", "Jabatan pejabat"),
        ),
    ),
    (
        "dokumen",
        gettext_lazy("Dokumen ini"),
        (("nomor", "Nomor dokumen"), ("judul", "Judul dokumen")),
    ),
    (
        "tanggal",
        gettext_lazy("Tanggal"),
        (("hari_ini", "Tanggal hari ini"), ("tahun", "Tahun berjalan")),
    ),
)
KNOWN_KEYS = {
    f"{group}.{name}" for group, _label, fields in FIELD_GROUPS for name, _l in fields
}


def _text(value) -> str:
    if value is None:
        return ""
    return str(value)


def _applicant_fields(applicant, fallback_name: str = "") -> dict:
    if applicant is None:
        return {"pemohon.nama": fallback_name}
    return {
        "pemohon.nama": applicant.name,
        "pemohon.jenis": applicant.get_applicant_type_display(),
        "pemohon.nib": applicant.nib,
        "pemohon.npwp": applicant.npwp,
        "pemohon.penanggung_jawab": applicant.pic_name,
        "pemohon.jabatan": applicant.pic_position,
        "pemohon.alamat": applicant.address,
        "pemohon.kota": applicant.city,
        "pemohon.telepon": applicant.phone,
        "pemohon.email": applicant.user.email if applicant.user_id else "",
    }


def _plot_fields(plot) -> dict:
    if plot is None:
        return {}
    return {
        "lahan.kode": plot.code,
        "lahan.nama": plot.name,
        "lahan.kecamatan": plot.district,
        "lahan.kelurahan": plot.village,
        "lahan.alamat": plot.address,
        "lahan.luas": angka(plot.area_m2, 2),
        "lahan.peruntukan": plot.intended_use,
        "lahan.zonasi": plot.zoning,
    }


def _land_use_fields(land_use) -> dict:
    data = {
        "pemanfaatan.nomor": land_use.number,
        "pemanfaatan.nama": land_use.title,
        "pemanfaatan.skema": land_use.get_scheme_display(),
        "pemanfaatan.referensi": land_use.reference,
        "pemanfaatan.luas": (
            angka(land_use.area_m2, 2) if land_use.area_m2 is not None else ""
        ),
        "pemanfaatan.sektor": land_use.sector.name if land_use.sector_id else "",
        "pemanfaatan.mulai": (
            tanggal(land_use.start_date) if land_use.start_date else ""
        ),
        "pemanfaatan.berakhir": tanggal(land_use.end_date) if land_use.end_date else "",
    }
    data.update(_applicant_fields(land_use.holder, land_use.holder_name))
    data.update(_plot_fields(land_use.plot))
    allocation = land_use.allocation
    if allocation is not None:
        data.update(
            {
                "alokasi.kpt": allocation.kpt_number,
                "alokasi.ppt": allocation.ppt_number,
                "alokasi.terbit": tanggal(allocation.issued_date),
                "alokasi.berakhir": tanggal(allocation.end_date),
            }
        )
    investment = land_use.investment
    if investment is not None:
        data.update(
            {
                "investasi.nomor": investment.number,
                "investasi.proyek": investment.project_name,
                "investasi.nilai": (
                    rupiah(investment.investment_value)
                    if investment.investment_value is not None
                    else ""
                ),
                "investasi.tenaga_kerja": _text(investment.workforce),
                "investasi.tarif": (
                    rupiah(investment.offer_rate_per_m2_year)
                    if investment.offer_rate_per_m2_year is not None
                    else ""
                ),
                "investasi.jangka": _text(investment.offer_term_years),
                "investasi.total": (
                    rupiah(investment.offer_total)
                    if investment.offer_total is not None
                    else ""
                ),
            }
        )
    return data


def build_context(*, land_use=None, record=None, document=None, extra=None) -> dict:
    """Nilai isian (kunci "grup.nama" → teks) untuk satu dokumen."""
    from alokasi.models import AllocationSettings

    config = AllocationSettings.load()
    today = timezone.localdate()
    data = {key: "" for key in KNOWN_KEYS}
    data.update(
        {
            "instansi.nama": config.authority_name,
            "instansi.singkatan": config.authority_short_name,
            "instansi.kota": config.city,
            "instansi.pejabat": config.signatory_name,
            "instansi.jabatan": config.signatory_title,
            "tanggal.hari_ini": tanggal(today),
            "tanggal.tahun": str(today.year),
        }
    )
    if record is not None and land_use is None:
        land_use = record.land_use
    if land_use is not None:
        data.update(_land_use_fields(land_use))
    if record is not None:
        data.update(
            {
                "izin.jenis": record.permit_type.name,
                "izin.nomor": record.number,
                "izin.terbit": (
                    tanggal(record.issued_date) if record.issued_date else ""
                ),
                "izin.berlaku": (
                    tanggal(record.expiry_date) if record.expiry_date else ""
                ),
                "izin.penerbit": record.permit_type.issuer,
            }
        )
    if document is not None:
        data.update({"dokumen.nomor": document.number, "dokumen.judul": document.title})
    for key, value in (extra or {}).items():
        if CUSTOM_KEY_RE.match(key):
            data[f"isian.{key}"] = _text(value)
    return {key: _text(value) for key, value in data.items()}


def sample_context() -> dict:
    """Contoh nilai untuk pratinjau templat tanpa data nyata."""
    data = build_context()
    for group, _label, fields in FIELD_GROUPS:
        for name, label in fields:
            key = f"{group}.{name}"
            if not data.get(key):
                data[key] = f"[{label}]"
    return data


def custom_fields(*texts: str) -> list[str]:
    """Kunci ``isian.*`` yang dipakai templat (diisi petugas saat membuat dokumen)."""
    keys = []
    for text in texts:
        for group, name in FIELD_RE.findall(text or ""):
            if group == "isian" and name not in keys:
                keys.append(name)
    return keys


def unknown_fields(text: str) -> list[str]:
    from dokumen.models import ContentBlock

    blocks = set(
        ContentBlock.objects.filter(is_active=True).values_list("code", flat=True)
    )
    found = []
    for group, name in FIELD_RE.findall(text or ""):
        key = f"{group}.{name}"
        if group == "isian" or key in KNOWN_KEYS:
            continue
        if group == "blok" and name in blocks:
            continue
        if key not in found:
            found.append(key)
    return found


def merge_html(body: str, context: dict, *, highlight_missing: bool = False) -> str:
    """Ganti isian pada HTML templat. Hasil selalu dibersihkan ulang."""
    from dokumen.models import ContentBlock

    blocks = {
        b.code: b.body
        for b in ContentBlock.objects.filter(is_active=True).only("code", "body")
    }

    def expand_blocks(text: str, depth: int = 0) -> str:
        def repl(match):
            group, name = match.groups()
            if group != "blok":
                return match.group(0)
            if name in blocks and depth < 3:
                return expand_blocks(sanitize_html(blocks[name]), depth + 1)
            return match.group(0)

        return FIELD_RE.sub(repl, text)

    def replace(match):
        group, name = match.groups()
        key = f"{group}.{name}"
        if key in context:
            value = context[key]
            if value:
                return escape(value).replace("\n", "<br>")
            if highlight_missing:
                return f'<span class="merge-field">[{escape(key)} kosong]</span>'
            return ""
        if highlight_missing:
            return f'<span class="merge-field">{escape(match.group(0))}</span>'
        return escape(match.group(0))

    return sanitize_html(FIELD_RE.sub(replace, expand_blocks(sanitize_html(body))))


def _nested(context: dict) -> dict:
    nested: dict[str, dict] = {}
    for key, value in context.items():
        group, _, name = key.partition(".")
        nested.setdefault(group, {})[name] = value
    return nested


class TemplateRenderError(ValueError):
    pass


def render_docx(data: bytes, context: dict) -> bytes:
    """Isi templat Word (.docx) dengan docxtpl di lingkungan Jinja tersandbox."""
    from docxtpl import DocxTemplate
    from jinja2 import TemplateError
    from jinja2.sandbox import SandboxedEnvironment

    if len(data) > MAX_DOCX_BYTES:
        raise TemplateRenderError(_("Berkas templat terlalu besar."))
    try:
        template = DocxTemplate(io.BytesIO(data))
        template.render(
            _nested(context), jinja_env=SandboxedEnvironment(), autoescape=True
        )
        output = io.BytesIO()
        template.save(output)
    except TemplateError as error:
        raise TemplateRenderError(
            _("Templat Word tidak valid: %s") % str(error)[:200]
        ) from error
    except Exception as error:  # noqa: BLE001 - berkas rusak/bukan docx
        raise TemplateRenderError(
            _("Berkas Word tidak dapat dibaca. Pastikan formatnya .docx yang sah.")
        ) from error
    return output.getvalue()


def docx_fields(data: bytes) -> list[str]:
    """Isian yang ditemukan di templat Word (untuk ditampilkan di panel)."""
    try:
        text = docx_to_html(data)
    except TemplateRenderError:
        return []
    return sorted({f"{g}.{n}" for g, n in FIELD_RE.findall(text)})


ALIGN = {1: "center", 2: "right", 3: "justify"}


def _run_html(run) -> str:
    text = escape(run.text or "")
    if not text:
        return ""
    if run.bold:
        text = f"<strong>{text}</strong>"
    if run.italic:
        text = f"<em>{text}</em>"
    if run.underline:
        text = f"<u>{text}</u>"
    return text


def _paragraph_html(paragraph) -> str:
    content = "".join(_run_html(run) for run in paragraph.runs) or ""
    style = (paragraph.style.name or "").lower() if paragraph.style is not None else ""
    align = (
        ALIGN.get(int(paragraph.alignment)) if paragraph.alignment is not None else None
    )
    attr = f' style="text-align: {align}"' if align else ""
    if style.startswith("heading 1") or style == "title":
        return f"<h1{attr}>{content}</h1>"
    if style.startswith("heading 2"):
        return f"<h2{attr}>{content}</h2>"
    if style.startswith("heading"):
        return f"<h3{attr}>{content}</h3>"
    if style.startswith("list"):
        return f"<li>{content}</li>"
    return f"<p{attr}>{content or '&nbsp;'}</p>"


def _table_html(table) -> str:
    rows = []
    for row in table.rows:
        cells = "".join(
            "<td>" + "".join(_paragraph_html(p) for p in cell.paragraphs) + "</td>"
            for cell in row.cells
        )
        rows.append(f"<tr>{cells}</tr>")
    return (
        '<table style="width: 100%; border-collapse: collapse" border="1">'
        + "".join(rows)
        + "</table>"
    )


def _open_docx(data: bytes):
    import docx

    if len(data) > MAX_DOCX_BYTES:
        raise TemplateRenderError(_("Berkas terlalu besar."))
    try:
        return docx.Document(io.BytesIO(data))
    except Exception as error:  # noqa: BLE001
        raise TemplateRenderError(
            _("Berkas Word tidak dapat dibaca. Pastikan formatnya .docx yang sah.")
        ) from error


def docx_to_html(data: bytes) -> str:
    """Ubah dokumen Word menjadi HTML sederhana untuk templat yang dapat diedit."""
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = _open_docx(data)
    parts: list[str] = []
    in_list = False
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            html = _paragraph_html(Paragraph(child, document))
        elif tag == "tbl":
            html = _table_html(Table(child, document))
        else:
            continue
        is_item = html.startswith("<li>")
        if is_item != in_list:
            parts.append("<ul>" if is_item else "</ul>")
            in_list = is_item
        parts.append(html)
    if in_list:
        parts.append("</ul>")
    return sanitize_html("".join(parts))
