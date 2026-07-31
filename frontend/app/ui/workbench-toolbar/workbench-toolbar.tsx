import type { ComponentPropsWithoutRef } from "react";

import styles from "./workbench-toolbar.module.css";

type WorkbenchToolbarProps = ComponentPropsWithoutRef<"section">;

export function WorkbenchToolbar({
  "aria-label": ariaLabel = "Инструменты списка",
  children,
  className,
  ...props
}: WorkbenchToolbarProps) {
  return (
    <section
      aria-label={ariaLabel}
      className={
        className === undefined
          ? styles.toolbar
          : `${styles.toolbar} ${className}`
      }
      {...props}
    >
      {children}
    </section>
  );
}
