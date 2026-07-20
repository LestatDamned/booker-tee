import type { ReactNode } from "react";

import { formatIsoDate } from "../../shared/date/format-date";
import styles from "./workbench-row.module.css";

type WorkbenchRowState = "default" | "recent" | "target" | "working";

type WorkbenchRowProps = {
  aside?: ReactNode;
  date?: string;
  description: ReactNode;
  details?: ReactNode;
  expansion?: ReactNode;
  id?: string;
  meta?: ReactNode;
  signals?: ReactNode;
  state?: WorkbenchRowState;
  value?: ReactNode;
};

export function WorkbenchRow({
  aside,
  date,
  description,
  details,
  expansion,
  id,
  meta,
  signals,
  state = "default",
  value,
}: WorkbenchRowProps) {
  return (
    <article className={`${styles.row} ${styles[state]}`} id={id}>
      <div className={styles.main}>
        <header className={styles.header}>
          <div>
            {date ? (
              <time className={styles.date} dateTime={date}>
                {formatIsoDate(date)}
              </time>
            ) : null}
            <h2 className={styles.description}>{description}</h2>
            {details ? <div className={styles.details}>{details}</div> : null}
          </div>
          {value ? <div className={styles.value}>{value}</div> : null}
        </header>
        {meta ? <div className={styles.meta}>{meta}</div> : null}
        {signals ? <div className={styles.signals}>{signals}</div> : null}
      </div>
      {aside ? <aside className={styles.aside}>{aside}</aside> : null}
      {expansion ? <div className={styles.expansion}>{expansion}</div> : null}
    </article>
  );
}
