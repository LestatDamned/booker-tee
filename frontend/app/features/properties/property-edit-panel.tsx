import type { FormEvent } from "react";

import { Button } from "../../ui/button/button";
import { ExpansionPanel } from "../../ui/expansion-panel/expansion-panel";
import { Field } from "../../ui/field/field";
import {
  FormErrorSummary,
  type FormErrorSummaryItem,
} from "../../ui/field/form-error-summary";
import { FormActions } from "../../ui/field/form-layout";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import type { CreatePropertyDraft } from "./api/properties-api";
import type { PropertyFieldErrors } from "./property-form";
import styles from "./properties-page.module.css";

export function PropertyEditPanel({
  conflict,
  draft,
  fieldErrors,
  onChange,
  onClose,
  onReload,
  onSubmit,
  panelId,
  pending,
  propertyId,
  submitError,
}: {
  conflict: boolean;
  draft: CreatePropertyDraft;
  fieldErrors: PropertyFieldErrors;
  onChange: (field: keyof CreatePropertyDraft, value: string) => void;
  onClose: () => void;
  onReload: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  panelId: string;
  pending: boolean;
  propertyId: string;
  submitError: string | null;
}) {
  const summaryErrors = formSummaryErrors(fieldErrors, panelId);
  return (
    <ExpansionPanel id={panelId} title="Изменить объект">
      <form
        className={styles.editForm}
        data-property-edit
        noValidate
        onSubmit={onSubmit}
      >
        {(submitError || summaryErrors.length > 0) && !conflict ? (
          <FormErrorSummary
            errors={summaryErrors}
            headingLevel={4}
            message={
              submitError ?? "Проверьте поля объекта и повторите сохранение."
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
                type="button"
              >
                Обновить данные
              </Button>
            }
            role="alert"
            title="Объект уже был изменён"
            tone="danger"
          >
            {submitError} Ваш draft сохранён. Обновление данных заменит его
            только после нажатия кнопки.
          </InlineNotice>
        ) : null}
        <div className={styles.formGrid}>
          <Field
            error={fieldErrors.name}
            errorId={`${panelId}-name-error`}
            htmlFor={`${panelId}-name`}
            label="Название"
            required
          >
            <input
              id={`${panelId}-name`}
              aria-describedby={
                fieldErrors.name ? `${panelId}-name-error` : undefined
              }
              aria-invalid={Boolean(fieldErrors.name)}
              autoComplete="off"
              data-property-edit-field="name"
              data-property-id={propertyId}
              disabled={pending}
              maxLength={255}
              name="name"
              required
              value={draft.name}
              onChange={(event) => onChange("name", event.target.value)}
            />
          </Field>
          <Field
            error={fieldErrors.shortName}
            errorId={`${panelId}-short-name-error`}
            hint="Компактная подпись в списках и формах."
            htmlFor={`${panelId}-short-name`}
            label="Короткое имя"
          >
            <input
              id={`${panelId}-short-name`}
              aria-describedby={
                fieldErrors.shortName
                  ? `${panelId}-short-name-error`
                  : undefined
              }
              aria-invalid={Boolean(fieldErrors.shortName)}
              autoComplete="off"
              data-property-edit-field="shortName"
              data-property-id={propertyId}
              disabled={pending}
              maxLength={64}
              name="shortName"
              value={draft.shortName}
              onChange={(event) => onChange("shortName", event.target.value)}
            />
          </Field>
          <Field
            error={fieldErrors.address}
            errorId={`${panelId}-address-error`}
            htmlFor={`${panelId}-address`}
            label="Адрес"
          >
            <textarea
              id={`${panelId}-address`}
              aria-describedby={
                fieldErrors.address ? `${panelId}-address-error` : undefined
              }
              aria-invalid={Boolean(fieldErrors.address)}
              autoComplete="street-address"
              data-property-edit-field="address"
              data-property-id={propertyId}
              disabled={pending}
              name="address"
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
            icon="check"
            isLoading={pending}
            tone="primary"
            type="submit"
          >
            {pending ? "Сохраняем…" : "Сохранить"}
          </Button>
        </FormActions>
      </form>
    </ExpansionPanel>
  );
}

function formSummaryErrors(
  errors: PropertyFieldErrors,
  panelId: string,
): FormErrorSummaryItem[] {
  const fields: Array<{
    field: keyof CreatePropertyDraft;
    fieldId: string;
    label: string;
  }> = [
    { field: "name", fieldId: `${panelId}-name`, label: "Название" },
    {
      field: "shortName",
      fieldId: `${panelId}-short-name`,
      label: "Короткое имя",
    },
    { field: "address", fieldId: `${panelId}-address`, label: "Адрес" },
  ];
  return fields.flatMap(({ field, fieldId, label }) =>
    errors[field] ? [{ fieldId, label, message: errors[field] }] : [],
  );
}
