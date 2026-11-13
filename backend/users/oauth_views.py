"""Endpoint OAuth2 (/oauth/): otorisasi, token, pencabutan.

Introspeksi token tidak dipasang: tidak ada scope ``introspection`` sehingga
rutenya tidak dapat dipakai, dan server ini tidak melayani resource server lain.
"""

from django.urls import path
from oauth2_provider import views


class OfficerAuthorizationView(views.AuthorizationView):
    """Halaman persetujuan memakai login panel petugas (dengan OTP bila aktif)."""

    login_url = "/admin/login/"
    template_name = "users/oauth_authorize.html"

    def render_to_response(self, context, **kwargs):
        context.setdefault("title", "Otorisasi aplikasi")
        context.setdefault("site_header", "Panel petugas")
        return super().render_to_response(context, **kwargs)


app_name = "oauth2_provider"

urlpatterns = [
    path("authorize/", OfficerAuthorizationView.as_view(), name="authorize"),
    path("token/", views.TokenView.as_view(), name="token"),
    path("revoke_token/", views.RevokeTokenView.as_view(), name="revoke-token"),
]
