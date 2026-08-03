import type { ReactNode } from "react";

import styles from "./page-header.module.css";

type PageHeaderProps = {
  actions?: ReactNode;
  description?: string;
  eyebrow?: string;
  title: string;
  titleId?: string;
};

export function PageHeader({
  actions,
  description,
  eyebrow,
  title,
  titleId,
}: PageHeaderProps) {
  return (
    <header className={styles.header}>
      <div>
        {eyebrow ? <p className={styles.eyebrow}>{eyebrow}</p> : null}
        <h1 className={styles.title} id={titleId}>
          {title}
        </h1>
        {description ? (
          <p className={styles.description}>{description}</p>
        ) : null}
      </div>
      {actions ? <div className={styles.actions}>{actions}</div> : null}
    </header>
  );
}
