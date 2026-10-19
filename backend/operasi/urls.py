"""URL pusat komando, dipasang di /komando/."""

from django.urls import path

from operasi import views

urlpatterns = [
    path("", views.command_center, name="operasi-command"),
    path("manifest.webmanifest", views.manifest, name="operasi-manifest"),
    path("sw.js", views.service_worker, name="operasi-sw"),
    path("berkas/<str:kind>/<int:pk>/", views.private_file, name="operasi-file"),
    path("api/ringkasan/", views.summary, name="operasi-summary"),
    path("api/lapisan/<str:key>/", views.layer, name="operasi-layer"),
    path("api/cari/", views.search, name="operasi-search"),
    path("api/absen/", views.attendance, name="operasi-attendance"),
    path("api/kegiatan/", views.activities, name="operasi-activities"),
    path(
        "api/kegiatan/<int:pk>/verifikasi/",
        views.verify_activity,
        name="operasi-activity-verify",
    ),
    path("api/tanah/", views.soil_tests, name="operasi-soil"),
    path("api/warga/", views.residents, name="operasi-residents"),
    path("api/warga/<int:pk>/", views.resident_detail, name="operasi-resident"),
    path("api/tugas/", views.tasks, name="operasi-tasks"),
    path("api/tugas/<int:pk>/", views.task_update, name="operasi-task"),
    path("api/kinerja/", views.performance, name="operasi-performance"),
    path("api/chat/", views.chat, name="operasi-chat"),
    path("api/sos/", views.sos, name="operasi-sos"),
    path("api/sos/<int:pk>/<str:action>/", views.sos_action, name="operasi-sos-action"),
    path("api/posisi/", views.position, name="operasi-position"),
    path("api/ai-satelit/", views.satellite_analysis, name="operasi-satellite"),
    path("api/kunci/", views.system_lock, name="operasi-lock"),
]
