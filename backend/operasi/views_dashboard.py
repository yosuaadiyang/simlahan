"""API pusat komando: beranda, detail Korwil, historis, peringkat, rincian kinerja."""

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

from operasi import dashboard, ranking, services
from operasi.views import _throttled, api

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _period(request, default="bulan") -> str:
    period = request.GET.get("periode") or request.POST.get("periode") or default
    return period if period in services.PERIODS else default


def _korwil_param(request, queryset):
    value = request.GET.get("korwil") or request.POST.get("korwil") or ""
    if not value:
        return None
    if not str(value).isdigit():
        raise PermissionDenied
    return get_object_or_404(queryset, pk=value)


def _insight_throttled(user) -> JsonResponse | None:
    if _throttled(f"operasi:wawasan:{user.pk}", 20, 3600):
        return JsonResponse(
            {"error": _("Batas 20 wawasan per jam tercapai. Coba lagi nanti.")},
            status=429,
        )
    return None


@api(permission="operasi.view_korwil")
def home(request):
    """Beranda: angka utama, tren dukungan, ringkasan per Korwil."""
    return JsonResponse(dashboard.home(request.user))


@api(permission="operasi.view_korwil")
def korwil_detail(request, pk):
    korwil = get_object_or_404(services.visible_korwils(request.user), pk=pk)
    return JsonResponse(dashboard.korwil_detail(request.user, korwil))


@api(permission="operasi.view_resident")
def history(request):
    """Historis komsos, perubahan sikap, dan perubahan luas lahan."""
    if not dashboard.can_view_history(request.user):
        raise PermissionDenied
    start, end = services.period_bounds(_period(request))
    korwil = _korwil_param(request, services.visible_korwils(request.user))
    return JsonResponse(dashboard.history(request.user, start, end, korwil))


def _board(request) -> dict:
    tier = request.GET.get("tier") or request.POST.get("tier") or ""
    view = request.GET.get("tampilan") or request.POST.get("tampilan") or "semua"
    return ranking.board(
        request.user,
        _period(request),
        korwil=_korwil_param(request, ranking.team_scope_korwils(request.user)),
        tier=tier if tier in dict(ranking.TIERS) else "",
        view=view if view in ranking.VIEWS else "semua",
    )


@api(permission="operasi.view_korwil")
def leaderboard(request):
    """Peringkat tim: periode, Korwil, tier, Top/Bottom, dan lencana."""
    data = _board(request)
    data["tiers"] = [{"value": k, "label": str(v)} for k, v in ranking.TIERS]
    data["korwils"] = [
        {"id": k.pk, "code": k.code, "name": k.name}
        for k in ranking.team_scope_korwils(request.user).order_by("code")
    ]
    return JsonResponse(data)


@api(permission="operasi.view_korwil")
def leaderboard_excel(request):
    data = _board(request)
    response = HttpResponse(ranking.board_workbook(data), content_type=XLSX)
    response["Content-Disposition"] = (
        f'attachment; filename="peringkat-{data["start"]}-{data["end"]}.xlsx"'
    )
    return response


@api(permission="operasi.view_korwil", methods=("POST",))
def leaderboard_insight(request):
    limited = _insight_throttled(request.user)
    if limited:
        return limited
    text, by_ai = ranking.board_insight(_board(request))
    return JsonResponse({"text": text, "ai": by_ai})


def _target(request):
    value = request.GET.get("petugas") or request.POST.get("petugas") or ""
    if str(value).isdigit():
        return get_object_or_404(services.team_users(request.user), pk=value)
    return request.user


@api()
def performance(request):
    """Kinerja sendiri atau anggota tim; ``rinci=1`` menambah grafik dan peta."""
    start, end = services.period_bounds(_period(request))
    team = services.team_users(request.user)
    target = _target(request)
    me = services.performance(target, start, end)
    data = {"me": me}
    if request.GET.get("rinci") == "1":
        data["detail"] = ranking.personal(target, start, end, me)
    if team.exclude(pk=request.user.pk).exists():
        data["team"] = services.leaderboard(request.user, start, end, trend=False)
    return JsonResponse(data)


@api(methods=("POST",))
def performance_insight(request):
    limited = _insight_throttled(request.user)
    if limited:
        return limited
    start, end = services.period_bounds(_period(request))
    target = _target(request)
    me = services.performance(target, start, end)
    text, by_ai = ranking.personal_insight(me, ranking.personal(target, start, end, me))
    return JsonResponse({"text": text, "ai": by_ai})
