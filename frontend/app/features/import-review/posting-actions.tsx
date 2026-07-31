import { useEffect, useRef, useState } from "react";

import { Button } from "../../ui/button/button";
import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import { Field } from "../../ui/field/field";
import { FormActions } from "../../ui/field/form-layout";
import { Icon } from "../../ui/icon/icon";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import {
  loadImportReview,
  type ImportReviewDto,
} from "./api/import-review-api";
import {
  confirmImportReviewItem,
  type ImportReviewDraftEvaluationDto,
  type ImportReviewMutationResult,
  undoImportReviewPosting,
} from "./api/import-review-mutations";
import styles from "./import-review-editor.module.css";

type PostingActionProps = {
  categoryName?: string;
  csrfToken: string;
  documentId: string;
  item: ImportReviewDto["items"][number];
  onCancel?: () => void;
  onMenuDismiss?: () => void;
  onReviewReconciled: (review: ImportReviewDto) => void;
  onSuccess: (message: string) => void;
  propertyName?: string;
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
  onSuccess,
  propertyName = "Без объекта",
  variant = "panel",
}: PostingActionProps & {
  dirty: boolean;
  evaluation: ImportReviewDraftEvaluationDto;
  variant?: "panel" | "quick";
}) {
  const [rulePattern, setRulePattern] = useState("");
  const [rulePatternError, setRulePatternError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [canRetry, setCanRetry] = useState(false);
  const alertRef = useRef<HTMLDivElement>(null);
  const rulePatternRef = useRef<HTMLInputElement>(null);
  const idempotencyKey = useRef(crypto.randomUUID());
  const cleanedRulePattern = rulePattern.trim();
  const rememberRule = cleanedRulePattern.length > 0;
  const selectionFingerprint = `${evaluation.classification.operationType}:${evaluation.selection.categoryId}:${evaluation.selection.propertyId}:${cleanedRulePattern}`;

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
      <FormActions layout="split">
        <Button onClick={onCancel} tone="secondary">
          Отмена
        </Button>
      </FormActions>
    ) : null;
  }
  const confirmedOperationType = operationType;
  const confirmedCategoryId = categoryId;

  async function confirm() {
    setPending(true);
    setError(null);
    setRulePatternError(null);
    setConflict(false);
    setCanRetry(false);
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
      }
      onSuccess("Операция проведена.");
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
    setCanRetry(
      result.status !== "unauthenticated" && result.status !== "forbidden",
    );
  }

  async function refresh() {
    setRefreshing(true);
    setError(null);
    setCanRetry(false);
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
    setCanRetry(true);
  }

  if (variant === "quick") {
    return (
      <>
        <Button
          disabled={pending || refreshing}
          isLoading={pending}
          onClick={() => void confirm()}
          tone="primary"
          icon="check"
        >
          Подтвердить
        </Button>
        <PostingError error={error} ref={alertRef} />
      </>
    );
  }

  return (
    <section aria-label="Подтверждение операции" className={styles.postingBox}>
      <div className={styles.rulePatternField}>
        <Field
          error={rulePatternError ?? undefined}
          errorId={`rule-pattern-error-${item.id}`}
          htmlFor={`rule-pattern-${item.id}`}
          label={
            <span className={styles.rulePatternLabel}>
              <Icon name="automation" size={16} />
              Автоправило <small>· необязательно</small>
            </span>
          }
        >
          <input
            aria-describedby={
              rulePatternError ? `rule-pattern-error-${item.id}` : undefined
            }
            aria-invalid={rulePatternError ? true : undefined}
            autoComplete="off"
            disabled={pending}
            id={`rule-pattern-${item.id}`}
            maxLength={255}
            onChange={(event) => {
              setRulePattern(event.target.value);
              setRulePatternError(null);
              setError(null);
            }}
            placeholder="Фрагмент описания"
            ref={rulePatternRef}
            value={rulePattern}
          />
        </Field>
        {rememberRule ? (
          <p className={styles.rulePreview} aria-label="Итог правила">
            <strong>{cleanedRulePattern}</strong>
            <span aria-hidden="true">→</span>
            <span>
              {operationType === "income" ? "Доход" : "Расход"} · {categoryName}{" "}
              · {propertyName}
            </span>
          </p>
        ) : null}
      </div>
      <FormActions layout="split">
        {onCancel ? (
          <Button onClick={onCancel} tone="secondary">
            Отмена
          </Button>
        ) : null}
        <Button
          disabled={pending || refreshing}
          isLoading={pending}
          onClick={() => void confirm()}
          tone="primary"
          icon={rememberRule ? "automation" : "check"}
        >
          {rememberRule ? "Провести с правилом" : "Провести"}
        </Button>
      </FormActions>
      <PostingError
        action={
          conflict ? (
            <Button
              isLoading={refreshing}
              onClick={() => void refresh()}
              tone="secondary"
              icon="retry"
            >
              Обновить строку
            </Button>
          ) : canRetry ? (
            <Button
              disabled={pending || refreshing}
              icon="retry"
              onClick={() => void confirm()}
              tone="secondary"
            >
              Повторить
            </Button>
          ) : undefined
        }
        error={error}
        ref={alertRef}
      />
    </section>
  );
}

export function UndoPostingAction({
  csrfToken,
  documentId,
  item,
  onMenuDismiss,
  onReviewReconciled,
  onSuccess,
  readonly = false,
}: PostingActionProps) {
  const [confirming, setConfirming] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const alertRef = useRef<HTMLDivElement>(null);

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
    if (result.status === "success") {
      setConfirming(false);
      onMenuDismiss?.();
      const review = result.data.reviews.find(
        (candidate) => candidate.document.id === documentId,
      );
      if (review) {
        onReviewReconciled(review);
      }
      onSuccess("Проведение отменено. Строка возвращена на проверку.");
      return;
    }
    setError(postingError(result));
  }

  return (
    <>
      <Button
        icon="undo"
        onClick={() => {
          setError(null);
          setConfirming(true);
        }}
        tone="dangerSecondary"
      >
        Вернуть на проверку
      </Button>
      {confirming ? (
        <ConfirmationDialog
          confirmLabel="Вернуть на проверку"
          description="Проведение будет отменено. Строка снова появится среди операций, требующих решения."
          disabled={pending}
          onCancel={() => setConfirming(false)}
          onConfirm={() => void undo()}
          pending={pending}
          title="Вернуть операцию на проверку?"
        >
          <PostingError error={error} ref={alertRef} />
        </ConfirmationDialog>
      ) : (
        <PostingError error={error} ref={alertRef} />
      )}
    </>
  );
}

function PostingError({
  action,
  error,
  ref,
}: {
  action?: React.ReactNode;
  error: string | null;
  ref: React.Ref<HTMLDivElement>;
}) {
  if (!error) return null;
  return (
    <InlineNotice
      action={action}
      ref={ref}
      role="alert"
      tabIndex={-1}
      title="Не удалось изменить операцию"
      tone="danger"
    >
      {error}
    </InlineNotice>
  );
}

type ImportReviewMutationFailure = Exclude<
  ImportReviewMutationResult<unknown>,
  { status: "success" }
>;

function postingError(result: ImportReviewMutationFailure): string {
  if (result.status === "unauthenticated") {
    return "Сессия завершилась. Войдите снова; операция не показана как проведённая.";
  }
  if (result.status === "forbidden") {
    return "Недостаточно прав для проведения операции.";
  }
  return "message" in result ? result.message : "Операцию не удалось изменить.";
}
