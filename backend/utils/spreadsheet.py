"""Netralkan rumus spreadsheet pada data yang diekspor.

Teks sel yang diawali ``=``, ``+``, ``-``, ``@``, atau tab dijadikan rumus
hidup oleh Excel/LibreOffice saat berkas dibuka (injeksi rumus klasik).
Data yang diekspor bisa berisi masukan pihak luar (form pengaduan publik,
nama pemasok lelang, dokumen OCR), jadi setiap sel teks dinetralkan.
"""

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t")


def neutralize_formula(value):
    """Awali teks berbahaya dengan petik tunggal agar dibaca sebagai teks."""
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return f"'{value}"
    return value
