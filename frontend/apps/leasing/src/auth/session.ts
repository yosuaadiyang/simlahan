/**
 * Manajemen sesi JWT (login lokal SimLahan).
 *
 * - Access token hanya disimpan di memori (Redux).
 * - Refresh token disimpan di localStorage agar sesi bertahan saat halaman
 *   dimuat ulang; dirotasi setiap kali dipakai dan di-blacklist saat logout.
 */
import store from "@/root/store";
import createUrl from "@/api/createUrl";
import { UI_ACCEPT_LANGUAGE_VALUE } from "@/api/constants";
import {
  clearApiToken,
  clearUser,
  receiveApiToken,
  userFound,
} from "./actions";
import {
  ACCESS_TOKEN_RENEW_MARGIN_SECONDS,
  REFRESH_TOKEN_STORAGE_KEY,
} from "./constants";
import type { AuthUser, TokenPair } from "./types";

let renewTimer: ReturnType<typeof setTimeout> | null = null;
let refreshInFlight: Promise<string | null> | null = null;

export class LoginError extends Error {}

/** Login perlu langkah kedua: kode OTP yang dikirim ke surel petugas. */
export class OtpRequiredError extends Error {
  otpToken: string;
  email: string;

  constructor(otpToken: string, email: string) {
    super("Masukkan kode OTP yang dikirim ke surel Anda.");
    this.otpToken = otpToken;
    this.email = email;
  }
}

const readRefreshToken = (): string | null => {
  try {
    return localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
};

const writeRefreshToken = (token: string | null) => {
  try {
    if (token) localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, token);
    else localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
  } catch {
    // localStorage tidak tersedia (mode privat): sesi hanya di memori.
  }
};

/** Ambil klaim `exp` (detik epoch) dari JWT tanpa memverifikasi tanda tangan. */
export const getTokenExpiry = (token: string): number | null => {
  try {
    const payload = token.split(".")[1];
    const json = JSON.parse(
      atob(payload.replace(/-/g, "+").replace(/_/g, "/")),
    );
    return typeof json.exp === "number" ? json.exp : null;
  } catch {
    return null;
  }
};

const postJson = async (path: string, body: Record<string, any>) => {
  const response = await fetch(
    new Request(createUrl(path), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept-Language": UI_ACCEPT_LANGUAGE_VALUE,
      },
      body: JSON.stringify(body),
    }),
  );
  let data: Record<string, any> = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }
  return { response, data };
};

export const normalizeUser = (data: Record<string, any>): AuthUser => ({
  ...(data as AuthUser),
  profile: {
    sub: data.uuid,
    name: data.name || data.username,
    email: data.email,
  },
});

const scheduleRenewal = (accessToken: string) => {
  if (renewTimer) clearTimeout(renewTimer);
  const exp = getTokenExpiry(accessToken);
  if (!exp) return;
  const delay = Math.max(
    (exp - ACCESS_TOKEN_RENEW_MARGIN_SECONDS) * 1000 - Date.now(),
    5000,
  );
  renewTimer = setTimeout(() => {
    refreshAccessToken();
  }, delay);
};

const applyTokens = (tokens: TokenPair) => {
  if (tokens.refresh) writeRefreshToken(tokens.refresh);
  store.dispatch(receiveApiToken(tokens.access));
  scheduleRenewal(tokens.access);
};

export const clearSession = () => {
  if (renewTimer) clearTimeout(renewTimer);
  renewTimer = null;
  writeRefreshToken(null);
  store.dispatch(clearApiToken());
  store.dispatch(clearUser());
};

/**
 * Perbarui access token memakai refresh token. Panggilan bersamaan berbagi
 * satu permintaan. Mengembalikan access token baru atau null (sesi berakhir).
 */
export const refreshAccessToken = (): Promise<string | null> => {
  if (refreshInFlight) return refreshInFlight;
  const refresh = readRefreshToken();
  if (!refresh) return Promise.resolve(null);
  refreshInFlight = (async () => {
    try {
      const { response, data } = await postJson("auth/refresh/", { refresh });
      if (!response.ok || !data.access) {
        clearSession();
        return null;
      }
      applyTokens({ access: data.access, refresh: data.refresh });
      return data.access as string;
    } catch {
      // Jaringan bermasalah: pertahankan sesi, coba lagi nanti.
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
};

const fetchCurrentUser = async (accessToken: string): Promise<AuthUser> => {
  const response = await fetch(
    new Request(createUrl("auth/me/"), {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Accept-Language": UI_ACCEPT_LANGUAGE_VALUE,
      },
    }),
  );
  if (!response.ok) throw new LoginError("Sesi tidak valid.");
  return normalizeUser(await response.json());
};

const TOO_MANY_ATTEMPTS =
  "Terlalu banyak percobaan masuk. Coba lagi dalam satu menit.";

const completeLogin = (data: Record<string, any>): AuthUser => {
  applyTokens({ access: data.access, refresh: data.refresh });
  const user = normalizeUser(data.user);
  store.dispatch(userFound(user));
  return user;
};

export const login = async (
  username: string,
  password: string,
): Promise<AuthUser> => {
  const { response, data } = await postJson("auth/login/", {
    username,
    password,
  });
  if (!response.ok) {
    if (response.status === 429) {
      throw new LoginError(TOO_MANY_ATTEMPTS);
    }
    throw new LoginError(data.detail || "Nama pengguna atau kata sandi salah.");
  }
  if (data.otp_required) {
    throw new OtpRequiredError(data.otp_token, data.email || "");
  }
  return completeLogin(data);
};

/** Langkah kedua login: tukar kode OTP dengan token sesi. */
export const verifyOtp = async (
  otpToken: string,
  code: string,
): Promise<AuthUser> => {
  const { response, data } = await postJson("auth/login/otp/", {
    otp_token: otpToken,
    code,
  });
  if (!response.ok) {
    if (response.status === 429) {
      throw new LoginError(TOO_MANY_ATTEMPTS);
    }
    throw new LoginError(
      data.detail || "Kode OTP salah atau sudah kedaluwarsa.",
    );
  }
  return completeLogin(data);
};

/** Pulihkan sesi dari refresh token tersimpan (saat aplikasi dimuat). */
export const restoreSession = async (): Promise<AuthUser | null> => {
  const access = await refreshAccessToken();
  if (!access) return null;
  try {
    const user = await fetchCurrentUser(access);
    store.dispatch(userFound(user));
    return user;
  } catch {
    clearSession();
    return null;
  }
};

export const logout = async () => {
  const refresh = readRefreshToken();
  clearSession();
  if (refresh) {
    try {
      await postJson("auth/logout/", { refresh });
    } catch {
      // Abaikan: token tetap akan kedaluwarsa.
    }
  }
};

export const hasStoredSession = (): boolean => Boolean(readRefreshToken());
