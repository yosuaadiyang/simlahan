import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router";
import { useAppDispatch, useAppSelector } from "@/root/hooks";
import Modal from "@/components/modal/Modal";
import PageContainerHDS from "@/components/content/PageContainerHDS";
import { receiveTopNavigationSettings } from "@/components/topNavigation/actions";
import { getRouteById, Routes } from "@/root/routes";
import {
  displayUIMessage,
  getUrlParams,
  hasPermissions,
  setPageTitle,
} from "@/util/helpers";
import { UsersPermissions } from "@/usersPermissions/enums";
import { getUsersPermissions } from "@/usersPermissions/selectors";
import { apiDownload, apiGet, apiGetAll, apiSend, apiUpload } from "../api";
import {
  useApi,
  useChoices,
  useDistricts,
  useMunicipalities,
  useUsers,
} from "../hooks";
import {
  formatArea,
  formatDateId,
  formatHectare,
  formatNumberId,
  formatRupiah,
  percent,
} from "../format";
import type { Deadline, Option } from "../types";
import AcquisitionMap from "./AcquisitionMap";
import ResourceForm from "./ResourceForm";
import ResourceSection from "./ResourceSection";
import { useCanViewResource } from "../permissions";
import { PROJECT_FORM_FIELDS } from "./AcquisitionListPage";
import {
  Button,
  DataTable,
  ErrorText,
  Progress,
  Section,
  Stat,
  Tabs,
  Tag,
  labelOf,
} from "./ui";

const TABS = [
  { key: "ringkasan", label: "Ringkasan" },
  { key: "bidang", label: "Bidang & peta" },
  { key: "pihak", label: "Pihak & inventarisasi" },
  { key: "pengumuman", label: "Pengumuman" },
  { key: "penilaian", label: "Penilaian" },
  { key: "musyawarah", label: "Musyawarah" },
  { key: "keberatan", label: "Keberatan & konsinyasi" },
  { key: "ganti-kerugian", label: "Ganti kerugian" },
  { key: "pelepasan", label: "Pelepasan & penyerahan" },
  { key: "relokasi", label: "Relokasi" },
  { key: "dokumen", label: "Dokumen" },
  { key: "tenggat", label: "Tenggat" },
];

const numberWithDate = (number?: string | null, date?: string | null) => {
  if (!number && !date) return "–";
  if (!date) return number;
  return `${number || "tanpa nomor"}, tanggal ${formatDateId(date)}`;
};

const PROJECT_DETAIL_FIELDS = [
  ...PROJECT_FORM_FIELDS,
  "stage",
  "status",
  "executing_chair",
  "planning_document_number",
  "planning_document_date",
  "notification_date",
  "public_consultation_date",
  "location_decree_number",
  "location_decree_date",
  "location_announcement_date",
  "location_decree_extended",
];

const ImportParcels: React.FC<{
  projectId: string;
  onDone: () => void;
}> = ({ projectId, onDone }) => {
  const [file, setFile] = useState<File | null>(null);
  const [numberField, setNumberField] = useState("parcel_number");
  const [areaField, setAreaField] = useState("");
  const [result, setResult] = useState<Record<string, any> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file) {
      setError("Pilih berkas GeoJSON atau shapefile (.zip).");
      return;
    }
    setBusy(true);
    setError(null);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("number_field", numberField);
    if (areaField) formData.append("area_field", areaField);
    try {
      const data = await apiUpload(
        `pengadaan/project/${projectId}/import_parcels/`,
        formData,
      );
      setResult(data);
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="acq-form" onSubmit={submit}>
      <p className="acq-muted">
        Unggah peta bidang hasil ukur (GeoJSON atau shapefile ber-.prj dalam
        .zip). Koordinat diubah otomatis ke WGS84. Bidang dengan nomor yang sama
        diperbarui, bukan digandakan.
      </p>
      <div className="acq-form__grid">
        <div className="acq-form__field acq-form__field--wide">
          <label htmlFor="acq-import-file">Berkas *</label>
          <input
            id="acq-import-file"
            type="file"
            accept=".geojson,.json,.zip"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </div>
        <div className="acq-form__field">
          <label htmlFor="acq-import-number">Atribut nomor bidang</label>
          <input
            id="acq-import-number"
            value={numberField}
            onChange={(e) => setNumberField(e.target.value)}
          />
        </div>
        <div className="acq-form__field">
          <label htmlFor="acq-import-area">Atribut luas (opsional)</label>
          <input
            id="acq-import-area"
            value={areaField}
            onChange={(e) => setAreaField(e.target.value)}
          />
        </div>
      </div>
      {error && <ErrorText>{error}</ErrorText>}
      {result && (
        <p className="acq-success">
          Dibuat {result.created}, diperbarui {result.updated}, dilewati{" "}
          {result.skipped}.
          {!!result.errors?.length && (
            <>
              <br />
              {result.errors.slice(0, 10).join(" · ")}
            </>
          )}
        </p>
      )}
      <div className="acq-form__actions">
        <Button type="submit" disabled={busy}>
          {busy ? "Mengimpor…" : "Impor"}
        </Button>
      </div>
    </form>
  );
};

const AcquisitionProjectPage: React.FC = () => {
  const { projectId = "" } = useParams();
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const location = useLocation();
  const usersPermissions = useAppSelector(getUsersPermissions);
  const can = useCallback(
    (perm: string) => hasPermissions(usersPermissions, perm),
    [usersPermissions],
  );
  const tab = getUrlParams(location.search).tab || "ringkasan";
  const [version, setVersion] = useState(0);
  const bump = useCallback(() => setVersion((v) => v + 1), []);
  const [isEditing, setIsEditing] = useState(false);
  const [isImportOpen, setIsImportOpen] = useState(false);

  const { data: choices } = useChoices();
  const { data: municipalities } = useMunicipalities();
  const { data: users } = useUsers();
  const project = useApi(
    () => apiGet(`pengadaan/project/${projectId}/`),
    [projectId, version],
  );
  const summary = useApi(
    () => apiGet(`pengadaan/project/${projectId}/summary/`),
    [projectId, version],
  );
  const geojson = useApi(
    () => apiGet(`pengadaan/project/${projectId}/geojson/`),
    [projectId, version],
  );
  const canView = useCanViewResource();
  // Daftar pilihan hanya dimuat dari endpoint yang boleh dilihat pengguna.
  const listProjectRows = (endpoint: string) =>
    canView(endpoint)
      ? apiGetAll(endpoint, { project: projectId })
      : Promise.resolve([]);
  const parcels = useApi(
    () => listProjectRows("pengadaan/parcel/"),
    [projectId, version, canView],
  );
  const parties = useApi(
    () => listProjectRows("pengadaan/party/"),
    [projectId, version, canView],
  );
  const lookups = useApi(async () => {
    const [deliberations, valuations, results, objections, compensations] =
      await Promise.all([
        listProjectRows("pengadaan/deliberation/"),
        listProjectRows("pengadaan/valuation/"),
        listProjectRows("pengadaan/deliberation_result/"),
        listProjectRows("pengadaan/objection/"),
        listProjectRows("pengadaan/compensation/"),
      ]);
    return { deliberations, valuations, results, objections, compensations };
  }, [projectId, version, canView]);

  const p = project.data;
  const { data: districts } = useDistricts(p?.municipality);

  useEffect(() => {
    const title = p ? `${p.identifier} ${p.name}` : "Proyek pengadaan";
    setPageTitle(title);
    dispatch(
      receiveTopNavigationSettings({
        linkUrl: getRouteById(Routes.ACQUISITIONS),
        pageTitle: "Pengadaan Tanah",
        showSearch: false,
      }),
    );
  }, [dispatch, p]);

  const options = useMemo(() => {
    const toOptions = (
      rows: Array<Record<string, any>> | undefined,
      label: (r: any) => string,
    ): Array<Option> =>
      (rows || []).map((r) => ({ value: r.id, label: label(r) }));
    const l = lookups.data;
    return {
      parcel: toOptions(
        parcels.data || [],
        (r) => `${r.parcel_number}${r.village ? ` – ${r.village}` : ""}`,
      ),
      party: toOptions(
        parties.data || [],
        (r) => `${r.parcel_number} – ${r.name}`,
      ),
      user: toOptions(
        users || [],
        (u) =>
          [u.first_name, u.last_name].filter(Boolean).join(" ") || u.username,
      ),
      municipality: toOptions(municipalities || [], (m) => m.name),
      district: toOptions(districts || [], (d) => d.name),
      deliberation: toOptions(
        l?.deliberations,
        (d) =>
          `${formatDateId(d.held_on)}${d.minutes_number ? ` – ${d.minutes_number}` : ""}`,
      ),
      valuation: toOptions(
        l?.valuations,
        (v) =>
          `${v.parcel_number} – ${formatRupiah(v.total_value)}${v.report_number ? ` (${v.report_number})` : ""}`,
      ),
      deliberation_result: toOptions(
        l?.results,
        (r) =>
          `${r.parcel_number} – ${r.party_name || ""} – ${labelOf(choices, "DeliberationOutcome", r.outcome)}`,
      ),
      court_decision: toOptions(
        l?.objections,
        (o) =>
          `${o.case_number || "tanpa nomor"} – ${labelOf(choices, "ObjectionType", o.objection_type)}`,
      ),
      compensation: toOptions(
        l?.compensations,
        (c) =>
          `${c.parcel_number} – ${c.party_name || ""} – ${formatRupiah(c.amount)}`,
      ),
    };
  }, [
    parcels.data,
    parties.data,
    users,
    municipalities,
    districts,
    lookups.data,
    choices,
  ]);

  const setTab = (key: string) =>
    navigate({ pathname: location.pathname, search: `?tab=${key}` });

  const parcelUrl = (id: number) =>
    `${getRouteById(Routes.ACQUISITIONS)}/${projectId}/bidang/${id}`;

  const exportNominative = async () => {
    try {
      await apiDownload(
        `pengadaan/project/${projectId}/nominative_list/`,
        `daftar-nominatif-${p?.identifier || projectId}.xlsx`,
      );
    } catch (e) {
      displayUIMessage(
        { title: "", body: (e as Error).message },
        { type: "error" },
      );
    }
  };

  const validateCompensation = async (
    row: Record<string, any>,
    reload: () => void,
  ) => {
    if (!window.confirm("Validasi ganti kerugian ini sebagai Ketua Pelaksana?"))
      return;
    try {
      await apiSend("POST", `pengadaan/compensation/${row.id}/validate/`);
      displayUIMessage({ title: "", body: "Ganti kerugian divalidasi" });
      reload();
      bump();
    } catch (e) {
      displayUIMessage(
        { title: "", body: (e as Error).message },
        { type: "error" },
      );
    }
  };

  if (project.error) {
    return (
      <PageContainerHDS className="acq-page">
        <ErrorText>{project.error}</ErrorText>
        <Link to={getRouteById(Routes.ACQUISITIONS)}>
          Kembali ke daftar proyek
        </Link>
      </PageContainerHDS>
    );
  }
  if (!p) {
    return (
      <PageContainerHDS className="acq-page">
        <p className="acq-muted">Memuat proyek…</p>
      </PageContainerHDS>
    );
  }

  const s = summary.data;
  const projectParams = { project: projectId };
  const sectionCommon = { refreshKey: version, onChanged: bump };
  const statusLabels = Object.fromEntries(
    (choices?.ParcelStatus || []).map((c) => [c.value, c.label]),
  );
  const deadlineCount = (s?.deadlines || []).filter(
    (d: Deadline) => d.state !== "upcoming",
  ).length;

  return (
    <PageContainerHDS className="acq-page">
      <header className="acq-page__header">
        <div>
          <p className="acq-muted">
            <Link to={getRouteById(Routes.ACQUISITIONS)}>Proyek pengadaan</Link>{" "}
            / {p.identifier}
          </p>
          <h1>{p.name}</h1>
          <p>
            <Tag value={p.status}>
              {labelOf(choices, "ProjectStatus", p.status)}
            </Tag>{" "}
            <Tag>{labelOf(choices, "ProjectStage", p.stage)}</Tag>{" "}
            <span className="acq-muted">
              {labelOf(choices, "AcquisitionType", p.acquisition_type)} ·{" "}
              {p.requiring_agency}
              {p.municipality_name ? ` · ${p.municipality_name}` : ""}
            </span>
          </p>
        </div>
        <div className="acq-page__actions">
          <Button variant="secondary" onClick={exportNominative}>
            Unduh daftar nominatif (.xlsx)
          </Button>
        </div>
      </header>

      <Tabs
        tabs={TABS.map((t) =>
          t.key === "tenggat" ? { ...t, badge: deadlineCount } : t,
        )}
        active={tab}
        onChange={setTab}
      />

      {tab === "ringkasan" && (
        <>
          {s && (
            <div className="acq-stats">
              <Stat
                label="Bidang"
                value={s.parcel_count}
                hint={`${s.party_count} pihak yang berhak`}
              />
              <Stat
                label="Luas terkena"
                value={formatArea(s.affected_area_m2)}
                hint={formatHectare(s.affected_area_m2)}
              />
              <Stat
                label="Hak dilepaskan"
                value={`${percent(s.released_area_m2, s.affected_area_m2)}%`}
                hint={formatArea(s.released_area_m2)}
                tone="success"
              />
              <Stat
                label="Nilai penilaian (final)"
                value={formatRupiah(s.valuation_total)}
              />
              <Stat
                label="Ganti kerugian dibayar"
                value={formatRupiah(s.paid_total)}
                hint={`dari ${formatRupiah(s.compensation_total)} · dititipkan ${formatRupiah(s.consigned_total)}`}
              />
              <Stat
                label="Keberatan berjalan"
                value={s.open_objections}
                tone={s.open_objections ? "warning" : "default"}
              />
            </div>
          )}
          {s && (
            <Section title="Kemajuan tahapan">
              <Progress
                value={percent(s.milestones_done, s.milestones_total)}
                label={`${s.milestones_done} dari ${s.milestones_total} tonggak selesai`}
              />
            </Section>
          )}
          <Section
            title="Data proyek"
            actions={
              can(UsersPermissions.CHANGE_ACQUISITIONPROJECT) && (
                <Button
                  variant="secondary"
                  onClick={() => setIsEditing((v) => !v)}
                >
                  {isEditing ? "Tutup" : "Ubah data"}
                </Button>
              )
            }
          >
            {isEditing ? (
              <ResourceForm
                endpoint="pengadaan/project/"
                fields={PROJECT_DETAIL_FIELDS}
                instance={p}
                fkOptions={{
                  municipality: options.municipality,
                  executing_chair: options.user,
                }}
                onCancel={() => setIsEditing(false)}
                onSaved={() => {
                  setIsEditing(false);
                  displayUIMessage({ title: "", body: "Proyek disimpan" });
                  bump();
                }}
              />
            ) : (
              <dl className="acq-dl">
                <dt>Kategori peruntukan</dt>
                <dd>
                  {labelOf(
                    choices,
                    "PublicInterestCategory",
                    p.purpose_category,
                  )}
                </dd>
                <dt>Sumber dana</dt>
                <dd>{labelOf(choices, "FundingSource", p.funding_source)}</dd>
                <dt>Prioritas</dt>
                <dd>{labelOf(choices, "Priority", p.priority)}</dd>
                <dt>Kantor pertanahan pelaksana</dt>
                <dd>{p.executing_office || "–"}</dd>
                <dt>Ketua Pelaksana</dt>
                <dd>{p.executing_chair_name || "–"}</dd>
                <dt>Perkiraan kebutuhan lahan</dt>
                <dd>{formatArea(p.estimated_area_m2)}</dd>
                <dt>Perkiraan anggaran</dt>
                <dd>{formatRupiah(p.estimated_budget)}</dd>
                <dt>Dokumen perencanaan (DPPT)</dt>
                <dd>
                  {numberWithDate(
                    p.planning_document_number,
                    p.planning_document_date,
                  )}
                </dd>
                <dt>Penetapan Lokasi</dt>
                <dd>
                  {numberWithDate(
                    p.location_decree_number,
                    p.location_decree_date,
                  )}
                  {p.location_decree_expires_on && (
                    <>
                      {" "}
                      · berlaku s.d.{" "}
                      {formatDateId(p.location_decree_expires_on)}
                    </>
                  )}
                  {p.location_decree_extended && " · diperpanjang"}
                </dd>
                <dt>Batas gugatan PTUN</dt>
                <dd>{formatDateId(p.ptun_filing_deadline)}</dd>
                <dt>Jadwal</dt>
                <dd>
                  {p.start_date || p.target_completion_date
                    ? `${formatDateId(p.start_date)} s.d. ${formatDateId(p.target_completion_date)}`
                    : "–"}
                </dd>
                <dt>Uraian lokasi</dt>
                <dd>{p.location_description || "–"}</dd>
              </dl>
            )}
          </Section>
          <ResourceSection
            {...sectionCommon}
            title="Tonggak tahapan"
            itemName="Tonggak"
            endpoint="pengadaan/milestone/"
            params={{ ...projectParams, ordering: "sequence" }}
            defaults={{ project: Number(projectId) }}
            fkOptions={{ responsible: options.user }}
            formFields={[
              "stage",
              "title",
              "legal_basis",
              "planned_date",
              "actual_date",
              "status",
              "responsible",
              { name: "note", wide: true },
            ]}
            columns={[
              {
                key: "stage",
                header: "Tahap",
                render: (r) => labelOf(choices, "ProjectStage", r.stage),
              },
              { key: "title", header: "Kegiatan" },
              { key: "legal_basis", header: "Dasar hukum" },
              {
                key: "planned_date",
                header: "Rencana",
                render: (r) => formatDateId(r.planned_date),
              },
              {
                key: "actual_date",
                header: "Realisasi",
                render: (r) => formatDateId(r.actual_date),
              },
              {
                key: "status",
                header: "Status",
                render: (r) => (
                  <Tag value={r.status}>
                    {labelOf(choices, "MilestoneStatus", r.status)}
                  </Tag>
                ),
              },
              { key: "responsible_name", header: "Penanggung jawab" },
            ]}
          />
        </>
      )}

      {tab === "bidang" && (
        <>
          <Section title="Peta bidang">
            <AcquisitionMap
              featureCollection={geojson.data}
              statusLabels={statusLabels}
              onParcelClick={(id) => navigate(parcelUrl(id))}
            />
          </Section>
          <ResourceSection
            {...sectionCommon}
            title="Bidang tanah"
            itemName="Bidang"
            endpoint="pengadaan/parcel/"
            params={{ ...projectParams, ordering: "parcel_number" }}
            defaults={{ project: Number(projectId) }}
            onRowClick={(row) => navigate(parcelUrl(row.id))}
            fkOptions={{ district: options.district }}
            headerActions={
              can(UsersPermissions.ADD_ACQUISITIONPARCEL) && (
                <Button
                  variant="secondary"
                  onClick={() => setIsImportOpen(true)}
                >
                  Impor GeoJSON/SHP
                </Button>
              )
            }
            formFields={[
              "parcel_number",
              "nib",
              "district",
              "village",
              "address",
              "right_type",
              "certificate_number",
              "land_use",
              "measured_area_m2",
              "affected_area_m2",
              "building_area_m2",
              { name: "building_description", wide: true },
              { name: "plants_description", wide: true },
              { name: "other_objects_description", wide: true },
              "is_disputed",
              "is_excluded",
              { name: "note", wide: true },
            ]}
            columns={[
              { key: "parcel_number", header: "No. bidang" },
              { key: "nib", header: "NIB" },
              { key: "village", header: "Desa/Kel." },
              {
                key: "right_type",
                header: "Jenis hak",
                render: (r) => labelOf(choices, "LandRightType", r.right_type),
              },
              {
                key: "party_names",
                header: "Pihak yang berhak",
                render: (r) => r.party_names || "–",
              },
              {
                key: "affected_area_m2",
                header: "Luas terkena",
                className: "acq-num",
                render: (r) => formatArea(r.affected_area_m2),
              },
              {
                key: "status",
                header: "Status",
                render: (r) => (
                  <Tag value={r.status}>
                    {labelOf(choices, "ParcelStatus", r.status)}
                  </Tag>
                ),
              },
            ]}
          />
          <Modal
            isOpen={isImportOpen}
            onClose={() => setIsImportOpen(false)}
            title="Impor peta bidang"
            className="acq-modal"
            scrollable
          >
            {isImportOpen && (
              <ImportParcels projectId={projectId} onDone={bump} />
            )}
          </Modal>
        </>
      )}

      {tab === "pihak" && (
        <>
          <ResourceSection
            {...sectionCommon}
            title="Pihak yang berhak"
            itemName="Pihak"
            endpoint="pengadaan/party/"
            params={projectParams}
            fkOptions={{ parcel: options.parcel }}
            formFields={[
              "parcel",
              "party_type",
              "role",
              "name",
              "nik",
              "npwp",
              "share_percentage",
              "phone",
              "email",
              { name: "address", wide: true },
              "bank_name",
              "bank_account_number",
              "bank_account_holder",
              { name: "note", wide: true },
            ]}
            columns={[
              { key: "parcel_number", header: "Bidang" },
              { key: "name", header: "Nama" },
              {
                key: "role",
                header: "Peran",
                render: (r) => labelOf(choices, "PartyRole", r.role),
              },
              { key: "nik", header: "NIK", render: (r) => r.nik || "–" },
              {
                key: "share_percentage",
                header: "Porsi (%)",
                className: "acq-num",
                render: (r) => formatNumberId(r.share_percentage),
              },
              {
                key: "bank_account_number",
                header: "Rekening",
                render: (r) =>
                  r.bank_account_number
                    ? `${r.bank_name} ${r.bank_account_number}`
                    : "–",
              },
            ]}
          />
          <ResourceSection
            {...sectionCommon}
            title="Inventarisasi & identifikasi (Satgas A/B)"
            itemName="Survei"
            endpoint="pengadaan/survey/"
            params={projectParams}
            fkOptions={{ parcel: options.parcel, surveyor: options.user }}
            formFields={[
              "parcel",
              "survey_type",
              "status",
              "survey_date",
              "team_name",
              "surveyor",
              "latitude",
              "longitude",
              { name: "findings", wide: true },
            ]}
            columns={[
              { key: "parcel_number", header: "Bidang" },
              {
                key: "survey_type",
                header: "Jenis",
                render: (r) => labelOf(choices, "SurveyType", r.survey_type),
              },
              {
                key: "survey_date",
                header: "Tanggal",
                render: (r) => formatDateId(r.survey_date),
              },
              { key: "team_name", header: "Satgas" },
              { key: "surveyor_name", header: "Petugas" },
              {
                key: "status",
                header: "Status",
                render: (r) => (
                  <Tag value={r.status}>
                    {labelOf(choices, "SurveyStatus", r.status)}
                  </Tag>
                ),
              },
            ]}
          />
        </>
      )}

      {tab === "pengumuman" && (
        <ResourceSection
          {...sectionCommon}
          title="Pengumuman"
          itemName="Pengumuman"
          endpoint="pengadaan/announcement/"
          params={projectParams}
          defaults={{ project: Number(projectId) }}
          formFields={[
            "announcement_type",
            "announced_on",
            "location",
            "document_number",
            { name: "note", wide: true },
          ]}
          columns={[
            {
              key: "announcement_type",
              header: "Jenis",
              render: (r) =>
                labelOf(choices, "AnnouncementType", r.announcement_type),
            },
            {
              key: "announced_on",
              header: "Diumumkan",
              render: (r) => formatDateId(r.announced_on),
            },
            {
              key: "period_ends_on",
              header: "Masa pengumuman s.d.",
              render: (r) => formatDateId(r.period_ends_on),
            },
            {
              key: "objection_deadline",
              header: "Batas keberatan",
              render: (r) => formatDateId(r.objection_deadline),
            },
            { key: "location", header: "Tempat" },
            { key: "document_number", header: "Nomor" },
          ]}
        />
      )}

      {tab === "penilaian" && (
        <ResourceSection
          {...sectionCommon}
          title="Penilaian ganti kerugian (KJPP)"
          itemName="Penilaian"
          endpoint="pengadaan/valuation/"
          params={projectParams}
          fkOptions={{ parcel: options.parcel }}
          formFields={[
            "parcel",
            "status",
            "appraiser_firm",
            "appraiser_name",
            "appraiser_license",
            "report_number",
            "valuation_date",
            "submitted_on",
            "value_land",
            "value_space",
            "value_building",
            "value_plants",
            "value_other_objects",
            "value_non_physical",
            { name: "note", wide: true },
          ]}
          columns={[
            { key: "parcel_number", header: "Bidang" },
            { key: "appraiser_firm", header: "KJPP" },
            { key: "report_number", header: "No. laporan" },
            {
              key: "total_value",
              header: "Nilai total",
              className: "acq-num",
              render: (r) => formatRupiah(r.total_value),
            },
            {
              key: "submitted_on",
              header: "Diserahkan",
              render: (r) => formatDateId(r.submitted_on),
            },
            {
              key: "deliberation_deadline",
              header: "Batas musyawarah",
              render: (r) => formatDateId(r.deliberation_deadline),
            },
            {
              key: "status",
              header: "Status",
              render: (r) => (
                <Tag value={r.status}>
                  {labelOf(choices, "ValuationStatus", r.status)}
                </Tag>
              ),
            },
          ]}
        />
      )}

      {tab === "musyawarah" && (
        <>
          <ResourceSection
            {...sectionCommon}
            title="Musyawarah"
            itemName="Musyawarah"
            endpoint="pengadaan/deliberation/"
            params={projectParams}
            defaults={{ project: Number(projectId) }}
            fkOptions={{ chaired_by: options.user }}
            formFields={[
              "held_on",
              "location",
              "minutes_number",
              "chaired_by",
              { name: "note", wide: true },
            ]}
            columns={[
              {
                key: "held_on",
                header: "Tanggal",
                render: (r) => formatDateId(r.held_on),
              },
              { key: "location", header: "Tempat" },
              { key: "minutes_number", header: "No. berita acara" },
              { key: "chaired_by_name", header: "Dipimpin oleh" },
              { key: "result_count", header: "Hasil", className: "acq-num" },
            ]}
          />
          <ResourceSection
            {...sectionCommon}
            title="Hasil musyawarah per pihak"
            itemName="Hasil musyawarah"
            endpoint="pengadaan/deliberation_result/"
            params={projectParams}
            fkOptions={{
              deliberation: options.deliberation,
              parcel: options.parcel,
              party: options.party,
            }}
            formFields={[
              "deliberation",
              "parcel",
              "party",
              "outcome",
              "compensation_form",
              "agreed_amount",
              "signed_on",
              { name: "note", wide: true },
            ]}
            columns={[
              {
                key: "held_on",
                header: "Musyawarah",
                render: (r) => formatDateId(r.held_on),
              },
              { key: "parcel_number", header: "Bidang" },
              { key: "party_name", header: "Pihak" },
              {
                key: "outcome",
                header: "Hasil",
                render: (r) => (
                  <Tag value={r.outcome}>
                    {labelOf(choices, "DeliberationOutcome", r.outcome)}
                  </Tag>
                ),
              },
              {
                key: "compensation_form",
                header: "Bentuk",
                render: (r) =>
                  labelOf(choices, "CompensationForm", r.compensation_form),
              },
              {
                key: "agreed_amount",
                header: "Nilai disepakati",
                className: "acq-num",
                render: (r) => formatRupiah(r.agreed_amount),
              },
              {
                key: "objection_deadline",
                header: "Batas keberatan PN",
                render: (r) => formatDateId(r.objection_deadline),
              },
            ]}
          />
        </>
      )}

      {tab === "keberatan" && (
        <>
          <ResourceSection
            {...sectionCommon}
            title="Keberatan, gugatan & kasasi"
            itemName="Keberatan"
            endpoint="pengadaan/objection/"
            params={projectParams}
            defaults={{ project: Number(projectId) }}
            fkOptions={{
              parcel: options.parcel,
              party: options.party,
              parent: options.court_decision,
            }}
            formFields={[
              "objection_type",
              "status",
              "parcel",
              "party",
              "parent",
              "filed_by_name",
              "court_name",
              "case_number",
              "filed_on",
              "received_on",
              "decided_on",
              "decided_amount",
              { name: "decision_summary", wide: true },
              { name: "note", wide: true },
            ]}
            columns={[
              {
                key: "objection_type",
                header: "Jenis",
                render: (r) =>
                  labelOf(choices, "ObjectionType", r.objection_type),
              },
              { key: "case_number", header: "No. perkara" },
              {
                key: "parcel_number",
                header: "Bidang",
                render: (r) => r.parcel_number || "–",
              },
              {
                key: "filed_on",
                header: "Diajukan",
                render: (r) => formatDateId(r.filed_on),
              },
              {
                key: "decision_deadline",
                header: "Batas putusan",
                render: (r) => formatDateId(r.decision_deadline),
              },
              {
                key: "appeal_deadline",
                header: "Batas kasasi",
                render: (r) => formatDateId(r.appeal_deadline),
              },
              {
                key: "status",
                header: "Status",
                render: (r) => (
                  <Tag value={r.status}>
                    {labelOf(choices, "ObjectionStatus", r.status)}
                  </Tag>
                ),
              },
            ]}
          />
          <ResourceSection
            {...sectionCommon}
            title="Penitipan ganti kerugian (konsinyasi)"
            itemName="Konsinyasi"
            endpoint="pengadaan/consignment/"
            params={projectParams}
            fkOptions={{ parcel: options.parcel, party: options.party }}
            formFields={[
              "parcel",
              "party",
              "reason",
              "status",
              "court_name",
              "application_date",
              "decree_number",
              "decree_date",
              "deposited_on",
              "amount",
              "collected_on",
              { name: "note", wide: true },
            ]}
            columns={[
              { key: "parcel_number", header: "Bidang" },
              { key: "party_name", header: "Pihak" },
              {
                key: "reason",
                header: "Alasan",
                render: (r) => labelOf(choices, "ConsignmentReason", r.reason),
              },
              {
                key: "amount",
                header: "Jumlah",
                className: "acq-num",
                render: (r) => formatRupiah(r.amount),
              },
              {
                key: "acceptance_deadline",
                header: "Batas penerimaan PN",
                render: (r) => formatDateId(r.acceptance_deadline),
              },
              {
                key: "status",
                header: "Status",
                render: (r) => (
                  <Tag value={r.status}>
                    {labelOf(choices, "ConsignmentStatus", r.status)}
                  </Tag>
                ),
              },
            ]}
          />
        </>
      )}

      {tab === "ganti-kerugian" && (
        <>
          <ResourceSection
            {...sectionCommon}
            title="Ganti kerugian"
            itemName="Ganti kerugian"
            endpoint="pengadaan/compensation/"
            params={projectParams}
            fkOptions={{
              parcel: options.parcel,
              party: options.party,
              valuation: options.valuation,
              deliberation_result: options.deliberation_result,
              court_decision: options.court_decision,
            }}
            formFields={[
              "parcel",
              "party",
              "form",
              "amount",
              "status",
              "valuation",
              "deliberation_result",
              "court_decision",
              { name: "description", wide: true },
              { name: "note", wide: true },
            ]}
            rowActions={(row, reload) =>
              row.status === "determined" &&
              can(UsersPermissions.VALIDATE_COMPENSATION) && (
                <Button
                  variant="link"
                  onClick={() => validateCompensation(row, reload)}
                >
                  Validasi
                </Button>
              )
            }
            columns={[
              { key: "parcel_number", header: "Bidang" },
              { key: "party_name", header: "Pihak" },
              {
                key: "form",
                header: "Bentuk",
                render: (r) => labelOf(choices, "CompensationForm", r.form),
              },
              {
                key: "amount",
                header: "Nilai",
                className: "acq-num",
                render: (r) => formatRupiah(r.amount),
              },
              {
                key: "paid_amount",
                header: "Dibayar",
                className: "acq-num",
                render: (r) => formatRupiah(r.paid_amount),
              },
              {
                key: "outstanding_amount",
                header: "Sisa",
                className: "acq-num",
                render: (r) => formatRupiah(r.outstanding_amount),
              },
              {
                key: "status",
                header: "Status",
                render: (r) => (
                  <Tag value={r.status}>
                    {labelOf(choices, "CompensationStatus", r.status)}
                  </Tag>
                ),
              },
              {
                key: "validated_by_name",
                header: "Divalidasi oleh",
                render: (r) =>
                  r.validated_by_name
                    ? `${r.validated_by_name} (${formatDateId(r.validated_on)})`
                    : "–",
              },
            ]}
          />
          <ResourceSection
            {...sectionCommon}
            title="Pembayaran"
            itemName="Pembayaran"
            endpoint="pengadaan/payment/"
            params={projectParams}
            fkOptions={{ compensation: options.compensation }}
            formFields={[
              "compensation",
              "paid_on",
              "amount",
              "method",
              "bank_reference",
              "recipient_name",
              { name: "note", wide: true },
            ]}
            columns={[
              {
                key: "compensation",
                header: "Ganti kerugian",
                render: (r) =>
                  options.compensation.find((o) => o.value === r.compensation)
                    ?.label || r.compensation,
              },
              {
                key: "paid_on",
                header: "Tanggal",
                render: (r) => formatDateId(r.paid_on),
              },
              {
                key: "amount",
                header: "Jumlah",
                className: "acq-num",
                render: (r) => formatRupiah(r.amount),
              },
              {
                key: "method",
                header: "Metode",
                render: (r) => labelOf(choices, "PaymentMethod", r.method),
              },
              { key: "bank_reference", header: "Referensi" },
              { key: "recipient_name", header: "Penerima" },
            ]}
          />
        </>
      )}

      {tab === "pelepasan" && (
        <>
          <ResourceSection
            {...sectionCommon}
            title="Pelepasan hak"
            itemName="Pelepasan hak"
            endpoint="pengadaan/rights_release/"
            params={projectParams}
            fkOptions={{ parcel: options.parcel, party: options.party }}
            formFields={[
              "parcel",
              "party",
              "minutes_number",
              "released_on",
              "certificate_surrendered",
              { name: "note", wide: true },
            ]}
            columns={[
              { key: "parcel_number", header: "Bidang" },
              { key: "party_name", header: "Pihak" },
              { key: "minutes_number", header: "No. berita acara" },
              {
                key: "released_on",
                header: "Tanggal",
                render: (r) => formatDateId(r.released_on),
              },
              {
                key: "certificate_surrendered",
                header: "Asli alas hak diserahkan",
                render: (r) => (r.certificate_surrendered ? "Ya" : "Belum"),
              },
              {
                key: "handover_deadline",
                header: "Batas penyerahan hasil",
                render: (r) => formatDateId(r.handover_deadline),
              },
            ]}
          />
          <ResourceSection
            {...sectionCommon}
            title="Penyerahan hasil kepada instansi"
            itemName="Penyerahan hasil"
            endpoint="pengadaan/handover/"
            params={projectParams}
            defaults={{ project: Number(projectId) }}
            fkOptions={{ parcels: options.parcel }}
            formFields={[
              "minutes_number",
              "handed_over_on",
              "recipient",
              { name: "parcels", multiple: true, wide: true },
              "registration_applied_on",
              "registration_number",
              { name: "note", wide: true },
            ]}
            columns={[
              { key: "minutes_number", header: "No. BAST" },
              {
                key: "handed_over_on",
                header: "Tanggal",
                render: (r) => formatDateId(r.handed_over_on),
              },
              { key: "recipient", header: "Penerima" },
              {
                key: "parcels",
                header: "Bidang",
                render: (r) => (r.parcels || []).length,
              },
              {
                key: "registration_deadline",
                header: "Batas pendaftaran hak",
                render: (r) => formatDateId(r.registration_deadline),
              },
              {
                key: "registration_number",
                header: "No. pendaftaran/sertipikat",
                render: (r) => r.registration_number || "–",
              },
            ]}
          />
        </>
      )}

      {tab === "relokasi" && (
        <ResourceSection
          {...sectionCommon}
          title="Rumah tangga terdampak & permukiman kembali"
          itemName="Rumah tangga"
          endpoint="pengadaan/household/"
          params={projectParams}
          defaults={{ project: Number(projectId) }}
          fkOptions={{ parcel: options.parcel }}
          formFields={[
            "parcel",
            "head_name",
            "nik",
            "family_card_number",
            "member_count",
            "displacement",
            "stage",
            "monetary_assistance_amount",
            "progress_percentage",
            { name: "assistance_description", wide: true },
            { name: "note", wide: true },
          ]}
          columns={[
            { key: "head_name", header: "Kepala keluarga" },
            {
              key: "parcel_number",
              header: "Bidang",
              render: (r) => r.parcel_number || "–",
            },
            { key: "member_count", header: "Anggota", className: "acq-num" },
            {
              key: "displacement",
              header: "Dampak",
              render: (r) =>
                labelOf(choices, "DisplacementStatus", r.displacement),
            },
            {
              key: "stage",
              header: "Tahap",
              render: (r) => labelOf(choices, "ResettlementStage", r.stage),
            },
            {
              key: "monetary_assistance_amount",
              header: "Bantuan uang",
              className: "acq-num",
              render: (r) => formatRupiah(r.monetary_assistance_amount),
            },
            {
              key: "progress_percentage",
              header: "Kemajuan",
              render: (r) => (
                <Progress value={Number(r.progress_percentage || 0)} />
              ),
            },
          ]}
        />
      )}

      {tab === "dokumen" && (
        <ResourceSection
          {...sectionCommon}
          title="Dokumen pengadaan"
          itemName="Dokumen"
          endpoint="pengadaan/document/"
          params={projectParams}
          defaults={{ project: Number(projectId) }}
          canEdit={false}
          fkOptions={{ parcel: options.parcel, party: options.party }}
          formFields={[
            "document_type",
            { name: "title", wide: true },
            "number",
            "document_date",
            "parcel",
            "party",
            { name: "file", wide: true },
            { name: "note", wide: true },
          ]}
          rowActions={(row) => (
            <Button
              variant="link"
              onClick={() =>
                apiDownload(
                  `pengadaan/document/${row.id}/download/`,
                  row.file_name || "dokumen",
                ).catch((e) =>
                  displayUIMessage(
                    { title: "", body: (e as Error).message },
                    { type: "error" },
                  ),
                )
              }
            >
              Unduh
            </Button>
          )}
          columns={[
            {
              key: "document_type",
              header: "Jenis",
              render: (r) => labelOf(choices, "DocumentType", r.document_type),
            },
            { key: "title", header: "Judul" },
            { key: "number", header: "Nomor" },
            {
              key: "document_date",
              header: "Tanggal",
              render: (r) => formatDateId(r.document_date),
            },
            { key: "file_name", header: "Berkas" },
            { key: "uploaded_by_name", header: "Diunggah oleh" },
          ]}
        />
      )}

      {tab === "tenggat" && (
        <Section title="Tenggat hukum proyek ini">
          <DataTable<Deadline>
            rows={s?.deadlines || []}
            empty="Tidak ada tenggat terbuka."
            columns={[
              {
                key: "state",
                header: "Status",
                render: (r) => (
                  <Tag value={r.state}>
                    {r.state === "overdue"
                      ? "Terlewat"
                      : r.state === "due_soon"
                        ? "Segera"
                        : "Akan datang"}
                  </Tag>
                ),
              },
              {
                key: "due_date",
                header: "Batas waktu",
                render: (r) => formatDateId(r.due_date),
              },
              { key: "workdays_left", header: "Sisa hari kerja" },
              { key: "title", header: "Kewajiban" },
              {
                key: "parcel_number",
                header: "Bidang",
                render: (r) =>
                  r.parcel_id ? (
                    <Link to={parcelUrl(r.parcel_id)}>{r.parcel_number}</Link>
                  ) : (
                    "–"
                  ),
              },
              { key: "reference", header: "Referensi" },
            ]}
          />
        </Section>
      )}
    </PageContainerHDS>
  );
};

export default AcquisitionProjectPage;
