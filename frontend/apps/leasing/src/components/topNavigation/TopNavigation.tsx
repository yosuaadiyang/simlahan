import React, { Component } from "react";
import classNames from "classnames";
import { Link } from "react-router";
import {
  withRouterLegacy,
  type WithRouterProps,
} from "@/root/withRouterLegacy";
import { ActionTypes, ModalConsumer } from "@/app/ModalContext";
import SearchInput from "@/components/inputs/SearchInput";
import UserServiceUnitSelectInput from "@/components/inputs/UserServiceUnitSelectInput";
import { ConfirmationModalTexts } from "@/enums";
import { ButtonColors } from "@/components/enums";
import { hasAnyPageDirtyForms } from "@/util/forms";
import { getSearchQuery, getUrlParams } from "@/util/helpers";
import { getRouteById, Routes } from "@/root/routes";

import type {
  UserServiceUnit,
  UserServiceUnits,
} from "@/usersPermissions/types";

const APP_NAME = import.meta.env.VITE_APP_NAME || "SimLahan";

// Inisial untuk avatar pengguna, mis. "Budi Santoso" -> "BS", "admin@x" -> "A".
export const getInitials = (name?: string | null): string => {
  const words = (name || "")
    .replace(/@.*$/, "")
    .split(/[\s._-]+/)
    .filter(Boolean);
  return words
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join("");
};

type Props = {
  isMenuOpen: boolean;
  linkUrl: string;
  onLogout: (...args: Array<any>) => any;
  pageTitle: string;
  showCommandCenter?: boolean;
  showSearch: boolean;
  toggleSideMenu: (...args: Array<any>) => any;
  toggleDisplayUserGroups: () => void;
  userActiveServiceUnit: UserServiceUnit;
  userServiceUnits: UserServiceUnits;
  username: string;
};
type State = {
  search: string;
};

class TopNavigation extends Component<Props & WithRouterProps, State> {
  state = {
    search: "",
  };

  componentDidMount() {
    this.setInitialSearchValue();
  }

  componentDidUpdate(prevProps: Props & WithRouterProps) {
    const {
      location: { pathname },
    } = this.props;

    if (pathname !== prevProps.location.pathname) {
      this.setInitialSearchValue();
    }
  }

  setInitialSearchValue = () => {
    const {
      location: { search },
    } = this.props;
    const query = getUrlParams(search);
    this.setState({
      search: query.search || "",
    });
  };
  handleSearchChange = (e: any) => {
    this.setState({
      search: e.target.value,
    });
  };
  moveSearchPage = () => {
    const { navigate } = this.props;
    const { search } = this.state;

    if (search) {
      const query = {
        search: search,
      };
      return navigate({
        pathname: getRouteById(Routes.LEASES),
        search: getSearchQuery(query),
      });
    }
  };

  render() {
    const {
      isMenuOpen,
      linkUrl,
      pageTitle,
      showCommandCenter,
      showSearch,
      toggleSideMenu,
      toggleDisplayUserGroups,
      userActiveServiceUnit,
      userServiceUnits,
      username,
    } = this.props;
    const { search } = this.state;
    return (
      <ModalConsumer>
        {({ modalDispatch }) => {
          const handleLinkClick = (e: any) => {
            const hasDirtyPages = hasAnyPageDirtyForms();

            if (hasDirtyPages) {
              // currentTarget: tautan <a> itu sendiri, juga saat yang diklik
              // adalah gambar/teks di dalamnya.
              const target = e.currentTarget;
              e.preventDefault();
              modalDispatch({
                type: ActionTypes.SHOW_CONFIRMATION_MODAL,
                confirmationFunction: () => {
                  const { navigate } = this.props;
                  const relativeUrl = target.href.replace(location.origin, "");
                  navigate(relativeUrl);
                },
                confirmationModalButtonClassName: ButtonColors.ALERT,
                confirmationModalButtonText:
                  ConfirmationModalTexts.CANCEL_CHANGES.BUTTON,
                confirmationModalLabel:
                  ConfirmationModalTexts.CANCEL_CHANGES.LABEL,
                confirmationModalTitle:
                  ConfirmationModalTexts.CANCEL_CHANGES.TITLE,
              });
            }
          };

          const handleSearch = () => {
            const hasDirtyPages = hasAnyPageDirtyForms();

            if (hasDirtyPages) {
              modalDispatch({
                type: ActionTypes.SHOW_CONFIRMATION_MODAL,
                confirmationFunction: () => {
                  this.moveSearchPage();
                },
                confirmationModalButtonClassName: ButtonColors.ALERT,
                confirmationModalButtonText:
                  ConfirmationModalTexts.CANCEL_CHANGES.BUTTON,
                confirmationModalLabel:
                  ConfirmationModalTexts.CANCEL_CHANGES.LABEL,
                confirmationModalTitle:
                  ConfirmationModalTexts.CANCEL_CHANGES.TITLE,
              });
            } else {
              this.moveSearchPage();
            }
          };

          // Halaman di luar aplikasi ini: minta konfirmasi bila ada perubahan
          // yang belum disimpan, sama seperti tautan di dalam aplikasi.
          const handleExternalLinkClick = (e: any) => {
            if (!hasAnyPageDirtyForms()) return;
            const href = e.currentTarget.href;
            e.preventDefault();
            modalDispatch({
              type: ActionTypes.SHOW_CONFIRMATION_MODAL,
              confirmationFunction: () => {
                window.location.assign(href);
              },
              confirmationModalButtonClassName: ButtonColors.ALERT,
              confirmationModalButtonText:
                ConfirmationModalTexts.CANCEL_CHANGES.BUTTON,
              confirmationModalLabel:
                ConfirmationModalTexts.CANCEL_CHANGES.LABEL,
              confirmationModalTitle:
                ConfirmationModalTexts.CANCEL_CHANGES.TITLE,
            });
          };

          const handleSearchKeyUp = (e: any) => {
            if (e.key === "Enter") {
              handleSearch();
            }
          };

          const handleLogout = () => {
            const { onLogout } = this.props,
              hasDirtyPages = hasAnyPageDirtyForms();

            if (hasDirtyPages) {
              modalDispatch({
                type: ActionTypes.SHOW_CONFIRMATION_MODAL,
                confirmationFunction: () => {
                  onLogout();
                },
                confirmationModalButtonClassName: ButtonColors.ALERT,
                confirmationModalButtonText:
                  ConfirmationModalTexts.CANCEL_CHANGES.BUTTON,
                confirmationModalLabel:
                  ConfirmationModalTexts.CANCEL_CHANGES.LABEL,
                confirmationModalTitle:
                  ConfirmationModalTexts.CANCEL_CHANGES.TITLE,
              });
            } else {
              onLogout();
            }
          };

          return (
            <header className="top-navigation">
              <div className="top-navigation__left-wrapper">
                <div
                  className={classNames("top-navigation__title", {
                    "is-open": isMenuOpen,
                  })}
                >
                  <button
                    className="top-navigation__title_button"
                    onClick={toggleSideMenu}
                    aria-controls="side-menu"
                    aria-expanded={isMenuOpen}
                    aria-label={
                      isMenuOpen ? "Tutup menu utama" : "Buka menu utama"
                    }
                    title="Menu utama"
                    type="button"
                  >
                    <span className="top-navigation__burger" aria-hidden="true">
                      <span />
                      <span />
                      <span />
                    </span>
                  </button>
                </div>
                <Link
                  className="top-navigation__brand"
                  onClick={handleLinkClick}
                  to="/"
                >
                  <img
                    src="/assets/images/logo-mark.svg"
                    alt=""
                    width={30}
                    height={30}
                  />
                  <span>{APP_NAME}</span>
                </Link>
                {!!pageTitle && (
                  <div className="page-title">
                    <Link onClick={handleLinkClick} to={linkUrl || ""}>
                      {pageTitle}
                    </Link>
                  </div>
                )}
              </div>
              <div className="top-navigation__right-wrapper">
                {!!showSearch && (
                  <div className="search">
                    <SearchInput
                      onChange={this.handleSearchChange}
                      onKeyUp={handleSearchKeyUp}
                      onSubmit={handleSearch}
                      value={search}
                    />
                  </div>
                )}

                {!!userServiceUnits?.length && userActiveServiceUnit && (
                  <div className="user-service-unit">
                    {userServiceUnits.length > 1 ? (
                      <UserServiceUnitSelectInput
                        userServiceUnits={userServiceUnits}
                        userActiveServiceUnit={userActiveServiceUnit}
                      />
                    ) : (
                      <div className="user-service-unit-text">
                        <div className="service-unit-label">
                          Unit layanan sendiri
                        </div>
                        <div className="service-unit-name">
                          {userActiveServiceUnit.name}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {!!showCommandCenter && (
                  <a
                    className="app-switch"
                    href="/komando/"
                    onClick={handleExternalLinkClick}
                    title="Pindah ke Pusat Komando"
                    aria-label="Pindah ke Pusat Komando"
                  >
                    <svg
                      className="app-switch__icon"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <circle cx="12" cy="12" r="8" />
                      <circle cx="12" cy="12" r="2.5" />
                      <path d="M12 1.5v4M12 18.5v4M1.5 12h4M18.5 12h4" />
                    </svg>
                    <span className="app-switch__label">Pusat Komando</span>
                  </a>
                )}

                <div className="username-wrapper">
                  <button
                    className="user-group-button"
                    onClick={toggleDisplayUserGroups}
                    title="Grup pengguna dan unit layanan"
                    type="button"
                  >
                    <span className="user-avatar" aria-hidden="true">
                      {getInitials(username) || "?"}
                    </span>
                    <span className="username">
                      <span className="username__text" title={username}>
                        {username}
                      </span>
                      <svg
                        className="username__chevron"
                        viewBox="0 0 24 24"
                        aria-hidden="true"
                      >
                        <path d="m6 9 6 6 6-6" />
                      </svg>
                    </span>
                  </button>
                  <button
                    className="logout-link"
                    onClick={handleLogout}
                    type="button"
                  >
                    <svg
                      className="logout-link__icon"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l5-5-5-5M15 12H3" />
                    </svg>
                    <span>Keluar</span>
                  </button>
                </div>
              </div>
            </header>
          );
        }}
      </ModalConsumer>
    );
  }
}

export default withRouterLegacy(TopNavigation);
