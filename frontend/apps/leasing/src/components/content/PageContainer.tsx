import React, { useRef } from "react";
import classNames from "classnames";
import usePageNavigationOffset from "./usePageNavigationOffset";

type Props = {
  children?: React.ReactNode;
  className?: string;
  hasTabs?: boolean;
};

const PageContainer: React.FC<Props> = ({ children, className, hasTabs }) => {
  const componentRef = useRef<HTMLDivElement | null>(null);

  usePageNavigationOffset(componentRef);

  return (
    <div
      ref={componentRef}
      className={classNames("content__page-container", className)}
      style={{
        paddingTop: hasTabs ? 0 : null,
      }}
    >
      {children}
    </div>
  );
};

export default PageContainer;
