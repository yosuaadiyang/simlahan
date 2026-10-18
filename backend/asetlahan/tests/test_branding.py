"""Pastikan tidak ada penyebutan instansi lain yang dilarang di kode sumber."""

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
FORBIDDEN = re.compile(r"\bbp[\s._-]*batam\b", re.IGNORECASE)
SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    "media",
    "static_root",
}


def _source_files():
    try:
        output = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return [ROOT / name for name in output.splitlines()]
    except (OSError, subprocess.CalledProcessError):
        files = []
        for directory, dirs, names in os.walk(ROOT):
            dirs[:] = [
                d for d in dirs if d not in SKIP_DIRS and not d.startswith("venv")
            ]
            files.extend(Path(directory) / name for name in names)
        return files


def test_no_forbidden_agency_name():
    files = _source_files()
    if not files:
        pytest.skip("Kode sumber tidak ditemukan.")
    hits = []
    for path in files:
        if path == Path(__file__).resolve() or not path.is_file():
            continue
        try:
            text = path.read_bytes()[:5_000_000].decode("utf-8")
        except UnicodeDecodeError:
            continue
        if FORBIDDEN.search(text):
            hits.append(str(path.relative_to(ROOT)))
    assert not hits, hits
