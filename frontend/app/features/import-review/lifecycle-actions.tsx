import { useEffect, useRef, useState } from "react";

import { Button, type ButtonTone } from "../../ui/button/button";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import {
  loadImportReview,
  type ImportReviewDto,
} from "./api/import-review-api";
import {
  updateImportReviewLifecycle,
  type ImportReviewLifecycleRequest,
} from "./api/import-review-mutations";
import styles from "./import-review-editor.module.css";

type LifecycleAction = ImportReviewLifecycleRequest["action"];

type LifecycleActionsProps = {
  actions?: LifecycleAction[];
  csrfToken: string;
  documentId: string;
  item: ImportReviewDto["items"][number];
  onMenuDismiss?: () => void;
  onReviewReconciled: (review: ImportReviewDto) => void;
  onSuccess: (message: string) => void;
  readonly: boolean;
};

export function LifecycleActions({
  actions,
  csrfToken,
  documentId,
  item,
  onMenuDismiss,
  onReviewReconciled,
  onSuccess,
  readonly,
}: LifecycleActionsProps) {
  const [pending, setPending] = useState<LifecycleAction | "refresh" | null>(
    null,
  );
  const [confirmation, setConfirmation] = useState<LifecycleAction | null>(
    null,
  );
  const [conflict, setConflict] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recovery, setRecovery] = useState<
    { kind: "refresh" } | { kind: "retry"; action: LifecycleAction } | null
  >(null);
  const cancelConfirmationRef = useRef<HTMLButtonElement>(null);
  const alertRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (confirmation) cancelConfirmationRef.current?.focus();
  }, [confirmation]);

  useEffect(() => {
    if (error) alertRef.current?.focus();
  }, [error]);

  const visibleActions = actions ?? item.lifecycle.allowedActions;
  if (readonly || visibleActions.length === 0) return null;

  async function run(action: LifecycleAction) {
    setPending(action);
    setError(null);
    setConflict(false);
    setRecovery(null);
    const result = await updateImportReviewLifecycle(
      documentId,
      item.id,
      { action, expectedStatus: item.status },
      csrfToken,
    );
    setPending(null);
    setConfirmation(null);
    if (result.status === "success") {
      onMenuDismiss?.();
      onReviewReconciled(result.data.review);
      const successMessage = lifecycleSuccessMessage(action, item.status);
      if (successMessage) onSuccess(successMessage);
      return;
    }
    if (result.status === "conflict") {
      setConflict(true);
      setRecovery({ kind: "refresh" });
      setError(`${result.message} Загрузите актуальное состояние строки.`);
      return;
    }
    if (result.status === "validation_error") {
      setRecovery({ kind: "refresh" });
      setError(`${result.message} Обновите строку и проверьте данные.`);
      return;
    }
    if (result.status === "error") {
      setRecovery({ kind: "retry", action });
      setError(`${result.message} Проверьте соединение и повторите действие.`);
      return;
    }
    setError(
      result.status === "forbidden"
        ? "Недостаточно прав для изменения строки."
        : "Сессия завершилась. Войдите снова.",
    );
  }

  async function refresh() {
    setPending("refresh");
    setError(null);
    setRecovery(null);
    const result = await loadImportReview(documentId);
    setPending(null);
    if (result.status === "success") {
      setConflict(false);
      onMenuDismiss?.();
      onReviewReconciled(result.review);
      return;
    }
    setError(
      result.status === "error"
        ? `${result.message} Проверьте соединение и повторите обновление.`
        : "Не удалось обновить состояние import review.",
    );
    setRecovery({ kind: "refresh" });
  }

  function requestAction(action: LifecycleAction) {
    setError(null);
    setConflict(false);
    setRecovery(null);
    if (isDangerAction(action)) {
      setConfirmation(action);
      return;
    }
    void run(action);
  }

  return (
    <section
      aria-label="Действия со строкой"
      className={styles.lifecycleActions}
    >
      <div className={styles.lifecycleButtons}>
        {visibleActions.map((action) => (
          <Button
            disabled={pending !== null}
            isLoading={pending === action}
            key={action}
            onClick={() => requestAction(action)}
            tone={actionTone(action)}
          >
            {actionLabel(action, item.status)}
          </Button>
        ))}
      </div>
      {confirmation ? (
        <div className={styles.lifecycleConfirmation} role="group">
          <p>{confirmationCopy(confirmation)}</p>
          <div>
            <Button
              disabled={pending !== null}
              onClick={() => {
                setConfirmation(null);
                onMenuDismiss?.();
              }}
              ref={cancelConfirmationRef}
            >
              Отмена
            </Button>
            <Button
              isLoading={pending === confirmation}
              onClick={() => void run(confirmation)}
              tone="danger"
            >
              Подтвердить
            </Button>
          </div>
        </div>
      ) : null}
      {error ? (
        <InlineNotice
          action={
            recovery?.kind === "retry" ? (
              <Button
                isLoading={pending === recovery.action}
                onClick={() => void run(recovery.action)}
                tone="secondary"
                icon="retry"
              >
                Повторить действие
              </Button>
            ) : recovery?.kind === "refresh" || conflict ? (
              <Button
                isLoading={pending === "refresh"}
                onClick={() => void refresh()}
                tone="secondary"
                icon="retry"
              >
                Обновить строку
              </Button>
            ) : undefined
          }
          ref={alertRef}
          role="alert"
          tabIndex={-1}
          title="Не удалось выполнить действие"
          tone="danger"
        >
          {error}
        </InlineNotice>
      ) : null}
    </section>
  );
}

function isDangerAction(action: LifecycleAction): boolean {
  return action === "mark_duplicate" || action === "ignore";
}

function actionTone(action: LifecycleAction): ButtonTone {
  if (action === "mark_unique") return "primary";
  if (isDangerAction(action)) return "dangerSecondary";
  return "secondary";
}

function actionLabel(
  action: LifecycleAction,
  status: ImportReviewDto["items"][number]["status"],
): string {
  if (action === "mark_unique") return "Это новая операция";
  if (action === "mark_duplicate") return "Отметить дублем";
  if (action === "ignore") return "Игнорировать";
  return status === "ignored" || status === "duplicate"
    ? "Восстановить на проверку"
    : "На проверку";
}

function confirmationCopy(action: LifecycleAction): string {
  return action === "mark_duplicate"
    ? "Пометить строку дублем? Она не попадёт в официальный ledger."
    : "Игнорировать строку? Она не попадёт в официальный ledger.";
}

function lifecycleSuccessMessage(
  action: LifecycleAction,
  previousStatus: ImportReviewDto["items"][number]["status"],
): string | null {
  if (action === "mark_duplicate") return "Строка отмечена дублем.";
  if (action === "ignore") return "Строка исключена из обработки.";
  if (
    action === "needs_review" &&
    (previousStatus === "ignored" || previousStatus === "duplicate")
  ) {
    return "Строка возвращена на проверку.";
  }
  return null;
}
