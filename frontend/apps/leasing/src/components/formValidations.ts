import { RentCalculatorTypes } from "./enums";
import { isEmptyValue } from "@/util/helpers";
import { year } from "./form/validations";
export const validateRentCalculatorForm = (values: Record<string, any>) => {
  const errors: any = {};

  switch (values.type) {
    case RentCalculatorTypes.YEAR:
      if (isEmptyValue(values.year)) errors.yearErrors = "Tahun wajib diisi";
      else if (year(values.year)) errors.yearErrors = year(values.year);
      break;

    case RentCalculatorTypes.BILLING_PERIOD:
      if (isEmptyValue(values.billing_period))
        errors.billingPeriodErrors = "Periode tagihan wajib diisi";
      break;
  }

  return errors;
};
