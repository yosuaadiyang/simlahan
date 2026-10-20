import { describe, expect, it, vi } from "vitest";
import { extractErrorMessage } from "./api";
import { formatArea, formatDateId, formatRupiah, percent } from "./format";
import { labelOf } from "./components/ui";
import { getResourcePermissions } from "./permissions";
import {
  buildPayload,
  findMissingRequired,
  REQUIRED_MESSAGE,
} from "./components/ResourceForm";

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
    // ValidationError tanpa nama bidang dikirim DRF sebagai daftar.
    expect(
      extractErrorMessage([
        "Pihak yang berhak tidak memiliki nomor rekening bank.",
      ] as any),
    ).toBe("Pihak yang berhak tidak memiliki nomor rekening bank.");
    expect(extractErrorMessage(["A", "B"] as any)).toBe("A B");
  });
  it("derives section rights from the user's permissions", () => {
    const readOnly = getResourcePermissions(
      [{ codename: "view_valuation" }],
      "pengadaan/valuation/",
    );
    expect(readOnly).toEqual({
      isLoaded: true,
      canView: true,
      canAdd: false,
      canChange: false,
      canDelete: false,
    });
    const noAccess = getResourcePermissions(
      [{ codename: "view_valuation" }],
      "pengadaan/payment/",
    );
    expect(noAccess.canView).toBe(false);
    expect(getResourcePermissions([], "pengadaan/payment/").isLoaded).toBe(
      false,
    );
  });
  it("flags empty required fields before saving", () => {
    const meta: any = {
      parcel: { type: "field", required: true, read_only: false },
      note: { type: "string", required: false, read_only: false },
      code: { type: "string", required: true, read_only: true },
    };
    expect(
      findMissingRequired(meta, { parcel: null, note: "", code: "" }),
    ).toEqual({ parcel: REQUIRED_MESSAGE });
    expect(findMissingRequired(meta, { parcel: 3, note: "" })).toEqual({});
  });
  it("leaves empty optional fields to server defaults on create", () => {
    const meta: any = {
      parcel: { type: "field", required: true, read_only: false },
      land_value: { type: "decimal", required: false, read_only: false },
      note: { type: "string", required: false, read_only: false },
    };
    const specs = [
      { name: "parcel" },
      { name: "land_value" },
      { name: "note" },
    ];
    expect(
      buildPayload(specs, meta, { land_value: "" }, null, { project: 1 }),
    ).toEqual({ project: 1, parcel: null, note: "" });
    expect(
      buildPayload(specs, meta, { land_value: "" }, null, { parcel: 7 }),
    ).toEqual({ parcel: 7, note: "" });
    // Saat mengubah data, pengosongan tetap dikirim sebagai null.
    expect(
      buildPayload(specs, meta, { parcel: 7, land_value: "" }, { id: 1 }),
    ).toEqual({ parcel: 7, land_value: null, note: "" });
  });
  it("resolves choice labels", () => {
    const choices = { ParcelStatus: [{ value: "paid", label: "Dibayar" }] };
    expect(labelOf(choices, "ParcelStatus", "paid")).toBe("Dibayar");
    expect(labelOf(choices, "ParcelStatus", "x")).toBe("x");
    expect(labelOf(choices, "ParcelStatus", null)).toBe("–");
  });
});
