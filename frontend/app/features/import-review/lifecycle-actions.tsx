import { useEffect, useRef, useState } from "react";

import { Button } from "../../ui/button/button";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import {
  loadImportReview,
  type ImportReviewDto,
} from "./api/import-review-api";
import { updateImportReviewLifecycle } from "./api/import-review-mutations";
import {
  isDangerAction,
  lifecycleActionLabel,
  lifecycleActionTone,
  lifecycleConfirmationCopy,
  lifecycleFailure,
  lifecycleRefreshFailure,
  lifecycleSuccessMessage,
  type LifecycleAction,
  type LifecycleRecovery,
} from "./lifecycle-action-model";
import styles from "./lifecycle-actions.module.css";
import { useImportReviewActionFeedback } from "./use-import-review-action-feedback";

type LifecycleActionsProps = {
  actions?: LifecycleAction[];
  csrfToken: string;
  documentId: string;
  item: ImportReviewDto["items"][number];
  onMenuDismiss?: () => void;
  onReviewReconciled: (review: ImportReviewDto) => void;
  onSuccess: (message: string) => void;
  readonly: boolean;
  toneOverride?: "secondary";
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
  toneOverride,
}: LifecycleActionsProps) {
  const [pending, setPending] = useState<LifecycleAction | "refresh" | null>(
    null,
  );
  const [confirmation, setConfirmation] = useState<LifecycleAction | null>(
    null,
  );
  const cancelConfirmationRef = useRef<HTMLButtonElement>(null);
  const { alertRef, clearFeedback, error, recovery, showFailure } =
    useImportReviewActionFeedback<LifecycleRecovery>();
  const visibleActions = actions ?? item.lifecycle.allowedActions;

  useEffect(() => {
    if (confirmation) cancelConfirmationRef.current?.focus();
  }, [confirmation]);

  async function run(action: LifecycleAction) {
    setPending(action);
    clearFeedback();
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
      const message = lifecycleSuccessMessage(action, item.status);
      if (message) onSuccess(message);
      return;
    }
    const failure = lifecycleFailure(result, action);
    showFailure(failure.message, failure.recovery);
  }

  async function refresh() {
    setPending("refresh");
    clearFeedback();
    const result = await loadImportReview(documentId);
    setPending(null);
    if (result.status === "success") {
      onMenuDismiss?.();
      onReviewReconciled(result.review);
      return;
    }
    showFailure(lifecycleRefreshFailure(result), { kind: "refresh" });
  }

  function requestAction(action: LifecycleAction) {
    clearFeedback();
    if (isDangerAction(action)) {
      setConfirmation(action);
      return;
    }
    void run(action);
  }

  function closeConfirmation() {
    setConfirmation(null);
    onMenuDismiss?.();
  }

  if (readonly || visibleActions.length === 0) return null;

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
            tone={toneOverride ?? lifecycleActionTone(action)}
          >
            {lifecycleActionLabel(action, item.status)}
          </Button>
        ))}
      </div>
      {confirmation ? (
        <div className={styles.lifecycleConfirmation} role="group">
          <p>{lifecycleConfirmationCopy(confirmation)}</p>
          <div>
            <Button
              disabled={pending !== null}
              onClick={closeConfirmation}
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
                icon="retry"
                isLoading={pending === recovery.action}
                onClick={() => void run(recovery.action)}
                tone="secondary"
              >
                Повторить действие
              </Button>
            ) : recovery?.kind === "refresh" ? (
              <Button
                icon="retry"
                isLoading={pending === "refresh"}
                onClick={() => void refresh()}
                tone="secondary"
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
