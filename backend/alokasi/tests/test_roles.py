"""Batas hak akses tiap peran alokasi lahan."""

from django.contrib.auth.models import Group
from django.urls import reverse

from alokasi import enums, services
from alokasi.models import AllocationSettings, IssuedDocument, VerificationCriterion
from utils.group_permissions import UserGroup

from .conftest import score_all
from .test_workflow import approve_and_pay

S = enums.ApplicationStatus


def test_officer_cannot_change_scoring_rules(client, officer, verifier, seeded):
    """Petugas yang memutuskan permohonan tidak boleh mengubah bobot/ambang nilai."""
    criterion = VerificationCriterion.objects.filter(is_active=True).first()
    for user in (officer, verifier):
        assert not user.has_perm("alokasi.change_verificationcriterion")
        assert not user.has_perm("alokasi.add_verificationcriterion")
        assert not user.has_perm("alokasi.change_allocationsettings")
        assert user.has_perm("alokasi.view_verificationcriterion")
    client.force_login(officer)
    url = reverse("admin:alokasi_verificationcriterion_change", args=[criterion.pk])
    weight = criterion.weight
    client.post(url, {"name": criterion.name, "weight": "99", "is_active": "on"})
    criterion.refresh_from_db()
    assert criterion.weight == weight
    assert (
        client.get(reverse("admin:alokasi_verificationcriterion_add")).status_code
        == 403
    )
    settings_url = reverse("admin:alokasi_allocationsettings_change", args=[1])
    page = client.get(settings_url)
    assert page.status_code == 200
    assert not page.context["has_change_permission"]
    passing = AllocationSettings.load().passing_score
    client.post(settings_url, {"passing_score": "1"})
    assert AllocationSettings.load().passing_score == passing


def test_revision_clears_scores(officer, verifier, filled_application):
    application = filled_application
    services.submit(application, application.applicant.user)
    services.start_verification(application, officer)
    score_all(application, verifier, 90)
    services.refresh_score(application)
    assert application.scores.exists() and application.score is not None
    services.request_revision(application, officer, "Lengkapi NPWP")
    application.refresh_from_db()
    assert not application.scores.exists()
    assert application.score is None


def test_verify_page_warns_after_transfer(
    client, officer, verifier, filled_application, make_applicant, upload_required_docs
):
    application = filled_application
    services.submit(application, application.applicant.user)
    approve_and_pay(application, officer, verifier)
    kpt = application.issued_documents.get(kind="kpt")
    url = reverse("portal:verify_token", args=[kpt.token])
    page = client.get(url).content.decode()
    assert "Dokumen terdaftar dan sah" in page

    recipient = make_applicant(name="PT Penerima")
    transfer = services.create_transfer_application(
        application.applicant, application.allocation, recipient, "Jual beli"
    )
    upload_required_docs(transfer)
    services.submit(transfer, application.applicant.user)
    services.accept_transfer(transfer, recipient, recipient.user)
    approve_and_pay(transfer, officer, verifier)
    iph = IssuedDocument.objects.get(application=transfer, kind="iph")

    page = client.get(url).content.decode()
    assert "hak sudah dialihkan" in page
    assert "Dokumen terdaftar dan sah" not in page
    assert iph.number in page and "PT Penerima" in page
    # Dokumen peralihan terbaru tetap sah.
    page = client.get(reverse("portal:verify_token", args=[iph.token])).content.decode()
    assert "Dokumen terdaftar dan sah" in page


def test_staff_status_follows_panel_groups(make_officer, django_user_model):
    officer = make_officer("lepas", UserGroup.PETUGAS_ALOKASI)
    assert officer.is_staff
    officer.groups.add(Group.objects.get(pk=UserGroup.TIM_VERIFIKASI))
    # Masih anggota grup panel lain: tetap staf.
    officer.groups.remove(Group.objects.get(pk=UserGroup.PETUGAS_ALOKASI))
    officer.refresh_from_db()
    assert officer.is_staff
    officer.groups.remove(Group.objects.get(pk=UserGroup.TIM_VERIFIKASI))
    officer.refresh_from_db()
    assert not officer.is_staff

    # Dikeluarkan lewat sisi grup.
    second = make_officer("lepas2", UserGroup.PETUGAS_ASET)
    Group.objects.get(pk=UserGroup.PETUGAS_ASET).user_set.remove(second)
    second.refresh_from_db()
    assert not second.is_staff

    # Semua grup dihapus sekaligus.
    third = make_officer("lepas3", UserGroup.KOORDINATOR_WILAYAH)
    third.groups.clear()
    third.refresh_from_db()
    assert not third.is_staff

    # Grup dikosongkan.
    fourth = make_officer("lepas4", UserGroup.PETUGAS_LAPANGAN)
    Group.objects.get(pk=UserGroup.PETUGAS_LAPANGAN).user_set.clear()
    fourth.refresh_from_db()
    assert not fourth.is_staff

    # Administrator tetap staf; superuser tidak disentuh.
    admin = make_officer("admin", UserGroup.PAAKAYTTAJA)
    admin.is_staff = True
    admin.save()
    admin.groups.add(Group.objects.get(pk=UserGroup.PETUGAS_ALOKASI))
    admin.groups.remove(Group.objects.get(pk=UserGroup.PETUGAS_ALOKASI))
    admin.refresh_from_db()
    assert admin.is_staff
    root = django_user_model.objects.create_superuser("root", "r@x.id", "x")
    root.groups.add(Group.objects.get(pk=UserGroup.PETUGAS_ALOKASI))
    root.groups.clear()
    root.refresh_from_db()
    assert root.is_staff
