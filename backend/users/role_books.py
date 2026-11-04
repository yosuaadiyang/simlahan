"""Buku panduan per peran di ``docs/panduan/peran/``.

Setiap buku berisi tulisan bebas (langkah kerja, gambar, tautan ke bab) dan
satu blok yang dibuat dari :mod:`users.role_guide` di antara penanda
``BLOCK_START`` dan ``BLOCK_END``. Blok itu diperbarui dengan
``python manage.py panduan_buku`` agar buku selalu sama dengan panduan peran
di aplikasi; ``--cek`` hanya memeriksa.

Agar setiap buku peran cukup dibaca sendiri, langkah kerja dari bab disalin
ke buku lewat penanda sisipan::

    <!-- sisip: 51-portal-pemohon.md#133-mengajukan-permohonan-alokasi -->
    <!-- akhir sisip -->

``panduan_buku`` mengisi di antara keduanya bagian bab itu (judul sampai
judul berikutnya yang setingkat), dengan judul diturunkan ke tingkat ###
dan alamat gambar/tautan disesuaikan untuk folder ``peran/``. Bab tetap satu
sumber: ubah bab, lalu jalankan ``panduan_buku``.
"""

import re
from pathlib import Path

from users.role_guide import (
    APPLICANT_GUIDE,
    INVESTOR_GUIDE,
    ROLE_GUIDES,
    RoleGuide,
)
from utils.group_permissions import UserGroup

MANUAL_DIR = Path(__file__).resolve().parents[2] / "docs" / "panduan"
BOOK_DIR = MANUAL_DIR / "peran"

BLOCK_START = (
    "<!-- awal: dibuat dari backend/users/role_guide.py; "
    "perbarui dengan: cd backend && python manage.py panduan_buku -->"
)
BLOCK_END = "<!-- akhir: blok role_guide.py -->"

BOOK_FILES: dict[UserGroup, str] = {
    UserGroup.SELAILIJA: "penelusur.md",
    UserGroup.VALMISTELIJA: "penyusun.md",
    UserGroup.SOPIMUSVALMISTELIJA: "penyusun-kontrak.md",
    UserGroup.SYOTTAJA: "operator-entri-data.md",
    UserGroup.PERINTALAKIMIES: "ahli-hukum-penagihan.md",
    UserGroup.LASKUTTAJA: "petugas-penagihan.md",
    UserGroup.PAAKAYTTAJA: "administrator.md",
    UserGroup.PELAKSANA_PENGADAAN: "pelaksana-pengadaan-tanah.md",
    UserGroup.SATGAS_PENGADAAN: "satgas-pengadaan-tanah.md",
    UserGroup.PENILAI: "penilai-pertanahan.md",
    UserGroup.INSTANSI_PEMOHON: "instansi-yang-memerlukan-tanah.md",
    UserGroup.PETUGAS_ALOKASI: "petugas-alokasi-lahan.md",
    UserGroup.TIM_VERIFIKASI: "tim-verifikasi-teknis.md",
    UserGroup.PETUGAS_ASET: "petugas-aset-lahan.md",
    UserGroup.PETUGAS_HUKUM: "petugas-hukum.md",
    UserGroup.PETUGAS_LAPANGAN: "petugas-lapangan.md",
    UserGroup.KOORDINATOR_WILAYAH: "koordinator-wilayah.md",
}
PORTAL_BOOK_FILES: tuple[tuple[RoleGuide, str], ...] = (
    (APPLICANT_GUIDE, "pemohon.md"),
    (INVESTOR_GUIDE, "investor.md"),
)


def books() -> list[tuple[RoleGuide, Path]]:
    pairs = [
        (ROLE_GUIDES[group], BOOK_DIR / name) for group, name in BOOK_FILES.items()
    ]
    pairs += [(guide, BOOK_DIR / name) for guide, name in PORTAL_BOOK_FILES]
    return pairs


def render_block(guide: RoleGuide) -> str:
    lines = [
        BLOCK_START,
        "",
        "## Ringkasan peran",
        "",
        guide.summary,
        "",
        f"- **Cara masuk:** {guide.login}",
        f"- **Halaman awal:** {guide.home}",
        f"- **Akun latihan** (hanya di sistem latihan berisi data contoh): "
        f"`{guide.sample}`",
        "",
        "### Menu yang Anda lihat",
        "",
    ]
    lines += [f"- {item}" for item in guide.menus]
    lines += ["", "### Yang bisa Anda lakukan", ""]
    lines += [f"- {item}" for item in guide.can]
    lines += ["", "### Batas akses", ""]
    lines += [f"- {item}" for item in guide.limits]
    lines += ["", BLOCK_END]
    return "\n".join(lines)


def replace_block(text: str, guide: RoleGuide) -> str:
    start = text.find(BLOCK_START)
    end = text.find(BLOCK_END)
    if start == -1 or end == -1 or end < start:
        raise ValueError("penanda blok role_guide.py tidak ditemukan")
    return text[:start] + render_block(guide) + text[end + len(BLOCK_END) :]


def sync(write: bool = True) -> list[Path]:
    """Perbarui blok di setiap buku; kembalikan buku yang berubah/berbeda."""
    changed = []
    for guide, path in books():
        text = path.read_text(encoding="utf-8")
        updated = fill_includes(replace_block(text, guide))
        if updated != text:
            changed.append(path)
            if write:
                path.write_text(updated, encoding="utf-8")
    return changed


INCLUDE_RE = re.compile(
    r"(<!-- sisip: (?P<file>[\w.-]+\.md)#(?P<anchor>[\w-]+) -->\n)"
    r"(?P<body>.*?)"
    r"(<!-- akhir sisip -->)",
    re.S,
)
HEADING_RE = re.compile(r"^(#{1,6}) (.+?)\s*$")
LINK_RE = re.compile(r"(!?\[[^\]]*\])\(([^)\s]+)\)")
INCLUDE_LEVEL = 3


def heading_slug(heading: str) -> str:
    """Jangkar judul seperti GitHub (sama dengan tautan di buku panduan)."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def chapter_section(name: str, anchor: str) -> list[str]:
    """Baris bagian bab ``name`` mulai judul ``#anchor`` (tanpa blok kode)."""
    lines = (MANUAL_DIR / name).read_text(encoding="utf-8").splitlines()
    start = level = None
    fence = False
    seen: dict[str, int] = {}
    for i, line in enumerate(lines):
        if line.startswith("```"):
            fence = not fence
            continue
        match = None if fence else HEADING_RE.match(line)
        if not match:
            continue
        depth = len(match.group(1))
        if start is not None:
            if depth <= level:
                return lines[start:i]
            continue
        slug = heading_slug(match.group(2))
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        if (slug if count == 0 else f"{slug}-{count}") == anchor:
            start, level = i, depth
    if start is None:
        raise ValueError(f"jangkar #{anchor} tidak ada di {name}")
    return lines[start:]


def _relink(line: str, name: str) -> str:
    def fix(match):
        label, target = match.groups()
        if re.match(r"^[a-z]+:", target):
            return match.group(0)
        if target.startswith("#"):
            target = name + target
        if not target.startswith("../"):
            target = "../" + target
        return f"{label}({target})"

    return LINK_RE.sub(fix, line)


def render_include(name: str, anchor: str) -> str:
    section = chapter_section(name, anchor)
    shift = INCLUDE_LEVEL - len(HEADING_RE.match(section[0]).group(1))
    out = []
    fence = False
    for line in section:
        if line.startswith("```"):
            fence = not fence
        match = None if fence else HEADING_RE.match(line)
        if match:
            depth = min(6, max(1, len(match.group(1)) + shift))
            line = "#" * depth + " " + match.group(2)
        elif not fence:
            line = _relink(line, name)
        out.append(line)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out) + "\n"


def fill_includes(text: str) -> str:
    def fill(match):
        body = render_include(match.group("file"), match.group("anchor"))
        return match.group(1) + "\n" + body + "\n" + match.group(5)

    return INCLUDE_RE.sub(fill, text)
