import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from file_operations.private_files import PrivateFileField
from file_operations.validators import validate_file_signature


@pytest.mark.parametrize(
    "name,content",
    [
        ("surat.pdf", b"%PDF-1.7\n..."),
        ("surat.PDF", b"\n\n%PDF-1.4\n"),
        ("foto.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIF"),
        ("foto.png", b"\x89PNG\r\n\x1a\n\x00"),
        ("foto.webp", b"RIFF\x10\x00\x00\x00WEBPVP8 "),
        ("berkas.zip", b"PK\x03\x04\x14\x00"),
        ("laporan.docx", b"PK\x03\x04\x14\x00"),
        ("data.csv", b"a,b\n1,2\n"),
        ("catatan.txt", b"MZ bukan masalah untuk teks"),
    ],
)
def test_matching_content_is_accepted(name, content):
    validate_file_signature(SimpleUploadedFile(name, content))


@pytest.mark.parametrize(
    "name,content",
    [
        ("surat.pdf", b"MZ\x90\x00\x03\x00\x00\x00"),
        ("foto.jpg", b"%PDF-1.4"),
        ("foto.png", b""),
        ("laporan.docx", b"<html></html>"),
    ],
)
def test_disguised_content_is_rejected(name, content):
    with pytest.raises(ValidationError) as error:
        validate_file_signature(SimpleUploadedFile(name, content))
    assert error.value.code == "invalid_file_signature"


def test_reading_keeps_file_position():
    upload = SimpleUploadedFile("surat.pdf", b"%PDF-1.4\nisi")
    upload.read(3)
    validate_file_signature(upload)
    assert upload.tell() == 3


def test_stored_files_are_not_reopened():
    # Berkas lama (sudah tersimpan) tidak dibaca ulang saat data diubah.
    class Stored:
        name = "lama.pdf"
        _committed = True

    validate_file_signature(Stored())


def test_private_file_field_validates_signature():
    assert validate_file_signature in PrivateFileField().validators
