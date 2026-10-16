"""Sinkronisasi status bidang setiap kali data terkait berubah."""

from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from pengadaan.models import (
    AcquisitionParcel,
    Announcement,
    Compensation,
    CompensationPayment,
    Consignment,
    DeliberationResult,
    Handover,
    Objection,
    ParcelSurvey,
    RightsRelease,
    Valuation,
)


def _refresh(parcel_id):
    if not parcel_id:
        return
    parcel = AcquisitionParcel.all_objects.filter(pk=parcel_id).first()
    if parcel is not None:
        parcel.recompute_status()


PARCEL_FK_MODELS = (
    ParcelSurvey,
    Valuation,
    DeliberationResult,
    Objection,
    Consignment,
    Compensation,
    RightsRelease,
)


def _parcel_related_changed(sender, instance, **kwargs):
    _refresh(getattr(instance, "parcel_id", None))


for _model in PARCEL_FK_MODELS:
    post_save.connect(_parcel_related_changed, sender=_model, weak=False)
    post_delete.connect(_parcel_related_changed, sender=_model, weak=False)


@receiver([post_save, post_delete], sender=CompensationPayment)
def _payment_changed(sender, instance, **kwargs):
    compensation = Compensation.objects.filter(pk=instance.compensation_id).first()
    if compensation is None:
        return
    _refresh(compensation.parcel_id)


@receiver([post_save, post_delete], sender=Announcement)
def _announcement_changed(sender, instance, **kwargs):
    for parcel in AcquisitionParcel.objects.filter(project_id=instance.project_id):
        parcel.recompute_status()


@receiver(post_save, sender=AcquisitionParcel)
def _parcel_saved(sender, instance, **kwargs):
    instance.recompute_status()


@receiver(m2m_changed, sender=Handover.parcels.through)
def _handover_parcels_changed(sender, instance, action, pk_set, **kwargs):
    if action not in ("post_add", "post_remove", "post_clear"):
        return
    if isinstance(instance, Handover):
        ids = pk_set or set()
        if action == "post_clear":
            ids = set(
                AcquisitionParcel.objects.filter(
                    project_id=instance.project_id
                ).values_list("pk", flat=True)
            )
        for parcel_id in ids:
            _refresh(parcel_id)
    else:
        _refresh(instance.pk)


@receiver(post_delete, sender=Handover)
def _handover_deleted(sender, instance, **kwargs):
    for parcel in AcquisitionParcel.objects.filter(project_id=instance.project_id):
        parcel.recompute_status()


@receiver([post_save, post_delete], sender=CompensationPayment)
def _payment_updates_compensation_status(sender, instance, **kwargs):
    from pengadaan.enums import CompensationStatus

    compensation = Compensation.objects.filter(pk=instance.compensation_id).first()
    if compensation is None:
        return
    fully_paid = (
        compensation.amount > 0 and compensation.paid_amount >= compensation.amount
    )
    if fully_paid and compensation.status != CompensationStatus.PAID:
        Compensation.objects.filter(pk=compensation.pk).update(
            status=CompensationStatus.PAID
        )
        _refresh(compensation.parcel_id)
    elif not fully_paid and compensation.status == CompensationStatus.PAID:
        Compensation.objects.filter(pk=compensation.pk).update(
            status=CompensationStatus.VALIDATED
        )
        _refresh(compensation.parcel_id)
