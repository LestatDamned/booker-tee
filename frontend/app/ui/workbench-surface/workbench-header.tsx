import type { ComponentPropsWithoutRef } from "react";

import styles from "./workbench-surface.module.css";

type WorkbenchHeaderProps = ComponentPropsWithoutRef<"div">;

export function WorkbenchHeader({
  children,
  className,
  ...props
}: WorkbenchHeaderProps) {
  return (
    <div
      className={
        className === undefined
          ? styles.header
          : `${styles.header} ${className}`
      }
      {...props}
    >
      {children}
    </div>
  );
}
