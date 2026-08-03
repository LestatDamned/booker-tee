import { useState } from "react";
import { Link } from "react-router";

import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import { Button } from "../../ui/button/button";
import { Icon } from "../../ui/icon/icon";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import type { ImportReviewDto } from "./api/import-review-api";
import { applyRulesToImportReview } from "./api/import-review-mutations";
import {
  ruleApplicationFailure,
  ruleApplicationMessage,
} from "./rule-application-model";
import styles from "./rule-actions.module.css";
import { useImportReviewActionFeedback } from "./use-import-review-action-feedback";

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
  const { alertRef, clearFeedback, error, recovery, showFailure } =
    useImportReviewActionFeedback<"retry">();

  async function applyRules() {
    setPending(true);
    clearFeedback();
    const result = await applyRulesToImportReview(documentId, csrfToken);
    setPending(false);
    if (result.status === "success") {
      onReviewReconciled(result.data.review);
      onSuccess(ruleApplicationMessage(result.data));
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    const failure = ruleApplicationFailure(result);
    showFailure(failure.message, failure.canRetry ? "retry" : null);
  }

  return (
    <div className={styles.reviewTools}>
      <div className={styles.reviewToolLinks}>
        <a href={`/app/imports/documents/${documentId}`}>
          <Icon name="source" size={16} />
          Открыть документ
        </a>
        <Link to="/rules">
          <Icon name="rules" size={16} />
          Открыть правила
        </Link>
      </div>
      {!readonly ? (
        <Button
          disabled={pending}
          icon="filterApply"
          isLoading={pending}
          onClick={() => void applyRules()}
          tone="secondary"
        >
          Применить правила
        </Button>
      ) : null}
      {error ? (
        <InlineNotice
          action={
            recovery === "retry" ? (
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
