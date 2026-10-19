import callApi from "@/api/callApi";
import createUrl from "@/api/createUrl";

export const fetchOldDwellingsInHousingCompaniesPriceIndex = (): Generator<
  any,
  any,
  any
> => {
  // Indeks pertama dari daftar: data indeks bisa saja belum dimuat, sehingga
  // id tetap (mis. 1) akan menghasilkan 404 di setiap halaman sewa.
  return callApi(
    new Request(
      createUrl("old_dwellings_in_housing_companies_price_index/", {
        limit: 1,
      }),
    ),
  );
};
