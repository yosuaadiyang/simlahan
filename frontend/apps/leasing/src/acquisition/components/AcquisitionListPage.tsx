import React, { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { useAppDispatch, useAppSelector } from "@/root/hooks";
import Modal from "@/components/modal/Modal";
import PageContainerHDS from "@/components/content/PageContainerHDS";
import { receiveTopNavigationSettings } from "@/components/topNavigation/actions";
import { getRouteById, Routes } from "@/root/routes";
import {
  getSearchQuery,
  getUrlParams,
  hasPermissions,
  setPageTitle,
} from "@/util/helpers";
import { UsersPermissions } from "@/usersPermissions/enums";
import { getUsersPermissions } from "@/usersPermissions/selectors";
import { apiGet } from "../api";
import { useApi, useChoices, useMunicipalities } from "../hooks";
import { formatArea, formatDateId } from "../format";
import ResourceForm from "./ResourceForm";
import { Button, DataTable, ErrorText, Section, Tag, labelOf } from "./ui";

const PAGE_SIZE = 25;

export const PROJECT_FORM_FIELDS = [
  { name: "name", wide: true },
  "acquisition_type",
  "purpose_category",
  "requiring_agency",
  "requiring_agency_contact",
  "funding_source",
  "priority",
  "municipality",
  "executing_office",
  "estimated_area_m2",
  "estimated_budget",
  "start_date",
  "target_completion_date",
  { name: "location_description", wide: true },
  { name: "description", wide: true },
];

const AcquisitionListPage: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const location = useLocation();
  const usersPermissions = useAppSelector(getUsersPermissions);
  const query = useMemo(() => getUrlParams(location.search), [location.search]);
  const page = Number(query.page || 1);
  const [search, setSearch] = useState<string>(query.search || "");
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const { data: choices } = useChoices();
  const { data: municipalities } = useMunicipalities();

  const municipalityOptions = useMemo(
    () =>
      (municipalities || []).map((m) => ({
        value: m.id,
        label: m.name,
      })),
    [municipalities],
  );

  useEffect(() => {
    setPageTitle("Proyek pengadaan tanah");
    dispatch(
      receiveTopNavigationSettings({
        linkUrl: getRouteById(Routes.ACQUISITIONS),
        pageTitle: "Pengadaan Tanah",
        showSearch: false,
      }),
    );
  }, [dispatch]);

  const { data, error, isLoading } = useApi(
    () =>
      apiGet("pengadaan/project/", {
        search: query.search,
        stage: query.stage,
        status: query.status,
        acquisition_type: query.acquisition_type,
        ordering: query.ordering || "-created_at",
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      }),
    [location.search],
  );

  const updateQuery = (changes: Record<string, any>) => {
    const next = { ...query, ...changes };
    Object.keys(next).forEach((key) => {
      if (next[key] === "" || next[key] === undefined) delete next[key];
    });
    if (!("page" in changes)) delete next.page;
    navigate({
      pathname: getRouteById(Routes.ACQUISITIONS),
      search: getSearchQuery(next),
    });
  };

  const count = data?.count || 0;
  const maxPage = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const canAdd = hasPermissions(
    usersPermissions,
    UsersPermissions.ADD_ACQUISITIONPROJECT,
  );

  return (
    <PageContainerHDS className="acq-page">
      <header className="acq-page__header">
        <div>
          <h1>Proyek pengadaan tanah</h1>
          <p className="acq-muted">{count} proyek</p>
        </div>
        {canAdd && (
          <Button onClick={() => setIsCreateOpen(true)}>+ Proyek baru</Button>
        )}
      </header>

      <Section title="Saring">
        <form
          className="acq-filters"
          onSubmit={(e) => {
            e.preventDefault();
            updateQuery({ search });
          }}
        >
          <input
            type="search"
            placeholder="Cari nomor, nama proyek, instansi, lokasi…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            aria-label="Tahap"
            value={query.stage || ""}
            onChange={(e) => updateQuery({ stage: e.target.value })}
          >
            <option value="">Semua tahap</option>
            {(choices?.ProjectStage || []).map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
          <select
            aria-label="Status"
            value={query.status || ""}
            onChange={(e) => updateQuery({ status: e.target.value })}
          >
            <option value="">Semua status</option>
            {(choices?.ProjectStatus || []).map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
          <select
            aria-label="Jenis pengadaan"
            value={query.acquisition_type || ""}
            onChange={(e) => updateQuery({ acquisition_type: e.target.value })}
          >
            <option value="">Semua jenis</option>
            {(choices?.AcquisitionType || []).map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
          <Button type="submit">Cari</Button>
        </form>
      </Section>

      {error && <ErrorText>{error}</ErrorText>}
      <DataTable
        rows={data?.results || []}
        empty={isLoading ? "Memuat…" : "Belum ada proyek pengadaan."}
        onRowClick={(row) =>
          navigate(`${getRouteById(Routes.ACQUISITIONS)}/${row.id}`)
        }
        columns={[
          { key: "identifier", header: "Nomor" },
          { key: "name", header: "Nama proyek" },
          { key: "requiring_agency", header: "Instansi" },
          {
            key: "municipality_name",
            header: "Kabupaten/Kota",
            render: (row) => row.municipality_name || "–",
          },
          {
            key: "stage",
            header: "Tahap",
            render: (row) => labelOf(choices, "ProjectStage", row.stage),
          },
          {
            key: "status",
            header: "Status",
            render: (row) => (
              <Tag value={row.status}>
                {labelOf(choices, "ProjectStatus", row.status)}
              </Tag>
            ),
          },
          {
            key: "parcel_count",
            header: "Bidang",
            className: "acq-num",
          },
          {
            key: "estimated_area_m2",
            header: "Kebutuhan lahan",
            className: "acq-num",
            render: (row) => formatArea(row.estimated_area_m2),
          },
          {
            key: "location_decree_expires_on",
            header: "Penlok berakhir",
            render: (row) => formatDateId(row.location_decree_expires_on),
          },
        ]}
      />
      {maxPage > 1 && (
        <nav className="acq-pagination" aria-label="Halaman">
          <Button
            variant="secondary"
            disabled={page <= 1}
            onClick={() => updateQuery({ page: page - 1 })}
          >
            ‹ Sebelumnya
          </Button>
          <span>
            Halaman {page} dari {maxPage}
          </span>
          <Button
            variant="secondary"
            disabled={page >= maxPage}
            onClick={() => updateQuery({ page: page + 1 })}
          >
            Berikutnya ›
          </Button>
        </nav>
      )}

      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Proyek pengadaan baru"
        className="acq-modal"
        scrollable
      >
        {isCreateOpen && (
          <ResourceForm
            endpoint="pengadaan/project/"
            fields={PROJECT_FORM_FIELDS}
            fkOptions={{ municipality: municipalityOptions }}
            submitLabel="Buat proyek"
            onCancel={() => setIsCreateOpen(false)}
            onSaved={(record) => {
              setIsCreateOpen(false);
              navigate(`${getRouteById(Routes.ACQUISITIONS)}/${record.id}`);
            }}
          />
        )}
      </Modal>
    </PageContainerHDS>
  );
};

export default AcquisitionListPage;
