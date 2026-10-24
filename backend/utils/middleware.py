from auditlog.context import set_actor
from auditlog.middleware import AuditlogMiddleware
from django.conf import settings
from django.http import HttpResponseBadRequest
from django.http.multipartparser import MultiPartParserError
from django.utils.functional import SimpleLazyObject
from django.utils.translation import gettext as _
from rest_framework.views import APIView


class CustomAuditlogMiddleware(AuditlogMiddleware):
    def __call__(self, request):
        remote_addr = self._get_remote_addr(request)

        user = SimpleLazyObject(lambda: getattr(request, "user", None))

        context = set_actor(actor=user, remote_addr=remote_addr)

        with context:
            return self.get_response(request)


FORM_CONTENT_TYPES = ("application/x-www-form-urlencoded", "multipart/form-data")


def _has_null(querydict) -> bool:
    return any(
        "\x00" in key or any("\x00" in value for value in values)
        for key, values in querydict.lists()
    )


class RejectNullBytesMiddleware:
    """Tolak karakter NUL pada parameter URL, isian formulir, dan JSON.

    PostgreSQL tidak dapat menyimpan atau mencari teks ber-NUL, sehingga nilai
    seperti ``?q=%00`` yang diteruskan ke kueri menghasilkan galat 500. Nilai
    ini tidak pernah sah, jadi ditolak dengan 400 sebelum mencapai view.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if self._contains_null(request, view_func):
            return HttpResponseBadRequest(
                _("Permintaan memuat karakter yang tidak sah."),
                content_type="text/plain; charset=utf-8",
            )
        return None

    def _contains_null(self, request, view_func) -> bool:
        if _has_null(request.GET):
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return False
        content_type = request.content_type or ""
        if content_type == "multipart/form-data" and _is_drf_view(view_func):
            # Membaca request.POST di sini menghabiskan stream sehingga parser
            # multipart DRF (isian "data" berisi JSON) tidak lagi berjalan.
            # Serializer DRF sudah menolak NUL lewat validator CharField.
            return False
        if content_type in FORM_CONTENT_TYPES:
            try:
                return _has_null(request.POST)
            except MultiPartParserError:
                # Biarkan view/parser yang melaporkan badan permintaan rusak.
                return False
        if content_type.endswith("json"):
            return _json_body_has_null(request)
        return False


def _json_body_has_null(request) -> bool:
    # Hanya badan kecil; unggahan besar dibaca view lewat stream.
    try:
        length = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return False
    limit = settings.DATA_UPLOAD_MAX_MEMORY_SIZE or 0
    if 0 < length <= limit:
        return b"\\u0000" in request.body or b"\x00" in request.body
    return False


def _is_drf_view(view_func) -> bool:
    view_class = getattr(view_func, "cls", None)
    return isinstance(view_class, type) and issubclass(view_class, APIView)
