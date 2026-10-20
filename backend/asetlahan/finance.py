"""Keuangan lahan: jurnal ekspor ERP dan buku besar gabungan lintas modul.

Format jurnal berpasangan (debit/kredit) dengan kolom umum yang dapat
dipetakan ke impor jurnal SAP, Microsoft Dynamics NAV/Navision, atau Tally.
"""

import datetime
from dataclasses import dataclass
from decimal import Decimal

from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.text import slugify

from asetlahan import enums, scope

ZERO = Decimal(0)

T = enums.TransactionType

# Akun bawaan per jenis transaksi bila kode akun tidak diisi.
DEFAULT_ACCOUNTS = {
    T.PURCHASE: "1301",
    T.SALE: "4201",
    T.LEASE_INCOME: "4101",
    T.LEASE_PAYMENT: "5101",
    T.COMPENSATION: "1302",
    T.RESETTLEMENT: "5201",
    T.TAX: "5301",
    T.SURVEY: "5401",
    T.LEGAL: "5501",
    T.OTHER_EXPENSE: "5901",
    T.OTHER_INCOME: "4901",
}

JOURNAL_HEADERS = [
    "Tanggal",
    "Nomor bukti",
    "Kode akun",
    "Pusat biaya",
    "Debit",
    "Kredit",
    "Uraian",
    "Referensi",
    "Kode aset",
    "Pihak",
]


def journal_rows(queryset) -> list[list]:
    """Dua baris jurnal per transaksi: akun transaksi dan akun kas/bank."""
    from asetlahan.models import ModuleSettings

    cash = ModuleSettings.load().cash_account_code
    rows = []
    for trx in queryset.select_related("asset").order_by("date", "id"):
        account = trx.account_code or DEFAULT_ACCOUNTS.get(trx.transaction_type, "")
        amount = trx.amount
        description = trx.description or trx.get_transaction_type_display()
        common = [trx.date.isoformat(), trx.number]
        tail = [
            description,
            trx.reference,
            trx.asset.code if trx.asset_id else "",
            trx.counterparty,
        ]
        if trx.is_income:
            rows.append(common + [cash, trx.cost_center, amount, ZERO] + tail)
            rows.append(common + [account, trx.cost_center, ZERO, amount] + tail)
        else:
            rows.append(common + [account, trx.cost_center, amount, ZERO] + tail)
            rows.append(common + [cash, trx.cost_center, ZERO, amount] + tail)
    return rows


def erp_export(rows, fmt: str, headers=None, title: str = "Jurnal ERP"):
    from asetlahan import reports

    headers = headers or JOURNAL_HEADERS
    filename = f"{slugify(title)}-{timezone.localtime():%Y%m%d-%H%M}"
    if fmt == "csv":
        return reports._csv(filename, headers, rows)
    return reports._xlsx(filename, title, headers, rows)


@dataclass
class LedgerEntry:
    date: datetime.date
    source: str
    number: str
    description: str
    party: str
    income: Decimal
    expense: Decimal
    url: str = ""


def _admin_url(name: str, pk) -> str:
    try:
        return reverse(name, args=[pk])
    except NoReverseMatch:
        return ""


def _land_transactions(user, start, end):
    from asetlahan.models import LandTransaction

    queryset = scope.scoped(LandTransaction.objects.select_related("asset"), user)
    if start:
        queryset = queryset.filter(date__gte=start)
    if end:
        queryset = queryset.filter(date__lte=end)
    for trx in queryset:
        amount = Decimal(trx.amount)
        yield LedgerEntry(
            date=trx.date,
            source="Aset lahan",
            number=trx.number,
            description=trx.description or trx.get_transaction_type_display(),
            party=trx.counterparty,
            income=amount if trx.is_income else Decimal(0),
            expense=Decimal(0) if trx.is_income else amount,
            url=_admin_url("admin:asetlahan_landtransaction_change", trx.pk),
        )


def _compensation_payments(start, end):
    from pengadaan.models import CompensationPayment

    queryset = CompensationPayment.objects.select_related(
        "compensation__parcel__project"
    )
    if start:
        queryset = queryset.filter(paid_on__gte=start)
    if end:
        queryset = queryset.filter(paid_on__lte=end)
    for payment in queryset:
        parcel = payment.compensation.parcel
        yield LedgerEntry(
            date=payment.paid_on,
            source="Pengadaan tanah",
            number=payment.bank_reference or f"GK-{payment.pk}",
            description=f"Ganti kerugian {parcel.project.identifier} bidang {parcel.parcel_number}",
            party=payment.recipient_name,
            income=Decimal(0),
            expense=Decimal(payment.amount),
            url=_admin_url("admin:pengadaan_compensationpayment_change", payment.pk),
        )


def _allocation_invoices(start, end):
    from alokasi.enums import InvoiceStatus
    from alokasi.models import Invoice

    queryset = Invoice.objects.filter(
        status=InvoiceStatus.PAID, paid_at__isnull=False
    ).select_related("application__applicant")
    if start:
        queryset = queryset.filter(paid_at__date__gte=start)
    if end:
        queryset = queryset.filter(paid_at__date__lte=end)
    for invoice in queryset:
        yield LedgerEntry(
            date=timezone.localtime(invoice.paid_at).date(),
            source="Alokasi lahan",
            number=invoice.number,
            description=invoice.description,
            party=invoice.application.applicant.name,
            income=Decimal(invoice.amount),
            expense=Decimal(0),
            url=_admin_url("admin:alokasi_invoice_change", invoice.pk),
        )


def ledger(user, start=None, end=None) -> dict:
    """Buku besar gabungan: transaksi aset, pembayaran ganti kerugian, tagihan alokasi lunas."""
    entries: list[LedgerEntry] = []
    if user.has_perm("asetlahan.view_landtransaction"):
        entries.extend(_land_transactions(user, start, end))
    if user.has_perm("pengadaan.view_compensationpayment"):
        entries.extend(_compensation_payments(start, end))
    if user.has_perm("alokasi.view_invoice"):
        entries.extend(_allocation_invoices(start, end))
    entries.sort(key=lambda e: (e.date, e.source, e.number))
    income = sum((e.income for e in entries), Decimal(0))
    expense = sum((e.expense for e in entries), Decimal(0))
    by_source: dict[str, dict] = {}
    for entry in entries:
        bucket = by_source.setdefault(
            entry.source, {"income": Decimal(0), "expense": Decimal(0), "count": 0}
        )
        bucket["income"] += entry.income
        bucket["expense"] += entry.expense
        bucket["count"] += 1
    return {
        "entries": entries,
        "income": income,
        "expense": expense,
        "net": income - expense,
        "by_source": by_source,
    }


LEDGER_HEADERS = [
    "Tanggal",
    "Sumber",
    "Nomor",
    "Uraian",
    "Pihak",
    "Penerimaan",
    "Pengeluaran",
]


def ledger_rows(entries) -> list[list]:
    return [
        [
            e.date.isoformat(),
            e.source,
            e.number,
            e.description,
            e.party,
            e.income,
            e.expense,
        ]
        for e in entries
    ]
