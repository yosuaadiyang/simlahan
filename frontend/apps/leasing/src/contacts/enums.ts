/**
 * Contact type enumerable.
 * @readonly
 * @enum {string}
 */
export const ContactTypes = {
  PERSON: "person",
  BUSINESS: "business",
  UNIT: "unit",
  ASSOCIATION: "association",
  OTHER: "other",
} as const;

/**
 * Contact field paths enumerable.
 * @readonly
 * @enum {string}
 */
export const ContactFieldPaths = {
  ACTIVE_LEASES: "contacts_active_leases",
  ADDRESS: "address",
  ADDRESS_PROTECTION: "address_protection",
  AUDIT_LOG: "audit_log",
  BASIC_INFO: "basic_info",
  BUSINESS_ID: "business_id",
  CARE_OF: "care_of",
  CITY: "city",
  COUNTRY: "country",
  ID: "id",
  ELECTRONIC_BILLING_ADDRESS: "electronic_billing_address",
  EMAIL: "email",
  FIRST_NAME: "first_name",
  IS_LESSOR: "is_lessor",
  LANGUAGE: "language",
  LAST_NAME: "last_name",
  NAME: "name",
  NATIONAL_IDENTIFICATION_NUMBER: "national_identification_number",
  NOTE: "note",
  PARTNER_CODE: "partner_code",
  PHONE: "phone",
  POSTAL_CODE: "postal_code",
  SAP_CUSTOMER_NUMBER: "sap_customer_number",
  SERVICE_UNIT: "service_unit",
  TYPE: "type",
};

/**
 * Contact field titles enumerable.
 * @readonly
 * @enum {string}
 */
export const ContactFieldTitles = {
  ACTIVE_LEASES: "Sewa",
  ADDRESS: "Alamat",
  ADDRESS_PROTECTION: "Perlindungan alamat",
  AUDIT_LOG: "Riwayat perubahan",
  BASIC_INFO: "Data dasar",
  BUSINESS_ID: "NPWP",
  CARE_OF: "c/o",
  CITY: "Kota/Kabupaten",
  COUNTRY: "Negara",
  ELECTRONIC_BILLING_ADDRESS: "ID e-faktur",
  EMAIL: "Email",
  FIRST_NAME: "Nama depan",
  ID: "Nomor pelanggan",
  IS_LESSOR: "Pemberi sewa",
  LANGUAGE: "Bahasa",
  LAST_NAME: "Nama belakang",
  NAME: "Nama badan usaha",
  NATIONAL_IDENTIFICATION_NUMBER: "NIK",
  NOTE: "Catatan",
  PARTNER_CODE: "Kode mitra",
  PHONE: "Nomor telepon",
  POSTAL_CODE: "Kode pos",
  SAP_CUSTOMER_NUMBER: "Nomor pelanggan SAP",
  SERVICE_UNIT: "Unit layanan",
  TYPE: "Jenis kontak",
};
