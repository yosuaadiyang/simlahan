import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useAppDispatch } from "@/root/hooks";
import PageContainerHDS from "@/components/content/PageContainerHDS";
import { receiveTopNavigationSettings } from "@/components/topNavigation/actions";
import { getRouteById, Routes } from "@/root/routes";
import { displayUIMessage, setPageTitle } from "@/util/helpers";
import { apiGet, apiGetAll } from "../api";
import { useApi, useChoices, useDistricts } from "../hooks";
import { useResourcePermissions } from "../permissions";
import {
  formatArea,
  formatDateId,
  formatNumberId,
  formatRupiah,
} from "../format";
import AcquisitionMap from "./AcquisitionMap";
import ResourceForm from "./ResourceForm";
import ResourceSection from "./ResourceSection";
import { Button, ErrorText, Section, Tag, labelOf } from "./ui";

const PARCEL_FIELDS = [
  "parcel_number",
  "nib",
  "district",
  "village",
  { name: "address", wide: true },
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
];

const AcquisitionParcelPage: React.FC = () => {
  const { projectId = "", parcelId = "" } = useParams();
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const [version, setVersion] = useState(0);
  const bump = useCallback(() => setVersion((v) => v + 1), []);
  const [isEditing, setIsEditing] = useState(false);
  const { data: choices } = useChoices();
  const parcelPermissions = useResourcePermissions("pengadaan/parcel/");
  const canViewParties = useResourcePermissions("pengadaan/party/").canView;
  const project = useApi(
    () => apiGet(`pengadaan/project/${projectId}/`),
    [projectId],
  );
  const parcel = useApi(
    () => apiGet(`pengadaan/parcel/${parcelId}/`),
    [parcelId, version],
  );
  const geojson = useApi(
    () => apiGet(`pengadaan/project/${projectId}/geojson/`),
    [projectId, version],
  );
  const parties = useApi(
    canViewParties
      ? () => apiGetAll("pengadaan/party/", { parcel: parcelId })
      : null,
    [parcelId, version, canViewParties],
  );
  const partyOptions = useMemo(
    () =>
      (parties.data || []).map((r: Record<string, any>) => ({
        value: r.id,
        label: r.name,
      })),
    [parties.data],
  );
  const { data: districts } = useDistricts(project.data?.municipality);
  const districtOptions = useMemo(
    () => (districts || []).map((d) => ({ value: d.id, label: d.name })),
    [districts],
  );

  const p = parcel.data;
  useEffect(() => {
    setPageTitle(p ? `Bidang ${p.parcel_number}` : "Bidang tanah");
    dispatch(
      receiveTopNavigationSettings({
        linkUrl: getRouteById(Routes.ACQUISITIONS),
        pageTitle: "Pengadaan Tanah",
        showSearch: false,
      }),
    );
  }, [dispatch, p]);

  const projectUrl = `${getRouteById(Routes.ACQUISITIONS)}/${projectId}`;
  const statusLabels = Object.fromEntries(
    (choices?.ParcelStatus || []).map((c) => [c.value, c.label]),
  );

  if (parcel.error) {
    return (
      <PageContainerHDS className="acq-page">
        <ErrorText>{parcel.error}</ErrorText>
        <Link to={projectUrl}>Kembali ke proyek</Link>
      </PageContainerHDS>
    );
  }
  if (!p) {
    return (
      <PageContainerHDS className="acq-page">
        <p className="acq-muted">Memuat bidang…</p>
      </PageContainerHDS>
    );
  }

  const parcelParams = { parcel: parcelId };
  const common = { refreshKey: version, onChanged: bump };

  return (
    <PageContainerHDS className="acq-page">
      <header className="acq-page__header">
        <div>
          <p className="acq-muted">
            <Link to={getRouteById(Routes.ACQUISITIONS)}>Proyek pengadaan</Link>{" "}
            /{" "}
            <Link to={projectUrl}>{project.data?.identifier || projectId}</Link>{" "}
            / bidang {p.parcel_number}
          </p>
          <h1>Bidang {p.parcel_number}</h1>
          <p>
            <Tag value={p.status}>
              {labelOf(choices, "ParcelStatus", p.status)}
            </Tag>{" "}
            {p.is_disputed && <Tag value="objection">Bersengketa</Tag>}{" "}
            <span className="acq-muted">
              {labelOf(choices, "LandRightType", p.right_type)} ·{" "}
              {formatArea(p.affected_area_m2)} terkena dari{" "}
              {formatArea(p.measured_area_m2)}
            </span>
          </p>
        </div>
        {parcelPermissions.canChange && (
          <div className="acq-page__actions">
            <Button variant="secondary" onClick={() => setIsEditing((v) => !v)}>
              {isEditing ? "Tutup" : "Ubah data bidang"}
            </Button>
          </div>
        )}
      </header>

      <div className="acq-columns">
        <Section title="Data bidang">
          {isEditing ? (
            <ResourceForm
              endpoint="pengadaan/parcel/"
              fields={PARCEL_FIELDS}
              instance={p}
              fkOptions={{ district: districtOptions }}
              onCancel={() => setIsEditing(false)}
              onSaved={() => {
                setIsEditing(false);
                displayUIMessage({ title: "", body: "Bidang disimpan" });
                bump();
              }}
            />
          ) : (
            <dl className="acq-dl">
              <dt>NIB</dt>
              <dd>{p.nib || "–"}</dd>
              <dt>Sertipikat / alas hak</dt>
              <dd>{p.certificate_number || "–"}</dd>
              <dt>Lokasi</dt>
              <dd>
                {[p.address, p.village, p.district_name]
                  .filter(Boolean)
                  .join(", ") || "–"}
              </dd>
              <dt>Penggunaan tanah</dt>
              <dd>{labelOf(choices, "LandUse", p.land_use)}</dd>
              <dt>Sisa luas</dt>
              <dd>{formatArea(p.remaining_area_m2)}</dd>
              <dt>Bangunan</dt>
              <dd>
                {p.building_description || "–"}
                {p.building_area_m2
                  ? ` (${formatArea(p.building_area_m2)})`
                  : ""}
              </dd>
              <dt>Tanaman</dt>
              <dd>{p.plants_description || "–"}</dd>
              <dt>Benda lain</dt>
              <dd>{p.other_objects_description || "–"}</dd>
              <dt>Catatan</dt>
              <dd>{p.note || "–"}</dd>
            </dl>
          )}
        </Section>
        <Section title="Peta">
          <AcquisitionMap
            featureCollection={geojson.data}
            highlightParcelId={Number(parcelId)}
            statusLabels={statusLabels}
            showParties={canViewParties}
            height={360}
            onParcelClick={(id) =>
              id !== Number(parcelId) && navigate(`${projectUrl}/bidang/${id}`)
            }
          />
        </Section>
      </div>

      <ResourceSection
        {...common}
        title="Pihak yang berhak"
        itemName="Pihak"
        endpoint="pengadaan/party/"
        params={parcelParams}
        defaults={{ parcel: Number(parcelId) }}
        formFields={[
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
          { key: "phone", header: "Telepon" },
        ]}
      />
      <ResourceSection
        {...common}
        title="Inventarisasi & identifikasi"
        itemName="Survei"
        endpoint="pengadaan/survey/"
        params={parcelParams}
        defaults={{ parcel: Number(parcelId) }}
        formFields={[
          "survey_type",
          "status",
          "survey_date",
          "team_name",
          "latitude",
          "longitude",
          { name: "findings", wide: true },
        ]}
        columns={[
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
      <ResourceSection
        {...common}
        title="Objek inventarisasi"
        itemName="Objek"
        endpoint="pengadaan/inventory_item/"
        params={parcelParams}
        defaults={{ parcel: Number(parcelId) }}
        fkOptions={{ party: partyOptions }}
        emptyText="Belum ada objek. Catat bangunan, tanaman, dan benda lain di atas bidang ini."
        formFields={[
          "item_type",
          "party",
          { name: "description", wide: true },
          "quantity",
          "unit",
          "condition",
          "unit_value",
          { name: "note", wide: true },
        ]}
        columns={[
          {
            key: "item_type",
            header: "Jenis",
            render: (r) => labelOf(choices, "InventoryItemType", r.item_type),
          },
          { key: "description", header: "Uraian" },
          {
            key: "quantity",
            header: "Jumlah",
            className: "acq-num",
            render: (r) =>
              `${formatNumberId(r.quantity)} ${r.unit || ""}`.trim(),
          },
          {
            key: "party_name",
            header: "Pemilik",
            render: (r) => r.party_name || "–",
          },
          {
            key: "total_value",
            header: "Perkiraan nilai",
            className: "acq-num",
            render: (r) => formatRupiah(r.total_value),
          },
        ]}
      />
      <ResourceSection
        {...common}
        title="Penilaian"
        itemName="Penilaian"
        endpoint="pengadaan/valuation/"
        params={parcelParams}
        defaults={{ parcel: Number(parcelId) }}
        formFields={[
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
          { key: "appraiser_firm", header: "KJPP" },
          { key: "report_number", header: "No. laporan" },
          {
            key: "total_value",
            header: "Nilai total",
            className: "acq-num",
            render: (r) => formatRupiah(r.total_value),
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
      <ResourceSection
        {...common}
        title="Ganti kerugian"
        itemName="Ganti kerugian"
        endpoint="pengadaan/compensation/"
        params={parcelParams}
        canAdd={false}
        canEdit={false}
        canDelete={false}
        emptyText="Belum ada ganti kerugian. Kelola melalui tab Ganti kerugian pada proyek."
        formFields={[]}
        columns={[
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
            key: "status",
            header: "Status",
            render: (r) => (
              <Tag value={r.status}>
                {labelOf(choices, "CompensationStatus", r.status)}
              </Tag>
            ),
          },
        ]}
      />
    </PageContainerHDS>
  );
};

export default AcquisitionParcelPage;
