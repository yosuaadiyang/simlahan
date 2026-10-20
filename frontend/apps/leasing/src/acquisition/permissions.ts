import { useMemo } from "react";
import { isEmpty } from "lodash-es";
import { useAppSelector } from "@/root/hooks";
import { getUsersPermissions } from "@/usersPermissions/selectors";
import { hasPermissions } from "@/util/helpers";
import type { UsersPermissions } from "@/usersPermissions/types";

/** Nama model Django (bagian codename izin) per endpoint API pengadaan. */
export const ENDPOINT_MODELS: Record<string, string> = {
  "pengadaan/project/": "acquisitionproject",
  "pengadaan/milestone/": "acquisitionmilestone",
  "pengadaan/parcel/": "acquisitionparcel",
  "pengadaan/party/": "entitledparty",
  "pengadaan/survey/": "parcelsurvey",
  "pengadaan/inventory_item/": "inventoryitem",
  "pengadaan/announcement/": "announcement",
  "pengadaan/valuation/": "valuation",
  "pengadaan/deliberation/": "deliberation",
  "pengadaan/deliberation_result/": "deliberationresult",
  "pengadaan/objection/": "objection",
  "pengadaan/consignment/": "consignment",
  "pengadaan/compensation/": "compensation",
  "pengadaan/payment/": "compensationpayment",
  "pengadaan/rights_release/": "rightsrelease",
  "pengadaan/handover/": "handover",
  "pengadaan/household/": "affectedhousehold",
  "pengadaan/document/": "acquisitiondocument",
  "pengadaan/holiday/": "holiday",
  "pengadaan/deadline_rule/": "deadlinerule",
};

export type ResourcePermissions = {
  /** Izin pengguna sudah dimuat dari server. */
  isLoaded: boolean;
  canView: boolean;
  canAdd: boolean;
  canChange: boolean;
  canDelete: boolean;
};

/** Hak lihat/tambah/ubah/hapus pengguna atas satu endpoint pengadaan. */
export const getResourcePermissions = (
  usersPermissions: UsersPermissions,
  endpoint: string,
): ResourcePermissions => {
  const isLoaded = !isEmpty(usersPermissions);
  const model = ENDPOINT_MODELS[endpoint];
  if (!model) {
    // Endpoint tak dikenal: biarkan server yang memutuskan.
    return {
      isLoaded,
      canView: true,
      canAdd: true,
      canChange: true,
      canDelete: true,
    };
  }
  const can = (action: string) =>
    hasPermissions(usersPermissions, `${action}_${model}`);
  return {
    isLoaded,
    canView: can("view"),
    canAdd: can("add"),
    canChange: can("change"),
    canDelete: can("delete"),
  };
};

export type ProjectCapabilities = {
  /** Nama pihak (kolom, keterangan peta) boleh ditampilkan. */
  canViewParties: boolean;
  /** Daftar nominatif memuat pihak, nilai penilaian dan ganti kerugian. */
  canExportNominative: boolean;
  /** Impor peta lewat endpoint proyek: perlu tambah bidang dan tambah proyek. */
  canImportParcels: boolean;
  /** Mencatat pembayaran/penyerahan ganti kerugian. */
  canRecordPayment: boolean;
};

/** Kemampuan halaman proyek yang bergantung pada beberapa izin sekaligus. */
export const getProjectCapabilities = (
  usersPermissions: UsersPermissions,
): ProjectCapabilities => {
  const resource = (endpoint: string) =>
    getResourcePermissions(usersPermissions, endpoint);
  const canViewParties = resource("pengadaan/party/").canView;
  return {
    canViewParties,
    canExportNominative:
      canViewParties &&
      resource("pengadaan/valuation/").canView &&
      resource("pengadaan/compensation/").canView,
    canImportParcels:
      resource("pengadaan/parcel/").canAdd &&
      resource("pengadaan/project/").canAdd,
    canRecordPayment: resource("pengadaan/payment/").canAdd,
  };
};

export const useProjectCapabilities = (): ProjectCapabilities => {
  const usersPermissions = useAppSelector(getUsersPermissions);
  return useMemo(
    () => getProjectCapabilities(usersPermissions),
    [usersPermissions],
  );
};

export const useResourcePermissions = (
  endpoint: string,
): ResourcePermissions => {
  const usersPermissions = useAppSelector(getUsersPermissions);
  return useMemo(
    () => getResourcePermissions(usersPermissions, endpoint),
    [usersPermissions, endpoint],
  );
};

/** Pemeriksa izin lihat untuk banyak endpoint sekaligus. */
export const useCanViewResource = (): ((endpoint: string) => boolean) => {
  const usersPermissions = useAppSelector(getUsersPermissions);
  return useMemo(
    () => (endpoint: string) =>
      getResourcePermissions(usersPermissions, endpoint).canView,
    [usersPermissions],
  );
};
