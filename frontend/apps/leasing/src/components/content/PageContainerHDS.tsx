import React, { useRef } from "react";
import classNames from "classnames";
import usePageNavigationOffset from "./usePageNavigationOffset";

type Props = {
  children?: React.ReactNode;
  className?: string;
  hasTabs?: boolean;
};

const PageContainerHDS: React.FC<Props> = ({
  children,
  className,
  hasTabs,
}) => {
  const componentRef = useRef<HTMLDivElement | null>(null);

  usePageNavigationOffset(componentRef);

  return (
    <div
      ref={componentRef}
      className={classNames(
        "content-hds__page-container",
        "foundation-form-reset",
        className,
      )}
      style={{
        paddingTop: hasTabs ? 0 : null,
      }}
    >
      {children}
    </div>
  );
};

export default PageContainerHDS;
