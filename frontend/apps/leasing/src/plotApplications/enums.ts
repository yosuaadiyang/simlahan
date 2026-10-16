export const ApplicationFieldPaths = {
  PLOTSEARCH: "plotsearch",
};
export const PlotApplicationTargetInfoCheckFieldPaths = {
  RESERVED: "target_statuses.child.children.reserved",
  NEGOTIATION_DATE: "target_statuses.child.children.counsel_date",
  SHARE_OF_RENT_INDICATOR:
    "target_statuses.child.children.share_of_rental_indicator",
  SHARE_OF_RENT_DENOMINATOR:
    "target_statuses.child.children.share_of_rental_denominator",
  ADDED_TARGET_TO_APPLICANT:
    "target_statuses.child.children.added_target_to_applicant",
  DECLINE_REASON: "target_statuses.child.children.decline_reason",
  PROPOSED_MANAGEMENTS: "target_statuses.child.children.proposed_managements",
  RESERVATION_CONDITIONS:
    "target_statuses.child.children.reservation_conditions.child",
  ARGUMENTS: "target_statuses.child.children.arguments",
  MEETING_MEMOS: "target_statuses.child.children.meeting_memos.child.children",
  PROPOSED_MANAGEMENT_TYPE:
    "target_statuses.child.children.proposed_managements.child.children.proposed_management",
  PROPOSED_MANAGEMENT_FINANCING:
    "target_statuses.child.children.proposed_managements.child.children.proposed_financing",
  PROPOSED_MANAGEMENT_HITAS:
    "target_statuses.child.children.proposed_managements.child.children.hitas",
};
export const PlotApplicationTargetInfoCheckFieldTitles = {
  RESERVED: "Diusulkan untuk dicadangkan",
  NEGOTIATION_DATE: "Tanggal negosiasi",
  SHARE_OF_RENT: "Porsi pencadangan",
  SHARE_OF_RENT_INDICATOR: "Pembilang porsi pencadangan",
  SHARE_OF_RENT_DENOMINATOR: "Penyebut porsi pencadangan",
  ADDED_TARGET_TO_APPLICANT: "Objek ditambahkan untuk pemohon",
  DECLINE_REASON: "Alasan penolakan",
  PROPOSED_MANAGEMENTS: "Bentuk pengelolaan dan pembiayaan yang diusulkan",
  RESERVATION_CONDITIONS: "Syarat sewa khusus",
  ARGUMENTS: "Alasan",
  MEETING_MEMOS: "Notulen rapat/negosiasi",
  PROPOSED_MANAGEMENT_TYPE: "Bentuk pengelolaan yang diusulkan",
  PROPOSED_MANAGEMENT_FINANCING: "Bentuk pembiayaan yang diusulkan",
  PROPOSED_MANAGEMENT_HITAS: "HITAS",
  RESERVATION_CONDITION_SINGULAR: "Syarat sewa khusus",
  MEETING_MEMO_NAME: "Nama",
  MEETING_MEMO_UPLOAD_DATE: "Tanggal simpan",
  MEETING_MEMO_UPLOADED_BY: "Pengirim",
};
export const PlotApplicationOpeningRecordPaths = {
  PLOT_SEARCH_TIMESTAMP: "plot_search_opening_time_stamp",
  TIMESTAMP: "opening_record.children.time_stamp",
  CREATED_BY: "opening_record.children.created_by",
  OPENERS: "opening_record.children.openers",
  NOTE: "opening_record.children.note",
};
export const PlotApplicationOpeningRecordLabels = {
  PLOT_SEARCH_TIMESTAMP: "Permohonan dibuka dan berita acara pembukaan dibuat",
  TIMESTAMP: "Permohonan dibuka",
  CREATED_BY: "Penyelenggara kompetisi",
  OPENERS: "Peserta acara pembukaan",
  NOTE: "Catatan",
};
