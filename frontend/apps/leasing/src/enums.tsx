import React from "react";
import { DELETE_MODAL_BUTTON_TEXT } from "./util/constants";

/**
 * Table sort order enumerable.
 * @readonly
 * @enum {string}
 */
export const TableSortOrder = {
  ASCENDING: "asc",
  DESCENDING: "desc",
};

/**
 * View modes enumerable.
 * @readonly
 * @enum {string}
 */
export const ViewModes = {
  EDIT: "edit",
  READONLY: "readonly",
};

/**
 * Key code enumerable.
 * @readonly
 * @enum {number}
 */
export const KeyCodes = {
  TAB: 9,
  ENTER: 13,
  ESC: 27,
  SPACE: 32,
  ARROW_LEFT: 37,
  ARROW_UP: 38,
  ARROW_RIGHT: 39,
  ARROW_DOWN: 40,
};

/**
 * Methods enumerable.
 * @readonly
 * @enum {string}
 */
export const Methods = {
  DELETE: "DELETE",
  GET: "GET",
  PATCH: "PATCH",
  POST: "POST",
};

/**
 * Confirmation modal texts
 * @readonly
 * @enum {Object}
 */
export const ConfirmationModalTexts = {
  ARCHIVE_LEASE_AREA: {
    BUTTON: "Arsipkan",
    LABEL: "Yakin ingin mengarsipkan objek?",
    TITLE: "Arsipkan objek",
  },
  ARCHIVE_LEASE_BASIS_OF_RENT: {
    BUTTON: "Arsipkan",
    LABEL: "Yakin ingin mengarsipkan kalkulator sewa?",
    TITLE: "Arsipkan kalkulator sewa",
  },
  CANCEL_CHANGES: {
    BUTTON: "Keluar tanpa menyimpan",
    LABEL: (
      <span>
        Formulir memiliki perubahan yang belum disimpan.
        <br /> Yakin ingin keluar tanpa menyimpan?
      </span>
    ) as React.ReactElement<React.ComponentProps<"span">, "span">,
    TITLE: "Keluar tanpa menyimpan",
  },
  CLOSE_COMMENT_PANEL: {
    BUTTON: "Tutup komentar",
    LABEL: (
      <span>
        Belum semua perubahan disimpan.
        <br /> Yakin ingin menutup komentar?
      </span>
    ) as React.ReactElement<React.ComponentProps<"span">, "span">,
    TITLE: "Tutup komentar",
  },
  COPY_AREAS_TO_CONTRACT: {
    BUTTON: "Salin ke kontrak",
    LABEL:
      "Yakin ingin menyalin bidang tanah dan unit rencana saat ini ke kontrak?",
    TITLE: "Salin ke kontrak",
  },
  CREATE_CONTACT: {
    BUTTON: "Buat kontak",
    LABEL: (
      <span>
        Kontak dengan pengenal ini sudah ada di unit layanan.
        <br />
        Buat kontak baru?
      </span>
    ) as React.ReactElement<React.ComponentProps<"span">, "span">,
    TITLE: "Buat kontak",
  },
  DELETE_ADDRESS: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus alamat?",
    TITLE: "Hapus alamat",
  },
  DELETE_AREA_NOTE: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus catatan area?",
    TITLE: "Hapus catatan area",
  },
  DELETE_ATTACHMENT: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus berkas?",
    TITLE: "Hapus berkas",
  },
  DELETE_BILLING_PERSON: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus penerima tagihan?",
    TITLE: "Hapus penerima tagihan",
  },
  DELETE_COLLATERAL: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus jaminan?",
    TITLE: "Hapus jaminan",
  },
  DELETE_COLLECTION_COURT_DECISIONS: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus putusan pengadilan?",
    TITLE: "Hapus putusan pengadilan",
  },
  DELETE_COLLECTION_LETTER: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus surat penagihan?",
    TITLE: "Hapus surat penagihan",
  },
  DELETE_COMPENSATION: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus kompensasi?",
    TITLE: "Hapus kompensasi",
  },
  DELETE_CONDITION: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus persyaratan?",
    TITLE: "Hapus persyaratan",
  },
  DELETE_CONTRACT: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus kontrak?",
    TITLE: "Hapus kontrak",
  },
  DELETE_CONTRACT_CHANGE: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus perubahan kontrak?",
    TITLE: "Hapus perubahan kontrak",
  },
  DELETE_CONTRACT_RENT: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus sewa kontrak?",
    TITLE: "Hapus sewa kontrak",
  },
  DELETE_DECISION: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus objek?",
    TITLE: "Hapus objek",
  },
  DELETE_CUSTOM_DETAILED_PLAN: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus area lain milik sendiri?",
    TITLE: "Hapus area lain milik sendiri",
  },
  DELETE_INFO_LINKS: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus tautan informasi?",
    TITLE: "Hapus tautan informasi",
  },
  DELETE_SUGGESTION: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus usulan?",
    TITLE: "Hapus usulan",
  },
  DELETE_APPLICANT: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus pemohon?",
    TITLE: "Hapus pemohon",
  },
  DELETE_TARGET: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus objek?",
    TITLE: "Hapus objek",
  },
  DELETE_FIXED_INITIAL_YEAR_RENT: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus sewa tahun awal tetap?",
    TITLE: "Hapus sewa tahun awal tetap",
  },
  DELETE_INFILL_DEVELOPMENT_COMPENSATION_LEASE: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus sewa dari kompensasi pembangunan sisipan?",
    TITLE: "Hapus sewa dari kompensasi pembangunan sisipan",
  },
  DELETE_INFO_LINK: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus tautan informasi?",
    TITLE: "Hapus tautan informasi",
  },
  DELETE_INSPECTION: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus pemeriksaan?",
    TITLE: "Hapus pemeriksaan",
  },
  DELETE_INTENDED_USE: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus peruntukan?",
    TITLE: "Hapus peruntukan",
  },
  DELETE_INVOICE: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus tagihan?",
    TITLE: "Hapus tagihan",
  },
  DELETE_INVOICE_NOTE: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus pembayaran?",
    TITLE: "Hapus pembayaran",
  },
  DELETE_INVOICE_PAYMENT: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus pembayaran?",
    TITLE: "Hapus pembayaran",
  },
  DELETE_INVOICE_ROW: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus baris tagihan?",
    TITLE: "Hapus baris tagihan",
  },
  DELETE_LEASE: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus pengenal sewa?",
    TITLE: "Hapus pengenal sewa",
  },
  DELETE_LEASE_AREA: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus objek?",
    TITLE: "Hapus objek",
  },
  DELETE_LEASE_BASIS_OF_RENT: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus kalkulator sewa?",
    TITLE: "Hapus kalkulator sewa",
  },
  DELETE_LEASEHOLD_TRASFER: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus pengalihan hak sewa?",
    TITLE: "Hapus pengalihan hak sewa",
  },
  DELETE_LITIGANT: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus pihak?",
    TITLE: "Hapus pihak",
  },
  DELETE_MANAGEMENT_SUBVENTION: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus bentuk pengelolaan?",
    TITLE: "Hapus bentuk pengelolaan",
  },
  DELETE_NOTE: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus catatan?",
    TITLE: "Hapus catatan",
  },
  DELETE_OTHER_TENANT: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus penerima tagihan/narahubung?",
    TITLE: "Hapus penerima tagihan/narahubung",
  },
  DELETE_PLAN_UNIT: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus unit rencana?",
    TITLE: "Hapus unit rencana",
  },
  DELETE_PLOT: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus bidang tanah?",
    TITLE: "Hapus bidang tanah",
  },
  DELETE_PROPERTY_IDENTIFIER: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus pengenal bidang?",
    TITLE: "Hapus pengenal bidang",
  },
  DELETE_RELATED_LEASE: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus keterkaitan antarpengenal sewa?",
    TITLE: "Hapus keterkaitan",
  },
  DELETE_RENT: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus sewa?",
    TITLE: "Hapus sewa",
  },
  DELETE_RENT_ADJUSTMENT: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus potongan/kenaikan?",
    TITLE: "Hapus potongan/kenaikan",
  },
  DELETE_RENT_FOR_PERIOD: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus perhitungan sewa?",
    TITLE: "Hapus perhitungan sewa",
  },
  DELETE_RENT_RATE: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus harga?",
    TITLE: "Hapus harga",
  },
  DELETE_RENT_SHARE: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus porsi tagihan?",
    TITLE: "Hapus porsi tagihan",
  },
  DELETE_SUBVENTION: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus subsidi?",
    TITLE: "Hapus subsidi",
  },
  DELETE_TEMPORARY_SUBVENTION: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus potongan sementara?",
    TITLE: "Hapus potongan sementara",
  },
  DELETE_TENANT: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus penyewa?",
    TITLE: "Hapus penyewa",
  },
  DELETE_UI_DATA: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus teks bantuan?",
    TITLE: "Hapus teks bantuan",
  },
  DELETE_USAGE_DISTRIBUTIONS: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus distribusi penggunaan?",
    TITLE: "Hapus distribusi penggunaan",
  },
  RESTORE_CHANGES: {
    BUTTON: "Pulihkan perubahan",
    LABEL:
      "Formulir memiliki perubahan yang belum disimpan. Pulihkan perubahan?",
    TITLE: "Pulihkan perubahan yang belum disimpan",
  },
  SET_RENT_INFO_COMPLETE: {
    BUTTON: "Tandai lengkap",
    LABEL: "Yakin ingin menandai data sewa lengkap?",
    TITLE: "Tandai data sewa lengkap",
  },
  SET_RENT_INFO_UNCOMPLETE: {
    BUTTON: "Tandai belum lengkap",
    LABEL: "Yakin ingin menandai data sewa belum lengkap?",
    TITLE: "Tandai data sewa belum lengkap",
  },
  START_INVOICING: {
    BUTTON: "Mulai penagihan",
    LABEL: "Yakin ingin memulai penagihan?",
    TITLE: "Mulai penagihan",
  },
  STOP_INVOICING: {
    BUTTON: "Hentikan penagihan",
    LABEL: "Yakin ingin menghentikan penagihan?",
    TITLE: "Hentikan penagihan",
  },
  UNARCHIVE_LEASE_AREA: {
    BUTTON: "Keluarkan dari arsip",
    LABEL: "Yakin ingin mengeluarkan objek dari arsip?",
    TITLE: "Keluarkan dari arsip",
  },
  UNARCHIVE_LEASE_BASIS_OF_RENT: {
    BUTTON: "Keluarkan dari arsip",
    LABEL: "Yakin ingin mengeluarkan kalkulator sewa dari arsip?",
    TITLE: "Keluarkan dari arsip",
  },
  DELETE_PLOT_SEARCH: {
    BUTTON: "Hapus pencarian kavling",
    LABEL: "Yakin ingin menghapus pencarian kavling?",
    TITLE: "Hapus pencarian kavling",
  },
  DELETE_PLOT_APPLICATION: {
    BUTTON: "Hapus permohonan kavling",
    LABEL: "Yakin ingin menghapus permohonan kavling?",
    TITLE: "Hapus permohonan kavling",
  },
  DELETE_SECTION_FIELD: {
    BUTTON: "Hapus kolom",
    LABEL: "Yakin ingin menghapus kolom?",
    TITLE: "Hapus kolom",
  },
  DELETE_SECTION_SUBSECTION: {
    BUTTON: "Hapus subbagian",
    LABEL: "Yakin ingin menghapus subbagian?",
    TITLE: "Hapus subbagian",
  },
  DELETE_APPLICATION_TARGET_PROPOSED_MANAGEMENT: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus usulan bentuk pengelolaan dan pembiayaan?",
    TITLE: "Hapus usulan bentuk pengelolaan dan pembiayaan",
  },
  DELETE_APPLICATION_TARGET_CONDITION: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus syarat pencadangan?",
    TITLE: "Hapus syarat pencadangan",
  },
  DELETE_APPLICATION_TARGET_MEETING_MEMO: {
    BUTTON: DELETE_MODAL_BUTTON_TEXT,
    LABEL: "Yakin ingin menghapus notulen rapat?",
    TITLE: "Hapus notulen rapat",
  },
};

/**
 * Redux form field type enumerable.
 * @readonly
 * @enum {string}
 */
export const FieldTypes = {
  ADDRESS: "address",
  AREASEARCH_DISTRICT: "areasearch-district",
  BOOLEAN: "boolean",
  CHOICE: "choice",
  CHECKBOX: "checkbox",
  CHECKBOX_DATE_TIME: "checkbox-date-time",
  CONTACT: "contact",
  DATE: "date",
  DECIMAL: "decimal",
  FIELD: "field",
  INTEGER: "integer",
  INTENDED_USE: "intended_use",
  LEASE: "lease",
  LEASE_TYPE: "lease-type",
  LESSOR: "lessor",
  MULTISELECT: "multiselect",
  RADIO_WITH_FIELD: "radio-with-field",
  REFERENCE_NUMBER: "reference_number",
  SEARCH: "search",
  STRING: "string",
  TEXTAREA: "textarea",
  USER: "user",
  TIME: "time",
  HIDDEN: "hidden",
  FRACTIONAL: "fractional",
} as const;

/**
 * Lease form names enumerable.
 * @readonly
 * @enum {string}
 */
export const FormNames = {
  AREA_SEARCH_SEARCH: "area-search-search-form",
  BASIS_OF_RENT_CALCULATOR: "basis-of-rent-calculator-form",
  CONTACT: "contact-form",
  CONTACT_SEARCH: "contact-search-form",
  CREDIT_DECISION_SEARCH: "credit-info-search-form",
  INFILL_DEVELOPMENT: "infill-development-form",
  INVOICE_NOTE_CREATE: "create-invoice-note-form",
  INVOICE_NOTE_SEARCH: "invoice-note-search-form",
  INVOICE_SIMULATOR: "invoice-simulator-form",
  LEASE_ARCHIVE_AREA: "archive-area-form",
  LEASE_AREAS: "lease-areas-form",
  LEASE_CONSTRUCTABILITY: "constructability-form",
  LEASE_CONTRACTS: "contracts-form",
  LEASE_CREATE_COLLECTION_COURT_DECISION:
    "create-collection-court-decision-form",
  LEASE_CREATE_COLLECTION_LETTER: "create-collection-letter-form",
  LEASE_CREATE_MODAL: "create-lease-form",
  LEASE_DEBT_COLLECTION: "debt-collection-form",
  LEASE_DECISIONS: "decisions-form",
  LEASE_INSPECTIONS: "inspections-form",
  LEASE_INVOICE_CREDIT: "credit-invoice-form",
  LEASE_INVOICE_EDIT: "edit-invoice-form",
  LEASE_INVOICE_NEW: "new-invoice-form",
  LEASE_INVOICE_NOTES: "invoice-notes-form",
  LEASE_NEW_COMMENT: "new-comment-form",
  LEASE_REFUND: "refund-form",
  LEASE_RENTS: "rents-form",
  LEASE_STEPPED_DISCOUNT: "lease-stepped-discount-form",
  LEASE_SUMMARY: "summary-form",
  LEASE_REPORTS: "reports-form",
  LEASE_TENANTS: "tenants-form",
  LEASE_BASIS_OF_RENTS: "basis-of-rents-form",
  LEASE_RENT_CALCULATOR: "rent-calculator-form",
  PLOT_SEARCH_SUMMARY: "plot-search-form",
  PLOT_SEARCH_SEARCH: "plot-search-search",
  PLOT_SEARCH_CREATE: "plot-search-create",
  RENT_BASIS: "rent-basis-form",
  RENT_BASIS_SEARCH: "rent-basis-search-form",
  RENT_CALCULATOR: "rent-calculator-form",
  TRADE_REGISTER_SEARCH: "trade-register-search-form",
  PLOT_SEARCH_BASIC_INFORMATION: "plot-search-basic-information-form",
  PLOT_SEARCH_DIRECT_RESERVATION_LINK: "plot-search-direct-reservation-link",
  PLOT_SEARCH_APPLICATION: "plot-search-application-form",
  PLOT_SEARCH_APPLICATION_SECTION_STAGING:
    "plot-search-application-form-section-staging",
  PLOT_SEARCH_APPLICATION_PREVIEW_MOCK_FORM:
    "plot-search-application-preview-mock-form",
  PLOT_SEARCH_APPLICATIONS_OPENING: "plot-search-applications-opening",
  PLOT_APPLICATIONS_CREATE: "plot-application-create-form",
  PLOT_APPLICATIONS_SEARCH: "plot-application-search",
  PLOT_APPLICATION: "plot-application",
  PLOT_APPLICATION_PREVIEW: "plot-application-preview",
  PLOT_APPLICATION_OPENING: "plot-application-opening",
  APPLICANT_INFO_CHECK: "applicant-info-check",
  PLOT_APPLICATION_TARGET_INFO_CHECK: "plot-application-target-info-check",
  AREA_SEARCH: "area-search",
  AREA_SEARCH_CREATE_SPECS: "area-search-create-specs",
  AREA_SEARCH_CREATE_FORM: "area-search-create-form",
  AREA_SEARCH_PREPARER: "area-search-preparer",
  AREA_SEARCH_EXPORT: "area-search-export",
  SAP_INVOICE_SEARCH: "sap-invoice-search",
};

/**
 * Permission missing texts enumerable.
 * @readonly
 * @enum {string}
 */
export const PermissionMissingTexts = {
  AREA_NOTE: "Tidak berwenang mengakses catatan area",
  AREA_SEARCH: "Tidak berwenang mengakses pencarian area",
  BASIS_OF_RENT_CALCULATOR: "Tidak berwenang mengakses kalkulator sewa",
  BATCHRUN: "Tidak berwenang mengakses tugas terjadwal",
  CONTACT: "Tidak berwenang mengakses kontak",
  CREDIT_DECISION: "Tidak berwenang mengakses data kredit",
  GENERAL: "Tidak berwenang mengakses konten.",
  INDEX: "Tidak berwenang mengakses indeks biaya hidup",
  INFILL_DEVELOPMENT:
    "Tidak berwenang mengakses kompensasi pembangunan sisipan",
  INVOICE: "Tidak berwenang mengakses tagihan",
  INVOICE_NOTE: "Tidak berwenang mengakses catatan tagihan",
  LEASE: "Tidak berwenang mengakses sewa.",
  LEASEHOLD_TRANSFER: "Tidak berwenang mengakses pengalihan hak sewa",
  LEASE_TENANTS_EDIT: "Tidak berwenang mengubah penyewa",
  RENT_BASIS: "Tidak berwenang mengakses prinsip sewa.",
  STATISTICS_AND_REPORTS: "Tidak berwenang mengakses statistik dan laporan",
  TRADE_REGISTER: "Tidak berwenang mengakses data badan usaha",
  PLOT_SEARCH: "Tidak berwenang mengakses pencarian kavling",
  PLOT_APPLICATIONS: "Tidak berwenang mengakses permohonan kavling",
};
