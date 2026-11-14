import pytest

from dokumen import merge
from dokumen.models import ContentBlock
from dokumen.sanitizer import html_to_text, sanitize_html


@pytest.mark.parametrize(
    "dirty",
    [
        '<p onclick="alert(1)">x</p>',
        "<script>alert(1)</script><p>x</p>",
        '<a href="javascript:alert(1)">x</a>',
        '<img src="http://evil/x.png"><p>x</p>',
        "<svg><script>alert(1)</script></svg><p>x</p>",
        '<p style="background:url(javascript:alert(1))">x</p>',
        "<iframe src=//evil></iframe><p>x</p>",
        "<style>body{display:none}</style><p>x</p>",
    ],
)
def test_sanitizer_removes_active_content(dirty):
    clean = sanitize_html(dirty)
    lowered = clean.lower()
    for bad in ("script", "onclick", "javascript", "iframe", "<style", "evil", "<svg"):
        assert bad not in lowered
    assert "x" in clean


def test_sanitizer_keeps_document_formatting():
    html = (
        '<h2 style="text-align: center">Judul</h2>'
        '<table><tr><td colspan="2"><b>a</b></td></tr></table><ol><li>i</li></ol>'
    )
    clean = sanitize_html(html)
    assert 'style="text-align: center"' in clean
    assert 'colspan="2"' in clean
    assert "<ol>" in clean and "<b>a</b>" in clean


def test_sanitizer_self_closing_drop_tag_does_not_swallow_rest():
    assert "sisa" in sanitize_html("<script/><p>sisa</p>")


def test_html_to_text():
    assert html_to_text("<p>Satu</p><p>Dua&nbsp;tiga</p>").split() == [
        "Satu",
        "Dua",
        "tiga",
    ]


def test_merge_escapes_values_and_marks_missing(land_use):
    land_use.holder.name = "<b>PT</b> Jahil"
    land_use.holder.save()
    context = merge.build_context(land_use=land_use)
    html = merge.merge_html(
        "<p>{{ pemohon.nama }} {{ tidak.ada }}</p>", context, highlight_missing=True
    )
    assert "&lt;b&gt;PT&lt;/b&gt; Jahil" in html
    assert "merge-field" in html


def test_merge_expands_content_blocks_with_limit(db):
    ContentBlock.objects.create(code="a", name="A", body="<p>A {{ blok.b }}</p>")
    ContentBlock.objects.create(code="b", name="B", body="<p>B {{ blok.a }}</p>")
    html = merge.merge_html("{{ blok.a }}", {})
    assert "A" in html and "B" in html
    # Rekursi berhenti; tidak ada loop tanpa akhir.
    assert html.count("<p>") <= 8


def test_custom_and_unknown_fields(db):
    body = "{{ isian.batas_waktu }} {{ pemohon.nama }} {{ ngawur.x }} {{ isian.batas_waktu }}"
    assert merge.custom_fields(body) == ["batas_waktu"]
    assert merge.unknown_fields(body) == ["ngawur.x"]


def test_render_docx_sandboxed(land_use):
    import io

    import docx

    document = docx.Document()
    document.add_paragraph("Nama: {{ pemohon.nama }}")
    document.add_paragraph("{{ ''.__class__.__mro__ }}")
    buffer = io.BytesIO()
    document.save(buffer)
    with pytest.raises(merge.TemplateRenderError):
        merge.render_docx(buffer.getvalue(), merge.build_context(land_use=land_use))


def test_render_docx_fills_fields(land_use):
    import io

    import docx

    document = docx.Document()
    document.add_paragraph("Nama: {{ pemohon.nama }} / {{ pemanfaatan.nomor }}")
    buffer = io.BytesIO()
    document.save(buffer)
    data = merge.render_docx(buffer.getvalue(), merge.build_context(land_use=land_use))
    text = "\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs)
    assert land_use.holder.name in text and land_use.number in text


def _docx_with_padding(padding_bytes: int) -> bytes:
    """DOCX sah ditambah satu bagian yang sangat mudah dikompresi (bom ZIP)."""
    import io
    import zipfile

    import docx

    document = docx.Document()
    document.add_paragraph("Nama: {{ pemohon.nama }}")
    buffer = io.BytesIO()
    document.save(buffer)
    with zipfile.ZipFile(buffer, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/media/padding.bin", b"\0" * padding_bytes)
    return buffer.getvalue()


def test_docx_uncompressed_size_is_bounded(land_use, monkeypatch):
    monkeypatch.setattr(merge, "MAX_DOCX_UNCOMPRESSED", 1024 * 1024)
    bomb = _docx_with_padding(2 * 1024 * 1024)
    assert len(bomb) < 64 * 1024  # kecil saat diunggah
    with pytest.raises(merge.TemplateRenderError, match="terlalu besar"):
        merge.docx_to_html(bomb)
    with pytest.raises(merge.TemplateRenderError, match="terlalu besar"):
        merge.render_docx(bomb, merge.build_context(land_use=land_use))
    # DOCX biasa di bawah batas tetap terbaca.
    assert "pemohon.nama" in merge.docx_to_html(_docx_with_padding(1024))


def test_docx_that_is_not_a_zip_is_rejected_cleanly():
    with pytest.raises(merge.TemplateRenderError):
        merge.docx_to_html(b"bukan docx")
