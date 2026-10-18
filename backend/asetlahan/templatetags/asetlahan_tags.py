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


@register.simple_tag
def aset_portal_flags():
    """Saklar modul untuk menu portal (pengaduan, lelang)."""
    from asetlahan.models import ModuleSettings

    config = ModuleSettings.load()
    return {
        "enable_grievance": config.enable_grievance,
        "enable_tender": config.enable_tender,
    }
