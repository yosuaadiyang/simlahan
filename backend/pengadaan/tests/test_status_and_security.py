import datetime
from decimal import Decimal

import pytest
from django.db import connection

from pengadaan import enums
from pengadaan.crypto import decrypt, encrypt, fingerprint, mask
from pengadaan.models import (
    AcquisitionMilestone,
    AcquisitionParcel,
    Announcement,
    Compensation,
    CompensationPayment,
    Consignment,
    Deliberation,
    DeliberationResult,
    EntitledParty,
    Handover,
    ParcelSurvey,
    RightsRelease,
    Valuation,
)

D = datetime.date


def _status(parcel):
    return AcquisitionParcel.all_objects.get(pk=parcel.pk).status


@pytest.mark.django_db
def test_project_identifier_and_default_milestones(project):
    year = datetime.date.today().year
    assert project.identifier.startswith(f"PT-{year}-")
    milestones = AcquisitionMilestone.objects.filter(project=project)
    assert milestones.count() > 10
    stages = set(milestones.values_list("stage", flat=True))
    assert {
        enums.ProjectStage.PLANNING,
        enums.ProjectStage.PREPARATION,
        enums.ProjectStage.IMPLEMENTATION,
        enums.ProjectStage.HANDOVER,
    } <= stages


@pytest.mark.django_db
def test_parcel_status_follows_acquisition_flow(project, parcel, party):
    assert _status(parcel) == enums.ParcelStatus.IDENTIFIED

    ParcelSurvey.objects.create(
        parcel=parcel,
        survey_type=enums.SurveyType.PHYSICAL,
        status=enums.SurveyStatus.DONE,
    )
    assert _status(parcel) == enums.ParcelStatus.INVENTORIED

    Announcement.objects.create(
        project=project,
        announcement_type=enums.AnnouncementType.INVENTORY,
        announced_on=D(2025, 1, 6),
    )
    assert _status(parcel) == enums.ParcelStatus.ANNOUNCED

    valuation = Valuation.objects.create(
        parcel=parcel,
        status=enums.ValuationStatus.FINAL,
        value_land=Decimal("150000000"),
        value_building=Decimal("50000000"),
        value_non_physical=Decimal("10000000"),
    )
    assert valuation.total_value == Decimal("210000000")
    assert _status(parcel) == enums.ParcelStatus.VALUED

    deliberation = Deliberation.objects.create(project=project, held_on=D(2025, 2, 3))
    result = DeliberationResult.objects.create(
        deliberation=deliberation,
        parcel=parcel,
        party=party,
        outcome=enums.DeliberationOutcome.AGREED,
        compensation_form=enums.CompensationForm.MONEY,
        agreed_amount=Decimal("210000000"),
    )
    assert _status(parcel) == enums.ParcelStatus.AGREED

    compensation = Compensation.objects.create(
        parcel=parcel,
        party=party,
        amount=Decimal("210000000"),
        status=enums.CompensationStatus.VALIDATED,
        valuation=valuation,
        deliberation_result=result,
    )
    CompensationPayment.objects.create(
        compensation=compensation, paid_on=D(2025, 3, 3), amount=Decimal("110000000")
    )
    assert _status(parcel) == enums.ParcelStatus.AGREED
    payment = CompensationPayment.objects.create(
        compensation=compensation, paid_on=D(2025, 3, 4), amount=Decimal("100000000")
    )
    compensation.refresh_from_db()
    assert compensation.status == enums.CompensationStatus.PAID
    assert compensation.outstanding_amount == Decimal("0")
    assert _status(parcel) == enums.ParcelStatus.PAID

    # Menghapus pembayaran mengembalikan status.
    payment.delete()
    compensation.refresh_from_db()
    assert compensation.status == enums.CompensationStatus.VALIDATED
    assert _status(parcel) == enums.ParcelStatus.AGREED
    CompensationPayment.objects.create(
        compensation=compensation, paid_on=D(2025, 3, 4), amount=Decimal("100000000")
    )

    RightsRelease.objects.create(parcel=parcel, party=party, released_on=D(2025, 3, 5))
    assert _status(parcel) == enums.ParcelStatus.RELEASED

    handover = Handover.objects.create(
        project=project, handed_over_on=D(2025, 3, 10), recipient="Dinas PUPR"
    )
    handover.parcels.add(parcel)
    assert _status(parcel) == enums.ParcelStatus.HANDED_OVER
    handover.parcels.remove(parcel)
    assert _status(parcel) == enums.ParcelStatus.RELEASED


@pytest.mark.django_db
def test_consignment_and_exclusion_status(project, parcel, party):
    Consignment.objects.create(
        parcel=parcel,
        party=party,
        reason=enums.ConsignmentReason.REFUSED,
        status=enums.ConsignmentStatus.DEPOSITED,
        application_date=D(2025, 4, 1),
        amount=Decimal("1000"),
    )
    assert _status(parcel) == enums.ParcelStatus.CONSIGNED
    parcel.is_excluded = True
    parcel.save()
    assert _status(parcel) == enums.ParcelStatus.EXCLUDED


def test_crypto_roundtrip_and_mask(settings):
    token = encrypt("2171010101900001")
    assert token.startswith("enc$")
    assert decrypt(token) == "2171010101900001"
    assert encrypt("") == ""
    assert fingerprint("2171010101900001") == fingerprint("2171010101900001")
    assert fingerprint("2171010101900001") != fingerprint("2171010101900002")
    masked = mask("2171010101900001")
    assert masked.endswith("0001") and "*" in masked
    assert "2171010101900001" not in masked


@pytest.mark.django_db
def test_personal_data_is_encrypted_at_rest(party):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT nik, bank_account_number, nik_fingerprint "
            "FROM pengadaan_entitledparty WHERE id = %s",
            [party.pk],
        )
        nik, account, fp = cursor.fetchone()
    assert nik.startswith("enc$") and "2171010101900001" not in nik
    assert account.startswith("enc$")
    assert fp == fingerprint("2171010101900001")
    assert EntitledParty.objects.get(pk=party.pk).nik == "2171010101900001"
