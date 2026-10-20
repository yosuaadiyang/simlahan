"""Panel petugas pusat komando di /admin/operasi/.

Pekerjaan lapangan sehari-hari ada di /komando/ (peta & PWA). Panel ini untuk
mengelola Korwil dan anggotanya, mengimpor batas wilayah dan data warga,
memeriksa laporan, absensi, SOS, dan mengatur pusat komando.
"""

import csv

from django import forms
from django.contrib import admin, messages
from django.contrib.gis.admin import GISModelAdmin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

from asetlahan import scope as aset_scope
from file_operations.private_files import PrivateFileField
from operasi import enums, geo, services
from operasi.models import (
    Activity,
    ActivityPhoto,
    AreaAnalysis,
    Attendance,
    ChatMessage,
    CommandSettings,
    Korwil,
    OfficerPosition,
    Resident,
    SoilTest,
    SosAlert,
    StanceChange,
    SystemLock,
)


def badge(color: str, label) -> str:
    return format_html(
        '<span style="color:#fff;background:{};padding:2px 6px;border-radius:3px;white-space:nowrap">{}</span>',
        color,
        label,
    )


def _local(moment) -> str:
    return timezone.localtime(moment).strftime("%d-%m-%Y %H:%M") if moment else ""


def csv_response(filename: str, header: list, rows) -> HttpResponse:
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    # BOM agar Excel membaca huruf non-ASCII dengan benar.
    response.write("﻿")
    writer = csv.writer(response)
    writer.writerow([str(h) for h in header])
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
    return response


# --------------------------------------------------------------------------
# Mixin
# --------------------------------------------------------------------------


class _FileLink:
    def __init__(self, url, name):
        self.url = url
        self.name = name

    def __str__(self):
        return self.name


class PrivateFileWidget(forms.ClearableFileInput):
    """Tautan berkas privat lewat unduhan petugas, bukan /media/."""

    def __init__(self, kind, attrs=None):
        super().__init__(attrs)
        self.kind = kind

    def format_value(self, value):
        from operasi.views import file_url

        if value and getattr(value, "instance", None) is not None and value.instance.pk:
            return _FileLink(
                file_url(self.kind, value.instance) + "?lihat=1",
                value.name.rsplit("/", 1)[-1],
            )
        return None


class OperasiAdminMixin:
    """Data hanya dari Korwil yang terlihat oleh petugas; berkas lewat unduhan privat."""

    scope_prefix: str | None = "korwil"
    file_kinds: dict[str, str] = {}

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if self.scope_prefix is not None:
            queryset = geo.scoped(queryset, request.user, self.scope_prefix)
        return queryset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.related_model is Korwil:
            kwargs["queryset"] = services.visible_korwils(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, PrivateFileField) and db_field.name in self.file_kinds:
            kwargs["widget"] = PrivateFileWidget(self.file_kinds[db_field.name])
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class OperasiModelAdmin(OperasiAdminMixin, admin.ModelAdmin):
    pass


class OperasiGISAdmin(OperasiAdminMixin, GISModelAdmin):
    pass


class ReadOnlyAdminMixin:
    """Data yang dibuat dari aplikasi lapangan: hanya dilihat (dan dihapus Administrator)."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class SingletonAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = self.model.load()
        opts = self.model._meta
        return HttpResponseRedirect(
            reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.pk])
        )


class ImportForm(forms.Form):
    file = forms.FileField(label=_("Berkas"))


def _import_page(model_admin, request, form, title, help_html):
    context = {
        **model_admin.admin_site.each_context(request),
        "opts": model_admin.model._meta,
        "form": form,
        "title": title,
        "help_html": help_html,
    }
    return TemplateResponse(request, "admin/operasi/import.html", context)


# --------------------------------------------------------------------------
# Pengaturan & kunci sistem
# --------------------------------------------------------------------------


@admin.register(CommandSettings)
class CommandSettingsAdmin(SingletonAdmin):
    fieldsets = (
        (
            _("Absensi"),
            {
                "fields": (
                    "work_start",
                    "late_tolerance_minutes",
                    "work_end",
                    "require_attendance_photo",
                    "enforce_geofence",
                    "geofence_tolerance_m",
                )
            },
        ),
        (
            _("Kinerja (KPI)"),
            {
                "fields": (
                    "weekly_activity_target",
                    "weight_attendance",
                    "weight_activity",
                    "weight_task",
                ),
                "description": _("Jumlah ketiga bobot harus 100%."),
            },
        ),
        (
            _("Peta, Live & SOS"),
            {"fields": ("online_minutes", "sos_emails", "satellite_tile_url")},
        ),
    )


class SystemLockForm(forms.ModelForm):
    new_passcode = forms.CharField(
        label=_("Kode rahasia baru"),
        required=False,
        min_length=6,
        widget=forms.PasswordInput(
            render_value=False, attrs={"autocomplete": "new-password"}
        ),
        help_text=_("Minimal 6 karakter. Kosongkan bila tidak diganti."),
    )
    confirm_passcode = forms.CharField(
        label=_("Ulangi kode rahasia baru"),
        required=False,
        widget=forms.PasswordInput(
            render_value=False, attrs={"autocomplete": "new-password"}
        ),
    )
    current_passcode = forms.CharField(
        label=_("Kode rahasia saat ini"),
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "off"}),
        help_text=_(
            "Wajib untuk menonaktifkan kunci atau mengganti kode rahasia yang sudah ada."
        ),
    )

    class Meta:
        model = SystemLock
        fields = ("is_armed", "shutdown_at", "message")

    def clean(self):
        data = super().clean()
        lock = self.instance
        new = data.get("new_passcode") or ""
        if new != (data.get("confirm_passcode") or ""):
            self.add_error("confirm_passcode", _("Kode rahasia tidak sama."))
        current_ok = lock.check_passcode(data.get("current_passcode") or "")
        if lock.passcode_hash and new and not current_ok:
            self.add_error(
                "current_passcode",
                _("Masukkan kode rahasia saat ini untuk menggantinya."),
            )
        armed = data.get("is_armed")
        if lock.is_armed and not armed and not current_ok:
            self.add_error(
                "current_passcode",
                _("Masukkan kode rahasia untuk menonaktifkan kunci sistem."),
            )
        if armed:
            if not (lock.passcode_hash or new):
                self.add_error(
                    "new_passcode", _("Tetapkan kode rahasia sebelum mengaktifkan.")
                )
            shutdown = data.get("shutdown_at")
            if shutdown is None:
                self.add_error("shutdown_at", _("Tentukan waktu sistem dimatikan."))
            elif not lock.is_armed and shutdown <= timezone.now():
                self.add_error("shutdown_at", _("Waktu harus di masa depan."))
        return data


@admin.register(SystemLock)
class SystemLockAdmin(SingletonAdmin):
    """Hanya superuser: tidak ada grup yang diberi izin model ini."""

    form = SystemLockForm
    readonly_fields = ("status", "armed_by", "armed_at", "defused_by", "defused_at")
    fieldsets = (
        (
            None,
            {
                "fields": ("status", "is_armed", "shutdown_at", "message"),
                "description": _(
                    "Bila aktif, hitung mundur tampil di pusat komando dan panel. Saat "
                    "waktunya tiba, seluruh aplikasi berhenti melayani pengguna selain "
                    "superuser sampai kunci dinonaktifkan dengan kode rahasia."
                ),
            },
        ),
        (
            _("Kode rahasia"),
            {"fields": ("new_passcode", "confirm_passcode", "current_passcode")},
        ),
        (
            _("Riwayat"),
            {"fields": ("armed_by", "armed_at", "defused_by", "defused_at")},
        ),
    )

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    @admin.display(description=_("Status"))
    def status(self, obj):
        if obj.is_armed and obj.shutdown_at:
            if obj.shutdown_at <= timezone.now():
                return badge("#cf222e", _("Sistem dihentikan"))
            return badge(
                "#9a6700", _("Hitung mundur sampai %s") % _local(obj.shutdown_at)
            )
        return badge("#1a7f37", _("Tidak aktif"))

    def save_model(self, request, obj, form, change):
        new = form.cleaned_data.get("new_passcode")
        if new:
            obj.set_passcode(new)
        if "is_armed" in form.changed_data:
            if obj.is_armed:
                obj.armed_by = request.user
                obj.armed_at = timezone.now()
            else:
                obj.defused_by = request.user
                obj.defused_at = timezone.now()
        super().save_model(request, obj, form, change)


# --------------------------------------------------------------------------
# Korwil & warga
# --------------------------------------------------------------------------


@admin.register(Korwil)
class KorwilAdmin(OperasiGISAdmin):
    scope_prefix = ""
    list_display = (
        "code",
        "name",
        "color_swatch",
        "coordinator",
        "member_count",
        "resident_count",
        "pro_pct",
        "has_map",
        "is_active",
        "service_unit",
    )
    list_display_links = ("code", "name")
    list_filter = ("is_active", "service_unit")
    search_fields = ("code", "name", "villages")
    filter_horizontal = ("members",)
    readonly_fields = ("statistics",)
    change_list_template = "admin/operasi/korwil/change_list.html"
    fieldsets = (
        (None, {"fields": ("code", "name", "color", "is_active", "service_unit")}),
        (_("Petugas"), {"fields": ("coordinator", "members")}),
        (
            _("Wilayah"),
            {"fields": ("villages", "target_households", "geometry", "note")},
        ),
        (_("Ringkasan"), {"fields": ("statistics",)}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("coordinator", "service_unit")
            .annotate(
                _members=Count("members", distinct=True),
                _residents=Count("residents", distinct=True),
                _pro=Count(
                    "residents",
                    filter=Q(residents__stance=enums.Stance.SUPPORT),
                    distinct=True,
                ),
            )
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "service_unit" and not aset_scope.sees_all(request.user):
            kwargs["queryset"] = request.user.service_units.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description=_("Warna"))
    def color_swatch(self, obj):
        return badge(obj.color, obj.color)

    @admin.display(description=_("Petugas"), ordering="_members")
    def member_count(self, obj):
        return obj._members

    @admin.display(description=_("Warga"), ordering="_residents")
    def resident_count(self, obj):
        return obj._residents

    @admin.display(description=_("Pro"))
    def pro_pct(self, obj):
        return f"{services.pct(obj._pro, obj._residents)}%" if obj._residents else "–"

    @admin.display(boolean=True, description=_("Peta"))
    def has_map(self, obj):
        return obj.geometry is not None

    @admin.display(description=_("Statistik"))
    def statistics(self, obj):
        if not obj.pk:
            return "–"
        data = services.resident_counts(Resident.objects.filter(korwil=obj))
        rows = [
            (
                _("Warga terdata"),
                f"{data['total']}"
                + (
                    f" / {obj.target_households} target"
                    if obj.target_households
                    else ""
                ),
            ),
            (
                _("Pro"),
                f"{data['pro']} ({data['pro_pct'] if data['pro_pct'] is not None else '–'}%)",
            ),
            (_("Menolak"), data["contra"]),
            (
                _("RTRW sesuai"),
                f"{data['conform']} ({data['rtrw_pct'] if data['rtrw_pct'] is not None else '–'}%)",
            ),
            (_("Lahan sudah / belum"), f"{data['released']} / {data['pending']}"),
            (_("Kegiatan"), obj.activities.count()),
            (_("Uji tanah"), obj.soil_tests.count()),
        ]
        return format_html_join("", "<div><b>{}</b>: {}</div>", rows)

    def get_urls(self):
        return [
            path(
                "impor/",
                self.admin_site.admin_view(self.import_view),
                name="operasi_korwil_import",
            ),
        ] + super().get_urls()

    def import_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        form = ImportForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            from asetlahan.importers import AssetImportError
            from operasi.importers import import_korwils

            upload = form.cleaned_data["file"]
            try:
                created, updated = import_korwils(upload.read(), upload.name)
            except AssetImportError as error:
                messages.error(request, str(error))
            else:
                messages.success(
                    request,
                    _("%(c)d Korwil dibuat, %(u)d diperbarui.")
                    % {"c": created, "u": updated},
                )
                return HttpResponseRedirect(reverse("admin:operasi_korwil_changelist"))
        return _import_page(
            self,
            request,
            form,
            _("Impor batas Korwil"),
            _(
                "GeoJSON, KML/KMZ (Google Earth), GeoPackage (.gpkg), atau Shapefile dalam ZIP berisi poligon "
                "wilayah. Atribut yang dikenali: <code>kode</code> (wajib, mis. A), "
                "<code>nama</code>, <code>warna</code> (#RRGGBB), <code>kampung</code>. "
                "Korwil dengan kode yang sudah ada diperbarui batasnya."
            ),
        )


class StanceChangeInline(admin.TabularInline):
    model = StanceChange
    extra = 0
    can_delete = False
    fields = ("changed_at", "old_stance", "new_stance", "changed_by", "activity")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Resident)
class ResidentAdmin(OperasiGISAdmin):
    list_display = (
        "number",
        "head_name",
        "korwil",
        "village",
        "stance_badge",
        "land_status",
        "rtrw_status",
        "relocation_choice",
        "member_count",
        "last_visited_on",
    )
    list_display_links = ("number", "head_name")
    list_filter = (
        "korwil",
        "stance",
        "land_status",
        "rtrw_status",
        "relocation_choice",
        "village",
    )
    search_fields = ("number", "head_name", "village", "address", "phone")
    raw_id_fields = ("pengadaan_household", "pengadaan_parcel", "land_asset")
    readonly_fields = ("number", "last_visited_on", "created_by", "visits")
    inlines = (StanceChangeInline,)
    actions = ("export_csv",)
    change_list_template = "admin/operasi/resident/change_list.html"
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "number",
                    "korwil",
                    "head_name",
                    "nik",
                    "family_card_number",
                    "member_count",
                    "phone",
                )
            },
        ),
        (_("Tempat tinggal"), {"fields": ("village", "address", "location")}),
        (
            _("Status"),
            {"fields": ("stance", "land_status", "rtrw_status", "relocation_choice")},
        ),
        (
            _("Keterkaitan modul lain"),
            {"fields": ("pengadaan_household", "pengadaan_parcel", "land_asset")},
        ),
        (_("Riwayat"), {"fields": ("last_visited_on", "visits", "created_by", "note")}),
    )

    @admin.display(description=_("Sikap"), ordering="stance")
    def stance_badge(self, obj):
        return badge(
            enums.STANCE_COLORS.get(obj.stance, "#57606a"), obj.get_stance_display()
        )

    @admin.display(description=_("Kegiatan"))
    def visits(self, obj):
        if not obj.pk:
            return "–"
        items = obj.activities.order_by("-started_at")[:20]
        if not items:
            return "–"
        return format_html_join(
            format_html("<br>"),
            '<a href="{}">{}</a> {} – {}',
            (
                (
                    reverse("admin:operasi_activity_change", args=[a.pk]),
                    a.number,
                    _local(a.started_at),
                    a.title,
                )
                for a in items
            ),
        )

    def get_search_results(self, request, queryset, search_term):
        results, distinct = super().get_search_results(request, queryset, search_term)
        digits = "".join(ch for ch in search_term if ch.isdigit())
        if len(digits) == 16:
            from pengadaan.crypto import fingerprint

            results = results | queryset.filter(nik_fingerprint=fingerprint(digits))
        return results, distinct

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        obj._changed_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description=_("Ekspor CSV"), permissions=["view"])
    def export_csv(self, request, queryset):
        rows = (
            (
                r.number,
                r.korwil.code if r.korwil_id else "",
                r.head_name,
                r.member_count,
                r.phone,
                r.village,
                r.address,
                r.location.y if r.location else "",
                r.location.x if r.location else "",
                r.get_stance_display(),
                r.get_land_status_display(),
                r.get_rtrw_status_display(),
                r.get_relocation_choice_display(),
                r.last_visited_on or "",
            )
            for r in queryset.select_related("korwil")
        )
        header = [
            _("Nomor"),
            _("Korwil"),
            _("Nama kepala keluarga"),
            _("Jiwa"),
            _("Telepon"),
            _("Kampung"),
            _("Alamat"),
            _("Lintang"),
            _("Bujur"),
            _("Sikap"),
            _("Status lahan"),
            _("RTRW"),
            _("Pilihan"),
            _("Terakhir dikunjungi"),
        ]
        return csv_response("warga-terdata.csv", header, rows)

    def get_urls(self):
        return [
            path(
                "impor/",
                self.admin_site.admin_view(self.import_view),
                name="operasi_resident_import",
            ),
        ] + super().get_urls()

    def import_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        form = ImportForm(request.POST or None, request.FILES or None)
        form.fields["korwil"] = forms.ModelChoiceField(
            services.visible_korwils(request.user),
            label=_("Korwil"),
            required=False,
            help_text=_("Kosongkan untuk mengikuti kolom korwil atau lokasi rumah."),
        )
        if request.method == "POST" and form.is_valid():
            from asetlahan.importers import AssetImportError
            from operasi.importers import import_residents

            upload = form.cleaned_data["file"]
            try:
                result = import_residents(
                    upload.read(),
                    upload.name,
                    user=request.user,
                    korwil=form.cleaned_data["korwil"],
                )
            except AssetImportError as error:
                messages.error(request, str(error))
            else:
                messages.success(
                    request,
                    _("%(c)d warga dibuat, %(u)d diperbarui.")
                    % {"c": result["created"], "u": result["updated"]},
                )
                for error in result.get("errors", [])[:20]:
                    messages.warning(request, error)
                return HttpResponseRedirect(
                    reverse("admin:operasi_resident_changelist")
                )
        return _import_page(
            self,
            request,
            form,
            _("Impor data warga"),
            _(
                "CSV (pemisah koma atau titik koma) atau berkas spasial titik (GeoJSON, KML/KMZ, "
                "GeoPackage, Shapefile ZIP). Kolom yang dikenali: <code>nama</code> (wajib), "
                "<code>nik</code>, <code>kk</code>, <code>jiwa</code>, <code>telepon</code>, "
                "<code>kampung</code>, <code>alamat</code>, <code>korwil</code>, <code>lat</code>, "
                "<code>lng</code>, <code>sikap</code> (pro/netral/kontra), <code>status_lahan</code> "
                "(sudah/belum), <code>rtrw</code> (sesuai/tidak), <code>pilihan</code> "
                "(relokasi/uang/geser), <code>catatan</code>. Warga dengan NIK yang sudah ada "
                "diperbarui."
            ),
        )


# --------------------------------------------------------------------------
# Kegiatan & uji tanah
# --------------------------------------------------------------------------


class ActivityPhotoInline(admin.TabularInline):
    model = ActivityPhoto
    extra = 0
    fields = ("photo", "caption", "uploaded_at")
    readonly_fields = ("uploaded_at",)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, PrivateFileField):
            kwargs["widget"] = PrivateFileWidget("kegiatan")
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(Activity)
class ActivityAdmin(OperasiGISAdmin):
    list_display = (
        "number",
        "title",
        "activity_type",
        "korwil",
        "started_at",
        "reported_by",
        "participants_count",
        "photo_count",
        "verified",
    )
    list_display_links = ("number", "title")
    list_filter = ("activity_type", "korwil", "verified", "started_at")
    date_hierarchy = "started_at"
    search_fields = ("number", "title", "description", "outcome")
    autocomplete_fields = ("residents", "task")
    readonly_fields = (
        "number",
        "client_id",
        "reported_by",
        "verified_by",
        "verified_at",
    )
    inlines = (ActivityPhotoInline,)
    actions = ("mark_verified", "export_csv")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "number",
                    "activity_type",
                    "title",
                    "description",
                    "started_at",
                    "duration_minutes",
                    "korwil",
                )
            },
        ),
        (_("Lokasi"), {"fields": ("location", "accuracy_m")}),
        (
            _("Hasil"),
            {"fields": ("participants_count", "residents", "outcome", "task")},
        ),
        (
            _("Pelapor & verifikasi"),
            {
                "fields": (
                    "reported_by",
                    "verified",
                    "verified_by",
                    "verified_at",
                    "client_id",
                )
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("korwil", "reported_by")
            .annotate(_photos=Count("photos"))
        )

    @admin.display(description=_("Foto"), ordering="_photos")
    def photo_count(self, obj):
        return obj._photos

    def save_model(self, request, obj, form, change):
        if not change and obj.reported_by_id is None:
            obj.reported_by = request.user
        if "verified" in form.changed_data:
            obj.verified_by = request.user if obj.verified else None
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.touch_residents()

    @admin.action(description=_("Tandai sudah diverifikasi"), permissions=["change"])
    def mark_verified(self, request, queryset):
        count = 0
        for activity in queryset.filter(verified=False):
            activity.verified = True
            activity.verified_by = request.user
            activity.save()
            count += 1
        messages.success(request, _("%d kegiatan diverifikasi.") % count)

    @admin.action(description=_("Ekspor CSV"), permissions=["view"])
    def export_csv(self, request, queryset):
        rows = (
            (
                a.number,
                _local(a.started_at),
                a.get_activity_type_display(),
                a.title,
                a.korwil.code if a.korwil_id else "",
                (
                    a.reported_by.get_full_name() or a.reported_by.get_username()
                    if a.reported_by_id
                    else ""
                ),
                a.duration_minutes,
                a.participants_count,
                a.location.y if a.location else "",
                a.location.x if a.location else "",
                a.outcome,
                _("Ya") if a.verified else _("Belum"),
            )
            for a in queryset.select_related("korwil", "reported_by")
        )
        header = [
            _("Nomor"),
            _("Waktu"),
            _("Jenis"),
            _("Judul"),
            _("Korwil"),
            _("Petugas"),
            _("Durasi (menit)"),
            _("Warga hadir"),
            _("Lintang"),
            _("Bujur"),
            _("Hasil"),
            _("Diverifikasi"),
        ]
        return csv_response("kegiatan.csv", header, rows)


@admin.register(SoilTest)
class SoilTestAdmin(OperasiGISAdmin):
    file_kinds = {"photo": "tanah-foto", "lab_report": "tanah-lab"}
    list_display = (
        "number",
        "korwil",
        "sampled_at",
        "sampled_by",
        "texture",
        "ph",
        "bearing_capacity_kpa",
        "suitability_badge",
    )
    list_filter = ("suitability", "texture", "korwil", "sampled_at")
    date_hierarchy = "sampled_at"
    search_fields = ("number", "lab_name", "note", "color")
    readonly_fields = ("number", "client_id", "sampled_by")
    actions = ("export_csv",)
    fieldsets = (
        (
            None,
            {"fields": ("number", "korwil", "sampled_at", "sampled_by", "location")},
        ),
        (
            _("Hasil uji"),
            {
                "fields": (
                    "depth_cm",
                    "texture",
                    "color",
                    "ph",
                    "moisture_pct",
                    "organic_c_pct",
                    "bearing_capacity_kpa",
                    "cbr_pct",
                    "suitability",
                )
            },
        ),
        (
            _("Laboratorium & berkas"),
            {"fields": ("lab_name", "lab_report", "photo", "note", "client_id")},
        ),
    )

    @admin.display(description=_("Kelayakan"), ordering="suitability")
    def suitability_badge(self, obj):
        return badge(
            enums.SOIL_COLORS.get(obj.suitability, "#57606a"),
            obj.get_suitability_display(),
        )

    def save_model(self, request, obj, form, change):
        if not change and obj.sampled_by_id is None:
            obj.sampled_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description=_("Ekspor CSV"), permissions=["view"])
    def export_csv(self, request, queryset):
        rows = (
            (
                t.number,
                _local(t.sampled_at),
                t.korwil.code if t.korwil_id else "",
                t.location.y,
                t.location.x,
                t.depth_cm,
                t.get_texture_display(),
                t.color,
                t.ph,
                t.moisture_pct,
                t.organic_c_pct,
                t.bearing_capacity_kpa,
                t.cbr_pct,
                t.get_suitability_display(),
                t.lab_name,
            )
            for t in queryset.select_related("korwil")
        )
        header = [
            _("Nomor"),
            _("Waktu"),
            _("Korwil"),
            _("Lintang"),
            _("Bujur"),
            _("Kedalaman (cm)"),
            _("Tekstur"),
            _("Warna"),
            _("pH"),
            _("Kadar air (%)"),
            _("C-organik (%)"),
            _("Daya dukung (kPa)"),
            _("CBR (%)"),
            _("Kelayakan"),
            _("Laboratorium"),
        ]
        return csv_response("uji-tanah.csv", header, rows)


# --------------------------------------------------------------------------
# Absensi
# --------------------------------------------------------------------------


@admin.register(Attendance)
class AttendanceAdmin(OperasiGISAdmin):
    scope_prefix = None
    file_kinds = {
        "check_in_photo": "absen-masuk",
        "check_out_photo": "absen-pulang",
        "attachment": "absen-lampiran",
    }
    list_display = (
        "date",
        "user",
        "status",
        "korwil",
        "check_in_time",
        "check_in_in_area",
        "check_out_time",
        "check_out_in_area",
        "worked",
        "missing_checkout",
    )
    list_filter = ("status", "korwil", "missing_checkout", "check_in_in_area", "date")
    date_hierarchy = "date"
    search_fields = ("user__username", "user__first_name", "user__last_name", "note")
    actions = ("export_csv",)
    fieldsets = (
        (None, {"fields": ("user", "date", "status", "korwil", "note", "attachment")}),
        (
            _("Masuk"),
            {
                "fields": (
                    "check_in_at",
                    "check_in_location",
                    "check_in_accuracy_m",
                    "check_in_in_area",
                    "check_in_photo",
                )
            },
        ),
        (
            _("Pulang"),
            {
                "fields": (
                    "check_out_at",
                    "check_out_location",
                    "check_out_accuracy_m",
                    "check_out_in_area",
                    "check_out_photo",
                    "missing_checkout",
                )
            },
        ),
    )

    def get_queryset(self, request):
        from operasi.views import attendance_queryset

        return attendance_queryset(request.user).select_related("user", "korwil")

    def _manages(self, request) -> bool:
        # Petugas absen lewat aplikasi (GPS & waktu server); koreksi hanya oleh Administrator.
        return aset_scope.sees_all(request.user)

    def has_add_permission(self, request):
        return self._manages(request) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return self._manages(request) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._manages(request) and super().has_delete_permission(request, obj)

    @admin.display(description=_("Masuk"), ordering="check_in_at")
    def check_in_time(self, obj):
        return (
            timezone.localtime(obj.check_in_at).strftime("%H:%M")
            if obj.check_in_at
            else "–"
        )

    @admin.display(description=_("Pulang"), ordering="check_out_at")
    def check_out_time(self, obj):
        return (
            timezone.localtime(obj.check_out_at).strftime("%H:%M")
            if obj.check_out_at
            else "–"
        )

    @admin.display(description=_("Durasi"))
    def worked(self, obj):
        minutes = obj.worked_minutes
        return f"{minutes // 60} j {minutes % 60} m" if minutes is not None else "–"

    @admin.action(description=_("Ekspor CSV"), permissions=["view"])
    def export_csv(self, request, queryset):
        rows = (
            (
                a.date,
                a.user.get_full_name() or a.user.get_username(),
                a.get_status_display(),
                a.korwil.code if a.korwil_id else "",
                _local(a.check_in_at),
                {True: _("Ya"), False: _("Tidak")}.get(a.check_in_in_area, ""),
                _local(a.check_out_at),
                {True: _("Ya"), False: _("Tidak")}.get(a.check_out_in_area, ""),
                a.worked_minutes,
                _("Ya") if a.missing_checkout else "",
                a.note,
            )
            for a in queryset.select_related("user", "korwil")
        )
        header = [
            _("Tanggal"),
            _("Petugas"),
            _("Status"),
            _("Korwil"),
            _("Masuk"),
            _("Masuk di wilayah"),
            _("Pulang"),
            _("Pulang di wilayah"),
            _("Menit kerja"),
            _("Lupa absen pulang"),
            _("Keterangan"),
        ]
        return csv_response("absensi.csv", header, rows)


# --------------------------------------------------------------------------
# Chat, SOS, Live, AI Satelit
# --------------------------------------------------------------------------


@admin.register(ChatMessage)
class ChatMessageAdmin(ReadOnlyAdminMixin, OperasiModelAdmin):
    list_display = ("created_at", "channel", "sender", "short_body", "is_system")
    list_filter = ("is_system", "korwil", "created_at")
    date_hierarchy = "created_at"
    search_fields = (
        "body",
        "sender__username",
        "sender__first_name",
        "sender__last_name",
    )
    readonly_fields = (
        "korwil",
        "sender",
        "body",
        "location",
        "is_system",
        "created_at",
    )

    @admin.display(description=_("Kanal"), ordering="korwil__code")
    def channel(self, obj):
        return obj.korwil.code if obj.korwil_id else _("Umum")

    @admin.display(description=_("Pesan"))
    def short_body(self, obj):
        return obj.body if len(obj.body) <= 80 else obj.body[:77] + "…"


@admin.register(SosAlert)
class SosAlertAdmin(OperasiGISAdmin):
    list_display = (
        "number",
        "created_at",
        "raised_by",
        "korwil",
        "status_badge",
        "acknowledged_by",
        "resolved_at",
    )
    list_filter = ("status", "korwil", "created_at")
    date_hierarchy = "created_at"
    search_fields = ("number", "message", "resolution_note")
    readonly_fields = (
        "number",
        "client_id",
        "raised_by",
        "korwil",
        "location",
        "accuracy_m",
        "message",
        "status",
        "acknowledged_by",
        "acknowledged_at",
        "resolved_by",
        "resolved_at",
        "map_link",
    )
    fields = (
        "number",
        "raised_by",
        "korwil",
        "status",
        "message",
        "location",
        "accuracy_m",
        "map_link",
        "acknowledged_by",
        "acknowledged_at",
        "resolved_by",
        "resolved_at",
        "resolution_note",
        "client_id",
    )
    actions = ("acknowledge", "resolve", "false_alarm")

    def has_add_permission(self, request):
        return False

    @admin.display(description=_("Status"), ordering="status")
    def status_badge(self, obj):
        colors = {"aktif": "#cf222e", "ditangani": "#9a6700", "selesai": "#1a7f37"}
        return badge(colors.get(obj.status, "#57606a"), obj.get_status_display())

    @admin.display(description=_("Peta"))
    def map_link(self, obj):
        if not obj.location:
            return "–"
        return format_html(
            '<a href="https://www.google.com/maps?q={},{}" target="_blank" rel="noopener">{}</a>',
            obj.location.y,
            obj.location.x,
            _("Buka di Google Maps"),
        )

    def _apply(self, request, queryset, action):
        count = 0
        for alert in queryset:
            services.update_sos(alert, action, request.user, "")
            count += 1
        messages.success(request, _("%d tanda darurat diperbarui.") % count)

    @admin.action(description=_("Tandai sedang ditangani"), permissions=["change"])
    def acknowledge(self, request, queryset):
        self._apply(request, queryset.filter(status=enums.SosStatus.ACTIVE), "tangani")

    @admin.action(description=_("Tandai selesai"), permissions=["change"])
    def resolve(self, request, queryset):
        self._apply(
            request, queryset.filter(status__in=enums.OPEN_SOS_STATUSES), "selesai"
        )

    @admin.action(description=_("Tandai alarm palsu"), permissions=["change"])
    def false_alarm(self, request, queryset):
        self._apply(
            request, queryset.filter(status__in=enums.OPEN_SOS_STATUSES), "palsu"
        )


@admin.register(OfficerPosition)
class OfficerPositionAdmin(ReadOnlyAdminMixin, OperasiGISAdmin):
    scope_prefix = None
    list_display = ("user", "updated_at", "accuracy_m", "battery_pct", "speed_mps")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    readonly_fields = (
        "user",
        "location",
        "accuracy_m",
        "heading",
        "speed_mps",
        "battery_pct",
        "updated_at",
    )


@admin.register(AreaAnalysis)
class AreaAnalysisAdmin(ReadOnlyAdminMixin, OperasiGISAdmin):
    scope_prefix = None
    list_display = (
        "created_at",
        "requested_by",
        "zoom",
        "area_ha",
        "ai_model",
        "error",
    )
    list_filter = ("created_at",)
    date_hierarchy = "created_at"
    readonly_fields = (
        "created_at",
        "requested_by",
        "bbox",
        "zoom",
        "image_preview",
        "ai_summary",
        "data_summary",
        "ai_model",
        "error",
    )
    fields = readonly_fields

    def get_queryset(self, request):
        from operasi.views import analysis_queryset

        return analysis_queryset(request.user).select_related("requested_by")

    @admin.display(description=_("Luas (ha)"))
    def area_ha(self, obj):
        return (obj.data_summary or {}).get("luas_ha", "–")

    @admin.display(description=_("Citra"))
    def image_preview(self, obj):
        if not obj.image:
            return "–"
        from operasi.views import file_url

        url = file_url("citra", obj) + "?lihat=1"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">'
            '<img src="{}" alt="" style="max-width:480px;max-height:480px"></a>',
            url,
            url,
        )

    @admin.display(description=_("Hasil AI"))
    def ai_summary(self, obj):
        result = obj.ai_result or {}
        if not result:
            return "–"
        cover = result.get("tutupan_lahan") or {}
        rows = [
            (str(k).replace("_pct", "").replace("_", " "), f"{v}%")
            for k, v in cover.items()
        ]
        rows.append(
            (_("Perkiraan bangunan"), result.get("perkiraan_jumlah_bangunan", "–"))
        )
        return format_html(
            "<p>{}</p>{}<p><b>{}</b></p><ul>{}</ul><p><b>{}</b></p><ul>{}</ul>",
            result.get("ringkasan", ""),
            format_html_join("", "<div><b>{}</b>: {}</div>", rows),
            _("Temuan"),
            format_html_join(
                "", "<li>{}</li>", ((t,) for t in result.get("temuan", []))
            ),
            _("Rekomendasi"),
            format_html_join(
                "", "<li>{}</li>", ((t,) for t in result.get("rekomendasi", []))
            ),
        )
