import React from "react";
import { Dialog, Button, ButtonVariant } from "hds-react";

interface TraceItem {
  file?: string;
  line?: number;
  class?: string;
  function?: string;
  code?: string;
}

interface ApiErrorData {
  exception?: string;
  message?: string;
  source?: string;
  errors?: Record<string, any>; // Validation errors as object, e.g., { field: ["error"] }
  trace?: TraceItem[];
}

/** Pesan bawaan redux-form untuk SubmissionError (bahasa Inggris). */
const SUBMISSION_ERROR_MESSAGE = "Submit Validation Failed";

/**
 * Saga lama membungkus setiap jawaban galat API dalam SubmissionError. Pesan
 * umum DRF (mis. 403/404) ada di "detail"; selebihnya galat per bidang.
 */
const getSubmissionErrors = (
  data: ApiErrorData | null | undefined,
): Record<string, any> | null =>
  data?.errors && data.message === SUBMISSION_ERROR_MESSAGE
    ? data.errors
    : null;

const getFieldErrors = (
  data: ApiErrorData | null | undefined,
): Record<string, any> | null | undefined => {
  const errors = getSubmissionErrors(data);
  if (!errors) return data?.errors;
  // "detail" tampil sebagai pesan; "get" hanya menandai permintaan asal.
  const fieldErrors = Object.fromEntries(
    Object.entries(errors).filter(([key]) => !["detail", "get"].includes(key)),
  );
  return Object.keys(fieldErrors).length ? fieldErrors : null;
};

export const getApiErrorTitle = (
  data: ApiErrorData | null | undefined,
): string => {
  const errors = getSubmissionErrors(data);
  if (errors) {
    return errors.detail && !getFieldErrors(data)
      ? "Permintaan gagal"
      : "Data tidak valid";
  }
  return `Galat server ${data?.exception || ""}`;
};

export const getApiErrorMessage = (
  data: ApiErrorData | null | undefined,
): string | undefined => {
  const errors = getSubmissionErrors(data);
  if (errors) {
    return errors.detail
      ? String(errors.detail)
      : "Validasi data gagal. Periksa isian berikut.";
  }
  return data?.message;
};

const ApiErrorModal = ({
  data,
  handleDismiss,
  isOpen,
}: {
  data: ApiErrorData;
  handleDismiss: (...args: Array<any>) => any;
  isOpen: boolean;
}) => (
  <Dialog
    id="api-error-modal"
    isOpen={isOpen}
    aria-labelledby="api-error-modal-title"
    close={handleDismiss}
    closeButtonLabelText="Tutup"
  >
    <Dialog.Header id="api-error-modal-title" title={getApiErrorTitle(data)} />
    <Dialog.Content>
      {data ? <ApiErrorContent data={data} /> : null}
    </Dialog.Content>
    <Dialog.ActionButtons>
      <Button onClick={handleDismiss} variant={ButtonVariant.Secondary}>
        Tutup
      </Button>
    </Dialog.ActionButtons>
  </Dialog>
);

const ApiErrorList = ({ errors }: ApiErrorData) => {
  const listObjectErrors = (obj: Record<string, any>) => {
    return (
      <ul>
        {Object.keys(obj).map(function (key, index) {
          if (typeof obj[key] === "object") {
            return (
              <li key={index}>
                {key}
                {listObjectErrors(obj[key])}
              </li>
            );
          }

          return (
            <li key={index}>
              {key}: {obj[key]}
            </li>
          );
        })}
      </ul>
    );
  };

  return (
    <div className="api-error-modal__error-list">
      <h5 className="api-error-modal__error-list-heading">Daftar galat</h5>
      {listObjectErrors(errors)}
    </div>
  );
};

const ApiErrorStackTrace = ({ trace }: ApiErrorData) => (
  <div className="api-error-modal__trace">
    <h5 className="api-error-modal__trace-heading">Jejak galat</h5>
    <ol className="api-error-modal__trace-nav">
      {trace
        .filter((item) => item.file)
        .map((item, index) => (
          <li className="api-error-modal__trace-item" key={index}>
            <span className="api-error-modal__trace-source">
              {item.file}({item.line})
            </span>
            &nbsp;
            <span className="api-error-modal__trace-function">
              {item.class ? `${item.class}::${item.function}` : item.function}
            </span>
          </li>
        ))}
    </ol>
  </div>
);

const ApiErrorContent = ({ data }: { data: ApiErrorData }) => {
  return (
    <div className="api-error-modal">
      <div className="api-error-modal__message">{getApiErrorMessage(data)}</div>
      <div className="api-error-modal__source">{data.source}</div>
      {getFieldErrors(data) ? (
        <ApiErrorList errors={getFieldErrors(data)} />
      ) : null}
      {data.trace ? <ApiErrorStackTrace trace={data.trace} /> : null}
    </div>
  );
};

export default ApiErrorModal;
