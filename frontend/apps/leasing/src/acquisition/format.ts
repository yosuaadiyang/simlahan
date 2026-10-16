const numberFormatter = new Intl.NumberFormat("id-ID", {
  maximumFractionDigits: 2,
});
const moneyFormatter = new Intl.NumberFormat("id-ID", {
  style: "currency",
  currency: "IDR",
  maximumFractionDigits: 0,
});
const dateFormatter = new Intl.DateTimeFormat("id-ID", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

const toNumber = (value: unknown): number | null => {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

export const formatRupiah = (value: unknown): string => {
  const n = toNumber(value);
  return n === null ? "–" : moneyFormatter.format(n);
};

export const formatArea = (value: unknown): string => {
  const n = toNumber(value);
  return n === null ? "–" : `${numberFormatter.format(n)} m²`;
};

export const formatHectare = (value: unknown): string => {
  const n = toNumber(value);
  return n === null ? "–" : `${numberFormatter.format(n / 10000)} ha`;
};

export const formatNumberId = (value: unknown): string => {
  const n = toNumber(value);
  return n === null ? "–" : numberFormatter.format(n);
};

export const formatDateId = (value: unknown): string => {
  if (!value) return "–";
  const d = new Date(
    String(value).length === 10 ? `${value}T00:00:00` : String(value),
  );
  return Number.isNaN(d.getTime()) ? String(value) : dateFormatter.format(d);
};

export const percent = (part: unknown, total: unknown): number => {
  const p = toNumber(part) || 0;
  const t = toNumber(total) || 0;
  return t > 0 ? Math.min(100, Math.round((p / t) * 100)) : 0;
};
