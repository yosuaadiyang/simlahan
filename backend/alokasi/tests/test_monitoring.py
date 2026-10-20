import datetime
import io

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from alokasi import enums, monitoring, services
from alokasi.models import Allocation, DevelopmentReport
from alokasi.setup import ensure_groups, ensure_monitoring_job
from alokasi.templatetags.alokasi_tags import (
    angka,
    bulan_ke_tahun,
    hektare,
    rupiah,
    tanggal,
)

from .test_workflow import approve_and_pay


@pytest.fixture
def allocation(filled_application, officer, verifier):
    services.submit(filled_application, filled_application.applicant.user)
    approve_and_pay(filled_application, officer, verifier)
    return filled_application.allocation


def backdate(allocation, years=0, days=0):
    start = timezone.localdate() - datetime.timedelta(days=365 * years + days)
    Allocation.objects.filter(pk=allocation.pk).update(
        start_date=start, issued_date=start
    )
    allocation.refresh_from_db()
    return allocation


def test_new_allocation_is_not_idle(allocation):
    assert not allocation.is_idle
    assert allocation not in monitoring.idle_queryset()


def test_idle_after_deadline_without_construction(allocation):
    backdate(allocation, years=2, days=2)
    assert allocation.is_idle
    assert list(monitoring.idle_queryset()) == [allocation]
    DevelopmentReport.objects.create(
        allocation=allocation,
        stage=enums.DevelopmentStage.PREPARATION,
        progress_percent=5,
        description="x",
    )
    assert allocation.is_idle  # pematangan saja belum dihitung membangun
    DevelopmentReport.objects.create(
        allocation=allocation,
        stage=enums.DevelopmentStage.CONSTRUCTION,
        progress_percent=10,
        description="y",
    )
    assert not allocation.is_idle
    assert not monitoring.idle_queryset().exists()


def test_overdue_reports(allocation):
    assert monitoring.overdue_report_allocations() == []
    backdate(allocation, days=200)
    assert [a.pk for a in monitoring.overdue_report_allocations()] == [allocation.pk]
    DevelopmentReport.objects.create(
        allocation=allocation,
        stage=enums.DevelopmentStage.PREPARATION,
        progress_percent=5,
        description="x",
    )
    assert monitoring.overdue_report_allocations() == []


def test_expire_allocations(allocation):
    Allocation.objects.filter(pk=allocation.pk).update(
        end_date=timezone.localdate() - datetime.timedelta(days=1)
    )
    assert [a.pk for a in monitoring.expire_allocations()] == [allocation.pk]
    allocation.refresh_from_db()
    assert allocation.status == enums.AllocationStatus.EXPIRED


def test_monitoring_command_sends_reminders(allocation, officer):
    backdate(allocation, years=3)
    mail.outbox.clear()
    out = io.StringIO()
    call_command("alokasi_pemantauan", "--email", stdout=out)
    text = out.getvalue()
    assert "[LAHAN TIDUR]" in text and "[LAPORAN TERLAMBAT]" in text
    recipients = {r for m in mail.outbox for r in m.to}
    assert allocation.holder.user.email in recipients
    assert officer.email in recipients


def test_monitoring_command_without_findings(seeded):
    out = io.StringIO()
    call_command("alokasi_pemantauan", stdout=out)
    assert "Tidak ada temuan" in out.getvalue()


def test_invoice_reminders(filled_application, officer, verifier):
    from .conftest import score_all

    services.submit(filled_application, filled_application.applicant.user)
    services.start_verification(filled_application, officer)
    score_all(filled_application, verifier, 90)
    services.approve(filled_application, officer)
    filled_application.invoices.update(
        due_date=timezone.localdate() - datetime.timedelta(days=1)
    )
    out = io.StringIO()
    call_command("alokasi_pemantauan", stdout=out)
    assert "LEWAT JATUH TEMPO" in out.getvalue()


def test_setup_is_idempotent(seeded):
    from batchrun.models import ScheduledJob

    assert ensure_groups() == []
    assert ensure_monitoring_job() is True
    assert ensure_monitoring_job() is False
    assert (
        ScheduledJob.objects.filter(job__name="Pemantauan alokasi lahan").count() == 1
    )


def test_import_command(tmp_path, seeded):
    import json

    path = tmp_path / "lahan.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "Feature",
                "properties": {"code": "X-1", "name": "Blok X", "luas_m2": "5000"},
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [
                        [[[104.1, 0.8], [104.101, 0.8], [104.101, 0.801], [104.1, 0.8]]]
                    ],
                },
            }
        )
    )
    out = io.StringIO()
    call_command("alokasi_impor_lahan", str(path), "--jenis", "langsung", stdout=out)
    assert "1 lahan baru" in out.getvalue()
    call_command("alokasi_impor_lahan", str(path), stdout=out)
    assert "1 diperbarui" in out.getvalue()
    from alokasi.models import LandPlot

    plot = LandPlot.objects.get(code="X-1")
    assert (
        plot.area_m2 == 5000
        and plot.allocation_type == "langsung"
        and not plot.is_published
    )


def test_template_filters():
    assert rupiah(1234567) == "Rp1.234.567"
    assert angka("1234.5", 2) == "1.234,50"
    assert hektare(125000) == "12,5 ha"
    assert hektare(100000) == "10 ha"
    assert tanggal(datetime.date(2026, 8, 17)) == "17 Agustus 2026"
    assert bulan_ke_tahun(30) == "2 tahun 6 bulan"
    assert bulan_ke_tahun(12) == "1 tahun"
    assert rupiah(None) == "-"


def test_youtube_embed():
    from alokasi.models import InfoPage

    page = InfoPage(video_url="https://www.youtube.com/watch?v=abc_DEF-123&t=5")
    assert (
        page.youtube_embed_url == "https://www.youtube-nocookie.com/embed/abc_DEF-123"
    )
    page.video_url = "https://vimeo.com/123"
    assert page.youtube_embed_url == ""
    page.video_url = "https://youtu.be/<script>"
    assert page.youtube_embed_url == ""


@pytest.mark.django_db
def test_ensure_groups_recreates_every_role_group():
    from django.contrib.auth.models import Group

    from alokasi.setup import GROUP_NAMES
    from utils.group_permissions import UserGroup

    assert set(GROUP_NAMES) == set(UserGroup)
    Group.objects.filter(pk__in=[UserGroup.PAAKAYTTAJA, UserGroup.PENILAI]).delete()
    assert sorted(ensure_groups()) == [UserGroup.PAAKAYTTAJA, UserGroup.PENILAI]
    assert Group.objects.get(pk=UserGroup.PAAKAYTTAJA).name == "Administrator"
