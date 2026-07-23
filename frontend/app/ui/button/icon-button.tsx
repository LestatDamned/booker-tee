import type { ButtonHTMLAttributes } from "react";

import { Icon, type IconName } from "../icon/icon";
import styles from "./button.module.css";

type IconButtonProps = Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "aria-label" | "children" | "className"
> & {
  "aria-label": string;
  icon: IconName;
  tone?: "ghost" | "danger";
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
      data-tooltip={accessibleLabel}
      type={type}
    >
      <Icon name={icon} size={20} />
    </button>
  );
}
