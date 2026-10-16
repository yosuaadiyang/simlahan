import { get, set } from "lodash-es";
import { CONTROL_SHARE_FIELD_IDENTIFIER } from "@/application/constants";
/**
 * Validasi NIK (Nomor Induk Kependudukan): 16 digit, kode wilayah tidak nol,
 * tanggal lahir valid (perempuan: tanggal + 40).
 */
export const personalIdentifierValidator = (
  value: any,
  error?: string,
): string | null | undefined => {
  if (value === "" || value === null || value === undefined) {
    return;
  }

  const nik = String(value).trim();

  if (!/^\d{16}$/.test(nik)) {
    return error || "NIK harus 16 digit angka";
  }

  if (nik.startsWith("00") || nik.slice(12) === "0000") {
    return error || "NIK tidak valid";
  }

  let day = parseInt(nik.slice(6, 8));
  const month = parseInt(nik.slice(8, 10));
  if (day > 40) day -= 40;
  if (day < 1 || day > 31 || month < 1 || month > 12) {
    return error || "NIK tidak valid";
  }
};

/**
 * Validasi NPWP: 15 digit (format lama, boleh dengan tanda baca
 * 00.000.000.0-000.000) atau 16 digit (NIK/NPWP baru).
 */
export const companyIdentifierValidator = (
  value: any,
  error?: string,
): string | null | undefined => {
  if (value === "" || value === null || value === undefined) {
    return;
  }

  if (typeof value !== "string") {
    return error || "NPWP tidak valid";
  }

  const trimmed = value.trim();
  const isFormatted = /^\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3}$/.test(trimmed);
  const isPlain = /^(\d{15}|\d{16})$/.test(trimmed);

  if (!isFormatted && !isPlain) {
    return error || "NPWP harus 15 atau 16 digit";
  }
};
export const emailValidator = (
  value: any,
  error?: string,
): string | null | undefined => {
  if (!value) {
    return;
  }

  // A relatively simple validation that catches the most egregious examples of invalid emails.
  // (Also intentionally denies some technically valid but in this context exceedingly rare addresses,
  // like ones with quoted strings containing spaces or a right-side value without a dot.)
  if (!/^\S+@\S+\.\S{2,}$/.exec(value)) {
    return error || "Alamat email tidak valid";
  }
};
export const validateApplicationForm: (
  arg0: string,
) => (arg0: Record<string, any>) => Record<string, any> =
  (pathPrefix: string) => (values: Record<string, any>) => {
    let sum = 0;
    const errors = {};
    const controlSharePaths = [];
    const root = get(values, pathPrefix);

    if (!root?.sections) {
      return {};
    }

    const searchSingleSection = (section, path) => {
      if (section.fields) {
        Object.keys(section.fields).forEach((fieldIdentifier) => {
          if (fieldIdentifier === CONTROL_SHARE_FIELD_IDENTIFIER) {
            const result = /^(\d+)\s*\/\s*(\d+)$/.exec(
              section.fields[fieldIdentifier].value,
            );

            if (!result) {
              set(
                errors,
                `${path}.fields.${fieldIdentifier}.value`,
                "Porsi penguasaan tidak valid",
              );
            } else {
              sum += parseInt(result[1]) / parseInt(result[2]);
              controlSharePaths.push(`${path}.fields.${fieldIdentifier}.value`);
            }
          }
        });
      }

      if (section.sections) {
        Object.keys(section.sections).forEach((identifier) =>
          searchSection(
            section.sections[identifier],
            `${path}.sections.${identifier}`,
          ),
        );
      }
    };

    const searchSection = (section, path) => {
      if (section instanceof Array) {
        section.forEach((singleSection, i) =>
          searchSingleSection(singleSection, `${path}[${i}]`),
        );
      } else {
        searchSingleSection(section, path);
      }
    };

    Object.keys(root.sections).forEach((identifier) =>
      searchSection(
        root.sections[identifier],
        `${pathPrefix}.sections.${identifier}`,
      ),
    );

    if (Math.abs(sum - 1) > 1e-9) {
      controlSharePaths.forEach((path) => {
        set(errors, path, "Total porsi penguasaan harus 100%");
      });
    }

    return errors;
  };
