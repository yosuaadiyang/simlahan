import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def sebaris(text: str) -> str:
    """Format sebaris panduan: `kode` dan **tebal** (teks lain di-escape)."""
    html = escape(text)
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
    html = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", html)
    return mark_safe(html)
