import { call, select } from "redux-saga/effects";
import { getApiToken } from "@/auth/selectors";
import { refreshAccessToken } from "@/auth/session";
import { UI_ACCEPT_LANGUAGE_VALUE } from "@/api/constants";

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

  switch (status) {
    case 204:
      return {
        response,
      };

    case 500:
      return {
        response,
        bodyAsJson: {
          exception: response.status,
          message: response.statusText,
        },
      };
  }

  const bodyAsJson = yield call([response, response.json]);
  return {
    response,
    bodyAsJson,
  };
}

export default callApi;
