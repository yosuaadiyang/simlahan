import { describe, expect, it, vi } from "vitest";
import {
  clearApiToken,
  receiveApiToken,
  userFound,
  clearUser,
} from "./actions";
import { authReducer } from "./reducer";
import { getTokenExpiry, normalizeUser } from "./session";
import type { AuthUser } from "./types";

vi.mock("@/root/store", () => ({
  default: { dispatch: vi.fn(), getState: vi.fn() },
}));

const getMockUser = (): AuthUser =>
  normalizeUser({
    id: 1,
    uuid: "0b4a0c3e-3c55-4d0f-9f7f-6a2c1f1d2e3f",
    username: "petugas",
    first_name: "Budi",
    last_name: "Santoso",
    name: "Budi Santoso",
    email: "budi@example.go.id",
    is_superuser: false,
    is_staff: false,
    groups: ["Pelaksana Pengadaan"],
    service_units: [],
  });

const makeJwt = (payload: Record<string, any>) =>
  ["header", btoa(JSON.stringify(payload)), "signature"].join(".");

describe("Auth", () => {
  describe("Reducer", () => {
    it("should set user", () => {
      const mockUser = getMockUser();
      const state = authReducer({ user: "" }, userFound(mockUser));
      expect(state).to.deep.equal({ user: mockUser, apiToken: "" });
    });
    it("should clear user", () => {
      const state = authReducer(
        { user: getMockUser(), apiToken: "" },
        clearUser(),
      );
      expect(state).to.deep.equal({ user: "", apiToken: "" });
    });
    it("should update apiToken", () => {
      const state = authReducer({}, receiveApiToken("token-123"));
      expect(state).to.deep.equal({ apiToken: "token-123", user: "" });
    });
    it("should clear apiToken", () => {
      let state = authReducer({}, receiveApiToken("token-123"));
      state = authReducer(state, clearApiToken());
      expect(state).to.deep.equal({ apiToken: "", user: "" });
    });
  });

  describe("Session helpers", () => {
    it("exposes a profile compatible with legacy components", () => {
      const user = getMockUser();
      expect(user.profile).to.deep.equal({
        sub: user.uuid,
        name: "Budi Santoso",
        email: "budi@example.go.id",
      });
    });
    it("reads the expiry claim of a JWT", () => {
      expect(getTokenExpiry(makeJwt({ exp: 1893456000 }))).toBe(1893456000);
      expect(getTokenExpiry("not-a-jwt")).toBe(null);
    });
  });
});
