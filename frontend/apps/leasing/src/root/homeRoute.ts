import { UsersPermissions } from "@/usersPermissions/enums";
import { hasPermissions } from "@/util/helpers";
import type { UsersPermissions as UsersPermissionsType } from "@/usersPermissions/types";

/**
 * Halaman awal per izin, berurutan seperti menu samping. Id rute ditulis
 * langsung agar modul ini tidak perlu memuat seluruh daftar halaman.
 */
const HOME_ROUTES: Array<[string, string]> = [
  [UsersPermissions.VIEW_LEASE, "leases"],
  [UsersPermissions.VIEW_ACQUISITIONPROJECT, "acquisition_dashboard"],
  [UsersPermissions.VIEW_CONTACT, "contacts"],
  [UsersPermissions.VIEW_AREANOTE, "area_notes"],
  [UsersPermissions.VIEW_BASISOFRENT, "rent_basis"],
  [UsersPermissions.VIEW_AREASEARCH, "area_search"],
];

/**
 * Halaman di luar aplikasi ini (panel admin, aplikasi lapangan, pusat komando)
 * untuk peran yang tidak memiliki halaman di aplikasi petugas.
 */
const EXTERNAL_HOME_PAGES: Array<[string, string]> = [
  // Koordinator wilayah bekerja dari pusat komando.
  [UsersPermissions.VIEW_KORWIL, "/komando/"],
  [UsersPermissions.VIEW_APPLICATION, "/admin/alokasi/application/"],
  [UsersPermissions.VERIFY_PAYMENT, "/admin/alokasi/invoice/"],
  [UsersPermissions.VIEW_ALLOCATION, "/admin/alokasi/allocation/"],
  [UsersPermissions.VIEW_LANDASSET, "/admin/asetlahan/dasbor/"],
  [UsersPermissions.VIEW_LEGALCASE, "/admin/asetlahan/legalcase/"],
  [UsersPermissions.ADD_FIELDREPORT, "/aset/lapangan/"],
];

/**
 * Alamat halaman luar untuk pengguna tanpa halaman di aplikasi petugas,
 * atau null bila pengguna punya halaman di sini (atau tidak punya izin apa pun).
 */
export const getExternalHomeHref = (
  usersPermissions: UsersPermissionsType,
): string | null => {
  const hasSpaPage = HOME_ROUTES.some(([permission]) =>
    hasPermissions(usersPermissions, permission),
  );
  if (hasSpaPage) return null;
  const match = EXTERNAL_HOME_PAGES.find(([permission]) =>
    hasPermissions(usersPermissions, permission),
  );
  return match ? match[1] : null;
};

/** Id rute halaman pertama yang boleh dibuka pengguna (bawaan: sewa). */
export const getHomeRouteId = (
  usersPermissions: UsersPermissionsType,
): string => {
  const match = HOME_ROUTES.find(([permission]) =>
    hasPermissions(usersPermissions, permission),
  );
  return match ? match[1] : "leases";
};
