"""Buku panduan per peran di ``docs/panduan/peran/``.

Setiap buku berisi tulisan bebas (langkah kerja, gambar, tautan ke bab) dan
satu blok yang dibuat dari :mod:`users.role_guide` di antara penanda
``BLOCK_START`` dan ``BLOCK_END``. Blok itu diperbarui dengan
``python manage.py panduan_buku`` agar buku selalu sama dengan panduan peran
di aplikasi; ``--cek`` hanya memeriksa.
"""

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
        updated = replace_block(text, guide)
        if updated != text:
            changed.append(path)
            if write:
                path.write_text(updated, encoding="utf-8")
    return changed
