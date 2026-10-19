"""Akses Claude (Anthropic) untuk asisten AI dan pembacaan dokumen.

Aktif hanya bila ``ANTHROPIC_API_KEY`` diisi. Model bawaan ``claude-opus-5-5``
dapat diganti lewat ``ANTHROPIC_MODEL``. Untuk model yang mendukungnya,
permintaan yang ditolak pengaman model dialihkan otomatis ke model cadangan
(server-side fallback).
"""

import base64
import json
import logging

from django.conf import settings

LOG = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Model yang menerima fallbacks="default" di Claude API.
FALLBACK_MODELS = {
    "claude-opus-5-5",
    "claude-opus-5",
    "claude-fable-5-1",
    "claude-sonnet-5-5",
}


class AIError(Exception):
    pass


def enabled() -> bool:
    return bool(getattr(settings, "ANTHROPIC_API_KEY", ""))


def model() -> str:
    return getattr(settings, "ANTHROPIC_MODEL", "") or DEFAULT_MODEL


def _client():
    import anthropic

    return anthropic.Anthropic(
        api_key=settings.ANTHROPIC_API_KEY, timeout=120.0, max_retries=2
    )


def create(**params):
    """Panggil Messages API; kesalahan jaringan/API dijadikan AIError."""
    import anthropic

    if not enabled():
        raise AIError("Asisten AI belum dikonfigurasi (ANTHROPIC_API_KEY kosong).")
    name = model()
    client = _client()
    try:
        if name in FALLBACK_MODELS:
            response = client.beta.messages.create(
                model=name, betas=[FALLBACK_BETA], fallbacks="default", **params
            )
        else:
            response = client.messages.create(model=name, **params)
    except anthropic.RateLimitError as error:
        LOG.warning("Batas permintaan Claude tercapai: %s", error)
        raise AIError("Layanan AI sedang sibuk. Coba beberapa saat lagi.")
    except anthropic.APIStatusError as error:
        LOG.warning(
            "Claude API menolak permintaan (%s): %s", error.status_code, error.message
        )
        raise AIError(f"Layanan AI menolak permintaan ({error.status_code}).")
    except anthropic.APIConnectionError as error:
        LOG.warning("Tidak dapat menghubungi Claude API: %s", error)
        raise AIError("Tidak dapat menghubungi layanan AI.")
    if response.stop_reason == "refusal":
        raise AIError("Permintaan tidak dapat diproses oleh layanan AI.")
    return response


def text_of(response) -> str:
    return "\n".join(
        block.text for block in response.content if block.type == "text"
    ).strip()


DOCUMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "jenis_hak": {
            "type": "string",
            "description": "SHM, HGB, HGU, HP, HPL, girik, atau kosong",
        },
        "nomor_hak": {"type": "string"},
        "nib": {"type": "string"},
        "pemegang_hak": {"type": "string"},
        "luas_m2": {
            "type": "string",
            "description": "angka luas dalam m², titik sebagai desimal",
        },
        "kelurahan": {"type": "string"},
        "kecamatan": {"type": "string"},
        "tanggal_terbit": {"type": "string", "description": "YYYY-MM-DD"},
        "tanggal_berakhir": {"type": "string", "description": "YYYY-MM-DD"},
        "nomor_perkara": {"type": "string"},
        "nop": {"type": "string"},
        "ringkasan": {
            "type": "string",
            "description": "ringkasan isi dokumen maksimal 3 kalimat",
        },
    },
    "required": [
        "jenis_hak",
        "nomor_hak",
        "nib",
        "pemegang_hak",
        "luas_m2",
        "kelurahan",
        "kecamatan",
        "tanggal_terbit",
        "tanggal_berakhir",
        "nomor_perkara",
        "nop",
        "ringkasan",
    ],
    "additionalProperties": False,
}

EXTRACTION_PROMPT = (
    "Baca dokumen pertanahan Indonesia ini (sertipikat, akta, SPPT, putusan, surat) dan isi setiap "
    "kolom persis seperti tertulis. Kosongkan kolom yang tidak ada di dokumen; jangan menebak."
)


def extract_document(
    *, text: str = "", data: bytes = b"", media_type: str = ""
) -> dict:
    """Ekstraksi isian terstruktur dari teks atau berkas (PDF/gambar) dokumen."""
    content: list = []
    if data and media_type == "application/pdf":
        content.append(
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.standard_b64encode(data).decode(),
                },
            }
        )
    elif data and media_type in ("image/jpeg", "image/png"):
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.standard_b64encode(data).decode(),
                },
            }
        )
    elif text:
        content.append(
            {"type": "text", "text": f"<dokumen>\n{text[:150000]}\n</dokumen>"}
        )
    else:
        return {}
    content.append({"type": "text", "text": EXTRACTION_PROMPT})
    response = create(
        max_tokens=4000,
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": DOCUMENT_SCHEMA},
        },
        messages=[{"role": "user", "content": content}],
    )
    try:
        return json.loads(text_of(response))
    except json.JSONDecodeError:
        raise AIError("Jawaban layanan AI tidak dapat dibaca.")
