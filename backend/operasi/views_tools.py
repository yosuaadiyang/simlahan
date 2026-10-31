"""API alat pusat komando: tiket & masukan, OCR, AI dokumen & foto lapangan,
audit data, uji tanah PLTS, dan sinkron Excel."""

import os

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from asetlahan import ai
from asetlahan import geo as aset_geo
from asetlahan.field_views import _parse_location
from operasi import enums, geo, geotech, tools
from operasi.models import GeotechPhoto, GeotechPoint, SoilTest, Ticket
from operasi.views import api, file_url
from operasi.views_spatial import _date, _visible_korwil

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_TICKET_IMAGE_BYTES = 10 * 1024 * 1024
MAX_POINT_ROWS = 3000


def _upload(request, key="berkas", limit=MAX_UPLOAD_BYTES, required=True):
    upload = request.FILES.get(key)
    if upload is None:
        if required:
            raise ValidationError({key: [_("Pilih berkas.")]})
        return None, b""
    if upload.size > limit:
        raise ValidationError(
            {key: [_("Berkas maksimal %(n)s MB.") % {"n": limit // (1024 * 1024)}]}
        )
    return os.path.basename(upload.name or "berkas"), upload


def _xlsx(content: bytes, filename: str) -> HttpResponse:
    response = HttpResponse(content, content_type=XLSX)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _stamp() -> str:
    return timezone.localdate().strftime("%Y%m%d")


# --------------------------------------------------------------------------
# Tiket & masukan
# --------------------------------------------------------------------------


@api(permission="operasi.view_ticket", methods=("GET", "POST"))
def tickets(request):
    user = request.user
    if request.method == "POST":
        if not user.has_perm("operasi.add_ticket"):
            raise PermissionDenied
        data = request.POST
        _name, image = _upload(
            request, "lampiran", MAX_TICKET_IMAGE_BYTES, required=False
        )
        category = data.get("kategori") or enums.TicketCategory.BUG
        priority = data.get("prioritas") or enums.TicketPriority.NORMAL
        ticket = Ticket(
            category=category,
            priority=priority,
            title=data.get("judul", "").strip()[:200],
            description=data.get("deskripsi", "").strip()[:10000],
            created_by=user,
        )
        if image:
            ticket.attachment = image
        ticket.full_clean()
        ticket.save()
        return JsonResponse(tools.ticket_row(ticket, user), status=201)
    queryset = tools.visible_tickets(user)
    status = request.GET.get("status", "")
    if status in enums.TicketStatus.values:
        filtered = queryset.filter(status=status)
    else:
        filtered = queryset
    q = request.GET.get("q", "").strip()[:100]
    if q:
        filtered = filtered.filter(
            Q(number__icontains=q) | Q(title__icontains=q) | Q(description__icontains=q)
        )
    return JsonResponse(
        {
            "rows": [tools.ticket_row(t, user) for t in filtered[:300]],
            "summary": tools.ticket_summary(queryset),
            "leaderboard": tools.ticket_leaderboard(user),
            "can_handle": tools.can_handle_tickets(user),
            "my_points": sum(
                queryset.filter(created_by=user).values_list("points", flat=True)
            ),
        }
    )


@api(permission="operasi.change_ticket", methods=("POST",))
def ticket_action(request, pk):
    ticket = get_object_or_404(tools.visible_tickets(request.user), pk=pk)
    tools.set_ticket_status(
        ticket,
        request.user,
        request.POST.get("status", ""),
        note=request.POST.get("catatan", ""),
        priority=request.POST.get("prioritas", ""),
    )
    return JsonResponse(tools.ticket_row(ticket, request.user))


@api(permission="operasi.view_ticket")
def tickets_excel(request):
    tickets = tools.visible_tickets(request.user)[:20000]
    return _xlsx(tools.tickets_workbook(tickets), f"tiket-{_stamp()}.xlsx")


# --------------------------------------------------------------------------
# OCR & AI
# --------------------------------------------------------------------------


@api(methods=("POST",))
def ocr(request):
    name, upload = _upload(request)
    return JsonResponse(tools.ocr(request.user, name, upload.read()))


@api(methods=("POST",))
def document_ai(request):
    name, upload = _upload(request)
    return JsonResponse(
        tools.document_report(
            request.user, name, upload.read(), request.POST.get("fokus", "")
        )
    )


@api(methods=("POST",))
def field_photo_ai(request):
    name, upload = _upload(request)
    return JsonResponse(
        tools.field_photo(
            request.user, name, upload.read(), request.POST.get("konteks", "")
        )
    )


@api(permission="operasi.run_data_audit", methods=("GET", "POST"))
def data_audit(request):
    result = tools.data_audit(request.user)
    if request.method == "POST":
        try:
            result["summary"] = tools.audit_summary(request.user, result)
        except ai.AIError as error:
            raise ValidationError({"ai": [str(error)]})
    return JsonResponse(result)


@api()
def sync_excel(request):
    return _xlsx(tools.full_workbook(request.user), f"sinkron-komando-{_stamp()}.xlsx")


# --------------------------------------------------------------------------
# Uji tanah PLTS
# --------------------------------------------------------------------------


def _filtered_points(request):
    queryset = geotech.visible_points(request.user)
    korwil = _visible_korwil(request)
    if korwil is not None:
        queryset = queryset.filter(korwil=korwil)
    params = request.GET
    if params.get("status") in enums.GeotechWorkStatus.values:
        queryset = queryset.filter(work_status=params["status"])
    if params.get("survei") in enums.SurveyStatus.values:
        queryset = queryset.filter(survey_status=params["survei"])
    if params.get("bagian") in enums.GeotechSegment.values:
        queryset = queryset.filter(segment=params["bagian"])
    if params.get("metode") in enums.GeotechMethod.values:
        queryset = queryset.filter(method=params["metode"])
    if str(params.get("batch", "")).isdigit():
        queryset = queryset.filter(batch=int(params["batch"]))
    q = params.get("q", "").strip()[:100]
    if q:
        key = "".join(ch for ch in q if ch.isalnum()).upper()
        condition = (
            Q(area_name__icontains=q)
            | Q(zone_name__icontains=q)
            | Q(landowner__icontains=q)
        )
        if key:
            condition |= Q(code_key__contains=key)
        queryset = queryset.filter(condition)
    return queryset


@api(permission="operasi.view_geotechpoint", methods=("GET", "POST"))
def geotech_points(request):
    user = request.user
    if request.method == "POST":
        if not user.has_perm("operasi.add_geotechpoint"):
            raise PermissionDenied
        point = GeotechPoint(created_by=user)
        _apply_form(request, point)
        if point.korwil_id is None:
            point.korwil = geo.korwil_for_write(user, point.location)
        geotech.save_with_history(point, user)
        return JsonResponse(geotech.point_rows([point])[0], status=201)
    queryset = _filtered_points(request)
    total = queryset.count()
    rows = geotech.point_rows(queryset.order_by("batch", "code")[:MAX_POINT_ROWS])
    every = geotech.visible_points(user)
    return JsonResponse(
        {
            "rows": rows,
            "summary": geotech.summary(rows),
            "total": total,
            "truncated": total > MAX_POINT_ROWS,
            "batches": sorted(set(every.values_list("batch", flat=True))),
            "areas": sorted(
                set(every.exclude(area_name="").values_list("area_name", flat=True))
            )[:200],
            "can_add": user.has_perm("operasi.add_geotechpoint"),
            "can_change": user.has_perm("operasi.change_geotechpoint"),
        }
    )


FORM_TEXT = {
    "kode": ("code", 64),
    "area": ("area_name", 128),
    "zona": ("zone_name", 128),
    "pemilik": ("landowner", 255),
    "kendala": ("obstacle", 255),
    "akses": ("access", 255),
    "catatan_survei": ("survey_note", 5000),
    "catatan_kerja": ("work_note", 5000),
    "rekomendasi": ("recommendation", 5000),
}
FORM_CHOICES = {
    "metode": "method",
    "bagian": "segment",
    "survei": "survey_status",
    "sosial": "social_condition",
    "status": "work_status",
}


def _form_numbers(data, point):
    if "batch" in data:
        if not str(data["batch"]).isdigit():
            raise ValidationError({"batch": [_("Batch harus angka 1–99.")]})
        point.batch = int(data["batch"])
    if "progres" in data:
        if not str(data["progres"]).isdigit():
            raise ValidationError({"progres": [_("Progres harus 0–100.")]})
        point.progress_pct = int(data["progres"])
    for key, field in (("mulai", "started_on"), ("selesai", "finished_on")):
        if key in data:
            setattr(point, field, _date(data[key], key))


def _form_place(request, data, point):
    if "korwil" in data:
        point.korwil = _visible_korwil(request)
    if "lat" in data or "lng" in data:
        point.location = (
            _parse_location(data) if data.get("lat") or data.get("lng") else None
        )
    if "uji_lab" in data:
        number = data["uji_lab"].strip()
        soil_tests = geo.scoped(SoilTest.objects.all(), request.user)
        point.soil_test = (
            get_object_or_404(soil_tests, number=number) if number else None
        )


def _apply_form(request, point):
    data = request.POST
    for key, (field, limit) in FORM_TEXT.items():
        if key in data:
            setattr(point, field, data[key].strip()[:limit])
    for key, field in FORM_CHOICES.items():
        if key in data:
            setattr(point, field, data[key])
    _form_numbers(data, point)
    _form_place(request, data, point)


def _point_detail(point, user) -> dict:
    row = geotech.point_rows([point])[0]
    row["history"] = geotech.history(point)
    row["photos"] = [
        {
            "id": photo.pk,
            "url": file_url("uji-plts", photo) + "?lihat=1",
            "caption": photo.caption,
            "by": tools._name(photo.uploaded_by),
            "at": timezone.localtime(photo.created_at).isoformat(),
            "can_delete": user.has_perm("operasi.delete_geotechphoto")
            or photo.uploaded_by_id == user.pk,
        }
        for photo in point.photos.select_related("uploaded_by")
    ]
    row["can_change"] = geotech.can_change(user, point)
    row["can_photo"] = (
        user.has_perm("operasi.add_geotechphoto")
        and len(row["photos"]) < geotech.MAX_PHOTOS
    )
    return row


def _visible_point(request, pk):
    return get_object_or_404(
        geotech.visible_points(request.user).select_related("korwil", "soil_test"),
        pk=pk,
    )


@api(permission="operasi.view_geotechpoint", methods=("GET", "POST"))
def geotech_point(request, pk):
    point = _visible_point(request, pk)
    if request.method == "POST":
        if not geotech.can_change(request.user, point):
            raise PermissionDenied
        before = geotech.snapshot(point)
        _apply_form(request, point)
        geotech.save_with_history(
            point,
            request.user,
            note=request.POST.get("catatan_ubah", "")[:255],
            source=_("Formulir"),
            before=before,
        )
    return JsonResponse(_point_detail(point, request.user))


@api(permission="operasi.change_geotechpoint", methods=("POST",))
def geotech_action(request, pk, action):
    point = _visible_point(request, pk)
    geotech.quick_action(point, request.user, action, request.POST.get("catatan", ""))
    return JsonResponse(_point_detail(point, request.user))


@api(permission="operasi.add_geotechphoto", methods=("POST",))
def geotech_photo(request, pk):
    point = _visible_point(request, pk)
    if point.photos.count() >= geotech.MAX_PHOTOS:
        raise ValidationError(
            {"foto": [_("Maksimal %(n)s foto per titik.") % {"n": geotech.MAX_PHOTOS}]}
        )
    _name, image = _upload(request, "foto", MAX_TICKET_IMAGE_BYTES)
    photo = GeotechPhoto(
        point=point,
        image=image,
        caption=request.POST.get("keterangan", "").strip()[:255],
        uploaded_by=request.user,
    )
    photo.full_clean()
    photo.save()
    return JsonResponse(_point_detail(point, request.user), status=201)


@api(permission="operasi.view_geotechpoint", methods=("POST",))
def geotech_photo_delete(request, pk):
    photo = get_object_or_404(
        GeotechPhoto.objects.filter(
            point__in=geotech.visible_points(request.user)
        ).select_related("point"),
        pk=pk,
    )
    user = request.user
    if not (
        user.has_perm("operasi.delete_geotechphoto")
        or (
            photo.uploaded_by_id == user.pk
            and user.has_perm("operasi.add_geotechphoto")
        )
    ):
        raise PermissionDenied
    point = photo.point
    photo.delete()
    return JsonResponse(_point_detail(point, user))


@api(permission="operasi.view_geotechpoint")
def geotech_excel(request):
    points = _filtered_points(request).order_by("batch", "code")
    return _xlsx(geotech.workbook(points), f"uji-tanah-plts-{_stamp()}.xlsx")


@api(permission="operasi.change_geotechpoint", methods=("POST",))
def geotech_import(request):
    mode = request.POST.get("mode", "perbarui")
    if mode not in ("perbarui", "lengkap"):
        raise ValidationError({"mode": [_("Mode impor tidak dikenal.")]})
    name, upload = _upload(request)
    rows = geotech.read_rows(name, upload.read())
    if request.POST.get("tahap") != "terapkan":
        data = geotech.preview_import(request.user, rows, mode)
        data["file"] = name
        return JsonResponse(data)
    selected = [
        int(part)
        for part in request.POST.get("pilih", "").split(",")
        if part.strip().isdigit()
    ]
    if not selected:
        raise ValidationError({"pilih": [_("Pilih minimal satu baris.")]})
    return JsonResponse(
        geotech.apply_import(request.user, rows, mode, selected, source=name[:64])
    )


# --------------------------------------------------------------------------
# Lapisan peta & konfigurasi
# --------------------------------------------------------------------------


def _geotech_features(request):
    points = geotech.visible_points(request.user).filter(location__isnull=False)
    if request.GET.get("status") in enums.GeotechWorkStatus.values:
        points = points.filter(work_status=request.GET["status"])
    for row in geotech.point_rows(points.order_by("code")[:5000]):
        yield aset_geo.feature(
            _point_geometry(row),
            {
                "id": row["id"],
                "kind": "uji-plts",
                "status": row["status"],
                "title": row["code"],
                "color": row["color"],
                "rows": [
                    [_("Metode"), row["method_label"]],
                    [_("Status"), f"{row['status_label']} · {row['progress']}%"],
                    [_("Survei"), row["survey_label"]],
                    [_("Kondisi sosial"), row["social_label"]],
                    [_("Area"), row["area"] or "-"],
                    [_("Batch"), row["batch"]],
                ],
            },
        )


def _point_geometry(row):
    from django.contrib.gis.geos import Point

    return Point(row["lng"], row["lat"], srid=4326)


LAYERS = {"uji-plts": ("operasi.view_geotechpoint", _geotech_features)}


def _choices(choices) -> list[dict]:
    return [{"value": str(v), "label": str(label)} for v, label in choices]


def config(user) -> dict:
    return {
        "perms": {
            "tiket": user.has_perm("operasi.view_ticket"),
            "kirimTiket": user.has_perm("operasi.add_ticket"),
            "tanganiTiket": user.has_perm("operasi.change_ticket"),
            "auditData": user.has_perm("operasi.run_data_audit"),
            "ujiPlts": user.has_perm("operasi.view_geotechpoint"),
            "tambahUjiPlts": user.has_perm("operasi.add_geotechpoint"),
            "ubahUjiPlts": user.has_perm("operasi.change_geotechpoint"),
            "fotoUjiPlts": user.has_perm("operasi.add_geotechphoto"),
        },
        "urls": {
            "tickets": reverse("operasi-tickets"),
            "ticketAction": reverse("operasi-ticket-action", args=[0]),
            "ticketsExcel": reverse("operasi-tickets-excel"),
            "ocr": reverse("operasi-ocr"),
            "documentAi": reverse("operasi-document-ai"),
            "fieldPhotoAi": reverse("operasi-field-photo-ai"),
            "dataAudit": reverse("operasi-data-audit"),
            "syncExcel": reverse("operasi-sync-excel"),
            "geotech": reverse("operasi-geotech"),
            "geotechPoint": reverse("operasi-geotech-point", args=[0]),
            "geotechAction": reverse("operasi-geotech-action", args=[0, "__aksi__"]),
            "geotechPhoto": reverse("operasi-geotech-photo", args=[0]),
            "geotechPhotoDelete": reverse("operasi-geotech-photo-delete", args=[0]),
            "geotechExcel": reverse("operasi-geotech-excel"),
            "geotechImport": reverse("operasi-geotech-import"),
        },
        "choices": {
            "ticketCategory": _choices(enums.TicketCategory.choices),
            "ticketPriority": _choices(enums.TicketPriority.choices),
            "ticketStatus": _choices(enums.TicketStatus.choices),
            "geoMethod": _choices(enums.GeotechMethod.choices),
            "geoSegment": _choices(enums.GeotechSegment.choices),
            "geoSurvey": _choices(enums.SurveyStatus.choices),
            "geoSocial": _choices(enums.SocialCondition.choices),
            "geoStatus": _choices(enums.GeotechWorkStatus.choices),
        },
        "colors": {
            "ticket": {str(k): v for k, v in enums.TICKET_COLORS.items()},
            "geotech": {str(k): v for k, v in enums.GEOTECH_COLORS.items()},
            "photoFinding": tools.PHOTO_CATEGORIES,
        },
        "ai": ai.enabled(),
    }
