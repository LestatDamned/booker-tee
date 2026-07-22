import { useEffect, useRef, useState } from "react";

import { Button } from "../../ui/button/button";
import {
  loadImportReview,
  type ImportReviewDto,
} from "./api/import-review-api";
import {
  confirmImportReviewItem,
  type ImportReviewDraftEvaluationDto,
  undoImportReviewPosting,
} from "./api/import-review-mutations";
import styles from "./import-review.module.css";

type PostingActionProps = {
  csrfToken: string;
  documentId: string;
  item: ImportReviewDto["items"][number];
  onReviewReconciled: (review: ImportReviewDto) => void;
  readonly?: boolean;
};

export function ConfirmPostingAction({
  csrfToken,
  dirty,
  documentId,
  evaluation,
  item,
  onReviewReconciled,
  variant = "panel",
}: PostingActionProps & {
  dirty: boolean;
  evaluation: ImportReviewDraftEvaluationDto;
  variant?: "panel" | "quick";
}) {
  const [rememberRule, setRememberRule] = useState(false);
  const [rulePattern, setRulePattern] = useState("");
  const [pending, setPending] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const alertRef = useRef<HTMLParagraphElement>(null);
  const rulePatternRef = useRef<HTMLInputElement>(null);
  const idempotencyKey = useRef(crypto.randomUUID());
  const selectionFingerprint = `${evaluation.classification.operationType}:${evaluation.selection.categoryId}:${evaluation.selection.propertyId}:${rememberRule}:${rulePattern}`;

  useEffect(() => {
    idempotencyKey.current = crypto.randomUUID();
  }, [selectionFingerprint]);

  useEffect(() => {
    if (error) alertRef.current?.focus();
  }, [error]);

  const operationType = evaluation.classification.operationType;
  const categoryId = evaluation.selection.categoryId;
  if (
    dirty ||
    !evaluation.confirmability.canConfirm ||
    (operationType !== "income" && operationType !== "expense") ||
    categoryId === null
  ) {
    return null;
  }
  const confirmedOperationType = operationType;
  const confirmedCategoryId = categoryId;

  async function confirm() {
    const cleanedRulePattern = rulePattern.trim();
    if (rememberRule && !cleanedRulePattern) {
      setError("Укажите текст, по которому определять похожие строки.");
      queueMicrotask(() => rulePatternRef.current?.focus());
      return;
    }
    setPending(true);
    setError(null);
    setConflict(false);
    const result = await confirmImportReviewItem(
      documentId,
      item.id,
      {
        operationType: confirmedOperationType,
        categoryId: confirmedCategoryId,
        propertyId: evaluation.selection.propertyId,
        expectedStatus: item.status,
        rememberRule,
        rulePattern: rememberRule ? cleanedRulePattern : null,
      },
      csrfToken,
      idempotencyKey.current,
    );
    setPending(false);
    if (result.status === "success") {
      const review = result.data.reviews.find(
        (candidate) => candidate.document.id === documentId,
      );
      if (review) {
        onReviewReconciled(review);
        focusNextReviewItem(review);
      }
      return;
    }
    if (result.status === "conflict") setConflict(true);
    setError(postingError(result));
  }

  async function refresh() {
    setRefreshing(true);
    setError(null);
    const result = await loadImportReview(documentId);
    setRefreshing(false);
    if (result.status === "success") {
      setConflict(false);
      onReviewReconciled(result.review);
      return;
    }
    setError(
      result.status === "error"
        ? result.message
        : "Не удалось обновить import review.",
    );
  }

  if (variant === "quick") {
    return (
      <>
        <Button
          disabled={pending || refreshing}
          isLoading={pending}
          onClick={() => void confirm()}
          tone="primary"
        >
          Подтвердить
        </Button>
        <PostingError error={error} ref={alertRef} />
      </>
    );
  }

  return (
    <section aria-label="Подтверждение операции" className={styles.postingBox}>
      <label className={styles.rememberRule}>
        <input
          checked={rememberRule}
          disabled={pending}
          onChange={(event) => setRememberRule(event.target.checked)}
          type="checkbox"
        />
        Создать правило для похожих строк
      </label>
      {rememberRule ? (
        <div className={styles.rulePatternField}>
          <label>
            Текст для определения <span aria-hidden="true">*</span>
            <input
              aria-describedby={`rule-pattern-help-${item.id}`}
              disabled={pending}
              onChange={(event) => setRulePattern(event.target.value)}
              placeholder="Например, КРАСНОЕ&БЕЛОЕ"
              ref={rulePatternRef}
              required
              value={rulePattern}
            />
          </label>
          <p
            className={styles.rulePatternHelp}
            id={`rule-pattern-help-${item.id}`}
          >
            Введите устойчивый фрагмент самостоятельно. Описание из выписки: «
            {item.normalized.description ??
              item.raw.description ??
              "без описания"}
            ».
          </p>
        </div>
      ) : null}
      <Button
        disabled={pending || refreshing}
        isLoading={pending}
        onClick={() => void confirm()}
        tone="primary"
      >
        Подтвердить и провести
      </Button>
      <PostingError error={error} ref={alertRef} />
      {conflict ? (
        <Button
          isLoading={refreshing}
          onClick={() => void refresh()}
          tone="secondary"
        >
          Обновить строку
        </Button>
      ) : null}
    </section>
  );
}

export function UndoPostingAction({
  csrfToken,
  documentId,
  item,
  onReviewReconciled,
  readonly = false,
}: PostingActionProps) {
  const [confirming, setConfirming] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const alertRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (confirming) cancelRef.current?.focus();
  }, [confirming]);
  useEffect(() => {
    if (error) alertRef.current?.focus();
  }, [error]);

  if (readonly || !item.posting.canUndo || item.posting.operationId === null) {
    return null;
  }

  async function undo() {
    if (item.posting.operationId === null) return;
    setPending(true);
    setError(null);
    const result = await undoImportReviewPosting(
      documentId,
      item.id,
      { expectedOperationId: item.posting.operationId },
      csrfToken,
    );
    setPending(false);
    setConfirming(false);
    if (result.status === "success") {
      const review = result.data.reviews.find(
        (candidate) => candidate.document.id === documentId,
      );
      if (review) onReviewReconciled(review);
      return;
    }
    setError(postingError(result));
  }

  return (
    <section
      aria-label="Проведённая операция"
      className={`${styles.postingBox} ${styles.undoPostingBox}`}
    >
      <p>Операция уже проведена в ledger.</p>
      {confirming ? (
        <div className={styles.lifecycleConfirmation} role="group">
          <p>Отменить проведение и вернуть строку в очередь проверки?</p>
          <div>
            <Button onClick={() => setConfirming(false)} ref={cancelRef}>
              Оставить проведённой
            </Button>
            <Button
              isLoading={pending}
              onClick={() => void undo()}
              tone="danger"
            >
              Отменить проведение
            </Button>
          </div>
        </div>
      ) : (
        <Button onClick={() => setConfirming(true)} tone="dangerSecondary">
          Отменить проведение
        </Button>
      )}
      <PostingError error={error} ref={alertRef} />
    </section>
  );
}

function PostingError({
  error,
  ref,
}: {
  error: string | null;
  ref: React.Ref<HTMLParagraphElement>;
}) {
  if (!error) return null;
  return (
    <p className={styles.draftError} ref={ref} role="alert" tabIndex={-1}>
      {error}
    </p>
  );
}

function postingError(result: { status: string; message?: string }): string {
  if (result.status === "unauthenticated") {
    return "Сессия завершилась. Войдите снова; операция не показана как проведённая.";
  }
  if (result.status === "forbidden") {
    return "Недостаточно прав для проведения операции.";
  }
  return result.message ?? "Операцию не удалось изменить.";
}

function focusNextReviewItem(review: ImportReviewDto) {
  if (!review.queue.firstRemainingItemId) return;
  window.setTimeout(() => {
    document
      .getElementById(`raw-${review.queue.firstRemainingItemId}`)
      ?.focus();
  });
}
