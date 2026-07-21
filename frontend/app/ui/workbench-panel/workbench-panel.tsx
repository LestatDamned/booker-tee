import { useEffect, useId, useRef, type ReactNode } from "react";

import { Button } from "../button/button";
import styles from "./workbench-panel.module.css";

type WorkbenchPanelProps = {
  children: ReactNode;
  description?: string;
  disabled?: boolean;
  onClose: () => void;
  title: string;
};

export function WorkbenchPanel({
  children,
  description,
  disabled = false,
  onClose,
  title,
}: WorkbenchPanelProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const trigger = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    if (dialog && typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog?.setAttribute("open", "");
    }

    return () => {
      if (dialog && typeof dialog.close === "function") {
        dialog.close();
      } else {
        dialog?.removeAttribute("open");
      }
      queueMicrotask(() => trigger?.focus());
    };
  }, []);

  return (
    <dialog
      aria-labelledby={titleId}
      className={styles.dialog}
      onCancel={(event) => {
        event.preventDefault();
        if (!disabled) {
          onClose();
        }
      }}
      ref={dialogRef}
    >
      <section className={styles.panel}>
        <header className={styles.header}>
          <div>
            <h2 id={titleId}>{title}</h2>
            {description ? <p>{description}</p> : null}
          </div>
          <Button disabled={disabled} onClick={onClose} tone="ghost">
            Закрыть
          </Button>
        </header>
        <div className={styles.body}>{children}</div>
      </section>
    </dialog>
  );
}
