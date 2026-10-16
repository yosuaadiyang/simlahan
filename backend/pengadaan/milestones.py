"""Templat langkah kerja pengadaan tanah per tahapan (PP 19/2021 jo. PP 39/2023)."""

from django.utils.translation import gettext_lazy as _

from pengadaan.enums import AcquisitionType, ProjectStage

S = ProjectStage

# (stage, code, title, legal basis)
PUBLIC_INTEREST_TEMPLATE = [
    (
        S.PLANNING,
        "dppt",
        _("Prepare the land acquisition planning document (DPPT)"),
        "UU 2/2012 Ps. 14–15",
    ),
    (S.PLANNING, "dppt_submit", _("Submit DPPT to the governor"), "PP 19/2021"),
    (S.PREPARATION, "prep_team", _("Form the preparation team"), "PP 19/2021"),
    (
        S.PREPARATION,
        "notification",
        _("Notify the development plan"),
        "UU 2/2012 Ps. 18",
    ),
    (
        S.PREPARATION,
        "initial_data",
        _("Initial data collection of the location"),
        "UU 2/2012 Ps. 18",
    ),
    (
        S.PREPARATION,
        "public_consultation",
        _("Public consultation"),
        "UU 2/2012 Ps. 19",
    ),
    (
        S.PREPARATION,
        "objection_handling",
        _("Handle objections to the location plan"),
        "UU 2/2012 Ps. 21",
    ),
    (
        S.PREPARATION,
        "penlok",
        _("Location determination (Penlok)"),
        "UU 2/2012 Ps. 19 & 22",
    ),
    (
        S.PREPARATION,
        "penlok_announcement",
        _("Announce the location determination"),
        "UU 2/2012 Ps. 26",
    ),
    (
        S.IMPLEMENTATION,
        "exec_prep",
        _("Prepare implementation and form task forces"),
        "PP 19/2021",
    ),
    (
        S.IMPLEMENTATION,
        "inventory",
        _("Inventory and identification of parcels and parties"),
        "UU 2/2012 Ps. 27–28",
    ),
    (
        S.IMPLEMENTATION,
        "inventory_announcement",
        _("Announce parcel map and nominative list"),
        "UU 2/2012 Ps. 29",
    ),
    (
        S.IMPLEMENTATION,
        "inventory_verification",
        _("Verify and correct inventory results"),
        "UU 2/2012 Ps. 30",
    ),
    (
        S.IMPLEMENTATION,
        "appraiser",
        _("Appoint the public appraiser (KJPP)"),
        "UU 2/2012 Ps. 31",
    ),
    (
        S.IMPLEMENTATION,
        "valuation",
        _("Valuation of compensation"),
        "UU 2/2012 Ps. 32–34",
    ),
    (
        S.IMPLEMENTATION,
        "deliberation",
        _("Deliberation on the form and amount of compensation"),
        "UU 2/2012 Ps. 37",
    ),
    (
        S.IMPLEMENTATION,
        "objections",
        _("Settle objections in the district court"),
        "UU 2/2012 Ps. 38",
    ),
    (
        S.IMPLEMENTATION,
        "validation",
        _("Validate compensation recipients"),
        "PP 19/2021",
    ),
    (S.IMPLEMENTATION, "payment", _("Provide compensation"), "UU 2/2012 Ps. 40–41"),
    (
        S.IMPLEMENTATION,
        "consignment",
        _("Consign compensation to the district court (if needed)"),
        "UU 2/2012 Ps. 42",
    ),
    (S.IMPLEMENTATION, "release", _("Release of rights"), "UU 2/2012 Ps. 43–45"),
    (
        S.HANDOVER,
        "handover",
        _("Hand over results to the agency requiring the land"),
        "UU 2/2012 Ps. 48",
    ),
    (
        S.HANDOVER,
        "registration",
        _("Apply for land rights registration/certification"),
        "PP 19/2021",
    ),
    (S.HANDOVER, "monitoring", _("Monitoring and evaluation"), "UU 2/2012 Ps. 47"),
]

SMALL_SCALE_TEMPLATE = [
    (S.PLANNING, "plan", _("Prepare the acquisition plan and location"), "PP 19/2021"),
    (S.PREPARATION, "spatial", _("Confirm conformity with spatial plan"), "PP 19/2021"),
    (S.IMPLEMENTATION, "inventory", _("Inventory and identification"), "PP 19/2021"),
    (S.IMPLEMENTATION, "valuation", _("Valuation by appraiser"), "PP 19/2021"),
    (
        S.IMPLEMENTATION,
        "deliberation",
        _("Deliberation / direct agreement"),
        "PP 19/2021",
    ),
    (S.IMPLEMENTATION, "payment", _("Payment and release of rights"), "PP 19/2021"),
    (
        S.HANDOVER,
        "registration",
        _("Register land rights in the name of the agency"),
        "PP 19/2021",
    ),
]

PRIVATE_TEMPLATE = [
    (S.PLANNING, "plan", _("Define land requirement and budget"), ""),
    (S.PLANNING, "permits", _("Check spatial suitability (KKPR) and permits"), ""),
    (S.PREPARATION, "socialization", _("Socialize the plan to landowners"), ""),
    (S.IMPLEMENTATION, "inventory", _("Inventory parcels and verify rights"), ""),
    (S.IMPLEMENTATION, "valuation", _("Price appraisal"), ""),
    (S.IMPLEMENTATION, "negotiation", _("Price negotiation"), ""),
    (
        S.IMPLEMENTATION,
        "deed",
        _("Sale and purchase / release deed before PPAT/notary"),
        "",
    ),
    (S.IMPLEMENTATION, "tax", _("Settle BPHTB and income tax"), ""),
    (S.HANDOVER, "registration", _("Transfer of title at the land office"), ""),
]

TEMPLATES = {
    AcquisitionType.PUBLIC_INTEREST: PUBLIC_INTEREST_TEMPLATE,
    AcquisitionType.SMALL_SCALE: SMALL_SCALE_TEMPLATE,
    AcquisitionType.PRIVATE: PRIVATE_TEMPLATE,
}


def create_default_milestones(project) -> None:
    from pengadaan.models import AcquisitionMilestone

    if project.milestones.exists():
        return
    template = TEMPLATES.get(project.acquisition_type, PUBLIC_INTEREST_TEMPLATE)
    AcquisitionMilestone.objects.bulk_create(
        [
            AcquisitionMilestone(
                project=project,
                stage=stage,
                code=code,
                sequence=(index + 1) * 10,
                title=str(title),
                legal_basis=basis,
            )
            for index, (stage, code, title, basis) in enumerate(template)
        ]
    )
