"""Petugas alokasi bekerja di /admin/, jadi anggota grupnya otomatis berstatus staf."""

from django.contrib.auth import get_user_model
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from utils.group_permissions import UserGroup

ALOKASI_GROUPS = {UserGroup.PETUGAS_ALOKASI, UserGroup.TIM_VERIFIKASI}


@receiver(m2m_changed, sender=get_user_model().groups.through)
def grant_staff_to_allocation_officers(
    sender, instance, action, pk_set, reverse, **kwargs
):
    if action != "post_add" or not pk_set:
        return
    User = get_user_model()
    if reverse:
        # group.user_set.add(...): instance adalah grup, pk_set berisi id pengguna.
        if instance.pk in ALOKASI_GROUPS:
            User.objects.filter(pk__in=pk_set, is_staff=False).update(is_staff=True)
        return
    if ALOKASI_GROUPS.intersection(pk_set) and not instance.is_staff:
        instance.is_staff = True
        instance.save(update_fields=["is_staff"])
