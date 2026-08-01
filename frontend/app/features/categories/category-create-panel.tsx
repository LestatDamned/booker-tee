import type { FormEvent, RefObject } from "react";

import { Button } from "../../ui/button/button";
import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import { Field } from "../../ui/field/field";
import {
  FormErrorSummary,
  type FormErrorSummaryItem,
} from "../../ui/field/form-error-summary";
import { FormActions } from "../../ui/field/form-layout";
import { WorkbenchPanel } from "../../ui/workbench-panel/workbench-panel";
import type {
  CategoryDirectoryDto,
  CreateCategoryDraft,
} from "./api/categories-api";
import type { CategoryFieldErrors } from "./category-form";
import styles from "./categories-page.module.css";

export function CategoryCreatePanel({
  confirmClose,
  draft,
  fieldErrors,
  kindOptions,
  kindRef,
  nameRef,
  notesRef,
  onCancelConfirm,
  onChange,
  onClose,
  onConfirmClose,
  onSubmit,
  pending,
  submitError,
}: {
  confirmClose: boolean;
  draft: CreateCategoryDraft;
  fieldErrors: CategoryFieldErrors;
  kindOptions: CategoryDirectoryDto["kindOptions"];
  kindRef: RefObject<HTMLSelectElement | null>;
  nameRef: RefObject<HTMLInputElement | null>;
  notesRef: RefObject<HTMLTextAreaElement | null>;
  onCancelConfirm: () => void;
  onChange: <FieldName extends keyof CreateCategoryDraft>(
    field: FieldName,
    value: CreateCategoryDraft[FieldName],
  ) => void;
  onClose: () => void;
  onConfirmClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  pending: boolean;
  submitError: string | null;
}) {
  const summaryErrors = formSummaryErrors(fieldErrors);
  const kindDescription = kindOptions.find(
    (option) => option.value === draft.kind,
  )?.description;

  return (
    <>
      <WorkbenchPanel
        description="Задайте назначение категории — оно помогает корректно классифицировать операции и читать отчёты."
        disabled={pending}
        onClose={onClose}
        title="Новая категория"
      >
        <form
          className={styles.createForm}
          data-category-create
          noValidate
          onSubmit={onSubmit}
        >
          {(submitError || summaryErrors.length > 0) && (
            <FormErrorSummary
              errors={summaryErrors}
              message={
                submitError ?? "Проверьте поля новой категории и повторите."
              }
            />
          )}
          <div className={styles.formGrid}>
            <Field
              error={fieldErrors.name}
              errorId="category-name-error"
              htmlFor="category-name"
              label="Название"
              required
            >
              <input
                ref={nameRef}
                id="category-name"
                aria-describedby={
                  fieldErrors.name ? "category-name-error" : undefined
                }
                aria-invalid={Boolean(fieldErrors.name)}
                autoFocus
                autoComplete="off"
                disabled={pending}
                maxLength={255}
                name="name"
                placeholder="Питомцы"
                required
                value={draft.name}
                onChange={(event) => onChange("name", event.target.value)}
              />
            </Field>
            <Field
              error={fieldErrors.kind}
              errorId="category-kind-error"
              {...(kindDescription ? { hint: kindDescription } : {})}
              htmlFor="category-kind"
              label="Тип"
              required
            >
              <select
                ref={kindRef}
                id="category-kind"
                aria-describedby={
                  fieldErrors.kind ? "category-kind-error" : undefined
                }
                aria-invalid={Boolean(fieldErrors.kind)}
                disabled={pending}
                name="kind"
                required
                value={draft.kind}
                onChange={(event) =>
                  onChange(
                    "kind",
                    event.target.value as CreateCategoryDraft["kind"],
                  )
                }
              >
                {kindOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              error={fieldErrors.notes}
              errorId="category-notes-error"
              hint="Необязательно. Коротко объясните, когда выбирать эту категорию."
              htmlFor="category-notes"
              label="Заметка"
            >
              <textarea
                ref={notesRef}
                id="category-notes"
                aria-describedby={
                  fieldErrors.notes ? "category-notes-error" : undefined
                }
                aria-invalid={Boolean(fieldErrors.notes)}
                disabled={pending}
                maxLength={1000}
                name="notes"
                placeholder="Корм, ветеринар и уход"
                rows={4}
                value={draft.notes}
                onChange={(event) => onChange("notes", event.target.value)}
              />
            </Field>
          </div>
          <FormActions layout="split">
            <Button
              disabled={pending}
              onClick={onClose}
              tone="secondary"
              type="button"
            >
              Отмена
            </Button>
            <Button
              disabled={pending}
              icon="plus"
              isLoading={pending}
              tone="primary"
              type="submit"
            >
              {pending ? "Создаём…" : "Создать категорию"}
            </Button>
          </FormActions>
        </form>
      </WorkbenchPanel>

      {confirmClose ? (
        <ConfirmationDialog
          cancelLabel="Продолжить создание"
          confirmLabel="Закрыть без сохранения"
          description="Несохранённые данные новой категории будут потеряны."
          onCancel={onCancelConfirm}
          onConfirm={onConfirmClose}
          title="Закрыть создание категории?"
        />
      ) : null}
    </>
  );
}

function formSummaryErrors(
  errors: CategoryFieldErrors,
): FormErrorSummaryItem[] {
  const fields: Array<{
    field: keyof CreateCategoryDraft;
    fieldId: string;
    label: string;
  }> = [
    { field: "name", fieldId: "category-name", label: "Название" },
    { field: "kind", fieldId: "category-kind", label: "Тип" },
    { field: "notes", fieldId: "category-notes", label: "Заметка" },
  ];
  return fields.flatMap(({ field, fieldId, label }) =>
    errors[field] ? [{ fieldId, label, message: errors[field] }] : [],
  );
}
