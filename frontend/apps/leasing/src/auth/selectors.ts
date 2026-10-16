import type { Selector } from "@/types";
import type { ApiToken, AuthUser } from "./types";

export const getApiToken: Selector<ApiToken, void> = (
  state: Record<string, any>,
): string => state.auth.apiToken || "";

export const getLoggedInUser: Selector<Record<string, any>, void> = (
  state: Record<string, any>,
): AuthUser | null => state.auth.user || null;
