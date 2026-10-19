import datetime

import pytest
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone

from operasi import enums
from operasi.models import (
    LOCK_CACHE_KEY,
    Activity,
    CommandSettings,
    Resident,
    SoilTest,
    StanceChange,
    SystemLock,
)
from operasi.tests.conftest import inside

pytestmark = pytest.mark.django_db


def test_numbers_and_korwil_from_location(korwil, field):
    resident = Resident.objects.create(head_name="Ahmad", location=inside(korwil))
    activity = Activity.objects.create(
        title="Sosialisasi", location=inside(korwil), reported_by=field
    )
    test = SoilTest.objects.create(location=inside(korwil), sampled_by=field)
    year = timezone.localdate().year
    assert resident.number == f"WRG-{year}-0001"
    assert activity.number == f"KGT-{year}-0001"
    assert test.number == f"UJT-{year}-0001"
    assert resident.korwil == activity.korwil == test.korwil == korwil


def test_activity_without_location_uses_reporter_korwil(korwil, field):
    activity = Activity.objects.create(title="Rapat", reported_by=field)
    assert activity.korwil == korwil


def test_stance_change_is_recorded(korwil, field):
    resident = Resident.objects.create(head_name="Hasan", korwil=korwil)
    assert not StanceChange.objects.exists()
    resident.stance = enums.Stance.SUPPORT
    resident._changed_by = field
    resident.save()
    change = StanceChange.objects.get()
    assert (change.old_stance, change.new_stance, change.changed_by) == (
        enums.Stance.UNKNOWN,
        enums.Stance.SUPPORT,
        field,
    )
    # Instance dengan field tertunda tidak memicu riwayat palsu.
    deferred = Resident.objects.only("pk", "head_name").get(pk=resident.pk)
    deferred.head_name = "Hasan bin Ali"
    deferred.save()
    assert StanceChange.objects.count() == 1


def test_nik_is_encrypted_with_fingerprint(korwil):
    from pengadaan.crypto import fingerprint

    resident = Resident.objects.create(head_name="Yusuf", nik="2171010101010001")
    assert resident.nik_fingerprint == fingerprint("2171010101010001")
    assert Resident.objects.get(pk=resident.pk).nik == "2171010101010001"


def test_activity_cannot_be_in_future(field):
    activity = Activity(
        title="Besok",
        started_at=timezone.now() + datetime.timedelta(hours=2),
        reported_by=field,
    )
    with pytest.raises(ValidationError):
        activity.full_clean(exclude=["number"])


def test_verified_at_follows_flag(field):
    activity = Activity.objects.create(
        title="Verifikasi", verified=True, verified_by=field
    )
    assert activity.verified_at is not None
    activity.verified = False
    activity.save()
    assert activity.verified_at is None and activity.verified_by is None


def test_command_settings_validation(db):
    config = CommandSettings.load()
    config.weight_task = 30
    with pytest.raises(ValidationError):
        config.full_clean()
    config.weight_task = 25
    config.work_end = datetime.time(7, 0)
    with pytest.raises(ValidationError):
        config.full_clean()
    config.work_end = datetime.time(17, 0)
    config.satellite_tile_url = "http://contoh.test/{z}/{x}/{y}"
    with pytest.raises(ValidationError):
        config.full_clean()


def test_system_lock_state_and_passcode(admin_user):
    lock = SystemLock.load()
    assert SystemLock.state()["armed"] is False
    lock.set_passcode("rahasia123")
    lock.is_armed = True
    lock.shutdown_at = timezone.now() - datetime.timedelta(minutes=1)
    lock.save()
    assert cache.get(LOCK_CACHE_KEY) is None
    state = SystemLock.state()
    assert state["armed"] and SystemLock.is_locked_state(state)
    assert not lock.check_passcode("salah")
    assert lock.check_passcode("rahasia123")
    lock.defuse(admin_user)
    assert SystemLock.state()["armed"] is False
    assert lock.defused_by == admin_user


def test_released_parcel_marks_land_released(korwil, municipality_factory):
    from decimal import Decimal

    from pengadaan import enums as p_enums
    from pengadaan.models import AcquisitionParcel, AcquisitionProject

    project = AcquisitionProject.objects.create(
        name="Proyek uji",
        requiring_agency="Dinas PUPR",
        municipality=municipality_factory(name="Kota Uji", identifier="9971"),
        acquisition_type=p_enums.AcquisitionType.PUBLIC_INTEREST,
        purpose_category=p_enums.PublicInterestCategory.ROADS,
    )
    parcel = AcquisitionParcel.objects.create(
        project=project,
        parcel_number="001",
        right_type=p_enums.LandRightType.SHM,
        measured_area_m2=Decimal("500"),
        affected_area_m2=Decimal("200"),
    )
    resident = Resident.objects.create(
        head_name="Salim", korwil=korwil, pengadaan_parcel=parcel
    )
    assert resident.land_status == enums.LandStatus.PENDING
    AcquisitionParcel.all_objects.filter(pk=parcel.pk).update(
        status=p_enums.ParcelStatus.RELEASED
    )
    resident.save()
    assert resident.land_status == enums.LandStatus.RELEASED


def test_point_outside_any_korwil_has_no_korwil(korwil):
    resident = Resident.objects.create(
        head_name="Jauh", location=Point(105.5, 1.5, srid=4326)
    )
    assert resident.korwil is None
