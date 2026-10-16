import React from "react";
import AuditLogTableItem from "./AuditLogTableItem";
type Props = {
  items: Array<Record<string, any>>;
};

const AuditLogTable = ({ items }: Props) => {
  return (
    <div className="sortable-table__container">
      <table className="sortable-table">
        <thead>
          <tr>
            <td></td>
            <th
              style={{
                width: "16.7%",
              }}
            >
              <div>Tgl</div>
            </th>
            <th
              style={{
                width: "16.7%",
              }}
            >
              <div>Nama</div>
            </th>
            <th
              style={{
                width: "16.7%",
              }}
            >
              <div>Jenis perubahan</div>
            </th>
            <th
              style={{
                width: "16.7%",
              }}
            >
              <div>Objek perubahan</div>
            </th>
            <th
              style={{
                width: "16.7%",
              }}
            >
              <div>Nilai lama</div>
            </th>
            <th
              style={{
                width: "16.7%",
              }}
            >
              <div>Nilai baru</div>
            </th>
          </tr>
        </thead>
        <tbody>
          {!items.length && (
            <tr className="no-data-row">
              <td colSpan={7}>Tidak ada perubahan</td>
            </tr>
          )}

          {items.map((item, index) => (
            <AuditLogTableItem key={`${index}_${item.object_id}`} item={item} />
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default AuditLogTable;
