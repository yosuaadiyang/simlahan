import React, { Component } from "react";
import { connect } from "react-redux";
import Modal from "@/components/modal/Modal";
import ModalButtonWrapper from "@/components/modal/ModalButtonWrapper";
import Button from "@/components/button/Button";
import { createPlotApplicationOpeningRecord } from "@/plotApplications/actions";
import { getLoggedInUser } from "@/auth/selectors";
import { getUsersPermissions } from "@/usersPermissions/selectors";
import { UsersPermissions } from "@/usersPermissions/enums";
import { getHoursAndMinutes } from "@/util/date";
import { formatDate, hasPermissions } from "@/util/helpers";
import type { RootState } from "@/root/types";
import type { UsersPermissions as UsersPermissionsType } from "@/usersPermissions/types";
type Props = {
  isOpen: boolean;
  onClose: (...args: Array<any>) => any;
};
type InnerProps = Props & {
  data: Record<string, any> | null | undefined;
  currentUser?: Record<string, any>;
  userPermissions?: UsersPermissionsType;
  createPlotApplicationOpeningRecord?: (...args: Array<any>) => any;
};

class PlotApplicationsListOpeningModal extends Component<InnerProps> {
  openApplications = () => {
    const { createPlotApplicationOpeningRecord, data, currentUser } =
      this.props;
    createPlotApplicationOpeningRecord(data?.id, currentUser);
  };

  render(): JSX.Element {
    const { isOpen, onClose, data, userPermissions } = this.props;
    const allowedToOpen = hasPermissions(
      userPermissions,
      UsersPermissions.ADD_ANSWEROPENINGRECORD,
    );
    const canBeOpened = data?.plot_search?.end_date
      ? new Date(data.plot_search.end_date) < new Date()
      : false;
    const endDate = data
      ? formatDate(data.plot_search?.end_date) +
        ", " +
        getHoursAndMinutes(data.plot_search?.end_date)
      : "";
    return (
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        title={canBeOpened ? "Buka permohonan" : "Kompetisi berlangsung"}
      >
        {data && canBeOpened && !allowedToOpen && (
          <>
            <p>
              {data.plot_search_subtype?.name} {data.plot_search?.name} telah
              berakhir {endDate}.
            </p>
            <p>Anda tidak berwenang membuka permohonan ini.</p>
          </>
        )}
        {data && canBeOpened && allowedToOpen && (
          <>
            <p>
              {data.plot_search_subtype?.name} {data.plot_search?.name} telah
              berakhir {endDate}.
            </p>
            <p>
              Sebagai penyelenggara kompetisi Anda dapat membuka permohonan.
            </p>
            <p>
              Pastikan tiga orang hadir dalam acara pembukaan permohonan.
              Pembukaan menghasilkan stempel waktu yang tidak dapat dibatalkan.
            </p>
          </>
        )}
        {data && !canBeOpened && (
          <>
            <p>
              {data.plot_search_subtype?.name} {data.plot_search?.name} berakhir{" "}
              {endDate}.
            </p>
            <p>
              Petugas tidak dapat melihat permohonan sebelum waktu berakhir.
            </p>
          </>
        )}
        <ModalButtonWrapper>
          <Button
            className={canBeOpened ? "secondary" : ""}
            onClick={onClose}
            text="Tutup"
          />
          {canBeOpened && (
            <Button onClick={this.openApplications} text="Buka permohonan" />
          )}
        </ModalButtonWrapper>
      </Modal>
    );
  }
}

export default connect(
  (state: RootState) => ({
    currentUser: getLoggedInUser(state),
    userPermissions: getUsersPermissions(state),
  }),
  {
    createPlotApplicationOpeningRecord,
  },
)(PlotApplicationsListOpeningModal) as React.ComponentType<InnerProps>;
