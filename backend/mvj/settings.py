import os
import subprocess
from datetime import timedelta

import django_stubs_ext
import environ
import sentry_sdk
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
from sentry_sdk.integrations.django import DjangoIntegration

django_stubs_ext.monkeypatch()
project_root = environ.Path(__file__) - 2
BASE_DIR = project_root

# Location of the fallback version file, used when no repository is available.
# This is hardcoded as reading it from configuration does not really make
# sense. It is supposed to be a fallback after all.
VERSION_FILE = project_root("../service_state/deployed_version")


def get_git_revision_hash():
    """
    We need a way to retrieve git revision hash for sentry reports
    """
    try:
        # We are not interested in gits complaints, stderr -> null
        git_hash = subprocess.check_output(
            ["git", "describe", "--tags", "--long", "--always"],
            stderr=subprocess.DEVNULL,
            encoding="utf8",
        )
    # First is "git not found", second is most likely "no repository"
    except (FileNotFoundError, subprocess.CalledProcessError):
        try:
            # fall back to hardcoded file location
            with open(VERSION_FILE) as f:
                git_hash = f.readline()
        except FileNotFoundError:
            git_hash = "revision_not_available"

    return git_hash.rstrip()


env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, ""),
    FIELD_ENCRYPTION_KEY=(str, ""),
    ALLOWED_HOSTS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
    TRUST_PROXY_HEADERS=(bool, False),
    CORS_ALLOWED_ORIGINS=(list, []),
    OFFICER_UI_URL=(str, ""),
    PUBLIC_UI_URL=(str, ""),
    ADMINS=(list, []),
    DATABASE_URL=(str, "postgis:///simlahan"),
    DATABASE_PASSWORD=(str, ""),
    CACHE_URL=(str, "locmemcache://"),
    SENTRY_DSN=(str, ""),
    SENTRY_ENVIRONMENT=(str, ""),
    EMAIL_URL=(str, "consolemail://"),
    DEFAULT_FROM_EMAIL=(str, "noreply@simlahan.local"),
    ORGANIZATION_NAME=(str, "Instansi Pengelola Lahan"),
    FROM_EMAIL_PLOT_SEARCH=(str, ""),
    FROM_EMAIL_AREA_SEARCH=(str, ""),
    JWT_ACCESS_TOKEN_MINUTES=(int, 30),
    JWT_REFRESH_TOKEN_HOURS=(int, 12),
    MAP_SERVICE_WMS_URL=(str, ""),
    MAP_SERVICE_WMS_USERNAME=(str, ""),
    MAP_SERVICE_WMS_PASSWORD=(str, ""),
    MAP_SERVICE_WMS_OWNED_AREAS_LAYER=(str, ""),
    FILE_SCAN_SERVICE_URL=(str, ""),
    PRIVATE_FILES_LOCATION=(str, ""),
    MEDIA_ROOT=(str, ""),
    STATIC_ROOT=(str, ""),
    FLAG_FILE_SCAN=(bool, False),
    FLAG_PLOTSEARCH=(bool, False),
    FLAG_SKIP_FILE_UPLOAD_PERMISSIONS=(bool, False),
    OFFICER_OTP_REQUIRED=(bool, False),
    MAP_CENTER_LAT=(float, 0.87),
    MAP_CENTER_LNG=(float, 104.15),
    MAP_DEFAULT_ZOOM=(int, 12),
    MAP_WMS_URL=(str, ""),
    MAP_WMS_LAYERS=(str, ""),
    MAP_WMS_NAME=(str, "Peta instansi"),
    MAP_EXTRA_BASEMAPS=(str, ""),
    WHATSAPP_TOKEN=(str, ""),
    WHATSAPP_PHONE_NUMBER_ID=(str, ""),
    WHATSAPP_API_VERSION=(str, "v21.0"),
    ANTHROPIC_API_KEY=(str, ""),
    ANTHROPIC_MODEL=(str, ""),
    OCR_LANGUAGES=(str, "ind+eng"),
)

env_file = project_root(".env")

if os.path.exists(env_file):
    env.read_env(env_file)

DEBUG = env.bool("DEBUG")
SECRET_KEY = env.str("SECRET_KEY", default=("dev-only-insecure-key" if DEBUG else ""))
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY wajib diisi untuk mode produksi.")

# Kunci Fernet (base64 urlsafe 32 byte) untuk enkripsi data pribadi (UU PDP):
# NIK, nomor rekening, nomor KK. WAJIB diisi & disimpan aman di produksi; bila
# berubah, data terenkripsi lama tidak dapat dibaca. Buat dengan:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FIELD_ENCRYPTION_KEY = env.str("FIELD_ENCRYPTION_KEY")
if not FIELD_ENCRYPTION_KEY and not DEBUG:
    raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY wajib diisi untuk mode produksi.")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

OFFICER_UI_URL = env.str("OFFICER_UI_URL")

ADMINS = env.list("ADMINS")

DATABASES = {"default": env.db()}
if env("DATABASE_PASSWORD"):
    DATABASES["default"]["PASSWORD"] = env("DATABASE_PASSWORD")


CACHES = {"default": env.cache()}

if env("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=env("SENTRY_DSN"),
        environment=env("SENTRY_ENVIRONMENT"),
        release=get_git_revision_hash(),
        integrations=[DjangoIntegration()],
    )

MEDIA_ROOT = env.str("MEDIA_ROOT", default=project_root("media"))
STATIC_ROOT = env.str("STATIC_ROOT", default=project_root("static"))
PRIVATE_FILES_LOCATION = env.str("PRIVATE_FILES_LOCATION") or project_root(
    "private_files"
)

MEDIA_URL = "/media/"
STATIC_URL = "/static/"

ROOT_URLCONF = "mvj.urls"
WSGI_APPLICATION = "mvj.wsgi.application"

LANGUAGE_CODE = "id"
LANGUAGES = [
    ("id", _("Indonesian")),
    ("en", _("English")),
]
TIME_ZONE = "Asia/Jakarta"
# Mata uang tunggal sistem (ISO 4217)
CURRENCY_CODE = "IDR"
# Nama instansi pengelola yang ditampilkan di dokumen/surel keluar.
ORGANIZATION_NAME = env.str("ORGANIZATION_NAME")
USE_I18N = True

LOCALE_PATHS = [project_root("locale")]

INSTALLED_APPS = [
    "modeltranslation",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "rangefilter",
    "nested_inline",
    "django_filters",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt.token_blacklist",
    "rest_framework_gis",
    "drf_yasg",
    "corsheaders",
    "auditlog",
    "safedelete",
    "sequences.apps.SequencesConfig",
    "django_countries",
    "users",
    "forms",
    "leasing",
    "plotsearch",
    "audittrail",
    "field_permissions",
    "batchrun",
    "utils",
    "django_q",
    "file_operations",
    "pengadaan",
    "alokasi",
    "asetlahan",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "alokasi.middleware.ApplicantIsolationMiddleware",
    "users.middleware.OfficerOTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "utils.middleware.CustomAuditlogMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "alokasi.context_processors.portal",
            ]
        },
    }
]

AUTH_USER_MODEL = "users.User"

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

MODELTRANSLATION_TRANSLATION_FILES = ("forms.translation",)

REST_FRAMEWORK = {
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "ALLOWED_VERSIONS": ("v1",),
    "DEFAULT_VERSION": "v1",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "leasing.permissions.MvjDjangoModelPermissions",
    ],
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "leasing.renderers.BrowsableAPIRendererWithoutForms",
    ],
    "DEFAULT_METADATA_CLASS": "leasing.metadata.FieldsMetadata",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 30,
    "EXCEPTION_HANDLER": "leasing.viewsets.utils.integrityerror_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {"login": "10/min"},
}

DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
MVJ_EMAIL_FROM = DEFAULT_FROM_EMAIL
FROM_EMAIL_PLOT_SEARCH = env.str("FROM_EMAIL_PLOT_SEARCH")
FROM_EMAIL_AREA_SEARCH = env.str("FROM_EMAIL_AREA_SEARCH")

vars().update(env.email_url("EMAIL_URL"))

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_ALL_ORIGINS = DEBUG and not CORS_ALLOWED_ORIGINS
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")

# Aktifkan bila Django berjalan di belakang reverse proxy (nginx) yang
# meneruskan X-Forwarded-Proto/Host, mis. pada docker compose bawaan.
if env.bool("TRUST_PROXY_HEADERS"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
if not DEBUG:
    SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)
    CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)
CORS_EXPOSE_HEADERS = ["Content-Disposition"]

Q_CLUSTER = {
    "name": "SimLahan",
    "timeout": 90,
    "retry": 60 * 60,  # 1 hour
    "orm": "default",
    "cpu_affinity": 1,
    "workers": 1,
    "error_reporter": {
        "sentry": {
            "dsn": env.str("SENTRY_DSN"),
        }
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_TOKEN_MINUTES")),
    "REFRESH_TOKEN_LIFETIME": timedelta(hours=env.int("JWT_REFRESH_TOKEN_HOURS")),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Peta latar (WMS) opsional untuk layanan peta internal instansi
MAP_SERVICE_WMS_URL = env.str("MAP_SERVICE_WMS_URL")
MAP_SERVICE_WMS_USERNAME = env.str("MAP_SERVICE_WMS_USERNAME")
MAP_SERVICE_WMS_PASSWORD = env.str("MAP_SERVICE_WMS_PASSWORD")
MAP_SERVICE_WMS_OWNED_AREAS_LAYER = env.str("MAP_SERVICE_WMS_OWNED_AREAS_LAYER")

# Peta modul aset lahan (peta tematik, peta berbagi, aplikasi lapangan).
MAP_CENTER_LAT = env.float("MAP_CENTER_LAT")
MAP_CENTER_LNG = env.float("MAP_CENTER_LNG")
MAP_DEFAULT_ZOOM = env.int("MAP_DEFAULT_ZOOM")
MAP_WMS_URL = env.str("MAP_WMS_URL")
MAP_WMS_LAYERS = env.str("MAP_WMS_LAYERS")
MAP_WMS_NAME = env.str("MAP_WMS_NAME")
# JSON daftar peta latar tambahan, mis. Google/Bing dengan kunci API instansi:
# [{"name": "Google Satelit", "url": "https://.../{z}/{x}/{y}?key=...", "attribution": "Google"}]
MAP_EXTRA_BASEMAPS = env.str("MAP_EXTRA_BASEMAPS")

# OTP surel saat petugas masuk (aplikasi petugas & /admin/).
OFFICER_OTP_REQUIRED = env.bool("OFFICER_OTP_REQUIRED")

# Notifikasi WhatsApp Cloud API (opsional).
WHATSAPP_TOKEN = env.str("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = env.str("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_API_VERSION = env.str("WHATSAPP_API_VERSION")

# Asisten AI & ekstraksi dokumen (opsional, Claude API).
ANTHROPIC_API_KEY = env.str("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = env.str("ANTHROPIC_MODEL")
OCR_LANGUAGES = env.str("OCR_LANGUAGES")

# Minimum offset in days from invoice date to due date for generated invoices.
# Ensures that the due date is always in the future.
MVJ_DUE_DATE_OFFSET_DAYS = 17

PUBLIC_UI_URL = env.str("PUBLIC_UI_URL")

FILE_SCAN_SERVICE_URL = env.str("FILE_SCAN_SERVICE_URL")

# Feature flags
FLAG_FILE_SCAN = env.bool("FLAG_FILE_SCAN")
FLAG_PLOTSEARCH = env.bool("FLAG_PLOTSEARCH")
FLAG_SKIP_FILE_UPLOAD_PERMISSIONS = env.bool(
    "FLAG_SKIP_FILE_UPLOAD_PERMISSIONS", default=False
)

if FLAG_SKIP_FILE_UPLOAD_PERMISSIONS:
    # Use operating-system dependent behavior
    # Required for Azure `azure-file` storage class, as it does not support chmod etc.
    FILE_UPLOAD_DIRECTORY_PERMISSIONS = None
    FILE_UPLOAD_PERMISSIONS = None


# Override with local settings if present
local_settings = project_root("local_settings.py")
if os.path.exists(local_settings):
    with open(local_settings) as fp:
        code = compile(fp.read(), local_settings, "exec")
    exec(code, globals(), locals())
