import { describe, expect, it, vi } from "vitest";
import { extractErrorMessage } from "./api";
import {
  formatArea,
  formatDateId,
  formatHectare,
  formatNumberId,
  formatRupiah,
  percent,
} from "./format";
import { labelOf } from "./components/ui";
import {
  canEditMilestone,
  getProjectCapabilities,
  getResourcePermissions,
} from "./permissions";
import {
  buildPayload,
  findMissingRequired,
  normalizeDecimalInput,
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
  it("formats very large decimals exactly", () => {
    // Di atas 2^53 Number kehilangan digit; string desimal dari API harus utuh.
    expect(formatRupiah("987654321987654321.99").replace(/\s/g, " ")).toBe(
      "Rp 987.654.321.987.654.322",
    );
    expect(formatRupiah("-1500000.40").replace(/\s/g, " ")).toBe(
      "-Rp 1.500.000",
    );
    expect(formatRupiah(2500).replace(/\s/g, " ")).toMatch(/Rp.?2\.500/);
    expect(formatArea("98765432198765.43")).toBe("98.765.432.198.765,43 m²");
    expect(formatArea("10.005")).toBe("10,01 m²");
    expect(formatArea("0.00")).toBe("0 m²");
    expect(formatNumberId("100.000")).toBe("100");
    expect(formatNumberId("abc")).toBe("–");
    expect(formatHectare("98765432198765.43")).toBe("9.876.543.219,88 ha");
    expect(formatHectare("2500")).toBe("0,25 ha");
    expect(formatHectare(null)).toBe("–");
  });
  it("accepts Indonesian number notation in decimal inputs", () => {
    expect(normalizeDecimalInput("1.500.000")).toBe("1500000");
    expect(normalizeDecimalInput("1.500.000,50")).toBe("1500000.50");
    expect(normalizeDecimalInput("Rp 2.000")).toBe("2000");
    expect(normalizeDecimalInput("Rp. 2.000.000")).toBe("2000000");
    expect(normalizeDecimalInput("12,5")).toBe("12.5");
    expect(normalizeDecimalInput("12.5")).toBe("12.5");
    expect(normalizeDecimalInput("1234.56")).toBe("1234.56");
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
  it("gates project page actions by combined permissions", () => {
    const perms = (...codenames: Array<string>) =>
      codenames.map((codename) => ({ codename }));
    // Satgas: boleh menambah bidang tetapi tidak menambah proyek.
    const satgas = getProjectCapabilities(
      perms(
        "view_acquisitionproject",
        "add_acquisitionparcel",
        "view_entitledparty",
        "view_valuation",
        "view_compensation",
      ),
    );
    expect(satgas.canImportParcels).toBe(false);
    expect(satgas.canExportNominative).toBe(true);
    expect(satgas.canRecordPayment).toBe(false);
    // Instansi pemohon: tanpa pihak dan nilai uang.
    const agency = getProjectCapabilities(
      perms("view_acquisitionproject", "view_acquisitionparcel"),
    );
    expect(agency.canViewParties).toBe(false);
    expect(agency.canExportNominative).toBe(false);
    const pelaksana = getProjectCapabilities(
      perms(
        "add_acquisitionproject",
        "add_acquisitionparcel",
        "view_entitledparty",
        "view_valuation",
        "view_compensation",
        "add_compensationpayment",
      ),
    );
    expect(pelaksana).toEqual({
      canViewParties: true,
      canExportNominative: true,
      canImportParcels: true,
      canRecordPayment: true,
    });
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
  it("keeps unchanged server decimals and reads typed Indonesian numbers", () => {
    const meta = {
      share_percentage: { type: "decimal", required: false, read_only: false },
      amount: { type: "decimal", required: false, read_only: false },
    } as any;
    const specs = [{ name: "share_percentage" }, { name: "amount" }];
    const instance = { id: 1, share_percentage: "33.333", amount: "1500.00" };
    expect(
      buildPayload(specs, meta, { ...instance, amount: "2.500.000" }, instance),
    ).toEqual({ share_percentage: "33.333", amount: "2500000" });
    expect(
      buildPayload(specs, meta, { share_percentage: "33.333" }, null),
    ).toEqual({ share_percentage: "33333" });
  });
  it("resolves choice labels", () => {
    const choices = { ParcelStatus: [{ value: "paid", label: "Dibayar" }] };
    expect(labelOf(choices, "ParcelStatus", "paid")).toBe("Dibayar");
    expect(labelOf(choices, "ParcelStatus", "x")).toBe("x");
    expect(labelOf(choices, "ParcelStatus", null)).toBe("–");
  });
});

describe("canEditMilestone", () => {
  it("Satgas hanya mengubah tonggak tanggung jawabnya", () => {
    const satgas = { canAdd: false, canChange: true };
    expect(canEditMilestone({ code: "inventory" }, satgas)).toBe(true);
    expect(canEditMilestone({ code: "release" }, satgas)).toBe(true);
    expect(canEditMilestone({ code: "location_decree" }, satgas)).toBe(false);
    expect(canEditMilestone({ code: null }, satgas)).toBe(false);
  });

  it("Pelaksana mengubah semua tonggak; tanpa izin ubah tidak ada", () => {
    const pelaksana = { canAdd: true, canChange: true };
    expect(canEditMilestone({ code: "location_decree" }, pelaksana)).toBe(true);
    expect(
      canEditMilestone(
        { code: "inventory" },
        { canAdd: false, canChange: false },
      ),
    ).toBe(false);
  });
});
