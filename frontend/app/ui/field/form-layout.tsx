import type { ReactNode } from "react";

import styles from "./form-layout.module.css";

type FormGridProps = {
  children: ReactNode;
  columns?: "two" | "three";
};

export function FormGrid({ children, columns = "three" }: FormGridProps) {
  return (
    <div className={styles.grid} data-columns={columns}>
      {children}
    </div>
  );
}

type FormGridItemProps = {
  children: ReactNode;
  span?: "full" | "two";
};

export function FormGridItem({ children, span = "full" }: FormGridItemProps) {
  return (
    <div className={styles.gridItem} data-span={span}>
      {children}
    </div>
  );
}

export function FormActions({
  children,
  layout = "start",
  sticky = false,
}: {
  children: ReactNode;
  layout?: "split" | "start";
  sticky?: boolean;
}) {
  return (
    <div
      className={styles.actions}
      data-layout={layout}
      data-sticky={sticky || undefined}
    >
      {children}
    </div>
  );
}
