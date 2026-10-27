"""Siapa boleh melihat apa di modul dokumen.

Petugas memakai izin model (matriks di ``dokumen.permissions``). Pemegang hak
(akun portal) hanya melihat pemanfaatan lahan atas namanya; penerima dokumen
tanda tangan hanya melihat dokumen yang dikirim kepadanya.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db.models import Q

from dokumen import enums


def applicant_of(user):
    if user is None or not user.is_authenticated:
        return None
    return getattr(user, "pemohon", None)


def is_holder(user, land_use) -> bool:
    applicant = applicant_of(user)
    return bool(
        applicant is not None and land_use is not None and land_use.holder_id == applicant.pk
    )


def can_view_land_use(user, land_use) -> bool:
    return user.has_perm("dokumen.view_landuse") or is_holder(user, land_use)


def can_view_record(user, record) -> bool:
    return user.has_perm("dokumen.view_permitrecord") or is_holder(user, record.land_use)


def can_view_signing(user, document) -> bool:
    if not user.is_authenticated:
        return False
    if user.has_perm("dokumen.view_signingdocument"):
        return True
    if document.status == enums.SigningStatus.DRAFT:
        return False
    if document.land_use_id and is_holder(user, document.land_use):
        # Pemegang hak melihat dokumen atas lahannya setelah dikirim.
        return document.status not in (
            enums.SigningStatus.PENDING_APPROVAL,
            enums.SigningStatus.APPROVED,
        )
    return document.recipients.filter(user=user).exists()


def can_request_download(user, *, version=None, signing=None) -> bool:
    if version is not None:
        return can_view_record(user, version.record)
    if signing is not None:
        return (
            signing.status == enums.SigningStatus.COMPLETED
            and bool(signing.final_file)
            and can_view_signing(user, signing)
        )
    return False


def approver_permission(confidentiality: str) -> str:
    if confidentiality == enums.Confidentiality.SECRET:
        return "dokumen.approve_confidential_download"
    return "dokumen.approve_downloadrequest"


def users_with_perm(perm: str):
    """Pengguna aktif yang memiliki izin ``app_label.codename``."""
    app_label, codename = perm.split(".", 1)
    permission = Permission.objects.filter(
        content_type__app_label=app_label, codename=codename
    ).first()
    User = get_user_model()
    query = Q(is_superuser=True)
    if permission is not None:
        query |= Q(user_permissions=permission) | Q(groups__permissions=permission)
    return User.objects.filter(query, is_active=True).exclude(email="").distinct()


def display_name(user) -> str:
    if user is None:
        return ""
    applicant = getattr(user, "pemohon", None)
    if applicant is not None:
        return applicant.name
    getter = getattr(user, "get_display_name", None)
    if callable(getter):
        return getter()
    return user.get_full_name() or user.email or user.get_username()
