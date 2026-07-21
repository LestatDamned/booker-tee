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

type ClassificationPanelProps = {
  categories: ImportReviewDto["references"]["categories"];
  csrfToken: string;
  documentId: string;
  item: ImportReviewDto["items"][number];
  onCategoryCreated: (category: ImportReviewCategoryReferenceDto) => void;
  properties: ImportReviewDto["references"]["properties"];
  readonly: boolean;
};

export function ClassificationPanel({
  categories,
  csrfToken,
  documentId,
  item,
  onCategoryCreated,
  properties,
  readonly,
}: ClassificationPanelProps) {
  const [draft, setDraft] = useState<ImportReviewDraftEvaluationRequest>({
    operationType: item.classification.operationType,
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
  const [categoryName, setCategoryName] = useState("");
  const [categoryKind, setCategoryKind] = useState<
    ImportReviewCategoryReferenceDto["kind"]
  >(defaultCategoryKind(item.classification.operationType));
  const categoryRef = useRef<HTMLSelectElement>(null);
  const propertyRef = useRef<HTMLSelectElement>(null);
  const categoryNameRef = useRef<HTMLInputElement>(null);

  function updateDraft(next: ImportReviewDraftEvaluationRequest) {
    setDraft(next);
    setDirty(true);
    setError(null);
    setFieldErrors({});
  }

  async function runEvaluation(nextDraft = draft) {
    setPending(true);
    setError(null);
    setFieldErrors({});
    const result = await evaluateImportReviewDraft(
      documentId,
      item.id,
      nextDraft,
      csrfToken,
    );
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
    setPending(true);
    setError(null);
    setFieldErrors({});
    const result = await createImportReviewCategory(
      documentId,
      item.id,
      { name: categoryName, kind: categoryKind },
      csrfToken,
    );
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

  return (
    <details className={styles.classificationPanel}>
      <summary>Разобрать строку</summary>
      <div className={styles.classificationPanelBody}>
        {item.ruleSuggestion.isActive ? (
          <p className={styles.ruleSuggestion}>
            Правило предложило значения, но не подтвердило строку автоматически.
          </p>
        ) : null}
        {readonly ? (
          <p>Изменение classification недоступно для вашей роли.</p>
        ) : (
          <>
            <DraftFields
              categories={categories}
              categoryRef={categoryRef}
              draft={draft}
              fieldErrors={fieldErrors}
              itemId={item.id}
              properties={properties}
              propertyRef={propertyRef}
              updateDraft={updateDraft}
            />
            <div className={styles.draftActions}>
              <Button
                disabled={pending}
                onClick={() => void runEvaluation()}
                tone="primary"
              >
                {pending ? "Проверяем…" : "Проверить выбор"}
              </Button>
              <Button
                aria-expanded={categoryEditorOpen}
                disabled={pending}
                onClick={() => setCategoryEditorOpen((open) => !open)}
              >
                Новая категория
              </Button>
            </div>
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
        {error ? (
          <p className={styles.draftError} role="alert">
            {error}
          </p>
        ) : null}
        <DraftCapability dirty={dirty} evaluation={evaluation} />
      </div>
    </details>
  );
}

type DraftFieldsProps = {
  categories: ClassificationPanelProps["categories"];
  categoryRef: RefObject<HTMLSelectElement | null>;
  draft: ImportReviewDraftEvaluationRequest;
  fieldErrors: Record<string, string[]>;
  itemId: string;
  properties: ClassificationPanelProps["properties"];
  propertyRef: RefObject<HTMLSelectElement | null>;
  updateDraft: (draft: ImportReviewDraftEvaluationRequest) => void;
};

function DraftFields({
  categories,
  categoryRef,
  draft,
  fieldErrors,
  itemId,
  properties,
  propertyRef,
  updateDraft,
}: DraftFieldsProps) {
  return (
    <div className={styles.draftFields}>
      <label>
        Тип операции
        <select
          onChange={(event) =>
            updateDraft({
              ...draft,
              operationType: event.target.value
                ? (event.target.value as NonNullable<
                    ImportReviewDraftEvaluationRequest["operationType"]
                  >)
                : null,
            })
          }
          value={draft.operationType ?? ""}
        >
          <option value="">Определить автоматически</option>
          <option value="income">Доход</option>
          <option value="expense">Расход</option>
          <option value="transfer">Перевод</option>
          <option value="adjustment">Корректировка</option>
        </select>
      </label>
      <label>
        Категория
        <select
          aria-describedby={
            fieldErrors.categoryId ? `category-error-${itemId}` : undefined
          }
          onChange={(event) =>
            updateDraft({ ...draft, categoryId: event.target.value || null })
          }
          ref={categoryRef}
          value={draft.categoryId ?? ""}
        >
          <option value="">Выберите категорию</option>
          {categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </select>
        <FieldError
          errors={fieldErrors.categoryId}
          id={`category-error-${itemId}`}
        />
      </label>
      <label>
        Объект
        <select
          aria-describedby={
            fieldErrors.propertyId ? `property-error-${itemId}` : undefined
          }
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
      </label>
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
    <form className={styles.categoryEditor} onSubmit={onSubmit}>
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
}: {
  dirty: boolean;
  evaluation: ImportReviewDraftEvaluationDto;
}) {
  if (dirty) {
    return (
      <p className={styles.draftStatus}>
        Выбор изменён — проверьте его на сервере.
      </p>
    );
  }
  if (evaluation.confirmability.canConfirm) {
    return (
      <p className={styles.draftReady}>
        Проверки выбора пройдены. Подтверждение будет добавлено в отдельном
        slice.
      </p>
    );
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
    missing_category: "Для дохода или расхода выберите категорию.",
    uncategorized_category: "Системная категория «Без категории» не подходит.",
    transfer_accounts_required: "Для перевода нужны два счёта.",
    same_transfer_account: "Счета перевода должны отличаться.",
    unsupported_operation_type: "Этот тип пока нельзя подтвердить из импорта.",
  }[reason];
}
