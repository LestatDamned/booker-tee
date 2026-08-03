import type { FormEvent, RefObject } from "react";

import { Button } from "../../ui/button/button";
import { Field } from "../../ui/field/field";
import { SearchableSelect } from "../../ui/searchable-select/searchable-select";
import type { ImportReviewDto } from "./api/import-review-api";
import type {
  ImportReviewCategoryReferenceDto,
  ImportReviewDraftEvaluationRequest,
} from "./api/import-review-mutations";
import {
  ordinaryOperationLabel,
  parseCategoryKind,
  type ClassificationItem,
  type ClassificationReviewMode,
} from "./classification-model";
import styles from "./classification-panel.module.css";

export function OperationModeSwitch({
  item,
  mode,
  onChange,
}: {
  item: ClassificationItem;
  mode: ClassificationReviewMode;
  onChange: (mode: ClassificationReviewMode) => void;
}) {
  return (
    <fieldset className={styles.operationModeSwitch}>
      <legend>Тип</legend>
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
  categories: ImportReviewDto["references"]["categories"];
  categoryEditorOpen: boolean;
  categoryRef: RefObject<HTMLInputElement | null>;
  draft: ImportReviewDraftEvaluationRequest;
  fieldErrors: Record<string, string[]>;
  itemId: string;
  onCreateCategory: () => void;
  pending: boolean;
  properties: ImportReviewDto["references"]["properties"];
  propertyRef: RefObject<HTMLSelectElement | null>;
  updateDraft: (draft: ImportReviewDraftEvaluationRequest) => void;
};

export function DraftFields({
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
      <Field
        error={fieldErrors.categoryId?.join(" ")}
        errorId={`category-error-${itemId}`}
        htmlFor={`category-${itemId}`}
        label="Категория"
      >
        <div className={styles.editorFieldControl}>
          <SearchableSelect
            aria-describedby={
              fieldErrors.categoryId ? `category-error-${itemId}` : undefined
            }
            aria-invalid={Boolean(fieldErrors.categoryId)}
            id={`category-${itemId}`}
            inputRef={categoryRef}
            onChange={(value) =>
              updateDraft({ ...draft, categoryId: value || null })
            }
            options={[
              { label: "Выберите категорию", value: "" },
              ...compatibleCategories.map((category) => ({
                label: category.name,
                value: category.id,
              })),
            ]}
            placeholder="Найти категорию"
            value={draft.categoryId ?? ""}
          />
          <Button
            aria-label="Создать категорию"
            aria-controls={`category-editor-${itemId}`}
            aria-expanded={categoryEditorOpen}
            className={styles.editorFieldAction ?? ""}
            disabled={pending}
            onClick={onCreateCategory}
            tone="secondary"
          >
            + Новая
          </Button>
        </div>
      </Field>
      <Field
        error={fieldErrors.propertyId?.join(" ")}
        errorId={`property-error-${itemId}`}
        htmlFor={`property-${itemId}`}
        label="Объект"
      >
        <select
          aria-describedby={
            fieldErrors.propertyId ? `property-error-${itemId}` : undefined
          }
          aria-invalid={Boolean(fieldErrors.propertyId)}
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
      </Field>
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

export function CategoryEditor({
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
      <Field
        error={fieldErrors.name?.join(" ")}
        errorId={`category-name-error-${itemId}`}
        htmlFor={`category-name-${itemId}`}
        label="Название категории"
      >
        <input
          aria-describedby={
            fieldErrors.name ? `category-name-error-${itemId}` : undefined
          }
          aria-invalid={Boolean(fieldErrors.name)}
          id={`category-name-${itemId}`}
          onChange={(event) => onNameChange(event.target.value)}
          ref={categoryNameRef}
          value={categoryName}
        />
      </Field>
      <Field htmlFor={`category-kind-${itemId}`} label="Вид категории">
        <select
          id={`category-kind-${itemId}`}
          onChange={(event) =>
            onKindChange(parseCategoryKind(event.target.value))
          }
          value={categoryKind}
        >
          <option value="income">Доход</option>
          <option value="expense">Расход</option>
          <option value="mixed">Смешанная</option>
          <option value="transfer">Перевод</option>
          <option value="adjustment">Корректировка</option>
        </select>
      </Field>
      <Button disabled={pending} icon="plus" tone="primary" type="submit">
        Создать и выбрать
      </Button>
    </form>
  );
}

export function DraftCapability({
  dirty,
  pending,
}: {
  dirty: boolean;
  pending: boolean;
}) {
  if (!dirty || !pending) return null;
  return (
    <p className={styles.draftStatus} role="status">
      Проверяем выбор…
    </p>
  );
}
