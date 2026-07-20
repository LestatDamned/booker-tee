import type { ButtonHTMLAttributes } from "react";

import styles from "./button.module.css";

type IconName = "close" | "edit" | "more" | "retry";

type IconButtonProps = Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "aria-label" | "children" | "className"
> & {
  "aria-label": string;
  icon: IconName;
  tone?: "ghost" | "danger";
};

const iconPaths: Record<IconName, string> = {
  close: "M6 6l12 12M18 6 6 18",
  edit: "M4 20h4L19 9l-4-4L4 16v4M13.5 6.5l4 4",
  more: "M5 12h.01M12 12h.01M19 12h.01",
  retry: "M20 11a8 8 0 10-2.3 5.7M20 4v7h-7",
};

export function IconButton({
  "aria-label": accessibleLabel,
  icon,
  tone = "ghost",
  type = "button",
  ...buttonProps
}: IconButtonProps) {
  return (
    <button
      {...buttonProps}
      aria-label={accessibleLabel}
      className={`${styles.iconButton} ${styles[tone]}`}
      type={type}
    >
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path d={iconPaths[icon]} />
      </svg>
    </button>
  );
}
