import type { ComponentPropsWithoutRef } from "react";

import styles from "./workbench-content.module.css";

type WorkbenchStatusProps = ComponentPropsWithoutRef<"span">;

export function WorkbenchStatus({
  "aria-live": ariaLive = "polite",
  children,
  className,
  ...props
}: WorkbenchStatusProps) {
  return (
    <span
      {...props}
      aria-live={ariaLive}
      className={
        className === undefined
          ? styles.status
          : `${styles.status} ${className}`
      }
    >
      {children}
    </span>
  );
}
