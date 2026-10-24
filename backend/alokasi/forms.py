"""Formulir portal pemohon dan panel petugas."""

from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _

from alokasi import enums
from alokasi.models import (
    Applicant,
    Application,
    ApplicationDocument,
    DevelopmentReport,
    Invoice,
    PermitReport,
    RequirementDocType,
    VerificationCriterion,
)

User = get_user_model()

DATE_INPUT = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


def _normalize_email(value: str) -> str:
    return (value or "").strip().lower()


class ApplicantProfileForm(forms.ModelForm):
    class Meta:
        model = Applicant
        fields = (
            "applicant_type",
            "name",
            "nib",
            "npwp",
            "nik",
            "pic_name",
            "pic_position",
            "phone",
            "address",
            "city",
        )
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "nik": forms.TextInput(attrs={"maxlength": 16, "inputmode": "numeric"}),
        }
        help_texts = {
            "nib": _("Wajib untuk badan usaha (Nomor Induk Berusaha dari OSS)."),
            "nik": _("Disimpan terenkripsi."),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get(
            "applicant_type"
        ) == enums.ApplicantType.COMPANY and not cleaned.get("nib"):
            self.add_error("nib", _("NIB wajib diisi untuk badan usaha."))
        nik = cleaned.get("nik") or ""
        if nik and (not nik.isdigit() or len(nik) != 16):
            self.add_error("nik", _("NIK harus 16 digit angka."))
        return cleaned


class RegistrationForm(ApplicantProfileForm):
    email = forms.EmailField(
        label=_("Surel"), help_text=_("Dipakai untuk masuk dan menerima notifikasi.")
    )
    password1 = forms.CharField(
        label=_("Kata sandi"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=_("Minimal 10 karakter, tidak boleh hanya angka atau terlalu umum."),
    )
    password2 = forms.CharField(
        label=_("Ulangi kata sandi"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    agree = forms.BooleanField(
        label=_(
            "Saya menyatakan data yang saya isi benar dan menyetujui ketentuan layanan."
        ),
    )

    field_order = ["email", "password1", "password2"]

    def clean_email(self):
        email = _normalize_email(self.cleaned_data["email"])
        if (
            User.objects.filter(email__iexact=email).exists()
            or User.objects.filter(username__iexact=email).exists()
        ):
            raise forms.ValidationError(
                _(
                    "Surel ini sudah terdaftar. Silakan masuk atau atur ulang kata sandi."
                )
            )
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", _("Kata sandi tidak sama."))
        if p1 and cleaned.get("email"):
            candidate = User(
                username=cleaned["email"],
                email=cleaned["email"],
                first_name=cleaned.get("pic_name", ""),
            )
            try:
                password_validation.validate_password(p1, candidate)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return cleaned


class PortalLoginForm(AuthenticationForm):
    username = forms.EmailField(
        label=_("Surel"), widget=forms.EmailInput(attrs={"autofocus": True})
    )

    error_messages = {
        "invalid_login": _("Surel atau kata sandi salah."),
        "inactive": _("Akun belum diaktifkan. Periksa surel aktivasi Anda."),
        "not_applicant": _(
            "Akun ini bukan akun pemohon. Petugas masuk melalui aplikasi petugas."
        ),
    }

    def clean_username(self):
        return _normalize_email(self.cleaned_data["username"])

    def clean(self):
        try:
            return super().clean()
        except forms.ValidationError as error:
            # ModelBackend menolak akun nonaktif seperti sandi salah. Bila sandinya
            # benar, beri tahu bahwa akun belum diaktifkan (bukan "sandi salah").
            if error.code == "invalid_login":
                user = User.objects.filter(
                    username__iexact=self.cleaned_data.get("username") or "",
                    is_active=False,
                    pemohon__isnull=False,
                ).first()
                if user and user.check_password(self.cleaned_data.get("password")):
                    raise forms.ValidationError(
                        self.error_messages["inactive"], code="inactive"
                    )
            raise

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not hasattr(user, "pemohon"):
            raise forms.ValidationError(
                self.error_messages["not_applicant"], code="not_applicant"
            )


class ResendActivationForm(forms.Form):
    email = forms.EmailField(label=_("Surel"))

    def clean_email(self):
        return _normalize_email(self.cleaned_data["email"])


class AllocationApplicationForm(forms.ModelForm):
    """Data rencana usaha. Kelengkapan diperiksa saat diajukan, jadi draf boleh sebagian."""

    class Meta:
        model = Application
        fields = (
            "activity",
            "investment_value",
            "workforce",
            "development_months",
            "description",
        )
        widgets = {"description": forms.Textarea(attrs={"rows": 6})}
        help_texts = {
            "investment_value": _("Perkiraan total nilai investasi dalam rupiah."),
            "description": _(
                "Jelaskan rencana usaha, tahapan pembangunan, dan manfaatnya."
            ),
        }

    def clean_investment_value(self):
        value = self.cleaned_data.get("investment_value")
        if value is not None and value <= 0:
            raise forms.ValidationError(_("Nilai investasi harus lebih dari nol."))
        return value


class RecipientEmailMixin:
    def clean_recipient_email(self):
        email = _normalize_email(self.cleaned_data["recipient_email"])
        recipient = (
            Applicant.objects.select_related("user")
            .filter(user__email__iexact=email, user__is_active=True)
            .first()
        )
        if recipient is None:
            raise forms.ValidationError(
                _(
                    "Penerima hak harus sudah memiliki akun pemohon aktif dengan surel ini."
                )
            )
        self.recipient = recipient
        return email


class TransferApplicationForm(RecipientEmailMixin, forms.Form):
    recipient_email = forms.EmailField(
        label=_("Surel akun penerima hak"),
        help_text=_("Penerima hak harus mendaftar di portal terlebih dahulu."),
    )
    transfer_reason = forms.CharField(
        label=_("Alasan / dasar peralihan"), widget=forms.Textarea(attrs={"rows": 4})
    )


# Layanan atas alokasi sendiri: perpanjangan, pembaruan, pecah PL, pengukuran ulang.
SERVICE_APPLICATION_TYPES = tuple(
    (value, label)
    for value, label in enums.ServiceType.choices
    if value in enums.OWN_ALLOCATION_SERVICES and value != enums.ServiceType.TRANSFER
)


class ServiceApplicationForm(forms.Form):
    service_type = forms.ChoiceField(
        label=_("Jenis layanan"), choices=SERVICE_APPLICATION_TYPES
    )
    reason = forms.CharField(
        label=_("Alasan / uraian permohonan"), widget=forms.Textarea(attrs={"rows": 4})
    )


class ServiceReasonEditForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ("transfer_reason",)
        labels = {"transfer_reason": _("Alasan / uraian permohonan")}
        widgets = {"transfer_reason": forms.Textarea(attrs={"rows": 4})}


class TransferEditForm(RecipientEmailMixin, forms.ModelForm):
    recipient_email = forms.EmailField(label=_("Surel akun penerima hak"))

    class Meta:
        model = Application
        fields = ("transfer_reason",)
        widgets = {"transfer_reason": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.recipient_id:
            self.fields["recipient_email"].initial = self.instance.recipient.email

    def save(self, commit=True):
        self.instance.recipient = self.recipient
        return super().save(commit=commit)


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = ApplicationDocument
        fields = ("doc_type", "file")
        help_texts = {"file": _("PDF, JPG, atau PNG; maksimal 10 MB.")}

    def __init__(self, *args, application, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.application = application
        self.fields["doc_type"].queryset = RequirementDocType.for_application(
            application
        )
        self.fields["doc_type"].empty_label = _("— pilih jenis dokumen —")

    def save(self, commit=True):
        self.instance.original_name = self.cleaned_data["file"].name[:255]
        return super().save(commit=commit)


class PaymentProofForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ("payment_proof",)
        labels = {"payment_proof": _("Bukti pembayaran")}
        help_texts = {"payment_proof": _("PDF, JPG, atau PNG; maksimal 10 MB.")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payment_proof"].required = True


class PermitReportForm(forms.ModelForm):
    class Meta:
        model = PermitReport
        fields = (
            "permit_type",
            "status",
            "permit_number",
            "issued_date",
            "document",
            "note",
        )
        widgets = {"issued_date": DATE_INPUT, "note": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == enums.PermitStatus.ISSUED:
            if not cleaned.get("permit_number"):
                self.add_error(
                    "permit_number", _("Nomor izin wajib diisi bila izin sudah terbit.")
                )
            if not cleaned.get("issued_date"):
                self.add_error(
                    "issued_date",
                    _("Tanggal terbit wajib diisi bila izin sudah terbit."),
                )
        return cleaned


class DevelopmentReportForm(forms.ModelForm):
    class Meta:
        model = DevelopmentReport
        fields = (
            "report_date",
            "stage",
            "progress_percent",
            "realized_investment",
            "workforce",
            "description",
            "photo",
        )
        widgets = {
            "report_date": DATE_INPUT,
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_report_date(self):
        from django.utils import timezone

        value = self.cleaned_data["report_date"]
        if value > timezone.localdate():
            raise forms.ValidationError(_("Tanggal laporan tidak boleh di masa depan."))
        return value


class VerifyCodeForm(forms.Form):
    code = forms.UUIDField(
        label=_("Kode verifikasi"),
        help_text=_("Kode tercetak di bawah kode QR pada dokumen."),
        error_messages={"invalid": _("Format kode tidak valid.")},
    )


class TrackApplicationForm(forms.Form):
    """Lacak permohonan tanpa login: nomor + PIN."""

    number = forms.CharField(label=_("Nomor permohonan"), max_length=32)
    pin = forms.CharField(
        label=_("PIN pelacakan"),
        max_length=12,
        help_text=_("PIN tercantum pada halaman permohonan Anda di portal."),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("autocomplete", "off")


class UwtCalculatorForm(forms.Form):
    """Simulasi biaya UWT; tidak menyimpan data apa pun."""

    plot = forms.ModelChoiceField(
        label=_("Lahan"), queryset=None, empty_label=_("— pilih lahan —")
    )
    area_m2 = forms.DecimalField(
        label=_("Luas (m²)"), min_value=Decimal("0.01"), max_digits=16, decimal_places=2
    )
    years = forms.IntegerField(
        label=_("Jangka waktu (tahun)"), min_value=1, max_value=99
    )

    def __init__(self, *args, **kwargs):
        from alokasi.models import LandPlot

        super().__init__(*args, **kwargs)
        self.fields["plot"].queryset = LandPlot.objects.filter(is_published=True)


# --------------------------------------------------------------------------
# Panel petugas
# --------------------------------------------------------------------------


class OfficerNoteForm(forms.Form):
    note = forms.CharField(
        label=_("Catatan"), widget=forms.Textarea(attrs={"rows": 4, "cols": 80})
    )

    def __init__(self, *args, required=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["note"].required = required


class ScoreForm(forms.Form):
    """Satu baris nilai per kriteria aktif untuk verifikator yang sedang masuk."""

    def __init__(self, *args, application, verifier, **kwargs):
        super().__init__(*args, **kwargs)
        self.criteria = list(VerificationCriterion.objects.filter(is_active=True))
        existing = {
            s.criterion_id: s for s in application.scores.filter(verifier=verifier)
        }
        for criterion in self.criteria:
            current = existing.get(criterion.pk)
            self.fields[f"score_{criterion.pk}"] = forms.DecimalField(
                label=f"{criterion.name} (bobot {criterion.weight}%)",
                help_text=criterion.description,
                min_value=0,
                max_value=100,
                max_digits=5,
                decimal_places=2,
                initial=current.score if current else None,
            )
            self.fields[f"note_{criterion.pk}"] = forms.CharField(
                label=_("Catatan"),
                required=False,
                widget=forms.Textarea(attrs={"rows": 2, "cols": 80}),
                initial=current.note if current else "",
            )

    def rows(self):
        for criterion in self.criteria:
            yield criterion, self[f"score_{criterion.pk}"], self[f"note_{criterion.pk}"]
