/**
 * Invoice note paths enumerable.
 * @readonly
 * @enum {string}
 */
export const InvoiceNoteFieldPaths = {
  ID: "id",
  CREATED_AT: "created_at",
  MODIFIED_AT: "modified_at",
  BILLING_PERIOD_START_DATE: "billing_period_start_date",
  BILLING_PERIOD_END_DATE: "billing_period_end_date",
  NOTES: "notes",
  LEASE: "lease",
};

/**
 * Invoice note titles enumerable.
 * @readonly
 * @enum {string}
 */
export const InvoiceNoteFieldTitles = {
  ID: "Id",
  CREATED_AT: "Dibuat",
  MODIFIED_AT: "Diubah",
  BILLING_PERIOD_START_DATE: "Tgl mulai penagihan",
  BILLING_PERIOD_END_DATE: "Tgl akhir penagihan",
  NOTES: "Pengumuman",
  LEASE: "Pengenal sewa",
};
