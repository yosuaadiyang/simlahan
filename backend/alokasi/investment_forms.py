"""Formulir portal investasi (investor) dan panel petugas permintaan investasi."""

import datetime
import json

from django import forms
from django.contrib.gis.gdal.error import GDALException
from django.contrib.gis.geos import GEOSException, GEOSGeometry, MultiPolygon
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from alokasi import enums
from alokasi.models import (
    MAX_REQUEST_AREA_M2,
    MAX_REQUEST_VERTICES,
    InvestmentMessage,
    InvestmentRequest,
    InvestmentSector,
    InvestmentZone,
    LandPlot,
)

DATE_INPUT = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
MAX_PLOTS_PER_REQUEST = 10


def available_plots():
    """Lahan yang dapat diminati/ditawarkan: terbit, tersedia, dan punya skema."""
    return (
        LandPlot.objects.filter(is_published=True, status=enums.PlotStatus.AVAILABLE)
        .filter(Q(offer_allocation=True) | Q(offer_lease=True))
        .select_related("sector")
        .order_by("code")
    )


def _load_geojson(value: str):
    if len(value) > 200_000:
        raise forms.ValidationError(_("Gambar lokasi terlalu rumit."))
    try:
        data = json.loads(value)
        if isinstance(data, dict) and data.get("type") == "Feature":
            data = data.get("geometry")
        if not isinstance(data, dict) or data.get("type") not in (
            "Polygon",
            "MultiPolygon",
        ):
            raise ValueError
        geom = GEOSGeometry(json.dumps(data), srid=4326)
    except (ValueError, TypeError, GEOSException, GDALException):
        raise forms.ValidationError(
            _("Gambar lokasi tidak valid. Gambar ulang di peta.")
        )
    if geom.geom_type == "Polygon":
        geom = MultiPolygon(geom, srid=4326)
    return geom


def _repair(geom) -> MultiPolygon:
    """Perbaiki gambar yang bersilangan; tolak bila tidak membentuk bidang."""
    not_area = forms.ValidationError(
        _("Gambar lokasi tidak membentuk bidang. Gambar ulang di peta.")
    )
    if not geom.valid:
        geom = geom.buffer(0)
        if geom.geom_type == "Polygon":
            geom = MultiPolygon(geom, srid=4326)
        if geom.empty or geom.geom_type != "MultiPolygon":
            raise not_area
    return geom


def parse_area(value: str) -> MultiPolygon | None:
    """GeoJSON (Polygon/MultiPolygon/Feature) dari peta gambar → MultiPolygon 4326."""
    value = (value or "").strip()
    if not value:
        return None
    geom = _load_geojson(value)
    if geom.num_coords > MAX_REQUEST_VERTICES:
        raise forms.ValidationError(
            _("Gambar lokasi maksimal %d titik.") % MAX_REQUEST_VERTICES
        )
    xmin, ymin, xmax, ymax = geom.extent
    if xmin < -180 or xmax > 180 or ymin < -90 or ymax > 90:
        raise forms.ValidationError(_("Koordinat gambar lokasi di luar batas peta."))
    geom = _repair(geom)
    from asetlahan.geo import area_m2

    size = area_m2(geom)
    if not size:
        raise forms.ValidationError(
            _("Gambar lokasi tidak membentuk bidang. Gambar ulang di peta.")
        )
    if size > MAX_REQUEST_AREA_M2:
        raise forms.ValidationError(_("Luas gambar lokasi maksimal 10.000 ha."))
    return geom


class InvestmentRequestForm(forms.ModelForm):
    requested_area_geojson = forms.CharField(
        label=_("Usulan lokasi di peta"),
        required=False,
        widget=forms.HiddenInput,
    )
    agree = forms.BooleanField(
        label=_(
            "Saya menyatakan data yang diisi benar dan bersedia dihubungi petugas "
            "untuk konsultasi."
        ),
        required=True,
    )

    class Meta:
        model = InvestmentRequest
        fields = (
            "scheme",
            "sector",
            "project_name",
            "activity",
            "plots",
            "zone",
            "requested_area_m2",
            "term_years",
            "investment_value",
            "workforce",
            "capital_origin",
            "origin_country",
            "target_start",
            "power_kva",
            "water_m3_day",
            "attachment",
        )
        widgets = {
            "activity": forms.Textarea(attrs={"rows": 5}),
            "plots": forms.CheckboxSelectMultiple,
            "target_start": DATE_INPUT,
            "scheme": forms.RadioSelect,
        }
        help_texts = {
            "activity": _(
                "Jelaskan jenis usaha, produk/layanan, tahapan pembangunan, dan "
                "manfaatnya bagi daerah."
            ),
            "plots": _("Opsional. Pilih hingga 10 lahan dari peta investasi."),
            "requested_area_m2": _(
                "Isi bila belum memilih lahan, atau bila kebutuhan berbeda dari luas lahan."
            ),
            "investment_value": _("Perkiraan total nilai investasi dalam rupiah."),
            "attachment": _(
                "Opsional. Proposal proyek atau profil perusahaan (PDF, JPG, PNG; maks. 10 MB)."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sector"].queryset = InvestmentSector.objects.filter(is_active=True)
        self.fields["sector"].required = True
        self.fields["sector"].empty_label = _("— pilih sektor usaha —")
        self.fields["zone"].queryset = InvestmentZone.objects.filter(is_published=True)
        self.fields["zone"].empty_label = _("— semua kawasan —")
        self.fields["plots"].queryset = available_plots()
        # Pilihan "belum ditentukan" di akhir, sebagai bawaan.
        self.fields["scheme"].choices = list(enums.InvestmentScheme.choices)
        self.fields["investment_value"].required = True
        self.fields["investment_value"].widget.attrs.update(
            {"inputmode": "numeric", "min": "1", "step": "1"}
        )
        self.fields["requested_area_m2"].widget.attrs.update({"step": "0.01"})

    def clean_plots(self):
        plots = self.cleaned_data.get("plots")
        if plots is not None and len(plots) > MAX_PLOTS_PER_REQUEST:
            raise forms.ValidationError(
                _("Pilih paling banyak %d lahan.") % MAX_PLOTS_PER_REQUEST
            )
        return plots

    def clean_requested_area_geojson(self):
        return parse_area(self.cleaned_data.get("requested_area_geojson"))

    def clean_target_start(self):
        value = self.cleaned_data.get("target_start")
        if value and value < timezone.localdate():
            raise forms.ValidationError(_("Rencana mulai tidak boleh di masa lalu."))
        return value

    def clean(self):
        cleaned = super().clean()
        if not (
            cleaned.get("plots")
            or cleaned.get("requested_area_geojson")
            or cleaned.get("requested_area_m2")
        ) and not self.has_error("requested_area_geojson"):
            self.add_error(
                "requested_area_m2",
                _(
                    "Pilih lahan, gambar usulan lokasi di peta, atau isi kebutuhan luas."
                ),
            )
        if cleaned.get(
            "capital_origin"
        ) == enums.CapitalOrigin.FOREIGN and not cleaned.get("origin_country"):
            self.add_error("origin_country", _("Isi negara asal untuk PMA."))
        return cleaned

    def save(self, commit=True):
        area = self.cleaned_data.get("requested_area_geojson")
        self.instance.requested_area = area
        if area is not None and not self.cleaned_data.get("requested_area_m2"):
            # Luas resmi dihitung server (UTM), sama dengan yang dilihat petugas.
            self.instance.requested_area_m2 = self.instance.requested_area_size_m2
        return super().save(commit=commit)


class InvestmentMessageForm(forms.ModelForm):
    class Meta:
        model = InvestmentMessage
        fields = ("body", "attachment")
        widgets = {
            "body": forms.Textarea(
                attrs={"rows": 3, "maxlength": 5000, "placeholder": _("Tulis pesan…")}
            )
        }
        labels = {"body": _("Pesan")}
        help_texts = {"attachment": _("Opsional. PDF, JPG, atau PNG; maks. 10 MB.")}


class DeclineOfferForm(forms.Form):
    reason = forms.CharField(
        label=_("Alasan / penyesuaian yang diinginkan"),
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class CancelRequestForm(forms.Form):
    note = forms.CharField(
        label=_("Alasan pembatalan"),
        max_length=2000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )


# --------------------------------------------------------------------------
# Panel petugas
# --------------------------------------------------------------------------


class ConsultationForm(forms.Form):
    meeting_at = forms.DateTimeField(
        label=_("Jadwal konsultasi / kunjungan"),
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
        ),
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"],
    )
    place = forms.CharField(
        label=_("Tempat / tautan pertemuan"),
        max_length=255,
        widget=forms.TextInput(attrs={"size": 60}),
    )
    note = forms.CharField(
        label=_("Catatan untuk investor"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "cols": 80}),
    )

    def clean_meeting_at(self):
        value = self.cleaned_data["meeting_at"]
        if value <= timezone.now():
            raise forms.ValidationError(_("Jadwal harus di masa mendatang."))
        return value


class OfferForm(forms.Form):
    scheme = forms.ChoiceField(
        label=_("Skema ditawarkan"),
        choices=[(s.value, s.label) for s in enums.OFFER_SCHEMES],
    )
    plot = forms.ModelChoiceField(
        label=_("Lahan ditawarkan"),
        queryset=LandPlot.objects.none(),
        required=False,
        empty_label=_("— tanpa lahan dari daftar (lokasi usulan) —"),
        help_text=_(
            "Wajib untuk skema alokasi. Luas & tarif diisi dari data lahan bila dikosongkan."
        ),
    )
    area_m2 = forms.DecimalField(
        label=_("Luas ditawarkan (m²)"),
        required=False,
        min_value=1,
        max_value=MAX_REQUEST_AREA_M2,
        max_digits=16,
        decimal_places=2,
    )
    rate_per_m2_year = forms.DecimalField(
        label=_("Tarif per m² per tahun (Rp)"),
        required=False,
        min_value=0,
        max_digits=20,
        decimal_places=2,
    )
    term_years = forms.IntegerField(
        label=_("Jangka waktu (tahun)"),
        required=False,
        min_value=1,
        max_value=99,
        help_text=_(
            "Bila dikosongkan: jangka alokasi lahan, jangka yang diminta investor, "
            "atau masa sewa minimum lahan."
        ),
    )
    valid_until = forms.DateField(label=_("Penawaran berlaku s.d."), widget=DATE_INPUT)
    note = forms.CharField(
        label=_("Ketentuan penawaran"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "cols": 80}),
    )

    def __init__(self, *args, investment=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plot"].queryset = available_plots()
        if investment is not None and not self.is_bound:
            first = investment.plots.filter(
                pk__in=self.fields["plot"].queryset.values("pk")
            ).first()
            scheme = investment.offer_scheme or (
                investment.scheme
                if investment.scheme in enums.OFFER_SCHEMES
                else enums.InvestmentScheme.LEASE
            )
            self.initial.update(
                {
                    "scheme": scheme,
                    "plot": investment.offer_plot or first,
                    "area_m2": investment.offer_area_m2,
                    "rate_per_m2_year": investment.offer_rate_per_m2_year,
                    "term_years": investment.offer_term_years or investment.term_years,
                    "valid_until": investment.offer_valid_until
                    or timezone.localdate() + datetime.timedelta(days=30),
                    "note": investment.offer_note,
                }
            )

    def clean_valid_until(self):
        value = self.cleaned_data["valid_until"]
        if value < timezone.localdate():
            raise forms.ValidationError(_("Tidak boleh di masa lalu."))
        return value


class CompleteForm(forms.Form):
    contract_number = forms.CharField(
        label=_("Nomor kontrak sewa / perjanjian kerja sama"),
        max_length=64,
        required=False,
        help_text=_("Wajib untuk skema sewa dan kerja sama."),
    )
    note = forms.CharField(
        label=_("Catatan untuk investor"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "cols": 80}),
    )


class OfficerMessageForm(forms.ModelForm):
    class Meta:
        model = InvestmentMessage
        fields = ("body", "attachment")
        widgets = {"body": forms.Textarea(attrs={"rows": 4, "cols": 80})}
        labels = {"body": _("Balas investor")}
