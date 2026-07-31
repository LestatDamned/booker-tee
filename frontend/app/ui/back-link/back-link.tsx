import type { ComponentPropsWithoutRef, ReactNode } from "react";
import { Link } from "react-router";

import { Icon } from "../icon/icon";
import styles from "./back-link.module.css";

type BackLinkProps = Omit<
  ComponentPropsWithoutRef<typeof Link>,
  "children" | "className"
> & {
  children: ReactNode;
  className?: string | undefined;
};

export function BackLink({ children, className, ...linkProps }: BackLinkProps) {
  const classes = [styles.link, className].filter(Boolean).join(" ");

  return (
    <Link {...linkProps} className={classes}>
      <Icon name="back" size={16} />
      <span>{children}</span>
    </Link>
  );
}
