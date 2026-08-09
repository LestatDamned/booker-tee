import { useRef, useState, type FormEvent } from "react";

import type { SessionDto } from "../../api/session";
import { todayIsoDate } from "../../shared/date/format-date";
import { formatMoneyAmount } from "../../shared/money/format-money";
import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import { Button } from "../../ui/button/button";
import { Field } from "../../ui/field/field";
import { FormErrorSummary } from "../../ui/field/form-error-summary";
import { FormActions } from "../../ui/field/form-layout";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { MoneyValue } from "../../ui/money-value/money-value";
import { WorkbenchPanel } from "../../ui/workbench-panel/workbench-panel";
import type { AccountSummaryDto } from "../accounts/api/accounts-api";
import type { CategorySummaryDto } from "../categories/api/categories-api";
import {
  recordDebtPayment,
  type DebtDetailDto,
  type DebtPaymentRequest,
} from "./api/debts-api";
import { DebtMoney } from "./debt-model";
import styles from "./debts.module.css";

type PaymentDraft = {
  accountId: string;
  categoryId: string;
  description: string;
  interest: string;
  notes: string;
  operationDate: string;
  principal: string;
};
type PaymentErrors = Partial<Record<keyof PaymentDraft, string>>;

export function DebtPaymentPanel({
  accounts,
  categories,
  detail,
  onClose,
  onCommitted,
  session,
}: {
  accounts: AccountSummaryDto[];
  categories: CategorySummaryDto[];
  detail: DebtDetailDto;
  onClose: () => void;
  onCommitted: (detail: DebtDetailDto) => void;
  session: SessionDto;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const pendingRef = useRef(false);
  const idempotencyKey = useRef(crypto.randomUUID());
  const [draft, setDraft] = useState<PaymentDraft>({
    accountId: "",
    categoryId: "",
    description: "",
    interest: "0.00",
    notes: "",
    operationDate: todayIsoDate(),
    principal: "0.00",
  });
  const [errors, setErrors] = useState<PaymentErrors>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const debt = detail.debt;
  const settlementAccounts = accounts.filter(
    (account) =>
      account.isActive &&
      account.accountType !== "debt" &&
      account.currency === debt.currency,
  );
  const interestKind = debt.kind === "loan_receivable" ? "income" : "expense";
  const interestCategories = categories.filter(
    (category) =>
      category.isActive &&
      (category.kind === interestKind || category.kind === "mixed"),
  );

  function change<Field extends keyof PaymentDraft>(
    field: Field,
    value: PaymentDraft[Field],
  ) {
    setDraft((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
    setFailure(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pendingRef.current) return;
    const nextErrors = validatePayment(draft, debt.outstanding);
    setErrors(nextErrors);
    setFailure(null);
    const firstInvalid = Object.keys(nextErrors)[0];
    if (firstInvalid) {
      formRef.current
        ?.querySelector<HTMLElement>(`[name="${firstInvalid}"]`)
        ?.focus();
      return;
    }
    const request: DebtPaymentRequest = {
      description: draft.description.trim() || null,
      interestAmount: normalizedMoney(draft.interest),
      interestCategoryId: draft.categoryId || null,
      notes: draft.notes.trim() || null,
      operationDate: draft.operationDate,
      principalAmount: normalizedMoney(draft.principal),
      settlementAccountId: draft.accountId,
    };
    pendingRef.current = true;
    setPending(true);
    const result = await recordDebtPayment(
      debt.accountId,
      request,
      session.csrfToken,
      idempotencyKey.current,
    );
    pendingRef.current = false;
    setPending(false);
    if (result.status === "success") {
      idempotencyKey.current = crypto.randomUUID();
      onCommitted(result.detail);
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    setFailure(result.message);
    if (result.status === "error") {
      setErrors(paymentServerErrors(result.fieldErrors));
    }
  }

  const summaryErrors = Object.entries(errors).flatMap(([field, message]) =>
    message
      ? [
          {
            fieldId: `debt-payment-${field}`,
            label: paymentLabel(field),
            message,
          },
        ]
      : [],
  );
  const principal = DebtMoney.toMinor(draft.principal);
  const interest = DebtMoney.toMinor(draft.interest);

  return (
    <WorkbenchPanel
      description={`Остаток основного долга: ${formatMoneyAmount(debt.outstanding, null)} ${debt.currency}.`}
      disabled={pending}
      onClose={onClose}
      title="Записать платёж"
    >
      <form className={styles.form} noValidate onSubmit={submit} ref={formRef}>
        {failure || summaryErrors.length ? (
          <FormErrorSummary
            errors={summaryErrors}
            message={failure ?? "Проверьте платёж."}
          />
        ) : null}
        <div className={styles.formGrid}>
          <PaymentMoneyField
            draft={draft}
            errors={errors}
            field="principal"
            label="Основной долг"
            onChange={change}
            pending={pending}
          />
          <PaymentMoneyField
            draft={draft}
            errors={errors}
            field="interest"
            label="Проценты"
            onChange={change}
            pending={pending}
          />
          <Field
            error={errors.accountId}
            errorId="debt-payment-accountId-error"
            htmlFor="debt-payment-accountId"
            label="Денежный счёт"
            required
          >
            <select
              disabled={pending}
              id="debt-payment-accountId"
              name="accountId"
              onChange={(event) => change("accountId", event.target.value)}
              value={draft.accountId}
            >
              <option value="">Выберите счёт в {debt.currency}</option>
              {settlementAccounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name} · {account.currency}
                </option>
              ))}
            </select>
          </Field>
          <Field
            error={errors.operationDate}
            errorId="debt-payment-operationDate-error"
            htmlFor="debt-payment-operationDate"
            label="Дата платежа"
            required
          >
            <input
              disabled={pending}
              id="debt-payment-operationDate"
              name="operationDate"
              onChange={(event) => change("operationDate", event.target.value)}
              type="date"
              value={draft.operationDate}
            />
          </Field>
          {interest !== null && interest > 0n ? (
            <Field
              error={errors.categoryId}
              errorId="debt-payment-categoryId-error"
              htmlFor="debt-payment-categoryId"
              label={`Категория ${interestKind === "income" ? "дохода" : "расхода"}`}
              required
            >
              <select
                disabled={pending}
                id="debt-payment-categoryId"
                name="categoryId"
                onChange={(event) => change("categoryId", event.target.value)}
                value={draft.categoryId}
              >
                <option value="">Выберите категорию</option>
                {interestCategories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </Field>
          ) : null}
          <Field htmlFor="debt-payment-description" label="Описание">
            <input
              disabled={pending}
              id="debt-payment-description"
              name="description"
              onChange={(event) => change("description", event.target.value)}
              value={draft.description}
            />
          </Field>
        </div>

        <InlineNotice title="Проверка платежа" tone="information">
          <div className={styles.preview}>
            <span>Основной долг уменьшится на</span>
            <MoneyValue
              amount={
                principal === null
                  ? "—"
                  : formatMoneyAmount(draft.principal, null)
              }
              currency={debt.currency}
              tone="transfer"
            />
            <span>
              Проценты станут{" "}
              {interestKind === "income" ? "доходом" : "расходом"}
            </span>
            <MoneyValue
              amount={
                interest === null
                  ? "—"
                  : formatMoneyAmount(draft.interest, null)
              }
              currency={debt.currency}
              tone={interestKind}
            />
          </div>
        </InlineNotice>

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
            {pending ? "Записываем…" : "Записать платёж"}
          </Button>
        </FormActions>
      </form>
    </WorkbenchPanel>
  );
}

type ChangePayment = <Field extends keyof PaymentDraft>(
  field: Field,
  value: PaymentDraft[Field],
) => void;

function PaymentMoneyField({
  draft,
  errors,
  field,
  label,
  onChange,
  pending,
}: {
  draft: PaymentDraft;
  errors: PaymentErrors;
  field: "interest" | "principal";
  label: string;
  onChange: ChangePayment;
  pending: boolean;
}) {
  return (
    <Field
      error={errors[field]}
      errorId={`debt-payment-${field}-error`}
      htmlFor={`debt-payment-${field}`}
      label={label}
      required
    >
      <input
        aria-invalid={Boolean(errors[field])}
        disabled={pending}
        id={`debt-payment-${field}`}
        inputMode="decimal"
        name={field}
        onChange={(event) => onChange(field, event.target.value)}
        value={draft[field]}
      />
    </Field>
  );
}

function validatePayment(
  draft: PaymentDraft,
  outstanding: string,
): PaymentErrors {
  const errors: PaymentErrors = {};
  const principal = DebtMoney.toMinor(draft.principal);
  const interest = DebtMoney.toMinor(draft.interest);
  if (principal === null) errors.principal = "Введите неотрицательную сумму.";
  if (interest === null) errors.interest = "Введите неотрицательную сумму.";
  if (principal === 0n && interest === 0n) {
    errors.principal = "Укажите основной долг или проценты.";
  }
  const balance = DebtMoney.toMinor(outstanding);
  if (principal !== null && balance !== null && principal > balance) {
    errors.principal = "Сумма больше остатка основного долга.";
  }
  if (!draft.accountId) errors.accountId = "Выберите денежный счёт.";
  if (!draft.operationDate) errors.operationDate = "Укажите дату платежа.";
  if (interest !== null && interest > 0n && !draft.categoryId) {
    errors.categoryId = "Выберите категорию процентов.";
  }
  return errors;
}

function normalizedMoney(value: string): string {
  return value.trim().replace(",", ".");
}

function paymentServerErrors(errors: Record<string, string[]>): PaymentErrors {
  const fields: Record<string, keyof PaymentDraft> = {
    interest_amount: "interest",
    interest_category_id: "categoryId",
    interestAmount: "interest",
    interestCategoryId: "categoryId",
    operation_date: "operationDate",
    operationDate: "operationDate",
    principal_amount: "principal",
    principalAmount: "principal",
    settlement_account_id: "accountId",
    settlementAccountId: "accountId",
  };
  return Object.fromEntries(
    Object.entries(errors).flatMap(([field, messages]) => {
      const key = fields[field.split(".").at(-1) ?? ""];
      return key && messages[0] ? [[key, messages[0]]] : [];
    }),
  );
}

function paymentLabel(field: string): string {
  return (
    {
      accountId: "Денежный счёт",
      categoryId: "Категория процентов",
      interest: "Проценты",
      operationDate: "Дата платежа",
      principal: "Основной долг",
    }[field] ?? field
  );
}
