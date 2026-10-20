import { describe, expect, it } from "vitest";
import {
  fetchIntendedUse,
  intendedUseNotFound,
  receiveIntendedUse,
} from "./actions";
import intendedUseReducer from "./reducer";
import type { IntendedUseState } from "./types";

const defaultState: IntendedUseState = {
  isFetched: false,
  isFetching: false,
  list: [],
};

describe("Intended use", () => {
  describe("Reducer", () => {
    it("should set isFetching when fetching", () => {
      const state = intendedUseReducer({}, fetchIntendedUse());
      expect(state).to.deep.equal({ ...defaultState, isFetching: true });
    });
    it("should mark an empty list as fetched so it is not requested again", () => {
      let state = intendedUseReducer({}, fetchIntendedUse());
      state = intendedUseReducer(state, receiveIntendedUse([]));
      expect(state).to.deep.equal({ ...defaultState, isFetched: true });
    });
    it("should mark the list as fetched when the request fails", () => {
      let state = intendedUseReducer({}, fetchIntendedUse());
      state = intendedUseReducer(state, intendedUseNotFound());
      expect(state).to.deep.equal({ ...defaultState, isFetched: true });
    });
  });
});
