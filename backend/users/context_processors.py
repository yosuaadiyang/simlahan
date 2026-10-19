from django.conf import settings


def branding(request):
    """Nama aplikasi untuk templat (judul API, Swagger, halaman login)."""
    return {"app_name": settings.APP_NAME}
