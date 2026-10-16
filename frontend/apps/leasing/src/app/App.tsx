import React, { useEffect, useState } from "react";
import { connect } from "react-redux";
import { withRouterLegacy } from "@/root/withRouterLegacy";
import { useNavigate } from "react-router";
import { flowRight, get } from "lodash-es";
import { setNavigate } from "@/root/navigationService";
import { ActionTypes, ModalConsumer, ModalProvider } from "@/app/ModalContext";
import ApiErrorModal from "@/api/ApiErrorModal";
import ConfirmationModal from "@/components/modal/ConfirmationModal";
import Loader from "@/components/loader/Loader";
import NotificationCenter from "@/components/notification/NotificationCenter";
import useAuth from "@/auth/useAuth";
import LoginPage from "@/auth/components/LoginPage";
import SideMenu from "@/components/sideMenu/SideMenu";
import TopNavigation from "@/components/topNavigation/TopNavigation";
import { clearError } from "@/api/slice";
import { getError } from "@/api/selectors";
import { getLoggedInUser } from "@/auth/selectors";
import {
  getLinkUrl,
  getPageTitle,
  getShowSearch,
} from "@/components/topNavigation/selectors";
import {
  getUserGroups,
  getUserActiveServiceUnit,
  getUserServiceUnits,
} from "@/usersPermissions/selectors";
import type { ApiError } from "@/api/types";
import type {
  UserGroups,
  UserServiceUnit,
  UserServiceUnits,
} from "@/usersPermissions/types";
import type { RootState } from "@/root/types";
import "@/main.scss";

const IS_DEVELOPMENT_URL = import.meta.env.VITE_SHOW_DEV_BANNER === "true";
type OwnProps = {
  children: JSX.Element;
};
type Props = OwnProps & {
  apiError?: ApiError;
  clearError: typeof clearError;
  linkUrl?: string;
  pageTitle: string;
  userActiveServiceUnit?: UserServiceUnit;
  userServiceUnits?: UserServiceUnits;
  showSearch?: boolean;
  user?: Record<string, any>;
  userGroups?: UserGroups;
};
type State = {
  displaySideMenu: boolean;
  loggedIn: boolean;
  displayUserGroups: boolean;
};

const App: React.FC<Props> = (props) => {
  const [displaySideMenu, setDisplaySideMenu] =
    useState<State["displaySideMenu"]>(false);
  const [displayUserGroups, setDisplayUserGroups] =
    useState<State["displayUserGroups"]>(false);
  const { loggedIn, isRestoring, authenticatedUser, login, logout } = useAuth();
  const navigate = useNavigate();
  useEffect(() => {
    setNavigate(navigate);
  }, [navigate]);

  const logOut = () => {
    logout();
  };

  const toggleSideMenu = () => {
    setDisplaySideMenu(!displaySideMenu);
  };

  const toggleDisplayUserGroups = () => {
    setDisplayUserGroups(!displayUserGroups);
  };

  const handleDismissErrorModal = () => {
    props.clearError();
  };

  const {
    apiError,
    children,
    linkUrl,
    pageTitle,
    showSearch,
    userGroups,
    userActiveServiceUnit,
    userServiceUnits,
  } = props;

  const appStyle = IS_DEVELOPMENT_URL ? "app-dev" : "app";

  if (!loggedIn) {
    return (
      <div className={appStyle}>
        <NotificationCenter />

        <ApiErrorModal
          data={apiError}
          isOpen={Boolean(apiError)}
          handleDismiss={handleDismissErrorModal}
        />

        {isRestoring ? (
          <Loader isLoading={true} />
        ) : (
          <LoginPage onLogin={login} />
        )}
      </div>
    );
  }

  return (
    <ModalProvider>
      <ModalConsumer>
        {({
          isConfirmationModalOpen,
          confirmationFunction,
          confirmationModalButtonClassName,
          confirmationModalButtonText,
          confirmationModalLabel,
          confirmationModalTitle,
          modalDispatch,
        }) => {
          const handleConfirmation = () => {
            confirmationFunction?.();
            handleHideConfirmationModal();
          };

          const handleHideConfirmationModal = () => {
            modalDispatch({
              type: ActionTypes.HIDE_CONFIRMATION_MODAL,
            });
          };

          return (
            <div className={appStyle}>
              <ApiErrorModal
                data={apiError}
                isOpen={Boolean(apiError)}
                handleDismiss={handleDismissErrorModal}
              />

              <ConfirmationModal
                confirmButtonClassName={confirmationModalButtonClassName}
                confirmButtonLabel={confirmationModalButtonText}
                isOpen={isConfirmationModalOpen}
                label={confirmationModalLabel}
                onCancel={handleHideConfirmationModal}
                onClose={handleHideConfirmationModal}
                onSave={handleConfirmation}
                title={confirmationModalTitle || ""}
              />

              <NotificationCenter />

              <TopNavigation
                isMenuOpen={displaySideMenu}
                linkUrl={linkUrl}
                onLogout={logOut}
                pageTitle={pageTitle}
                showSearch={showSearch}
                toggleSideMenu={toggleSideMenu}
                toggleDisplayUserGroups={toggleDisplayUserGroups}
                username={get(authenticatedUser, "profile.name")}
                userServiceUnits={userServiceUnits}
                userActiveServiceUnit={userActiveServiceUnit}
              />

              {displayUserGroups && (
                <section className="app__usergroup-list">
                  <strong>Grup pengguna dan unit layanan</strong>
                  {userGroups &&
                    userGroups.length > 0 &&
                    userGroups.map((group, index) => {
                      return (
                        <p className="usergroup-list-item" key={group}>
                          {group}
                        </p>
                      );
                    })}
                </section>
              )}

              <section className="app__content">
                <SideMenu
                  isOpen={displaySideMenu}
                  onLinkClick={toggleSideMenu}
                />
                <div className="wrapper">{children}</div>
              </section>
            </div>
          );
        }}
      </ModalConsumer>
    </ModalProvider>
  );
};

const mapStateToProps = (state: RootState) => {
  const user = getLoggedInUser(state);
  if (!user) {
    return {
      pageTitle: getPageTitle(state),
      showSearch: getShowSearch(state),
      user: null,
    };
  }
  return {
    apiError: getError(state),
    linkUrl: getLinkUrl(state),
    pageTitle: getPageTitle(state),
    showSearch: getShowSearch(state),
    userGroups: getUserGroups(state),
    userServiceUnits: getUserServiceUnits(state),
    userActiveServiceUnit: getUserActiveServiceUnit(state),
  };
};

export default flowRight(
  withRouterLegacy,
  connect(mapStateToProps, {
    clearError,
  }),
)(App) as React.ComponentType<OwnProps>;
