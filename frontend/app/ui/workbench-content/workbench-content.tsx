import type { ComponentPropsWithoutRef } from "react";

import styles from "./workbench-content.module.css";

type WorkbenchContentProps = ComponentPropsWithoutRef<"section"> & {
  isEmpty: boolean;
};

export function WorkbenchContent({
  children,
  className,
  isEmpty,
  ...props
}: WorkbenchContentProps) {
  return (
    <section
      {...props}
      className={
        className === undefined
          ? styles.content
          : `${styles.content} ${className}`
      }
      data-empty={isEmpty ? "true" : undefined}
    >
      {children}
    </section>
  );
}
