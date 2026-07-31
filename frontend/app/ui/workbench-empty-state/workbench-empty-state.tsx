import type { ReactNode } from "react";

import { Icon, type IconName } from "../icon/icon";
import styles from "./workbench-empty-state.module.css";

type WorkbenchEmptyStateProps = {
  action?: ReactNode;
  children: ReactNode;
  icon: IconName;
  kind?: "primary" | "filtered";
  title: string;
};

export function WorkbenchEmptyState({
  action,
  children,
  icon,
  kind = "primary",
  title,
}: WorkbenchEmptyStateProps) {
  return (
    <section
      aria-live="polite"
      className={styles.state}
      data-kind={kind}
      role="status"
    >
      <span aria-hidden="true" className={styles.icon}>
        <Icon name={icon} size={28} weight="regular" />
      </span>
      <div className={styles.copy}>
        <h2>{title}</h2>
        <p>{children}</p>
      </div>
      {action ? <div className={styles.action}>{action}</div> : null}
    </section>
  );
}
