from django.urls import path

from alokasi import views

app_name = "portal"

urlpatterns = [
    path("", views.home, name="home"),
    # Lahan
    path("lahan/", views.plot_list, name="plot_list"),
    path("lahan.geojson", views.plot_geojson, name="plot_geojson"),
    path("lahan/<str:code>/", views.plot_detail, name="plot_detail"),
    path("lahan/<str:code>/foto/", views.plot_photo, name="plot_photo"),
    path(
        "lahan/<str:code>/ajukan/", views.application_create, name="application_create"
    ),
    # Informasi
    path("layanan/", views.services_page, name="services"),
    path("informasi/", views.info_index, name="info_index"),
    path("informasi/kategori/<str:category>/", views.info_index, name="info_category"),
    path("informasi/<slug:slug>/", views.info_detail, name="info_detail"),
    path(
        "informasi/<slug:slug>/lampiran/", views.info_attachment, name="info_attachment"
    ),
    path("verifikasi/", views.verify_document, name="verify"),
    path("verifikasi/<uuid:token>/", views.verify_document, name="verify_token"),
    # Akun
    path("daftar/", views.register, name="register"),
    path("aktivasi/kirim-ulang/", views.resend_activation, name="resend_activation"),
    path("aktivasi/<str:uidb64>/<str:token>/", views.activate, name="activate"),
    path("masuk/", views.PortalLoginView.as_view(), name="login"),
    path("keluar/", views.logout_view, name="logout"),
    path("lupa-sandi/", views.PortalPasswordResetView.as_view(), name="password_reset"),
    path(
        "lupa-sandi/terkirim/",
        views.PortalPasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "atur-sandi/<str:uidb64>/<str:token>/",
        views.PortalPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "atur-sandi/selesai/",
        views.PortalPasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path("akun/", views.dashboard, name="dashboard"),
    path("akun/profil/", views.profile, name="profile"),
    path("akun/sandi/", views.password_change, name="password_change"),
    # Permohonan
    path(
        "permohonan/<str:number>/", views.application_detail, name="application_detail"
    ),
    path(
        "permohonan/<str:number>/ubah/", views.application_edit, name="application_edit"
    ),
    path(
        "permohonan/<str:number>/dokumen/",
        views.document_upload,
        name="document_upload",
    ),
    path(
        "permohonan/<str:number>/dokumen/<int:pk>/",
        views.document_download,
        name="document_download",
    ),
    path(
        "permohonan/<str:number>/dokumen/<int:pk>/hapus/",
        views.document_delete,
        name="document_delete",
    ),
    path(
        "permohonan/<str:number>/ajukan/",
        views.application_submit,
        name="application_submit",
    ),
    path(
        "permohonan/<str:number>/terima/",
        views.application_accept_transfer,
        name="application_accept_transfer",
    ),
    path(
        "permohonan/<str:number>/batal/",
        views.application_cancel,
        name="application_cancel",
    ),
    # Tagihan
    path("tagihan/<str:number>/pdf/", views.invoice_pdf, name="invoice_pdf"),
    path(
        "tagihan/<str:number>/bukti/",
        views.invoice_proof_upload,
        name="invoice_proof_upload",
    ),
    path(
        "tagihan/<str:number>/bukti/lihat/", views.invoice_proof, name="invoice_proof"
    ),
    # Dokumen terbit
    path("dokumen/<uuid:token>/unduh/", views.issued_download, name="issued_download"),
    # Alokasi
    path("alokasi/<int:pk>/", views.allocation_detail, name="allocation_detail"),
    path("alokasi/<int:pk>/izin/", views.permit_report_save, name="permit_report_save"),
    path(
        "alokasi/<int:pk>/izin/<int:report_pk>/dokumen/",
        views.permit_document,
        name="permit_document",
    ),
    path(
        "alokasi/<int:pk>/progres/",
        views.development_report_create,
        name="development_report_create",
    ),
    path(
        "alokasi/<int:pk>/progres/<int:report_pk>/lampiran/",
        views.development_attachment,
        name="development_attachment",
    ),
    path("alokasi/<int:pk>/peralihan/", views.transfer_create, name="transfer_create"),
]
