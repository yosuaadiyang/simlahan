import isBefore from "date-fns/isBefore";
import { isArray } from "lodash-es";
import { isValidDate } from "@/util/date";
import { isEmptyValue } from "@/util/helpers";

const decimalPlaces = (n) => {
  const result = /^-?[0-9]+\.([0-9]+)$/.exec(n);
  return result === null ? 0 : result[1].length;
};

/**
 * Ensures that if errorText is provided, it is a string. Otherwise, return a default error message.
 *
 * @param errorText - The error value from the form library (string from redux-form or object from final-form)
 * @param defaultErrorMessage - Fallback message to use when errorText is not provided or a string
 * @returns A string error message suitable for display
 */
const formatError = (
  errorText: string | unknown,
  defaultErrorMessage: string,
): string => {
  return errorText && typeof errorText === "string"
    ? errorText
    : defaultErrorMessage;
};

export const required = (
  value: any,
  errorText?: string,
): string | undefined => {
  const defaultError = formatError(errorText, "Kolom wajib");

  if (value instanceof Date) {
    return !isNaN(value.valueOf())
      ? undefined
      : formatError(errorText, "Nilai tidak valid");
  }

  if (isArray(value)) {
    return value.length ? undefined : defaultError;
  }

  const actualValue = value?.value !== undefined ? value.value : value;

  return !!actualValue || actualValue === 0 ? undefined : defaultError;
};

export const integer = (
  value: any,
  errorText?: string,
): string | null | undefined =>
  isEmptyValue(value) || Number.isInteger(Number(value))
    ? undefined
    : formatError(errorText, "Nilai harus bilangan bulat");

export const isDate = (
  value: any,
  errorText?: string,
): string | null | undefined =>
  isEmptyValue(value) || isValidDate(new Date(value))
    ? undefined
    : formatError(errorText, "Nilai harus berupa tanggal");

export const decimalNumber = (
  value: any,
  errorText?: string,
): string | null | undefined =>
  isEmptyValue(value) ||
  !isNaN(value.toString().replace(",", ".").replace(/\s+/g, ""))
    ? undefined
    : formatError(errorText, "Nilai harus berupa angka");

export const min = (
  value: any,
  min: number,
  errorText?: string,
): string | null | undefined =>
  isEmptyValue(value) || Number(value) >= min
    ? undefined
    : formatError(errorText, `Nilai minimum adalah ${min}`);

export const max = (
  value: any,
  max: number,
  errorText?: string,
): string | null | undefined =>
  isEmptyValue(value) || Number(value) <= max
    ? undefined
    : formatError(errorText, `Nilai maksimum adalah ${max}`);

export const maxLength = (
  value: any,
  max: number,
  errorText?: string,
): string | undefined =>
  isEmptyValue(value) || value.length <= max
    ? undefined
    : formatError(errorText, `Panjang maksimum adalah ${max}`);

export const digitsMaxLength = (
  value: any,
  max: number,
  errorText?: string,
): string | null | undefined =>
  isEmptyValue(value) || parseInt(value).toString().length <= max
    ? undefined
    : formatError(
        errorText,
        `Panjang maksimum bagian bilangan bulat adalah ${max}`,
      );

export const decimalsMaxLength = (
  value: any,
  max: number,
  errorText?: string,
): string | null | undefined =>
  isEmptyValue(value) ||
  decimalPlaces(value.toString().replace(",", ".")) <= max
    ? undefined
    : formatError(errorText, `Panjang maksimum bagian desimal adalah ${max}`);

export const dateGreaterOrEqual = (
  date: string | null | undefined,
  otherDate: string | null | undefined,
  errorText?: string,
): string | null | undefined => {
  if (isEmptyValue(date) || isEmptyValue(otherDate)) {
    return undefined;
  }

  return date && otherDate && !isBefore(new Date(date), new Date(otherDate))
    ? undefined
    : formatError(errorText, "Tgl akhir tidak boleh sebelum tgl mulai");
};

export const internalOrder = (
  value: any,
  errorText?: string,
): string | null | undefined => {
  if (isEmptyValue(value)) {
    return undefined;
  }

  return value.length <= 12
    ? undefined
    : formatError(
        errorText,
        "Nomor pesanan internal berupa deret angka maksimal 12 digit.",
      );
};

export const referenceNumber = (
  value: any,
  errorText?: string,
): string | undefined => {
  if (isEmptyValue(value)) {
    return undefined;
  }
  // Nomor surat/keputusan bebas format, cukup dibatasi panjang & karakter cetak.
  const text = String(value).trim();
  const isValid = text.length > 0 && text.length <= 128 && !/[\r\n]/.test(text);
  return isValid
    ? undefined
    : formatError(errorText, "Format nilai tidak valid");
};

export const year = (
  value: any,
  errorText?: string,
): string | null | undefined => {
  if (isEmptyValue(value)) {
    return undefined;
  }

  const numbers = /^[0-9]+$/;
  const year = value.toString();

  if (!numbers.test(year) || year.length !== 4) {
    return errorText ? errorText : "Tahun harus terdiri dari 4 angka";
  }

  return undefined;
};

export const genericValidator = (
  value: any,
  options: Record<string, any>,
): any => {
  if (!options) {
    return undefined;
  }

  let errorText = "";

  if (options.required) {
    errorText = required(value);

    if (errorText) {
      return errorText;
    }
  }

  if (options.type === "date") {
    errorText = isDate(value);

    if (errorText) {
      return errorText;
    }
  }

  if (options.type === "decimal") {
    errorText = decimalNumber(value);

    if (errorText) {
      return errorText;
    }

    if (options.max_digits) {
      errorText = digitsMaxLength(value, options.max_digits);

      if (errorText) {
        return errorText;
      }
    }

    if (options.decimal_places) {
      errorText = decimalsMaxLength(value, options.decimal_places);

      if (errorText) {
        return errorText;
      }
    }
  }

  if (options.type === "integer") {
    errorText = integer(value);

    if (errorText) {
      return errorText;
    }
  }

  if (options.type === "string" && options.max_length) {
    errorText = maxLength(value, options.max_length);

    if (errorText) {
      return errorText;
    }
  }

  if (options.min_value !== undefined && options.min_value !== null) {
    errorText = min(value, options.min_value);

    if (errorText) {
      return errorText;
    }
  }

  if (options.max_value !== undefined && options.max_value !== null) {
    errorText = max(value, options.max_value);

    if (errorText) {
      return errorText;
    }
  }

  return undefined;
};
