import { useEffect } from "react";
import { useAppDispatch, useAppSelector } from "@/root/hooks";
import { fetchIntendedUse } from "./actions";
import { getIntendedUseList, getIsFetched, getIsFetching } from "./selectors";
import type { IntendedUseList } from "./types";

export const useIntendedUses = (): {
  intendedUseList: IntendedUseList;
  isFetchingIntendedUses: boolean;
} => {
  const dispatch = useAppDispatch();
  const intendedUseList = useAppSelector(getIntendedUseList);
  const isFetchingIntendedUses = useAppSelector(getIsFetching);
  const isFetchedIntendedUses = useAppSelector(getIsFetched);

  useEffect(() => {
    // Only fetch if we don't have data and aren't already fetching
    if (!isFetchedIntendedUses && !isFetchingIntendedUses) {
      dispatch(fetchIntendedUse());
    }
  }, [dispatch, isFetchedIntendedUses, isFetchingIntendedUses]);

  return {
    intendedUseList,
    isFetchingIntendedUses,
  };
};
