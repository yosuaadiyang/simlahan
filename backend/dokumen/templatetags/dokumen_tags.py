from django import template
from django.urls import reverse
from django.utils.translation import gettext as _

register = template.Library()


@register.simple_tag(takes_context=True)
def dokumen_shortcuts(context):
    """Pintasan di halaman indeks Dokumen & perizinan sesuai hak pengguna."""
    from dokumen.admin_views import other_counts

    request = context.get("request")
    if request is None:
        return []
    user = request.user
    counts = other_counts(user)
    items = []
    if user.has_perm("dokumen.view_landuse"):
        items.append(
            {
                "url": reverse("dokumen-dashboard"),
                "label": _("Dasbor"),
                "description": _(
                    "Kelengkapan dokumen, masa berlaku, tanda tangan, dan unduhan."
                ),
            }
        )
    if "waiting" in counts:
        items.append(
            {
                "url": reverse("admin:dokumen_permitrecord_changelist")
                + "?status__exact=diajukan",
                "label": _("Dokumen menunggu verifikasi"),
                "count": counts["waiting"],
                "description": _("Unggahan pemegang hak yang perlu diperiksa."),
            }
        )
    if "downloads" in counts:
        items.append(
            {
                "url": reverse("admin:dokumen_downloadrequest_changelist")
                + "?saya=putuskan",
                "label": _("Permintaan unduh menunggu keputusan"),
                "count": counts["downloads"],
                "description": _("Setujui atau tolak permintaan unduh dokumen."),
            }
        )
    if "approvals" in counts:
        items.append(
            {
                "url": reverse("admin:dokumen_signingdocument_changelist")
                + "?status__exact=menunggu_persetujuan",
                "label": _("Dokumen menunggu persetujuan internal"),
                "count": counts["approvals"],
                "description": _(
                    "Periksa dokumen sebelum dikirim untuk ditandatangani."
                ),
            }
        )
    if user.has_perm("dokumen.add_signingdocument"):
        items.append(
            {
                "url": reverse("admin:dokumen_signingdocument_add"),
                "label": _("Buat dokumen tanda tangan"),
                "description": _(
                    "Dari templat isian atau PDF, kirim ke penanda tangan berurutan."
                ),
            }
        )
    if user.has_perm("dokumen.add_documenttemplate"):
        items.append(
            {
                "url": reverse("admin:dokumen_documenttemplate_import"),
                "label": _("Impor templat"),
                "description": _(
                    "Unggah format Word, HTML, PDF, atau ZIP berisi banyak format."
                ),
            }
        )
    if user.has_perm("dokumen.view_downloadrequest"):
        items.append(
            {
                "url": reverse("admin:dokumen_downloadrequest_changelist")
                + "?saya=milik",
                "label": _("Permintaan unduh saya"),
                "description": _("Status izin unduh yang Anda ajukan."),
            }
        )
    return items


@register.filter
def bersih(value):
    """Tampilkan HTML isi dokumen setelah dibersihkan ulang (lapis pengaman)."""
    from django.utils.safestring import mark_safe

    from dokumen.sanitizer import sanitize_html

    return mark_safe(
        sanitize_html(value or "")
    )  # noqa: S308 - sudah disaring allowlist


@register.filter
def ambil(mapping, key):
    """``{{ dict|ambil:key }}`` — ambil nilai kamus di templat."""
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def pecah(value, size=32):
    """Pecah kata panjang tanpa spasi (sidik, URL, surel) agar tidak meluber di PDF."""
    import re

    from django.utils.html import escape
    from django.utils.safestring import mark_safe

    size = max(int(size), 8)

    def split(match):
        word = match.group(0)
        return "<br/>".join(
            escape(word[i : i + size]) for i in range(0, len(word), size)
        )

    text = str(value or "")
    parts = re.split(r"(\S+)", text)
    return mark_safe(
        "".join(
            (
                split(re.match(r".+", p))
                if p and not p.isspace() and len(p) > size
                else escape(p)
            )
            for p in parts
        )
    )
