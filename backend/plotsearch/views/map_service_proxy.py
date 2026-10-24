import logging

import requests
from django.conf import settings
from django.http import StreamingHttpResponse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from requests.auth import HTTPBasicAuth
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_502_BAD_GATEWAY,
    HTTP_503_SERVICE_UNAVAILABLE,
    HTTP_504_GATEWAY_TIMEOUT,
)

from plotsearch.serializers.map_service_proxy import WmsRequestSerializer

logger = logging.getLogger(__name__)


def _json_response(data, status) -> Response:
    """Response DRF yang bisa dirender dari view fungsi biasa (bukan APIView).

    Tanpa renderer, Django gagal merender Response DRF (AssertionError -> 500).
    """
    response = Response(data, status=status)
    response.accepted_renderer = JSONRenderer()
    response.accepted_media_type = "application/json"
    response.renderer_context = {}
    return response


@require_http_methods(["GET", "OPTIONS"])
def owned_areas_wms_proxy(request):
    """
    One may wonder why this is a function based view, but there is a reason for that.
    Django rest framework based views take a query parameter `format` and use that for router route matching.
    This is not compatible with WMS proxying, as the `format` parameter is used in the WMS request for its own purposes.
    This is a workaround to avoid that. Otherwise passing the `format` query parameter will not find any urls,
    and will return 404.
    """
    map_service_url = settings.MAP_SERVICE_WMS_URL
    username = settings.MAP_SERVICE_WMS_USERNAME
    password = settings.MAP_SERVICE_WMS_PASSWORD
    layer = settings.MAP_SERVICE_WMS_OWNED_AREAS_LAYER

    if not all([username, password, map_service_url, layer]):
        # Layanan opsional yang belum dikonfigurasi: endpoint publik ini tidak
        # boleh menghasilkan galat server (dan log galat) bagi setiap pengunjung.
        logger.debug("Owned Areas WMS Proxy Public: Missing configuration settings.")
        return _json_response(
            "Service misconfigured.",
            status=HTTP_503_SERVICE_UNAVAILABLE,
        )

    serializer = WmsRequestSerializer(data=request.GET)
    if not serializer.is_valid():
        logger.warning(f"Invalid WMS parameters: {serializer.errors}")
        return _json_response(serializer.errors, status=HTTP_400_BAD_REQUEST)

    validated_data = serializer.validated_data

    params = {
        "service": "WMS",
        "request": "GetMap",
        "layers": layer,
        "styles": "",
        "format": validated_data.get("format"),
        "transparent": "true",
        "version": "1.1.1",
        "width": str(validated_data.get("width")),
        "height": str(validated_data.get("height")),
        "srs": validated_data.get("srs"),
        "bbox": validated_data.get("bbox"),
    }
    timeout = 5.0
    try:
        r = requests.get(
            map_service_url,
            params=params,
            auth=HTTPBasicAuth(username, password),
            stream=True,
            timeout=timeout,
        )
    except requests.exceptions.Timeout as e:
        logger.error(f"WMS request timed out after {timeout}s: {str(e)}")
        return _json_response(
            "Error connecting to map service, timeout", status=HTTP_504_GATEWAY_TIMEOUT
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"WMS request failed: {type(e).__name__}")
        return _json_response(
            "Error connecting to map service", status=HTTP_500_INTERNAL_SERVER_ERROR
        )

    if r.status_code != 200:
        content = _("Error in upstream service")
        if settings.DEBUG:
            content = r.content

        return _json_response(content, status=r.status_code)

    response_content_type = r.headers.get("Content-Type", "").lower()
    format_choices = serializer.fields.fields.get("format").choices.keys()
    if response_content_type not in format_choices:
        logger.warning(
            f"Unexpected content type from upstream: {response_content_type}"
        )
        return _json_response(
            "Invalid response from upstream service", status=HTTP_502_BAD_GATEWAY
        )

    response_headers = {
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'self'",
        "Cache-Control": "max-age=3600, public",  # 1 hour
    }
    return StreamingHttpResponse(
        status=r.status_code,
        reason=r.reason,
        content_type=r.headers["Content-Type"],
        streaming_content=r.raw,
        headers=response_headers,
    )
