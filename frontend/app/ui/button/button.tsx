import type {
  ComponentPropsWithRef,
  ComponentPropsWithoutRef,
  ReactNode,
} from "react";
import { Link } from "react-router";

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

type RouterButtonLinkProps = Omit<
  ComponentPropsWithoutRef<typeof Link>,
  "children" | "className"
> & {
  children: ReactNode;
  className?: string | undefined;
  icon?: IconName;
  tone?: ButtonTone;
};

function buttonClassNames(tone: ButtonTone, className?: string) {
  return [styles.button, styles[tone], className].filter(Boolean).join(" ");
}

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
  return (
    <button
      {...buttonProps}
      aria-busy={isLoading || undefined}
      className={buttonClassNames(tone, className)}
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
  return (
    <a
      {...linkProps}
      className={buttonClassNames(tone, className)}
      data-tone={tone}
    >
      {icon ? <Icon name={icon} size={18} /> : null}
      <span>{children}</span>
    </a>
  );
}

export function RouterButtonLink({
  children,
  className,
  icon,
  tone = "secondary",
  ...linkProps
}: RouterButtonLinkProps) {
  return (
    <Link
      {...linkProps}
      className={buttonClassNames(tone, className)}
      data-tone={tone}
    >
      {icon ? <Icon name={icon} size={18} /> : null}
      <span>{children}</span>
    </Link>
  );
}
