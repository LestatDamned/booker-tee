import { useEffect, useRef, useState } from "react";

import { Button } from "../../ui/button/button";
import { Icon } from "../../ui/icon/icon";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import type { ImportReviewDto } from "./api/import-review-api";
import { applyRulesToImportReview } from "./api/import-review-mutations";
import styles from "./import-review-page.module.css";

type RuleActionsProps = {
  csrfToken: string;
  documentId: string;
  onReviewReconciled: (review: ImportReviewDto) => void;
  onSuccess: (message: string) => void;
  readonly: boolean;
};

export function RuleActions({
  csrfToken,
  documentId,
  onReviewReconciled,
  onSuccess,
  readonly,
}: RuleActionsProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [canRetry, setCanRetry] = useState(false);
  const alertRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (error) alertRef.current?.focus();
  }, [error]);

  async function applyRules() {
    setPending(true);
    setError(null);
    setCanRetry(false);
    const result = await applyRulesToImportReview(documentId, csrfToken);
    setPending(false);
    if (result.status === "success") {
      onReviewReconciled(result.data.review);
      onSuccess(ruleApplicationMessage(result.data));
      return;
    }
    if (result.status === "unauthenticated") {
      window.location.assign(
        `/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`,
      );
      return;
    }
    if (result.status === "forbidden") {
      setError("Недостаточно прав для применения правил.");
      setCanRetry(false);
      return;
    }
    if (
      result.status === "validation_error" ||
      result.status === "conflict" ||
      result.status === "error"
    ) {
      setError(result.message);
      setCanRetry(true);
      return;
    }
    setError("Не удалось применить правила.");
    setCanRetry(true);
  }

  return (
    <div className={styles.reviewTools}>
      <div className={styles.reviewToolLinks}>
        <a href={`/app/imports/documents/${documentId}`}>
          <Icon name="source" size={16} />
          Открыть документ
        </a>
        <a href="/transaction-rules">
          <Icon name="rules" size={16} />
          Открыть правила
        </a>
      </div>
      {!readonly ? (
        <Button
          disabled={pending}
          isLoading={pending}
          onClick={() => void applyRules()}
          tone="secondary"
          icon="filterApply"
        >
          Применить правила
        </Button>
      ) : null}
      {error ? (
        <InlineNotice
          action={
            canRetry ? (
              <Button
                disabled={pending}
                icon="retry"
                onClick={() => void applyRules()}
                tone="secondary"
              >
                Повторить
              </Button>
            ) : undefined
          }
          className={styles.ruleApplicationFeedback}
          ref={alertRef}
          role="alert"
          tabIndex={-1}
          title="Не удалось применить правила"
          tone="danger"
        >
          {error}
        </InlineNotice>
      ) : null}
    </div>
  );
}

function ruleApplicationMessage({
  checkedCount,
  suggestedCount,
}: {
  checkedCount: number;
  suggestedCount: number;
}) {
  if (checkedCount === 0)
    return "Нет строк, к которым можно применить правила.";
  return `Проверено строк: ${checkedCount}. Предложений применено: ${suggestedCount}.`;
}
