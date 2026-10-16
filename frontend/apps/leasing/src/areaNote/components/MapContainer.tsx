import React, { useCallback, useEffect, useRef } from "react";
import {
  LayersControl,
  LayerGroup,
  Map,
  TileLayer,
  WMSTileLayer,
  ZoomControl,
} from "react-leaflet";

const { BaseLayer, Overlay } = LayersControl;

import FullscreenControl from "react-leaflet-fullscreen";
import GeoSearch from "@/components/map/GeoSearch";
import Loader from "@/components/loader/Loader";
import LoaderWrapper from "@/components/loader/LoaderWrapper";
import ZoomBox from "@/components/map/ZoomBox";
import { MAP_WMS, MIN_ZOOM, MAX_ZOOM } from "@/util/constants";

// Peta memakai Web Mercator (EPSG:3857, bawaan Leaflet); data dari API dalam
// WGS84 (EPSG:4326).

type Props = {
  bounds?: Record<string, any>;
  center: Record<string, any>;
  children: React.ReactNode;
  isLoading?: boolean;
  onMapDidMount?: (...args: Array<any>) => any;
  onViewportChanged?: (...args: Array<any>) => any;
  overlayLayers?: Array<Record<string, any>>;
  zoom: number;
  enableSearch?: boolean;
  onMapRefAvailable?: (...args: Array<any>) => any;
};

const MapContainer: React.FC<Props> = ({
  bounds,
  center,
  children,
  isLoading,
  onMapDidMount,
  onViewportChanged,
  overlayLayers,
  zoom,
  enableSearch = true,
  onMapRefAvailable,
}) => {
  const mapRef = useRef<any>(null);

  const setMapRef = useCallback(
    (el: any) => {
      mapRef.current = el;
      onMapRefAvailable?.(el);
    },
    [onMapRefAvailable],
  );

  const getMapValues = useCallback((): Record<string, any> => {
    return {
      bBox: mapRef.current.leafletElement.getBounds().toBBoxString(),
      zoom: mapRef.current.leafletElement.getZoom(),
    };
  }, []);

  useEffect(() => {
    if (mapRef.current && onMapDidMount) {
      onMapDidMount(getMapValues());
    }
  }, [getMapValues, onMapDidMount]);

  const handleViewportChanged = useCallback(() => {
    if (mapRef.current && onViewportChanged) {
      onViewportChanged(getMapValues());
    }
  }, [getMapValues, onViewportChanged]);

  return (
    <Map
      ref={setMapRef}
      center={center || undefined}
      bounds={bounds || undefined}
      maxBoundsViscosity={0}
      minZoom={MIN_ZOOM}
      maxZoom={MAX_ZOOM}
      zoom={zoom}
      zoomControl={false}
      boxZoom={false}
      onViewportChanged={handleViewportChanged}
    >
      {isLoading && (
        <LoaderWrapper className="relative-overlay-wrapper">
          <Loader isLoading={true} />
        </LoaderWrapper>
      )}
      <LayersControl position="topright">
        <BaseLayer checked name="OpenStreetMap">
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            maxZoom={MAX_ZOOM}
          />
        </BaseLayer>
        <BaseLayer name="Citra satelit (Esri)">
          <TileLayer
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            attribution="Tiles &copy; Esri, Maxar, Earthstar Geographics"
            maxZoom={MAX_ZOOM}
          />
        </BaseLayer>
        {!!MAP_WMS.url && !!MAP_WMS.layers && (
          <Overlay name={MAP_WMS.name}>
            <WMSTileLayer
              url={MAP_WMS.url}
              layers={MAP_WMS.layers}
              format={"image/png"}
              transparent={true}
            />
          </Overlay>
        )}
        {!!overlayLayers &&
          overlayLayers.length &&
          overlayLayers.map((layer, index) => (
            <Overlay checked={layer.checked} name={layer.name} key={index}>
              <LayerGroup>{layer.component}</LayerGroup>
            </Overlay>
          ))}
      </LayersControl>

      {enableSearch && <GeoSearch />}
      <FullscreenControl position="topright" title="Layar penuh" />
      <ZoomControl
        position="topright"
        zoomInTitle="Perbesar"
        zoomOutTitle="Perkecil"
      />
      <ZoomBox
        position="topright"
        modal={true}
        title="Perbesar ke area terpilih"
      />
      {children}
    </Map>
  );
};

export default MapContainer;
