import { type FormEvent, type RefObject, useRef, useState } from "react";

import { Button } from "../../ui/button/button";
import type { ImportReviewDto } from "./api/import-review-api";
import {
  createImportReviewCategory,
  evaluateImportReviewDraft,
  type ImportReviewCategoryReferenceDto,
  type ImportReviewDraftEvaluationDto,
  type ImportReviewDraftEvaluationRequest,
} from "./api/import-review-mutations";
import styles from "./import-review.module.css";
import { ConfirmPostingAction } from "./posting-actions";
import { TransferPanel } from "./transfer-panel";

type ReviewMode = "ordinary" | "transfer";

type ClassificationPanelProps = {
  categories: ImportReviewDto["references"]["categories"];
  csrfToken: string;
  documentId: string;
  item: ImportReviewDto["items"][number];
  onCancel: () => void;
  onCategoryCreated: (category: ImportReviewCategoryReferenceDto) => void;
  onReviewReconciled: (review: ImportReviewDto) => void;
  properties: ImportReviewDto["references"]["properties"];
  readonly: boolean;
};

export function ClassificationPanel({
  categories,
  csrfToken,
  documentId,
  item,
  onCancel,
  onCategoryCreated,
  onReviewReconciled,
  properties,
  readonly,
}: ClassificationPanelProps) {
  const [draft, setDraft] = useState<ImportReviewDraftEvaluationRequest>({
    operationType: ordinaryOperationType(item),
    categoryId: item.selection.categoryId,
    propertyId: item.selection.propertyId,
  });
  const [evaluation, setEvaluation] = useState<ImportReviewDraftEvaluationDto>({
    itemId: item.id,
    classification: item.classification,
    selection: item.selection,
    confirmability: item.confirmability,
    ruleSuggestion: item.ruleSuggestion,
  });
  const [dirty, setDirty] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [categoryEditorOpen, setCategoryEditorOpen] = useState(false);
  const [editorResetVersion, setEditorResetVersion] = useState(0);
  const [mode, setMode] = useState<ReviewMode>(
    item.classification.operationType === "transfer" ? "transfer" : "ordinary",
  );
  const [transferSelection, setTransferSelection] = useState("");
  const [categoryName, setCategoryName] = useState("");
  const [categoryKind, setCategoryKind] = useState<
    ImportReviewCategoryReferenceDto["kind"]
  >(defaultCategoryKind(item.classification.operationType));
  const categoryRef = useRef<HTMLSelectElement>(null);
  const propertyRef = useRef<HTMLSelectElement>(null);
  const categoryNameRef = useRef<HTMLInputElement>(null);
  const evaluationRequestId = useRef(0);
  const categoryRequestId = useRef(0);

  function updateDraft(next: ImportReviewDraftEvaluationRequest) {
    setDraft(next);
    setDirty(true);
    setError(null);
    setFieldErrors({});
    void runEvaluation(next);
  }

  async function runEvaluation(nextDraft = draft) {
    const requestId = ++evaluationRequestId.current;
    setPending(true);
    setError(null);
    setFieldErrors({});
    const result = await evaluateImportReviewDraft(
      documentId,
      item.id,
      nextDraft,
      csrfToken,
    );
    if (requestId !== evaluationRequestId.current) return;
    setPending(false);
    if (result.status === "success") {
      setEvaluation(result.data);
      setDirty(false);
    } else if (result.status === "validation_error") {
      setError(result.message);
      setFieldErrors(result.fieldErrors);
      focusDraftField(
        result.fieldErrors,
        categoryRef.current,
        propertyRef.current,
      );
    } else {
      setError(draftMutationError(result));
    }
  }

  async function handleCreateCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const requestId = ++categoryRequestId.current;
    setPending(true);
    setError(null);
    setFieldErrors({});
    const result = await createImportReviewCategory(
      documentId,
      item.id,
      { name: categoryName, kind: categoryKind },
      csrfToken,
    );
    if (requestId !== categoryRequestId.current) return;
    setPending(false);
    if (result.status === "success") {
      onCategoryCreated(result.data);
      const nextDraft = { ...draft, categoryId: result.data.id };
      setDraft(nextDraft);
      setCategoryName("");
      setCategoryEditorOpen(false);
      await runEvaluation(nextDraft);
    } else if (result.status === "validation_error") {
      setError(result.message);
      setFieldErrors(result.fieldErrors);
      categoryNameRef.current?.focus();
    } else {
      setError(categoryMutationError(result));
    }
  }

  function changeMode(nextMode: ReviewMode) {
    setMode(nextMode);
    setError(null);
    setFieldErrors({});
    if (nextMode === "ordinary") {
      void runEvaluation(draft);
    } else {
      setCategoryEditorOpen(false);
    }
  }

  function cancelChanges() {
    evaluationRequestId.current += 1;
    categoryRequestId.current += 1;
    setDraft(serverDraft(item));
    setEvaluation(serverEvaluation(item));
    setDirty(false);
    setPending(false);
    setError(null);
    setFieldErrors({});
    setCategoryEditorOpen(false);
    setCategoryName("");
    setCategoryKind(defaultCategoryKind(item.classification.operationType));
    setMode(
      item.classification.operationType === "transfer"
        ? "transfer"
        : "ordinary",
    );
    setTransferSelection("");
    setEditorResetVersion((version) => version + 1);
    onCancel();
  }

  return (
    <div className={styles.classificationPanelBody}>
      {readonly ? (
        <p>Изменение classification недоступно для вашей роли.</p>
      ) : (
        <>
          <OperationModeSwitch item={item} mode={mode} onChange={changeMode} />
          {mode === "transfer" ? (
            <TransferPanel
              key={editorResetVersion}
              csrfToken={csrfToken}
              documentId={documentId}
              item={item}
              onCancel={cancelChanges}
              onReviewReconciled={onReviewReconciled}
              onSelectionChange={setTransferSelection}
              selection={transferSelection}
            />
          ) : (
            <>
              <DraftFields
                categories={categories}
                categoryRef={categoryRef}
                draft={draft}
                fieldErrors={fieldErrors}
                itemId={item.id}
                onCreateCategory={() => setCategoryEditorOpen((open) => !open)}
                categoryEditorOpen={categoryEditorOpen}
                pending={pending}
                properties={properties}
                propertyRef={propertyRef}
                updateDraft={updateDraft}
              />
              {categoryEditorOpen ? (
                <CategoryEditor
                  categoryKind={categoryKind}
                  categoryName={categoryName}
                  categoryNameRef={categoryNameRef}
                  fieldErrors={fieldErrors}
                  itemId={item.id}
                  onKindChange={setCategoryKind}
                  onNameChange={setCategoryName}
                  onSubmit={handleCreateCategory}
                  pending={pending}
                />
              ) : null}
            </>
          )}
        </>
      )}
      {error ? (
        <div className={styles.errorRecovery}>
          <p className={styles.draftError} role="alert">
            {error}
          </p>
          {Object.keys(fieldErrors).length === 0 && mode === "ordinary" ? (
            <Button
              disabled={pending}
              onClick={() => void runEvaluation(draft)}
              tone="secondary"
            >
              Повторить проверку
            </Button>
          ) : null}
        </div>
      ) : null}
      {mode === "ordinary" ? (
        <section
          aria-label="Решение по операции"
          className={styles.reviewDecisionSummary}
        >
          <OrdinaryOutcome
            categories={categories}
            dirty={dirty}
            evaluation={evaluation}
            pending={pending}
            properties={properties}
          />
          <DraftCapability
            dirty={dirty}
            evaluation={evaluation}
            pending={pending}
          />
          {!readonly ? (
            <ConfirmPostingAction
              categoryName={
                categories.find(
                  (category) => category.id === evaluation.selection.categoryId,
                )?.name ?? "Выбранная категория"
              }
              csrfToken={csrfToken}
              dirty={dirty}
              documentId={documentId}
              evaluation={evaluation}
              item={item}
              key={editorResetVersion}
              onCancel={cancelChanges}
              onReviewReconciled={onReviewReconciled}
            />
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

function OperationModeSwitch({
  item,
  mode,
  onChange,
}: {
  item: ClassificationPanelProps["item"];
  mode: ReviewMode;
  onChange: (mode: ReviewMode) => void;
}) {
  return (
    <fieldset className={styles.operationModeSwitch}>
      <legend>Финансовый смысл</legend>
      <div>
        <label data-tone={item.transfer.ordinaryOperationType ?? "neutral"}>
          <input
            checked={mode === "ordinary"}
            name={`operation-mode-${item.id}`}
            onChange={() => onChange("ordinary")}
            type="radio"
          />
          <span>{ordinaryOperationLabel(item)}</span>
        </label>
        <label data-tone="transfer">
          <input
            checked={mode === "transfer"}
            name={`operation-mode-${item.id}`}
            onChange={() => onChange("transfer")}
            type="radio"
          />
          <span>Перевод</span>
        </label>
      </div>
    </fieldset>
  );
}

type DraftFieldsProps = {
  categories: ClassificationPanelProps["categories"];
  categoryEditorOpen: boolean;
  categoryRef: RefObject<HTMLSelectElement | null>;
  draft: ImportReviewDraftEvaluationRequest;
  fieldErrors: Record<string, string[]>;
  itemId: string;
  onCreateCategory: () => void;
  pending: boolean;
  properties: ClassificationPanelProps["properties"];
  propertyRef: RefObject<HTMLSelectElement | null>;
  updateDraft: (draft: ImportReviewDraftEvaluationRequest) => void;
};

function DraftFields({
  categories,
  categoryEditorOpen,
  categoryRef,
  draft,
  fieldErrors,
  itemId,
  onCreateCategory,
  pending,
  properties,
  propertyRef,
  updateDraft,
}: DraftFieldsProps) {
  const compatibleCategories = categories.filter(
    (category) =>
      draft.operationType === null ||
      category.kind === "mixed" ||
      category.kind === draft.operationType,
  );

  return (
    <div className={styles.draftFields}>
      <div className={styles.editorField}>
        <div className={styles.editorFieldHeader}>
          <label htmlFor={`category-${itemId}`}>Категория</label>
          <Button
            aria-controls={`category-editor-${itemId}`}
            aria-expanded={categoryEditorOpen}
            className={styles.editorFieldAction ?? ""}
            disabled={pending}
            onClick={onCreateCategory}
            tone="ghost"
          >
            Создать категорию
          </Button>
        </div>
        <select
          aria-describedby={
            fieldErrors.categoryId ? `category-error-${itemId}` : undefined
          }
          id={`category-${itemId}`}
          onChange={(event) =>
            updateDraft({ ...draft, categoryId: event.target.value || null })
          }
          ref={categoryRef}
          value={draft.categoryId ?? ""}
        >
          <option value="">Выберите категорию</option>
          {compatibleCategories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </select>
        <FieldError
          errors={fieldErrors.categoryId}
          id={`category-error-${itemId}`}
        />
      </div>
      <div className={styles.editorField}>
        <label htmlFor={`property-${itemId}`}>Объект</label>
        <select
          aria-describedby={
            fieldErrors.propertyId ? `property-error-${itemId}` : undefined
          }
          id={`property-${itemId}`}
          onChange={(event) =>
            updateDraft({ ...draft, propertyId: event.target.value || null })
          }
          ref={propertyRef}
          value={draft.propertyId ?? ""}
        >
          <option value="">Без объекта</option>
          {properties.map((property) => (
            <option key={property.id} value={property.id}>
              {property.name}
            </option>
          ))}
        </select>
        <FieldError
          errors={fieldErrors.propertyId}
          id={`property-error-${itemId}`}
        />
      </div>
    </div>
  );
}

type CategoryEditorProps = {
  categoryKind: ImportReviewCategoryReferenceDto["kind"];
  categoryName: string;
  categoryNameRef: RefObject<HTMLInputElement | null>;
  fieldErrors: Record<string, string[]>;
  itemId: string;
  onKindChange: (kind: ImportReviewCategoryReferenceDto["kind"]) => void;
  onNameChange: (name: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  pending: boolean;
};

function CategoryEditor({
  categoryKind,
  categoryName,
  categoryNameRef,
  fieldErrors,
  itemId,
  onKindChange,
  onNameChange,
  onSubmit,
  pending,
}: CategoryEditorProps) {
  return (
    <form
      className={styles.categoryEditor}
      id={`category-editor-${itemId}`}
      onSubmit={onSubmit}
    >
      <label>
        Название категории
        <input
          aria-describedby={
            fieldErrors.name ? `category-name-error-${itemId}` : undefined
          }
          onChange={(event) => onNameChange(event.target.value)}
          ref={categoryNameRef}
          value={categoryName}
        />
        <FieldError
          errors={fieldErrors.name}
          id={`category-name-error-${itemId}`}
        />
      </label>
      <label>
        Вид категории
        <select
          onChange={(event) =>
            onKindChange(
              event.target.value as ImportReviewCategoryReferenceDto["kind"],
            )
          }
          value={categoryKind}
        >
          <option value="income">Доход</option>
          <option value="expense">Расход</option>
          <option value="mixed">Смешанная</option>
          <option value="transfer">Перевод</option>
          <option value="adjustment">Корректировка</option>
        </select>
      </label>
      <Button disabled={pending} tone="primary" type="submit">
        Создать и выбрать
      </Button>
    </form>
  );
}

function DraftCapability({
  dirty,
  evaluation,
  pending,
}: {
  dirty: boolean;
  evaluation: ImportReviewDraftEvaluationDto;
  pending: boolean;
}) {
  if (dirty) {
    return (
      <p className={styles.draftStatus}>
        {pending
          ? "Проверяем выбранный финансовый смысл…"
          : "Исправьте выбор и повторите попытку."}
      </p>
    );
  }
  if (evaluation.confirmability.canConfirm) {
    return null;
  }
  return (
    <div className={styles.draftStatus}>
      <strong>Что мешает подтверждению:</strong>
      <ul>
        {evaluation.confirmability.blockingReasonCodes.map((reason) => (
          <li key={reason}>{blockingReasonLabel(reason)}</li>
        ))}
      </ul>
    </div>
  );
}

function OrdinaryOutcome({
  categories,
  dirty,
  evaluation,
  pending,
  properties,
}: {
  categories: ClassificationPanelProps["categories"];
  dirty: boolean;
  evaluation: ImportReviewDraftEvaluationDto;
  pending: boolean;
  properties: ClassificationPanelProps["properties"];
}) {
  if (dirty) {
    return pending ? (
      <p className={styles.editorOutcomePending}>Обновляем итог…</p>
    ) : null;
  }
  const operationType = evaluation.classification.operationType;
  const category = categories.find(
    (candidate) => candidate.id === evaluation.selection.categoryId,
  );
  const property = properties.find(
    (candidate) => candidate.id === evaluation.selection.propertyId,
  );

  return (
    <div className={styles.editorOutcome} aria-label="Итог операции">
      <span>Итог:</span>
      <strong>
        {operationType === "income"
          ? "Доход"
          : operationType === "expense"
            ? "Расход"
            : "Тип не выбран"}
        {category ? ` — ${category.name}` : " — категория не выбрана"}
      </strong>
      <small>{property ? `, объект: ${property.name}` : ", без объекта"}</small>
    </div>
  );
}

function FieldError({
  errors,
  id,
}: {
  errors: string[] | undefined;
  id: string;
}) {
  if (!errors?.length) return null;
  return (
    <span className={styles.fieldError} id={id}>
      {errors.join(" ")}
    </span>
  );
}

function defaultCategoryKind(
  operationType: ImportReviewDraftEvaluationRequest["operationType"],
): ImportReviewCategoryReferenceDto["kind"] {
  return operationType === "income" || operationType === "expense"
    ? operationType
    : "mixed";
}

function ordinaryOperationType(
  item: ClassificationPanelProps["item"],
): "income" | "expense" | null {
  if (
    item.classification.operationType === "income" ||
    item.classification.operationType === "expense"
  ) {
    return item.classification.operationType;
  }
  return item.transfer.ordinaryOperationType;
}

function serverDraft(
  item: ClassificationPanelProps["item"],
): ImportReviewDraftEvaluationRequest {
  return {
    operationType: ordinaryOperationType(item),
    categoryId: item.selection.categoryId,
    propertyId: item.selection.propertyId,
  };
}

function serverEvaluation(
  item: ClassificationPanelProps["item"],
): ImportReviewDraftEvaluationDto {
  return {
    itemId: item.id,
    classification: item.classification,
    selection: item.selection,
    confirmability: item.confirmability,
    ruleSuggestion: item.ruleSuggestion,
  };
}

function ordinaryOperationLabel(
  item: ClassificationPanelProps["item"],
): string {
  const operationType = ordinaryOperationType(item);
  if (operationType === "income") return "Доход";
  if (operationType === "expense") return "Расход";
  return "Доход или расход";
}

function focusDraftField(
  fieldErrors: Record<string, string[]>,
  category: HTMLSelectElement | null,
  property: HTMLSelectElement | null,
) {
  if (fieldErrors.categoryId) category?.focus();
  else if (fieldErrors.propertyId) property?.focus();
}

function draftMutationError(result: {
  status: string;
  message?: string;
}): string {
  if (result.status === "unauthenticated") {
    return "Сессия завершилась. Войдите снова, draft сохранён на странице.";
  }
  if (result.status === "forbidden")
    return "Недостаточно прав для проверки draft.";
  return result.message ?? "Draft не удалось проверить.";
}

function categoryMutationError(result: {
  status: string;
  message?: string;
}): string {
  if (result.status === "unauthenticated") {
    return "Сессия завершилась. Название новой категории сохранено в draft.";
  }
  if (result.status === "forbidden")
    return "Недостаточно прав для создания категории.";
  return result.message ?? "Категорию не удалось создать.";
}

function blockingReasonLabel(
  reason: ImportReviewDraftEvaluationDto["confirmability"]["blockingReasonCodes"][number],
): string {
  return {
    terminal_state: "Строка уже завершена.",
    failed_state: "Строка находится в состоянии ошибки.",
    duplicate_review_required: "Сначала разберите возможный дубль.",
    normalization_error: "Исправьте ошибку нормализации.",
    missing_operation_date: "Не определена дата операции.",
    missing_amount: "Не определена сумма.",
    missing_currency: "Не определена валюта.",
    missing_source_account: "Не определён исходный счёт.",
    missing_operation_type: "Не выбран тип операции.",
    operation_type_amount_mismatch:
      "Выбранный тип не соответствует знаку суммы операции.",
    missing_category: "Для дохода или расхода выберите категорию.",
    uncategorized_category: "Системная категория «Без категории» не подходит.",
    transfer_accounts_required: "Для перевода нужны два счёта.",
    same_transfer_account: "Счета перевода должны отличаться.",
    unsupported_operation_type: "Этот тип пока нельзя подтвердить из импорта.",
  }[reason];
}
