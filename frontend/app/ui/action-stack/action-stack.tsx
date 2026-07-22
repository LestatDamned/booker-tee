import type { ReactNode } from "react";

import styles from "./action-stack.module.css";

type ActionStackProps = {
  danger?: ReactNode;
  overflow?: ReactNode;
  primary?: ReactNode;
  secondary?: ReactNode;
  orientation?: "column" | "row";
};

export function ActionStack({
  danger,
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
        <details className={styles.more}>
          <summary>Ещё действия</summary>
          <div className={styles.menu}>
            {overflow ? <div className={styles.group}>{overflow}</div> : null}
            {danger ? (
              <div aria-label="Опасные действия" className={styles.danger}>
                {danger}
              </div>
            ) : null}
          </div>
        </details>
      ) : null}
    </div>
  );
}
