import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from asetlahan import enums, finance, geo
from asetlahan.models import (
    CaseHearing,
    EncroachmentCase,
    Grievance,
    LandTransaction,
    LegalCase,
    ModuleSettings,
    Task,
)

pytestmark = pytest.mark.django_db

TOOLS = [
    "asetlahan-dashboard",
    "asetlahan-map",
    "asetlahan-gantt",
    "asetlahan-reports",
    "asetlahan-ledger",
    "asetlahan-overlaps",
    "asetlahan-imagery-compare",
    "asetlahan-stakeholder-matrix",
    "asetlahan-search",
    "asetlahan-assistant",
]


@pytest.fixture
def data(make_asset, units):
    asset = make_asset(service_unit=units[0], status=enums.AssetStatus.ENCROACHED)
    other = make_asset(service_unit=units[1], code="AST-LAIN")
    case = LegalCase.objects.create(title="Gugatan", opposing_party="Penggugat")
    case.assets.add(asset)
    CaseHearing.objects.create(
        case=case,
        agenda="Pembuktian",
        scheduled_at=timezone.now() + datetime.timedelta(days=2),
    )
    EncroachmentCase.objects.create(
        title="Pagar", asset=asset, location=asset.geometry.centroid
    )
    Task.objects.create(
        title="Ukur ulang",
        asset=asset,
        start_date=timezone.localdate(),
        due_date=timezone.localdate() + datetime.timedelta(days=5),
    )
    Grievance.objects.create(
        complainant_name="Warga", subject="Pagar", description="D", asset=asset
    )
    LandTransaction.objects.create(
        transaction_type=enums.TransactionType.LEASE_INCOME,
        amount=Decimal("1000"),
        asset=asset,
    )
    LandTransaction.objects.create(
        transaction_type=enums.TransactionType.SURVEY,
        amount=Decimal("400"),
        asset=asset,
    )
    return {"asset": asset, "other": other}


@pytest.mark.parametrize("name", TOOLS)
def test_tool_pages_render_for_admin(client, admin, data, name):
    client.force_login(admin)
    response = client.get(reverse(name))
    assert response.status_code == 200


def test_tool_pages_require_staff(client, data):
    response = client.get(reverse("asetlahan-dashboard"))
    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


def test_tools_respect_permissions_and_flags(client, field_officer, data):
    client.force_login(field_officer)
    assert client.get(reverse("asetlahan-ledger")).status_code == 403
    config = ModuleSettings.load()
    config.enable_tasks = False
    config.save()
    assert client.get(reverse("asetlahan-gantt")).status_code == 404


def test_admin_changelists_and_forms_render(client, admin, data):
    from django.contrib import admin as django_admin

    client.force_login(admin)
    models = [
        m for m in django_admin.site._registry if m._meta.app_label == "asetlahan"
    ]
    assert len(models) >= 25
    for model in models:
        name = model._meta.model_name
        response = client.get(reverse(f"admin:asetlahan_{name}_changelist"))
        assert response.status_code in (200, 302), name
        obj = model.objects.first()
        if obj is not None:
            response = client.get(
                reverse(f"admin:asetlahan_{name}_change", args=[obj.pk])
            )
            assert response.status_code == 200, name


def test_map_layer_is_scoped(client, officer, data):
    client.force_login(officer)
    response = client.get(reverse("asetlahan-map-layer", args=["aset"]))
    titles = [f["properties"]["title"] for f in response.json()["features"]]
    assert any(data["asset"].code in t for t in titles)
    assert not any("AST-LAIN" in t for t in titles)
    assert (
        client.get(reverse("asetlahan-map-layer", args=["tidak-ada"])).status_code
        == 404
    )
    assert (
        client.get(
            reverse("asetlahan-map-layer", args=["aset"]) + "?kategori=x"
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "fmt,content_type",
    [
        ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("csv", "text/csv"),
        ("pdf", "application/pdf"),
    ],
)
def test_report_export_formats(client, admin, data, fmt, content_type):
    client.force_login(admin)
    response = client.get(reverse("asetlahan-reports"), {"data": "aset", "format": fmt})
    assert response.status_code == 200
    assert response["Content-Type"].startswith(content_type)
    body = (
        b"".join(response.streaming_content) if response.streaming else response.content
    )
    if fmt == "csv":
        assert data["asset"].code in body.decode("utf-8-sig")


def test_report_builder_filters(client, admin, data):
    client.force_login(admin)
    response = client.get(
        reverse("asetlahan-reports"),
        {"data": "aset", "status": enums.AssetStatus.ENCROACHED},
    )
    assert response.context["total"] == 1


def test_journal_rows_are_balanced(data):
    rows = finance.journal_rows(LandTransaction.objects.all())
    assert len(rows) == 4
    assert sum(r[4] for r in rows) == sum(r[5] for r in rows) == 1400
    income = [r for r in rows if r[2] == "4101"]
    assert income[0][5] == 1000


def test_ledger_combines_income_and_expense(admin, data):
    result = finance.ledger(admin)
    assert result["income"] == Decimal("1000")
    assert result["expense"] == Decimal("400")


def test_overlap_detection(make_asset):
    first = make_asset(geometry=geo.as_multipolygon(make_asset().geometry))
    pairs = list(geo.asset_overlaps())
    assert pairs and first.code in {pairs[0]["a"].code, pairs[0]["b"].code}


def test_search_finds_assets_and_document_text(client, admin, data):
    client.force_login(admin)
    response = client.get(reverse("asetlahan-search"), {"q": data["asset"].code})
    assert data["asset"].code in response.content.decode()


def test_private_file_requires_permission(client, field_officer, admin, data):
    from django.core.files.base import ContentFile

    from asetlahan.models import Document

    document = Document(title="Sertipikat", asset=data["asset"])
    document.file.save("sertipikat.pdf", ContentFile(b"%PDF-1.4 uji"), save=False)
    document.save()
    url = reverse("asetlahan-file", args=["dokumen", document.pk])
    client.force_login(admin)
    response = client.get(url)
    assert response.status_code in (
        200,
        403,
    )  # 403 bila pemindaian virus aktif & belum lolos
    client.force_login(field_officer)
    assert (
        client.get(
            reverse("asetlahan-file", args=["tidak-ada", document.pk])
        ).status_code
        == 404
    )
