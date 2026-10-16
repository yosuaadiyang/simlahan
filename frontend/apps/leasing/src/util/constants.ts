const envNumber = (value: string | undefined, fallback: number): number => {
  const parsed = Number(value);
  return value !== undefined && value !== "" && Number.isFinite(parsed)
    ? parsed
    : fallback;
};

/**
 * Pusat peta awal (WGS84). Default: tengah Indonesia; atur lewat
 * VITE_MAP_CENTER_LAT / VITE_MAP_CENTER_LNG.
 * @readonly
 * @const {{lat: number, lng: number}}
 */
export const DEFAULT_CENTER = {
  lat: envNumber(import.meta.env.VITE_MAP_CENTER_LAT, -2.5),
  lng: envNumber(import.meta.env.VITE_MAP_CENTER_LNG, 118),
};

/**
 * Zoom awal peta (Web Mercator / EPSG:3857).
 * @readonly
 * @const {number}
 */
export const DEFAULT_ZOOM = envNumber(import.meta.env.VITE_MAP_DEFAULT_ZOOM, 5);

/**
 * Zoom minimum
 * @readonly
 * @const {number}
 */
export const MIN_ZOOM = 4;

/**
 * Zoom maksimum
 * @readonly
 * @const {number}
 */
export const MAX_ZOOM = 19;

/**
 * Layer WMS tambahan opsional (mis. peta bidang atau RDTR instansi).
 */
export const MAP_WMS = {
  url: import.meta.env.VITE_MAP_WMS_URL || "",
  layers: import.meta.env.VITE_MAP_WMS_LAYERS || "",
  name: import.meta.env.VITE_MAP_WMS_NAME || "Peta instansi",
};

/**
 * Map color palette
 * @readonly
 * @const {string[]}
 */
export const MAP_COLORS = [
  "#0078C0",
  "#FF9800",
  "#1976D2",
  "#D32F2F",
  "#E040FB",
  "#FF4081",
  "#512DA8",
  "#536DFE",
  "#F57C00",
  "#E64A19",
  "#8BC34A",
  "#689F38",
  "#FFC107",
  "#CDDC39",
];

/**
 * Delete modal button text
 * @readonly
 * @const {string}
 */
export const DELETE_MODAL_BUTTON_TEXT = "Hapus";

/**
 * Maximum number of results per page on list tables
 * @readonly
 * @const {number}
 */
export const LIST_TABLE_PAGE_SIZE = 25;
