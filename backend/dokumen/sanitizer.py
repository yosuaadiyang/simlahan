"""Pembersih HTML berbasis daftar izin untuk isi templat & dokumen.

Isi dokumen ditulis petugas lewat editor atau diimpor dari Word/HTML, lalu
ditampilkan di portal dan dicetak ke PDF. Hanya tag, atribut, dan gaya yang
aman yang dipertahankan; skrip, event handler, iframe, form, dan URL berbahaya
dibuang. Teks di luar tag selalu di-escape ulang.
"""

import re
from html import escape
from html.parser import HTMLParser

ALLOWED_TAGS = {
    "a",
    "b",
    "blockquote",
    "br",
    "caption",
    "col",
    "colgroup",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "hr",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "s",
    "small",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
}
VOID_TAGS = {"br", "hr", "img", "col"}
# Isi tag ini dibuang seluruhnya, bukan hanya tagnya.
DROP_CONTENT_TAGS = {"script", "style", "iframe", "object", "embed", "noscript", "template", "svg", "math", "head", "title", "textarea", "select"}

ALLOWED_ATTRS = {
    "*": {"style", "class"},
    "a": {"href", "title"},
    "img": {"src", "alt", "width", "height"},
    "td": {"colspan", "rowspan", "width"},
    "th": {"colspan", "rowspan", "width", "scope"},
    "col": {"span", "width"},
    "table": {"width", "border", "cellpadding", "cellspacing"},
    "ol": {"start", "type"},
}
ALLOWED_CLASSES = {"page-break", "merge-field", "text-center", "text-right"}
ALLOWED_STYLES = {
    "text-align",
    "font-weight",
    "font-style",
    "font-size",
    "text-decoration",
    "color",
    "background-color",
    "width",
    "height",
    "border",
    "border-top",
    "border-bottom",
    "border-left",
    "border-right",
    "border-collapse",
    "padding",
    "padding-left",
    "padding-right",
    "margin-left",
    "margin-top",
    "margin-bottom",
    "vertical-align",
    "line-height",
    "page-break-before",
    "page-break-after",
    "list-style-type",
}
SAFE_STYLE_VALUE = re.compile(r"^[#a-zA-Z0-9.%,()\s\-]+$")
SAFE_NUMBER = re.compile(r"^\d{1,4}%?$")
SAFE_HREF = re.compile(r"^(https?://|mailto:|#)", re.IGNORECASE)
SAFE_IMG = re.compile(r"^data:image/(png|jpeg|gif);base64,[A-Za-z0-9+/=\s]+$")


def _clean_style(value: str) -> str:
    kept = []
    for declaration in value.split(";"):
        if ":" not in declaration:
            continue
        name, _, raw = declaration.partition(":")
        name = name.strip().lower()
        raw = raw.strip()
        lowered = raw.lower()
        if (
            name in ALLOWED_STYLES
            and raw
            and SAFE_STYLE_VALUE.match(raw)
            and "url" not in lowered
            and "expression" not in lowered
        ):
            kept.append(f"{name}: {raw}")
    return "; ".join(kept)


def _clean_attr(tag: str, name: str, value: str) -> str | None:
    value = (value or "").strip()
    if name == "style":
        return _clean_style(value) or None
    if name == "class":
        classes = [c for c in value.split() if c in ALLOWED_CLASSES]
        return " ".join(classes) or None
    if name == "href":
        return value if SAFE_HREF.match(value) else None
    if name == "src":
        return value if SAFE_IMG.match(value) else None
    if name in {"colspan", "rowspan", "span", "start", "border", "cellpadding", "cellspacing"}:
        return value if value.isdigit() and len(value) <= 3 else None
    if name in {"width", "height"}:
        return value if SAFE_NUMBER.match(value) else None
    if name == "type":
        return value if value in {"1", "a", "A", "i", "I"} else None
    if name == "scope":
        return value if value in {"row", "col"} else None
    return value[:255]


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.open: list[str] = []
        self.drop_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in DROP_CONTENT_TAGS:
            if tag not in VOID_TAGS:
                self.drop_depth += 1
            return
        if self.drop_depth or tag not in ALLOWED_TAGS:
            return
        allowed = ALLOWED_ATTRS["*"] | ALLOWED_ATTRS.get(tag, set())
        parts = [tag]
        for name, value in attrs:
            name = (name or "").lower()
            if name not in allowed:
                continue
            cleaned = _clean_attr(tag, name, value or "")
            if cleaned is not None:
                parts.append(f'{name}="{escape(cleaned, quote=True)}"')
        if tag == "a":
            parts.append('rel="noopener noreferrer"')
        if tag == "img" and not any(p.startswith("src=") for p in parts[1:]):
            return
        self.out.append(f"<{' '.join(parts)}>")
        if tag not in VOID_TAGS:
            self.open.append(tag)

    def handle_startendtag(self, tag, attrs):
        if tag.lower() in DROP_CONTENT_TAGS:
            return
        self.handle_starttag(tag, attrs)
        tag = tag.lower()
        if tag not in VOID_TAGS and self.open and self.open[-1] == tag:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in DROP_CONTENT_TAGS:
            self.drop_depth = max(self.drop_depth - 1, 0)
            return
        if self.drop_depth or tag not in ALLOWED_TAGS or tag in VOID_TAGS:
            return
        if tag not in self.open:
            return
        # Tutup tag yang belum ditutup di dalamnya agar struktur tetap sah.
        while self.open:
            current = self.open.pop()
            self.out.append(f"</{current}>")
            if current == tag:
                break

    def handle_data(self, data):
        if not self.drop_depth:
            self.out.append(escape(data, quote=False))

    def result(self) -> str:
        while self.open:
            self.out.append(f"</{self.open.pop()}>")
        return "".join(self.out)


def sanitize_html(value: str) -> str:
    parser = _Sanitizer()
    parser.feed(value or "")
    parser.close()
    return parser.result().strip()


def html_to_text(value: str) -> str:
    """Teks polos (untuk pencarian/ringkasan)."""

    class _Text(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []
            self.skip = 0

        def handle_starttag(self, tag, attrs):
            if tag in DROP_CONTENT_TAGS:
                self.skip += 1
            elif tag in {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
                self.parts.append("\n")

        def handle_endtag(self, tag):
            if tag in DROP_CONTENT_TAGS:
                self.skip = max(self.skip - 1, 0)

        def handle_data(self, data):
            if not self.skip:
                self.parts.append(data)

    parser = _Text()
    parser.feed(value or "")
    parser.close()
    return re.sub(r"\n\s*\n+", "\n\n", "".join(parser.parts)).strip()
