import type { ReactNode } from "react";

import { Icon, type IconName } from "../icon/icon";
import styles from "./status-label.module.css";

export type StatusTone =
  "neutral" | "success" | "warning" | "danger" | "information" | "automation";

type StatusLabelProps = {
  children: ReactNode;
  showIcon?: boolean;
  tone?: StatusTone;
  variant?: "plain" | "soft";
};

const toneIcons: Record<StatusTone, IconName> = {
  automation: "automation",
  danger: "error",
  information: "information",
  neutral: "neutral",
  success: "check",
  warning: "warning",
};

export function StatusLabel({
  children,
  showIcon = true,
  tone = "neutral",
  variant = "plain",
}: StatusLabelProps) {
  return (
    <span
      className={`${styles.status} ${styles[tone]} ${styles[variant]}`}
      data-tone={tone}
      {...(variant === "soft" ? { "data-variant": variant } : {})}
    >
      {showIcon ? (
        <Icon name={toneIcons[tone]} size={16} weight="bold" />
      ) : null}
      {children}
    </span>
  );
}
