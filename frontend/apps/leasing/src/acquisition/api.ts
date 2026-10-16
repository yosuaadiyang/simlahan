/**
 * Klien API modul pengadaan tanah (/v1/pengadaan/...).
 *
 * Memakai token JWT dari store; bila server membalas 401, access token
 * diperbarui sekali lalu permintaan diulang.
 */
import store from "@/root/store";
import createUrl from "@/api/createUrl";
import { UI_ACCEPT_LANGUAGE_VALUE } from "@/api/constants";
import { getApiToken } from "@/auth/selectors";
import { refreshAccessToken } from "@/auth/session";

export type ApiErrorBody = Record<string, any> | null;

export class ApiRequestError extends Error {
  status: number;
  body: ApiErrorBody;

  constructor(status: number, body: ApiErrorBody) {
    super(extractErrorMessage(body) || `Galat server (${status})`);
    this.status = status;
    this.body = body;
  }
}

/** Ringkas pesan galat DRF menjadi satu kalimat. */
export const extractErrorMessage = (body: ApiErrorBody): string => {
  if (!body) return "";
  if (typeof body === "string") return body;
  if (body.detail) return String(body.detail);
  if (Array.isArray(body.non_field_errors)) {
    return body.non_field_errors.join(" ");
  }
  const first = Object.entries(body)[0];
  if (!first) return "";
  const [key, value] = first;
  const text = Array.isArray(value) ? value.join(" ") : String(value);
  return key === "non_field_errors" ? text : `${key}: ${text}`;
};

const buildUrl = (path: string, params?: Record<string, any>): string => {
  const cleaned: Record<string, any> = {};
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      cleaned[key] = value;
    }
  });
  return createUrl(path, Object.keys(cleaned).length ? cleaned : undefined);
};

const doFetch = async (
  makeRequest: () => Request,
  isRetry = false,
): Promise<Response> => {
  const request = makeRequest();
  const token = getApiToken(store.getState());
  if (token) request.headers.set("Authorization", `Bearer ${token}`);
  request.headers.set("Accept-Language", UI_ACCEPT_LANGUAGE_VALUE);
  const response = await fetch(request);
  if (response.status === 401 && token && !isRetry) {
    const renewed = await refreshAccessToken();
    if (renewed) return doFetch(makeRequest, true);
  }
  return response;
};

const parseBody = async (response: Response): Promise<any> => {
  if (response.status === 204) return null;
  const type = response.headers.get("Content-Type") || "";
  if (type.includes("application/json")) return response.json();
  return response.text();
};

export const apiGet = async <T = any>(
  path: string,
  params?: Record<string, any>,
): Promise<T> => {
  const url = buildUrl(path, params);
  const response = await doFetch(() => new Request(url));
  const body = await parseBody(response);
  if (!response.ok) throw new ApiRequestError(response.status, body);
  return body as T;
};

export const apiSend = async <T = any>(
  method: "POST" | "PATCH" | "PUT" | "DELETE",
  path: string,
  data?: Record<string, any>,
): Promise<T> => {
  const url = buildUrl(path);
  const response = await doFetch(
    () =>
      new Request(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: data === undefined ? undefined : JSON.stringify(data),
      }),
  );
  const body = await parseBody(response);
  if (!response.ok) throw new ApiRequestError(response.status, body);
  return body as T;
};

export const apiUpload = async <T = any>(
  path: string,
  formData: FormData,
  method: "POST" | "PATCH" = "POST",
): Promise<T> => {
  const url = buildUrl(path);
  const response = await doFetch(
    () => new Request(url, { method, body: formData }),
  );
  const body = await parseBody(response);
  if (!response.ok) throw new ApiRequestError(response.status, body);
  return body as T;
};

/** Metadata kolom (DRF OPTIONS) sebuah endpoint. */
export const apiOptions = async (
  path: string,
): Promise<Record<string, any>> => {
  const url = buildUrl(path);
  const response = await doFetch(() => new Request(url, { method: "OPTIONS" }));
  const body = await parseBody(response);
  if (!response.ok) throw new ApiRequestError(response.status, body);
  return body;
};

/** Unduh berkas biner (xlsx, pdf, dokumen) lalu simpan di perangkat. */
export const apiDownload = async (
  path: string,
  fallbackName: string,
): Promise<void> => {
  const url = buildUrl(path);
  const response = await doFetch(() => new Request(url));
  if (!response.ok) {
    throw new ApiRequestError(response.status, await parseBody(response));
  }
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
  const name = match ? decodeURIComponent(match[1]) : fallbackName;
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
};

/** Ambil seluruh halaman hasil (LimitOffsetPagination). */
export const apiGetAll = async <T = any>(
  path: string,
  params?: Record<string, any>,
  pageSize = 500,
): Promise<Array<T>> => {
  const results: Array<T> = [];
  let offset = 0;
  // Batas aman agar tidak berulang tanpa akhir.
  for (let i = 0; i < 100; i++) {
    const page = await apiGet<any>(path, {
      ...params,
      limit: pageSize,
      offset,
    });
    if (Array.isArray(page)) return page as Array<T>;
    results.push(...(page?.results || []));
    if (!page?.next) break;
    offset += pageSize;
  }
  return results;
};
