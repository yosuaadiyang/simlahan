import base64
import uuid

import django.contrib.auth.models
from django.contrib import admin
from django.contrib.auth.models import AbstractUser as DjangoAbstractUser
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from rest_framework.authtoken.models import Token


class OfficerUserManager(models.Manager):
    def get_queryset(self):
        """
        Returns users that are officers (internal staff) of the organisation.

        An officer is an active user who belongs to at least one permission group
        (e.g. "Penelusur", "Penyusun", "Admin"). Groups are assigned directly by an
        administrator; there is no external identity provider dependency.
        """
        return (
            super()
            .get_queryset()
            .filter(is_active=True, groups__isnull=False)
            .distinct()
        )


class AbstractUser(DjangoAbstractUser):
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    department_name = models.CharField(
        verbose_name=_("Department"), max_length=100, null=True, blank=True
    )
    last_api_use = models.DateField(
        null=True, blank=True, verbose_name=_("Latest API token usage date")
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.uuid is None:
            self.uuid = uuid.uuid4()
        if not self.username:
            # Nama pengguna otomatis bila dibuat tanpa username (mis. via API/impor).
            encoded = base64.b32encode(self.uuid.bytes).decode().rstrip("=").lower()
            self.username = f"u-{encoded}"
        return super().save(*args, **kwargs)

    def get_display_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.email or self.username


class User(AbstractUser):
    # Default manager needs to be set due to having custom manager.
    objects = django.contrib.auth.models.UserManager()

    # Manager for users that are officers (internal staff)
    officers = OfficerUserManager()

    service_units = models.ManyToManyField("leasing.ServiceUnit", related_name="users")

    recursive_get_related_skip_relations = [
        "auth_token",
        "logentry",
        "emaillog",
        "emaillogs",
        "Emaillog_recipients+",
        "groups",
        "user_permissions",
        "outstandingtoken",
        "favourite",
        "answer",
        "plotsearch",
        "areasearch",
        "areasearchstatusnote",
        "targetstatus",
        "informationcheck",
        "service_units",
        "credit_decisions",
    ]

    @admin.display(boolean=True, description=_("Token exists"))
    def has_token(self) -> bool:
        return Token.objects.filter(user=self).exists()

    @transaction.atomic
    def update_service_units(self):
        """Updates users Service Units according to Service Unit Group Mappings"""
        from leasing.models.service_unit import ServiceUnitGroupMapping

        group_mappings = {
            mapping.group: mapping.service_unit
            for mapping in ServiceUnitGroupMapping.objects.all()
        }
        managed_service_units = set(group_mappings.values())
        old_service_units = set(
            self.service_units.filter(id__in=[s.id for s in managed_service_units])
        )
        new_service_units = set(
            [group_mappings[x] for x in self.groups.all() if x in group_mappings]
        )

        service_units_to_delete = old_service_units.difference(new_service_units)
        if service_units_to_delete:
            self.service_units.remove(*service_units_to_delete)

        service_units_to_add = new_service_units.difference(old_service_units)
        if service_units_to_add:
            self.service_units.add(*service_units_to_add)
