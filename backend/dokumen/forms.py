import json

from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import AutocompleteSelect
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from dokumen import enums, merge
from dokumen.models import (
    DOCUMENT_EXTENSIONS,
    ContentBlock,
    DocumentRecipient,
    DocumentTemplate,
    LandUse,
    PermitRecord,
    SigningDocument,
)
from dokumen.permissions import DOKUMEN_GROUP_MODEL_PERMISSIONS

DATE_INPUT = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
ACCEPT_DOCUMENT = ",".join(f".{e}" for e in DOCUMENT_EXTENSIONS)


class RichTextarea(forms.Textarea):
    """Textarea yang diubah editor.js menjadi editor dokumen (dengan menu isian)."""

    def __init__(self, attrs=None):
        base = {"class": "dk-editor-source", "rows": 24}
        base.update(attrs or {})
        super().__init__(base)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        groups = [
            {
                "label": str(label),
                "fields": [
                    {"key": f"{group}.{field}", "label": text} for field, text in fields
                ],
            }
            for group, label, fields in merge.FIELD_GROUPS
        ]
        blocks = list(
            ContentBlock.objects.filter(is_active=True).values("code", "name")
        )
        if blocks:
            groups.append(
                {
                    "label": str(_("Pustaka konten")),
                    "fields": [
                        {"key": f"blok.{b['code']}", "label": b["name"]} for b in blocks
                    ],
                }
            )
        context["widget"]["attrs"]["data-fields"] = json.dumps(groups)
        return context

    class Media:
        css = {"all": ("dokumen/editor.css",)}
        js = ("dokumen/editor.js",)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            return [single(item, initial) for item in data]
        return [single(data, initial)]


# --------------------------------------------------------------------------
# Portal pemegang hak
# --------------------------------------------------------------------------


class HolderRecordForm(forms.Form):
    status = forms.ChoiceField(
        label=_("Status pengurusan"),
        choices=[("", _("— tidak diubah —"))]
        + [
            (v, label)
            for v, label in enums.RecordStatus.choices
            if v in enums.HOLDER_RECORD_STATUSES
        ],
        required=False,
    )
    file = forms.FileField(
        label=_("Unggah dokumen"),
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": ACCEPT_DOCUMENT}),
        help_text=_(
            "PDF, JPG, PNG, DOCX, atau XLSX; maksimal 20 MB. Mengunggah berarti mengajukan verifikasi."
        ),
    )
    number = forms.CharField(
        label=_("Nomor dokumen / izin"), max_length=128, required=False
    )
    issued_date = forms.DateField(
        label=_("Tanggal terbit"), required=False, widget=DATE_INPUT
    )
    expiry_date = forms.DateField(
        label=_("Berlaku sampai"),
        required=False,
        widget=DATE_INPUT,
        help_text=_("Kosongkan bila tidak ada masa berlaku."),
    )
    note = forms.CharField(
        label=_("Catatan untuk petugas"),
        required=False,
        max_length=5000,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("file") and not cleaned.get("status"):
            raise forms.ValidationError(
                _("Unggah dokumen atau pilih status pengurusan.")
            )
        issued, expiry = cleaned.get("issued_date"), cleaned.get("expiry_date")
        if issued and expiry and expiry < issued:
            self.add_error(
                "expiry_date", _("Masa berlaku berakhir sebelum tanggal terbit.")
            )
        return cleaned


class DownloadRequestForm(forms.Form):
    purpose = forms.ChoiceField(
        label=_("Keperluan"), choices=enums.DownloadPurpose.choices
    )
    reason = forms.CharField(
        label=_("Alasan"),
        min_length=5,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text=_("Permintaan diperiksa pejabat berwenang dan dicatat."),
    )


class SignForm(forms.Form):
    name = forms.CharField(label=_("Nama lengkap"), max_length=255, min_length=3)
    signature = forms.CharField(
        widget=forms.HiddenInput, required=False, max_length=600_000
    )
    agree = forms.BooleanField(
        label=_(
            "Saya telah membaca dokumen ini dan setuju menandatanganinya secara elektronik."
        ),
        required=True,
    )


class DeclineForm(forms.Form):
    reason = forms.CharField(
        label=_("Alasan menolak"),
        max_length=5000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class OtpForm(forms.Form):
    code = forms.CharField(
        label=_("Kode verifikasi"),
        min_length=6,
        max_length=6,
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "pattern": "[0-9]{6}",
            }
        ),
    )


class CommentForm(forms.Form):
    body = forms.CharField(
        label=_("Komentar"), max_length=5000, widget=forms.Textarea(attrs={"rows": 3})
    )


class HashCheckForm(forms.Form):
    file = forms.FileField(
        label=_("Berkas PDF yang ingin diperiksa"),
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf"}),
    )

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if upload.size > 20 * 1024 * 1024:
            raise forms.ValidationError(_("Ukuran berkas maksimal 20 MB."))
        return upload


# --------------------------------------------------------------------------
# Panel petugas
# --------------------------------------------------------------------------


class OfficerVerifyForm(forms.Form):
    number = forms.CharField(
        label=_("Nomor dokumen / izin"), max_length=128, required=False
    )
    issued_date = forms.DateField(
        label=_("Tanggal terbit"), required=False, widget=DATE_INPUT
    )
    expiry_date = forms.DateField(
        label=_("Berlaku sampai"),
        required=False,
        widget=DATE_INPUT,
        help_text=_(
            "Kosong = dihitung dari masa berlaku bawaan jenis dokumen (bila ada)."
        ),
    )
    note = forms.CharField(
        label=_("Catatan verifikasi"),
        required=False,
        max_length=5000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class OfficerNoteForm(forms.Form):
    note = forms.CharField(
        label=_("Catatan"), max_length=5000, widget=forms.Textarea(attrs={"rows": 4})
    )


class OfficerUploadForm(OfficerVerifyForm):
    file = forms.FileField(
        label=_("Berkas"),
        widget=forms.ClearableFileInput(attrs={"accept": ACCEPT_DOCUMENT}),
        help_text=_("PDF, JPG, PNG, DOCX, atau XLSX; maksimal 20 MB."),
    )
    verify_now = forms.BooleanField(
        label=_("Langsung nyatakan terverifikasi"), required=False
    )
    field_order = ["file", "number", "issued_date", "expiry_date", "note", "verify_now"]


def custom_value_fields(keys):
    return {
        f"isian_{key}": forms.CharField(
            label=key.replace("_", " ").capitalize(),
            max_length=1000,
            required=True,
            help_text=f"{{{{ isian.{key} }}}}",
        )
        for key in keys
    }


class GenerateForm(forms.Form):
    template = forms.ModelChoiceField(
        label=_("Templat"),
        queryset=DocumentTemplate.objects.filter(is_active=True),
    )
    note = forms.CharField(label=_("Keterangan versi"), max_length=2000, required=False)

    def __init__(self, *args, custom_keys=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.update(custom_value_fields(custom_keys))

    def custom_values(self) -> dict:
        return {
            name[len("isian_") :]: value
            for name, value in self.cleaned_data.items()
            if name.startswith("isian_")
        }


class FillFieldsForm(forms.Form):
    def __init__(self, *args, keys=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.update(custom_value_fields(keys))

    def values(self) -> dict:
        return {
            name[len("isian_") :]: value for name, value in self.cleaned_data.items()
        }


class DownloadDecisionForm(forms.Form):
    note = forms.CharField(
        label=_("Catatan keputusan"),
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text=_("Wajib diisi bila menolak."),
    )
    hours = forms.IntegerField(
        label=_("Berlaku (jam)"),
        min_value=1,
        max_value=720,
        required=False,
        help_text=_("Kosong = sesuai pengaturan."),
    )
    max_count = forms.IntegerField(
        label=_("Batas unduh"),
        min_value=1,
        max_value=20,
        required=False,
        help_text=_("Kosong = sesuai pengaturan."),
    )

    def __init__(self, *args, form_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        if form_id:
            # Kolom tampil di dalam formulir halaman admin, tetapi dikirim lewat formulir keputusan terpisah.
            for field in self.fields.values():
                field.widget.attrs["form"] = form_id


class TemplateImportForm(forms.Form):
    files = MultipleFileField(
        label=_("Berkas templat"),
        help_text=_(
            "Boleh beberapa berkas sekaligus atau satu ZIP: DOCX, HTML, TXT, PDF, XLSX, "
            "JPG, PNG (maks. 20 MB per berkas, 50 berkas per ZIP)."
        ),
    )
    category = forms.ChoiceField(label=_("Kategori"), choices=enums.Category.choices)
    docx_mode = forms.ChoiceField(
        label=_("Berkas Word dijadikan"),
        choices=(
            ("docx", _("Templat Word dengan isian otomatis (hasil berupa .docx)")),
            ("html", _("Dokumen isian yang dapat diedit & ditandatangani elektronik")),
        ),
        initial="docx",
        widget=forms.RadioSelect,
    )


class TemplatePreviewForm(forms.Form):
    land_use = forms.ModelChoiceField(
        label=_("Contoh data dari pemanfaatan lahan"),
        queryset=LandUse.objects.all(),
        required=False,
        widget=AutocompleteSelect(
            SigningDocument._meta.get_field("land_use"), admin.site
        ),
        help_text=_("Kosongkan untuk memakai data contoh."),
    )


class SigningCreateForm(forms.Form):
    title = forms.CharField(label=_("Judul dokumen"), max_length=255)
    template = forms.ModelChoiceField(
        label=_("Templat isian"),
        queryset=DocumentTemplate.objects.filter(
            is_active=True, kind=enums.TemplateKind.HTML
        ),
        required=False,
    )
    source_file = forms.FileField(
        label=_("Atau unggah PDF"),
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf"}),
        help_text=_(
            "PDF siap tanda tangan (maks. 20 MB). Lembar pengesahan & sertifikat ditambahkan otomatis."
        ),
    )
    land_use = forms.ModelChoiceField(
        label=_("Pemanfaatan lahan"),
        queryset=LandUse.objects.all(),
        required=False,
        widget=AutocompleteSelect(
            SigningDocument._meta.get_field("land_use"), admin.site
        ),
        help_text=_(
            "Data pemegang hak & lahan dipakai untuk isian otomatis; pemegang hak ditambahkan sebagai penanda tangan."
        ),
    )
    record = forms.ModelChoiceField(
        label=_("Untuk dokumen perizinan"),
        queryset=PermitRecord.objects.select_related("land_use", "permit_type"),
        required=False,
        widget=forms.HiddenInput,
    )

    def clean_source_file(self):
        upload = self.cleaned_data.get("source_file")
        if upload is None:
            return upload
        if not (upload.name or "").lower().endswith(".pdf"):
            raise forms.ValidationError(_("Unggah berkas berformat PDF."))
        if upload.size > 20 * 1024 * 1024:
            raise forms.ValidationError(_("Ukuran berkas maksimal 20 MB."))
        from file_operations.validators import validate_file_signature

        validate_file_signature(upload)
        return upload

    def clean(self):
        cleaned = super().clean()
        template, upload = cleaned.get("template"), cleaned.get("source_file")
        if bool(template) == bool(upload):
            raise forms.ValidationError(
                _("Pilih salah satu: templat isian atau unggah PDF.")
            )
        record = cleaned.get("record")
        if record is not None:
            if cleaned.get("land_use") is None:
                cleaned["land_use"] = record.land_use
            elif cleaned["land_use"].pk != record.land_use_id:
                raise forms.ValidationError(
                    _("Dokumen perizinan bukan milik pemanfaatan lahan ini.")
                )
        return cleaned


def recipient_user_queryset(document=None):
    """Akun yang boleh dipilih sebagai penerima: petugas modul dokumen dan
    pemegang hak dari pemanfaatan lahan dokumen ini."""
    User = get_user_model()
    group_ids = {
        int(group)
        for config in DOKUMEN_GROUP_MODEL_PERMISSIONS.values()
        for group, perms in config["model"].items()
        if perms
    }
    query = Q(is_staff=True, groups__in=group_ids) | Q(is_superuser=True)
    if document is not None and document.land_use_id and document.land_use.holder_id:
        query |= Q(pk=document.land_use.holder.user_id)
    return (
        User.objects.filter(query, is_active=True)
        .exclude(email="")
        .distinct()
        .order_by("first_name", "last_name", "email")
    )


class RecipientForm(forms.ModelForm):
    class Meta:
        model = DocumentRecipient
        fields = ("order", "role", "action", "user", "name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required = False
        self.fields["email"].required = False
        if "user" in self.fields:
            self.fields["user"].label_from_instance = (
                lambda u: f"{u.get_full_name() or u.username} <{u.email}>"
            )

    def clean(self):
        cleaned = super().clean()
        user = cleaned.get("user")
        if user is not None:
            from dokumen.access import display_name

            if not cleaned.get("name"):
                cleaned["name"] = display_name(user)[:255]
            if not cleaned.get("email"):
                cleaned["email"] = user.email
            elif cleaned["email"].lower() != (user.email or "").lower():
                self.add_error(
                    "email", _("Surel harus sama dengan surel akun yang dipilih.")
                )
        else:
            if not cleaned.get("name"):
                self.add_error("name", _("Isi nama atau pilih akun."))
            if not cleaned.get("email"):
                self.add_error("email", _("Isi surel atau pilih akun."))
        return cleaned


class SigningDocumentForm(forms.ModelForm):
    class Meta:
        model = SigningDocument
        fields = (
            "title",
            "land_use",
            "record",
            "body",
            "message",
            "expires_on",
            "reminder_every_days",
            "needs_approval",
            "confidentiality",
        )
        widgets = {
            "body": RichTextarea(),
            "expires_on": DATE_INPUT,
            "message": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_body(self):
        from dokumen.sanitizer import sanitize_html

        return sanitize_html(self.cleaned_data.get("body") or "")

    def clean(self):
        cleaned = super().clean()
        land_use, record = cleaned.get("land_use"), cleaned.get("record")
        if record is not None and (
            land_use is None or record.land_use_id != land_use.pk
        ):
            self.add_error(
                "record",
                _("Dokumen perizinan harus milik pemanfaatan lahan yang dipilih."),
            )
        if (
            self.instance.source == enums.SigningSource.HTML
            and "body" in self.fields
            and not cleaned.get("body")
        ):
            self.add_error("body", _("Isi dokumen tidak boleh kosong."))
        return cleaned


class DocumentTemplateForm(forms.ModelForm):
    class Meta:
        model = DocumentTemplate
        fields = "__all__"
        widgets = {
            "body": RichTextarea(),
            "signer_roles": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_body(self):
        from dokumen.sanitizer import sanitize_html

        return sanitize_html(self.cleaned_data.get("body") or "")


class ContentBlockForm(forms.ModelForm):
    class Meta:
        model = ContentBlock
        fields = "__all__"
        widgets = {"body": RichTextarea(attrs={"rows": 10})}

    def clean_body(self):
        from dokumen.sanitizer import sanitize_html

        body = sanitize_html(self.cleaned_data.get("body") or "")
        if not body:
            raise forms.ValidationError(_("Isi tidak boleh kosong."))
        return body
