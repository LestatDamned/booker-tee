import { useEffect, useRef, useState, type ReactNode, type Ref } from "react";

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
  undoImportReviewPosting,
  type ImportReviewDraftEvaluationDto,
} from "./api/import-review-mutations";
import styles from "./posting-actions.module.css";
import {
  buildPostingConfirmationRequest,
  confirmedPostingSelection,
  normalizedRulePattern,
  postingError,
  postingSelectionFingerprint,
} from "./posting-model";
import { reviewForDocument } from "./review-reconciliation";

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
  const selection = confirmedPostingSelection(dirty, evaluation);
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
  const { cleanedRulePattern, rememberRule } =
    normalizedRulePattern(rulePattern);
  const selectionFingerprint = postingSelectionFingerprint(
    selection,
    rulePattern,
  );

  useEffect(() => {
    idempotencyKey.current = crypto.randomUUID();
  }, [selectionFingerprint]);

  useEffect(() => {
    if (error) alertRef.current?.focus();
  }, [error]);

  useEffect(() => {
    if (rulePatternError) rulePatternRef.current?.focus();
  }, [rulePatternError]);

  function changeRulePattern(value: string) {
    setRulePattern(value);
    setRulePatternError(null);
    setError(null);
  }

  async function confirm() {
    if (selection === null) return;
    setPending(true);
    setError(null);
    setRulePatternError(null);
    setConflict(false);
    setCanRetry(false);
    const result = await confirmImportReviewItem(
      documentId,
      item.id,
      buildPostingConfirmationRequest(selection, item.status, rulePattern),
      csrfToken,
      idempotencyKey.current,
    );
    setPending(false);
    if (result.status === "success") {
      onMenuDismiss?.();
      const review = reviewForDocument(result.data.reviews, documentId);
      if (review) onReviewReconciled(review);
      onSuccess("Операция проведена.");
      return;
    }
    if (result.status === "conflict") setConflict(true);
    if (
      result.status === "validation_error" &&
      result.fieldErrors.rulePattern?.length
    ) {
      setRulePatternError(result.fieldErrors.rulePattern.join(" "));
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

  if (selection === null) {
    return variant === "panel" && onCancel ? (
      <FormActions layout="split">
        <Button onClick={onCancel} tone="secondary">
          Отмена
        </Button>
      </FormActions>
    ) : null;
  }

  if (variant === "quick") {
    return (
      <>
        <Button
          disabled={pending || refreshing}
          icon="check"
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
      <PostingRuleField
        categoryName={categoryName}
        cleanedRulePattern={cleanedRulePattern}
        error={rulePatternError}
        inputRef={rulePatternRef}
        itemId={item.id}
        onChange={changeRulePattern}
        operationType={selection.operationType}
        pending={pending}
        propertyName={propertyName}
        rememberRule={rememberRule}
        rulePattern={rulePattern}
      />
      <FormActions layout="split">
        {onCancel ? (
          <Button onClick={onCancel} tone="secondary">
            Отмена
          </Button>
        ) : null}
        <Button
          disabled={pending || refreshing}
          icon={rememberRule ? "automation" : "check"}
          isLoading={pending}
          onClick={() => void confirm()}
          tone="primary"
        >
          {rememberRule ? "Провести с правилом" : "Провести"}
        </Button>
      </FormActions>
      <PostingError
        action={
          conflict ? (
            <Button
              icon="retry"
              isLoading={refreshing}
              onClick={() => void refresh()}
              tone="secondary"
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

  function openConfirmation() {
    setError(null);
    setConfirming(true);
  }

  async function undo() {
    const operationId = item.posting.operationId;
    if (operationId === null) return;
    setPending(true);
    setError(null);
    const result = await undoImportReviewPosting(
      documentId,
      item.id,
      { expectedOperationId: operationId },
      csrfToken,
    );
    setPending(false);
    if (result.status === "success") {
      setConfirming(false);
      onMenuDismiss?.();
      const review = reviewForDocument(result.data.reviews, documentId);
      if (review) onReviewReconciled(review);
      onSuccess("Проведение отменено. Строка возвращена на проверку.");
      return;
    }
    setError(postingError(result));
  }

  if (readonly || !item.posting.canUndo || item.posting.operationId === null) {
    return null;
  }

  return (
    <>
      <Button icon="undo" onClick={openConfirmation} tone="dangerSecondary">
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

type PostingRuleFieldProps = {
  categoryName: string;
  cleanedRulePattern: string;
  error: string | null;
  inputRef: Ref<HTMLInputElement>;
  itemId: string;
  onChange: (value: string) => void;
  operationType: "income" | "expense";
  pending: boolean;
  propertyName: string;
  rememberRule: boolean;
  rulePattern: string;
};

function PostingRuleField({
  categoryName,
  cleanedRulePattern,
  error,
  inputRef,
  itemId,
  onChange,
  operationType,
  pending,
  propertyName,
  rememberRule,
  rulePattern,
}: PostingRuleFieldProps) {
  return (
    <div className={styles.rulePatternField}>
      <Field
        error={error ?? undefined}
        errorId={`rule-pattern-error-${itemId}`}
        htmlFor={`rule-pattern-${itemId}`}
        label={
          <span className={styles.rulePatternLabel}>
            <Icon name="automation" size={16} />
            Автоправило <small>· необязательно</small>
          </span>
        }
      >
        <input
          aria-describedby={error ? `rule-pattern-error-${itemId}` : undefined}
          aria-invalid={error ? true : undefined}
          autoComplete="off"
          disabled={pending}
          id={`rule-pattern-${itemId}`}
          maxLength={255}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Фрагмент описания"
          ref={inputRef}
          value={rulePattern}
        />
      </Field>
      {rememberRule ? (
        <p className={styles.rulePreview} aria-label="Итог правила">
          <strong>{cleanedRulePattern}</strong>
          <span aria-hidden="true">→</span>
          <span>
            {operationType === "income" ? "Доход" : "Расход"} · {categoryName} ·{" "}
            {propertyName}
          </span>
        </p>
      ) : null}
    </div>
  );
}

function PostingError({
  action,
  error,
  ref,
}: {
  action?: ReactNode;
  error: string | null;
  ref: Ref<HTMLDivElement>;
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
