import type { MouseEvent, ReactNode } from "react";

import { formatIsoDate } from "../../shared/date/format-date";
import styles from "./workbench-row.module.css";

type WorkbenchRowState = "default" | "recent" | "target" | "working";

type WorkbenchRowProps = {
  aside?: ReactNode;
  date?: string;
  description: ReactNode;
  details?: ReactNode;
  expansion?: ReactNode;
  expansionHidden?: boolean;
  id?: string;
  meta?: ReactNode;
  onAction?: () => void;
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
  expansionHidden = false,
  id,
  meta,
  onAction,
  signals,
  state = "default",
  value,
}: WorkbenchRowProps) {
  function notifyAction(event: MouseEvent<HTMLDivElement>) {
    if (event.target instanceof Element && event.target.closest("button")) {
      onAction?.();
    }
  }

  return (
    <article
      aria-current={state === "target" ? "true" : undefined}
      className={`${styles.row} ${styles[state]}`}
      data-state={state}
      id={id}
    >
      {state !== "default" ? (
        <span className="visually-hidden">{rowStateLabel(state)}</span>
      ) : null}
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
      {aside ? (
        <div className={styles.aside} onClickCapture={notifyAction}>
          {aside}
        </div>
      ) : null}
      {expansion ? (
        <div className={styles.expansion} hidden={expansionHidden}>
          {expansion}
        </div>
      ) : null}
    </article>
  );
}

function rowStateLabel(state: Exclude<WorkbenchRowState, "default">): string {
  const labels = {
    recent: "Недавно изменённая операция.",
    target: "Выбранная операция.",
    working: "Операция открыта для работы.",
  } satisfies Record<Exclude<WorkbenchRowState, "default">, string>;
  return labels[state];
}
