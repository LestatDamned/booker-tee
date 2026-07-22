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
  | "category"
  | "adjustment";

export type BadgeVariant = "outline" | "soft" | "status";

type BadgeProps = {
  children: ReactNode;
  tone?: BadgeTone;
  variant?: BadgeVariant;
};

export function Badge({
  children,
  tone = "neutral",
  variant = "outline",
}: BadgeProps) {
  return (
    <span
      className={`${styles.badge} ${styles[tone]} ${styles[variant]}`}
      data-variant={variant}
    >
      {children}
    </span>
  );
}
