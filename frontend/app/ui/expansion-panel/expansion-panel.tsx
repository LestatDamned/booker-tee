import type { ReactNode } from "react";

import { IconButton } from "../button/icon-button";
import styles from "./expansion-panel.module.css";

type ExpansionPanelProps = {
  children: ReactNode;
  id: string;
  isOpen: boolean;
  onClose: () => void;
  showHeader?: boolean;
  title: string;
};

export function ExpansionPanel({
  children,
  id,
  isOpen,
  onClose,
  showHeader = true,
  title,
}: ExpansionPanelProps) {
  return (
    <section
      aria-live="polite"
      className={styles.panel}
      hidden={!isOpen}
      id={id}
    >
      {showHeader ? (
        <header className={styles.header}>
          <h3 className={styles.title}>{title}</h3>
          <IconButton
            aria-label="Закрыть панель"
            icon="close"
            onClick={onClose}
          />
        </header>
      ) : null}
      <div className={styles.content}>{children}</div>
    </section>
  );
}
