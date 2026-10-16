import React, { useEffect, useState } from "react";
import { useAppDispatch } from "@/root/hooks";
import PageContainerHDS from "@/components/content/PageContainerHDS";
import { receiveTopNavigationSettings } from "@/components/topNavigation/actions";
import { getRouteById, Routes } from "@/root/routes";
import { setPageTitle } from "@/util/helpers";
import { apiGet } from "../api";
import { formatDateId } from "../format";
import ResourceSection from "./ResourceSection";
import { Button, ErrorText, Section } from "./ui";

const UNIT_LABEL: Record<string, string> = {
  workdays: "hari kerja",
  days: "hari",
  years: "tahun",
};

const WorkdayCalculator: React.FC = () => {
  const [start, setStart] = useState("");
  const [days, setDays] = useState("14");
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const calculate = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setResult(null);
    try {
      const data = await apiGet("pengadaan/workdays/", { start, days });
      setResult(formatDateId(data.date));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <form className="acq-filters" onSubmit={calculate}>
      <label>
        Tanggal awal{" "}
        <input
          type="date"
          value={start}
          onChange={(e) => setStart(e.target.value)}
          required
        />
      </label>
      <label>
        + hari kerja{" "}
        <input
          type="number"
          min={0}
          max={3650}
          value={days}
          onChange={(e) => setDays(e.target.value)}
          required
        />
      </label>
      <Button type="submit">Hitung</Button>
      {result && <strong className="acq-success">Jatuh pada {result}</strong>}
      {error && <ErrorText>{error}</ErrorText>}
    </form>
  );
};

const AcquisitionSettingsPage: React.FC = () => {
  const dispatch = useAppDispatch();
  const [year, setYear] = useState<string>(String(new Date().getFullYear()));

  useEffect(() => {
    setPageTitle("Kalender & aturan tenggat");
    dispatch(
      receiveTopNavigationSettings({
        linkUrl: getRouteById(Routes.ACQUISITION_SETTINGS),
        pageTitle: "Pengadaan Tanah",
        showSearch: false,
      }),
    );
  }, [dispatch]);

  return (
    <PageContainerHDS className="acq-page">
      <header className="acq-page__header">
        <div>
          <h1>Kalender & aturan tenggat</h1>
          <p className="acq-muted">
            Tenggat dihitung dalam hari kerja (Senin–Jumat di luar libur
            nasional dan cuti bersama). Perbarui daftar libur setiap tahun
            sesuai SKB 3 Menteri.
          </p>
        </div>
      </header>

      <Section title="Kalkulator hari kerja">
        <WorkdayCalculator />
      </Section>

      <ResourceSection
        title="Aturan tenggat"
        itemName="Aturan"
        endpoint="pengadaan/deadline_rule/"
        params={{ ordering: "code" }}
        canAdd={false}
        canDelete={false}
        formFields={[
          "name",
          "amount",
          "unit",
          "legal_basis",
          { name: "description", wide: true },
        ]}
        columns={[
          { key: "name", header: "Aturan" },
          {
            key: "amount",
            header: "Jangka waktu",
            render: (r) => `${r.amount} ${UNIT_LABEL[r.unit] || r.unit}`,
          },
          { key: "legal_basis", header: "Dasar hukum" },
          { key: "description", header: "Keterangan" },
        ]}
      />

      <ResourceSection
        title="Hari libur & cuti bersama"
        itemName="Hari libur"
        endpoint="pengadaan/holiday/"
        params={{
          date__year: year,
          ordering: "date",
        }}
        headerActions={
          <select
            aria-label="Tahun"
            value={year}
            onChange={(e) => setYear(e.target.value)}
          >
            {Array.from(
              { length: 6 },
              (_, i) => new Date().getFullYear() - 1 + i,
            ).map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        }
        formFields={["date", "name", "is_collective_leave"]}
        columns={[
          {
            key: "date",
            header: "Tanggal",
            render: (r) => formatDateId(r.date),
          },
          { key: "name", header: "Keterangan" },
          {
            key: "is_collective_leave",
            header: "Jenis",
            render: (r) =>
              r.is_collective_leave ? "Cuti bersama" : "Libur nasional",
          },
        ]}
      />
    </PageContainerHDS>
  );
};

export default AcquisitionSettingsPage;
