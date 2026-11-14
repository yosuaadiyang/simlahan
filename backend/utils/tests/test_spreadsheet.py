import io
import zipfile
from decimal import Decimal

import pytest

from asetlahan import reports
from operasi.admin import csv_response
from utils.spreadsheet import neutralize_formula, safe_workbook

PAYLOADS = ["=1+1", "+1+cmd", "-2+3+cmd|' /C calc'!A0", "@SUM(1)", "\t=1"]


def _sheet_xml(data: bytes) -> tuple[str, str]:
    with zipfile.ZipFile(io.BytesIO(data)) as book:
        sheet = book.read("xl/worksheets/sheet1.xml").decode()
        strings = book.read("xl/sharedStrings.xml").decode()
    return sheet, strings


@pytest.mark.parametrize("value", PAYLOADS)
def test_neutralize_formula_prefixes_formula_text(value):
    assert neutralize_formula(value) == "'" + value


@pytest.mark.parametrize(
    "value",
    ["Budi", "-5", "+62 812-3456-7890", "1.250,50", "(021) 555-1234", "", None, 7],
)
def test_neutralize_formula_keeps_ordinary_values(value):
    assert neutralize_formula(value) == value


def test_safe_workbook_writes_formula_text_as_text():
    buffer = io.BytesIO()
    workbook = safe_workbook(buffer, {"in_memory": True})
    sheet = workbook.add_worksheet()
    for row, value in enumerate(PAYLOADS + ["https://contoh.invalid"]):
        sheet.write(row, 0, value)
    workbook.close()
    xml, strings = _sheet_xml(buffer.getvalue())
    assert "<f>" not in xml
    assert "hyperlink" not in xml
    assert "=1+1" in strings


def test_asetlahan_report_xlsx_and_csv_neutralize_formulas():
    data = [["=1+1", Decimal("5")], ["-5", Decimal("1")]]
    xml, strings = _sheet_xml(reports.xlsx_bytes("Uji", ["Nama", "Nilai"], data))
    assert "<f>" not in xml and "=1+1" in strings
    text = reports._csv("uji", ["Nama", "Nilai"], data).content.decode()
    assert "'=1+1;" in text
    assert "\n-5;" in text.replace("\r\n", "\n")


def test_operasi_admin_csv_neutralizes_formulas():
    response = csv_response(
        "uji.csv", ["Nama", "Telepon"], [["=HYPERLINK(1)", "+62 812-3456"]]
    )
    text = response.content.decode()
    assert "'=HYPERLINK(1)" in text
    assert "+62 812-3456" in text and "'+62" not in text
