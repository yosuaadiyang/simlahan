import io

import pytest
from docx import Document
from jinja2.exceptions import SecurityError

from leasing.models.debt_collection import render_docx_template


def _docx(text: str) -> io.BytesIO:
    document = Document()
    document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer


def _text(data: bytes) -> str:
    return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)


def test_render_docx_template_fills_fields():
    result = render_docx_template(
        _docx("Sewa {{ lease_identifier }}"), {"lease_identifier": "S0120-1"}
    )

    assert "Sewa S0120-1" in _text(result)


def test_render_docx_template_blocks_code_execution():
    # Templat diunggah pengguna (mis. Ahli Hukum Penagihan); ekspresi Jinja
    # tidak boleh menjangkau objek Python internal untuk menjalankan kode.
    payload = "{{ cycler.__init__.__globals__.os.getcwd() }}"

    with pytest.raises(SecurityError):
        render_docx_template(_docx(payload), {})
