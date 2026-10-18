from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def aset_tools(context):
    """Daftar halaman alat modul aset lahan yang boleh dibuka pengguna."""
    from asetlahan.admin_views import available_tools

    request = context.get("request")
    if request is None or not request.user.is_authenticated:
        return []
    return available_tools(request.user)
