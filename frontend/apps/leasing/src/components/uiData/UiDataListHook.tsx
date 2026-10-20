import { useEffect } from "react";
import { useAppDispatch, useAppSelector } from "@/root/hooks";
import {
  fetchUiDataList,
  fetchAttributes as fetchUiDataAttributes,
} from "@/uiData/actions";
import {
  getAttributes as getUiDataAttributes,
  getIsFetching,
  getIsFetchingAttributes as getIsFetchingUiDataAttributes,
  getMethods as getUiDataMethods,
  getIsFetched as getIsUiDataListFetched,
  getUiDataList,
} from "@/uiData/selectors";

export function useUiDataList() {
  const dispatch = useAppDispatch();

  const uiDataAttributes = useAppSelector(getUiDataAttributes);
  const uiDataMethods = useAppSelector(getUiDataMethods);
  const uiDataList = useAppSelector(getUiDataList);
  const isUiDataListFetched = useAppSelector(getIsUiDataListFetched);
  const isFetchingUiDataAttributes = useAppSelector(
    getIsFetchingUiDataAttributes,
  );
  const isFetchingUiDataList = useAppSelector(getIsFetching);

  useEffect(() => {
    if (!isFetchingUiDataAttributes && !uiDataAttributes && !uiDataMethods) {
      dispatch(fetchUiDataAttributes());
    }

    if (!isFetchingUiDataList && !isUiDataListFetched) {
      dispatch(
        fetchUiDataList({
          limit: 100000,
        }),
      );
    }
  }, [
    dispatch,
    isFetchingUiDataAttributes,
    isFetchingUiDataList,
    uiDataAttributes,
    isUiDataListFetched,
    uiDataMethods,
  ]);

  return {
    uiDataAttributes,
    uiDataMethods,
    uiDataList,
    isFetchingUiDataAttributes,
    isFetchingUiDataList,
  };
}
