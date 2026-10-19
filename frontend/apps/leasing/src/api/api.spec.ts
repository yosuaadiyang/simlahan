import { describe, expect, it } from "vitest";
import apiReducer, { receiveError, clearError, initialState } from "./slice";
import { getApiErrorMessage, getApiErrorTitle } from "./ApiErrorModal";
import {
  INVALID_RESPONSE_MESSAGE,
  readResponseBody,
  SERVER_ERROR_MESSAGE,
} from "./responseBody";

describe("API", () => {
  describe("Reducer", () => {
    describe("apiReducer", () => {
      it("should update error", () => {
        const dummyError = {
          error: "test",
        };
        const newState = { ...initialState, error: dummyError };
        const state = apiReducer(initialState, receiveError(dummyError));
        expect(state).to.deep.equal(newState);
      });
      it("should clear error", () => {
        const dummyError = {
          error: "test",
        };
        const newState = { ...initialState, error: null };
        let state = apiReducer(initialState, receiveError(dummyError));
        state = apiReducer(state, clearError());
        expect(state).to.deep.equal(newState);
      });
    });
  });
  describe("readResponseBody", () => {
    it("parses JSON bodies", async () => {
      const response = new Response(JSON.stringify({ detail: "Ok" }), {
        status: 400,
      });
      expect(await readResponseBody(response)).toEqual({ detail: "Ok" });
    });
    it("does not fail on HTML error pages", async () => {
      const response = new Response("<html>Bad Gateway</html>", {
        status: 502,
      });
      expect(await readResponseBody(response)).toEqual({
        exception: 502,
        message: SERVER_ERROR_MESSAGE,
      });
      const notFound = new Response("<html></html>", { status: 404 });
      expect((await readResponseBody(notFound)).message).toBe(
        INVALID_RESPONSE_MESSAGE,
      );
    });
    it("uses an Indonesian message for server errors", async () => {
      const response = new Response("Internal Server Error", {
        status: 500,
        statusText: "Internal Server Error",
      });
      expect((await readResponseBody(response)).message).toBe(
        SERVER_ERROR_MESSAGE,
      );
    });
  });
  describe("ApiErrorModal texts", () => {
    it("translates redux-form validation errors", () => {
      const data = {
        message: "Submit Validation Failed",
        errors: { name: ["Bidang ini harus diisi."] },
      };
      expect(getApiErrorTitle(data)).toBe("Data tidak valid");
      expect(getApiErrorMessage(data)).toBe(
        "Validasi data gagal. Periksa isian berikut.",
      );
    });
    it("shows the DRF detail of wrapped request errors", () => {
      const data = {
        message: "Submit Validation Failed",
        errors: { detail: "Anda tidak memiliki izin.", get: "x" },
      };
      expect(getApiErrorMessage(data)).toBe("Anda tidak memiliki izin.");
      expect(getApiErrorTitle(data)).toBe("Permintaan gagal");
      expect(getApiErrorTitle({ ...data, errors: { detail: "Ditolak" } })).toBe(
        "Permintaan gagal",
      );
    });
    it("keeps other error messages", () => {
      const data = { exception: "500", message: "Galat" };
      expect(getApiErrorTitle(data)).toBe("Galat server 500");
      expect(getApiErrorMessage(data)).toBe("Galat");
    });
  });
});
