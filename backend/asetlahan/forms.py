"""Formulir portal (pengaduan & lelang) modul aset lahan."""

from django import forms
from django.contrib.gis.geos import Point
from django.utils.translation import gettext_lazy as _

from asetlahan import enums
from asetlahan.models import Bid, Grievance, GrievanceCategory


class GrievanceForm(forms.ModelForm):
    latitude = forms.FloatField(
        required=False, min_value=-90, max_value=90, widget=forms.HiddenInput
    )
    longitude = forms.FloatField(
        required=False, min_value=-180, max_value=180, widget=forms.HiddenInput
    )
    # Isian jebakan untuk bot: harus kosong.
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )

    class Meta:
        model = Grievance
        fields = (
            "complainant_name",
            "phone",
            "email",
            "category",
            "subject",
            "description",
            "location_text",
            "attachment",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "attachment": forms.FileInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = GrievanceCategory.objects.filter(
            is_active=True
        )
        self.fields["category"].required = False
        self.fields["website"].label = _("Situs web (biarkan kosong)")
        self.fields["attachment"].help_text = _(
            "Opsional. PDF, JPG, atau PNG; maksimal 25 MB."
        )
        self.fields["phone"].help_text = _("Untuk kabar tindak lanjut lewat WhatsApp.")

    def clean(self):
        data = super().clean()
        if data.get("website"):
            raise forms.ValidationError(_("Pengaduan tidak dapat diproses."))
        if not data.get("phone") and not data.get("email"):
            raise forms.ValidationError(
                _("Isi nomor telepon atau surel agar kami dapat mengabari Anda.")
            )
        lat, lng = data.get("latitude"), data.get("longitude")
        if (lat is None) != (lng is None):
            raise forms.ValidationError(_("Titik lokasi tidak lengkap."))
        return data

    def save(self, commit=True):
        grievance = super().save(commit=False)
        lat, lng = self.cleaned_data.get("latitude"), self.cleaned_data.get("longitude")
        if lat is not None and lng is not None:
            grievance.location = Point(lng, lat, srid=4326)
        if commit:
            grievance.save()
        return grievance


class GrievanceCheckForm(forms.Form):
    number = forms.CharField(label=_("Nomor pengaduan"), max_length=32)
    access_code = forms.CharField(label=_("Kode akses"), max_length=12)

    def clean_number(self):
        return self.cleaned_data["number"].strip().upper()

    def clean_access_code(self):
        return self.cleaned_data["access_code"].strip().upper()


class BidForm(forms.ModelForm):
    class Meta:
        model = Bid
        fields = ("bidder_name", "email", "phone", "amount", "proposal")
        widgets = {"proposal": forms.FileInput}

    def __init__(self, *args, tender=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tender = tender
        self.fields["proposal"].help_text = _(
            "PDF atau ZIP berisi proposal & dokumen persyaratan; maksimal 25 MB."
        )
        if tender is not None and tender.reserve_price:
            self.fields["amount"].help_text = _("Tidak boleh kurang dari nilai limit.")
        if (
            tender is not None
            and tender.method == enums.TenderMethod.BEAUTY_CONTEST
            and not self.instance.proposal
        ):
            self.fields["proposal"].required = True

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if (
            self.tender is not None
            and self.tender.reserve_price
            and amount < self.tender.reserve_price
        ):
            raise forms.ValidationError(_("Nilai penawaran di bawah nilai limit."))
        return amount
