import React, { useMemo } from "react";
import L from "leaflet";
import { GeoJSON } from "react-leaflet";
import MapContainer from "@/areaNote/components/MapContainer";
import { DEFAULT_CENTER, DEFAULT_ZOOM } from "@/util/constants";
import { escapeHtml } from "@/util/helpers";

/** Warna bidang per status (mudah dibedakan juga oleh pengguna buta warna). */
export const PARCEL_STATUS_COLORS: Record<string, string> = {
  identified: "#9e9e9e",
  inventoried: "#5c6bc0",
  announced: "#3949ab",
  valued: "#00897b",
  deliberation: "#f9a825",
  agreed: "#7cb342",
  objection: "#c62828",
  consigned: "#ef6c00",
  paid: "#2e7d32",
  released: "#1b5e20",
  handed_over: "#004d40",
  excluded: "#424242",
};

type Props = {
  featureCollection: Record<string, any> | null;
  onParcelClick?: (parcelId: number) => void;
  highlightParcelId?: number | null;
  height?: number;
  statusLabels?: Record<string, string>;
  /** Tampilkan nama pihak yang berhak pada keterangan bidang. */
  showParties?: boolean;
};


const AcquisitionMap: React.FC<Props> = ({
  featureCollection,
  onParcelClick,
  highlightParcelId,
  height = 480,
  statusLabels,
  showParties = true,
}) => {
  const hasFeatures = Boolean(featureCollection?.features?.length);
  const bounds = useMemo(() => {
    if (!hasFeatures) return undefined;
    try {
      const b = L.geoJSON(featureCollection as any).getBounds();
      return b.isValid() ? b.pad(0.1) : undefined;
    } catch {
      return undefined;
    }
  }, [featureCollection, hasFeatures]);

  const style = (feature: any) => {
    const properties = feature?.properties || {};
    if (properties.kind === "project") {
      return {
        color: "#1f6f4a",
        weight: 2,
        dashArray: "6 4",
        fillOpacity: 0.05,
      };
    }
    const highlighted =
      highlightParcelId && properties.id === highlightParcelId;
    return {
      color: highlighted ? "#000" : "#333",
      weight: highlighted ? 3 : 1,
      fillColor: PARCEL_STATUS_COLORS[properties.status] || "#9e9e9e",
      fillOpacity: highlighted ? 0.75 : 0.5,
    };
  };

  const onEachFeature = (feature: any, layer: any) => {
    const p = feature?.properties || {};
    if (p.kind !== "parcel") return;
    layer.bindTooltip(
      `<strong>Bidang ${escapeHtml(p.parcel_number)}</strong><br/>` +
        `${escapeHtml(p.status_display)}<br/>` +
        `${escapeHtml(p.right_type)}${p.affected_area_m2 ? ` · ${escapeHtml(p.affected_area_m2)} m²` : ""}` +
        `${showParties && p.parties ? `<br/>${escapeHtml(p.parties)}` : ""}` +
        `${p.is_disputed ? "<br/><em>Bersengketa</em>" : ""}`,
      { sticky: true },
    );
    if (onParcelClick) {
      layer.on("click", () => onParcelClick(p.id));
    }
  };

  return (
    <div className="acq-map" style={{ height }}>
      <MapContainer
        center={bounds ? undefined : DEFAULT_CENTER}
        bounds={bounds}
        zoom={DEFAULT_ZOOM}
      >
        {hasFeatures && (
          <GeoJSON
            key={
              JSON.stringify(featureCollection).length +
              String(highlightParcelId)
            }
            data={featureCollection as any}
            style={style}
            onEachFeature={onEachFeature}
          />
        )}
      </MapContainer>
      <ul className="acq-map__legend">
        {Object.entries(PARCEL_STATUS_COLORS).map(([status, color]) => (
          <li key={status}>
            <span style={{ background: color }} />
            {statusLabels?.[status] || status}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default AcquisitionMap;
