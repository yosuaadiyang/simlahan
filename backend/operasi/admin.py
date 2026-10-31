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
from operasi import daily_reports, enums, geo, hierarchy, services
from operasi.models import (
    Activity,
    ActivityPhoto,
    ActivityWeight,
    AreaAnalysis,
    Attendance,
    ChatMessage,
    CommandSettings,
    DailyReport,
    DailyReportAttachment,
    DailyReportEvent,
    HuntingParkFinding,
    HuntingParkPatrol,
    IllegalFinding,
    IllegalFindingVisit,
    Korwil,
    LandAreaChange,
    LandPlot,
    LandPlotChange,
    OfficerPosition,
    OfficerProfile,
    OfficerTrackPoint,
    PatrolObservation,
    PatrolSession,
    Resident,
    Seedling,
    SitePhoto360,
    SoilTest,
    SosAlert,
    StanceChange,
    SystemLock,
    TaskEvent,
    TaskPoint,
    ThreatZone,
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
    # Bila diisi, baris hanya dapat diubah oleh pembuatnya (field ini),
    # koordinator Korwil-nya, atau pengawas (Administrator / Petugas Aset Lahan).
    owner_field: str | None = None

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        if obj is None or self.owner_field is None or geo.is_supervisor(request.user):
            return True
        user = request.user
        if getattr(obj, f"{self.owner_field}_id") == user.pk:
            return True
        return bool(obj.korwil_id and obj.korwil.coordinator_id == user.pk)

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
            _("Poin usaha kegiatan"),
            {
                "fields": (
                    "scoring_mode",
                    "effort_target_multiplier",
                    "effort_base_default",
                    ("effort_per_finding", "effort_finding_max"),
                    ("effort_per_photo", "effort_photo_max"),
                    ("effort_narrative_bonus", "effort_narrative_min_chars"),
                    ("effort_per_km", "effort_km_max"),
                    "effort_geotag_bonus",
                ),
                "description": _(
                    "Poin usaha = poin dasar jenis (Bobot kegiatan KPI; Komsos per "
                    "warga yang ditemui; Kegiatan lainnya dari rubrik dampak 3/6/9/12) "
                    "+ bonus temuan, foto, narasi lengkap, jarak tempuh, dan lokasi "
                    "GPS. Klaim dampak Signifikan/Kritis dihitung 6 poin sampai "
                    "dikonfirmasi atasan."
                ),
            },
        ),
        (
            _("Peta, Live & SOS"),
            {"fields": ("online_minutes", "sos_emails", "satellite_tile_url")},
        ),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if {f for f in form.changed_data if f.startswith("effort_")}:
            services.recompute_effort()


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


class LandAreaChangeInline(StanceChangeInline):
    model = LandAreaChange
    fields = ("changed_at", "old_area_m2", "new_area_m2", "changed_by", "activity")
    readonly_fields = fields


NIK_FIELDS = ("nik", "family_card_number")


def sees_nik(request) -> bool:
    return request.user.has_perm("operasi.view_resident_nik")


@admin.register(Resident)
class ResidentAdmin(OperasiGISAdmin):
    list_select_related = ("korwil",)
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
    readonly_fields = (
        "number",
        "last_visited_on",
        "created_by",
        "registered_activity",
        "visits",
    )
    inlines = (StanceChangeInline, LandAreaChangeInline)
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
            {
                "fields": (
                    "stance",
                    "land_status",
                    "rtrw_status",
                    "rtrw_zone",
                    "relocation_choice",
                )
            },
        ),
        (
            _("Detail sosial-ekonomi"),
            {
                "fields": (
                    "gender",
                    "age",
                    "occupation",
                    "origin",
                    "years_living",
                    "residency_status",
                    "spouse_name",
                    "spouse_occupation",
                    "child_count",
                    "children_detail",
                    "land_area_m2",
                    "cultivation_status",
                    "land_condition",
                )
            },
        ),
        (
            _("Keterkaitan modul lain"),
            {"fields": ("pengadaan_household", "pengadaan_parcel", "land_asset")},
        ),
        (
            _("Riwayat"),
            {
                "fields": (
                    "last_visited_on",
                    "visits",
                    "created_by",
                    "registered_activity",
                    "note",
                )
            },
        ),
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

    # Tautan ke modul lain: tanpa izin melihat modul itu, jendela pencarian
    # raw_id berujung 403, jadi kolomnya hanya ditampilkan (baca saja).
    LINKED_FIELD_PERMS = (
        ("pengadaan_household", "pengadaan.view_affectedhousehold"),
        ("pengadaan_parcel", "pengadaan.view_acquisitionparcel"),
        ("land_asset", "asetlahan.view_landasset"),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        for name, perm in self.LINKED_FIELD_PERMS:
            if name not in fields and not request.user.has_perm(perm):
                fields.append(name)
        return fields

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if sees_nik(request):
            return fieldsets
        # Tanpa izin NIK, kolom NIK & KK tidak tampil (dan tidak ikut formulir).
        return [
            (
                name,
                {
                    **options,
                    "fields": tuple(
                        f for f in options["fields"] if f not in NIK_FIELDS
                    ),
                },
            )
            for name, options in fieldsets
        ]

    def get_search_results(self, request, queryset, search_term):
        results, distinct = super().get_search_results(request, queryset, search_term)
        digits = "".join(ch for ch in search_term if ch.isdigit())
        if len(digits) == 16 and sees_nik(request):
            from pengadaan.crypto import fingerprint

            results = results | queryset.filter(nik_fingerprint=fingerprint(digits))
        return results, distinct

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        obj._changed_by = request.user
        geo.assign_korwil(obj, request.user, strict=False)
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
                    _("%(c)d warga dibuat, %(u)d diperbarui, %(s)d dilewati.")
                    % {
                        "c": result["created"],
                        "u": result["updated"],
                        "s": result.get("skipped", 0),
                    },
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
                "(relokasi/uang/geser), <code>catatan</code>, <code>zona</code> "
                "(lindung/budi daya/khusus/lainnya), <code>jenis_kelamin</code> (L/P), "
                "<code>umur</code>, <code>pekerjaan</code>, <code>asal</code>, "
                "<code>lama_menetap</code>, <code>pasangan</code>, <code>anak</code>, "
                "<code>luas_lahan</code> (m²), <code>penggarapan</code> "
                "(digarapi/disewakan/tidak), <code>kondisi_lahan</code>. Warga di wilayah kerja Anda "
                "dengan NIK yang sudah ada diperbarui (catatan ditambahkan); baris lain "
                "dengan NIK yang tidak dapat dipakai dilewati."
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


@admin.register(ActivityWeight)
class ActivityWeightAdmin(admin.ModelAdmin):
    list_display = ("activity_type", "points")
    list_editable = ("points",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        services.recompute_effort(
            Activity.objects.filter(activity_type=obj.activity_type)
        )

    def delete_model(self, request, obj):
        activity_type = obj.activity_type
        super().delete_model(request, obj)
        services.recompute_effort(Activity.objects.filter(activity_type=activity_type))

    def has_add_permission(self, request):
        return request.user.has_perm("operasi.change_commandsettings")

    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm("operasi.change_commandsettings")


@admin.register(Activity)
class ActivityAdmin(OperasiGISAdmin):
    owner_field = "reported_by"
    list_display = (
        "number",
        "title",
        "activity_type",
        "korwil",
        "started_at",
        "reported_by",
        "participants_count",
        "photo_count",
        "effort_points",
        "impact_badge",
        "verified",
    )
    list_display_links = ("number", "title")
    list_filter = (
        "activity_type",
        "korwil",
        "verified",
        "impact_confirmed",
        "started_at",
    )
    date_hierarchy = "started_at"
    search_fields = ("number", "title", "description", "outcome")
    autocomplete_fields = ("residents", "task")
    readonly_fields = (
        "number",
        "client_id",
        "reported_by",
        "verified_by",
        "verified_at",
        "effort_points",
        "impact_summary",
        "impact_confirmed",
        "impact_confirmed_by",
        "impact_confirmed_at",
        "ai_stance",
        "special_parts",
    )
    inlines = (ActivityPhotoInline,)
    file_kinds = {"voice_note": "kegiatan-suara"}
    actions = ("mark_verified", "confirm_impact", "export_csv")
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
                    "companion",
                )
            },
        ),
        (
            _("Lokasi"),
            {"fields": ("location_name", "location", "accuracy_m", "distance_m")},
        ),
        (
            _("Penilaian dampak (Kegiatan lainnya)"),
            {
                "fields": (
                    "impact_scope",
                    "impact_risk",
                    "impact_result",
                    "impact_summary",
                    "impact_confirmed",
                    "impact_confirmed_by",
                    "impact_confirmed_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Hasil"),
            {
                "fields": (
                    "participants_count",
                    "residents",
                    "outcome",
                    "voice_note",
                    "task",
                    "ai_stance",
                    "special_parts",
                    "effort_points",
                )
            },
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

    @admin.display(description=_("Dampak"))
    def impact_badge(self, obj):
        if not obj.impact_tier:
            return "–"
        label = enums.ImpactTier(obj.impact_tier).label
        if obj.needs_impact_confirmation:
            return badge("#bf8700", _("%s (menunggu konfirmasi)") % label)
        return badge("#1a7f37", label)

    @admin.display(description=_("Tingkat dampak"))
    def impact_summary(self, obj):
        if not obj.impact_tier:
            return "–"
        tier = enums.ImpactTier(obj.impact_tier)
        text = _("%(label)s (skor %(score)s, %(points)s poin)") % {
            "label": tier.label,
            "score": obj.impact_score,
            "points": enums.IMPACT_POINTS[tier],
        }
        if obj.needs_impact_confirmation:
            text += " – " + str(_("sementara dihitung 6 poin sampai dikonfirmasi"))
        return text

    @admin.display(description=_("Bagian khusus"))
    def special_parts(self, obj):
        if not obj.pk:
            return "–"
        links = []
        visit = IllegalFindingVisit.objects.filter(activity=obj).first()
        if visit is not None:
            links.append(
                (
                    reverse(
                        "admin:operasi_illegalfinding_change", args=[visit.finding_id]
                    ),
                    _("Temuan ilegal %s") % visit.finding.number,
                )
            )
        report = HuntingParkPatrol.objects.filter(activity=obj).first()
        if report is not None:
            links.append(
                (
                    reverse("admin:operasi_huntingparkpatrol_change", args=[report.pk]),
                    _("Laporan patroli Taman Buru"),
                )
            )
        for session in obj.patrol_sessions.all():
            links.append(
                (
                    reverse("admin:operasi_patrolsession_change", args=[session.pk]),
                    _("Jejak SMART %s") % session.number,
                )
            )
        for resident in obj.registered_residents.all():
            links.append(
                (
                    reverse("admin:operasi_resident_change", args=[resident.pk]),
                    _("Warga baru %s") % resident,
                )
            )
        if not links:
            return "–"
        return format_html_join(format_html("<br>"), '<a href="{}">{}</a>', links)

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if aset_scope.sees_all(request.user):
            return fields
        # Verifikasi oleh koordinator lewat tindakan/pusat komando, bukan kotak centang.
        return (*fields, "verified")

    def save_model(self, request, obj, form, change):
        if not change and obj.reported_by_id is None:
            obj.reported_by = request.user
        if "verified" in form.changed_data:
            obj.verified_by = request.user if obj.verified else None
        geo.assign_korwil(obj, request.user, strict=False)
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.touch_residents()
        form.instance.refresh_effort()

    @admin.action(
        description=_("Konfirmasi dampak tinggi (Kegiatan lainnya)"),
        permissions=["change"],
    )
    def confirm_impact(self, request, queryset):
        if not aset_scope.sees_all(request.user):
            queryset = queryset.filter(korwil__coordinator=request.user)
        count = 0
        # Pelapor tidak boleh mengonfirmasi klaim dampaknya sendiri.
        for activity in queryset.exclude(reported_by=request.user).filter(
            activity_type=enums.ActivityType.OTHER, impact_confirmed=False
        ):
            if not activity.needs_impact_confirmation:
                continue
            activity.impact_confirmed = True
            activity.impact_confirmed_by = request.user
            activity.impact_confirmed_at = timezone.now()
            activity.save()
            activity.refresh_effort()
            count += 1
        messages.success(request, _("%d klaim dampak dikonfirmasi.") % count)

    @admin.action(description=_("Tandai sudah diverifikasi"), permissions=["change"])
    def mark_verified(self, request, queryset):
        if not aset_scope.sees_all(request.user):
            # Koordinator hanya memverifikasi laporan Korwil yang dipimpinnya.
            queryset = queryset.filter(korwil__coordinator=request.user)
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
                a.location_name,
                a.effort_points,
                enums.ImpactTier(a.impact_tier).label if a.impact_tier else "",
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
            _("Nama lokasi"),
            _("Poin usaha"),
            _("Tingkat dampak"),
            _("Diverifikasi"),
        ]
        return csv_response("kegiatan.csv", header, rows)


# --------------------------------------------------------------------------
# Temuan ilegal & patroli Taman Buru
# --------------------------------------------------------------------------


class IllegalFindingVisitInline(admin.TabularInline):
    model = IllegalFindingVisit
    extra = 0
    can_delete = False
    fields = (
        "activity_link",
        "is_new",
        "permit",
        "business_activity",
        "persons_involved",
        "equipment",
        "buildings",
        "follow_up",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description=_("Kegiatan"))
    def activity_link(self, obj):
        return format_html(
            '<a href="{}">{}</a> {}',
            reverse("admin:operasi_activity_change", args=[obj.activity_id]),
            obj.activity.number,
            _local(obj.activity.started_at),
        )


@admin.register(IllegalFinding)
class IllegalFindingAdmin(OperasiGISAdmin):
    owner_field = "created_by"
    list_select_related = ("korwil",)
    list_display = (
        "number",
        "kind_badge",
        "location_name",
        "korwil",
        "owner_name",
        "area_ha",
        "visit_count",
        "created_at",
    )
    list_display_links = ("number", "location_name")
    list_filter = ("activity_kind", "korwil")
    search_fields = ("number", "location_name", "owner_name", "manager_name")
    readonly_fields = ("number", "created_by")
    inlines = (IllegalFindingVisitInline,)
    actions = ("export_csv",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "number",
                    "activity_kind",
                    "location_name",
                    "korwil",
                    "location",
                )
            },
        ),
        (
            _("Pemilik & pengurus"),
            {
                "fields": (
                    "owner_name",
                    "owner_phone",
                    "owner_domicile",
                    "manager_name",
                    "manager_phone",
                )
            },
        ),
        (
            _("Lahan & usaha"),
            {"fields": ("area_ha", "forest_status", "business_started")},
        ),
        (_("Catatan"), {"fields": ("note", "created_by")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_visits=Count("visits"))

    @admin.display(description=_("Aktivitas"), ordering="activity_kind")
    def kind_badge(self, obj):
        return badge(
            enums.ILLEGAL_COLORS.get(obj.activity_kind, "#57606a"),
            obj.get_activity_kind_display(),
        )

    @admin.display(description=_("Kunjungan"), ordering="_visits")
    def visit_count(self, obj):
        return obj._visits

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        geo.assign_korwil(obj, request.user, strict=False)
        super().save_model(request, obj, form, change)

    @admin.action(description=_("Ekspor CSV"), permissions=["view"])
    def export_csv(self, request, queryset):
        rows = (
            (
                f.number,
                f.get_activity_kind_display(),
                f.location_name,
                f.korwil.code if f.korwil_id else "",
                f.owner_name,
                f.owner_phone,
                f.owner_domicile,
                f.manager_name,
                f.manager_phone,
                f.area_ha if f.area_ha is not None else "",
                f.forest_status,
                f.business_started,
                f.location.y if f.location else "",
                f.location.x if f.location else "",
                f.visits.count(),
            )
            for f in queryset.select_related("korwil")
        )
        header = [
            _("Nomor"),
            _("Aktivitas"),
            _("Lokasi"),
            _("Korwil"),
            _("Pemilik"),
            _("No. HP pemilik"),
            _("Domisili pemilik"),
            _("Pengurus"),
            _("No. HP pengurus"),
            _("Luas (ha)"),
            _("Status hutan"),
            _("Mulai usaha"),
            _("Lintang"),
            _("Bujur"),
            _("Kunjungan"),
        ]
        return csv_response("temuan-ilegal.csv", header, rows)


class HuntingParkFindingInline(admin.TabularInline):
    model = HuntingParkFinding
    extra = 0
    fields = (
        "category",
        "description",
        "quantity",
        "forest_status",
        "new_activity",
        "note",
    )


class SeedlingInline(admin.TabularInline):
    model = Seedling
    extra = 0
    fields = ("kind", "species", "quantity")


@admin.register(HuntingParkPatrol)
class HuntingParkPatrolAdmin(OperasiModelAdmin):
    scope_prefix = "activity__korwil"
    list_select_related = ("activity", "activity__korwil", "activity__reported_by")
    list_display = (
        "activity_link",
        "location",
        "korwil",
        "grid",
        "situation",
        "finding_count",
        "tended",
        "produced",
    )
    list_filter = ("situation", "activity__korwil", "activity__started_at")
    search_fields = ("activity__number", "activity__location_name", "grid", "team")
    readonly_fields = ("activity_link",)
    inlines = (HuntingParkFindingInline, SeedlingInline)
    fieldsets = (
        (None, {"fields": ("activity_link", "input_mode", "grid", "routes")}),
        (
            _("Tim"),
            {
                "fields": (
                    "objective",
                    "team_leader",
                    "team",
                    "station",
                    "transport",
                    "patrol_started_at",
                    "patrol_ended_at",
                )
            },
        ),
        (
            _("Kondisi"),
            {
                "fields": (
                    "situation",
                    "personnel_condition",
                    "materiel_condition",
                    ("weather_morning", "weather_noon", "weather_afternoon"),
                    "obstacles",
                    "suggestions",
                )
            },
        ),
    )

    def has_add_permission(self, request):
        # Dibuat dari laporan Taman Buru di pusat komando.
        return False

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        if obj is None or geo.is_supervisor(request.user):
            return True
        activity = obj.activity
        return activity.reported_by_id == request.user.pk or bool(
            activity.korwil_id and activity.korwil.coordinator_id == request.user.pk
        )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_findings=Count("findings", distinct=True))
            .prefetch_related("seedlings")
        )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.activity.refresh_effort()

    @admin.display(description=_("Kegiatan"), ordering="activity__started_at")
    def activity_link(self, obj):
        return format_html(
            '<a href="{}">{}</a> {}',
            reverse("admin:operasi_activity_change", args=[obj.activity_id]),
            obj.activity.number,
            _local(obj.activity.started_at),
        )

    @admin.display(description=_("Lokasi"))
    def location(self, obj):
        return obj.activity.location_name

    @admin.display(description=_("Korwil"))
    def korwil(self, obj):
        return obj.activity.korwil or "–"

    @admin.display(description=_("Temuan"), ordering="_findings")
    def finding_count(self, obj):
        return obj._findings

    @admin.display(description=_("Bibit dirawat"))
    def tended(self, obj):
        return obj.seedling_total(enums.SeedlingKind.TENDED)

    @admin.display(description=_("Bibit diproduksi"))
    def produced(self, obj):
        return obj.seedling_total(enums.SeedlingKind.PRODUCED)


class PatrolObservationInline(admin.TabularInline):
    model = PatrolObservation
    extra = 0
    can_delete = False
    fields = ("seq", "kind", "observed_at", "comment", "photo_links")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description=_("Foto"))
    def photo_links(self, obj):
        photos = list(obj.photos.all())
        if not photos:
            return "–"
        return format_html_join(
            " ",
            '<a href="{}" target="_blank" rel="noopener">📷</a>',
            (
                (reverse("operasi-file", args=["patroli-foto", p.pk]) + "?lihat=1",)
                for p in photos
            ),
        )


@admin.register(PatrolSession)
class PatrolSessionAdmin(ReadOnlyAdminMixin, OperasiGISAdmin):
    list_select_related = ("korwil", "activity", "uploaded_by")
    list_display = (
        "number",
        "name",
        "korwil",
        "started_at",
        "leader",
        "distance_m",
        "obs_count",
        "activity",
    )
    list_display_links = ("number", "name")
    list_filter = ("korwil", "started_at")
    search_fields = ("number", "name", "leader", "team", "smart_patrol_id")
    inlines = (PatrolObservationInline,)
    change_list_template = "admin/operasi/patrolsession/change_list.html"
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "number",
                    "name",
                    "korwil",
                    "activity",
                    "smart_patrol_id",
                    "source_name",
                    "uploaded_by",
                )
            },
        ),
        (
            _("Patroli"),
            {
                "fields": (
                    "started_at",
                    "ended_at",
                    "leader",
                    "team",
                    "station",
                    "transport",
                    "distance_m",
                    "comments",
                    "track",
                )
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_obs=Count("observations"))

    @admin.display(description=_("Observasi"), ordering="_obs")
    def obs_count(self, obj):
        return obj._obs

    def get_urls(self):
        return [
            path(
                "impor/",
                self.admin_site.admin_view(self.import_view),
                name="operasi_patrolsession_import",
            ),
        ] + super().get_urls()

    def import_view(self, request):
        if not request.user.has_perm("operasi.add_patrolsession"):
            raise PermissionDenied
        form = ImportForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            from django.core.exceptions import ValidationError

            from operasi import patrol

            upload = form.cleaned_data["file"]
            try:
                if upload.size > patrol.MAX_FILE_BYTES:
                    raise ValidationError(_("Berkas SMART maksimal 15 MB."))
                session = patrol.save_session(
                    patrol.parse(upload.read()), request.user, None, upload.name
                )
            except ValidationError as error:
                messages.error(request, " ".join(error.messages))
            else:
                messages.success(
                    request,
                    _("Jejak patroli %(n)s tersimpan (%(o)d observasi).")
                    % {"n": session.number, "o": session.observations.count()},
                )
                return HttpResponseRedirect(
                    reverse("admin:operasi_patrolsession_change", args=[session.pk])
                )
        return _import_page(
            self,
            request,
            form,
            _("Impor patroli SMART"),
            _(
                "Berkas <code>.json</code> (GeoJSON) hasil ekspor SMART Mobile / "
                "CyberTracker. Jalur, observasi, dan foto disimpan dan tampil di "
                "lapisan <b>Patroli SMART</b> pusat komando. Maksimal 15 MB."
            ),
        )


@admin.register(SoilTest)
class SoilTestAdmin(OperasiGISAdmin):
    owner_field = "sampled_by"
    file_kinds = {"photo": "tanah-foto", "lab_report": "tanah-lab"}
    list_select_related = ("korwil", "sampled_by")
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
        geo.assign_korwil(obj, request.user, strict=False)
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
        "approval",
    )
    list_filter = (
        "status",
        "approval",
        "korwil",
        "missing_checkout",
        "check_in_in_area",
        "date",
    )
    date_hierarchy = "date"
    search_fields = ("user__username", "user__first_name", "user__last_name", "note")
    actions = ("approve_leave", "reject_leave", "export_csv")
    readonly_fields = ("approved_by", "approved_at")
    fieldsets = (
        (None, {"fields": ("user", "date", "status", "korwil", "note", "attachment")}),
        (
            _("Persetujuan izin"),
            {"fields": ("approval", "approved_by", "approved_at")},
        ),
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

    def save_model(self, request, obj, form, change):
        if obj.status not in enums.ABSENCE_STATUSES:
            obj.approval = ""
            obj.approved_by, obj.approved_at = None, None
        elif not obj.approval:
            # Izin yang dicatat langsung oleh Administrator dianggap disetujui.
            obj.approval = enums.LeaveApproval.APPROVED
        if obj.approval and (
            "approval" in form.changed_data or obj.approved_by_id is None
        ):
            obj.approved_by, obj.approved_at = request.user, timezone.now()
        super().save_model(request, obj, form, change)

    def _decide(self, request, queryset, approve: bool):
        pending = services.leave_requests(request.user).filter(
            pk__in=queryset.values("pk")
        )
        count = 0
        for record in pending:
            services.decide_leave(record, request.user, approve)
            count += 1
        messages.success(request, _("%d pengajuan izin diputuskan.") % count)

    @admin.action(description=_("Setujui pengajuan izin"), permissions=["change"])
    def approve_leave(self, request, queryset):
        self._decide(request, queryset, True)

    @admin.action(description=_("Tolak pengajuan izin"), permissions=["change"])
    def reject_leave(self, request, queryset):
        self._decide(request, queryset, False)

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
                a.status_text,
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
    scope_prefix = None
    list_select_related = ("korwil", "sender")
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

    def get_queryset(self, request):
        return super().get_queryset(request).filter(services.chat_q(request.user))

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

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(user__in=services.visible_officers(request.user))
            .select_related("user")
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


# --------------------------------------------------------------------------
# Struktur atasan, riwayat & poin tugas, laporan harian berjenjang
# --------------------------------------------------------------------------


@admin.register(OfficerProfile)
class OfficerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "position", "supervisor", "effective_supervisor")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "position",
    )
    autocomplete_fields = ("user", "supervisor")
    list_select_related = ("user", "supervisor")

    @admin.display(description=_("Laporan dikirim ke"))
    def effective_supervisor(self, obj):
        boss = hierarchy.supervisor_of(obj.user)
        if boss is None:
            return _("— (pimpinan tertinggi)")
        return boss.get_full_name() or boss.get_username()


@admin.register(TaskEvent)
class TaskEventAdmin(ReadOnlyAdminMixin, OperasiGISAdmin):
    scope_prefix = "task__korwil"
    list_display = ("created_at", "task", "kind", "actor", "note_short")
    list_filter = ("kind",)
    search_fields = ("task__number", "task__title", "note")
    list_select_related = ("task", "actor")
    file_kinds = {"photo": "tugas-foto"}
    readonly_fields = (
        "task",
        "kind",
        "actor",
        "note",
        "photo",
        "location",
        "created_at",
    )

    @admin.display(description=_("Catatan"))
    def note_short(self, obj):
        return (obj.note or "")[:80]

    def get_queryset(self, request):
        from operasi import task_flow

        return (
            super()
            .get_queryset(request)
            .filter(task__in=task_flow.visible_tasks(request.user).values("pk"))
        )


@admin.register(TaskPoint)
class TaskPointAdmin(ReadOnlyAdminMixin, OperasiModelAdmin):
    scope_prefix = "task__korwil"
    list_display = ("awarded_at", "user", "points", "role", "task")
    list_filter = ("role",)
    search_fields = (
        "task__number",
        "user__username",
        "user__first_name",
        "user__last_name",
    )
    list_select_related = ("task", "user")
    readonly_fields = ("task", "user", "role", "points", "awarded_at")

    def get_queryset(self, request):
        from operasi import task_flow

        queryset = super().get_queryset(request)
        if aset_scope.sees_all(request.user):
            return queryset
        return queryset.filter(
            Q(user=request.user)
            | Q(task__in=task_flow.visible_tasks(request.user).values("pk"))
        )


class DailyReportEventInline(admin.TabularInline):
    model = DailyReportEvent
    extra = 0
    can_delete = False
    fields = ("created_at", "action", "actor", "target", "note")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class DailyReportAttachmentInline(admin.TabularInline):
    model = DailyReportAttachment
    extra = 0
    can_delete = False
    fields = ("name", "file", "uploaded_by", "uploaded_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "file":
            kwargs["widget"] = PrivateFileWidget("laporan-lampiran")
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(DailyReport)
class DailyReportAdmin(ReadOnlyAdminMixin, OperasiModelAdmin):
    """Laporan harian dikirim, direvisi, dan dirangkum dari pusat komando."""

    scope_prefix = None
    list_display = (
        "number",
        "report_date",
        "author",
        "recipient",
        "korwil",
        "status",
        "revision_owner",
    )
    list_filter = ("status", "korwil", "report_date", "ai_generated")
    search_fields = (
        "number",
        "content",
        "author__username",
        "author__first_name",
        "author__last_name",
    )
    list_select_related = ("author", "recipient", "korwil", "revision_owner")
    date_hierarchy = "report_date"
    inlines = (DailyReportAttachmentInline, DailyReportEventInline)
    fields = (
        "number",
        "report_date",
        "author",
        "author_position",
        "recipient",
        "korwil",
        "status",
        "consolidated_into",
        "revision_owner",
        "return_note",
        "returned_by",
        "returned_at",
        "reviewed_by",
        "reviewed_at",
        "ai_generated",
        "sent_at",
        "content",
    )
    readonly_fields = fields

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.filter(
            pk__in=daily_reports.visible_reports(request.user).values("pk")
        )


# --------------------------------------------------------------------------
# Peta & spasial
# --------------------------------------------------------------------------


class LandPlotChangeInline(admin.TabularInline):
    model = LandPlotChange
    extra = 0
    can_delete = False
    fields = ("changed_at", "old_status", "new_status", "changed_by", "note")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(LandPlot)
class LandPlotAdmin(OperasiGISAdmin):
    owner_field = "created_by"
    list_select_related = ("korwil", "resident")
    list_display = (
        "number",
        "name",
        "owner_name",
        "korwil",
        "area_display",
        "status_badge",
        "urgency",
        "controlled_on",
    )
    list_filter = ("control_status", "urgency", "korwil")
    search_fields = ("number", "name", "owner_name", "guard_name", "control_team")
    readonly_fields = ("number", "measured_area_ha", "created_by")
    autocomplete_fields = ("resident",)
    inlines = (LandPlotChangeInline,)
    actions = ("export_csv",)
    fieldsets = (
        (None, {"fields": ("number", "name", "owner_name", "guard_name", "korwil")}),
        (
            _("Penguasaan"),
            {
                "fields": (
                    "control_status",
                    "controlled_on",
                    "control_team",
                    "urgency",
                    "resident",
                )
            },
        ),
        (
            _("Batas & luas"),
            {"fields": ("geometry", "official_area_ha", "measured_area_ha")},
        ),
        (_("Lainnya"), {"fields": ("source", "note", "created_by")}),
    )

    @admin.display(description=_("Luas (ha)"))
    def area_display(self, obj):
        return obj.area_ha

    @admin.display(description=_("Status"), ordering="control_status")
    def status_badge(self, obj):
        return badge(
            enums.CONTROL_COLORS.get(obj.control_status, "#57606a"),
            obj.get_control_status_display(),
        )

    def save_model(self, request, obj, form, change):
        old = ""
        if change:
            old = (
                LandPlot.objects.filter(pk=obj.pk)
                .values_list("control_status", flat=True)
                .first()
                or ""
            )
        else:
            obj.created_by = request.user
        if obj.control_status != enums.ControlStatus.CONTROLLED:
            obj.controlled_on = None
        elif obj.controlled_on is None:
            obj.controlled_on = timezone.localdate()
        if obj.korwil_id is None and obj.geometry is not None:
            obj.korwil = geo.korwil_for_write(
                request.user, obj.geometry.point_on_surface, strict=False
            )
        super().save_model(request, obj, form, change)
        if old != obj.control_status:
            LandPlotChange.objects.create(
                plot=obj,
                old_status=old,
                new_status=obj.control_status,
                changed_by=request.user,
                note=_("Diubah di panel admin"),
            )

    @admin.action(description=_("Ekspor CSV"), permissions=["view"])
    def export_csv(self, request, queryset):
        rows = (
            (
                p.number,
                p.name,
                p.owner_name,
                p.guard_name,
                p.korwil.code if p.korwil_id else "",
                p.get_control_status_display(),
                p.controlled_on or "",
                p.control_team,
                p.get_urgency_display(),
                p.official_area_ha if p.official_area_ha is not None else "",
                p.measured_area_ha if p.measured_area_ha is not None else "",
                p.source,
            )
            for p in queryset.select_related("korwil")
        )
        header = [
            _("Nomor"),
            _("Nama / titik bidang"),
            _("Pemilik"),
            _("Penjaga lahan"),
            _("Korwil"),
            _("Status penguasaan"),
            _("Tanggal dikuasai"),
            _("Tim penguasaan"),
            _("Urgensi"),
            _("Luas resmi (ha)"),
            _("Luas terukur (ha)"),
            _("Sumber data"),
        ]
        return csv_response("bidang-penguasaan.csv", header, rows)


@admin.register(ThreatZone)
class ThreatZoneAdmin(OperasiGISAdmin):
    owner_field = "created_by"
    list_select_related = ("korwil", "created_by")
    list_display = ("name", "level_badge", "korwil", "is_active", "created_by")
    list_filter = ("level", "is_active", "korwil")
    search_fields = ("name", "note")
    readonly_fields = ("created_by",)
    fields = ("name", "level", "korwil", "is_active", "geometry", "note", "created_by")

    @admin.display(description=_("Tingkat"), ordering="level")
    def level_badge(self, obj):
        return badge(
            enums.THREAT_COLORS.get(obj.level, "#57606a"), obj.get_level_display()
        )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        if obj.korwil_id is None and obj.geometry is not None:
            obj.korwil = geo.korwil_for_write(
                request.user, obj.geometry.point_on_surface, strict=False
            )
        super().save_model(request, obj, form, change)


@admin.register(SitePhoto360)
class SitePhoto360Admin(OperasiGISAdmin):
    owner_field = "uploaded_by"
    file_kinds = {"image": "foto-360"}
    list_select_related = ("korwil", "uploaded_by")
    list_display = ("title", "korwil", "captured_on", "uploaded_by", "created_at")
    list_filter = ("korwil", "captured_on")
    search_fields = ("title", "note")
    readonly_fields = ("uploaded_by",)
    fields = (
        "title",
        "korwil",
        "captured_on",
        "location",
        "image",
        "note",
        "uploaded_by",
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploaded_by = request.user
        geo.assign_korwil(obj, request.user, strict=False)
        super().save_model(request, obj, form, change)


@admin.register(OfficerTrackPoint)
class OfficerTrackPointAdmin(ReadOnlyAdminMixin, OperasiGISAdmin):
    scope_prefix = None
    list_display = ("user", "recorded_at", "accuracy_m")
    list_filter = ("recorded_at",)
    date_hierarchy = "recorded_at"
    search_fields = ("user__username", "user__first_name", "user__last_name")
    readonly_fields = ("user", "location", "accuracy_m", "recorded_at")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(user__in=services.visible_officers(request.user))
            .select_related("user")
        )
