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
import type { CreatePropertyDraft } from "./api/properties-api";
import type { PropertyFieldErrors } from "./property-form";
import styles from "./properties-page.module.css";

export function PropertyCreatePanel({
  addressRef,
  confirmClose,
  draft,
  fieldErrors,
  nameRef,
  onCancelConfirm,
  onChange,
  onClose,
  onConfirmClose,
  onSubmit,
  pending,
  shortNameRef,
  submitError,
}: {
  addressRef: RefObject<HTMLTextAreaElement | null>;
  confirmClose: boolean;
  draft: CreatePropertyDraft;
  fieldErrors: PropertyFieldErrors;
  nameRef: RefObject<HTMLInputElement | null>;
  onCancelConfirm: () => void;
  onChange: (field: keyof CreatePropertyDraft, value: string) => void;
  onClose: () => void;
  onConfirmClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  pending: boolean;
  shortNameRef: RefObject<HTMLInputElement | null>;
  submitError: string | null;
}) {
  const summaryErrors = formSummaryErrors(fieldErrors);
  return (
    <>
      <WorkbenchPanel
        description="Название и необязательные ориентиры для аналитической привязки операций."
        disabled={pending}
        onClose={onClose}
        title="Новый объект"
      >
        <form
          className={styles.createForm}
          data-property-create
          noValidate
          onSubmit={onSubmit}
        >
          {(submitError || summaryErrors.length > 0) && (
            <FormErrorSummary
              errors={summaryErrors}
              message={
                submitError ?? "Проверьте поля нового объекта и повторите."
              }
            />
          )}
          <div className={styles.formGrid}>
            <Field
              error={fieldErrors.name}
              errorId="property-name-error"
              htmlFor="property-name"
              label="Название"
              required
            >
              <input
                ref={nameRef}
                id="property-name"
                aria-describedby={
                  fieldErrors.name ? "property-name-error" : undefined
                }
                aria-invalid={Boolean(fieldErrors.name)}
                autoFocus
                autoComplete="off"
                disabled={pending}
                maxLength={255}
                name="name"
                placeholder="Квартира на Мира"
                required
                value={draft.name}
                onChange={(event) => onChange("name", event.target.value)}
              />
            </Field>
            <Field
              error={fieldErrors.shortName}
              errorId="property-short-name-error"
              hint="Компактная подпись в списках и формах."
              htmlFor="property-short-name"
              label="Короткое имя"
            >
              <input
                ref={shortNameRef}
                id="property-short-name"
                aria-describedby={
                  fieldErrors.shortName
                    ? "property-short-name-error"
                    : undefined
                }
                aria-invalid={Boolean(fieldErrors.shortName)}
                autoComplete="off"
                disabled={pending}
                maxLength={64}
                name="shortName"
                placeholder="Дом"
                value={draft.shortName}
                onChange={(event) => onChange("shortName", event.target.value)}
              />
            </Field>
            <Field
              error={fieldErrors.address}
              errorId="property-address-error"
              htmlFor="property-address"
              label="Адрес"
            >
              <textarea
                ref={addressRef}
                id="property-address"
                aria-describedby={
                  fieldErrors.address ? "property-address-error" : undefined
                }
                aria-invalid={Boolean(fieldErrors.address)}
                autoComplete="street-address"
                disabled={pending}
                name="address"
                placeholder="Красноярск, ул. Мира, 1"
                rows={3}
                value={draft.address}
                onChange={(event) => onChange("address", event.target.value)}
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
              {pending ? "Создаём…" : "Создать объект"}
            </Button>
          </FormActions>
        </form>
      </WorkbenchPanel>

      {confirmClose ? (
        <ConfirmationDialog
          cancelLabel="Продолжить создание"
          confirmLabel="Закрыть без сохранения"
          description="Несохранённые данные нового объекта будут потеряны."
          onCancel={onCancelConfirm}
          onConfirm={onConfirmClose}
          title="Закрыть создание объекта?"
        />
      ) : null}
    </>
  );
}

function formSummaryErrors(
  errors: PropertyFieldErrors,
): FormErrorSummaryItem[] {
  const fields: Array<{
    field: keyof CreatePropertyDraft;
    fieldId: string;
    label: string;
  }> = [
    { field: "name", fieldId: "property-name", label: "Название" },
    {
      field: "shortName",
      fieldId: "property-short-name",
      label: "Короткое имя",
    },
    { field: "address", fieldId: "property-address", label: "Адрес" },
  ];
  return fields.flatMap(({ field, fieldId, label }) =>
    errors[field] ? [{ fieldId, label, message: errors[field] }] : [],
  );
}
