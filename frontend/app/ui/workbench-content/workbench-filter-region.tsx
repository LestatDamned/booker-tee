import type { ComponentPropsWithoutRef } from "react";

import styles from "./workbench-content.module.css";

type WorkbenchFilterRegionProps = ComponentPropsWithoutRef<"div">;

export function WorkbenchFilterRegion({
  children,
  className,
  ...props
}: WorkbenchFilterRegionProps) {
  return (
    <div
      {...props}
      className={
        className === undefined
          ? styles.filterRegion
          : `${styles.filterRegion} ${className}`
      }
    >
      {children}
    </div>
  );
}
