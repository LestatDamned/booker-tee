import type { ReactNode } from "react";

import styles from "./badge.module.css";

export type BadgeTone =
  | "neutral"
  | "success"
  | "warning"
  | "danger"
  | "income"
  | "expense"
  | "transfer"
  | "adjustment";

type BadgeProps = {
  children: ReactNode;
  tone?: BadgeTone;
};

export function Badge({ children, tone = "neutral" }: BadgeProps) {
  return <span className={`${styles.badge} ${styles[tone]}`}>{children}</span>;
}
