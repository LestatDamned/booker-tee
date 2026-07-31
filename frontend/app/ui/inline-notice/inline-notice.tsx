import type { ComponentPropsWithoutRef, ReactNode } from "react";

import { Icon, type IconName } from "../icon/icon";
import styles from "./inline-notice.module.css";

export type InlineNoticeTone =
  "neutral" | "information" | "warning" | "success" | "danger";

type InlineNoticeProps = Omit<
  ComponentPropsWithoutRef<"div">,
  "children" | "className" | "title"
> & {
  action?: ReactNode;
  children: ReactNode;
  className?: string | undefined;
  title?: ReactNode;
  tone?: InlineNoticeTone;
};

const toneIcons: Record<InlineNoticeTone, IconName> = {
  danger: "error",
  information: "information",
  neutral: "neutral",
  success: "check",
  warning: "warning",
};

export function InlineNotice({
  action,
  children,
  className,
  title,
  tone = "neutral",
  ...props
}: InlineNoticeProps) {
  return (
    <div
      {...props}
      className={[styles.notice, className].filter(Boolean).join(" ")}
      data-tone={tone}
    >
      <Icon
        className={styles.icon}
        name={toneIcons[tone]}
        size={22}
        weight="bold"
      />
      <div className={styles.content}>
        {title === undefined ? null : (
          <strong className={styles.title}>{title}</strong>
        )}
        <div className={styles.message}>{children}</div>
      </div>
      {action === undefined ? null : (
        <div className={styles.action}>{action}</div>
      )}
    </div>
  );
}
