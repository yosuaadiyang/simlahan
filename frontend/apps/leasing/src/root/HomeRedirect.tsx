import React, { useEffect, useState } from "react";
import { Navigate } from "react-router";
import { isEmpty } from "lodash-es";
import Loader from "@/components/loader/Loader";
import { useAppDispatch, useAppSelector } from "@/root/hooks";
import {
  getIsFetching,
  getUsersPermissions,
} from "@/usersPermissions/selectors";
import { fetchUsersPermissions } from "@/usersPermissions/slice";
import { getExternalHomeHref, getHomeRouteId } from "./homeRoute";

type Props = {
  getRoute: (id: string) => string;
};

/** Arahkan "/" ke halaman pertama yang boleh dibuka pengguna. */
const HomeRedirect: React.FC<Props> = ({ getRoute }) => {
  const dispatch = useAppDispatch();
  const usersPermissions = useAppSelector(getUsersPermissions);
  const isFetching = useAppSelector(getIsFetching);
  const [isRequested, setIsRequested] = useState(false);

  useEffect(() => {
    if (isEmpty(usersPermissions) && !isFetching) {
      dispatch(fetchUsersPermissions());
    }
    setIsRequested(true);
    // Hanya saat halaman dibuka.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isLoading = isEmpty(usersPermissions) && (!isRequested || isFetching);
  const externalHref = isLoading ? null : getExternalHomeHref(usersPermissions);

  useEffect(() => {
    // Sesi peramban dibuat saat login, jadi halaman luar terbuka tanpa login ulang.
    if (externalHref) window.location.replace(externalHref);
  }, [externalHref]);

  if (isLoading || externalHref) {
    return <Loader isLoading={true} />;
  }
  return <Navigate replace to={getRoute(getHomeRouteId(usersPermissions))} />;
};

export default HomeRedirect;
