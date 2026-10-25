from auditlog.admin import LogEntryAdmin
from auditlog.models import LogEntry
from auditlog.render import get_field_verbose_name, render_logentry_changes_html
from django.contrib import admin
from django.core.exceptions import FieldDoesNotExist
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy


def _readable(value):
    # auditlog menyimpan nilai sebagai teks Python ("None", "True", "False").
    if value in (None, "", "None"):
        return "–"
    if value == "True":
        return _("Ya")
    if value == "False":
        return _("Tidak")
    return value


def _field_key(entry, name):
    """Relasi balik (mis. ``photos``) tidak punya verbose_name; pakai nama modelnya."""
    model = entry.content_type.model_class()
    try:
        field = model._meta.get_field(name) if model else None
    except FieldDoesNotExist:
        return name
    if field is not None and field.auto_created and not field.concrete:
        return str(field.related_model._meta.verbose_name_plural)
    return name


class _ReadableChanges:
    """Bungkus LogEntry agar tabel perubahan memakai nilai yang mudah dibaca."""

    def __init__(self, entry):
        self._entry = entry

    def __getattr__(self, name):
        return getattr(self._entry, name)

    @property
    def changes_dict(self):
        changes = {}
        for field, change in (self._entry.changes_dict or {}).items():
            if isinstance(change, (list, tuple)):
                change = [_readable(value) for value in change]
            changes[_field_key(self._entry, field)] = change
        return changes


admin.site.unregister(LogEntry)


@admin.register(LogEntry)
class ReadableLogEntryAdmin(LogEntryAdmin):
    @admin.display(description=gettext_lazy("Changes"))
    def msg_short(self, obj):
        if obj.action in (LogEntry.Action.DELETE, LogEntry.Action.ACCESS):
            return ""
        fields = ", ".join(
            str(get_field_verbose_name(obj, _field_key(obj, name)))
            for name in (obj.changes_dict or {})
        )
        if len(fields) > 140:
            fields = fields[: fields.rfind(" ", 0, 140)] + " …"
        return _("%(count)d perubahan: %(fields)s") % {
            "count": len(obj.changes_dict or {}),
            "fields": fields,
        }

    @admin.display(description=gettext_lazy("Changes"))
    def msg(self, obj):
        return render_logentry_changes_html(_ReadableChanges(obj))
