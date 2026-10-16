import { isArray } from "lodash-es";
import * as L from "leaflet";
import "leaflet-draw";
import type { LatLngBounds } from "leaflet";

/**
 * Translate leaflet draw literals in Finnish
 */
export const localizeMap = (): void => {
  L.drawLocal.draw.handlers.circle.tooltip.start =
    "Klik dan seret untuk menggambar lingkaran";
  L.drawLocal.draw.handlers.circle.radius = "Radius";
  L.drawLocal.draw.handlers.polygon.tooltip.start =
    "Klik untuk mulai menggambar area.";
  L.drawLocal.draw.handlers.polygon.tooltip.cont =
    "Klik untuk melanjutkan menggambar area";
  L.drawLocal.draw.handlers.polygon.tooltip.end =
    "Klik titik pertama untuk menutup bentuk";
  L.drawLocal.draw.handlers.polyline.error =
    "<strong>Galat:</strong> sisi bidang tidak boleh saling berpotongan!";
  L.drawLocal.draw.handlers.polyline.tooltip.start =
    "Klik untuk mulai menggambar garis.";
  L.drawLocal.draw.handlers.polyline.tooltip.cont =
    "Klik untuk melanjutkan menggambar garis";
  L.drawLocal.draw.handlers.polyline.tooltip.end =
    "Klik titik terakhir untuk mengakhiri garis";
  L.drawLocal.draw.handlers.rectangle.tooltip.start =
    "Klik dan seret untuk menggambar persegi panjang";
  L.drawLocal.draw.handlers.simpleshape.tooltip.end =
    "Lepaskan tombol mouse untuk selesai menggambar.";
  L.drawLocal.edit.handlers.edit.tooltip.text =
    "Ubah bentuk dengan menyeret titik kendali";
  L.drawLocal.edit.handlers.edit.tooltip.subtext =
    "Klik tombol batal untuk membatalkan perubahan";
  L.drawLocal.edit.handlers.remove.tooltip.text =
    "Klik area untuk menghapusnya";
  L.drawLocal.draw.toolbar.actions.title = "Batalkan penggambaran";
  L.drawLocal.draw.toolbar.actions.text = "Batal";
  L.drawLocal.draw.toolbar.finish.title = "Selesai menggambar";
  L.drawLocal.draw.toolbar.finish.text = "Selesai";
  L.drawLocal.draw.toolbar.undo.title = "Hapus titik terakhir yang digambar";
  L.drawLocal.draw.toolbar.undo.text = "Hapus titik terakhir";
  L.drawLocal.edit.toolbar.actions.save.title = "Simpan perubahan";
  L.drawLocal.edit.toolbar.actions.save.text = "Simpan";
  L.drawLocal.edit.toolbar.actions.cancel.title = "Batalkan perubahan";
  L.drawLocal.edit.toolbar.actions.cancel.text = "Batal";
  L.drawLocal.edit.toolbar.actions.clearAll.title = "Hapus semua";
  L.drawLocal.edit.toolbar.actions.clearAll.text = "Hapus semua";
  L.drawLocal.draw.toolbar.buttons.polyline = "Gambar garis";
  L.drawLocal.draw.toolbar.buttons.polygon = "Gambar poligon";
  L.drawLocal.draw.toolbar.buttons.rectangle = "Gambar persegi panjang";
  L.drawLocal.draw.toolbar.buttons.circle = "Gambar lingkaran";
  L.drawLocal.edit.toolbar.buttons.editDisabled =
    "Tidak ada area yang dapat diubah";
  L.drawLocal.edit.toolbar.buttons.edit = "Ubah area";
  L.drawLocal.edit.toolbar.buttons.editDisabled =
    "Tidak ada area yang dapat diubah";
  L.drawLocal.edit.toolbar.buttons.remove = "Hapus area";
  L.drawLocal.edit.toolbar.buttons.removeDisabled =
    "Tidak ada area yang dapat dihapus";
};

/**
 * Get coordinates array from geometry
 * @param  geometry
 * @returns {Object[]}
 */
export const getCoordinatesOfGeometry = (
  geometry: any,
): Array<[number, number]> => {
  if (!geometry) {
    return [];
  }

  const getSingleArrayOfCoordinates = (items) => {
    let tempCoords = [];

    if (isArray(items) && !isArray(items[0])) {
      tempCoords.push([items[0], items[1]]);
    } else {
      items.forEach((item) => {
        tempCoords = [...tempCoords, ...getSingleArrayOfCoordinates(item)];
      });
    }

    return tempCoords;
  };

  return getSingleArrayOfCoordinates(geometry.coordinates);
};

/**
 * Format geojson coordinates to leaflet understandable format
 * @param  {Object} geojson
 * @returns {Object}
 */
export const formatCoordsToLatLng = (
  _geojson: Record<string, any> | null | undefined,
): (Record<string, any> | null | undefined) | null => {
  // Semua geometri dari API SimLahan berformat WGS84 (EPSG:4326) sehingga
  // konversi bawaan Leaflet (lng/lat) sudah tepat.
  return undefined;
};

/**
 * Get bounds for leaflet from bbox array
 * @param {Object[]} bbox
 * @returns {Object}
 */
export const getBoundsFromBBox = (bbox: Array<number>): LatLngBounds => {
  if (!bbox || !isArray(bbox) || bbox.length < 4) return null;
  const maxBoundsSouthWest = new L.LatLng(bbox[3], bbox[2]),
    maxBoundsNorthEast = new L.LatLng(bbox[1], bbox[0]);
  return new L.LatLngBounds(maxBoundsSouthWest, maxBoundsNorthEast);
};

/**
 * Get bounds for leaflet from coordinates
 * @param {Object[]} coordinates
 * @returns Object
 */
export const getBoundsFromCoordinates = (
  coordinates: Array<any>,
): LatLngBounds => {
  const lats = [],
    lons = [];
  coordinates.forEach((coordinate) => {
    lats.push(coordinate[0]);
    lons.push(coordinate[1]);
  });
  const minLat = Math.min(...lats),
    maxLat = Math.max(...lats),
    minLon = Math.min(...lons),
    maxLon = Math.max(...lons),
    maxBoundsSouthWest = new L.LatLng(minLon, minLat),
    maxBoundsNorthEast = new L.LatLng(maxLon, maxLat);
  return new L.LatLngBounds(maxBoundsSouthWest, maxBoundsNorthEast);
};

/**
 * Get bounds for leaflet from features object
 * @param {Object[]} leasesGeoJson
 * @returns Object
 */
export const getBoundsFromFeatures = (
  leasesGeoJson: Record<string, any>,
): Record<string, any> => {
  const lats = [],
    lons = [];
  if (leasesGeoJson && leasesGeoJson.features)
    leasesGeoJson.features.forEach((feature) => {
      if (feature.geometry && feature.geometry.coordinates)
        feature.geometry.coordinates.forEach((points) =>
          points.forEach((point) =>
            point.forEach((coordinate) => {
              lats.push(coordinate[0]);
              lons.push(coordinate[1]);
            }),
          ),
        );
    });
  if (lats.length < 1 || lons.length < 1) return null;
  const minLat = Math.min(...lats),
    maxLat = Math.max(...lats),
    minLon = Math.min(...lons),
    maxLon = Math.max(...lons),
    maxBoundsSouthWest = new L.LatLng(minLon, minLat),
    maxBoundsNorthEast = new L.LatLng(maxLon, maxLat);
  return new L.LatLngBounds(maxBoundsSouthWest, maxBoundsNorthEast);
};

/**
 * Get center for leaflet from coordinates
 * @param {Object[]} coordinates
 * @returns Object
 */
export const getCenterFromCoordinates = (
  coordinates: Array<any>,
): [number, number] => {
  const lats = [],
    lons = [];
  coordinates.forEach((coordinate) => {
    lats.push(coordinate[0]);
    lons.push(coordinate[1]);
  });
  const minLat = Math.min(...lats),
    maxLat = Math.max(...lats),
    minLon = Math.min(...lons),
    maxLon = Math.max(...lons),
    lat = maxLat - (maxLat - minLat) / 2,
    lng = maxLon - (maxLon - minLon) / 2;
  return [lng, lat];
};
export const getAreaFromGeoJSON = (geometry: Record<string, any>): number => {
  let area = 0;

  if (!geometry?.type) {
    return area;
  }

  switch (geometry.type) {
    case "GeometryCollection":
      geometry.geometries.forEach((geometry) => {
        area += getAreaFromGeoJSON(geometry);
      });
      break;

    case "MultiPolygon":
      L.GeoJSON.coordsToLatLngs(geometry.coordinates, 2).forEach((latLngs) => {
        latLngs.forEach((latLng) => {
          const polygonArea = L.GeometryUtil.geodesicArea(latLng);
          area += polygonArea;
        });
      });
      break;

    case "Polygon":
      L.GeoJSON.coordsToLatLngs(geometry.coordinates, 1).forEach((latLng) => {
        area = L.GeometryUtil.geodesicArea(latLng);
      });
      break;

    default:
      break;
  }

  return area;
};
