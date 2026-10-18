"""URL modul aset lahan.

``admin_urlpatterns`` dipasang di /admin/asetlahan/ (sebelum situs admin),
``portal_urlpatterns`` di /portal/ (pengaduan & lelang), dan
``public_urlpatterns`` di /aset/ (peta berbagi & aplikasi lapangan).
"""

from django.urls import path

from asetlahan import admin_views, field_views, portal_views

admin_urlpatterns = [
    path(
        "berkas/<str:kind>/<int:pk>/", admin_views.officer_file, name="asetlahan-file"
    ),
    path("dasbor/", admin_views.dashboard, name="asetlahan-dashboard"),
    path("peta/", admin_views.thematic_map, name="asetlahan-map"),
    path(
        "peta/lapisan/<str:layer>/", admin_views.map_layer, name="asetlahan-map-layer"
    ),
    path("gantt/", admin_views.gantt, name="asetlahan-gantt"),
    path("laporan/", admin_views.report_builder, name="asetlahan-reports"),
    path("buku-besar/", admin_views.ledger_view, name="asetlahan-ledger"),
    path("tumpang-tindih/", admin_views.overlaps, name="asetlahan-overlaps"),
    path("citra/", admin_views.imagery_compare, name="asetlahan-imagery-compare"),
    path(
        "pemangku/matriks/",
        admin_views.stakeholder_matrix,
        name="asetlahan-stakeholder-matrix",
    ),
    path("cari/", admin_views.search, name="asetlahan-search"),
    path("asisten/", admin_views.assistant, name="asetlahan-assistant"),
]

portal_urlpatterns = [
    path("pengaduan/", portal_views.grievance_create, name="grievance_create"),
    path("pengaduan/terkirim/", portal_views.grievance_done, name="grievance_done"),
    path("pengaduan/cek/", portal_views.grievance_check, name="grievance_check"),
    path("lelang/", portal_views.tender_list, name="tender_list"),
    path("lelang/<str:number>/", portal_views.tender_detail, name="tender_detail"),
    path("lelang/<str:number>/tawar/", portal_views.bid_submit, name="bid_submit"),
]

public_urlpatterns = [
    path("peta/<uuid:token>/", field_views.shared_map, name="asetlahan-share"),
    path(
        "peta/<uuid:token>/data.geojson",
        field_views.shared_map_data,
        name="asetlahan-share-data",
    ),
    path("lapangan/", field_views.field_app, name="asetlahan-field"),
    path(
        "lapangan/manifest.webmanifest",
        field_views.field_manifest,
        name="asetlahan-field-manifest",
    ),
    path("lapangan/sw.js", field_views.field_service_worker, name="asetlahan-field-sw"),
    path(
        "lapangan/batas.geojson",
        field_views.field_boundaries,
        name="asetlahan-field-boundaries",
    ),
    path("lapangan/sinkron/", field_views.field_sync, name="asetlahan-field-sync"),
]
