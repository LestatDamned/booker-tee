import { useRef, useState, type FormEvent } from "react";

import type { AccountSummaryDto } from "../accounts/api/accounts-api";
import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import { Button } from "../../ui/button/button";
import { Field } from "../../ui/field/field";
import { FormErrorSummary } from "../../ui/field/form-error-summary";
import { FormActions } from "../../ui/field/form-layout";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { WorkbenchPanel } from "../../ui/workbench-panel/workbench-panel";
import { createDebt, type DebtDetailDto, type DebtKind } from "./api/debts-api";
import {
  DebtCreateDrafts,
  debtActionLabels,
  debtKindLabels,
  type DebtCreateAction,
  type DebtCreateDraft,
  type DebtCreateFieldErrors,
} from "./debt-model";
import styles from "./debts.module.css";

export function DebtCreatePanel({
  accounts,
  csrfToken,
  defaultCurrency,
  onClose,
  onCreated,
}: {
  accounts: AccountSummaryDto[];
  csrfToken: string;
  defaultCurrency: string;
  onClose: () => void;
  onCreated: (detail: DebtDetailDto) => void;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const pendingRef = useRef(false);
  const idempotencyKey = useRef(crypto.randomUUID());
  const [draft, setDraft] = useState(() =>
    DebtCreateDrafts.empty(defaultCurrency),
  );
  const [errors, setErrors] = useState<DebtCreateFieldErrors>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const eligibleAccounts = accounts.filter(
    (account) =>
      account.isActive &&
      account.accountType !== "debt" &&
      account.currency === draft.currency.toUpperCase(),
  );

  function change<Field extends keyof DebtCreateDraft>(
    field: Field,
    value: DebtCreateDraft[Field],
  ) {
    setDraft((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
    setFailure(null);
  }

  function changeAction(action: DebtCreateAction) {
    setDraft((current) => ({
      ...current,
      action,
      accountId: "",
      kind:
        action === "give_loan"
          ? "loan_receivable"
          : action === "open_credit_card"
            ? "credit_card"
            : "loan_payable",
    }));
    setErrors({});
    setFailure(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pendingRef.current) return;
    const nextErrors = DebtCreateDrafts.validate(draft);
    setErrors(nextErrors);
    setFailure(null);
    const firstInvalid = Object.keys(nextErrors)[0];
    if (firstInvalid) {
      formRef.current
        ?.querySelector<HTMLElement>(`[name="${firstInvalid}"]`)
        ?.focus();
      return;
    }
    pendingRef.current = true;
    setPending(true);
    const result = await createDebt(
      DebtCreateDrafts.build(draft),
      csrfToken,
      idempotencyKey.current,
    );
    pendingRef.current = false;
    setPending(false);
    if (result.status === "success") {
      idempotencyKey.current = crypto.randomUUID();
      onCreated(result.detail);
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    setFailure(result.message);
    if (result.status === "error") {
      setErrors(DebtCreateDrafts.fieldErrors(result.fieldErrors));
    }
  }

  const summaryErrors = Object.entries(errors).flatMap(([field, message]) =>
    message
      ? [{ fieldId: `debt-create-${field}`, label: fieldLabel(field), message }]
      : [],
  );

  return (
    <WorkbenchPanel
      description="Укажите фактический долг. Отрицательные суммы вводить не нужно."
      disabled={pending}
      onClose={onClose}
      title="Добавить долг"
    >
      <form className={styles.form} noValidate onSubmit={submit} ref={formRef}>
        {failure || summaryErrors.length ? (
          <FormErrorSummary
            errors={summaryErrors}
            message={failure ?? "Проверьте заполненные поля."}
          />
        ) : null}

        <Field htmlFor="debt-create-action" label="Что произошло" required>
          <select
            disabled={pending}
            id="debt-create-action"
            name="action"
            onChange={(event) =>
              changeAction(event.target.value as DebtCreateAction)
            }
            value={draft.action}
          >
            {Object.entries(debtActionLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>

        <div className={styles.formGrid}>
          <TextField
            draft={draft}
            errors={errors}
            field="name"
            label="Название"
            onChange={change}
            pending={pending}
            placeholder="Ипотека ВТБ"
          />
          <TextField
            draft={draft}
            errors={errors}
            field="currency"
            hint="Например RUB. Валюта должна совпадать с денежным счётом."
            label="Валюта"
            maxLength={3}
            onChange={(_, value) => change("currency", value.toUpperCase())}
            pending={pending}
          />
          {draft.action === "add_existing" ? (
            <KindField
              draft={draft}
              onChange={change}
              options={["loan_receivable", "loan_payable", "mortgage"]}
              pending={pending}
            />
          ) : draft.action === "take_loan" ? (
            <KindField
              draft={draft}
              onChange={change}
              options={["loan_payable", "mortgage"]}
              pending={pending}
            />
          ) : null}
          {draft.action === "add_existing" ? (
            <>
              <MoneyField
                draft={draft}
                errors={errors}
                field="openingBalance"
                hint="Сколько основного долга осталось сейчас."
                label="Текущий остаток"
                onChange={change}
                pending={pending}
              />
              <MoneyField
                draft={draft}
                errors={errors}
                field="originalPrincipal"
                label="Первоначальная сумма"
                onChange={change}
                pending={pending}
              />
            </>
          ) : draft.action === "open_credit_card" ? (
            <>
              <MoneyField
                draft={draft}
                errors={errors}
                field="creditLimit"
                label="Кредитный лимит"
                onChange={change}
                pending={pending}
              />
              <MoneyField
                draft={draft}
                errors={errors}
                field="openingDebt"
                hint="Можно оставить 0, если задолженности пока нет."
                label="Текущий долг"
                onChange={change}
                pending={pending}
              />
            </>
          ) : (
            <>
              <MoneyField
                draft={draft}
                errors={errors}
                field="amount"
                label="Сумма"
                onChange={change}
                pending={pending}
              />
              <Field
                error={errors.accountId}
                errorId="debt-create-accountId-error"
                htmlFor="debt-create-accountId"
                label={
                  draft.action === "give_loan"
                    ? "Счёт, с которого выданы деньги"
                    : "Счёт, на который получены деньги"
                }
                required
              >
                <select
                  aria-invalid={Boolean(errors.accountId)}
                  disabled={pending}
                  id="debt-create-accountId"
                  name="accountId"
                  onChange={(event) => change("accountId", event.target.value)}
                  value={draft.accountId}
                >
                  <option value="">Выберите счёт</option>
                  {eligibleAccounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.name} · {account.currency}
                    </option>
                  ))}
                </select>
              </Field>
              <TextField
                draft={draft}
                errors={errors}
                field="operationDate"
                label="Дата операции"
                onChange={change}
                pending={pending}
                type="date"
              />
            </>
          )}
          <TextField
            draft={draft}
            errors={errors}
            field="openedOn"
            label="Дата открытия"
            onChange={change}
            pending={pending}
            required={false}
            type="date"
          />
          {draft.action !== "open_credit_card" ? (
            <TextField
              draft={draft}
              errors={errors}
              field="maturityDate"
              label="Конечный срок"
              onChange={change}
              pending={pending}
              required={false}
              type="date"
            />
          ) : null}
        </div>

        {draft.action === "give_loan" || draft.action === "take_loan" ? (
          <InlineNotice title="Что будет записано" tone="information">
            {draft.action === "give_loan"
              ? "Деньги уйдут с выбранного счёта, а сумма появится как долг вам. Это перевод и он не станет расходом."
              : "Деньги поступят на выбранный счёт, а сумма появится как ваш долг. Это перевод и он не станет доходом."}
          </InlineNotice>
        ) : null}

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
            {pending ? "Добавляем…" : "Добавить долг"}
          </Button>
        </FormActions>
      </form>
    </WorkbenchPanel>
  );
}

type ChangeDraft = <Field extends keyof DebtCreateDraft>(
  field: Field,
  value: DebtCreateDraft[Field],
) => void;

function TextField({
  draft,
  errors,
  field,
  hint,
  label,
  maxLength,
  inputMode,
  onChange,
  pending,
  placeholder,
  required = true,
  type = "text",
}: {
  draft: DebtCreateDraft;
  errors: DebtCreateFieldErrors;
  field: keyof DebtCreateDraft;
  hint?: string;
  label: string;
  maxLength?: number;
  inputMode?: "decimal";
  onChange: ChangeDraft;
  pending: boolean;
  placeholder?: string;
  required?: boolean;
  type?: string;
}) {
  const id = `debt-create-${field}`;
  return (
    <Field
      error={errors[field]}
      errorId={`${id}-error`}
      {...(hint ? { hint } : {})}
      htmlFor={id}
      label={label}
      required={required}
    >
      <input
        aria-invalid={Boolean(errors[field])}
        disabled={pending}
        id={id}
        inputMode={inputMode}
        maxLength={maxLength}
        name={field}
        onChange={(event) => onChange(field, event.target.value)}
        placeholder={placeholder}
        required={required}
        type={type}
        value={draft[field]}
      />
    </Field>
  );
}

function MoneyField(props: Omit<Parameters<typeof TextField>[0], "type">) {
  return <TextField {...props} inputMode="decimal" type="text" />;
}

function KindField({
  draft,
  onChange,
  options,
  pending,
}: {
  draft: DebtCreateDraft;
  onChange: ChangeDraft;
  options: DebtKind[];
  pending: boolean;
}) {
  return (
    <Field htmlFor="debt-create-kind" label="Вид долга" required>
      <select
        disabled={pending}
        id="debt-create-kind"
        name="kind"
        onChange={(event) => onChange("kind", event.target.value as DebtKind)}
        value={draft.kind}
      >
        {options.map((kind) => (
          <option key={kind} value={kind}>
            {debtKindLabels[kind]}
          </option>
        ))}
      </select>
    </Field>
  );
}

function fieldLabel(field: string): string {
  return (
    {
      accountId: "Денежный счёт",
      amount: "Сумма",
      creditLimit: "Кредитный лимит",
      currency: "Валюта",
      maturityDate: "Конечный срок",
      name: "Название",
      openingBalance: "Текущий остаток",
      openingDebt: "Текущий долг",
      operationDate: "Дата операции",
      originalPrincipal: "Первоначальная сумма",
    }[field] ?? field
  );
}
