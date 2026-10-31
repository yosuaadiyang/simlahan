"""URL pusat komando, dipasang di /komando/."""

from django.urls import path

from operasi import (
    auth_views,
    views,
    views_dashboard,
    views_flow,
    views_spatial,
    views_tools,
)

urlpatterns = [
    path("", views.command_center, name="operasi-command"),
    path("masuk/", auth_views.CommandLoginView.as_view(), name="operasi-login"),
    path("keluar/", auth_views.command_logout, name="operasi-logout"),
    path("manifest.webmanifest", views.manifest, name="operasi-manifest"),
    path("sw.js", views.service_worker, name="operasi-sw"),
    path("berkas/<str:kind>/<int:pk>/", views.private_file, name="operasi-file"),
    path("api/ringkasan/", views.summary, name="operasi-summary"),
    path("api/lapisan/<str:key>/", views.layer, name="operasi-layer"),
    path("api/cari/", views.search, name="operasi-search"),
    path("api/absen/", views.attendance, name="operasi-attendance"),
    path(
        "api/absen/persetujuan/",
        views.leave_requests,
        name="operasi-leave-requests",
    ),
    path(
        "api/absen/<int:pk>/persetujuan/",
        views.leave_decision,
        name="operasi-leave-decision",
    ),
    path("api/kegiatan/", views.activities, name="operasi-activities"),
    path(
        "api/kegiatan/<int:pk>/verifikasi/",
        views.verify_activity,
        name="operasi-activity-verify",
    ),
    path(
        "api/kegiatan/<int:pk>/konfirmasi-dampak/",
        views.confirm_impact,
        name="operasi-activity-impact",
    ),
    path(
        "api/temuan-ilegal/",
        views.illegal_findings,
        name="operasi-illegal-findings",
    ),
    path(
        "api/patroli/pratinjau/",
        views.patrol_preview,
        name="operasi-patrol-preview",
    ),
    path("api/tanah/", views.soil_tests, name="operasi-soil"),
    path("api/warga/", views.residents, name="operasi-residents"),
    path("api/warga/<int:pk>/", views.resident_detail, name="operasi-resident"),
    path("api/tugas/", views_flow.tasks, name="operasi-tasks"),
    path(
        "api/tugas/penerima/",
        views_flow.task_assignees,
        name="operasi-task-assignees",
    ),
    path("api/tugas/<int:pk>/", views_flow.task_detail, name="operasi-task"),
    path(
        "api/laporan-harian/",
        views_flow.daily_report_home,
        name="operasi-daily-reports",
    ),
    path(
        "api/laporan-harian/susun/",
        views_flow.daily_report_compose,
        name="operasi-daily-report-compose",
    ),
    path(
        "api/laporan-harian/selesai/",
        views_flow.daily_report_finish,
        name="operasi-daily-report-finish",
    ),
    path(
        "api/laporan-harian/lacak/",
        views_flow.daily_report_trace,
        name="operasi-daily-report-trace",
    ),
    path(
        "api/laporan-harian/<int:pk>/",
        views_flow.daily_report_detail,
        name="operasi-daily-report",
    ),
    path(
        "api/laporan-harian/<int:pk>/<str:action>/",
        views_flow.daily_report_detail,
        name="operasi-daily-report-action",
    ),
    path("api/persetujuan/", views_flow.approval_queue, name="operasi-approvals"),
    path("api/lencana/", views_flow.badges, name="operasi-badges"),
    path("api/rekap/", views_flow.recap_excel, name="operasi-recap"),
    path("api/beranda/", views_dashboard.home, name="operasi-home"),
    path(
        "api/korwil/<int:pk>/",
        views_dashboard.korwil_detail,
        name="operasi-korwil-detail",
    ),
    path("api/historis/", views_dashboard.history, name="operasi-history"),
    path("api/kinerja/", views_dashboard.performance, name="operasi-performance"),
    path(
        "api/kinerja/wawasan/",
        views_dashboard.performance_insight,
        name="operasi-performance-insight",
    ),
    path("api/peringkat/", views_dashboard.leaderboard, name="operasi-leaderboard"),
    path(
        "api/peringkat/excel/",
        views_dashboard.leaderboard_excel,
        name="operasi-leaderboard-excel",
    ),
    path(
        "api/peringkat/wawasan/",
        views_dashboard.leaderboard_insight,
        name="operasi-leaderboard-insight",
    ),
    path("api/struktur/", views.structure, name="operasi-structure"),
    path("api/feed/", views.feed, name="operasi-feed"),
    path("api/ai-chat/", views.ai_chat, name="operasi-ai-chat"),
    path("api/chat/", views.chat, name="operasi-chat"),
    path("api/sos/", views.sos, name="operasi-sos"),
    path("api/sos/<int:pk>/<str:action>/", views.sos_action, name="operasi-sos-action"),
    path("api/posisi/", views.position, name="operasi-position"),
    path("api/ai-satelit/", views.satellite_analysis, name="operasi-satellite"),
    path("api/kunci/", views.system_lock, name="operasi-lock"),
    path("api/bidang/", views_spatial.plots, name="operasi-plots"),
    path("api/bidang/impor/", views_spatial.plot_import, name="operasi-plot-import"),
    path("api/bidang/<int:pk>/", views_spatial.plot_detail, name="operasi-plot"),
    path("api/tumpang-tindih/", views_spatial.overlap, name="operasi-overlap"),
    path("api/audit-rtrw/", views_spatial.rtrw_audit, name="operasi-rtrw-audit"),
    path("api/anomali/", views_spatial.anomalies, name="operasi-anomalies"),
    path("api/peta-panas/", views_spatial.heatmap, name="operasi-heatmap"),
    path("api/jejak/", views_spatial.track, name="operasi-track"),
    path("api/zona-ancaman/", views_spatial.threat_zones, name="operasi-threat-zones"),
    path(
        "api/zona-ancaman/<int:pk>/<str:action>/",
        views_spatial.threat_zone_action,
        name="operasi-threat-zone-action",
    ),
    path("api/foto-360/", views_spatial.site_photos, name="operasi-site-photos"),
    path(
        "api/foto-360/<int:pk>/hapus/",
        views_spatial.site_photo_delete,
        name="operasi-site-photo-delete",
    ),
    # Alat
    path("api/tiket/", views_tools.tickets, name="operasi-tickets"),
    path("api/tiket/excel/", views_tools.tickets_excel, name="operasi-tickets-excel"),
    path(
        "api/tiket/<int:pk>/status/",
        views_tools.ticket_action,
        name="operasi-ticket-action",
    ),
    path("api/alat/ocr/", views_tools.ocr, name="operasi-ocr"),
    path("api/alat/dokumen-ai/", views_tools.document_ai, name="operasi-document-ai"),
    path(
        "api/alat/foto-lapangan-ai/",
        views_tools.field_photo_ai,
        name="operasi-field-photo-ai",
    ),
    path("api/alat/audit-data/", views_tools.data_audit, name="operasi-data-audit"),
    path("api/alat/sinkron-excel/", views_tools.sync_excel, name="operasi-sync-excel"),
    path("api/uji-plts/", views_tools.geotech_points, name="operasi-geotech"),
    path(
        "api/uji-plts/excel/", views_tools.geotech_excel, name="operasi-geotech-excel"
    ),
    path(
        "api/uji-plts/impor/", views_tools.geotech_import, name="operasi-geotech-import"
    ),
    path(
        "api/uji-plts/<int:pk>/",
        views_tools.geotech_point,
        name="operasi-geotech-point",
    ),
    path(
        "api/uji-plts/<int:pk>/foto/",
        views_tools.geotech_photo,
        name="operasi-geotech-photo",
    ),
    path(
        "api/uji-plts/<int:pk>/<str:action>/",
        views_tools.geotech_action,
        name="operasi-geotech-action",
    ),
    path(
        "api/uji-plts/foto/<int:pk>/hapus/",
        views_tools.geotech_photo_delete,
        name="operasi-geotech-photo-delete",
    ),
]
