import React, { Component } from "react";
import { Link } from "react-router";
import {
  withRouterLegacy,
  type WithRouterProps,
} from "@/root/withRouterLegacy";
import classnames from "classnames";
import { flowRight, isEmpty } from "lodash-es";
import Authorization from "@/components/authorization/Authorization";
import Loader from "@/components/loader/Loader";
import LoaderWrapper from "@/components/loader/LoaderWrapper";
import SubMenu from "./SubMenu";
import { ActionTypes, ModalConsumer } from "@/app/ModalContext";
import { ConfirmationModalTexts } from "@/enums";
import { ButtonColors } from "@/components/enums";
import { UsersPermissions } from "@/usersPermissions/enums";
import { hasAnyPageDirtyForms } from "@/util/forms";
import { hasPermissions } from "@/util/helpers";
import { getRouteById, Routes } from "@/root/routes";
import { withUsersPermissions } from "@/components/attributes/UsersPermissions";
import { FLAG_PLOTSEARCH } from "@/featureFlags";
import type { UsersPermissions as UsersPermissionsType } from "@/usersPermissions/types";
type OwnProps = {
  isOpen: boolean;
  onLinkClick: (...args: Array<any>) => any;
};
type Props = OwnProps & {
  isFetchingUsersPermissions: boolean;
  usersPermissions: UsersPermissionsType;
};
type State = {
  isClosing: boolean;
  isOpen: boolean;
  isOpening: boolean;
  subMenuKey: string;
};

class SideMenu extends Component<Props & WithRouterProps, State> {
  _isMounted: boolean;
  component: any;
  firstLink: HTMLElement | null = null;
  state = {
    isClosing: false,
    isOpen: false,
    isOpening: false,
    subMenuKey: "",
  };

  static getDerivedStateFromProps(props: Props, state: State) {
    const newState: any = {};

    if (props.isOpen !== state.isOpen) {
      newState.isOpen = props.isOpen;

      if (props.isOpen) {
        newState.isOpening = true;
      } else {
        newState.isClosing = true;
      }
    }

    return !isEmpty(newState) ? newState : null;
  }

  componentDidUpdate(prevProps: Props) {
    if (!prevProps.isOpen && this.props.isOpen) {
      const linkNode = this.firstLink;

      if (linkNode) {
        linkNode.focus();
      }
    }
  }

  componentDidMount() {
    this._isMounted = true;
    this.component.addEventListener("transitionend", this.transitionEnds);
  }

  componentWillUnmount() {
    this._isMounted = false;
    this.component.removeEventListener("transitionend", this.transitionEnds);
  }

  transitionEnds = () => {
    if (!this._isMounted) return;
    this.setState({
      isClosing: false,
      isOpening: false,
    });
  };
  setComponentRef = (element: any) => {
    this.component = element;
  };
  setLinkRef = (element: HTMLElement | null) => {
    this.firstLink = element;
  };
  getSideMenuWidth = () => {
    const menuButton = document.getElementsByClassName(
      "top-navigation__title_button",
    );

    if (menuButton.length) {
      return menuButton[0].clientWidth;
    }

    return null;
  };
  handleHeaderClick = (key) => {
    this.setState({
      subMenuKey: key,
    });
  };

  render() {
    const { isFetchingUsersPermissions, isOpen, usersPermissions } = this.props;
    const { isClosing, isOpening, subMenuKey } = this.state;
    const width = this.getSideMenuWidth();
    return (
      <ModalConsumer>
        {({ modalDispatch }) => {
          const handleClick = (e: any) => {
            const { onLinkClick } = this.props,
              hasDirtyPages = hasAnyPageDirtyForms();
            this.setState({
              subMenuKey: "",
            });

            if (hasDirtyPages) {
              const target = e.target;
              e.preventDefault();
              modalDispatch({
                type: ActionTypes.SHOW_CONFIRMATION_MODAL,
                confirmationFunction: () => {
                  const { navigate } = this.props;
                  const relativeUrl = target.href.replace(location.origin, "");
                  navigate(relativeUrl);
                  onLinkClick();
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
              onLinkClick();
            }
          };

          return (
            <div
              ref={this.setComponentRef}
              className={classnames("side-menu", {
                "is-closing": isClosing,
                "is-menu-open": isOpen,
                "is-opening": isOpening,
              })}
              style={{
                width: width,
              }}
            >
              {isFetchingUsersPermissions && (
                <LoaderWrapper>
                  <Loader isLoading={true} />
                </LoaderWrapper>
              )}
              {!isFetchingUsersPermissions && (
                <ul hidden={!isOpen && !isClosing && !isOpening}>
                  <Authorization
                    allow={hasPermissions(
                      usersPermissions,
                      UsersPermissions.VIEW_LEASE,
                    )}
                  >
                    <li>
                      <span ref={this.setLinkRef} tabIndex={0}>
                        <Link
                          onClick={handleClick}
                          to={getRouteById(Routes.LEASES)}
                        >
                          Sewa
                        </Link>
                      </span>
                    </li>
                  </Authorization>

                  <Authorization
                    allow={hasPermissions(
                      usersPermissions,
                      UsersPermissions.VIEW_ACQUISITIONPROJECT,
                    )}
                  >
                    <SubMenu
                      header="Pengadaan Tanah"
                      isOpen={subMenuKey === "acquisition"}
                      items={[
                        {
                          allow: true,
                          onClick: handleClick,
                          text: "Dasbor & tenggat",
                          to: getRouteById(Routes.ACQUISITION_DASHBOARD),
                        },
                        {
                          allow: true,
                          onClick: handleClick,
                          text: "Proyek pengadaan",
                          to: getRouteById(Routes.ACQUISITIONS),
                        },
                        {
                          allow: hasPermissions(
                            usersPermissions,
                            UsersPermissions.VIEW_HOLIDAY,
                          ),
                          onClick: handleClick,
                          text: "Kalender & aturan tenggat",
                          to: getRouteById(Routes.ACQUISITION_SETTINGS),
                        },
                      ]}
                      menuKey="acquisition"
                      onHeaderClick={this.handleHeaderClick}
                    />
                  </Authorization>

                  <Authorization
                    allow={
                      hasPermissions(
                        usersPermissions,
                        UsersPermissions.VIEW_APPLICATION,
                      ) ||
                      hasPermissions(
                        usersPermissions,
                        UsersPermissions.VERIFY_PAYMENT,
                      ) ||
                      hasPermissions(
                        usersPermissions,
                        UsersPermissions.VIEW_ALLOCATION,
                      )
                    }
                  >
                    <SubMenu
                      header="Alokasi Lahan"
                      isOpen={subMenuKey === "allocation"}
                      items={[
                        {
                          allow: hasPermissions(
                            usersPermissions,
                            UsersPermissions.VIEW_APPLICATION,
                          ),
                          text: "Permohonan & verifikasi",
                          href: "/admin/alokasi/application/",
                        },
                        {
                          allow: hasPermissions(
                            usersPermissions,
                            UsersPermissions.VERIFY_PAYMENT,
                          ),
                          text: "Tagihan & pembayaran",
                          href: "/admin/alokasi/invoice/",
                        },
                        {
                          allow: hasPermissions(
                            usersPermissions,
                            UsersPermissions.VIEW_ALLOCATION,
                          ),
                          text: "Alokasi & lahan tidur",
                          href: "/admin/alokasi/allocation/",
                        },
                        {
                          allow: hasPermissions(
                            usersPermissions,
                            UsersPermissions.VIEW_LANDPLOT,
                          ),
                          text: "Data lahan",
                          href: "/admin/alokasi/landplot/",
                        },
                        {
                          allow: true,
                          text: "Portal publik",
                          href: "/portal/",
                        },
                      ]}
                      menuKey="allocation"
                      onHeaderClick={this.handleHeaderClick}
                    />
                  </Authorization>

                  <Authorization
                    allow={
                      hasPermissions(
                        usersPermissions,
                        UsersPermissions.VIEW_LANDASSET,
                      ) ||
                      hasPermissions(
                        usersPermissions,
                        UsersPermissions.VIEW_LEGALCASE,
                      ) ||
                      hasPermissions(
                        usersPermissions,
                        UsersPermissions.ADD_FIELDREPORT,
                      )
                    }
                  >
                    <SubMenu
                      header="Manajemen Aset Lahan"
                      isOpen={subMenuKey === "landAssets"}
                      items={[
                        {
                          allow: hasPermissions(
                            usersPermissions,
                            UsersPermissions.VIEW_LANDASSET,
                          ),
                          text: "Dasbor aset",
                          href: "/admin/asetlahan/dasbor/",
                        },
                        {
                          allow: hasPermissions(
                            usersPermissions,
                            UsersPermissions.VIEW_LANDASSET,
                          ),
                          text: "Data aset & peta",
                          href: "/admin/asetlahan/landasset/",
                        },
                        {
                          allow: hasPermissions(
                            usersPermissions,
                            UsersPermissions.VIEW_LEGALCASE,
                          ),
                          text: "Perkara & sidang",
                          href: "/admin/asetlahan/legalcase/",
                        },
                        {
                          allow: hasPermissions(
                            usersPermissions,
                            UsersPermissions.VIEW_ENCROACHMENTCASE,
                          ),
                          text: "Okupasi & perambahan",
                          href: "/admin/asetlahan/encroachmentcase/",
                        },
                        {
                          allow: hasPermissions(
                            usersPermissions,
                            UsersPermissions.VIEW_GRIEVANCE,
                          ),
                          text: "Pengaduan masyarakat",
                          href: "/admin/asetlahan/grievance/",
                        },
                        {
                          allow: hasPermissions(
                            usersPermissions,
                            UsersPermissions.VIEW_TENDER,
                          ),
                          text: "Lelang & seleksi lahan",
                          href: "/admin/asetlahan/tender/",
                        },
                        {
                          allow: hasPermissions(
                            usersPermissions,
                            UsersPermissions.VIEW_LANDASSET,
                          ),
                          text: "Laporan & asisten AI",
                          href: "/admin/asetlahan/",
                        },
                        {
                          allow: hasPermissions(
                            usersPermissions,
                            UsersPermissions.ADD_FIELDREPORT,
                          ),
                          text: "Aplikasi lapangan",
                          href: "/aset/lapangan/",
                        },
                      ]}
                      menuKey="landAssets"
                      onHeaderClick={this.handleHeaderClick}
                    />
                  </Authorization>

                  <Authorization
                    allow={hasPermissions(
                      usersPermissions,
                      UsersPermissions.VIEW_KORWIL,
                    )}
                  >
                    <SubMenu
                      header="Pusat Komando"
                      isOpen={subMenuKey === "command"}
                      items={[
                        {
                          allow: true,
                          text: "Peta operasi & PWA",
                          href: "/komando/",
                        },
                        {
                          allow: true,
                          text: "Absen",
                          href: "/komando/?tab=absen",
                        },
                        {
                          allow: true,
                          text: "Lapor kegiatan",
                          href: "/komando/?tab=korwil",
                        },
                        {
                          allow: true,
                          text: "Tugas",
                          href: "/komando/?tab=tasks",
                        },
                        {
                          allow: true,
                          text: "Kinerja (KPI)",
                          href: "/komando/?tab=perf",
                        },
                        {
                          allow: true,
                          text: "Korwil, warga & laporan",
                          href: "/admin/operasi/",
                        },
                      ]}
                      menuKey="command"
                      onHeaderClick={this.handleHeaderClick}
                    />
                  </Authorization>

                  <Authorization
                    allow={hasPermissions(
                      usersPermissions,
                      UsersPermissions.VIEW_CONTACT,
                    )}
                  >
                    <li>
                      <Link
                        onClick={handleClick}
                        to={getRouteById(Routes.CONTACTS)}
                      >
                        Kontak
                      </Link>
                    </li>
                  </Authorization>

                  <Authorization
                    allow={hasPermissions(
                      usersPermissions,
                      UsersPermissions.VIEW_AREANOTE,
                    )}
                  >
                    <li>
                      <Link
                        onClick={handleClick}
                        to={getRouteById(Routes.AREA_NOTES)}
                      >
                        Catatan area
                      </Link>
                    </li>
                  </Authorization>

                  <Authorization
                    allow={hasPermissions(
                      usersPermissions,
                      UsersPermissions.VIEW_BASISOFRENT,
                    )}
                  >
                    <li>
                      <Link
                        onClick={handleClick}
                        to={getRouteById(Routes.RENT_BASIS)}
                      >
                        Prinsip sewa
                      </Link>
                    </li>
                  </Authorization>

                  <Authorization
                    allow={hasPermissions(
                      usersPermissions,
                      UsersPermissions.VIEW_INVOICE,
                    )}
                  >
                    <li>
                      <Link
                        onClick={handleClick}
                        to={getRouteById(Routes.LEASE_REPORTS)}
                      >
                        Statistik dan laporan
                      </Link>
                    </li>
                  </Authorization>

                  <Authorization
                    allow={hasPermissions(
                      usersPermissions,
                      UsersPermissions.VIEW_INFILLDEVELOPMENTCOMPENSATION,
                    )}
                  >
                    <li>
                      <Link
                        style={{
                          color: "#b7b7b7",
                        }}
                        onClick={handleClick}
                        to={getRouteById(Routes.INFILL_DEVELOPMENTS)}
                      >
                        Kompensasi pembangunan sisipan
                      </Link>
                    </li>
                  </Authorization>

                  {FLAG_PLOTSEARCH && (
                    <SubMenu
                      header="Pencarian kavling dan kompetisi"
                      isOpen={subMenuKey === "plot"}
                      items={[
                        {
                          allow: hasPermissions(
                            usersPermissions,
                            UsersPermissions.VIEW_PLOTSEARCH,
                          ),
                          onClick: handleClick,
                          text: "Pencarian kavling",
                          to: getRouteById(Routes.PLOT_SEARCH),
                        },
                        {
                          allow: hasPermissions(
                            usersPermissions,
                            UsersPermissions.VIEW_ANSWER,
                          ),
                          onClick: handleClick,
                          text: "Permohonan kavling",
                          to: getRouteById(Routes.PLOT_APPLICATIONS),
                        },
                      ]}
                      menuKey="plot"
                      onHeaderClick={this.handleHeaderClick}
                    />
                  )}

                  <Authorization
                    allow={hasPermissions(
                      usersPermissions,
                      UsersPermissions.VIEW_AREASEARCH,
                    )}
                  >
                    <li>
                      <Link
                        onClick={handleClick}
                        to={getRouteById(Routes.AREA_SEARCH)}
                      >
                        Pencarian area
                      </Link>
                    </li>
                  </Authorization>

                  <Authorization
                    allow={
                      hasPermissions(
                        usersPermissions,
                        UsersPermissions.ADD_LEASEBASISOFRENT,
                      ) ||
                      hasPermissions(
                        usersPermissions,
                        UsersPermissions.VIEW_INDEX,
                      ) ||
                      hasPermissions(
                        usersPermissions,
                        UsersPermissions.VIEW_JOBRUN,
                      ) ||
                      hasPermissions(
                        usersPermissions,
                        UsersPermissions.VIEW_SCHEDULEDJOB,
                      ) ||
                      hasPermissions(
                        usersPermissions,
                        UsersPermissions.VIEW_INVOICE,
                      ) ||
                      hasPermissions(
                        usersPermissions,
                        UsersPermissions.VIEW_INVOICENOTE,
                      )
                    }
                  >
                    <SubMenu
                      header="Lainnya"
                      isOpen={subMenuKey === "tools"}
                      items={[
                        {
                          allow: hasPermissions(
                            usersPermissions,
                            UsersPermissions.VIEW_INDEX,
                          ),
                          onClick: handleClick,
                          text: "Indeks biaya hidup",
                          to: getRouteById(Routes.INDEX),
                        },
                        {
                          allow:
                            hasPermissions(
                              usersPermissions,
                              UsersPermissions.VIEW_JOBRUN,
                            ) ||
                            hasPermissions(
                              usersPermissions,
                              UsersPermissions.VIEW_SCHEDULEDJOB,
                            ),
                          onClick: handleClick,
                          text: "Tugas terjadwal",
                          to: getRouteById(Routes.BATCH_RUN),
                        },
                        {
                          allow: hasPermissions(
                            usersPermissions,
                            UsersPermissions.VIEW_INVOICENOTE,
                          ),
                          onClick: handleClick,
                          text: "Catatan tagihan",
                          to: getRouteById(Routes.INVOICE_NOTES),
                        },
                        {
                          allow: hasPermissions(
                            usersPermissions,
                            UsersPermissions.ADD_LEASEBASISOFRENT,
                          ),
                          onClick: handleClick,
                          text: "Kalkulator sewa",
                          to: getRouteById(Routes.BASIS_OF_RENT_CALCULATOR),
                        },
                      ]}
                      menuKey="tools"
                      onHeaderClick={this.handleHeaderClick}
                    />
                  </Authorization>
                </ul>
              )}
            </div>
          );
        }}
      </ModalConsumer>
    );
  }
}

export default flowRight(
  withUsersPermissions,
  withRouterLegacy,
)(SideMenu) as React.ComponentType<OwnProps>;
