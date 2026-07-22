import type { ReactNode } from "react";

import styles from "./action-stack.module.css";

type ActionStackProps = {
  danger?: ReactNode;
  disclosureOpen?: boolean;
  onDisclosureChange?: (open: boolean) => void;
  overflow?: ReactNode;
  primary?: ReactNode;
  secondary?: ReactNode;
  orientation?: "column" | "row";
};

export function ActionStack({
  danger,
  disclosureOpen,
  onDisclosureChange,
  overflow,
  primary,
  secondary,
  orientation = "column",
}: ActionStackProps) {
  return (
    <div
      className={`${styles.stack} ${orientation === "row" ? styles.horizontal : ""}`}
    >
      {primary ? <div className={styles.group}>{primary}</div> : null}
      {secondary ? <div className={styles.group}>{secondary}</div> : null}
      {overflow || danger ? (
        <details
          className={styles.more}
          onToggle={(event) => onDisclosureChange?.(event.currentTarget.open)}
          {...(disclosureOpen === undefined ? {} : { open: disclosureOpen })}
        >
          <summary>Ещё действия</summary>
          <div className={styles.menu}>
            {overflow ? <div className={styles.group}>{overflow}</div> : null}
            {danger ? (
              <div aria-label="Опасные действия" className={styles.danger}>
                <span className={styles.dangerLabel}>Опасные действия</span>
                {danger}
              </div>
            ) : null}
          </div>
        </details>
      ) : null}
    </div>
  );
}
