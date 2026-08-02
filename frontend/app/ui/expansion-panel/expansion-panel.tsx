import type { ReactNode } from "react";

import { IconButton } from "../button/icon-button";
import styles from "./expansion-panel.module.css";

type ExpansionPanelProps = {
  children: ReactNode;
  className?: string | undefined;
  id: string;
  isOpen?: boolean;
  onClose?: () => void;
  showHeader?: boolean;
  title: string;
  titleId?: string;
};

export function ExpansionPanel({
  children,
  className,
  id,
  isOpen = true,
  onClose,
  showHeader = true,
  title,
  titleId = `${id}-title`,
}: ExpansionPanelProps) {
  return (
    <section
      aria-labelledby={showHeader ? titleId : undefined}
      aria-live="polite"
      className={[styles.panel, className].filter(Boolean).join(" ")}
      data-workbench-row-expansion
      hidden={!isOpen}
      id={id}
    >
      {showHeader ? (
        <header className={styles.header}>
          <h3 className={styles.title} id={titleId}>
            {title}
          </h3>
          {onClose ? (
            <IconButton
              aria-label="Закрыть панель"
              icon="close"
              onClick={onClose}
            />
          ) : null}
        </header>
      ) : null}
      <div className={styles.content}>{children}</div>
    </section>
  );
}
