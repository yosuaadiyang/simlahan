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

// Nilai desimal dari API dikirim sebagai string (mis. "987654321987654321.99").
// Mengubahnya ke Number kehilangan presisi di atas ±9 kuadriliun, jadi string
// desimal diformat langsung digit per digit (pembulatan setengah ke atas).
const DECIMAL_RE = /^(-)?(\d+)(?:\.(\d+))?$/;

const formatDecimalString = (
  value: string,
  fractionDigits: number,
): string | null => {
  const match = DECIMAL_RE.exec(value.trim());
  if (!match) return null;
  const [, sign, intPart, fracPart = ""] = match;
  const frac = fracPart.padEnd(fractionDigits + 1, "0");
  let scaled = BigInt(intPart + frac.slice(0, fractionDigits));
  if (Number(frac[fractionDigits]) >= 5) scaled += BigInt(1);
  const digits = scaled.toString().padStart(fractionDigits + 1, "0");
  const cut = digits.length - fractionDigits;
  const whole = digits.slice(0, cut).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const decimals = digits.slice(cut).replace(/0+$/, "");
  const negative = !!sign && scaled !== BigInt(0);
  return `${negative ? "-" : ""}${whole}${decimals ? `,${decimals}` : ""}`;
};

/** Geser titik desimal string ke kiri (mis. m² → ha = 4 digit). */
const shiftDecimalLeft = (value: string, places: number): string | null => {
  const match = DECIMAL_RE.exec(value.trim());
  if (!match) return null;
  const [, sign, intPart, fracPart = ""] = match;
  const padded = intPart.padStart(places + 1, "0");
  const cut = padded.length - places;
  return `${sign || ""}${padded.slice(0, cut)}.${padded.slice(cut)}${fracPart}`;
};

const formatExact = (
  value: unknown,
  fractionDigits: number,
  fallback: Intl.NumberFormat,
): string | null => {
  if (typeof value === "string") {
    const exact = formatDecimalString(value, fractionDigits);
    if (exact !== null) return exact;
  }
  const n = toNumber(value);
  return n === null ? null : fallback.format(n);
};

export const formatRupiah = (value: unknown): string => {
  if (typeof value === "string") {
    const exact = formatDecimalString(value, 0);
    if (exact !== null) {
      return exact.startsWith("-")
        ? `-Rp\u00a0${exact.slice(1)}`
        : `Rp\u00a0${exact}`;
    }
  }
  const n = toNumber(value);
  return n === null ? "–" : moneyFormatter.format(n);
};

export const formatArea = (value: unknown): string => {
  const text = formatExact(value, 2, numberFormatter);
  return text === null ? "–" : `${text} m²`;
};

export const formatHectare = (value: unknown): string => {
  if (typeof value === "string") {
    const shifted = shiftDecimalLeft(value, 4);
    const exact = shifted === null ? null : formatDecimalString(shifted, 2);
    if (exact !== null) return `${exact} ha`;
  }
  const n = toNumber(value);
  return n === null ? "–" : `${numberFormatter.format(n / 10000)} ha`;
};

export const formatNumberId = (value: unknown): string => {
  const text = formatExact(value, 2, numberFormatter);
  return text === null ? "–" : text;
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
