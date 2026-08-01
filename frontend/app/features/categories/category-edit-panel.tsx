import type { FormEvent } from "react";

import { Button } from "../../ui/button/button";
import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import { Field } from "../../ui/field/field";
import {
  FormErrorSummary,
  type FormErrorSummaryItem,
} from "../../ui/field/form-error-summary";
import { FormActions } from "../../ui/field/form-layout";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { WorkbenchPanel } from "../../ui/workbench-panel/workbench-panel";
import type { UpdateCategoryDraft } from "./api/category-detail-api";
import type { CategoryFieldErrors } from "./category-form";
import type { CategoryEditState } from "./use-category-editor";
import styles from "./category-detail-page.module.css";

export function CategoryEditPanel({
  confirmation,
  editState,
  onCancelConfirmation,
  onChange,
  onClose,
  onConfirmDiscard,
  onConfirmKindChange,
  onReload,
  onSubmit,
}: {
  confirmation: "close" | "kind" | null;
  editState: CategoryEditState;
  onCancelConfirmation: () => void;
  onChange: (
    field: keyof UpdateCategoryDraft,
    value: UpdateCategoryDraft[keyof UpdateCategoryDraft],
  ) => void;
  onClose: () => void;
  onConfirmDiscard: () => void;
  onConfirmKindChange: () => void;
  onReload: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const { conflict, draft, fieldErrors, pending, snapshot, submitError } =
    editState;
  const summaryErrors = formSummaryErrors(fieldErrors);
  const kindDescription = snapshot.kindOptions.find(
    (option) => option.value === draft.kind,
  )?.description;

  return (
    <>
      <WorkbenchPanel
        description="Измените название, тип или пояснение категории."
        disabled={pending}
        onClose={onClose}
        title="Изменить категорию"
      >
        <form
          className={styles.editForm}
          data-category-edit
          noValidate
          onSubmit={onSubmit}
        >
          {(submitError || summaryErrors.length > 0) && !conflict ? (
            <FormErrorSummary
              errors={summaryErrors}
              headingLevel={3}
              message={
                submitError ??
                "Проверьте поля категории и повторите сохранение."
              }
              title="Не удалось сохранить изменения"
            />
          ) : null}
          {conflict ? (
            <InlineNotice
              action={
                <Button
                  disabled={pending}
                  icon="retry"
                  onClick={onReload}
                  tone="secondary"
                >
                  Загрузить актуальную версию
                </Button>
              }
              role="alert"
              title="Категория уже была изменена"
              tone="danger"
            >
              {submitError} Ваши поля сохранены в draft. После загрузки можно
              проверить изменения и повторить сохранение с новой версией.
            </InlineNotice>
          ) : null}

          <div className={styles.editGrid}>
            <Field
              error={fieldErrors.name}
              errorId="category-edit-name-error"
              htmlFor="category-edit-name"
              label="Название"
              required
            >
              <input
                id="category-edit-name"
                aria-describedby={
                  fieldErrors.name ? "category-edit-name-error" : undefined
                }
                aria-invalid={Boolean(fieldErrors.name)}
                autoComplete="off"
                disabled={pending}
                maxLength={255}
                name="name"
                required
                value={draft.name}
                onChange={(event) => onChange("name", event.target.value)}
              />
            </Field>
            <Field
              error={fieldErrors.kind}
              errorId="category-edit-kind-error"
              {...(kindDescription ? { hint: kindDescription } : {})}
              htmlFor="category-edit-kind"
              label="Тип"
              required
            >
              <select
                id="category-edit-kind"
                aria-describedby={
                  fieldErrors.kind ? "category-edit-kind-error" : undefined
                }
                aria-invalid={Boolean(fieldErrors.kind)}
                disabled={pending}
                name="kind"
                required
                value={draft.kind}
                onChange={(event) =>
                  onChange(
                    "kind",
                    event.target.value as UpdateCategoryDraft["kind"],
                  )
                }
              >
                {snapshot.kindOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              error={fieldErrors.notes}
              errorId="category-edit-notes-error"
              hint="Необязательно. Коротко объясните, когда выбирать эту категорию."
              htmlFor="category-edit-notes"
              label="Заметка"
            >
              <textarea
                id="category-edit-notes"
                aria-describedby={
                  fieldErrors.notes ? "category-edit-notes-error" : undefined
                }
                aria-invalid={Boolean(fieldErrors.notes)}
                disabled={pending}
                maxLength={1000}
                name="notes"
                rows={4}
                value={draft.notes}
                onChange={(event) => onChange("notes", event.target.value)}
              />
            </Field>
          </div>
          <FormActions layout="split">
            <Button disabled={pending} onClick={onClose} tone="secondary">
              Отмена
            </Button>
            <Button
              disabled={pending}
              icon="check"
              isLoading={pending}
              tone="primary"
              type="submit"
            >
              {pending ? "Сохраняем…" : "Сохранить"}
            </Button>
          </FormActions>
        </form>
      </WorkbenchPanel>

      {confirmation === "close" ? (
        <ConfirmationDialog
          cancelLabel="Продолжить редактирование"
          confirmLabel="Отменить изменения"
          description="Несохранённые изменения категории будут потеряны."
          onCancel={onCancelConfirmation}
          onConfirm={onConfirmDiscard}
          title="Закрыть редактирование?"
        />
      ) : null}

      {confirmation === "kind" ? (
        <ConfirmationDialog
          cancelLabel="Вернуться к форме"
          confirmLabel="Изменить тип"
          confirmTone="primary"
          description="Тип влияет на доступность категории в формах классификации, но не изменяет существующую финансовую историю."
          onCancel={onCancelConfirmation}
          onConfirm={onConfirmKindChange}
          pending={pending}
          title="Изменить тип связанной категории?"
        >
          <ul className={styles.kindImpactList}>
            <li>
              {impactCount(
                snapshot.kindChangeImpact.operationCount,
                "операция сохранится",
                "операции сохранятся",
                "операций сохранятся",
              )}
            </li>
            <li>
              {impactCount(
                snapshot.kindChangeImpact.ruleCount,
                "правило останется связанным",
                "правила останутся связанными",
                "правил останутся связанными",
              )}
            </li>
            <li>Доходы, расходы и прибыль не пересчитываются.</li>
          </ul>
        </ConfirmationDialog>
      ) : null}
    </>
  );
}

function formSummaryErrors(
  errors: CategoryFieldErrors,
): FormErrorSummaryItem[] {
  const fields = [
    { field: "name", fieldId: "category-edit-name", label: "Название" },
    { field: "kind", fieldId: "category-edit-kind", label: "Тип" },
    { field: "notes", fieldId: "category-edit-notes", label: "Заметка" },
  ] as const;
  return fields.flatMap(({ field, fieldId, label }) =>
    errors[field] ? [{ fieldId, label, message: errors[field] }] : [],
  );
}

function impactCount(count: number, one: string, few: string, many: string) {
  const tens = count % 100;
  const units = count % 10;
  const label =
    tens >= 11 && tens <= 14
      ? many
      : units === 1
        ? one
        : units >= 2 && units <= 4
          ? few
          : many;
  return `${count} ${label}`;
}
