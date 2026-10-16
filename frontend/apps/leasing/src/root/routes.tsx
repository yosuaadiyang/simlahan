import React from "react";
import { Navigate, Route, Routes as RouterRoutes } from "react-router";
import ErrorPage from "@/errorPage/ErrorPage";
import App from "@/app/App";
import AreaNoteListPage from "@/areaNote/components/AreaNoteListPage";
import BasisOfRentCalculatorPage from "@/basisOfRentCalculator/components/BasisOfRentCalculatorPage";
import BatchRunPage from "@/batchrun/components/BatchRunPage";
import ContactListPage from "@/contacts/components/ContactsListPage";
import ContactPage from "@/contacts/components/ContactPage";
import IndexListPage from "@/index/components/IndexListPage";
import InfillDevelopmentPage from "@/infillDevelopment/components/InfillDevelopmentPage";
import InfillDevelopmentListPage from "@/infillDevelopment/components/InfillDevelopmentListPage";
import InvoiceNoteListPage from "@/invoiceNote/components/InvoiceNoteListPage";
import LeaseListPage from "@/leases/components/LeaseListPage";
import LeasePage from "@/leases/components/LeasePage";
import NewContactPage from "@/contacts/components/NewContactPage";
import NewInfillDevelopmentPage from "@/infillDevelopment/components/NewInfillDevelopmentPage";
import NewRentBasisPage from "@/rentbasis/components/NewRentBasisPage";
import PlotSearchListPage from "@/plotSearch/components/PlotSearchListPage";
import PlotApplicationsListPage from "@/plotApplications/components/PlotApplicationsListPage";
import PlotSearchPage from "@/plotSearch/components/PlotSearchPage";
import PlotApplicationsPage from "@/plotApplications/components/PlotApplicationPage";
import RentBasisListPage from "@/rentbasis/components/RentBasisListPage";
import RentBasisPage from "@/rentbasis/components/RentBasisPage";
import LeaseReportsPage from "@/reports/components/LeaseReportsPage";
import PlotApplicationCreatePage from "@/plotApplications/components/PlotApplicationCreatePage";
import AreaSearchApplicationListPage from "@/areaSearch/components/AreaSearchApplicationListPage";
import AreaSearchApplicationPage from "@/areaSearch/components/AreaSearchApplicationPage";
import AreaSearchApplicationCreatePage from "@/areaSearch/components/AreaSearchApplicationCreatePage";
import AcquisitionDashboardPage from "@/acquisition/components/AcquisitionDashboardPage";
import AcquisitionListPage from "@/acquisition/components/AcquisitionListPage";
import AcquisitionProjectPage from "@/acquisition/components/AcquisitionProjectPage";
import AcquisitionParcelPage from "@/acquisition/components/AcquisitionParcelPage";
import AcquisitionSettingsPage from "@/acquisition/components/AcquisitionSettingsPage";

/**
 * Routes enumerate
 * @enum {string}
 */
export const Routes = {
  ACQUISITIONS: "acquisitions",
  ACQUISITION_DASHBOARD: "acquisition_dashboard",
  ACQUISITION_SETTINGS: "acquisition_settings",
  AREA_NOTES: "area_notes",
  AREA_SEARCH: "area_search",
  BASIS_OF_RENT_CALCULATOR: "basis_of_rent_calculator",
  BATCH_RUN: "batch_jobs",
  CONTACTS: "contacts",
  CONTACT_NEW: "contact_new",
  INDEX: "index",
  INFILL_DEVELOPMENTS: "infill_developments",
  INFILL_DEVELOPMENT_NEW: "infill_development_new",
  INVOICE_NOTES: "invoice_notes",
  LEASES: "leases",
  LOGOUT: "logout",
  PLOT_SEARCH: "plotSearch",
  PLOT_APPLICATIONS: "plotApplications",
  RENT_BASIS: "rent_basis",
  RENT_BASIS_NEW: "rent_basis_new",
  LEASE_REPORTS: "reports",
};

/**
 * Get route by id
 * @param {string} string
 * @returns {string}
 */
export const getRouteById = (id: string): string => {
  const routes = {
    [Routes.ACQUISITIONS]: "/pengadaan-tanah",
    [Routes.ACQUISITION_DASHBOARD]: "/dasbor-pengadaan",
    [Routes.ACQUISITION_SETTINGS]: "/pengaturan-pengadaan",
    [Routes.AREA_NOTES]: "/catatan-area",
    [Routes.AREA_SEARCH]: "/pencarian-area",
    [Routes.BASIS_OF_RENT_CALCULATOR]: "/kalkulator-sewa",
    [Routes.BATCH_RUN]: "/tugas-terjadwal",
    [Routes.CONTACTS]: "/kontak",
    [Routes.CONTACT_NEW]: "/kontak-baru",
    [Routes.INDEX]: "/indeks",
    [Routes.INFILL_DEVELOPMENTS]: "/kompensasi-pembangunan-sisipan",
    [Routes.INFILL_DEVELOPMENT_NEW]: "/kompensasi-pembangunan-sisipan-baru",
    [Routes.INVOICE_NOTES]: "/catatan-tagihan",
    [Routes.LEASES]: "/sewa",
    [Routes.LOGOUT]: "/keluar",
    [Routes.PLOT_SEARCH]: "/pencarian-kavling",
    [Routes.PLOT_APPLICATIONS]: "/permohonan-kavling",
    [Routes.RENT_BASIS]: "/dasar-sewa",
    [Routes.RENT_BASIS_NEW]: "/dasar-sewa-baru",
    [Routes.LEASE_REPORTS]: "/laporan",
  };
  return routes[id] ? routes[id] : "";
};
export default (
  <App>
    <RouterRoutes>
      <Route path="/" element={<Navigate to={getRouteById(Routes.LEASES)} />} />
      <Route path={getRouteById(Routes.LEASES)} element={<LeaseListPage />} />
      <Route
        path={getRouteById(Routes.ACQUISITION_DASHBOARD)}
        element={<AcquisitionDashboardPage />}
      />
      <Route
        path={getRouteById(Routes.ACQUISITIONS)}
        element={<AcquisitionListPage />}
      />
      <Route
        path={`${getRouteById(Routes.ACQUISITIONS)}/:projectId`}
        element={<AcquisitionProjectPage />}
      />
      <Route
        path={`${getRouteById(Routes.ACQUISITIONS)}/:projectId/bidang/:parcelId`}
        element={<AcquisitionParcelPage />}
      />
      <Route
        path={getRouteById(Routes.ACQUISITION_SETTINGS)}
        element={<AcquisitionSettingsPage />}
      />
      <Route
        path={`${getRouteById(Routes.LEASES)}/:leaseId`}
        element={<LeasePage />}
      />
      <Route
        path={getRouteById(Routes.CONTACTS)}
        element={<ContactListPage />}
      />
      <Route
        path={`${getRouteById(Routes.CONTACTS)}/:contactId`}
        element={<ContactPage />}
      />
      <Route
        path={getRouteById(Routes.CONTACT_NEW)}
        element={<NewContactPage />}
      />
      <Route
        path={getRouteById(Routes.INVOICE_NOTES)}
        element={<InvoiceNoteListPage />}
      />
      <Route
        path={`${getRouteById(Routes.INDEX)}`}
        element={<IndexListPage />}
      />
      <Route
        path={getRouteById(Routes.AREA_NOTES)}
        element={<AreaNoteListPage />}
      />
      <Route
        path={`${getRouteById(Routes.INFILL_DEVELOPMENTS)}`}
        element={<InfillDevelopmentListPage />}
      />
      <Route
        path={`${getRouteById(Routes.INFILL_DEVELOPMENTS)}/:infillDevelopmentId`}
        element={<InfillDevelopmentPage />}
      />
      <Route
        path={getRouteById(Routes.INFILL_DEVELOPMENT_NEW)}
        element={<NewInfillDevelopmentPage />}
      />
      <Route
        path={getRouteById(Routes.LEASE_REPORTS)}
        element={<LeaseReportsPage />}
      />
      <Route
        path={getRouteById(Routes.RENT_BASIS)}
        element={<RentBasisListPage />}
      />
      <Route
        path={`${getRouteById(Routes.RENT_BASIS)}/:rentBasisId`}
        element={<RentBasisPage />}
      />
      <Route
        path={getRouteById(Routes.RENT_BASIS_NEW)}
        element={<NewRentBasisPage />}
      />
      <Route path={getRouteById(Routes.BATCH_RUN)} element={<BatchRunPage />} />
      <Route
        path={getRouteById(Routes.BASIS_OF_RENT_CALCULATOR)}
        element={<BasisOfRentCalculatorPage />}
      />
      <Route
        path={getRouteById(Routes.PLOT_SEARCH)}
        element={<PlotSearchListPage />}
      />
      <Route
        path={`${getRouteById(Routes.PLOT_SEARCH)}/:plotSearchId`}
        element={<PlotSearchPage />}
      />
      <Route
        path={getRouteById(Routes.PLOT_APPLICATIONS)}
        element={<PlotApplicationsListPage />}
      />
      <Route
        path={`${getRouteById(Routes.PLOT_APPLICATIONS)}/baru`}
        element={<PlotApplicationCreatePage />}
      />
      <Route
        path={`${getRouteById(Routes.PLOT_APPLICATIONS)}/:plotApplicationId`}
        element={<PlotApplicationsPage />}
      />
      <Route
        path={getRouteById(Routes.AREA_SEARCH)}
        element={<AreaSearchApplicationListPage />}
      />
      <Route
        path={`${getRouteById(Routes.AREA_SEARCH)}/baru`}
        element={<AreaSearchApplicationCreatePage />}
      />
      <Route
        path={`${getRouteById(Routes.AREA_SEARCH)}/:areaSearchId`}
        element={<AreaSearchApplicationPage />}
      />
      <Route path="*" element={<ErrorPage />} />
    </RouterRoutes>
  </App>
);
