import { useState, type FormEvent } from "react";

import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import { Button } from "../../ui/button/button";
import { Field } from "../../ui/field/field";
import { FormErrorSummary } from "../../ui/field/form-error-summary";
import { FormActions } from "../../ui/field/form-layout";
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
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validation = validate(draft, debt.kind);
    if (validation) {
      setFailure(validation);
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
      <form className={styles.form} noValidate onSubmit={submit}>
        {failure ? <FormErrorSummary message={failure} /> : null}
        <div className={styles.formGrid}>
          <Field htmlFor="debt-edit-name" label="Название" required>
            <input
              disabled={pending}
              id="debt-edit-name"
              maxLength={255}
              onChange={(event) => change("name", event.target.value)}
              value={draft.name}
            />
          </Field>
          <Field htmlFor="debt-edit-opened-on" label="Дата открытия">
            <input
              disabled={pending}
              id="debt-edit-opened-on"
              onChange={(event) => change("openedOn", event.target.value)}
              type="date"
              value={draft.openedOn}
            />
          </Field>
          {debt.kind === "credit_card" ? (
            <MoneyField
              id="debt-edit-credit-limit"
              label="Кредитный лимит"
              onChange={(value) => change("creditLimit", value)}
              pending={pending}
              value={draft.creditLimit}
            />
          ) : (
            <>
              <Field htmlFor="debt-edit-maturity-date" label="Конечный срок">
                <input
                  disabled={pending}
                  id="debt-edit-maturity-date"
                  onChange={(event) =>
                    change("maturityDate", event.target.value)
                  }
                  type="date"
                  value={draft.maturityDate}
                />
              </Field>
            </>
          )}
        </div>
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
  id,
  label,
  onChange,
  pending,
  value,
}: {
  id: string;
  label: string;
  onChange: (value: string) => void;
  pending: boolean;
  value: string;
}) {
  return (
    <Field htmlFor={id} label={label} required>
      <input
        disabled={pending}
        id={id}
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
): string | null {
  if (!draft.name.trim()) return "Укажите название долга.";
  if (
    draft.openedOn &&
    draft.maturityDate &&
    draft.maturityDate < draft.openedOn
  ) {
    return "Конечный срок не может быть раньше даты открытия.";
  }
  if (kind === "credit_card") {
    const amount = DebtMoney.toMinor(draft.creditLimit);
    if (amount === null || amount === 0n) {
      return "Укажите кредитный лимит больше нуля.";
    }
  }
  return null;
}

function optional(value: string): string | null {
  return value.trim() || null;
}
