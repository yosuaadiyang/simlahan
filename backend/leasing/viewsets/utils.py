import json

from django.db import DataError, IntegrityError, transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import parsers, status, viewsets
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.views import exception_handler


class AtomicTransactionMixin:
    @transaction.atomic
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class AtomicTransactionModelViewSet(AtomicTransactionMixin, viewsets.ModelViewSet):
    """Viewset that combines AtomicTransactionMixin and rest_framework.viewsets.ModelViewSet"""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # Badan JSON berupa list/angka membuat create()/update() kustom gagal
        # 500 saat memanggil request.data.get(...); laporkan sebagai 400.
        if self.action in ("create", "update", "partial_update") and not isinstance(
            request.data, dict
        ):
            raise ParseError(_("Request body must be a JSON object."))


class MultiPartJsonParser(parsers.MultiPartParser):
    def parse(self, stream, media_type=None, parser_context=None):
        result = super().parse(
            stream, media_type=media_type, parser_context=parser_context
        )

        try:
            data = json.loads(result.data["data"])
        except (KeyError, TypeError, ValueError):
            raise ParseError(
                _("The multipart request must contain a JSON 'data' field.")
            )

        # Flatten the result.files MultiValueDict.
        # If the "files" is not flatten, the serializer would receive the data like this:
        # <MultiValueDict: {'file': [<InMemoryUploadedFile: filename.jpg (image/jpeg)>]}>
        # The serializer wouldn't find the file because the value is an array, not a single File
        files = {}
        for key in result.files.keys():
            files[key] = result.files.get(key)

        return parsers.DataAndFiles(data, files)


def integrityerror_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if isinstance(exc, IntegrityError) and not response:
        response = Response(
            {"detail": _("Data integrity error"), "error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Nilai di luar jangkauan kolom (angka terlalu besar, teks terlalu panjang,
    # format interval salah) adalah kesalahan masukan, bukan galat server.
    if isinstance(exc, DataError) and not response:
        response = Response(
            {"detail": _("Invalid data")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return response
