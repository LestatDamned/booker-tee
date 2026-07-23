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
import { focusNextReviewItem } from "./focus-next-review-item";
import styles from "./import-review.module.css";

type PostingActionProps = {
  categoryName?: string;
  csrfToken: string;
  documentId: string;
  item: ImportReviewDto["items"][number];
  onCancel?: () => void;
  onMenuDismiss?: () => void;
  onReviewReconciled: (review: ImportReviewDto) => void;
  readonly?: boolean;
};

export function ConfirmPostingAction({
  categoryName = "Выбранная категория",
  csrfToken,
  dirty,
  documentId,
  evaluation,
  item,
  onCancel,
  onMenuDismiss,
  onReviewReconciled,
  variant = "panel",
}: PostingActionProps & {
  dirty: boolean;
  evaluation: ImportReviewDraftEvaluationDto;
  variant?: "panel" | "quick";
}) {
  const [rememberRule, setRememberRule] = useState(false);
  const [rulePattern, setRulePattern] = useState("");
  const [rulePatternError, setRulePatternError] = useState<string | null>(null);
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
    return variant === "panel" && onCancel ? (
      <div className={styles.editorActions}>
        <Button onClick={onCancel}>Отмена</Button>
      </div>
    ) : null;
  }
  const confirmedOperationType = operationType;
  const confirmedCategoryId = categoryId;

  async function confirm() {
    const cleanedRulePattern = rulePattern.trim();
    if (rememberRule && !cleanedRulePattern) {
      setRulePatternError(
        "Вставьте фрагмент описания, по которому применять правило.",
      );
      setError(null);
      queueMicrotask(() => rulePatternRef.current?.focus());
      return;
    }
    setPending(true);
    setError(null);
    setRulePatternError(null);
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
      onMenuDismiss?.();
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
    if (
      result.status === "validation_error" &&
      result.fieldErrors.rulePattern?.length
    ) {
      setRulePatternError(result.fieldErrors.rulePattern.join(" "));
      queueMicrotask(() => rulePatternRef.current?.focus());
      return;
    }
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
      <div className={styles.editorActions}>
        <Button
          disabled={pending || refreshing}
          isLoading={pending}
          onClick={() => void confirm()}
          tone="primary"
        >
          Подтвердить и провести
        </Button>
        {onCancel ? <Button onClick={onCancel}>Отмена</Button> : null}
      </div>
      <details className={styles.ruleDisclosure}>
        <summary>Правило для похожих операций</summary>
        <div className={styles.ruleDisclosureBody}>
          <label className={styles.rememberRule}>
            <input
              checked={rememberRule}
              disabled={pending}
              onChange={(event) => {
                setRememberRule(event.target.checked);
                setRulePatternError(null);
                setError(null);
              }}
              type="checkbox"
            />
            Применять это решение к похожим строкам
          </label>
          {rememberRule ? (
            <div className={styles.rulePatternField}>
              <div className={styles.ruleSourceDescription}>
                <span>Исходное описание</span>
                <p>
                  {item.raw.description ??
                    item.normalized.description ??
                    "Без описания"}
                </p>
              </div>
              <div className={styles.ruleDefinition}>
                <label>
                  <span className={styles.rulePatternLabel}>
                    Фрагмент описания <span aria-hidden="true">*</span>
                  </span>
                  <input
                    aria-describedby={`${`rule-pattern-help-${item.id}`} ${
                      rulePatternError ? `rule-pattern-error-${item.id}` : ""
                    }`.trim()}
                    aria-invalid={rulePatternError ? true : undefined}
                    autoComplete="off"
                    disabled={pending}
                    maxLength={255}
                    onChange={(event) => {
                      setRulePattern(event.target.value);
                      setRulePatternError(null);
                      setError(null);
                    }}
                    placeholder="Например, KRASNOE&BELOE"
                    ref={rulePatternRef}
                    required
                    value={rulePattern}
                  />
                </label>
                <p
                  className={styles.rulePatternHelp}
                  id={`rule-pattern-help-${item.id}`}
                >
                  Скопируйте устойчивую часть без даты, суммы и реквизитов.
                </p>
                {rulePatternError ? (
                  <p
                    className={styles.fieldError}
                    id={`rule-pattern-error-${item.id}`}
                    role="alert"
                  >
                    {rulePatternError}
                  </p>
                ) : null}
                <div className={styles.rulePreview} aria-label="Итог правила">
                  <span>Правило:</span>
                  <strong>
                    Если описание содержит «{rulePattern.trim() || "…"}» →
                    категория «{categoryName}»
                  </strong>
                  <small>
                    Только предложит категорию — без автопроведения.
                  </small>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </details>
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
  onMenuDismiss,
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
      onMenuDismiss?.();
      const review = result.data.reviews.find(
        (candidate) => candidate.document.id === documentId,
      );
      if (review) {
        onReviewReconciled(review);
        focusNextReviewItem(review);
      }
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
            <Button
              onClick={() => {
                setConfirming(false);
                onMenuDismiss?.();
              }}
              ref={cancelRef}
            >
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
