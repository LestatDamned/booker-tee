import type { ComponentPropsWithoutRef, ElementType, ReactNode } from "react";
import { Link } from "react-router";

import { Badge } from "../badge/badge";
import styles from "./selection-tabs.module.css";

type SelectionTabsProps = Omit<ComponentPropsWithoutRef<"div">, "className"> & {
  as?: "div" | "nav";
  className?: string | undefined;
};

export function SelectionTabs({
  as = "div",
  className,
  ...props
}: SelectionTabsProps) {
  const Element: ElementType = as;
  return (
    <Element
      {...props}
      className={[styles.tabs, className].filter(Boolean).join(" ")}
    />
  );
}

type SelectionTabLinkProps = Omit<
  ComponentPropsWithoutRef<typeof Link>,
  "aria-current" | "children" | "className"
> & {
  children: ReactNode;
  className?: string | undefined;
  count?: number;
  selected: boolean;
};

export function SelectionTabLink({
  children,
  className,
  count,
  selected,
  ...props
}: SelectionTabLinkProps) {
  return (
    <Link
      {...props}
      aria-current={selected ? "page" : undefined}
      className={[styles.tab, className].filter(Boolean).join(" ")}
      data-selected={selected}
    >
      <span>{children}</span>{" "}
      {count === undefined ? null : <Badge>{count}</Badge>}
    </Link>
  );
}

type SelectionTabButtonProps = Omit<
  ComponentPropsWithoutRef<"button">,
  "aria-pressed" | "children" | "className" | "type"
> & {
  children: ReactNode;
  className?: string | undefined;
  count?: number;
  selected: boolean;
};

export function SelectionTabButton({
  children,
  className,
  count,
  selected,
  ...props
}: SelectionTabButtonProps) {
  return (
    <button
      {...props}
      aria-pressed={selected}
      className={[styles.tab, className].filter(Boolean).join(" ")}
      data-selected={selected}
      type="button"
    >
      <span>{children}</span>{" "}
      {count === undefined ? null : <Badge>{count}</Badge>}
    </button>
  );
}
