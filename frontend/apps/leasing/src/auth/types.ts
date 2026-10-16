import type { Action } from "@/types";

export type ApiToken = string | null;
export type AuthState = string | null;

/** Pengguna yang sedang login (respons /v1/auth/me/). */
export type AuthUser = {
  id: number;
  uuid: string;
  username: string;
  first_name: string;
  last_name: string;
  name: string;
  email: string;
  is_superuser: boolean;
  is_staff: boolean;
  groups: Array<string>;
  service_units: Array<Record<string, any>>;
  /** Kompatibilitas dengan komponen lama yang membaca `profile.name/email`. */
  profile: {
    sub: string;
    name: string;
    email: string;
  };
};

export type TokenPair = {
  access: string;
  refresh?: string;
};

export type ReceiveApiTokenAction = Action<string, string>;
export type ClearApiTokenAction = Action<string, void>;
export type ReceiveUserAction = Action<string, AuthUser | null>;
