import type { ComponentPropsWithRef, ReactNode } from "react";

import styles from "./button.module.css";

export type ButtonTone = "primary" | "secondary" | "ghost" | "danger";

type ButtonProps = Omit<ComponentPropsWithRef<"button">, "className"> & {
  children: ReactNode;
  className?: string;
  isLoading?: boolean;
  tone?: ButtonTone;
};

export function Button({
  children,
  className,
  disabled,
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
      disabled={disabled || isLoading}
      type={type}
    >
      {isLoading ? (
        <span aria-hidden="true" className={styles.spinner} />
      ) : null}
      <span>{children}</span>
    </button>
  );
}
