import type { ComponentPropsWithoutRef } from "react";

import styles from "./workbench-surface.module.css";

type WorkbenchSurfaceProps = ComponentPropsWithoutRef<"section">;

export function WorkbenchSurface({
  children,
  className,
  ...props
}: WorkbenchSurfaceProps) {
  return (
    <section
      className={
        className === undefined
          ? styles.surface
          : `${styles.surface} ${className}`
      }
      {...props}
    >
      {children}
    </section>
  );
}
