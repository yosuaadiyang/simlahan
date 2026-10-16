import { useEffect } from "react";
import { useLeaflet } from "react-leaflet";
import type { Map } from "leaflet";
import { GeoSearchControl, OpenStreetMapProvider } from "leaflet-geosearch";

const GeoSearch = (): null => {
  const leaflet = useLeaflet();
  const map: Map = leaflet.map;

  useEffect(() => {
    if (!map) return;

    const geoSearchControl = GeoSearchControl({
      position: "topright",
      style: "bar",
      showMarker: false,
      provider: new OpenStreetMapProvider({
        params: {
          countrycodes: "id",
          "accept-language": "id",
        },
      }),
      showPopup: false,
      autoClose: true,
      retainZoomLevel: false,
      animateZoom: true,
      keepResult: false,
      searchLabel: "Cari alamat atau tempat",
      zoomLevel: 17,
    });

    map.addControl(geoSearchControl);

    return () => {
      map.removeControl(geoSearchControl);
    };
  }, [map]);

  return null;
};

export default GeoSearch;
