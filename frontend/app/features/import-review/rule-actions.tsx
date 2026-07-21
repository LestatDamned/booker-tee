import { useEffect, useRef, useState } from "react";

import { Button } from "../../ui/button/button";
import type { ImportReviewDto } from "./api/import-review-api";
import { applyRulesToImportReview } from "./api/import-review-mutations";
import styles from "./import-review.module.css";

type RuleActionsProps = {
  csrfToken: string;
  documentId: string;
  onReviewReconciled: (review: ImportReviewDto) => void;
  readonly: boolean;
};

export function RuleActions({
  csrfToken,
  documentId,
  onReviewReconciled,
  readonly,
}: RuleActionsProps) {
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const alertRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (error) alertRef.current?.focus();
  }, [error]);

  async function applyRules() {
    setPending(true);
    setMessage(null);
    setError(null);
    const result = await applyRulesToImportReview(documentId, csrfToken);
    setPending(false);
    if (result.status === "success") {
      onReviewReconciled(result.data.review);
      setMessage(ruleApplicationMessage(result.data));
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
      return;
    }
    if (
      result.status === "validation_error" ||
      result.status === "conflict" ||
      result.status === "error"
    ) {
      setError(result.message);
      return;
    }
    setError("Не удалось применить правила.");
  }

  return (
    <div className={styles.reviewTools}>
      <div className={styles.reviewToolLinks}>
        <a href={`/imports/documents/${documentId}`}>Открыть документ</a>
        <a href="/transaction-rules">Открыть правила</a>
      </div>
      {!readonly ? (
        <Button
          disabled={pending}
          isLoading={pending}
          onClick={() => void applyRules()}
          tone="secondary"
        >
          Применить правила
        </Button>
      ) : null}
      {message ? (
        <p aria-live="polite" className={styles.ruleApplicationStatus}>
          {message}
        </p>
      ) : null}
      {error ? (
        <p
          className={styles.draftError}
          ref={alertRef}
          role="alert"
          tabIndex={-1}
        >
          {error}
        </p>
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
