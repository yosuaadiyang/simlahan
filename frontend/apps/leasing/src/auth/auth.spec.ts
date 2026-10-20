import { describe, expect, it, vi } from "vitest";
import {
  clearApiToken,
  receiveApiToken,
  userFound,
  clearUser,
} from "./actions";
import { authReducer } from "./reducer";
import {
  OtpRequiredError,
  clearKomandoDeviceData,
  getTokenExpiry,
  login,
  normalizeUser,
  verifyOtp,
} from "./session";
import type { AuthUser } from "./types";

vi.mock("@/root/store", () => ({
  default: { dispatch: vi.fn(), getState: vi.fn() },
}));
vi.mock("@/api/createUrl", () => ({
  default: (url: string) => `http://localhost/v1/${url}`,
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

  describe("Login with OTP", () => {
    const respond = (status: number, body: Record<string, any>) =>
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(body), {
          status,
          headers: { "Content-Type": "application/json" },
        }),
      );

    it("asks for an OTP code when the server requires one", async () => {
      vi.stubGlobal(
        "fetch",
        respond(200, {
          otp_required: true,
          otp_token: "6a0f0c5e-7d1b-4f0e-9a51-1f5f1d7b8c11",
          email: "b***@example.go.id",
        }),
      );
      const error = await login("petugas", "rahasia").catch((e) => e);
      expect(error).toBeInstanceOf(OtpRequiredError);
      expect(error.otpToken).toBe("6a0f0c5e-7d1b-4f0e-9a51-1f5f1d7b8c11");
      expect(error.email).toBe("b***@example.go.id");
      vi.unstubAllGlobals();
    });

    it("completes the login with a valid OTP code", async () => {
      const fetchMock = respond(200, {
        access: makeJwt({ exp: 1893456000 }),
        refresh: "refresh-token",
        user: getMockUser(),
      });
      vi.stubGlobal("fetch", fetchMock);
      const user = await verifyOtp(
        "6a0f0c5e-7d1b-4f0e-9a51-1f5f1d7b8c11",
        "123456",
      );
      expect(user.username).toBe("petugas");
      const request = fetchMock.mock.calls[0][0] as Request;
      expect(request.url).toContain("/auth/login/otp/");
      expect(JSON.parse(await request.text())).toEqual({
        otp_token: "6a0f0c5e-7d1b-4f0e-9a51-1f5f1d7b8c11",
        code: "123456",
      });
      vi.unstubAllGlobals();
    });

    it("rejects a wrong OTP code with the server message", async () => {
      vi.stubGlobal(
        "fetch",
        respond(401, { detail: "Kode OTP salah atau sudah kedaluwarsa." }),
      );
      await expect(verifyOtp("token", "000000")).rejects.toThrow(
        "Kode OTP salah atau sudah kedaluwarsa.",
      );
      vi.unstubAllGlobals();
    });
  });
});

describe("clearKomandoDeviceData", () => {
  it("menghapus cache & antrean luring pusat komando saja", async () => {
    const deleted: string[] = [];
    vi.stubGlobal("caches", {
      keys: async () => ["komando-shell-4", "komando-data-4", "lain-1"],
      delete: async (key: string) => {
        deleted.push(key);
        return true;
      },
    });
    const deleteDatabase = vi.fn();
    vi.stubGlobal("indexedDB", { deleteDatabase });
    await clearKomandoDeviceData();
    expect(deleted.sort()).toEqual(["komando-data-4", "komando-shell-4"]);
    expect(deleteDatabase).toHaveBeenCalledWith("simlahan-komando");
    vi.unstubAllGlobals();
  });

  it("tidak gagal bila penyimpanan peramban tidak tersedia", async () => {
    vi.stubGlobal("caches", {
      keys: async () => {
        throw new Error("diblokir");
      },
    });
    await expect(clearKomandoDeviceData()).resolves.toBeUndefined();
    vi.unstubAllGlobals();
  });
});
