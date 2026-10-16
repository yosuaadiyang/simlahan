/**
 * Collection note field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const CollectionNoteFieldPaths = {
  COLLECTION_NOTES: "collection_notes",
  FILE: "file",
  MODIFIED_AT: "modified_at",
  CREATED_AT: "created_at",
  NOTE: "note",
  USER: "user",
  COLLECTION_STAGE: "collection_stage",
  INVOICES: "invoices",
  SENT_DATE: "sent_date",
  INSPECTION_DATE: "inspection_date",
  POSTPONE_DATE: "postpone_date",
  ENTIRE_LEASE: "entire_lease",
};

/**
 * Collection note field titles enumerable.
 * @readonly
 * @enum {string}
 */
export const CollectionNoteFieldTitles = {
  COLLECTION_NOTES: "Catatan",
  MODIFIED_AT: "Diubah",
  CREATED_AT: "Ditambahkan",
  NOTE: "Catatan",
  USER: "Ditambahkan oleh",
  COLLECTION_STAGE: "Tahap penagihan",
  INVOICES: "Tagihan",
  SENT_DATE: "Tanggal kirim",
  INSPECTION_DATE: "Tanggal pengawasan",
  POSTPONE_DATE: "Tanggal penundaan pembayaran",
  ENTIRE_LEASE: "Seluruh sewa",
};

/**
 * Collection note stage enumerable.
 */
export const CollectionStageOptions = {
  RISK_OF_DEMOLITION: "risk_of_demolition",
  RISK_OF_DEMOLITION_AND_LITIGATION: "risk_of_demolition_and_litigation",
  RISK_OF_LITIGATION: "risk_of_litigation",
  RISK_OF_TERMINATION_AND_LITIGATION: "risk_of_termination_and_litigation",
  SIMPLE_PAYMENT_REMINDER: "simple_payment_reminder",
  PAYMENT_DEMAND: "payment_demand",
  PAYMENT_DEFERRAL: "payment_deferral",
  CONTRACT_CHANGE: "contract_change",
  BANKRUPTCY_OR_REORGANIZATION: "bankruptcy_or_reorganization",
  DISTRAINT: "distraint",
  DISTRAINT_NOTICE: "distraint_notice",
  NOTICE: "notice",
  COMPLAINT_OR_OTHER_OBSTRUCTION: "complaint_or_other_obstruction",
};
