import store from "@/root/store";
import { getApiToken } from "@/auth/selectors";
import { refreshAccessToken } from "@/auth/session";
import { UI_ACCEPT_LANGUAGE_VALUE } from "@/api/constants";
import { readResponseBody } from "./responseBody";
import type { ApiSyncResponse } from "./types";
import type { ApiResponse } from "types";

const callApiAsync = async <T = ApiResponse>(
  request: Request,
  isRetry: boolean = false,
): Promise<ApiSyncResponse<T>> => {
  const apiToken = getApiToken(store.getState());
  const retryRequest = isRetry ? null : request.clone();

  if (apiToken) {
    request.headers.set("Authorization", `Bearer ${apiToken}`);
  }

  request.headers.set("Accept-Language", UI_ACCEPT_LANGUAGE_VALUE);

  if (
    request.method === "PATCH" ||
    request.method === "POST" ||
    request.method === "PUT"
  ) {
    request.headers.set("Content-Type", "application/json");
  }

  const response = await fetch(request);
  if (response.status === 401 && apiToken && retryRequest) {
    const newToken = await refreshAccessToken();
    if (newToken) return callApiAsync<T>(retryRequest, true);
  }
  const bodyAsJson = await readResponseBody(response);
  return {
    response,
    bodyAsJson,
  };
};

export default callApiAsync;
