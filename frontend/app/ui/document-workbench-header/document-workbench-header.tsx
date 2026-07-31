import type { ComponentPropsWithoutRef, ReactNode } from "react";

import styles from "./document-workbench-header.module.css";

type DocumentWorkbenchHeaderProps = Omit<
  ComponentPropsWithoutRef<"header">,
  "title"
> & {
  context: ReactNode;
  eyebrow: ReactNode;
  filename: string;
  status: ReactNode;
  statusLabel?: ReactNode;
  title: ReactNode;
};

export function DocumentWorkbenchHeader({
  className,
  context,
  eyebrow,
  filename,
  status,
  statusLabel = "Состояние документа",
  title,
  ...props
}: DocumentWorkbenchHeaderProps) {
  return (
    <header
      className={
        className === undefined
          ? styles.header
          : `${styles.header} ${className}`
      }
      {...props}
    >
      <div className={styles.identity}>
        <p className={styles.eyebrow}>{eyebrow}</p>
        <h1>{title}</h1>
        <p className={styles.context}>{context}</p>
        <p className={styles.filename} title={filename}>
          {filename}
        </p>
      </div>
      <div className={styles.status}>
        <span>{statusLabel}</span>
        {status}
      </div>
    </header>
  );
}
