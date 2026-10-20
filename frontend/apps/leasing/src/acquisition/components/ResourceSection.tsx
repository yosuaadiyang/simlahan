import React, { useState } from "react";
import Modal from "@/components/modal/Modal";
import { displayUIMessage } from "@/util/helpers";
import { apiGetAll, apiSend } from "../api";
import { useApi } from "../hooks";
import { useResourcePermissions } from "../permissions";
import ResourceForm from "./ResourceForm";
import type { FormFieldSpec } from "./ResourceForm";
import { Button, DataTable, ErrorText, Section } from "./ui";
import type { Column } from "./ui";
import type { Option } from "../types";

type Props = {
  title: string;
  endpoint: string;
  params: Record<string, any>;
  columns: Array<Column<Record<string, any>>>;
  formFields: Array<FormFieldSpec>;
  defaults?: Record<string, any>;
  fkOptions?: Record<string, Array<Option>>;
  canAdd?: boolean;
  canEdit?: boolean;
  canDelete?: boolean;
  itemName: string;
  rowActions?: (
    row: Record<string, any>,
    reload: () => void,
  ) => React.ReactNode;
  headerActions?: React.ReactNode;
  onChanged?: () => void;
  emptyText?: string;
  onRowClick?: (row: Record<string, any>) => void;
  /** Ubah nilai ini untuk memaksa data dimuat ulang. */
  refreshKey?: number;
};

/** Tabel data + formulir tambah/ubah/hapus untuk satu sumber daya API. */
const ResourceSection: React.FC<Props> = ({
  title,
  endpoint,
  params,
  columns,
  formFields,
  defaults,
  fkOptions,
  canAdd: canAddProp = true,
  canEdit: canEditProp = true,
  canDelete: canDeleteProp = true,
  itemName,
  rowActions,
  headerActions,
  onChanged,
  emptyText,
  onRowClick,
  refreshKey = 0,
}) => {
  const permissions = useResourcePermissions(endpoint);
  const canView = permissions.isLoaded && permissions.canView;
  const canAdd = canAddProp && permissions.canAdd;
  const canEdit = canEditProp && permissions.canChange;
  const canDelete = canDeleteProp && permissions.canDelete;
  const paramsKey = JSON.stringify(params);
  const { data, error, isLoading, reload } = useApi(
    canView ? () => apiGetAll(endpoint, params) : null,
    [endpoint, paramsKey, refreshKey, canView],
  );
  const [editing, setEditing] = useState<Record<string, any> | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);

  const refresh = () => {
    reload();
    onChanged?.();
  };

  const handleSaved = (record?: Record<string, any>) => {
    setIsFormOpen(false);
    setEditing(null);
    displayUIMessage({ title: "", body: `${itemName} disimpan` });
    if (record?.notice) {
      // Mis. validasi ganti kerugian dibatalkan karena data berubah.
      displayUIMessage({ title: "", body: record.notice }, { type: "info" });
    }
    refresh();
  };

  const handleDelete = async (row: Record<string, any>) => {
    if (!window.confirm(`Hapus ${itemName.toLowerCase()} ini?`)) return;
    try {
      await apiSend("DELETE", `${endpoint}${row.id}/`);
      displayUIMessage({ title: "", body: `${itemName} dihapus` });
      refresh();
    } catch (e) {
      displayUIMessage(
        { title: "", body: (e as Error).message },
        { type: "error" },
      );
    }
  };

  const showActions = canEdit || canDelete || Boolean(rowActions);

  return (
    <Section
      title={title}
      actions={
        <>
          {headerActions}
          {canAdd && (
            <Button
              onClick={() => {
                setEditing(null);
                setIsFormOpen(true);
              }}
            >
              + Tambah {itemName.toLowerCase()}
            </Button>
          )}
        </>
      }
    >
      {error && <ErrorText>{error}</ErrorText>}
      {!canView ? (
        <p className="acq-muted">
          {permissions.isLoaded
            ? "Anda tidak berwenang melihat data ini."
            : "Memuat…"}
        </p>
      ) : isLoading && !data ? (
        <p className="acq-muted">Memuat…</p>
      ) : (
        <DataTable
          columns={columns}
          rows={data || []}
          empty={emptyText}
          onRowClick={onRowClick}
          actions={
            showActions
              ? (row) => (
                  <div className="acq-row-actions">
                    {rowActions?.(row, refresh)}
                    {canEdit && (
                      <Button
                        variant="link"
                        onClick={() => {
                          setEditing(row);
                          setIsFormOpen(true);
                        }}
                      >
                        Ubah
                      </Button>
                    )}
                    {canDelete && (
                      <Button variant="link" onClick={() => handleDelete(row)}>
                        Hapus
                      </Button>
                    )}
                  </div>
                )
              : undefined
          }
        />
      )}
      <Modal
        isOpen={isFormOpen}
        onClose={() => setIsFormOpen(false)}
        title={`${editing ? "Ubah" : "Tambah"} ${itemName.toLowerCase()}`}
        className="acq-modal"
        scrollable
      >
        {isFormOpen && (
          <ResourceForm
            key={editing?.id ?? "new"}
            endpoint={endpoint}
            fields={formFields}
            instance={editing}
            defaults={defaults}
            fkOptions={fkOptions}
            onSaved={handleSaved}
            onCancel={() => setIsFormOpen(false)}
          />
        )}
      </Modal>
    </Section>
  );
};

export default ResourceSection;
