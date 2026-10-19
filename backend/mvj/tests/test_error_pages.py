import pytest
from django.template.loader import render_to_string


@pytest.mark.django_db
def test_404_page_is_indonesian(client):
    response = client.get("/portal/lahan/TIDAK-ADA/")
    assert response.status_code == 404
    html = response.content.decode()
    assert '<html lang="id">' in html
    assert "Halaman tidak ditemukan" in html
    assert "Not Found" not in html


@pytest.mark.parametrize(
    "template,text",
    [
        ("400.html", "Permintaan tidak valid"),
        ("403.html", "Akses ditolak"),
        ("500.html", "Terjadi kesalahan"),
    ],
)
def test_error_templates_render_without_context(template, text):
    # handler500 merender tanpa context processor; templat tetap harus jalan.
    html = render_to_string(template)
    assert text in html and "SimLahan" in html
