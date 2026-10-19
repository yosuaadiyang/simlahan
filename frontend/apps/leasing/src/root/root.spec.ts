import { describe, expect, it } from "vitest";
import { getExternalHomeHref, getHomeRouteId } from "./homeRoute";

describe("getHomeRouteId", () => {
  it("opens leases for lease officers", () => {
    expect(
      getHomeRouteId([
        { codename: "view_acquisitionproject" },
        { codename: "view_lease" },
      ]),
    ).toBe("leases");
  });
  it("opens the acquisition dashboard for acquisition-only users", () => {
    expect(getHomeRouteId([{ codename: "view_acquisitionproject" }])).toBe(
      "acquisition_dashboard",
    );
  });
  it("falls back to leases without matching permissions", () => {
    expect(getHomeRouteId([])).toBe("leases");
  });
});

describe("getExternalHomeHref", () => {
  it("stays in the app for users with an app page", () => {
    expect(
      getExternalHomeHref([
        { codename: "view_lease" },
        { codename: "view_korwil" },
      ]),
    ).toBeNull();
  });
  it("opens the command center for command-only users", () => {
    expect(
      getExternalHomeHref([
        { codename: "view_landasset" },
        { codename: "view_korwil" },
      ]),
    ).toBe("/komando/");
  });
  it("opens the allocation admin for allocation officers", () => {
    expect(getExternalHomeHref([{ codename: "view_application" }])).toBe(
      "/admin/alokasi/application/",
    );
  });
  it("does nothing without permissions", () => {
    expect(getExternalHomeHref([])).toBeNull();
  });
});
