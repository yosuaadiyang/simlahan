import React, { useMemo, useState } from "react";
import {
  ApiRequestError,
  apiSend,
  apiUpload,
  extractErrorMessage,
} from "../api";
import { useFieldMeta } from "../hooks";
import type { FieldMeta, Option } from "../types";

export type FormFieldSpec =
  | string
  | {
      name: string;
      wide?: boolean;
      options?: Array<Option>;
      help?: string;
      label?: string;
      multiple?: boolean;
      onChange?: (
        value: any,
        values: Record<string, any>,
      ) => Record<string, any>;
    };

type Props = {
  endpoint: string;
  fields: Array<FormFieldSpec>;
  instance?: Record<string, any> | null;
  defaults?: Record<string, any>;
  fkOptions?: Record<string, Array<Option>>;
  submitLabel?: string;
  onSaved: (record: Record<string, any>) => void;
  onCancel?: () => void;
};

const normalizeSpec = (spec: FormFieldSpec) =>
  typeof spec === "string" ? { name: spec } : spec;

const TEXTAREA_TYPES = new Set(["string"]);

const isFileType = (meta?: FieldMeta) =>
  Boolean(meta && /^(file|image)/.test(meta.type));

const initialValue = (meta: FieldMeta | undefined, value: any) => {
  if (Array.isArray(value)) return value;
  if (value === null || value === undefined) {
    return meta?.type === "boolean" ? false : "";
  }
  if (meta?.type === "date" && typeof value === "string") {
    return value.slice(0, 10);
  }
  return value;
};

/**
 * Terima penulisan angka gaya Indonesia: "1.500.000,50" atau "1.500"
 * (titik = pemisah ribuan, koma = desimal) selain "1500000.50".
 */
export const normalizeDecimalInput = (value: string): string => {
  let text = value.replace(/[\s\u00a0]/g, "").replace(/^Rp\.?/i, "");
  if (text.includes(",")) {
    text = text.replace(/\./g, "").replace(",", ".");
  } else if (/^-?\d{1,3}(\.\d{3})+$/.test(text)) {
    text = text.replace(/\./g, "");
  }
  return text;
};

const serialize = (
  meta: FieldMeta | undefined,
  value: any,
  unchanged = false,
) => {
  if (!meta) return value;
  if (meta.type === "boolean") return Boolean(value);
  if (value === "" || value === undefined) {
    return ["string", "email", "url"].includes(meta.type) ? "" : null;
  }
  if (meta.type === "decimal" && typeof value === "string") {
    // Nilai dari server ("33.333") dikirim apa adanya; hanya ketikan pengguna
    // yang dibaca dengan aturan penulisan Indonesia.
    return unchanged ? value : normalizeDecimalInput(value);
  }
  return value;
};

export const REQUIRED_MESSAGE = "Bidang ini wajib diisi.";

/** Bidang wajib yang masih kosong, sebelum data dikirim ke server. */
export const findMissingRequired = (
  meta: Record<string, FieldMeta>,
  payload: Record<string, any>,
): Record<string, string> => {
  const missing: Record<string, string> = {};
  Object.entries(payload).forEach(([name, value]) => {
    const fieldMeta = meta[name];
    if (!fieldMeta?.required || fieldMeta.read_only) return;
    if (value === null || value === undefined || value === "") {
      missing[name] = REQUIRED_MESSAGE;
    }
  });
  return missing;
};

/** Data yang dikirim ke API dari isian formulir. */
export const buildPayload = (
  specs: Array<{ name: string; multiple?: boolean }>,
  meta: Record<string, FieldMeta>,
  values: Record<string, any>,
  instance?: Record<string, any> | null,
  defaults?: Record<string, any>,
): Record<string, any> => {
  const payload: Record<string, any> = { ...(instance ? {} : defaults) };
  specs.forEach(({ name, multiple }) => {
    const fieldMeta = meta[name];
    if (!fieldMeta || fieldMeta.read_only || isFileType(fieldMeta)) return;
    if (multiple) {
      payload[name] = Array.isArray(values[name]) ? values[name] : [];
      return;
    }
    const value = initialValue(fieldMeta, values[name]);
    if (fieldMeta.type === "choice" && (value === "" || value === null)) {
      // Biarkan nilai bawaan server untuk pilihan yang dikosongkan.
      return;
    }
    const serialized = serialize(
      fieldMeta,
      value,
      !!instance && values[name] === instance[name],
    );
    if (
      serialized === null &&
      !instance &&
      (!fieldMeta.required || defaults?.[name] != null)
    ) {
      // Bidang kosong saat menambah data: pakai nilai bawaan (formulir atau
      // server), bukan null; kolom berangka dengan nilai bawaan menolak null.
      return;
    }
    payload[name] = serialized;
  });
  return payload;
};

const ResourceForm: React.FC<Props> = ({
  endpoint,
  fields,
  instance,
  defaults,
  fkOptions,
  submitLabel,
  onSaved,
  onCancel,
}) => {
  const { data: meta, isLoading, error: metaError } = useFieldMeta(endpoint);
  const specs = useMemo(() => fields.map(normalizeSpec), [fields]);
  const [values, setValues] = useState<Record<string, any>>(() => {
    const result: Record<string, any> = {};
    specs.forEach(({ name }) => {
      result[name] = instance ? instance[name] : undefined;
    });
    return result;
  });
  const [files, setFiles] = useState<Record<string, File | null>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  if (isLoading) return <p className="acq-muted">Memuat formulir…</p>;
  if (metaError || !meta) {
    return (
      <p className="acq-error">{metaError || "Formulir tidak tersedia."}</p>
    );
  }

  const setValue = (spec: ReturnType<typeof normalizeSpec>, value: any) => {
    setValues((prev) => {
      const next = { ...prev, [spec.name]: value };
      return spec.onChange ? { ...next, ...spec.onChange(value, next) } : next;
    });
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSaving(true);
    setErrors({});
    setFormError(null);
    const payload = buildPayload(specs, meta, values, instance, defaults);
    const missing = findMissingRequired(
      meta,
      Object.fromEntries(
        specs
          .filter(({ name }) => name in payload)
          .map(({ name }) => [name, payload[name]]),
      ),
    );
    if (Object.keys(missing).length) {
      setErrors(missing);
      setFormError("Periksa kembali isian yang ditandai.");
      setIsSaving(false);
      return;
    }
    const hasFiles = Object.values(files).some(Boolean);
    try {
      let record: Record<string, any>;
      const path = instance ? `${endpoint}${instance.id}/` : endpoint;
      if (hasFiles) {
        const formData = new FormData();
        Object.entries(payload).forEach(([key, value]) => {
          if (value === null || value === undefined) return;
          if (Array.isArray(value)) {
            value.forEach((item) => formData.append(key, String(item)));
          } else {
            formData.append(key, String(value));
          }
        });
        Object.entries(files).forEach(([key, file]) => {
          if (file) formData.append(key, file);
        });
        record = await apiUpload(path, formData, instance ? "PATCH" : "POST");
      } else {
        record = await apiSend(instance ? "PATCH" : "POST", path, payload);
      }
      onSaved(record);
    } catch (e) {
      if (
        e instanceof ApiRequestError &&
        e.body &&
        typeof e.body === "object"
      ) {
        const fieldErrors: Record<string, string> = {};
        Object.entries(e.body).forEach(([key, value]) => {
          if (specs.some((s) => s.name === key)) {
            fieldErrors[key] = Array.isArray(value)
              ? value.join(" ")
              : String(value);
          }
        });
        setErrors(fieldErrors);
        const rest = { ...e.body };
        Object.keys(fieldErrors).forEach((key) => delete rest[key]);
        setFormError(
          Object.keys(rest).length
            ? extractErrorMessage(rest)
            : Object.keys(fieldErrors).length
              ? "Periksa kembali isian yang ditandai."
              : e.message,
        );
      } else {
        setFormError((e as Error).message || "Gagal menyimpan.");
      }
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <form className="acq-form" onSubmit={handleSubmit} noValidate>
      <div className="acq-form__grid">
        {specs.map((spec) => {
          const fieldMeta = meta[spec.name];
          if (!fieldMeta) return null;
          const id = `acq-${endpoint.replace(/\W/g, "-")}-${spec.name}`;
          const value = initialValue(fieldMeta, values[spec.name]);
          const label = spec.label || fieldMeta.label;
          const disabled = fieldMeta.read_only || isSaving;
          const options: Array<Option> | null =
            spec.options ||
            fkOptions?.[spec.name] ||
            (fieldMeta.choices
              ? fieldMeta.choices.map((c) => ({
                  value: c.value,
                  label: c.display_name,
                }))
              : null);
          let input: React.ReactNode;

          if (fieldMeta.type === "boolean") {
            input = (
              <label className="acq-checkbox" htmlFor={id}>
                <input
                  id={id}
                  type="checkbox"
                  checked={Boolean(value)}
                  disabled={disabled}
                  onChange={(e) => setValue(spec, e.target.checked)}
                />
                <span>{label}</span>
              </label>
            );
          } else if (isFileType(fieldMeta)) {
            input = (
              <input
                id={id}
                type="file"
                disabled={disabled}
                onChange={(e) =>
                  setFiles((prev) => ({
                    ...prev,
                    [spec.name]: e.target.files?.[0] || null,
                  }))
                }
              />
            );
          } else if (options && spec.multiple) {
            const selected: Array<string> = (
              Array.isArray(value) ? value : []
            ).map(String);
            input = (
              <select
                id={id}
                multiple
                size={Math.min(8, Math.max(3, options.length))}
                value={selected}
                disabled={disabled}
                onChange={(e) => {
                  const raw = Array.from(e.target.selectedOptions).map(
                    (o) => o.value,
                  );
                  setValue(
                    spec,
                    options
                      .filter((o) => raw.includes(String(o.value)))
                      .map((o) => o.value),
                  );
                }}
              >
                {options.map((option) => (
                  <option
                    key={String(option.value)}
                    value={String(option.value)}
                  >
                    {option.label}
                  </option>
                ))}
              </select>
            );
          } else if (options) {
            input = (
              <select
                id={id}
                value={value ?? ""}
                disabled={disabled}
                onChange={(e) => {
                  const raw = e.target.value;
                  const match = options.find((o) => String(o.value) === raw);
                  setValue(spec, match ? match.value : "");
                }}
              >
                <option value="">– pilih –</option>
                {options.map((option) => (
                  <option
                    key={String(option.value)}
                    value={String(option.value)}
                  >
                    {option.label}
                  </option>
                ))}
              </select>
            );
          } else if (
            TEXTAREA_TYPES.has(fieldMeta.type) &&
            !fieldMeta.max_length
          ) {
            input = (
              <textarea
                id={id}
                rows={3}
                value={value}
                disabled={disabled}
                onChange={(e) => setValue(spec, e.target.value)}
              />
            );
          } else {
            const type =
              fieldMeta.type === "date"
                ? "date"
                : fieldMeta.type === "email"
                  ? "email"
                  : fieldMeta.type === "integer"
                    ? "number"
                    : "text";
            input = (
              <input
                id={id}
                type={type}
                inputMode={fieldMeta.type === "decimal" ? "decimal" : undefined}
                maxLength={fieldMeta.max_length}
                value={value}
                disabled={disabled}
                onChange={(e) => setValue(spec, e.target.value)}
              />
            );
          }

          const wide =
            spec.wide ||
            (TEXTAREA_TYPES.has(fieldMeta.type) && !fieldMeta.max_length);
          return (
            <div
              key={spec.name}
              className={`acq-form__field${wide ? " acq-form__field--wide" : ""}${
                errors[spec.name] ? " has-error" : ""
              }`}
            >
              {fieldMeta.type !== "boolean" && (
                <label htmlFor={id}>
                  {label}
                  {fieldMeta.required && !fieldMeta.read_only ? " *" : ""}
                </label>
              )}
              {input}
              {spec.help && <small className="acq-muted">{spec.help}</small>}
              {errors[spec.name] && (
                <small className="acq-error">{errors[spec.name]}</small>
              )}
            </div>
          );
        })}
      </div>
      {formError && (
        <p className="acq-error" role="alert">
          {formError}
        </p>
      )}
      <div className="acq-form__actions">
        {onCancel && (
          <button
            type="button"
            className="acq-button acq-button--secondary"
            onClick={onCancel}
            disabled={isSaving}
          >
            Batal
          </button>
        )}
        <button type="submit" className="acq-button" disabled={isSaving}>
          {isSaving ? "Menyimpan…" : submitLabel || "Simpan"}
        </button>
      </div>
    </form>
  );
};

export default ResourceForm;
