"""Netralkan rumus spreadsheet pada data yang diekspor.

Teks sel yang diawali ``=``, ``+``, ``-``, ``@``, tab, atau CR dijadikan rumus
hidup oleh Excel/LibreOffice saat berkas dibuka (injeksi rumus klasik).
Data yang diekspor bisa berisi masukan pihak luar (form pengaduan publik,
nama pemasok lelang, dokumen OCR, isian formulir), jadi setiap sel teks
dinetralkan.
"""

import re

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
# Angka biasa ("-5", "1.250,50") dan nomor telepon ("+62 812-3456-7890") tidak
# memuat huruf sehingga tidak bisa memanggil fungsi; dibiarkan apa adanya.
_PLAIN_NUMBER = re.compile(r"^[+-]?[\d(][\d\s.,()-]*$")

# Opsi xlsxwriter: teks selalu ditulis sebagai teks, bukan rumus atau tautan.
SAFE_XLSX_OPTIONS = {"strings_to_formulas": False, "strings_to_urls": False}


def neutralize_formula(value):
    """Awali teks berbahaya dengan petik tunggal agar dibaca sebagai teks."""
    if (
        isinstance(value, str)
        and value.startswith(FORMULA_PREFIXES)
        and not _PLAIN_NUMBER.match(value)
    ):
        return f"'{value}"
    return value


def safe_workbook(output, options=None):
    """``xlsxwriter.Workbook`` yang menulis teks sebagai teks, untuk ekspor
    yang memakai ``write()`` polimorfik pada data pengguna. Jangan dipakai
    untuk laporan yang sengaja menulis rumus lewat ``write()``."""
    import xlsxwriter

    return xlsxwriter.Workbook(output, {**(options or {}), **SAFE_XLSX_OPTIONS})
