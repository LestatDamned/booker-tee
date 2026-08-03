import type { FormEvent, RefObject } from "react";

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
import type {
  CreateWorkspaceDraft,
  WorkspaceDirectoryDto,
} from "./api/workspaces-api";
import type { WorkspaceFieldErrors } from "./workspace-form";
import styles from "./workspaces-page.module.css";

export function WorkspaceCreatePanel({
  confirmClose,
  directory,
  draft,
  fieldErrors,
  nameRef,
  onCancelConfirm,
  onChange,
  onClose,
  onConfirmClose,
  onSubmit,
  pending,
  submitError,
}: {
  confirmClose: boolean;
  directory: WorkspaceDirectoryDto;
  draft: CreateWorkspaceDraft;
  fieldErrors: WorkspaceFieldErrors;
  nameRef: RefObject<HTMLInputElement | null>;
  onCancelConfirm: () => void;
  onChange: <FieldName extends keyof CreateWorkspaceDraft>(
    field: FieldName,
    value: CreateWorkspaceDraft[FieldName],
  ) => void;
  onClose: () => void;
  onConfirmClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  pending: boolean;
  submitError: string | null;
}) {
  const summaryErrors = formSummaryErrors(fieldErrors);
  return (
    <>
      <WorkbenchPanel
        description="После создания новое пространство станет текущим финансовым контекстом."
        disabled={pending}
        initialFocusRef={nameRef}
        onClose={onClose}
        title="Новое пространство"
      >
        <form className={styles.createForm} noValidate onSubmit={onSubmit}>
          {(submitError || summaryErrors.length > 0) && (
            <FormErrorSummary
              errors={summaryErrors}
              message={
                submitError ?? "Проверьте поля пространства и повторите."
              }
            />
          )}
          <Field
            error={fieldErrors.name}
            errorId="workspace-name-error"
            htmlFor="workspace-name"
            label="Название"
            required
          >
            <input
              ref={nameRef}
              id="workspace-name"
              aria-describedby={
                fieldErrors.name ? "workspace-name-error" : undefined
              }
              aria-invalid={Boolean(fieldErrors.name)}
              autoFocus
              autoComplete="organization"
              disabled={pending}
              maxLength={255}
              name="name"
              required
              value={draft.name}
              onChange={(event) => onChange("name", event.target.value)}
            />
          </Field>
          <div className={styles.formColumns}>
            <Field
              error={fieldErrors.workspaceType}
              errorId="workspace-type-error"
              htmlFor="workspace-type"
              label="Тип"
              required
            >
              <select
                id="workspace-type"
                aria-describedby={
                  fieldErrors.workspaceType ? "workspace-type-error" : undefined
                }
                aria-invalid={Boolean(fieldErrors.workspaceType)}
                disabled={pending}
                name="workspaceType"
                value={draft.workspaceType}
                onChange={(event) =>
                  onChange(
                    "workspaceType",
                    event.target.value as CreateWorkspaceDraft["workspaceType"],
                  )
                }
              >
                {directory.workspaceTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              error={fieldErrors.defaultCurrency}
              errorId="workspace-currency-error"
              htmlFor="workspace-currency"
              label="Основная валюта"
              required
            >
              <select
                id="workspace-currency"
                aria-describedby={
                  fieldErrors.defaultCurrency
                    ? "workspace-currency-error"
                    : undefined
                }
                aria-invalid={Boolean(fieldErrors.defaultCurrency)}
                disabled={pending}
                name="defaultCurrency"
                value={draft.defaultCurrency}
                onChange={(event) =>
                  onChange("defaultCurrency", event.target.value)
                }
              >
                {directory.currencyOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <InlineNotice title="Граница финансовых данных" tone="information">
            Счета, импорты, операции и отчёты нового пространства будут
            изолированы от текущего.
          </InlineNotice>
          <FormActions layout="split">
            <Button disabled={pending} onClick={onClose} tone="secondary">
              Отмена
            </Button>
            <Button
              disabled={pending}
              icon="plus"
              isLoading={pending}
              tone="primary"
              type="submit"
            >
              {pending ? "Создаём…" : "Создать и перейти"}
            </Button>
          </FormActions>
        </form>
      </WorkbenchPanel>
      {confirmClose ? (
        <ConfirmationDialog
          cancelLabel="Продолжить создание"
          confirmLabel="Закрыть без сохранения"
          description="Несохранённые данные нового пространства будут потеряны."
          onCancel={onCancelConfirm}
          onConfirm={onConfirmClose}
          title="Закрыть создание пространства?"
        />
      ) : null}
    </>
  );
}

function formSummaryErrors(
  errors: WorkspaceFieldErrors,
): FormErrorSummaryItem[] {
  const fields: Array<{
    field: keyof CreateWorkspaceDraft;
    fieldId: string;
    label: string;
  }> = [
    { field: "name", fieldId: "workspace-name", label: "Название" },
    { field: "workspaceType", fieldId: "workspace-type", label: "Тип" },
    {
      field: "defaultCurrency",
      fieldId: "workspace-currency",
      label: "Основная валюта",
    },
  ];
  return fields.flatMap(({ field, fieldId, label }) =>
    errors[field] ? [{ fieldId, label, message: errors[field] }] : [],
  );
}
