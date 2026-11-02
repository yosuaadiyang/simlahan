"""Pembaca cadangan PostgreSQL (``pg_dump``) tanpa memerlukan program PostgreSQL.

Dipakai untuk memindahkan data sistem pusat komando lama (cadangan Supabase)
ke SimLahan. Dua bentuk didukung:

* format kustom (``pg_dump -Fc``, berkas ``.dump``), versi arsip 1.12–1.16
  (PostgreSQL 11–17) dengan isi tanpa kompresi atau gzip;
* format teks (``pg_dump`` biasa, berkas ``.sql``) yang memuat blok
  ``COPY … FROM stdin``.

Hanya data tabel yang dibaca; perintah SQL di dalam berkas tidak pernah
dijalankan. Berkas diperlakukan sebagai masukan tak tepercaya: setiap panjang
dibatasi agar berkas rusak tidak menghabiskan memori.
"""

from __future__ import annotations

import gzip
import io
import re
import zlib
from collections.abc import Iterator

MAGIC = b"PGDMP"
MAX_STRING = 64 * 1024 * 1024
MAX_TABLE_TEXT = 512 * 1024 * 1024
MAX_TOC_ENTRIES = 200_000
BLOCK_DATA = 1
OFFSET_HAS_DATA = 2
COMPRESSION_NONE = 0
COMPRESSION_GZIP = 1
COPY_RE = re.compile(
    r'^COPY\s+(?P<table>(?:"[^"]+"|[\w$]+)(?:\.(?:"[^"]+"|[\w$]+))?)\s*'
    r"\((?P<columns>[^)]*)\)\s+FROM\s+stdin;",
    re.IGNORECASE,
)
_ESCAPES = {"b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v"}
_OCTAL = re.compile(r"[0-7]{1,3}")
_HEX = re.compile(r"[0-9a-fA-F]{1,2}")


class DumpError(Exception):
    """Berkas bukan cadangan PostgreSQL yang dapat dibaca."""


# --------------------------------------------------------------------------
# Teks COPY
# --------------------------------------------------------------------------


def _ident(value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('""', '"')
    return value.lower()


def _qualified(name: str) -> str:
    parts = re.findall(r'"(?:[^"]|"")*"|[^.]+', name)
    parts = [_ident(p) for p in parts]
    return ".".join(parts if len(parts) == 2 else ["public"] + parts)


def _unescape(value: str) -> str | None:
    if value == r"\N":
        return None
    if "\\" not in value:
        return value
    out = []
    i, size = 0, len(value)
    while i < size:
        char = value[i]
        if char != "\\" or i + 1 >= size:
            out.append(char)
            i += 1
            continue
        nxt = value[i + 1]
        if nxt in _ESCAPES:
            out.append(_ESCAPES[nxt])
            i += 2
        elif nxt in "01234567":
            digits = _OCTAL.match(value, i + 1).group()
            out.append(chr(int(digits, 8)))
            i += 1 + len(digits)
        elif nxt == "x" and _HEX.match(value, i + 2):
            digits = _HEX.match(value, i + 2).group()
            out.append(chr(int(digits, 16)))
            i += 2 + len(digits)
        else:
            out.append(nxt)
            i += 2
    return "".join(out)


def parse_copy_rows(columns: list[str], text: str) -> Iterator[dict]:
    """Baris data COPY (teks, pemisah tab) menjadi dict kolom → nilai teks/None."""
    width = len(columns)
    for line in text.split("\n"):
        if line == "\\." or not line:
            continue
        values = line.split("\t")
        if len(values) != width:
            raise DumpError(
                f"Jumlah kolom tidak cocok ({len(values)} dari {width} kolom)."
            )
        yield dict(zip(columns, (_unescape(v) for v in values)))


def _columns(spec: str) -> list[str]:
    return [_ident(c) for c in re.findall(r'"(?:[^"]|"")*"|[^,]+', spec) if c.strip()]


# --------------------------------------------------------------------------
# Format kustom
# --------------------------------------------------------------------------


class _Reader:
    def __init__(self, stream):
        self.stream = stream
        self.int_size = 4
        self.offset_size = 8

    def read(self, size: int) -> bytes:
        data = self.stream.read(size)
        if len(data) != size:
            raise DumpError("Berkas cadangan terpotong.")
        return data

    def byte(self) -> int:
        return self.read(1)[0]

    def int(self) -> int:
        negative = self.byte()
        value = int.from_bytes(self.read(self.int_size), "little")
        return -value if negative else value

    def string(self) -> str | None:
        size = self.int()
        if size < 0:
            return None
        if size > MAX_STRING:
            raise DumpError("Isi berkas cadangan tidak wajar (teks terlalu panjang).")
        return self.read(size).decode("utf-8", "replace")

    def offset(self) -> tuple[int, int]:
        flag = self.byte()
        return flag, int.from_bytes(self.read(self.offset_size), "little")


class CustomDump:
    """Daftar isi (TOC) dan data tabel dari arsip format kustom."""

    def __init__(self, stream):
        self.stream = stream
        reader = _Reader(stream)
        if reader.read(5) != MAGIC:
            raise DumpError("Bukan berkas pg_dump format kustom.")
        major, minor, _rev = reader.read(3)
        self.version = (major, minor)
        if not (1, 12) <= self.version <= (1, 16):
            raise DumpError(
                f"Versi arsip {major}.{minor} belum didukung (didukung 1.12–1.16)."
            )
        reader.int_size = reader.byte()
        reader.offset_size = reader.byte()
        if reader.int_size not in (4, 8) or reader.offset_size not in (4, 8):
            raise DumpError("Header berkas cadangan tidak wajar.")
        if reader.byte() != 1:  # 1 = archCustom
            raise DumpError("Bukan berkas pg_dump format kustom.")
        if self.version >= (1, 15):
            self.compression = reader.byte()
        else:
            level = reader.int()
            self.compression = COMPRESSION_NONE if level == 0 else COMPRESSION_GZIP
        if self.compression not in (COMPRESSION_NONE, COMPRESSION_GZIP):
            raise DumpError(
                "Cadangan memakai kompresi lz4/zstd. Buat ulang dengan "
                "pg_dump -Fc --compress=gzip (atau tanpa kompresi)."
            )
        for _i in range(7):  # waktu pembuatan
            reader.int()
        self.database = reader.string()
        self.server_version = reader.string()
        self.dump_version = reader.string()
        count = reader.int()
        if not 0 <= count <= MAX_TOC_ENTRIES:
            raise DumpError("Daftar isi berkas cadangan tidak wajar.")
        self.entries = [self._entry(reader) for _i in range(count)]
        self.reader = reader

    def _entry(self, reader: _Reader) -> dict:
        entry = {"id": reader.int(), "had_dumper": reader.int()}
        reader.string()  # table oid
        reader.string()  # oid
        entry["tag"] = reader.string() or ""
        entry["desc"] = reader.string() or ""
        reader.int()  # section
        reader.string()  # definisi
        reader.string()  # perintah drop
        entry["copy"] = reader.string() or ""
        entry["schema"] = reader.string() or ""
        reader.string()  # tablespace
        reader.string()  # table access method
        if self.version >= (1, 16):
            reader.int()  # relkind
        reader.string()  # pemilik
        reader.string()  # with oids
        while reader.string() is not None:  # dependensi
            pass
        entry["flag"], entry["offset"] = reader.offset()
        return entry

    def tables(self) -> dict[str, dict]:
        return {
            f"{e['schema']}.{e['tag']}": e
            for e in self.entries
            if e["desc"] == "TABLE DATA" and e["copy"]
        }

    def _data_text(self, entry: dict) -> str:
        if entry["flag"] != OFFSET_HAS_DATA:
            return ""
        reader = self.reader
        self.stream.seek(entry["offset"])
        if reader.byte() != BLOCK_DATA or reader.int() != entry["id"]:
            raise DumpError(f"Blok data tabel {entry['tag']} tidak ditemukan.")
        inflater = zlib.decompressobj() if self.compression else None
        parts, total = [], 0
        while (size := reader.int()) != 0:
            if not 0 < size <= MAX_STRING:
                raise DumpError("Blok data berkas cadangan tidak wajar.")
            chunk = self._inflate(inflater, reader.read(size), MAX_TABLE_TEXT - total)
            total += len(chunk)
            if total > MAX_TABLE_TEXT:
                raise DumpError(f"Data tabel {entry['tag']} terlalu besar.")
            parts.append(chunk)
        if inflater is not None:
            parts.append(inflater.flush())
        return b"".join(parts).decode("utf-8", "replace")

    @staticmethod
    def _inflate(inflater, chunk: bytes, room: int) -> bytes:
        if inflater is None:
            return chunk
        if room <= 0:
            raise DumpError("Data tabel terlalu besar.")
        data = inflater.decompress(chunk, room)
        if inflater.unconsumed_tail:
            raise DumpError("Data tabel terlalu besar.")
        return data

    def rows(self, entry: dict) -> list[dict]:
        match = COPY_RE.match(entry["copy"].strip())
        if not match:
            raise DumpError(f"Perintah COPY tabel {entry['tag']} tidak dikenali.")
        return list(parse_copy_rows(_columns(match["columns"]), self._data_text(entry)))


# --------------------------------------------------------------------------
# Antarmuka umum
# --------------------------------------------------------------------------


class Dump:
    """Isi cadangan per tabel (``schema.tabel`` → daftar baris dict)."""

    def __init__(self, path: str):
        self.path = path
        self._custom = None
        self._plain: dict[str, list[dict]] | None = None
        with open(path, "rb") as handle:
            head = handle.read(5)
        if head == MAGIC:
            self._file = open(path, "rb")
            self._custom = CustomDump(self._file)
            self._entries = self._custom.tables()
        else:
            self._plain = _plain_tables(path)
            self._entries = {}

    def close(self):
        if self._custom is not None:
            self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def table_names(self) -> list[str]:
        if self._plain is not None:
            return sorted(self._plain)
        return sorted(self._entries)

    def has(self, name: str) -> bool:
        return name in (self._plain if self._plain is not None else self._entries)

    def rows(self, name: str) -> list[dict]:
        if self._plain is not None:
            return list(self._plain.get(name, []))
        entry = self._entries.get(name)
        return self._custom.rows(entry) if entry else []


def _open_text(path: str):
    with open(path, "rb") as handle:
        gzipped = handle.read(2) == b"\x1f\x8b"
    if gzipped:
        return io.TextIOWrapper(gzip.open(path, "rb"), "utf-8", errors="replace")
    return open(path, encoding="utf-8", errors="replace")


def _plain_tables(path: str) -> dict[str, list[dict]]:
    tables: dict[str, list[dict]] = {}
    with _open_text(path) as handle:
        current = None
        lines: list[str] = []
        total = 0
        for raw in handle:
            line = raw.rstrip("\n")
            if current is None:
                match = COPY_RE.match(line)
                if match:
                    current = (_qualified(match["table"]), _columns(match["columns"]))
                    lines, total = [], 0
                continue
            if line == "\\.":
                name, columns = current
                tables.setdefault(name, []).extend(
                    parse_copy_rows(columns, "\n".join(lines))
                )
                current = None
                continue
            total += len(line)
            if total > MAX_TABLE_TEXT:
                raise DumpError(f"Data tabel {current[0]} terlalu besar.")
            lines.append(line)
        if current is not None:
            raise DumpError("Berkas cadangan terpotong (blok COPY tidak ditutup).")
    if not tables:
        raise DumpError("Tidak ada data tabel (COPY) di dalam berkas.")
    return tables
