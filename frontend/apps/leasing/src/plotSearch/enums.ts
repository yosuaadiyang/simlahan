/**
 * PlotSearch field paths enumerable.
 *
 * @type {{}}
 */
export const PlotSearchFieldPaths = {
  BASIC_INFO: "basic_info",
  name: "name",
  PREPARERS: "preparers",
  APPLICATIONS: "applications",
  TYPE: "type",
  SUBTYPE: "subtype",
  START_DATE: "start_date",
  BEGIN_AT: "begin_at",
  CLOCK: "clock",
  END_DATE: "end_date",
  END_AT: "end_at",
  APPLICATIONS_UPDATED_DATE: "Applications_updated_date",
  DECISION: "decision",
  DECISION_TO_LIST: "decision_to_list",
  STAGE: "stage",
  SEARCH_CLASS: "search_class",
};

/**
 * PlotSearch field titles enumerable.
 *
 * @type {{}}
 */
export const PlotSearchFieldTitles = {
  BASIC_INFO: "Data dasar",
  NAME: "Nama pencarian",
  PREPARERS: "Penyiap",
  APPLICATIONS: "Permohonan",
  TYPE: "Jenis pencarian",
  SUBTYPE: "Subjenis pencarian",
  SEARCH_CLASS: "Klasifikasi pencarian",
  START_DATE: "Tgl mulai",
  CLOCK: "Pukul",
  END_DATE: "Tgl akhir",
  APPLICATIONS_UPDATED_DATE: "Permohonan diperbarui",
  DECISION: "Keputusan",
  DECISION_TO_LIST: "Keputusan ke daftar hasil pencarian",
  STAGE: "Tahap pencarian",
  INFO_LINK_DESCRIPTION: "Uraian tautan informasi",
  INFO_LINK_URL: "Tautan informasi",
  INFO_LINK_LANGUAGE: "Bahasa",
  USAGE_DISTRIBUTION: "Distribusi penggunaan",
  USAGE_DISTRIBUTION_BUILD_PERMISSION: "Hak membangun",
  USAGE_DISTRIBUTION_NOTE: "Catatan",
  LEASE_IDENTIFIER: "Pengenal sewa",
  CUSTOM_DETAILED_PLAN_INTENDED_USE: "Peruntukan unit rencana",
  AREA: "Area total",
  ADDRESS: "Alamat",
  DETAILED_PLAN: "Rencana detail",
  DETAILED_PLAN_LATEST_PROCESSING_DATE:
    "Tgl pemrosesan terakhir rencana detail",
  DETAILED_PLAN_LATEST_PROCESSING_DATE_NOTE:
    "Keterangan tgl pemrosesan terakhir rencana detail",
  STATE: "Status unit rencana",
  CUSTOM_DETAILED_PLAN_TYPE: "Jenis unit rencana",
  RENT_BUILD_PERMISSION: "Total hak membangun",
  PRECONSTRUCTION_ESTIMATED_CONSTRUCTION_READINESS_MOMENT:
    "Perkiraan kesiapan konstruksi",
  TARGET_IDENTIFIER: "Pengenal objek",
  TARGET_TYPE: "Jenis objek",
  LEASE_MANAGEMENT: "Bentuk pengelolaan",
  LEASE_FINANCING: "Bentuk pembiayaan",
  LEASE_HITAS: "Skema harga terkendali",
  SECTION_AREA: "Luas bagian",
  PLOT_DIVISION_STATE: "Status pemecahan bidang",
  PLOT_DIVISION_IDENTIFIER: "Pengenal pemecahan bidang",
  PLOT_DIVISION_EFFECTIVE_DATE: "Tgl berlaku pemecahan bidang",
  PLOT_DIVISION_DATE_OF_APPROVAL: "Tgl persetujuan pemecahan bidang",
  PLAN_UNIT_TYPE: "Jenis unit rencana",
  PLAN_UNIT_STATE: "Status unit rencana",
  IN_CONTRACT: "Pada saat kontrak",
  PLAN_UNIT_INTENDED_USE: "Peruntukan unit rencana",
  RESERVATION_RECIPIENT: "Penerima pencadangan yang diusulkan",
  RESERVATION_RECIPIENT_SHARE_OF_RENTAL: "Porsi",
  RESERVATION_IDENTIFIER: "Pengenal pencadangan",
};

/**
 * PlotSearch application field paths enumerable.
 *
 * @type {{}}
 */
export const ApplicationFieldPaths = {
  APPLICATION: "formData",
  NAME: "name",
};

/**
 * PlotSearch field titles enumerable.
 *
 * @type {{}}
 */
export const ApplicationFieldTitles = {
  APPLICATION: "FORMULIR PERMOHONAN",
  APPLICATION_TEMPLATE: "Templat formulir",
  APPLICATION_NAME: "Judul formulir",
};
export const PlotSearchTargetType = {
  SEARCHABLE: "searchable",
  PROCEDURAL: "procedural_reservation",
  DIRECT: "direct_reservation",
};
export const PlotSearchStageTypes = {
  IN_PREPARATION: "in_preparation",
  IN_ACTION: "in_action",
  PROCESSING: "processing",
  DECISION: "decision",
  SETTLED: "settled",
};
export const AreaSearchState = {
  RECEIVED: "received",
  PENDING_INFORMATION: "pending_information",
  IN_ACTION: "in_action",
  SETTLED: "settled",
  REVOKED: "revoked",
  DECLINED: "declined",
};
