import { call, put, select } from "redux-saga/effects";
import { receiveError } from "@/api/slice";
import { getApiToken } from "@/auth/selectors";
import { refreshAccessToken } from "@/auth/session";
import { UI_ACCEPT_LANGUAGE_VALUE } from "@/api/constants";

function* callUploadRequest(
  request: Request,
  isRetry: boolean = false,
): Generator<any, any, any> {
  const apiToken = yield select(getApiToken);
  const retryRequest = isRetry ? null : request.clone();

  if (apiToken) {
    request.headers.set("Authorization", `Bearer ${apiToken}`);
  }

  request.headers.set("Accept-Language", UI_ACCEPT_LANGUAGE_VALUE);
  const response = yield call(fetch, request);
  const status = response.status;

  if (status === 401 && apiToken && retryRequest) {
    const newToken = yield call(refreshAccessToken);
    if (newToken) {
      return yield call(callUploadRequest, retryRequest, true);
    }
  }

  const bodyAsJson = yield call([response, response.json]);

  if (status === 500) {
    yield put(receiveError(bodyAsJson));
  }

  return {
    response,
    bodyAsJson,
  };
}

export default callUploadRequest;
