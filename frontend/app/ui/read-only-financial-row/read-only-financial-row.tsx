import type { ReactNode } from "react";

import styles from "./read-only-financial-row.module.css";

type ReadOnlyFinancialRowProps = {
  context?: ReactNode;
  date?: ReactNode;
  dateTime?: string | undefined;
  description: ReactNode;
  details?: ReactNode;
  id?: string;
  issues?: ReactNode;
  status?: ReactNode;
  tone?: "default" | "problem";
  value?: ReactNode;
};

export function ReadOnlyFinancialRow({
  context,
  date,
  dateTime,
  description,
  details,
  id,
  issues,
  status,
  tone = "default",
  value,
}: ReadOnlyFinancialRowProps) {
  return (
    <article className={`${styles.row} ${styles[tone]}`} id={id}>
      <header className={styles.header}>
        <div className={styles.facts}>
          {date ? (
            dateTime ? (
              <time className={styles.date} dateTime={dateTime}>
                {date}
              </time>
            ) : (
              <span className={styles.date}>{date}</span>
            )
          ) : null}
          {context ? <span className={styles.context}>{context}</span> : null}
          {status ? <div className={styles.status}>{status}</div> : null}
        </div>
        {value ? <div className={styles.value}>{value}</div> : null}
      </header>
      <div className={styles.description}>{description}</div>
      {details ? <div className={styles.details}>{details}</div> : null}
      {issues ? <div className={styles.issues}>{issues}</div> : null}
    </article>
  );
}
