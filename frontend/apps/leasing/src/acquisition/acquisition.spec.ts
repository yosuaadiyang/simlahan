import { describe, expect, it, vi } from "vitest";
import { extractErrorMessage } from "./api";
import { formatArea, formatDateId, formatRupiah, percent } from "./format";
import { labelOf } from "./components/ui";

vi.mock("@/root/store", () => ({
  default: { dispatch: vi.fn(), getState: vi.fn(() => ({ auth: {} })) },
}));

describe("Acquisition helpers", () => {
  it("formats rupiah without decimals", () => {
    expect(formatRupiah("1500000").replace(/\s/g, " ")).toMatch(
      /Rp.?1\.500\.000/,
    );
    expect(formatRupiah(null)).toBe("–");
  });
  it("formats area in square metres", () => {
    expect(formatArea("1234.5")).toBe("1.234,5 m²");
    expect(formatArea("")).toBe("–");
  });
  it("formats ISO dates", () => {
    expect(formatDateId("2026-08-17")).toMatch(/17 Agu\w* 2026/);
    expect(formatDateId(null)).toBe("–");
  });
  it("computes bounded percentages", () => {
    expect(percent(50, 200)).toBe(25);
    expect(percent(300, 200)).toBe(100);
    expect(percent(1, 0)).toBe(0);
  });
  it("extracts DRF error messages", () => {
    expect(extractErrorMessage({ detail: "Tidak berwenang." })).toBe(
      "Tidak berwenang.",
    );
    expect(extractErrorMessage({ non_field_errors: ["A", "B"] })).toBe("A B");
    expect(extractErrorMessage({ nik: ["NIK tidak valid"] })).toBe(
      "nik: NIK tidak valid",
    );
    expect(extractErrorMessage(null)).toBe("");
  });
  it("resolves choice labels", () => {
    const choices = { ParcelStatus: [{ value: "paid", label: "Dibayar" }] };
    expect(labelOf(choices, "ParcelStatus", "paid")).toBe("Dibayar");
    expect(labelOf(choices, "ParcelStatus", "x")).toBe("x");
    expect(labelOf(choices, "ParcelStatus", null)).toBe("–");
  });
});
