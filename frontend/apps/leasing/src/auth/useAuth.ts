import { useCallback, useEffect, useState } from "react";
import { useAppSelector } from "@/root/hooks";
import { getApiToken, getLoggedInUser } from "./selectors";
import {
  hasBrowserSession,
  hasStoredSession,
  login as loginRequest,
  logout as logoutRequest,
  restoreFromBrowserSession,
  restoreSession,
} from "./session";

const canRestore = () => hasStoredSession() || hasBrowserSession();

/** Token tersimpan dulu; bila tidak ada/kedaluwarsa, sesi peramban. */
const restore = async () =>
  (hasStoredSession() ? await restoreSession() : null) ||
  restoreFromBrowserSession();

const useAuth = () => {
  const user = useAppSelector(getLoggedInUser);
  const apiToken = useAppSelector(getApiToken);
  const [isRestoring, setIsRestoring] = useState<boolean>(
    () => !user && canRestore(),
  );

  useEffect(() => {
    let cancelled = false;
    if (!user && canRestore()) {
      setIsRestoring(true);
      restore().finally(() => {
        if (!cancelled) setIsRestoring(false);
      });
    }
    return () => {
      cancelled = true;
    };
    // Hanya saat aplikasi pertama kali dimuat.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(
    (username: string, password: string) => loginRequest(username, password),
    [],
  );
  const logout = useCallback(() => logoutRequest(), []);

  return {
    loggedIn: Boolean(user) && Boolean(apiToken),
    isRestoring,
    authenticatedUser: user,
    login,
    logout,
  };
};

export default useAuth;
