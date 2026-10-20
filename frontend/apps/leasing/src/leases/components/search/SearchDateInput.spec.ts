import { describe, expect, it } from "vitest";
import { formatSearchDate, parseSearchDate } from "./SearchDateInput";

describe("SearchDateInput", () => {
  it("parses search dates written with dots", () => {
    expect(parseSearchDate("1.2.2026")).toEqual(new Date(2026, 1, 1));
    expect(parseSearchDate("01.02.2026")).toEqual(new Date(2026, 1, 1));
    expect(parseSearchDate("bukan tanggal")).toBeNull();
    expect(parseSearchDate("")).toBeNull();
  });
  it("formats dates as dd.mm.yyyy", () => {
    expect(formatSearchDate(new Date(2026, 1, 1))).toBe("01.02.2026");
    expect(formatSearchDate(null)).toBe("");
  });
});
