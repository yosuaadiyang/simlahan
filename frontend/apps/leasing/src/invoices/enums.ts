/**
 * Invoice state enumerable.
 * @readonly
 * @enum {string}
 */
export const InvoiceState = {
  OPEN: "open",
  PAID: "paid",
  REFUNDED: "refunded",
};

/**
 * Invoice type enumerable.
 * @readonly
 * @enum {string}
 */
export const InvoiceType = {
  CHARGE: "charge",
  CREDIT_NOTE: "credit_note",
};

/**
 * Receivable type enumerable
 * @readonly
 * @enum {number}
 */
export const ReceivableTypes = {
  INTEREST: 2,
  OTHER: 3,
  RENTAL: 1,
};

/**
 * Invoice field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const InvoiceFieldPaths = {
  ADJUSTED_DUE_DATE: "adjusted_due_date",
  BILLED_AMOUNT: "billed_amount",
  BILLING_PERIOD: "billing_period",
  BILLING_PERIOD_END_DATE: "billing_period_end_date",
  BILLING_PERIOD_START_DATE: "billing_period_start_date",
  COLLECTION_CHARGE: "collection_charge",
  CREDIT_INVOICES: "credit_invoices",
  CREDITED_INVOICE: "credited_invoice",
  DELIVERY_METHOD: "delivery_method",
  DUE_DATE: "due_date",
  INTEREST_INVOICE_FOR: "interest_invoice_for",
  INVOICING_DATE: "invoicing_date",
  INVOICESET: "invoiceset",
  LEASE: "lease",
  NOTES: "notes",
  NUMBER: "number",
  OUTSTANDING_AMOUNT: "outstanding_amount",
  PAYMENT_NOTIFICATION_DATE: "payment_notification_date",
  PAYMENT_NOTIFICATION_CATALOG_DATE: "payment_notification_catalog_date",
  POSTPONE_DATE: "postpone_date",
  RECIPIENT: "recipient",
  SAP_ID: "sap_id",
  SENT_TO_SAP_AT: "sent_to_sap_at",
  SHARE: "share",
  STATE: "state",
  TYPE: "type",
  TOTAL_AMOUNT: "total_amount",
};

/**
 * Invoice field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const InvoiceFieldTitles = {
  ADJUSTED_DUE_DATE: "Jatuh tempo diubah",
  BILLED_AMOUNT: "Jumlah ditagih",
  BILLING_PERIOD: "Periode tagihan",
  BILLING_PERIOD_END_DATE: "Periode tagihan tgl akhir",
  BILLING_PERIOD_START_DATE: "Periode tagihan tgl mulai",
  COLLECTION_CHARGE: "Biaya penagihan",
  CREDIT_INVOICES: "Nota kredit",
  CREDITED_INVOICE: "Tagihan yang dikreditkan",
  DELIVERY_METHOD: "Tagihan elektronik atau kertas",
  DUE_DATE: "Jatuh tempo",
  INTEREST_INVOICE_FOR: "Tagihan bunga untuk tagihan",
  INVOICING_DATE: "Tgl penagihan",
  INVOICESET: "Kelompok tagihan",
  LEASE: "Sewa",
  NOTES: "Pengumuman",
  NUMBER: "Nomor tagihan",
  OUTSTANDING_AMOUNT: "Jumlah belum dibayar",
  PAYMENT_NOTIFICATION_DATE: "Tgl pemberitahuan pembayaran",
  PAYMENT_NOTIFICATION_CATALOG_DATE: "Daftar pemberitahuan pembayaran",
  POSTPONE_DATE: "Tgl penundaan",
  RECIPIENT: "Penerima tagihan",
  SAP_ID: "Nomor SAP",
  SENT_TO_SAP_AT: "Dikirim ke SAP",
  SHARE: "Porsi tagihan",
  STATE: "Status tagihan",
  TYPE: "Jenis tagihan",
  TOTAL_AMOUNT: "Pokok tagihan",
};

/**
 * Invoice credit invoices field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const InvoiceCreditInvoicesFieldPaths = {
  CREDIT_INVOICES: "credit_invoices",
  DUE_DATE: "credit_invoices.child.children.due_date",
  NUMBER: "credit_invoices.child.children.number",
  TOTAL_AMOUNT: "credit_invoices.child.children.total_amount",
};

/**
 * Invoice credit invoices field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const InvoiceCreditInvoicesFieldTitles = {
  CREDIT_INVOICES: "Nota kredit",
  DUE_DATE: "Jatuh tempo",
  NUMBER: "Nomor tagihan",
  TOTAL_AMOUNT: "Jumlah",
};

/**
 * Invoice interest invoices field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const InvoiceInterestInvoicesFieldPaths = {
  INTEREST_INVOICES: "interest_invoices",
  DUE_DATE: "interest_invoices.child.children.due_date",
  NUMBER: "interest_invoices.child.children.number",
  TOTAL_AMOUNT: "interest_invoices.child.children.total_amount",
};

/**
 * Invoice interest invoices field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const InvoiceInterestInvoicesFieldTitles = {
  INTEREST_INVOICES: "Tagihan bunga",
  DUE_DATE: "Jatuh tempo",
  NUMBER: "Nomor tagihan",
  TOTAL_AMOUNT: "Jumlah",
};

/**
 * Invoice payments field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const InvoicePaymentsFieldPaths = {
  PAYMENTS: "payments",
  PAID_AMOUNT: "payments.child.children.paid_amount",
  PAID_DATE: "payments.child.children.paid_date",
};

/**
 * Invoice payments field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const InvoicePaymentsFieldTitles = {
  PAYMENTS: "Pembayaran",
  PAID_AMOUNT: "Jumlah dibayar (tanpa PPN)",
  PAID_DATE: "Tgl dibayar",
};

/**
 * Invoice rows field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const InvoiceRowsFieldPaths = {
  ROWS: "rows",
  AMOUNT: "rows.child.children.amount",
  BILLING_PERIOD_END_DATE: "rows.child.children.billing_period_end_date",
  BILLING_PERIOD_START_DATE: "rows.child.children.billing_period_start_date",
  DESCRIPTION: "rows.child.children.description",
  RECEIVABLE_TYPE: "rows.child.children.receivable_type",
  TENANT: "rows.child.children.tenant",
};

/**
 * Invoice rows field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const InvoiceRowsFieldTitles = {
  ROWS: "Rincian",
  AMOUNT: "Jumlah (tanpa PPN)",
  BILLING_PERIOD_END_DATE: "Tgl akhir periode tagihan",
  BILLING_PERIOD_START_DATE: "Tgl mulai periode tagihan",
  DESCRIPTION: "Keterangan",
  SHARE_BASIS: "Penyebut porsi tagihan",
  RECEIVABLE_TYPE: "Jenis piutang",
  TENANT: "Penyewa",
};
