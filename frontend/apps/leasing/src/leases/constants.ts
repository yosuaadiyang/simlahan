import { TableSortOrder } from "@/enums";
import {
  CreditInvoiceOptions as CreditInvoiceOptionsEnum,
  RentDueDateTypes,
  SteppedDiscountAmountTypes,
} from "./enums";

/**
 * Credit invoice options
 * @const {[*]}
 */
export const CreditInvoiceOptions = [
  {
    value: CreditInvoiceOptionsEnum.FULL,
    label: "Seluruh tagihan",
  },
  {
    value: CreditInvoiceOptionsEnum.RECEIVABLE_TYPE,
    label: "Seluruh jenis piutang",
  },
  {
    value: CreditInvoiceOptionsEnum.RECEIVABLE_TYPE_AMOUNT,
    label: "Jumlah per jenis piutang",
  },
];

/**
 * Credit invoiceset options
 * @const {[*]}
 */
export const CreditInvoiceSetOptions = [
  {
    value: CreditInvoiceOptionsEnum.FULL,
    label: "Seluruh kelompok tagihan",
  },
  {
    value: CreditInvoiceOptionsEnum.RECEIVABLE_TYPE,
    label: "Seluruh jenis piutang",
  },
  {
    value: CreditInvoiceOptionsEnum.RECEIVABLE_TYPE_AMOUNT,
    label: "Jumlah per jenis piutang",
  },
];

/**
 * Stepped discount amount type options
 * @const {[*]}
 */
export const SteppedDiscountAmountTypeOptions = [
  {
    value: SteppedDiscountAmountTypes.PERCENTAGE_PER_YEAR,
    label: "% per tahun",
  },
  {
    value: SteppedDiscountAmountTypes.PERCENTAGE_PER_6_MONTHS,
    label: "% per 6 bln",
  },
  {
    value: SteppedDiscountAmountTypes.PERCENTAGE_PER_MONTH,
    label: "% per bulan",
  },
];

/**
 * One time rent due date type options
 * @const {[*]}
 */
export const oneTimeRentDueDateTypeOptions = [
  {
    value: "",
    label: "",
  },
  {
    value: RentDueDateTypes.CUSTOM,
    label: "Ditentukan terpisah",
  },
];

/**
 * Share basis options for manual invoice creation
 */
export const shareBasisOptions = [
  {
    label: "Porsi tagihan",
    value: "tenant_share",
  },
  {
    label: "Porsi penguasaan",
    value: "rent_share",
  },
];

/**
 * Preparation status options for lease list table filter
 * @const {[*]}
 */
export const preparationStateFilterOptions = [
  {
    value: "missing_lease_property",
    label: "Objek sewa belum ada",
  },
  {
    value: "missing_lease_area_geometry",
    label: "Geometri area sewa belum ada",
  },
  {
    value: "missing_tenant",
    label: "Penyewa belum ada",
  },
  {
    value: "missing_rent",
    label: "Sewa belum ada",
  },
  {
    value: "missing_decision",
    label: "Keputusan belum ada",
  },
  {
    value: "missing_constructability",
    label: "Kelayakan bangun belum ada",
  },
  {
    value: "contract_not_signed",
    label: "Kontrak belum ditandatangani",
  },
  {
    value: "rent_not_marked_ready",
    label: "Sewa belum ditandai lengkap",
  },
  {
    value: "invoicing_not_started",
    label: "Penagihan belum dimulai",
  },
];

/**
 * Rent custom date options
 * @const {[*]}
 */
export const rentCustomDateOptions = [
  {
    value: "",
    label: "",
  },
  {
    value: "1",
    label: "1",
  },
  {
    value: "2",
    label: "2",
  },
  {
    value: "4",
    label: "4",
  },
  {
    value: "12",
    label: "12",
  },
];

/**
 * Default lease states value for lease list search
 * @const {string[]}
 */
export const DEFAULT_LEASE_STATES: Array<string> = [];

/**
 * Default only_active_leases value for lease list search
 * @const {boolean}
 */
export const DEFAULT_ONLY_ACTIVE_LEASES = false;

/**
 * Default sort key for lease list table
 * @const {string}
 */
export const DEFAULT_SORT_KEY = "identifier";

/**
 * Default sort order for lease list table
 * @const {string}
 */
export const DEFAULT_SORT_ORDER = TableSortOrder.ASCENDING;

/**
 * Max zoom level to fetch leases for map
 * @const {number}
 */
export const MAX_ZOOM_LEVEL_TO_FETCH_LEASES = 14;

/**
 * Bounding box for search query
 * @const {string[]}
 */
export const BOUNDING_BOX_FOR_SEARCH_QUERY = [
  "24.681112147072024",
  "60.102173950499285",
  "25.388881322490807",
  "60.31481365757164",
];
