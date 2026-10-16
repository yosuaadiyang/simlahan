/**
 * Infill development compensation field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const InfillDevelopmentCompensationFieldPaths = {
  BASIC_INFO: "basic_info",
  DETAILED_PLAN_IDENTIFIER: "detailed_plan_identifier",
  LEASE_CONTRACT_CHANGE_DATE: "lease_contract_change_date",
  MAP: "map",
  NAME: "name",
  NOTE: "note",
  REFERENCE_NUMBER: "reference_number",
  STATE: "state",
  USER: "user",
};

/**
 * Infill development compensation field titles enumerable.
 * @readonly
 * @enum {string}
 */
export const InfillDevelopmentCompensationFieldTitles = {
  BASIC_INFO: "Data dasar",
  DETAILED_PLAN_IDENTIFIER: "No. rencana detail",
  LEASE_CONTRACT_CHANGE_DATE: "Tgl perubahan kontrak sewa",
  MAP: "Peta",
  NAME: "Nama proyek",
  NOTE: "Catatan",
  REFERENCE_NUMBER: "Nomor agenda",
  STATE: "Tahap negosiasi",
  USER: "Penanggung jawab",
};

/**
 * Infill development compensation leases field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const InfillDevelopmentCompensationLeasesFieldPaths = {
  INFILL_DEVELOPMENT_COMPENSATION_LEASES:
    "infill_development_compensation_leases",
  COMPENSATION_INVESTMENT_AMOUNT:
    "infill_development_compensation_leases.child.children.compensation_investment_amount",
  DISCOUNT_IN_RENT:
    "infill_development_compensation_leases.child.children.discount_in_rent",
  INCREASE_IN_VALUE:
    "infill_development_compensation_leases.child.children.increase_in_value",
  LEASE: "infill_development_compensation_leases.child.children.lease",
  MONETARY_COMPENSATION_AMOUNT:
    "infill_development_compensation_leases.child.children.monetary_compensation_amount",
  NOTE: "infill_development_compensation_leases.child.children.note",
  PAID_DATE: "infill_development_compensation_leases.child.children.paid_date",
  PART_OF_THE_INCREASE_IN_VALUE:
    "infill_development_compensation_leases.child.children.part_of_the_increase_in_value",
  SENT_TO_SAP_DATE:
    "infill_development_compensation_leases.child.children.sent_to_sap_date",
  TOTAL_COMPENSATION:
    "infill_development_compensation_leases.child.children.total_compensation",
  YEAR: "infill_development_compensation_leases.child.children.year",
};

/**
 * Infill development compensation leases field titles enumerable.
 * @readonly
 * @enum {string}
 */
export const InfillDevelopmentCompensationLeasesFieldTitles = {
  INFILL_DEVELOPMENT_COMPENSATION_LEASES: "Sewa",
  COMPENSATION_INVESTMENT_AMOUNT: "Investasi kompensasi",
  DISCOUNT_IN_RENT: "Potongan sewa",
  INCREASE_IN_VALUE: "Kenaikan nilai (PPN 0%)",
  LEASE: "Pengenal sewa",
  MONETARY_COMPENSATION_AMOUNT: "Kompensasi uang",
  NOTE: "Catatan",
  PAID_DATE: "Dibayar",
  PART_OF_THE_INCREASE_IN_VALUE: "Porsi kenaikan nilai",
  SENT_TO_SAP_DATE: "Pembayaran dikirim ke SAP",
  TOTAL_COMPENSATION: "Total kompensasi",
  YEAR: "Perkiraan tahun pembayaran",
};

/**
 * Infill development compensation lease decisions field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const InfillDevelopmentCompensationLeaseDecisionsFieldPaths = {
  DECISIONS: "infill_development_compensation_leases.child.children.decisions",
  DECISION_DATE:
    "infill_development_compensation_leases.child.children.decisions.child.children.decision_date",
  DECISION_MAKER:
    "infill_development_compensation_leases.child.children.decisions.child.children.decision_maker",
  REFERENCE_NUMBER:
    "infill_development_compensation_leases.child.children.decisions.child.children.reference_number",
  SECTION:
    "infill_development_compensation_leases.child.children.decisions.child.children.section",
};

/**
 * Infill development compensation lease decisions field titles enumerable.
 * @readonly
 * @enum {string}
 */
export const InfillDevelopmentCompensationLeaseDecisionsFieldTitles = {
  DECISIONS: "Keputusan kompensasi",
  DECISION_DATE: "Tgl",
  DECISION_MAKER: "Pengambil keputusan",
  REFERENCE_NUMBER: "Nomor agenda",
  SECTION: "Pasal",
};

/**
 * Infill development compensation lease intended uses field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const InfillDevelopmentCompensationLeaseIntendedUsesFieldPaths = {
  INTENDED_USES:
    "infill_development_compensation_leases.child.children.intended_uses",
  AMOUNT_PER_FLOOR_M2:
    "infill_development_compensation_leases.child.children.intended_uses.child.children.amount_per_floor_m2",
  FLOOR_M2:
    "infill_development_compensation_leases.child.children.intended_uses.child.children.floor_m2",
  INTENDED_USE:
    "infill_development_compensation_leases.child.children.intended_uses.child.children.intended_use",
};

/**
 * Infill development compensation lease intended uses field titles enumerable.
 * @readonly
 * @enum {string}
 */
export const InfillDevelopmentCompensationLeaseIntendedUsesFieldTitles = {
  INTENDED_USES: "Peruntukan",
  AMOUNT_PER_FLOOR_M2: "Rp / m² lantai",
  FLOOR_M2: "k-m²",
  INTENDED_USE: "Peruntukan",
};
