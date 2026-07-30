import type {
  ComponentPropsWithRef,
  ComponentPropsWithoutRef,
  ReactNode,
} from "react";

import { Icon, type IconName } from "../icon/icon";
import styles from "./button.module.css";

export type ButtonTone =
  "primary" | "secondary" | "ghost" | "dangerSecondary" | "danger";

type ButtonProps = Omit<ComponentPropsWithRef<"button">, "className"> & {
  children: ReactNode;
  className?: string;
  icon?: IconName;
  isLoading?: boolean;
  tone?: ButtonTone;
};

type ButtonLinkProps = Omit<
  ComponentPropsWithoutRef<"a">,
  "children" | "className"
> & {
  children: ReactNode;
  className?: string;
  icon?: IconName;
  tone?: ButtonTone;
};

export function Button({
  children,
  className,
  disabled,
  icon,
  isLoading = false,
  tone = "secondary",
  type = "button",
  ...buttonProps
}: ButtonProps) {
  const classes = [styles.button, styles[tone], className]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      {...buttonProps}
      aria-busy={isLoading || undefined}
      className={classes}
      data-tone={tone}
      disabled={disabled || isLoading}
      type={type}
    >
      {isLoading ? (
        <span aria-hidden="true" className={styles.spinner} />
      ) : icon ? (
        <Icon name={icon} size={18} />
      ) : null}
      <span>{children}</span>
    </button>
  );
}

export function ButtonLink({
  children,
  className,
  icon,
  tone = "secondary",
  ...linkProps
}: ButtonLinkProps) {
  const classes = [styles.button, styles[tone], className]
    .filter(Boolean)
    .join(" ");

  return (
    <a {...linkProps} className={classes} data-tone={tone}>
      {icon ? <Icon name={icon} size={18} /> : null}
      <span>{children}</span>
    </a>
  );
}
