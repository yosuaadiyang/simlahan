"""Bagian khusus laporan kegiatan per jenis.

* Komsos: warga baru didata langsung dari laporan (beberapa orang sekaligus).
* Temuan ilegal: profil temuan (baru) atau kunjungan ulang (berulang).
* Patroli Taman Buru: rute, temuan + foto bukti, bibit, impor SMART.
* Kegiatan lainnya: rubrik dampak (divalidasi model Activity).

``prepare`` memeriksa seluruh isian sebelum apa pun disimpan; ``commit``
menyimpannya di dalam transaksi laporan setelah kegiatan tersimpan.
"""

import json
from dataclasses import dataclass, field

from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _

from asetlahan.field_views import _parse_location
from operasi import enums, geo, patrol
from operasi.models import (
    HuntingParkFinding,
    HuntingParkPatrol,
    IllegalFinding,
    IllegalFindingVisit,
    Resident,
    Seedling,
)

MAX_NEW_RESIDENTS = enums.KOMSOS_MAX_PERSONS
MAX_FINDINGS = 50
MAX_SEEDLINGS = 50
MAX_FINDING_PHOTOS = 3


@dataclass
class ReportParts:
    residents: list = field(default_factory=list)
    finding: IllegalFinding | None = None
    visit: IllegalFindingVisit | None = None
    patrol: HuntingParkPatrol | None = None
    patrol_findings: list = field(default_factory=list)  # (temuan, [foto])
    seedlings: list = field(default_factory=list)
    smart: dict | None = None
    smart_name: str = ""


def _json_list(raw, key: str, limit: int) -> list[dict]:
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        raise ValidationError({key: [_("Data tidak sah.")]})
    if not isinstance(items, list) or len(items) > limit:
        raise ValidationError({key: [_("Paling banyak %(n)s baris.") % {"n": limit}]})
    if not all(isinstance(item, dict) for item in items):
        raise ValidationError({key: [_("Data tidak sah.")]})
    return items


def _text(data, key: str, size: int) -> str:
    value = data.get(key)
    return str(value).strip()[:size] if value not in (None, "") else ""


def _choice(data, key: str, choices) -> str:
    value = _text(data, key, 32)
    if value not in choices.values:
        raise ValidationError({key: [_("Pilihan tidak sah.")]})
    return value


def _time(data, key):
    value = _text(data, key, 40)
    if not value:
        return None
    moment = parse_datetime(value)
    if moment is None:
        raise ValidationError({key: [_("Waktu tidak sah.")]})
    return patrol._time(value)


def _point(item):
    if item.get("lat") in (None, "") or item.get("lng") in (None, ""):
        return None
    return _parse_location({"lat": str(item["lat"]), "lng": str(item["lng"])})


# --------------------------------------------------------------------------
# Komsos
# --------------------------------------------------------------------------


def _new_residents(activity, data, user) -> list[Resident]:
    from operasi.views import _apply_resident_fields

    people = _json_list(data.get("warga_baru"), "warga_baru", MAX_NEW_RESIDENTS)
    if not people:
        return []
    if not user.has_perm("operasi.add_resident"):
        raise PermissionDenied
    residents = []
    for index, person in enumerate(people, start=1):
        values = {
            str(k): "" if v is None else str(v)
            for k, v in person.items()
            if not isinstance(v, (dict, list))
        }
        resident = Resident(created_by=user)
        try:
            _apply_resident_fields(resident, values)
        except ValidationError as error:
            raise ValidationError({f"warga_baru {index}": [m for m in error.messages]})
        if not resident.head_name.strip():
            raise ValidationError(
                {f"warga_baru {index}": [_("Nama warga wajib diisi.")]}
            )
        resident.location = _point(person) or activity.location
        residents.append(resident)
    return residents


# --------------------------------------------------------------------------
# Temuan ilegal
# --------------------------------------------------------------------------

PROFILE_FIELDS = (
    ("ti_lokasi", "location_name", 255),
    ("ti_pemilik", "owner_name", 255),
    ("ti_pemilik_hp", "owner_phone", 32),
    ("ti_domisili", "owner_domicile", 255),
    ("ti_pengurus", "manager_name", 255),
    ("ti_pengurus_hp", "manager_phone", 32),
    ("ti_status_hutan", "forest_status", 128),
    ("ti_mulai", "business_started", 128),
)


def _finding(activity, data, user):
    """Temuan yang dikunjungi: (temuan, baru?, boleh memperbarui profil?)."""
    finding_id = _text(data, "temuan_id", 12)
    if finding_id:
        if not finding_id.isdigit():
            raise ValidationError({"temuan_id": [_("Temuan tidak ditemukan.")]})
        finding = get_object_or_404(
            geo.scoped(IllegalFinding.objects.all(), user), pk=finding_id
        )
        return finding, False, user.has_perm("operasi.change_illegalfinding")
    if not user.has_perm("operasi.add_illegalfinding"):
        raise PermissionDenied
    if activity.location is None:
        raise ValidationError(
            {"location": [_("Temuan ilegal baru wajib memakai lokasi GPS.")]}
        )
    return IllegalFinding(created_by=user, location=activity.location), True, True


def _update_profile(finding, data, is_new: bool) -> None:
    """Isi profil temuan baru; pada kunjungan berulang hanya isian yang diisi."""
    from operasi.views import _decimal_or_none

    if is_new or _text(data, "ti_aktivitas", 16):
        finding.activity_kind = _choice(data, "ti_aktivitas", enums.IllegalActivityKind)
    for key, attr, size in PROFILE_FIELDS:
        value = _text(data, key, size)
        if is_new or value:
            setattr(finding, attr, value)
    raw_area = _text(data, "ti_luas", 32)
    if raw_area:
        area = _decimal_or_none(raw_area, 0, 99_999_999, places=4)
        if area is None:
            raise ValidationError({"ti_luas": [_("Luas harus angka 0 atau lebih.")]})
        finding.area_ha = area


def _illegal(activity, data, user, parts: ReportParts) -> None:
    finding, is_new, may_update = _finding(activity, data, user)
    if may_update:
        _update_profile(finding, data, is_new)
    if not finding.location_name.strip():
        raise ValidationError({"ti_lokasi": [_("Lokasi temuan wajib diisi.")]})
    finding.full_clean(
        exclude=["number", "korwil", "created_by"], validate_unique=False
    )
    parts.finding = finding
    parts.visit = IllegalFindingVisit(
        is_new=is_new,
        permit=_choice(data, "ti_izin", enums.PermitStatus),
        business_activity=_choice(data, "ti_usaha", enums.BusinessActivity),
        persons_involved=_text(data, "ti_oknum", 5000),
        equipment=_text(data, "ti_peralatan", 5000),
        buildings=_text(data, "ti_bangunan", 5000),
        follow_up=_text(data, "ti_tindak", 5000),
    )
    activity.location_name = activity.location_name or finding.location_name


# --------------------------------------------------------------------------
# Patroli Taman Buru
# --------------------------------------------------------------------------


def _smart(activity, files, parts: ReportParts) -> None:
    smart_file = files.get("smart")
    if smart_file is None:
        return
    if smart_file.size > patrol.MAX_FILE_BYTES:
        raise ValidationError({"smart": [_("Berkas SMART maksimal 15 MB.")]})
    parts.smart = patrol.parse(smart_file.read())
    parts.smart_name = smart_file.name
    if activity.location is None and parts.smart["coords"]:
        lng, lat = parts.smart["coords"][0]
        activity.location = _parse_location({"lat": str(lat), "lng": str(lng)})
    if activity.distance_m is None:
        activity.distance_m = parts.smart["meta"]["distance_m"] or None


def _patrol_report(data) -> HuntingParkPatrol:
    routes = [r for r in _text(data, "tb_rute", 200).split(",") if r]
    if any(r not in enums.PatrolRoute.values for r in routes):
        raise ValidationError({"tb_rute": [_("Pilihan tidak sah.")]})
    report = HuntingParkPatrol(
        input_mode=(
            _choice(data, "tb_mode", enums.PatrolInput)
            if data.get("tb_mode")
            else enums.PatrolInput.MANUAL
        ),
        grid=_text(data, "tb_grid", 255),
        routes=list(dict.fromkeys(routes)),
        objective=_text(data, "tb_objektif", 255),
        team_leader=_text(data, "tb_ketua", 255),
        team=_text(data, "tb_regu", 255),
        station=_text(data, "tb_stasiun", 255),
        transport=_text(data, "tb_transport", 128),
        patrol_started_at=_time(data, "tb_mulai"),
        patrol_ended_at=_time(data, "tb_selesai"),
        situation=_choice(data, "tb_situasi", enums.PatrolSituation),
        personnel_condition=_choice(data, "tb_personil", enums.PersonnelCondition),
        materiel_condition=_choice(data, "tb_materiil", enums.MaterielCondition),
        weather_morning=_choice(data, "tb_cuaca_pagi", enums.Weather),
        weather_noon=_choice(data, "tb_cuaca_siang", enums.Weather),
        weather_afternoon=_choice(data, "tb_cuaca_sore", enums.Weather),
        obstacles=_text(data, "tb_kendala", 5000),
        suggestions=_text(data, "tb_saran", 5000),
    )
    start, end = report.patrol_started_at, report.patrol_ended_at
    if start and end and end < start:
        raise ValidationError({"tb_selesai": [_("Waktu selesai sebelum waktu mulai.")]})
    report.full_clean(exclude=["activity"])
    return report


def _patrol_finding(item, label: str) -> HuntingParkFinding:
    description = _text(item, "deskripsi", 500)
    if not description:
        raise ValidationError({label: [_("Deskripsi temuan wajib diisi.")]})
    quantity = _text(item, "jumlah", 12)
    if quantity and not quantity.isdigit():
        raise ValidationError({label: [_("Jumlah harus bilangan bulat.")]})
    finding = HuntingParkFinding(
        category=(
            _choice(item, "kategori", enums.FindingCategory)
            if item.get("kategori")
            else enums.FindingCategory.OTHER
        ),
        description=description,
        quantity=int(quantity) if quantity else None,
        forest_status=_text(item, "status_hutan", 128),
        new_activity={"ada": True, "tidak": False}.get(
            _text(item, "aktivitas_baru", 8)
        ),
        note=_text(item, "keterangan", 500),
        location=_point(item),
    )
    finding.full_clean(exclude=["patrol"])
    return finding


def _seedling(item, label: str) -> Seedling:
    quantity = _text(item, "jumlah", 12)
    species = _text(item, "nama", 128)
    if not species or not quantity.isdigit() or int(quantity) > 100_000_000:
        raise ValidationError({label: [_("Isi jenis dan jumlah bibit.")]})
    seedling = Seedling(
        kind=_choice(item, "jenis", enums.SeedlingKind),
        species=species,
        quantity=int(quantity),
    )
    seedling.full_clean(exclude=["patrol"])
    return seedling


def _patrol(activity, data, files, user, parts: ReportParts) -> None:
    from operasi.views import photo_object

    if not activity.location_name:
        raise ValidationError({"lokasi": [_("Lokasi patroli wajib diisi.")]})
    _smart(activity, files, parts)
    if activity.location is None:
        raise ValidationError(
            {"location": [_("Patroli Taman Buru wajib memakai lokasi GPS.")]}
        )
    parts.patrol = _patrol_report(data)
    items = _json_list(data.get("temuan_patroli"), "temuan_patroli", MAX_FINDINGS)
    for index, item in enumerate(items):
        finding = _patrol_finding(item, f"temuan_patroli {index + 1}")
        uploads = files.getlist(f"foto_temuan_{index}")[:MAX_FINDING_PHOTOS]
        photos = [photo_object(u, location=finding.location) for u in uploads]
        parts.patrol_findings.append((finding, photos))
    items = _json_list(data.get("bibit"), "bibit", MAX_SEEDLINGS)
    parts.seedlings = [
        _seedling(item, f"bibit {index + 1}") for index, item in enumerate(items)
    ]


# --------------------------------------------------------------------------
# Rangkaian
# --------------------------------------------------------------------------


def prepare(activity, data, files, user) -> ReportParts:
    parts = ReportParts()
    kind = activity.activity_type
    if kind == enums.ActivityType.KOMSOS:
        parts.residents = _new_residents(activity, data, user)
    elif kind == enums.ActivityType.ILLEGAL:
        _illegal(activity, data, user, parts)
    elif kind == enums.ActivityType.HUNTING_PARK:
        _patrol(activity, data, files, user, parts)
    return parts


def commit(parts: ReportParts, activity, user) -> None:
    for resident in parts.residents:
        resident.korwil = resident.korwil or activity.korwil
        resident._korwil_resolved = resident.korwil_id is not None
        resident.registered_activity = activity
        resident.save()
        activity.residents.add(resident)
    if parts.finding is not None:
        if parts.finding.pk is None:
            parts.finding.korwil = activity.korwil
            parts.finding._korwil_resolved = True
        parts.finding.save()
        parts.visit.activity = activity
        parts.visit.finding = parts.finding
        parts.visit.save()
    if parts.patrol is not None:
        parts.patrol.activity = activity
        parts.patrol.save()
        for finding, photos in parts.patrol_findings:
            finding.patrol = parts.patrol
            finding.save()
            for photo in photos:
                photo.activity = activity
                photo.hunting_finding = finding
                photo.save()
        for seedling in parts.seedlings:
            seedling.patrol = parts.patrol
            seedling.save()
    if parts.smart is not None:
        patrol.save_session(parts.smart, user, activity, parts.smart_name)


def describe(activity) -> dict:
    """Ringkasan bagian khusus untuk daftar laporan di pusat komando."""
    info = {}
    visit = getattr(activity, "illegal_visit", None)
    if visit is not None:
        info["temuan"] = {
            "number": visit.finding.number,
            "kind": visit.finding.get_activity_kind_display(),
            "location": visit.finding.location_name,
            "is_new": visit.is_new,
            "visits": visit.finding.visits.count(),
        }
    report = getattr(activity, "patrol_report", None)
    if report is not None:
        info["patroli"] = {
            "grid": report.grid,
            "routes": [enums.PatrolRoute(r).label for r in report.routes],
            "findings": report.findings.count(),
            "tended": report.seedling_total(enums.SeedlingKind.TENDED),
            "produced": report.seedling_total(enums.SeedlingKind.PRODUCED),
            "smart": activity.patrol_sessions.count(),
        }
    return info
