import { call, select } from "redux-saga/effects";
import { getApiToken } from "@/auth/selectors";
import { refreshAccessToken } from "@/auth/session";
import { UI_ACCEPT_LANGUAGE_VALUE } from "@/api/constants";
import { readResponseBody } from "./responseBody";

function* callApi(
  request: Request,
  isRetry: boolean = false,
): Generator<any, any, any> {
  const apiToken = yield select(getApiToken);
  // Simpan salinan untuk percobaan ulang setelah token diperbarui.
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

  const response = yield call(fetch, request);
  const status = response.status;

  if (status === 401 && apiToken && retryRequest) {
    const newToken = yield call(refreshAccessToken);
    if (newToken) {
      return yield call(callApi, retryRequest, true);
    }
  }

  if (status === 204) {
    return {
      response,
    };
  }

  const bodyAsJson = yield call(readResponseBody, response);
  return {
    response,
    bodyAsJson,
  };
}

export default callApi;
