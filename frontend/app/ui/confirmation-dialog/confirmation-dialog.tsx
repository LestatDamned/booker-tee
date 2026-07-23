import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { Button } from "../button/button";
import { IconButton } from "../button/icon-button";
import styles from "./confirmation-dialog.module.css";

type ConfirmationDialogProps = {
  cancelLabel?: string;
  children?: ReactNode;
  confirmLabel: string;
  description: string;
  disabled?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  pending?: boolean;
  title: string;
};

export function ConfirmationDialog({
  cancelLabel = "Отмена",
  children,
  confirmLabel,
  description,
  disabled = false,
  onCancel,
  onConfirm,
  pending = false,
  title,
}: ConfirmationDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const trigger = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    if (dialog && typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog?.setAttribute("open", "");
    }
    queueMicrotask(() => cancelRef.current?.focus());

    return () => {
      if (dialog && typeof dialog.close === "function") {
        dialog.close();
      } else {
        dialog?.removeAttribute("open");
      }
      queueMicrotask(() => trigger?.focus());
    };
  }, []);

  return createPortal(
    <dialog
      aria-describedby={descriptionId}
      aria-labelledby={titleId}
      className={styles.dialog}
      data-action-stack-overlay="true"
      onCancel={(event) => {
        event.preventDefault();
        if (!disabled && !pending) onCancel();
      }}
      ref={dialogRef}
    >
      <section className={styles.panel}>
        <header className={styles.header}>
          <h2 id={titleId}>{title}</h2>
          <IconButton
            aria-label="Закрыть"
            disabled={disabled || pending}
            icon="close"
            onClick={onCancel}
          />
        </header>
        <p className={styles.description} id={descriptionId}>
          {description}
        </p>
        {children}
        <footer className={styles.actions}>
          <Button
            disabled={disabled || pending}
            onClick={onCancel}
            ref={cancelRef}
          >
            {cancelLabel}
          </Button>
          <Button
            disabled={disabled}
            isLoading={pending}
            onClick={onConfirm}
            tone="danger"
          >
            {confirmLabel}
          </Button>
        </footer>
      </section>
    </dialog>,
    document.body,
  );
}
