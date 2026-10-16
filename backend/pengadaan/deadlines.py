"""Pemantauan tenggat waktu hukum pengadaan tanah.

Menghasilkan daftar tenggat (batas waktu) beserta statusnya untuk dasbor,
notifikasi email, dan API.
"""

import datetime
from dataclasses import asdict, dataclass

from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

from pengadaan import enums
from pengadaan.models import (
    AcquisitionProject,
    Announcement,
    Consignment,
    DeliberationResult,
    Handover,
    Objection,
    RightsRelease,
    Valuation,
)
from pengadaan.workdays import workdays_between


@dataclass
class Deadline:
    project_id: int
    project_identifier: str
    project_name: str
    kind: str
    title: str
    due_date: datetime.date
    reference: str
    parcel_id: int | None = None
    parcel_number: str | None = None
    workdays_left: int = 0
    state: str = "upcoming"  # upcoming | due_soon | overdue

    def as_dict(self):
        data = asdict(self)
        data["due_date"] = self.due_date.isoformat()
        return data


def _make(project, kind, title, due, reference, parcel=None) -> Deadline | None:
    if due is None:
        return None
    return Deadline(
        project_id=project.id,
        project_identifier=project.identifier,
        project_name=project.name,
        kind=kind,
        title=title,
        due_date=due,
        reference=reference,
        parcel_id=getattr(parcel, "id", None),
        parcel_number=getattr(parcel, "parcel_number", None),
    )


def collect_deadlines(  # noqa: C901
    projects=None, today: datetime.date | None = None, soon_workdays: int = 5
) -> list[Deadline]:
    """Kumpulkan tenggat yang masih terbuka (belum ditindaklanjuti)."""
    today = today or timezone.localdate()
    if projects is None:
        projects = AcquisitionProject.objects.exclude(
            status__in=[enums.ProjectStatus.COMPLETED, enums.ProjectStatus.CANCELLED]
        )
    project_ids = list(projects.values_list("id", flat=True))
    items: list[Deadline] = []

    for project in AcquisitionProject.objects.filter(id__in=project_ids):
        if project.location_decree_date and project.stage in (
            enums.ProjectStage.PREPARATION,
            enums.ProjectStage.IMPLEMENTATION,
        ):
            items.append(
                _make(
                    project,
                    "penlok_expiry",
                    _("Location determination (Penlok) expires"),
                    project.location_decree_expires_on,
                    project.location_decree_number,
                )
            )

    for ann in Announcement.objects.filter(
        project_id__in=project_ids,
        announcement_type=enums.AnnouncementType.INVENTORY,
    ).select_related("project"):
        if ann.objection_deadline and ann.objection_deadline >= today:
            items.append(
                _make(
                    ann.project,
                    "inventory_objection",
                    _("Objection period for inventory results ends"),
                    ann.objection_deadline,
                    ann.document_number,
                )
            )

    # Hasil penilaian sudah diserahkan tetapi belum ada musyawarah untuk bidang tsb.
    for val in Valuation.objects.filter(
        parcel__project_id__in=project_ids,
        status=enums.ValuationStatus.FINAL,
        submitted_on__isnull=False,
        parcel__deliberation_results__isnull=True,
    ).select_related("parcel__project"):
        items.append(
            _make(
                val.parcel.project,
                "deliberation",
                _("Deliberation must be held"),
                val.deliberation_deadline,
                val.report_number,
                val.parcel,
            )
        )

    # Hasil musyawarah "menolak": batas pengajuan keberatan ke PN.
    for res in DeliberationResult.objects.filter(
        parcel__project_id__in=project_ids,
        outcome=enums.DeliberationOutcome.REJECTED,
    ).select_related("parcel__project", "deliberation"):
        if res.parcel.objections.filter(
            objection_type=enums.ObjectionType.COMPENSATION
        ).exists():
            continue
        items.append(
            _make(
                res.parcel.project,
                "compensation_objection",
                _("Last day to file an objection to the district court"),
                res.objection_deadline,
                res.deliberation.minutes_number,
                res.parcel,
            )
        )

    for obj in Objection.objects.filter(project_id__in=project_ids).select_related(
        "project", "parcel"
    ):
        if obj.is_open and obj.decision_deadline:
            items.append(
                _make(
                    obj.project,
                    "court_decision",
                    _("Court/handling body must decide"),
                    obj.decision_deadline,
                    obj.case_number,
                    obj.parcel,
                )
            )
        if (
            obj.appeal_deadline
            and obj.status == enums.ObjectionStatus.REJECTED
            and not obj.appeals.exists()
        ):
            items.append(
                _make(
                    obj.project,
                    "cassation_filing",
                    _("Last day to file cassation"),
                    obj.appeal_deadline,
                    obj.case_number,
                    obj.parcel,
                )
            )

    for con in Consignment.objects.filter(
        parcel__project_id__in=project_ids,
        status=enums.ConsignmentStatus.REQUESTED,
    ).select_related("parcel__project"):
        items.append(
            _make(
                con.parcel.project,
                "consignment_acceptance",
                _("District court must accept the consignment"),
                con.acceptance_deadline,
                con.decree_number,
                con.parcel,
            )
        )

    for rel in RightsRelease.objects.filter(
        parcel__project_id__in=project_ids, parcel__handovers__isnull=True
    ).select_related("parcel__project"):
        items.append(
            _make(
                rel.parcel.project,
                "handover",
                _("Results must be handed over to the requiring agency"),
                rel.handover_deadline,
                rel.minutes_number,
                rel.parcel,
            )
        )

    for hand in (
        Handover.objects.filter(project_id__in=project_ids)
        .filter(Q(registration_applied_on__isnull=True))
        .select_related("project")
    ):
        items.append(
            _make(
                hand.project,
                "registration",
                _("Apply for land rights registration"),
                hand.registration_deadline,
                hand.minutes_number,
            )
        )

    result = []
    for item in items:
        if item is None:
            continue
        item.workdays_left = workdays_between(today, item.due_date)
        if item.due_date < today:
            item.state = "overdue"
        elif item.workdays_left <= soon_workdays:
            item.state = "due_soon"
        result.append(item)
    result.sort(key=lambda d: (d.due_date, d.project_identifier))
    return result
