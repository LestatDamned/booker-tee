import {
  forwardRef,
  useMemo,
  useRef,
  useState,
  useImperativeHandle,
  type FormEvent,
  type RefObject,
} from "react";

import { Button } from "../../ui/button/button";
import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import { Field } from "../../ui/field/field";
import { FormActions } from "../../ui/field/form-layout";
import {
  FormErrorSummary,
  type FormErrorSummaryItem,
} from "../../ui/field/form-error-summary";
import { SearchableSelect } from "../../ui/searchable-select/searchable-select";
import {
  updateImportedOperationReviewFields,
  type AccountDetailDto,
  type ImportedOperationCorrectionDraft,
} from "./api/account-detail-api";
import panelStyles from "./account-settings-panel.module.css";
import styles from "./imported-operation-correction-panel.module.css";

type Movement = AccountDetailDto["items"][number];
type EditableField = "categoryId" | "description" | "propertyId";
type FieldErrors = Partial<Record<EditableField, string>>;

type Props = {
  accountId: string;
  categories: AccountDetailDto["filterOptions"]["categories"];
  csrfToken: string;
  movement: Movement;
  onClose: () => void;
  onCommitted: (movement: Movement) => void;
  properties: AccountDetailDto["filterOptions"]["properties"];
};

export type ImportedOperationCorrectionPanelHandle = {
  requestClose: () => void;
};

export const ImportedOperationCorrectionPanel = forwardRef<
  ImportedOperationCorrectionPanelHandle,
  Props
>(function ImportedOperationCorrectionPanel(
  {
    accountId,
    categories,
    csrfToken,
    movement,
    onClose,
    onCommitted,
    properties,
  },
  ref,
) {
  const initialDraft = useMemo(() => correctionDraft(movement), [movement]);
  const [draft, setDraft] = useState(initialDraft);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [pending, setPending] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const descriptionRef = useRef<HTMLInputElement>(null);
  const categoryRef = useRef<HTMLInputElement>(null);
  const propertyRef = useRef<HTMLSelectElement>(null);
  const dirty = !sameDraft(draft, initialDraft);
  const categoryOptions = includeCurrentOption(categories, movement.category);
  const propertyOptions = includeCurrentOption(properties, movement.property);
  const summaryErrors = formSummaryErrors(fieldErrors);

  function changeDraft<Key extends EditableField>(
    field: Key,
    value: ImportedOperationCorrectionDraft[Key],
  ) {
    setDraft((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: undefined }));
    setSubmitError(null);
    setConflict(false);
  }

  function requestClose() {
    if (pending) return;
    if (dirty) {
      setConfirmClose(true);
      return;
    }
    onClose();
  }

  useImperativeHandle(ref, () => ({ requestClose }));

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors = validateDraft(draft);
    setFieldErrors(errors);
    setSubmitError(null);
    setConflict(false);
    const invalid = firstInvalidField(errors);
    if (invalid) {
      fieldRefs({ categoryRef, descriptionRef, propertyRef })[
        invalid
      ].current?.focus();
      return;
    }

    setPending(true);
    const result = await updateImportedOperationReviewFields({
      accountId,
      csrfToken,
      draft,
      operationId: movement.operationId,
    });
    setPending(false);
    if (result.status === "success") {
      onCommitted(result.movement);
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    if (result.status === "conflict") {
      setConflict(result.code === "operation_version_conflict");
      setSubmitError(result.message);
      return;
    }
    if (result.status === "forbidden") {
      setSubmitError(result.message);
      return;
    }
    const serverErrors = correctionFieldErrors(result.fieldErrors);
    setFieldErrors(serverErrors);
    setSubmitError(result.message);
    const serverInvalid = firstInvalidField(serverErrors);
    if (serverInvalid) {
      fieldRefs({ categoryRef, descriptionRef, propertyRef })[
        serverInvalid
      ].current?.focus();
    }
  }

  return (
    <>
      <form
        aria-busy={pending}
        className={panelStyles.form}
        data-imported-operation-correction
        data-imported-operation-correction-panel
        noValidate
        onSubmit={submit}
      >
        {(submitError || summaryErrors.length > 0) && (
          <FormErrorSummary
            errors={summaryErrors}
            message={
              submitError ?? "Проверьте поля операции и повторите сохранение."
            }
          />
        )}
        {conflict ? (
          <Button onClick={() => window.location.reload()} type="button">
            Загрузить актуальные данные
          </Button>
        ) : null}

        <fieldset className={panelStyles.group}>
          <Field
            error={fieldErrors.description}
            errorId="correction-description-error"
            hint="Можно уточнить назначение операции, не меняя финансовые данные."
            htmlFor="correction-description"
            label="Описание"
          >
            <input
              aria-describedby={
                fieldErrors.description
                  ? "correction-description-error"
                  : undefined
              }
              aria-invalid={Boolean(fieldErrors.description)}
              autoFocus
              disabled={pending}
              id="correction-description"
              maxLength={2000}
              onChange={(event) =>
                changeDraft("description", event.target.value)
              }
              ref={descriptionRef}
              type="text"
              value={draft.description}
            />
          </Field>
          <div className={styles.classification}>
            <Field
              error={fieldErrors.categoryId}
              errorId="correction-category-error"
              htmlFor="correction-category"
              label="Категория"
            >
              <SearchableSelect
                aria-describedby={
                  fieldErrors.categoryId
                    ? "correction-category-error"
                    : undefined
                }
                aria-invalid={Boolean(fieldErrors.categoryId)}
                disabled={pending}
                id="correction-category"
                inputRef={categoryRef}
                onChange={(value) => changeDraft("categoryId", value || null)}
                options={[
                  { label: "Без категории", value: "" },
                  ...categoryOptions.map((category) => ({
                    label: category.name,
                    value: category.id,
                  })),
                ]}
                placeholder="Найти категорию"
                value={draft.categoryId ?? ""}
              />
            </Field>
            <Field
              error={fieldErrors.propertyId}
              errorId="correction-property-error"
              htmlFor="correction-property"
              label="Объект"
            >
              <select
                aria-describedby={
                  fieldErrors.propertyId
                    ? "correction-property-error"
                    : undefined
                }
                aria-invalid={Boolean(fieldErrors.propertyId)}
                disabled={pending}
                id="correction-property"
                onChange={(event) =>
                  changeDraft("propertyId", event.target.value || null)
                }
                ref={propertyRef}
                value={draft.propertyId ?? ""}
              >
                <option value="">Без объекта</option>
                {propertyOptions.map((property) => (
                  <option key={property.id} value={property.id}>
                    {property.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        </fieldset>

        <FormActions layout="split">
          <Button
            disabled={pending}
            onClick={requestClose}
            tone="secondary"
            type="button"
          >
            Отмена
          </Button>
          <Button
            disabled={!dirty || pending}
            icon="check"
            isLoading={pending}
            tone="primary"
            type="submit"
          >
            Сохранить исправления
          </Button>
        </FormActions>
      </form>

      {confirmClose ? (
        <ConfirmationDialog
          cancelLabel="Продолжить редактирование"
          confirmLabel="Закрыть без сохранения"
          description="Несохранённые исправления операции будут потеряны."
          onCancel={() => setConfirmClose(false)}
          onConfirm={onClose}
          title="Закрыть исправление?"
        />
      ) : null}
    </>
  );
});

function correctionDraft(movement: Movement): ImportedOperationCorrectionDraft {
  return {
    categoryId: movement.category?.id ?? null,
    description: movement.description,
    expectedVersion: movement.version,
    propertyId: movement.property?.id ?? null,
  };
}

function sameDraft(
  left: ImportedOperationCorrectionDraft,
  right: ImportedOperationCorrectionDraft,
) {
  return (
    left.categoryId === right.categoryId &&
    left.description === right.description &&
    left.expectedVersion === right.expectedVersion &&
    left.propertyId === right.propertyId
  );
}

function includeCurrentOption(
  options: Array<{ id: string; name: string }>,
  current: { id: string; name: string } | null,
) {
  if (!current || options.some((option) => option.id === current.id)) {
    return options;
  }
  return [current, ...options];
}

function validateDraft(draft: ImportedOperationCorrectionDraft): FieldErrors {
  if (draft.description.length > 2000) {
    return { description: "Описание не должно быть длиннее 2000 символов." };
  }
  return {};
}

function correctionFieldErrors(
  fieldErrors: Record<string, string[]>,
): FieldErrors {
  const errors: FieldErrors = {};
  for (const field of ["categoryId", "description", "propertyId"] as const) {
    const message = fieldErrors[field]?.[0];
    if (message) errors[field] = message;
  }
  return errors;
}

function firstInvalidField(errors: FieldErrors): EditableField | null {
  for (const field of ["description", "categoryId", "propertyId"] as const) {
    if (errors[field]) return field;
  }
  return null;
}

function fieldRefs({
  categoryRef,
  descriptionRef,
  propertyRef,
}: {
  categoryRef: RefObject<HTMLInputElement | null>;
  descriptionRef: RefObject<HTMLInputElement | null>;
  propertyRef: RefObject<HTMLSelectElement | null>;
}): Record<EditableField, RefObject<HTMLElement | null>> {
  return {
    categoryId: categoryRef,
    description: descriptionRef,
    propertyId: propertyRef,
  };
}

function formSummaryErrors(errors: FieldErrors): FormErrorSummaryItem[] {
  const fields: Array<{
    field: EditableField;
    fieldId: string;
    label: string;
  }> = [
    {
      field: "description",
      fieldId: "correction-description",
      label: "Описание",
    },
    {
      field: "categoryId",
      fieldId: "correction-category",
      label: "Категория",
    },
    {
      field: "propertyId",
      fieldId: "correction-property",
      label: "Объект",
    },
  ];
  return fields.flatMap(({ field, fieldId, label }) =>
    errors[field] ? [{ fieldId, label, message: errors[field] }] : [],
  );
}
