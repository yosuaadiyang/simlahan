import { RentCalculatorTypes } from "./enums";

/**
 * Rent calculator type options
 * @readonly
 * @const {Object[]}
 */
export const RentCalculatorTypeOptions = [
  {
    value: RentCalculatorTypes.YEAR,
    label: "Tahun",
  },
  {
    value: RentCalculatorTypes.BILLING_PERIOD,
    label: "Periode tagihan",
  },
];
