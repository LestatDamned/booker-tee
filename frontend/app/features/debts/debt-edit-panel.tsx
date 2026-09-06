import { useRef, useState, type FormEvent } from "react";

import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import { Button } from "../../ui/button/button";
import { Field } from "../../ui/field/field";
import { FormErrorSummary } from "../../ui/field/form-error-summary";
import { FormActions, FormGrid } from "../../ui/field/form-layout";
import { WorkbenchPanel } from "../../ui/workbench-panel/workbench-panel";
import { updateDebt, type DebtDetailDto } from "./api/debts-api";
import { DebtMoney } from "./debt-model";
import styles from "./debts.module.css";

type Draft = {
  creditLimit: string;
  maturityDate: string;
  name: string;
  notes: string;
  openedOn: string;
};

export function DebtEditPanel({
  csrfToken,
  detail,
  onClose,
  onUpdated,
}: {
  csrfToken: string;
  detail: DebtDetailDto;
  onClose: () => void;
  onUpdated: (detail: DebtDetailDto) => void;
}) {
  const debt = detail.debt;
  const formRef = useRef<HTMLFormElement>(null);
  const [errors, setErrors] = useState<Partial<Record<keyof Draft, string>>>(
    {},
  );
  const [draft, setDraft] = useState<Draft>({
    creditLimit: debt.creditLimit ?? "",
    maturityDate: debt.maturityDate ?? "",
    name: debt.name,
    notes: detail.notes ?? "",
    openedOn: debt.openedOn ?? "",
  });
  const [failure, setFailure] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  function change<Field extends keyof Draft>(
    field: Field,
    value: Draft[Field],
  ) {
    setDraft((current) => ({ ...current, [field]: value }));
    setFailure(null);
    setErrors((current) => ({ ...current, [field]: undefined }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const validation = validate(draft, debt.kind);
    setErrors(validation);
    setFailure(null);
    const firstInvalid = Object.keys(validation)[0];
    if (firstInvalid) {
      formRef.current
        ?.querySelector<HTMLElement>(`[name="${firstInvalid}"]`)
        ?.focus();
      return;
    }
    setPending(true);
    const result = await updateDebt(
      debt.accountId,
      {
        creditLimit: optional(draft.creditLimit),
        expectedUpdatedAt: debt.updatedAt,
        maturityDate: optional(draft.maturityDate),
        name: draft.name.trim(),
        notes: optional(draft.notes),
        openedOn: optional(draft.openedOn),
      },
      csrfToken,
    );
    setPending(false);
    if (result.status === "success") {
      onUpdated(result.detail);
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    setFailure(result.message);
  }

  return (
    <WorkbenchPanel
      description="Вид долга, валюта и текущий остаток изменяются только финансовыми операциями."
      disabled={pending}
      onClose={onClose}
      title="Изменить долг"
    >
      <form className={styles.form} noValidate onSubmit={submit} ref={formRef}>
        {failure || Object.values(errors).some(Boolean) ? (
          <FormErrorSummary
            message={failure ?? "Проверьте заполненные поля."}
            errors={Object.entries(errors).flatMap(([field, message]) =>
              message
                ? [
                    {
                      fieldId: `debt-edit-${field}`,
                      label: editLabels[field as keyof Draft],
                      message,
                    },
                  ]
                : [],
            )}
          />
        ) : null}
        <FormGrid columns="two">
          <Field
            htmlFor="debt-edit-name"
            error={errors.name}
            errorId="debt-edit-name-error"
            label="Название"
            required
          >
            <input
              disabled={pending}
              id="debt-edit-name"
              name="name"
              aria-invalid={Boolean(errors.name)}
              aria-describedby={
                errors.name ? "debt-edit-name-error" : undefined
              }
              maxLength={255}
              onChange={(event) => change("name", event.target.value)}
              value={draft.name}
            />
          </Field>
          <Field
            htmlFor="debt-edit-openedOn"
            error={errors.openedOn}
            errorId="debt-edit-openedOn-error"
            label="Дата открытия"
          >
            <input
              disabled={pending}
              id="debt-edit-openedOn"
              name="openedOn"
              aria-invalid={Boolean(errors.openedOn)}
              aria-describedby={
                errors.openedOn ? "debt-edit-openedOn-error" : undefined
              }
              onChange={(event) => change("openedOn", event.target.value)}
              type="date"
              value={draft.openedOn}
            />
          </Field>
          {debt.kind === "credit_card" ? (
            <MoneyField
              error={errors.creditLimit}
              id="debt-edit-creditLimit"
              label="Кредитный лимит"
              onChange={(value) => change("creditLimit", value)}
              pending={pending}
              value={draft.creditLimit}
            />
          ) : (
            <>
              <Field
                htmlFor="debt-edit-maturityDate"
                error={errors.maturityDate}
                errorId="debt-edit-maturityDate-error"
                label="Конечный срок"
              >
                <input
                  disabled={pending}
                  id="debt-edit-maturityDate"
                  name="maturityDate"
                  aria-invalid={Boolean(errors.maturityDate)}
                  aria-describedby={
                    errors.maturityDate
                      ? "debt-edit-maturityDate-error"
                      : undefined
                  }
                  onChange={(event) =>
                    change("maturityDate", event.target.value)
                  }
                  type="date"
                  value={draft.maturityDate}
                />
              </Field>
            </>
          )}
        </FormGrid>
        <Field htmlFor="debt-edit-notes" label="Заметки">
          <textarea
            disabled={pending}
            id="debt-edit-notes"
            onChange={(event) => change("notes", event.target.value)}
            rows={4}
            value={draft.notes}
          />
        </Field>
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
            isLoading={pending}
            tone="primary"
            type="submit"
          >
            Сохранить
          </Button>
        </FormActions>
      </form>
    </WorkbenchPanel>
  );
}

function MoneyField({
  error,
  id,
  label,
  onChange,
  pending,
  value,
}: {
  error?: string | undefined;
  id: string;
  label: string;
  onChange: (value: string) => void;
  pending: boolean;
  value: string;
}) {
  return (
    <Field
      htmlFor={id}
      label={label}
      required
      error={error}
      errorId={`${id}-error`}
    >
      <input
        disabled={pending}
        id={id}
        name="creditLimit"
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        inputMode="decimal"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
    </Field>
  );
}

function validate(
  draft: Draft,
  kind: DebtDetailDto["debt"]["kind"],
): Partial<Record<keyof Draft, string>> {
  const errors: Partial<Record<keyof Draft, string>> = {};
  if (!draft.name.trim()) errors.name = "Укажите название долга.";
  if (
    draft.openedOn &&
    draft.maturityDate &&
    draft.maturityDate < draft.openedOn
  ) {
    errors.maturityDate = "Конечный срок не может быть раньше даты открытия.";
  }
  if (kind === "credit_card") {
    const amount = DebtMoney.toMinor(draft.creditLimit);
    if (amount === null || amount === 0n) {
      errors.creditLimit = "Укажите кредитный лимит больше нуля.";
    }
  }
  return errors;
}

function optional(value: string): string | null {
  return value.trim() || null;
}

const editLabels: Record<keyof Draft, string> = {
  name: "Название",
  openedOn: "Дата открытия",
  maturityDate: "Конечный срок",
  creditLimit: "Кредитный лимит",
  notes: "Заметки",
};
