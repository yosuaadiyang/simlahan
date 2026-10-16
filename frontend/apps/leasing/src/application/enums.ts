export const ApplicantInfoCheckTypes = {
  TRADE_REGISTER: "trade_register",
  CREDITWORTHINESS: "creditworthiness",
  PENSION_CONTRIBUTIONS: "pension_contributions",
  VAT_REGISTER: "vat_register",
  ADVANCE_PAYMENT: "advance_payment",
  TAX_DEBT: "tax_debt",
  EMPLOYER_REGISTER: "employer_register",
};
export const ApplicantInfoCheckStatuses = {
  CHECKED: "checked",
  NOT_CHECKED: "not_checked",
  NOT_NEEDED: "not_needed",
  FURTHER_ACTION: "further_action",
};
export const ApplicantInfoCheckFieldPaths = {
  PREPARER: "preparer",
  STATE: "state",
  MARK_ALL: "mark_all",
  COMMENT: "comment",
};
export const ApplicantInfoCheckFieldTitles = {
  PREPARER: "Pemeriksa",
  STATE: "Status",
  MARK_ALL: "Tandai pada semua permohonan pemohon",
  COMMENT: "Komentar",
};
export const ApplicantInfoCheckExternalTypes = {
  CREDIT_INQUIRY: "credit_inquiry",
  TRADE_REGISTER_INQUIRY: "trade_register_inquiry",
};
export const ApplicantTypes = {
  PERSON: "person",
  COMPANY: "company",
  BOTH: "both",
  UNKNOWN: null,
  // UI only states
  UNSELECTED: "unselected",
  NOT_APPLICABLE: "No.",
};
export const TargetIdentifierTypes = {
  PLAN_UNIT: "plan_unit",
  CUSTOM_DETAILED_PLAN: "custom_detailed_plan",
};
