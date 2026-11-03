"""Pemeriksaan buku panduan pengguna di ``docs/panduan/``."""

import re
from pathlib import Path
from urllib.parse import unquote

from users.role_books import BOOK_DIR, MANUAL_DIR, books, sync
from users.role_guide import ROLE_GUIDES

LINK_RE = re.compile(r"(!?)\[[^\]]*\]\(([^)\s]+)\)")
HEADING_RE = re.compile(r"^(#{1,6}) (.+?)\s*$")


def manual_files() -> list[Path]:
    return sorted(MANUAL_DIR.rglob("*.md"))


def strip_code(text: str) -> str:
    """Buang blok kode berpagar agar contoh di dalamnya tidak ikut diperiksa."""
    return re.sub(r"^```.*?^```", "", text, flags=re.M | re.S)


def github_slug(heading: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    seen: dict[str, int] = {}
    result = set()
    for line in strip_code(path.read_text(encoding="utf-8")).splitlines():
        match = HEADING_RE.match(line)
        if not match:
            continue
        slug = github_slug(match.group(2))
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        result.add(slug if count == 0 else f"{slug}-{count}")
    return result


def test_manual_exists():
    assert (MANUAL_DIR / "README.md").is_file()
    assert len(manual_files()) > 30


def test_every_role_has_a_book():
    paths = [path for _guide, path in books()]
    assert len(paths) == len(ROLE_GUIDES) + 2
    for path in paths:
        assert path.is_file(), f"buku peran belum ada: {path.name}"
    readme = (MANUAL_DIR / "README.md").read_text(encoding="utf-8")
    for path in paths:
        assert f"(peran/{path.name})" in readme, f"{path.name} tidak ada di README"
    extra = {p.name for p in BOOK_DIR.glob("*.md")} - {p.name for p in paths}
    assert not extra, f"buku peran tanpa peran: {extra}"


def test_role_books_match_role_guide():
    changed = sync(write=False)
    assert not changed, (
        "Ringkasan peran di buku panduan tidak sama dengan role_guide.py. "
        "Jalankan: cd backend && python manage.py panduan_buku"
    )


def test_images_and_links_resolve():
    anchor_cache: dict[Path, set[str]] = {}
    problems = []
    for path in manual_files():
        text = strip_code(path.read_text(encoding="utf-8"))
        for is_image, target in LINK_RE.findall(text):
            if re.match(r"^[a-z]+:", target):
                continue
            file_part, _, fragment = target.partition("#")
            dest = (path.parent / unquote(file_part)).resolve() if file_part else path
            rel = path.relative_to(MANUAL_DIR)
            if not dest.exists():
                problems.append(f"{rel}: {target} tidak ditemukan")
                continue
            if is_image:
                if dest.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".svg"}:
                    problems.append(f"{rel}: {target} bukan gambar")
                continue
            if fragment:
                if dest not in anchor_cache:
                    anchor_cache[dest] = anchors(dest)
                if fragment not in anchor_cache[dest]:
                    problems.append(f"{rel}: jangkar #{fragment} tidak ada")
    assert not problems, "\n".join(problems)


def test_every_image_is_used():
    used = set()
    for path in manual_files():
        for is_image, target in LINK_RE.findall(path.read_text(encoding="utf-8")):
            if is_image:
                used.add((path.parent / unquote(target)).resolve())
    images = {p.resolve() for p in (MANUAL_DIR / "gambar").rglob("*.png")}
    unused = sorted(str(p.relative_to(MANUAL_DIR.resolve())) for p in images - used)
    assert not unused, f"gambar tidak dipakai: {unused}"


def test_no_framework_name():
    """Buku panduan memakai nama SimLahan, bukan nama kerangka kerjanya.

    Nama instansi terlarang sudah dijaga untuk seluruh repositori oleh
    asetlahan/tests/test_branding.py.
    """
    word = "django"
    hits = [
        str(path.relative_to(MANUAL_DIR))
        for path in MANUAL_DIR.rglob("*")
        if path.is_file()
        and path.suffix in {".md", ".js", ".json", ".py", ".html", ".css"}
        and word in path.read_text(encoding="utf-8").lower()
    ]
    assert not hits, f"nama kerangka kerja ditemukan di: {hits}"
