import { ContactTypes } from "@/contacts/enums";

export const ApplicantTypeSectionToContactTypeEnum = {
  "yrityksen-tiedot": ContactTypes.BUSINESS,
  "henkilon-tiedot": ContactTypes.PERSON,
};

export const AreaSearchFieldPaths = {
  INTENDED_USE: "intended_use",
  LESSOR: "lessor",
  AUDIT_LOG: "audit_log",
  AREA_SEARCH_STATUS: "area_search_status",
};
export const AreaSearchFieldTitles = {
  INTENDED_USE: "Peruntukan",
  LESSOR: "Pemberi sewa",
  STATE: "Status",
  RECEIVED_DATE: "Waktu kedatangan",
  SETTLED_DATE: "Tgl diputuskan",
  PREPARER: "Petugas",
  RENT_PERIOD: "Masa sewa",
  DESCRIPTION_INTENDED_USE: "Peruntukan",
  DESCRIPTION_AREA: "Uraian area",
  AREA: "Luas",
  PROPERTY_IDENTIFIER: "Pengenal bidang (NIB)",
  DECLINE_REASON: "Alasan penolakan",
  PREPARER_NOTE: "Catatan data pemrosesan",
  STATUS_NOTES: "Catatan petugas",
  AUDIT_LOG: "Riwayat perubahan",
  LEASE: "Sewa",
};

export const ApplicantInfoSectionIdentifiers = {
  PERSON_INFO: "henkilon-tiedot",
  COMPANY_INFO: "yrityksen-tiedot",
  // yhteyshenkilo should be used with regexes or includes method for matching,
  // because it includes a number at the end of the identifier
  // Example: "yhteyshenkilo-1"
  CONTACT_PERSON: "yhteyshenkilo",
  BILL_RECIPIENT: "laskunsaaja",
};

/**
 * Map form answer to contact fields enumerable.
 * @readonly
 * @enum {string}
 */
export const MapFormAnswerFieldsToContactFields = {
  first_name: "etunimi",
  last_name: "Nama belakang",
  name: "nimi",
  c_o: "c_o",
  business_id: "y-tunnus",
  address: "katuosoite",
  postal_code: "postinumero",
  city: "postitoimipaikka",
  country: "maa",
  email: "sahkoposti",
  phone: "puhelinnumero",
  language: "kieli",
  national_identification_number: "henkilotunnus",
  address_protection: "turvakielto",
};

export const MapLanguageNameToCodeEnum = {
  indonesia: "id",
  inggris: "en",
  englanti: "en",
};
