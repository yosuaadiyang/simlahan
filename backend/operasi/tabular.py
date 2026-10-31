"""Pembaca tabel sederhana untuk impor & analisis: .xlsx dan .csv.

Hanya pustaka standar + lxml (tanpa entitas eksternal) agar aman terhadap
berkas yang dibuat-buat: ukuran isi zip dibatasi dan entitas XML tidak
diselesaikan. Nilai dikembalikan sebagai teks; angka seri tanggal Excel dapat
diubah dengan :func:`excel_date`.
"""

import csv
import datetime
import io
import posixpath
import re
import zipfile

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

MAX_ROWS = 20_000
MAX_COLUMNS = 200
MAX_UNCOMPRESSED = 60 * 1024 * 1024
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
CELL_REF = re.compile(r"^([A-Z]{1,3})(\d+)$")


def _parse_xml(data: bytes):
    from lxml import etree

    parser = etree.XMLParser(
        resolve_entities=False, no_network=True, huge_tree=False, recover=False
    )
    try:
        return etree.fromstring(data, parser)
    except etree.XMLSyntaxError:
        raise ValidationError({"berkas": [_("Berkas Excel rusak atau tidak sah.")]})


def _column_index(letters: str) -> int:
    value = 0
    for ch in letters:
        value = value * 26 + (ord(ch) - 64)
    return value - 1


def _text(node) -> str:
    """Teks elemen <si>/<is>: gabungan semua <t>, kecuali teks fonetik <rPh>."""
    parts = []
    for t in node.iter(f"{NS}t"):
        parent = t.getparent()
        if parent is not None and parent.tag == f"{NS}rPh":
            continue
        parts.append(t.text or "")
    return "".join(parts)


def _sheet_path(book: zipfile.ZipFile, sheet_name: str | None) -> tuple[str, str]:
    workbook = _parse_xml(book.read("xl/workbook.xml"))
    rels = _parse_xml(book.read("xl/_rels/workbook.xml.rels"))
    targets = {
        rel.get("Id"): rel.get("Target", "")
        for rel in rels.iter(f"{PKG_REL_NS}Relationship")
    }
    sheets = [
        (sheet.get("name", ""), targets.get(sheet.get(f"{REL_NS}id"), ""))
        for sheet in workbook.iter(f"{NS}sheet")
    ]
    if not sheets:
        raise ValidationError({"berkas": [_("Berkas Excel tidak berisi lembar.")]})
    chosen = sheets[0]
    if sheet_name:
        wanted = sheet_name.strip().lower()
        for item in sheets:
            if item[0].strip().lower() == wanted:
                chosen = item
                break
    target = chosen[1]
    if target.startswith("/"):
        path = target.lstrip("/")
    else:
        path = posixpath.normpath(posixpath.join("xl", target))
    return chosen[0], path


def _cell_value(cell, shared: list[str]):
    kind = cell.get("t", "n")
    v = cell.find(f"{NS}v")
    raw = v.text if v is not None and v.text is not None else ""
    if kind == "s":
        try:
            return shared[int(raw)]
        except (ValueError, IndexError):
            return ""
    if kind == "inlineStr":
        node = cell.find(f"{NS}is")
        return _text(node) if node is not None else ""
    if kind == "b":
        return raw == "1"
    if kind in ("str", "e"):
        return raw
    try:
        number = float(raw)
    except ValueError:
        return ""
    return int(number) if number.is_integer() else number


def _row_values(row, shared: list[str]) -> list:
    values: dict[int, object] = {}
    position = 0
    for cell in row.iter(f"{NS}c"):
        match = CELL_REF.match(cell.get("r", ""))
        column = _column_index(match[1]) if match else position
        position = column + 1
        if column < MAX_COLUMNS:
            values[column] = _cell_value(cell, shared)
    width = max(values) + 1 if values else 0
    return [values.get(i, "") for i in range(width)]


def _too_many_rows():
    return ValidationError({"berkas": [_("Maksimal %(n)s baris.") % {"n": MAX_ROWS}]})


def _open_sheet(data: bytes, sheet_name: str | None):
    try:
        book = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValidationError({"berkas": [_("Berkas Excel rusak atau tidak sah.")]})
    with book:
        if sum(info.file_size for info in book.infolist()) > MAX_UNCOMPRESSED:
            raise ValidationError({"berkas": [_("Isi berkas Excel terlalu besar.")]})
        try:
            name, path = _sheet_path(book, sheet_name)
            shared = []
            if "xl/sharedStrings.xml" in book.namelist():
                strings = _parse_xml(book.read("xl/sharedStrings.xml"))
                shared = [_text(si) for si in strings.iter(f"{NS}si")]
            sheet = _parse_xml(book.read(path))
        except KeyError:
            raise ValidationError({"berkas": [_("Berkas Excel rusak atau tidak sah.")]})
    return name, shared, sheet


def read_xlsx(data: bytes, sheet_name: str | None = None) -> tuple[str, list[list]]:
    """(nama lembar, baris) dari lembar pilihan (atau lembar pertama)."""
    name, shared, sheet = _open_sheet(data, sheet_name)
    rows: list[list] = []
    for row in sheet.iter(f"{NS}row"):
        index = row.get("r", "")
        if index.isdigit():
            if int(index) > MAX_ROWS + 1:
                raise _too_many_rows()
            while len(rows) < int(index) - 1:
                rows.append([])
        rows.append(_row_values(row, shared))
        if len(rows) > MAX_ROWS + 1:
            raise _too_many_rows()
    return name, rows


def read_csv(data: bytes) -> list[list]:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:4096]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    if sample.count("\t") > max(sample.count(";"), sample.count(",")):
        delimiter = "\t"
    rows = []
    for row in csv.reader(io.StringIO(text), delimiter=delimiter):
        rows.append(row[:MAX_COLUMNS])
        if len(rows) > MAX_ROWS + 1:
            raise _too_many_rows()
    return rows


def read_table(name: str, data: bytes, sheet_name: str | None = None):
    """(nama lembar, baris) dari .xlsx/.csv/.tsv/.txt; galat ValidationError."""
    extension = (name or "").lower().rsplit(".", 1)[-1]
    if extension in ("xlsx", "xlsm"):
        return read_xlsx(data, sheet_name)
    if extension in ("csv", "tsv", "txt"):
        return "", read_csv(data)
    raise ValidationError(
        {
            "berkas": [
                _(
                    "Format berkas harus .xlsx atau .csv. Berkas Excel lama (.xls) "
                    "simpan ulang sebagai .xlsx."
                )
            ]
        }
    )


def cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return _("Ya") if value else _("Tidak")
    if isinstance(value, float):
        return f"{value:.10g}"
    return " ".join(str(value).split())


def excel_date(value) -> datetime.date | None:
    """Tanggal dari seri Excel (angka) atau teks ISO/dd-mm-yyyy/dd/mm/yyyy."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 20_000 <= value <= 80_000:
            return datetime.date(1899, 12, 30) + datetime.timedelta(days=int(value))
        return None
    text = str(value).strip()[:10]
    for pattern in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return datetime.datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def number(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip().replace(" ", "").rstrip("%")
    if not text:
        return None
    if text.count(",") == 1 and text.count(".") == 0:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None
