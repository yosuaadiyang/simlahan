/**
 * Lease statistics report field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const LeaseReportsPaths = {
  START_DATE: "lease",
  END_DATE: "lease",
  LEASE_STATE: "lease",
  ONLY_ACTIVE_LEASES: "lease",
};

/**
 * Lease statistics report field titles enumerable.
 * @readonly
 * @enum {string}
 */
export const LeaseReportsTitles = {
  LEASE_STATISTICS_REPORT: "Laporan statistik sewa",
  REPORT_TYPE: "Laporan",
  START_DATE: "Tgl mulai",
  END_DATE: "Tgl akhir",
  START_YEAR: "Tahun mulai",
  END_YEAR: "Tahun berakhir",
  LEASE_STATE: "Jenis",
  ONLY_ACTIVE_LEASES: "Kondisi",
  INVOICE_STATE: "Status tagihan",
  LEASE_TYPE: "Jenis penagihan",
};

/**
 * Lease invoicing confirmation report titles.
 * @readonly
 * @enum {string}
 */
export const LeaseInvoicingReportTitles = {
  TYPE: "Jenis",
  LEASE_ID: "Pengenal sewa",
  START_DATE: "Tgl mulai sewa",
  END_DATE: "Tgl akhir sewa",
  ERROR_MESSAGE: "Teks galat",
  AREA: "Area",
  ADDRESS: "Alamat",
  SUPERVISION_DATE: "Tgl pemeriksaan",
  DESCRIPTION: "Uraian",
  LEASE_TYPE: "Jenis",
  COUNT: "Jumlah",
  TENANT_NAME: "Nama penyewa",
  AREA_IDENTIFIER: "Pengenal bidang (NIB)",
  AREA_SQUARE: "Luas",
  AREA_ADDRESS: "Alamat",
  RENT: "Sewa",
  TOTAL_AMOUNT: "Pokok",
  PAID_DATE: "Tgl dibayar",
  RETURNED_DATE: "Tgl dikembalikan",
  NOTE: "Komentar",
  NUMBER: "Nomor",
  DUE_DATE: "Jatuh tempo",
  BILLED_AMOUNT: "Jumlah ditagih",
  OUTSTANDING_AMOUNT: "Jumlah belum dibayar",
  RECIPIENT_NAME: "Penerima tagihan",
  RECIPIENT_ADDRESS: "Alamat penerima tagihan",
  INVOICE_NUMBER: "Nomor tagihan",
  PAID_AMOUNT: "Jumlah dibayar",
  FILLING_CODE: "Kode arsip",
  STATE: "Status",
  SEND_DATE: "Tgl kirim",
  INVOICE_COUNT: "Jumlah tagihan",
  IS_ESTIMATE: "Perkiraan?",
};

/**
 * Leaseinvoicing report paths
 * @readonly
 * @enum {string}
 */
export const LeaseInvoicingReportPaths = {
  LEASE_ID: "lease_id",
  AREA: "area",
  ADDRESS: "address",
  TYPE: "type",
  SUPERVISION_DATE: "supervision_date",
  DESCRIPTION: "description",
  START_DATE: "start_date",
  END_DATE: "end_date",
  LEASE_TYPE: "lease_type",
  COUNT: "count",
  TENANT_NAME: "tenant_name",
  AREA_IDENTIFIER: "area_identifier",
  AREA_ADDRESS: "area_address",
  RENT: "rent",
  PAID_DATE: "paid_date",
  RETURNED_DATE: "returned_date",
  NOTE: "note",
  NUMBER: "number",
  DUE_DATE: "due_date",
  TOTAL_AMOUNT: "total_amount",
  BILLED_AMOUNT: "billed_amount",
  OUTSTANDING_AMOUNT: "outstanding_amount",
  PAID_AMOUNT: "paid_amount",
  RECIPIENT_NAME: "recipient_name",
  RECIPIENT_ADDRESS: "recipient_address",
  INVOICE_NUMBER: "invoice_number",
  FILLING_CODE: "filling_code",
  STATE: "state",
  SEND_DATE: "send_date",
  INVOICE_COUNT: "invoice_count",
  INVOICE_STATE: "invoice_state",
  IS_ESTIMATE: "is_estimate",
};

/**
 * Lease statistics report value format enumerable
 * @readonly
 * @enum {string}
 */
export const LeaseReportsFormatOptions = {
  AREA: "area",
  BOLD: "bold",
  BOLD_MONEY: "bold_money",
  BOOLEAN: "boolean",
  DATE: "date",
  MONEY: "money",
  PERCENTAGE: "percentage",
  URL: "url",
};

/**
 * Lease statistics report field label enumerable
 * @readonly
 * @enum {string}
 */
export const LeaseReportsFieldLabels = {
  LEASE_IDENTIFIER: "lease_identifier",
  SUBVENTION_EUROS_PER_YEAR: "subvention_euros_per_year",
};
