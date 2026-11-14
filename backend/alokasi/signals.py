"""Administrator serta petugas alokasi, aset lahan dan pusat komando bekerja di
/admin/, jadi anggota grupnya otomatis berstatus staf.

Sebaliknya, pengguna yang dikeluarkan dari grup panel admin terakhirnya kehilangan
status staf sehingga tidak dapat lagi masuk ke /admin/ dengan sisa izinnya.
"""

from django.contrib.auth import get_user_model
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from utils.group_permissions import ADMIN_PANEL_GROUPS


def _revoke_staff_without_panel_group(user_ids) -> None:
    User = get_user_model()
    (
        User.objects.filter(pk__in=user_ids, is_staff=True, is_superuser=False)
        .exclude(groups__in=ADMIN_PANEL_GROUPS)
        .update(is_staff=False)
    )


def _before_clear(instance, reverse) -> None:
    # Catat siapa yang terdampak sebelum keanggotaan dihapus.
    if reverse:
        instance._panel_users_before_clear = (
            list(instance.user_set.values_list("pk", flat=True))
            if instance.pk in ADMIN_PANEL_GROUPS
            else []
        )
    else:
        instance._had_panel_group = instance.groups.filter(
            pk__in=ADMIN_PANEL_GROUPS
        ).exists()


def _after_clear(instance, reverse) -> None:
    if reverse:
        _revoke_staff_without_panel_group(
            getattr(instance, "_panel_users_before_clear", [])
        )
    elif getattr(instance, "_had_panel_group", False):
        _revoke_staff_without_panel_group([instance.pk])
        instance.refresh_from_db(fields=["is_staff"])


def _after_remove(instance, reverse, pk_set) -> None:
    if reverse:
        if instance.pk in ADMIN_PANEL_GROUPS:
            _revoke_staff_without_panel_group(pk_set)
    elif ADMIN_PANEL_GROUPS.intersection(pk_set):
        _revoke_staff_without_panel_group([instance.pk])
        instance.refresh_from_db(fields=["is_staff"])


def _after_add(instance, reverse, pk_set) -> None:
    if reverse:
        # group.user_set.add(...): instance adalah grup, pk_set berisi id pengguna.
        if instance.pk in ADMIN_PANEL_GROUPS:
            get_user_model().objects.filter(pk__in=pk_set, is_staff=False).update(
                is_staff=True
            )
        return
    if ADMIN_PANEL_GROUPS.intersection(pk_set) and not instance.is_staff:
        instance.is_staff = True
        instance.save(update_fields=["is_staff"])


@receiver(m2m_changed, sender=get_user_model().groups.through)
def grant_staff_to_allocation_officers(
    sender, instance, action, pk_set, reverse, **kwargs
):
    if action == "pre_clear":
        _before_clear(instance, reverse)
    elif action == "post_clear":
        _after_clear(instance, reverse)
    elif action == "post_remove" and pk_set:
        _after_remove(instance, reverse, pk_set)
    elif action == "post_add" and pk_set:
        _after_add(instance, reverse, pk_set)


@receiver(post_save, sender=get_user_model())
def close_email_activation_once_active(sender, instance, created, **kwargs):
    """Akun pemohon yang pernah aktif tidak bisa diaktifkan ulang lewat surel
    setelah dinonaktifkan petugas (jalur mana pun: admin pengguna, aksi admin,
    tautan aktivasi)."""
    if kwargs.get("raw") or not instance.is_active:
        return
    update_fields = kwargs.get("update_fields")
    if update_fields is not None and "is_active" not in update_fields:
        return  # mis. last_login saat masuk: status aktif tidak berubah
    from alokasi.models import Applicant

    Applicant.objects.filter(user_id=instance.pk, email_activation_closed=False).update(
        email_activation_closed=True
    )
