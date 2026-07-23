import type { ReactNode } from "react";

import styles from "./tag.module.css";

export type TagTone =
  | "neutral"
  | "income"
  | "expense"
  | "transfer"
  | "category"
  | "automation"
  | "adjustment";

export type TagVariant = "outline" | "soft";

type TagProps = {
  children: ReactNode;
  tone?: TagTone;
  variant?: TagVariant;
};

export function Tag({
  children,
  tone = "neutral",
  variant = "outline",
}: TagProps) {
  return (
    <span
      className={`${styles.tag} ${styles[tone]} ${styles[variant]}`}
      data-tone={tone}
      data-variant={variant}
    >
      {children}
    </span>
  );
}
