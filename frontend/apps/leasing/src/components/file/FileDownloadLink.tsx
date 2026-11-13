import React, { PureComponent } from "react";
import { connect } from "react-redux";
import { saveAs } from "file-saver";
import classNames from "classnames";
import Loader from "@/components/loader/Loader";
import LoaderWrapper from "@/components/loader/LoaderWrapper";
import { displayUIMessage, escapeHtml, getFileNameFromResponse } from "@/util/helpers";
import { getApiToken } from "@/auth/selectors";

type Props = {
  apiToken: string;
  className?: string;
  fileName?: string;
  fileUrl: string;
  label: string;
  openInlineInNewTab?: boolean;
};
type State = {
  isLoading: boolean;
};

class FileDownloadLink extends PureComponent<Props, State> {
  state = {
    isLoading: false,
  };
  handleClick = () => {
    const {
      apiToken,
      fileName: fileNameProp,
      fileUrl,
      label,
      openInlineInNewTab,
    } = this.props;
    const { isLoading } = this.state;
    if (isLoading) return;
    this.setState({
      isLoading: true,
    });

    const stopLoader = () => {
      this.setState({
        isLoading: false,
      });
    };

    const fetchFile = async () => {
      const request = new Request(fileUrl);

      if (apiToken) {
        request.headers.set("Authorization", `Bearer ${apiToken}`);
      }

      try {
        const response = await fetch(request);

        switch (response.status) {
          case 200: {
            const blob = await response.blob();

            if (!openInlineInNewTab) {
              // Download the file
              const filename = fileNameProp
                ? fileNameProp
                : getFileNameFromResponse(response);
              saveAs(blob, filename || label);

              break;
            }

            // Show the file in a new tab inside a html embed element
            const contentTypeHeader = response.headers.get("Content-Type");
            const contentType = contentTypeHeader
              ? contentTypeHeader.split(";")[0]
              : "application/pdf";
            const fileBlob = new Blob([blob], { type: contentType });
            const fileUrl = URL.createObjectURL(fileBlob);
            const title = fileNameProp ? fileNameProp : label;
            // Nama berkas bisa berasal dari unggahan pengguna: di-escape agar
            // tidak bisa keluar dari atribut title/type pada blob HTML ini.
            const htmlContent = `<html><head><meta charset="UTF-8" /><title>${escapeHtml(title)}</title></head><body style="margin:0;"><embed src="${fileUrl}" type="${escapeHtml(contentType)}" width="100%" height="100%"></body></html>`;

            const htmlBlob = new Blob([htmlContent], { type: "text/html" });
            const htmlUrl = URL.createObjectURL(htmlBlob);

            window.open(htmlUrl, "_blank");
            break;
          }

          default: {
            const errors = await response.json();
            const errorMessage = errors?.error ? errors.error : "";
            displayUIMessage(
              {
                title: "Pengunduhan berkas gagal",
                body: errorMessage,
              },
              {
                type: "error",
                timeOut: 10000,
              },
            );
            break;
          }
        }

        stopLoader();
      } catch (e) {
        console.error(`Failed to download file with error ${e}`);
        stopLoader();
        displayUIMessage(
          {
            title: "",
            body: "Pengunduhan berkas gagal",
          },
          {
            type: "error",
          },
        );
      }
    };

    fetchFile();
  };
  handleKeyDown = (e: any) => {
    if (e.keyCode === 13) {
      e.preventDefault();
      this.handleClick();
    }
  };

  render() {
    const { className, label } = this.props;
    const { isLoading } = this.state;
    return (
      <a
        className={classNames("file__file-download-link", className)}
        onClick={this.handleClick}
        onKeyDown={this.handleKeyDown}
        tabIndex={0}
      >
        {label}
        {isLoading && (
          <LoaderWrapper className="small-inline-wrapper">
            <Loader isLoading={isLoading} className="small" />
          </LoaderWrapper>
        )}
      </a>
    );
  }
}

export default connect((state) => {
  return {
    apiToken: getApiToken(state),
  };
})(FileDownloadLink);
