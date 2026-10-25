from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import Exists, OuterRef
from django.utils.translation import gettext_lazy as _
from rest_framework.authtoken.models import Token

User = get_user_model()


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        (None, {"fields": ("service_units",)}),
        (None, {"fields": ("department_name",)}),
    )
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "token_exists",
    )

    def get_queryset(self, request):
        # Satu subkueri, bukan satu kueri token per baris daftar.
        return (
            super()
            .get_queryset(request)
            .annotate(_has_token=Exists(Token.objects.filter(user=OuterRef("pk"))))
        )

    @admin.display(boolean=True, description=_("Token exists"))
    def token_exists(self, obj) -> bool:
        if hasattr(obj, "_has_token"):
            return obj._has_token
        return obj.has_token()
