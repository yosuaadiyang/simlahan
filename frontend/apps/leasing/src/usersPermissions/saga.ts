import { all, call, fork, put, takeLatest } from "redux-saga/effects";
import {
  fetchUsersPermissions as fetchUsersPermissionsAction,
  receiveUserGroups,
  receiveUsersPermissions,
  receiveUserServiceUnits,
  setUserActiveServiceUnit,
  notFound,
} from "./slice";
import { fetchUsersPermissions } from "./requests";
import { receiveError } from "@/api/slice";

function* fetchUsersPermissionsSaga(): Generator<any, any, any> {
  try {
    const {
      response: { status: statusCode },
      bodyAsJson,
    } = yield call(fetchUsersPermissions);

    switch (statusCode) {
      case 200:
        yield put(receiveUserGroups(bodyAsJson.groups));
        yield put(receiveUserServiceUnits(bodyAsJson.service_units));
        yield put(receiveUsersPermissions(bodyAsJson.permissions));
        if (!bodyAsJson.service_units[0]) {
          yield put(
            receiveError(
              new Error(
                `Pengguna belum memiliki unit layanan. Coba muat ulang halaman, lalu hubungi administrator untuk mengatur grup pengguna yang benar.`,
              ),
            ),
          );
        } else {
          yield put(setUserActiveServiceUnit(bodyAsJson.service_units[0]));
        }
        break;

      default:
        yield put(receiveError(bodyAsJson));
        yield put(notFound());
        break;
    }
  } catch (error) {
    console.error('Failed to fetch users permissions with error "%s"', error);
    yield put(notFound());
    yield put(receiveError(error));
  }
}

export default function* (): Generator<any, any, any> {
  yield all([
    fork(function* (): Generator<any, any, any> {
      yield takeLatest(fetchUsersPermissionsAction, fetchUsersPermissionsSaga);
    }),
  ]);
}
