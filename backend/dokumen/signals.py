"""Pemanfaatan lahan dibuat dan disesuaikan otomatis dari alokasi lahan dan
permintaan investasi (sewa/kerja sama) yang selesai."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from alokasi.models import Allocation, InvestmentRequest
from dokumen import services


@receiver(post_save, sender=Allocation, dispatch_uid="dokumen_allocation_land_use")
def allocation_saved(sender, instance, raw=False, **kwargs):
    if raw:
        return
    services.sync_from_allocation(instance)


@receiver(
    post_save, sender=InvestmentRequest, dispatch_uid="dokumen_investment_land_use"
)
def investment_saved(sender, instance, raw=False, **kwargs):
    if raw:
        return
    services.sync_from_investment(instance)
