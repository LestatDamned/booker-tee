import {
  forwardRef,
  type ComponentPropsWithoutRef,
  type ReactNode,
} from "react";

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
  layout?: "auto" | "stacked";
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

export const InlineNotice = forwardRef<HTMLDivElement, InlineNoticeProps>(
  function InlineNotice(
    {
      action,
      children,
      className,
      layout = "auto",
      title,
      tone = "neutral",
      ...props
    },
    ref,
  ) {
    return (
      <div
        {...props}
        className={[styles.notice, className].filter(Boolean).join(" ")}
        data-layout={layout}
        data-tone={tone}
        ref={ref}
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
  },
);
