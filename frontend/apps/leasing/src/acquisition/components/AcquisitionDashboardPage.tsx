import React, { useEffect, useState } from "react";
import { Link } from "react-router";
import { useAppDispatch } from "@/root/hooks";
import PageContainerHDS from "@/components/content/PageContainerHDS";
import { receiveTopNavigationSettings } from "@/components/topNavigation/actions";
import { getRouteById, Routes } from "@/root/routes";
import { setPageTitle } from "@/util/helpers";
import { apiGet } from "../api";
import { useApi, useChoices } from "../hooks";
import { formatArea, formatDateId, formatRupiah, percent } from "../format";
import type { Deadline } from "../types";
import {
  DataTable,
  ErrorText,
  Progress,
  Section,
  Stat,
  Tag,
  labelOf,
} from "./ui";

const STATE_LABEL: Record<Deadline["state"], string> = {
  overdue: "Terlewat",
  due_soon: "Segera",
  upcoming: "Akan datang",
};

const projectUrl = (id: number) => `${getRouteById(Routes.ACQUISITIONS)}/${id}`;

const AcquisitionDashboardPage: React.FC = () => {
  const dispatch = useAppDispatch();
  const { data: choices } = useChoices();
  const [stateFilter, setStateFilter] = useState<string>("");
  const dashboard = useApi(() => apiGet("pengadaan/dashboard/"), []);
  const deadlines = useApi<Array<Deadline>>(
    () => apiGet("pengadaan/deadlines/", { state: stateFilter }),
    [stateFilter],
  );

  useEffect(() => {
    setPageTitle("Dasbor pengadaan tanah");
    dispatch(
      receiveTopNavigationSettings({
        linkUrl: getRouteById(Routes.ACQUISITION_DASHBOARD),
        pageTitle: "Pengadaan Tanah",
        showSearch: false,
      }),
    );
  }, [dispatch]);

  const d = dashboard.data;
  const parcelsByStatus: Record<string, number> = d?.parcels_by_status || {};
  const totalParcels = Object.values(parcelsByStatus).reduce(
    (a, b) => a + Number(b),
    0,
  );

  return (
    <PageContainerHDS className="acq-page">
      <header className="acq-page__header">
        <div>
          <h1>Dasbor pengadaan tanah</h1>
          <p className="acq-muted">
            Ringkasan seluruh proyek, status bidang, dan tenggat hukum (hari
            kerja, UU 2/2012 &amp; PP 19/2021).
          </p>
        </div>
        <Link className="acq-button" to={getRouteById(Routes.ACQUISITIONS)}>
          Lihat proyek
        </Link>
      </header>

      {dashboard.error && <ErrorText>{dashboard.error}</ErrorText>}
      {d && (
        <>
          <div className="acq-stats">
            <Stat
              label="Tenggat terlewat"
              value={d.deadlines_overdue}
              tone={d.deadlines_overdue ? "danger" : "success"}
            />
            <Stat
              label="Tenggat ≤ 5 hari kerja"
              value={d.deadlines_due_soon}
              tone={d.deadlines_due_soon ? "warning" : "default"}
            />
            {d.open_objections !== undefined && (
              <Stat
                label="Keberatan/perkara berjalan"
                value={d.open_objections}
                tone={d.open_objections ? "warning" : "default"}
              />
            )}
            <Stat
              label="Luas terkena"
              value={formatArea(d.affected_area_m2)}
              hint={`Dilepaskan: ${formatArea(d.released_area_m2)}`}
            />
            {d.compensation_total !== undefined && (
              <Stat
                label="Ganti kerugian ditetapkan"
                value={formatRupiah(d.compensation_total)}
                hint={`Dibayar: ${formatRupiah(d.paid_total)}`}
              />
            )}
          </div>

          <div className="acq-columns">
            <Section title="Proyek per tahap">
              <ul className="acq-bars">
                {(choices?.ProjectStage || []).map((stage) => {
                  const count = Number(d.projects_by_stage?.[stage.value] || 0);
                  const total = Object.values(d.projects_by_stage || {}).reduce(
                    (a: number, b) => a + Number(b),
                    0,
                  );
                  return (
                    <li key={stage.value}>
                      <span>{stage.label}</span>
                      <Progress
                        value={percent(count, total)}
                        label={String(count)}
                      />
                    </li>
                  );
                })}
              </ul>
            </Section>
            <Section title="Bidang per status">
              <ul className="acq-bars">
                {(choices?.ParcelStatus || [])
                  .filter((s) => parcelsByStatus[s.value])
                  .map((s) => (
                    <li key={s.value}>
                      <span>{s.label}</span>
                      <Progress
                        value={percent(parcelsByStatus[s.value], totalParcels)}
                        label={String(parcelsByStatus[s.value])}
                      />
                    </li>
                  ))}
                {!totalParcels && (
                  <li className="acq-muted">Belum ada bidang.</li>
                )}
              </ul>
            </Section>
          </div>
        </>
      )}

      <Section
        title="Tenggat hukum"
        actions={
          <select
            aria-label="Saring tenggat"
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
          >
            <option value="">Semua tenggat terbuka</option>
            <option value="overdue">Terlewat</option>
            <option value="due_soon">Segera jatuh tempo</option>
            <option value="upcoming">Akan datang</option>
          </select>
        }
      >
        {deadlines.error && <ErrorText>{deadlines.error}</ErrorText>}
        <DataTable<Deadline>
          rows={deadlines.data || []}
          empty={deadlines.isLoading ? "Memuat…" : "Tidak ada tenggat terbuka."}
          columns={[
            {
              key: "state",
              header: "Status",
              render: (row) => (
                <Tag value={row.state}>{STATE_LABEL[row.state]}</Tag>
              ),
            },
            {
              key: "due_date",
              header: "Batas waktu",
              render: (row) => formatDateId(row.due_date),
            },
            {
              key: "workdays_left",
              header: "Sisa hari kerja",
              render: (row) => row.workdays_left,
            },
            { key: "title", header: "Kewajiban" },
            {
              key: "project",
              header: "Proyek",
              render: (row) => (
                <Link to={projectUrl(row.project_id)}>
                  {row.project_identifier} – {row.project_name}
                </Link>
              ),
            },
            {
              key: "parcel_number",
              header: "Bidang",
              render: (row) =>
                row.parcel_id ? (
                  <Link
                    to={`${projectUrl(row.project_id)}/bidang/${row.parcel_id}`}
                  >
                    {row.parcel_number}
                  </Link>
                ) : (
                  "–"
                ),
            },
            { key: "reference", header: "Referensi" },
          ]}
        />
      </Section>

      {d?.projects_by_status && (
        <p className="acq-muted">
          Status proyek:{" "}
          {Object.entries(d.projects_by_status)
            .map(
              ([status, n]) =>
                `${labelOf(choices, "ProjectStatus", status)} ${n}`,
            )
            .join(" · ") || "–"}
        </p>
      )}
    </PageContainerHDS>
  );
};

export default AcquisitionDashboardPage;
