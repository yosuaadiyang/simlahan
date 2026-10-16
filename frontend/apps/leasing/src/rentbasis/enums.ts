/**
 * Rent basis field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const RentBasisFieldPaths = {
  ID: "id",
  BASIC_INFO: "basic_info",
  DETAILED_PLAN_IDENTIFIER: "detailed_plan_identifier",
  END_DATE: "end_date",
  FINANCING: "financing",
  GEOMETRY: "geometry",
  INDEX: "index",
  LEASE_RIGHTS_END_DATE: "lease_rights_end_date",
  MANAGEMENT: "management",
  MAP: "map",
  NOTE: "note",
  PLOT_TYPE: "plot_type",
  START_DATE: "start_date",
};

/**
 * Rent basis field titles enumerable.
 * @readonly
 * @enum {string}
 */
export const RentBasisFieldTitles = {
  IDENTIFIER: "Pengenal prinsip sewa",
  BASIC_INFO: "Data dasar",
  DETAILED_PLAN_IDENTIFIER: "Rencana detail",
  END_DATE: "Tgl akhir",
  FINANCING: "Bentuk pembiayaan",
  GEOMETRY: "Tautan peta",
  INDEX: "Indeks",
  LEASE_RIGHTS_END_DATE: "Hak sewa berakhir",
  MANAGEMENT: "Bentuk pengelolaan",
  MAP: "Peta",
  NOTE: "Catatan",
  PLOT_TYPE: "Jenis kavling",
  START_DATE: "Tgl mulai",
};

/**
 * Rent basis property identifiers field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const RentBasisPropertyIdentifiersFieldPaths = {
  PROPERTY_IDENTIFIERS: "property_identifiers",
  IDENTIFIER: "property_identifiers.child.children.identifier",
};

/**
 * Rent basis property identifiers field titles enumerable.
 * @readonly
 * @enum {string}
 */
export const RentBasisPropertyIdentifiersFieldTitles = {
  PROPERTY_IDENTIFIERS: "Pengenal bidang (NIB)",
  IDENTIFIER: "Pengenal bidang (NIB)",
};

/**
 * Rent basis decisions field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const RentBasisDecisionsFieldPaths = {
  DECISIONS: "decisions",
  DECISION_DATE: "decisions.child.children.decision_date",
  DECISION_MAKER: "decisions.child.children.decision_maker",
  REFERENCE_NUMBER: "decisions.child.children.reference_number",
  SECTION: "decisions.child.children.section",
};

/**
 * Rent basis decisions field titles enumerable.
 * @readonly
 * @enum {string}
 */
export const RentBasisDecisionsFieldTitles = {
  DECISIONS: "Keputusan",
  DECISION_DATE: "Tgl",
  DECISION_MAKER: "Pengambil keputusan",
  REFERENCE_NUMBER: "Nomor agenda",
  SECTION: "Pasal",
};

/**
 * Rent basis rent rates field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const RentBasisRentRatesFieldPaths = {
  RENT_RATES: "rent_rates",
  AMOUNT: "rent_rates.child.children.amount",
  AREA_UNIT: "rent_rates.child.children.area_unit",
  BUILD_PERMISSION_TYPE: "rent_rates.child.children.build_permission_type",
};

/**
 * Rent basis rent rates field titles enumerable.
 * @readonly
 * @enum {string}
 */
export const RentBasisRentRatesFieldTitles = {
  RENT_RATES: "Harga",
  AMOUNT: "Rupiah",
  AREA_UNIT: "Satuan",
  BUILD_PERMISSION_TYPE: "Peruntukan utama",
};
