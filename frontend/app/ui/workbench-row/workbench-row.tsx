import type { MouseEvent, ReactNode } from "react";

import { formatIsoDate } from "../../shared/date/format-date";
import styles from "./workbench-row.module.css";

type WorkbenchRowState = "default" | "recent" | "target" | "working";
type WorkbenchRowWorkflowState =
  "default" | "problem" | "review" | "settled" | "suggestion";

type WorkbenchRowProps = {
  aside?: ReactNode;
  date?: string;
  description: ReactNode;
  details?: ReactNode;
  expansion?: ReactNode;
  expansionHidden?: boolean;
  financialHierarchy?: boolean;
  layout?: "card" | "table";
  id?: string;
  meta?: ReactNode;
  onAction?: () => void;
  signals?: ReactNode;
  state?: WorkbenchRowState;
  tabIndex?: number;
  value?: ReactNode;
  workflowState?: WorkbenchRowWorkflowState;
};

export function WorkbenchRow({
  aside,
  date,
  description,
  details,
  expansion,
  expansionHidden = false,
  financialHierarchy = false,
  layout = "card",
  id,
  meta,
  onAction,
  signals,
  state = "default",
  tabIndex,
  value,
  workflowState = "default",
}: WorkbenchRowProps) {
  function notifyAction(event: MouseEvent<HTMLDivElement>) {
    if (event.target instanceof Element && event.target.closest("button")) {
      onAction?.();
    }
  }

  const dateContent = date ? (
    <time className={styles.date} dateTime={date}>
      {formatIsoDate(date)}
    </time>
  ) : null;

  if (layout === "table") {
    return (
      <article
        aria-current={state === "target" ? "true" : undefined}
        className={`${styles.row} ${styles.table} ${styles[state]} ${styles[workflowState]} ${financialHierarchy ? styles.financialHierarchy : ""}`}
        data-state={state}
        data-workflow-state={workflowState}
        id={id}
        tabIndex={tabIndex}
      >
        <div className={styles.dateCell}>{dateContent}</div>
        <div className={styles.descriptionCell}>
          <h2 className={styles.description}>{description}</h2>
          {details ? <div className={styles.details}>{details}</div> : null}
        </div>
        {meta ? <div className={styles.meta}>{meta}</div> : <div />}
        {value ? <div className={styles.value}>{value}</div> : <div />}
        {aside ? (
          <div className={styles.aside} onClickCapture={notifyAction}>
            {aside}
          </div>
        ) : (
          <div />
        )}
        {signals ? <div className={styles.signals}>{signals}</div> : null}
        {expansion ? (
          <div className={styles.expansion} hidden={expansionHidden}>
            {expansion}
          </div>
        ) : null}
      </article>
    );
  }

  return (
    <article
      aria-current={state === "target" ? "true" : undefined}
      className={`${styles.row} ${styles[state]} ${styles[workflowState]} ${financialHierarchy ? styles.financialHierarchy : ""}`}
      data-state={state}
      data-workflow-state={workflowState}
      id={id}
      tabIndex={tabIndex}
    >
      <div className={styles.main}>
        <header className={styles.header}>
          <div>
            {dateContent}
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
