import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet, apiGetAll, apiOptions } from "./api";
import type { ChoiceMap, FieldMeta } from "./types";

type AsyncState<T> = {
  data: T | null;
  error: string | null;
  isLoading: boolean;
  reload: () => void;
};

/** Ambil data dari API; muat ulang saat `deps` berubah atau `reload()` dipanggil. */
export const useApi = <T = any>(
  loader: (() => Promise<T>) | null,
  deps: Array<unknown>,
): AsyncState<T> => {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(Boolean(loader));
  const [nonce, setNonce] = useState(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  useEffect(() => {
    let cancelled = false;
    const current = loaderRef.current;
    if (!current) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    current()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message || "Gagal memuat data.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data, error, isLoading, reload };
};

const metadataCache: Record<string, Promise<Record<string, FieldMeta>>> = {};

/** Metadata kolom (OPTIONS) sebuah endpoint pengadaan, di-cache per sesi. */
export const useFieldMeta = (endpoint: string) =>
  useApi<Record<string, FieldMeta>>(() => {
    if (!metadataCache[endpoint]) {
      metadataCache[endpoint] = optionsRequest(endpoint).catch((e) => {
        delete metadataCache[endpoint];
        throw e;
      });
    }
    return metadataCache[endpoint];
  }, [endpoint]);

const optionsRequest = async (
  endpoint: string,
): Promise<Record<string, FieldMeta>> => {
  const data = await apiOptions(endpoint);
  return (data?.fields || {}) as Record<string, FieldMeta>;
};

let choicesPromise: Promise<ChoiceMap> | null = null;

/** Label pilihan (enum) modul pengadaan dari /pengadaan/choices/. */
export const useChoices = () =>
  useApi<ChoiceMap>(() => {
    if (!choicesPromise) {
      choicesPromise = apiGet<ChoiceMap>("pengadaan/choices/").catch((e) => {
        choicesPromise = null;
        throw e;
      });
    }
    return choicesPromise;
  }, []);

let municipalitiesPromise: Promise<Array<Record<string, any>>> | null = null;

export const useMunicipalities = () =>
  useApi<Array<Record<string, any>>>(() => {
    if (!municipalitiesPromise) {
      municipalitiesPromise = apiGetAll("municipality/", {}, 1000).catch(
        (e) => {
          municipalitiesPromise = null;
          throw e;
        },
      );
    }
    return municipalitiesPromise;
  }, []);

export const useDistricts = (municipalityId?: number | null) =>
  useApi<Array<Record<string, any>>>(
    municipalityId
      ? () => apiGetAll("district/", { municipality: municipalityId }, 1000)
      : null,
    [municipalityId],
  );

export const useUsers = () =>
  useApi<Array<Record<string, any>>>(() => apiGetAll("user/", {}, 500), []);
