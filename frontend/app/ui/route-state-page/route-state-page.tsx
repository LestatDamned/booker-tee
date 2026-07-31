import type { ReactNode } from "react";

import { ButtonLink } from "../button/button";
import { Icon, type IconName } from "../icon/icon";
import styles from "./route-state-page.module.css";

export type RouteStateKind =
  "unauthenticated" | "forbidden" | "notFound" | "error";

type RouteStatePageProps = {
  actionHref: string;
  actionIcon?: IconName;
  actionLabel: string;
  children?: ReactNode;
  eyebrow: string;
  kind: RouteStateKind;
  title: string;
};

const statePresentation: Record<
  RouteStateKind,
  { actionIcon: IconName; icon: IconName }
> = {
  unauthenticated: { actionIcon: "forward", icon: "information" },
  forbidden: { actionIcon: "back", icon: "warning" },
  notFound: { actionIcon: "back", icon: "search" },
  error: { actionIcon: "retry", icon: "error" },
};

export function RouteStatePage({
  actionHref,
  actionIcon,
  actionLabel,
  children,
  eyebrow,
  kind,
  title,
}: RouteStatePageProps) {
  const presentation = statePresentation[kind];
  const titleId = `route-state-${kind}-title`;

  return (
    <main aria-labelledby={titleId} className={styles.page} data-kind={kind}>
      <section
        className={styles.state}
        role={kind === "error" ? "alert" : undefined}
      >
        <span aria-hidden="true" className={styles.icon}>
          <Icon name={presentation.icon} size={30} weight="regular" />
        </span>
        <div className={styles.copy}>
          <p className={styles.eyebrow}>{eyebrow}</p>
          <h1 id={titleId}>{title}</h1>
          {children ? <p className={styles.message}>{children}</p> : null}
        </div>
        <ButtonLink
          icon={actionIcon ?? presentation.actionIcon}
          href={actionHref}
          tone="primary"
        >
          {actionLabel}
        </ButtonLink>
      </section>
    </main>
  );
}
