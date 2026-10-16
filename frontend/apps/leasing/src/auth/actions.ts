import { createAction } from "redux-actions";
import type { Action } from "redux";
import type {
  AuthUser,
  ClearApiTokenAction,
  ReceiveApiTokenAction,
} from "./types";

export const clearApiToken = (): ClearApiTokenAction =>
  createAction("mvj/auth/CLEAR_API_TOKEN")();
export const receiveApiToken = (token: string): ReceiveApiTokenAction =>
  createAction("mvj/auth/RECEIVE_API_TOKEN")(token);
export const userFound = (user: AuthUser): Action<string> =>
  createAction("mvj/auth/USER_FOUND")({ ...user });
export const clearUser = (): Action<string> =>
  createAction("mvj/auth/CLEAR_USER")();
