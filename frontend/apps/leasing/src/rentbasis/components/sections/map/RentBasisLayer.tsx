import React from "react";
import { GeoJSON } from "react-leaflet";
import { formatDate, getLabelOfOption } from "@/util/helpers";
import type { LeafletGeoJson } from "types";
type Props = {
  color: string;
  financingOptions: Array<Record<string, any>>;
  geoJSON: LeafletGeoJson;
  indexOptions: Array<Record<string, any>>;
  managementOptions: Array<Record<string, any>>;
  plotTypeOptions: Array<Record<string, any>>;
};

const RentBasisLayer = ({
  color,
  financingOptions,
  geoJSON,
  indexOptions,
  managementOptions,
  plotTypeOptions,
}: Props) => {
  const onMouseOver = (e) => {
    const layer = e.target;
    layer.setStyle({
      fillOpacity: 0.7,
    });
  };

  const onMouseOut = (e) => {
    const layer = e.target;
    layer.setStyle({
      fillOpacity: 0.2,
    });
  };

  return (
    <GeoJSON
      data={geoJSON}
      onEachFeature={(feature, layer) => {
        if (feature.properties) {
          const {
            detailed_plan_identifier,
            end_date,
            financing,
            id,
            index,
            lease_rights_end_date,
            management,
            plot_type,
            property_identifiers,
            start_date,
          } = feature.properties;

          const getPropertyIdentifierString = () => {
            if (property_identifiers && property_identifiers.length) {
              let text = "";
              property_identifiers.forEach((identifier, index) => {
                if (index + 1 < property_identifiers.length) {
                  text += `${identifier.identifier}, `;
                } else {
                  text += `${identifier.identifier}`;
                }
              });
              return text;
            }

            return "-";
          };

          const identifierText = getPropertyIdentifierString();
          const popupContent = `<p class='title'><strong>Prinsip sewa</strong></p>
            <p><strong>Id:</strong> ${id}</p>
            <p><strong>Jenis kavling:</strong> ${getLabelOfOption(plotTypeOptions, plot_type) || "-"}</p>
            <p><strong>Tgl mulai:</strong> ${formatDate(start_date) || "-"}</p>
            <p><strong>Tgl akhir:</strong> ${formatDate(end_date) || "-"}</p>
            <p><strong>Pengenal bidang:</strong> ${identifierText}</p>
            <p><strong>Rencana detail:</strong> ${detailed_plan_identifier || "-"}</p>
            <p><strong>Bentuk pengelolaan:</strong> ${getLabelOfOption(managementOptions, management) || "-"}</p>
            <p><strong>Bentuk pembiayaan:</strong> ${getLabelOfOption(financingOptions, financing) || "-"}</p>
            <p><strong>Hak sewa berakhir:</strong> ${formatDate(lease_rights_end_date) || "-"}</p>
            <p><strong>Indeks:</strong> ${getLabelOfOption(indexOptions, index) || "-"}</p>`;
          layer.bindPopup(popupContent);
        }

        layer.on({
          mouseover: onMouseOver,
          mouseout: onMouseOut,
        });
      }}
      style={{
        color: color,
      }}
    />
  );
};

export default RentBasisLayer;
