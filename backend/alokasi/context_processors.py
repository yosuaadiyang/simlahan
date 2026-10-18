from django.utils.functional import SimpleLazyObject


def portal(request):
    """Pengaturan layanan untuk templat portal (dimuat hanya bila dipakai)."""

    def load():
        from alokasi.models import AllocationSettings

        return AllocationSettings.load()

    def applicant():
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return None
        return getattr(user, "pemohon", None)

    return {
        "portal_config": SimpleLazyObject(load),
        "portal_applicant": SimpleLazyObject(applicant),
    }
