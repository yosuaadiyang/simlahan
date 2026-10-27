"""URL modul dokumen.

``portal_urlpatterns`` dipasang di /portal/dokumen/ (namespace ``dokumen_portal``)
dan ``admin_urlpatterns`` di /admin/dokumen/ sebelum situs admin.
"""

from django.urls import path

from dokumen import admin_views, views

portal_urlpatterns = [
    path("", views.index, name="index"),
    path("pemanfaatan/<str:number>/", views.land_use_detail, name="land_use"),
    path("izin/<int:pk>/perbarui/", views.record_update, name="record_update"),
    path("izin/<int:pk>/format/", views.template_download, name="template_download"),
    path("versi/<int:pk>/minta-unduh/", views.request_version_download, name="request_version_download"),
    path("tanda-tangan/<str:number>/", views.signing_detail, name="signing_detail"),
    path("tanda-tangan/<str:number>/komentar/", views.signing_comment, name="signing_comment"),
    path("tanda-tangan/<str:number>/minta-unduh/", views.request_signing_download, name="request_signing_download"),
    path("unduhan/", views.downloads_list, name="downloads"),
    path("unduhan/<str:number>/batal/", views.download_cancel, name="download_cancel"),
    path("unduh/<str:number>/", views.download, name="download"),
    path("ttd/<uuid:token>/", views.sign, name="sign"),
    path("ttd/<uuid:token>/pdf/", views.sign_pdf, name="sign_pdf"),
    path("verifikasi/", views.verify, name="verify"),
    path("verifikasi/<uuid:token>/", views.verify, name="verify_token"),
]

admin_urlpatterns = [
    path("dasbor/", admin_views.dashboard, name="dokumen-dashboard"),
    path("unduh/<str:number>/", admin_views.staff_download, name="dokumen-staff-download"),
    path("pratinjau/versi/<int:pk>/", admin_views.version_preview, name="dokumen-version-preview"),
    path("minta-unduh/<str:kind>/<int:pk>/", admin_views.staff_request_download, name="dokumen-staff-request"),
]
