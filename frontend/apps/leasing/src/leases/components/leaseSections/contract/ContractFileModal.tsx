import React, { useEffect } from "react";
import { useAppDispatch, useAppSelector } from "@/root/hooks";
import { Row, Column } from "@/components/grid/Grid";
import Button from "@/components/button/Button";
import FileDownloadLink from "@/components/file/FileDownloadLink";
import FormText from "@/components/form/FormText";
import FormTextTitle from "@/components/form/FormTextTitle";
import Loader from "@/components/loader/Loader";
import LoaderWrapper from "@/components/loader/LoaderWrapper";
import Modal from "@/components/modal/Modal";
import ModalButtonWrapper from "@/components/modal/ModalButtonWrapper";
import { ButtonColors } from "@/components/enums";
import { fetchContractFilesById } from "@/contractFile/actions";
import createUrlWithoutVersionSuffix from "@/api/createUrlWithoutVersionSuffix";
import { humanReadableByteCount } from "@/util/helpers";
import {
  getContractFilesById,
  getIsFetchingById,
} from "@/contractFile/selectors";
type Props = {
  contractId: number;
  onClose: (...args: Array<any>) => any;
  open: boolean;
};

const ContractFileModal: React.FC<Props> = ({ contractId, onClose, open }) => {
  const files = useAppSelector((state) =>
    getContractFilesById(state, contractId),
  );
  const isFetching = useAppSelector((state) =>
    getIsFetchingById(state, contractId),
  );

  const dispatch = useAppDispatch();

  useEffect(() => {
    if (open && !files) {
      dispatch(fetchContractFilesById(contractId));
    }
  }, [open, files, contractId, dispatch]);

  return (
    <Modal isOpen={open} onClose={onClose} title="Berkas kontrak">
      {isFetching && (
        <LoaderWrapper>
          <Loader isLoading={true} />
        </LoaderWrapper>
      )}
      {files && !files.length && (
        <FormText>Dalam kontrak {contractId} tidak ada berkas</FormText>
      )}
      {files && !!files.length && (
        <>
          <Row>
            <Column small={4}>
              <FormTextTitle>Berkas</FormTextTitle>
            </Column>
            <Column small={4}>
              <FormTextTitle>Jenis</FormTextTitle>
            </Column>
            <Column small={4}>
              <FormTextTitle>Seluruh</FormTextTitle>
            </Column>
          </Row>

          {files.map((file, index) => {
            const getCategoryText = () => {
              switch (file.fileCategory) {
                case "CONTRACT":
                  return "Kontrak";

                case "CONTRACT_ATTACHMENT":
                  return "Lampiran kontrak";

                case "OTHER_ATTACHMENT":
                  return "Lainnya";

                default:
                  return file.fileCategory;
              }
            };

            return (
              <Row key={index}>
                <Column small={4}>
                  <FileDownloadLink
                    fileUrl={createUrlWithoutVersionSuffix(
                      `contract_file/${contractId}/${file.id}/`,
                    )}
                    label={file.fileName}
                  />
                </Column>
                <Column small={4}>
                  <FormText>{getCategoryText()}</FormText>
                </Column>
                <Column small={4}>
                  <FormText>{humanReadableByteCount(file.fileSize)}</FormText>
                </Column>
              </Row>
            );
          })}
        </>
      )}
      <ModalButtonWrapper>
        <Button
          className={ButtonColors.SECONDARY}
          onClick={onClose}
          text="Tutup"
        />
      </ModalButtonWrapper>
    </Modal>
  );
};

export default ContractFileModal;
