"""Ekspor Daftar Nominatif (Excel) per proyek."""

import io
from decimal import Decimal

import xlsxwriter
from django.utils import timezone
from django.utils.translation import gettext as _

from pengadaan import enums


def _latest_final_valuation(parcel):
    finals = [
        v for v in parcel.valuations.all() if v.status == enums.ValuationStatus.FINAL
    ]
    return finals[0] if finals else None


def nominative_list_xlsx(project) -> bytes:
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    sheet = workbook.add_worksheet(_("Nominative list")[:31])

    title = workbook.add_format({"bold": True, "font_size": 13})
    header = workbook.add_format(
        {
            "bold": True,
            "bg_color": "#E5E7EB",
            "border": 1,
            "text_wrap": True,
            "valign": "top",
        }
    )
    cell = workbook.add_format({"border": 1, "valign": "top", "text_wrap": True})
    money = workbook.add_format(
        {"border": 1, "num_format": '"Rp" #,##0', "valign": "top"}
    )
    area = workbook.add_format({"border": 1, "num_format": "#,##0.00", "valign": "top"})
    total_fmt = workbook.add_format(
        {"bold": True, "border": 1, "num_format": '"Rp" #,##0', "bg_color": "#F3F4F6"}
    )

    sheet.write(0, 0, _("NOMINATIVE LIST OF LAND ACQUISITION"), title)
    sheet.write(1, 0, f"{project.identifier} — {project.name}")
    sheet.write(
        2,
        0,
        _("Agency requiring the land: %(agency)s")
        % {"agency": project.requiring_agency},
    )
    sheet.write(
        3,
        0,
        _("Printed on %(date)s") % {"date": timezone.localdate().strftime("%d-%m-%Y")},
    )

    columns = [
        (_("No."), 5),
        (_("Parcel number"), 12),
        (_("NIB"), 14),
        (_("Village"), 18),
        (_("Type of right"), 18),
        (_("Certificate / evidence number"), 18),
        (_("Entitled parties"), 30),
        (_("Measured area (m²)"), 13),
        (_("Affected area (m²)"), 13),
        (_("Land use"), 14),
        (_("Buildings"), 22),
        (_("Plants"), 22),
        (_("Valuation (IDR)"), 18),
        (_("Compensation (IDR)"), 18),
        (_("Paid (IDR)"), 18),
        (_("Status"), 18),
    ]
    header_row = 5
    for col, (label, width) in enumerate(columns):
        sheet.write(header_row, col, label, header)
        sheet.set_column(col, col, width)
    sheet.freeze_panes(header_row + 1, 2)

    parcels = (
        project.parcels.select_related("district")
        .prefetch_related("parties", "valuations", "compensations__payments")
        .order_by("parcel_number")
    )
    row = header_row + 1
    totals = {
        "valuation": Decimal("0"),
        "compensation": Decimal("0"),
        "paid": Decimal("0"),
    }
    for index, parcel in enumerate(parcels, start=1):
        valuation = _latest_final_valuation(parcel)
        compensations = [
            c
            for c in parcel.compensations.all()
            if c.status != enums.CompensationStatus.CANCELLED
        ]
        comp_total = sum((c.amount for c in compensations), Decimal("0"))
        paid_total = sum((c.paid_amount for c in compensations), Decimal("0"))
        parties = "\n".join(
            f"{p.name} ({p.get_role_display()}"
            + (f", {p.share_percentage}%" if p.share_percentage is not None else "")
            + ")"
            for p in parcel.parties.all()
        )
        values = [
            (index, cell),
            (parcel.parcel_number, cell),
            (parcel.nib, cell),
            (parcel.village, cell),
            (parcel.get_right_type_display(), cell),
            (parcel.certificate_number, cell),
            (parties, cell),
            (
                (
                    float(parcel.measured_area_m2)
                    if parcel.measured_area_m2 is not None
                    else ""
                ),
                area,
            ),
            (
                (
                    float(parcel.affected_area_m2)
                    if parcel.affected_area_m2 is not None
                    else ""
                ),
                area,
            ),
            (parcel.get_land_use_display(), cell),
            (parcel.building_description, cell),
            (parcel.plants_description, cell),
            (float(valuation.total_value) if valuation else "", money),
            (float(comp_total) if compensations else "", money),
            (float(paid_total) if compensations else "", money),
            (parcel.get_status_display(), cell),
        ]
        for col, (value, fmt) in enumerate(values):
            sheet.write(row, col, value, fmt)
        totals["valuation"] += valuation.total_value if valuation else Decimal("0")
        totals["compensation"] += comp_total
        totals["paid"] += paid_total
        row += 1

    sheet.write(row, 11, _("Total"), total_fmt)
    sheet.write(row, 12, float(totals["valuation"]), total_fmt)
    sheet.write(row, 13, float(totals["compensation"]), total_fmt)
    sheet.write(row, 14, float(totals["paid"]), total_fmt)

    workbook.close()
    return output.getvalue()
