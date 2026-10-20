from django.db import models
from django.db.models.fields.json import JSONField
from django.utils.translation import gettext_lazy as _
from enumfields import EnumField

from file_operations.private_files import PrivateFileField
from file_operations.viewsets.mixins import FileScanMixin
from users.models import User

from ..enums import ApplicantType, FormState, SectionType
from ..utils import clone_object, generate_unique_identifier


class Form(models.Model):
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    is_template = models.BooleanField(default=False, verbose_name=_("Is template"))
    is_area_form = models.BooleanField(default=False, verbose_name=_("Is area form"))
    state = EnumField(
        FormState,
        max_length=30,
        default=FormState.WORK_IN_PROGRESS,
        verbose_name=_("State"),
    )

    title = models.CharField(max_length=255, blank=True, verbose_name=_("Title"))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Time created"))
    modified_at = models.DateTimeField(auto_now=True, verbose_name=_("Time modified"))

    class Meta:
        verbose_name = _("form")
        verbose_name_plural = _("forms")

    def clone(self):
        assert self.is_template  # Only templates can be clone
        return clone_object(self)

    def __str__(self):
        return self.name

    recursive_get_related_skip_relations = [
        "section",
        "answer",
        "areasearch",
        "plotsearch",
    ]


class Section(models.Model):
    title = models.CharField(max_length=255, verbose_name=_("Title"))
    identifier = models.SlugField(verbose_name=_("Identifier"))
    visible = models.BooleanField(default=True, verbose_name=_("Visible"))
    sort_order = models.PositiveIntegerField(default=0, verbose_name=_("Sort order"))

    add_new_allowed = models.BooleanField(
        default=False, verbose_name=_("Add new allowed")
    )
    add_new_text = models.CharField(
        max_length=255, null=True, blank=True, verbose_name=_("Add new text")
    )
    show_duplication_check = models.BooleanField(
        default=True, verbose_name=_("Show duplication check")
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="subsections",
        verbose_name=_("Parent section"),
    )
    form = models.ForeignKey(
        Form, on_delete=models.CASCADE, related_name="sections", verbose_name=_("Form")
    )
    type = EnumField(
        SectionType,
        max_length=30,
        default=SectionType.SHOW_ALWAYS,
        verbose_name=_("Type"),
    )
    applicant_type = EnumField(
        ApplicantType,
        max_length=30,
        default=ApplicantType.BOTH,
        verbose_name=_("Applicant type"),
    )

    class Meta:
        verbose_name = _("form section")
        verbose_name_plural = _("form sections")
        ordering = ["sort_order"]
        unique_together = (
            "form",
            "identifier",
        )

    def save(self, *args, **kwargs):
        if not self.id or not self.identifier:
            max_length = self._meta.get_field("identifier").max_length
            self.identifier = generate_unique_identifier(
                Section,
                "identifier",
                self.title,
                max_length,
                filter={"form_id": self.form.id},
            )
        super(Section, self).save(*args, **kwargs)

    @staticmethod
    def get_root(section):
        if section.parent is not None:
            return Section.get_root(section.parent)
        return section

    def __str__(self):
        return self.title

    recursive_get_related_skip_relations = [
        "field",
    ]


class Field(models.Model):
    FIELD_TYPES = (
        ("textbox", _("Text field")),
        ("textarea", _("Text area")),
        ("dropdown", _("Dropdown")),
        ("checkbox", _("Checkbox")),
        ("radiobutton", _("Radio button")),
        ("radiobuttoninline", _("Radio button inline")),
        ("uploadfiles", _("Upload file")),
        ("fractional", _("Fraction")),
        ("hidden", _("Hidden")),
    )
    label = models.CharField(max_length=255, verbose_name=_("Label"))
    hint_text = models.CharField(
        max_length=1024, null=True, blank=True, verbose_name=_("Hint text")
    )
    identifier = models.SlugField(verbose_name=_("Identifier"))
    enabled = models.BooleanField(default=True, verbose_name=_("Enabled"))
    required = models.BooleanField(default=False, verbose_name=_("Required"))
    validation = models.CharField(
        max_length=255, null=True, blank=True, verbose_name=_("Validation")
    )
    action = models.CharField(
        max_length=255, null=True, blank=True, verbose_name=_("Action")
    )
    sort_order = models.PositiveIntegerField(default=0, verbose_name=_("Sort order"))
    default_value = models.CharField(
        max_length=512, null=True, blank=True, verbose_name=_("Default value")
    )
    type = models.CharField(max_length=255, choices=FIELD_TYPES, verbose_name=_("Type"))
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name="fields",
        verbose_name=_("Form section"),
    )

    class Meta:
        verbose_name = _("form field")
        verbose_name_plural = _("form fields")
        ordering = ["sort_order"]
        unique_together = (
            "section",
            "identifier",
        )

    def save(self, *args, **kwargs):
        if not self.identifier:
            max_length = self._meta.get_field("identifier").max_length
            self.identifier = generate_unique_identifier(
                Field,
                "identifier",
                self.label,
                max_length,
                filter={"section_id": self.section.id},
            )
        super(Field, self).save(*args, **kwargs)

    def __str__(self):
        return self.label

    recursive_get_related_skip_relations = [
        "choice",
        "attachment",
        "entry",
    ]


class Choice(models.Model):
    text = models.CharField(max_length=255, verbose_name=_("Text"))
    value = models.CharField(max_length=50, verbose_name=_("Value"))
    action = models.CharField(
        max_length=255, null=True, blank=True, verbose_name=_("Action")
    )
    has_text_input = models.BooleanField(
        default=False, verbose_name=_("Has text input")
    )

    field = models.ForeignKey(
        Field,
        on_delete=models.CASCADE,
        related_name="choices",
        verbose_name=_("Form field"),
    )

    recursive_get_related_skip_relations = []

    class Meta:
        verbose_name = _("field choice")
        verbose_name_plural = _("field choices")


class Answer(models.Model):
    """
    Model for saving form inputs
    """

    form = models.ForeignKey(Form, on_delete=models.PROTECT)
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)

    created_at = models.DateTimeField(auto_now=True)
    ready = models.BooleanField(default=False)

    recursive_get_related_skip_relations = [
        "form",
        "user",
        "attachment",
        "areasearch",
        "targetstatus",
        "entrysection",
        "answeropeningrecord",
    ]


class AnswerOpeningRecord(models.Model):
    """
    In Finnish: Avauspöytäkirja
    """

    time_stamp = models.DateTimeField(auto_now=True)
    openers = models.ManyToManyField(User, related_name="+")
    note = models.TextField(blank=True, null=True)

    answer = models.OneToOneField(
        Answer, on_delete=models.CASCADE, related_name="opening_record"
    )

    recursive_get_related_skip_relations = [
        "answeropeningrecord_openers",
    ]


def get_attachment_file_upload_to(instance, filename):
    return "/".join(
        [
            "plot_search_attachments",
            str(instance.field.id),
            str(instance.user.username),
            filename,
        ]
    )


class Attachment(FileScanMixin, models.Model):
    name = models.CharField(max_length=255)
    attachment = PrivateFileField(upload_to=get_attachment_file_upload_to)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Time created"))
    path = models.TextField(null=True, blank=True)

    answer = models.ForeignKey(Answer, on_delete=models.CASCADE, null=True, blank=True)
    field = models.ForeignKey(Field, on_delete=models.CASCADE)
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)

    recursive_get_related_skip_relations = [
        "user",
    ]


class EntrySection(models.Model):
    metadata = JSONField(null=True)
    identifier = models.SlugField()

    answer = models.ForeignKey(
        Answer, on_delete=models.CASCADE, related_name="entry_sections", null=True
    )

    recursive_get_related_skip_relations = [
        "entry",
    ]


class Entry(models.Model):
    """
    Model for saving Answer entries
    """

    entry_section = models.ForeignKey(
        EntrySection, on_delete=models.CASCADE, related_name="entries", null=True
    )
    field = models.ForeignKey(Field, on_delete=models.PROTECT)
    value = models.TextField()
    extra_value = models.TextField(blank=True, null=True)
    path = models.TextField()

    recursive_get_related_skip_relations = [
        "field",
    ]


from forms.signals import *  # noqa: E402 F403 F401
