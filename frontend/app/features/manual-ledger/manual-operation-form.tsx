import type { components } from "../../api/generated/schema";
import { Field } from "../../ui/field/field";
import type { ManualLedgerDto, ManualOperationDto } from "./manual-ledger-api";
import styles from "./manual-ledger.module.css";

export type ManualOperationType =
  | components["schemas"]["ManualIncomeExpenseCreateRequest"]["operationType"]
  | components["schemas"]["ManualTransferCreateRequest"]["operationType"];

export type ManualOperationDraft = {
  accountId: string;
  amount: string;
  categoryId: string;
  description: string;
  destinationAccountId: string;
  operationDate: string;
  operationType: ManualOperationType;
  propertyId: string;
};

type ManualOperationFieldsProps = {
  draft: ManualOperationDraft;
  fieldErrors: Record<string, string[]>;
  idPrefix: string;
  onChange: (draft: ManualOperationDraft) => void;
  options: ManualLedgerDto["filterOptions"];
};

export function ManualOperationFields({
  draft,
  fieldErrors,
  idPrefix,
  onChange,
  options,
}: ManualOperationFieldsProps) {
  const isTransfer = draft.operationType === "transfer";
  return (
    <div className={styles.createGrid}>
      <Field htmlFor={`${idPrefix}-type`} label="Тип операции" required>
        <select
          id={`${idPrefix}-type`}
          onChange={(event) =>
            onChange({
              ...draft,
              operationType: parseManualOperationType(
                event.currentTarget.value,
              ),
            })
          }
          value={draft.operationType}
        >
          <option value="income">Доход</option>
          <option value="expense">Расход</option>
          <option value="transfer">Перевод</option>
        </select>
      </Field>
      <AccountSelect
        error={isTransfer ? fieldErrors.sourceAccountId : fieldErrors.accountId}
        id={`${idPrefix}-account`}
        label={isTransfer ? "Счёт списания" : "Счёт"}
        onChange={(accountId) =>
          onChange({
            ...draft,
            accountId,
            destinationAccountId:
              draft.destinationAccountId === accountId
                ? ""
                : draft.destinationAccountId,
          })
        }
        options={options.accounts}
        value={draft.accountId}
      />
      {isTransfer ? (
        <AccountSelect
          error={fieldErrors.destinationAccountId}
          id={`${idPrefix}-destination-account`}
          label="Счёт зачисления"
          onChange={(destinationAccountId) =>
            onChange({ ...draft, destinationAccountId })
          }
          options={options.accounts.filter(
            (account) => account.id !== draft.accountId,
          )}
          value={draft.destinationAccountId}
        />
      ) : null}
      <Field
        {...fieldErrorProps(fieldErrors.amount, `${idPrefix}-amount-error`)}
        htmlFor={`${idPrefix}-amount`}
        label="Сумма"
        required
      >
        <input
          aria-describedby={describedBy(
            fieldErrors.amount,
            `${idPrefix}-amount-error`,
          )}
          aria-invalid={Boolean(fieldErrors.amount)}
          autoComplete="off"
          id={`${idPrefix}-amount`}
          inputMode="decimal"
          onChange={(event) =>
            onChange({ ...draft, amount: event.currentTarget.value })
          }
          placeholder="0,00"
          required
          value={draft.amount}
        />
      </Field>
      <Field
        {...fieldErrorProps(
          fieldErrors.operationDate,
          `${idPrefix}-date-error`,
        )}
        htmlFor={`${idPrefix}-date`}
        label="Дата"
        required
      >
        <input
          aria-describedby={describedBy(
            fieldErrors.operationDate,
            `${idPrefix}-date-error`,
          )}
          aria-invalid={Boolean(fieldErrors.operationDate)}
          id={`${idPrefix}-date`}
          onChange={(event) =>
            onChange({ ...draft, operationDate: event.currentTarget.value })
          }
          required
          type="date"
          value={draft.operationDate}
        />
      </Field>
      {!isTransfer ? (
        <>
          <ReferenceSelect
            error={fieldErrors.categoryId}
            id={`${idPrefix}-category`}
            label="Категория"
            onChange={(categoryId) => onChange({ ...draft, categoryId })}
            options={options.categories}
            value={draft.categoryId}
          />
          <ReferenceSelect
            error={fieldErrors.propertyId}
            id={`${idPrefix}-property`}
            label="Объект"
            onChange={(propertyId) => onChange({ ...draft, propertyId })}
            options={options.properties}
            value={draft.propertyId}
          />
        </>
      ) : null}
      <Field htmlFor={`${idPrefix}-description`} label="Описание">
        <input
          id={`${idPrefix}-description`}
          onChange={(event) =>
            onChange({ ...draft, description: event.currentTarget.value })
          }
          value={draft.description}
        />
      </Field>
    </div>
  );
}

export function emptyManualOperationDraft(): ManualOperationDraft {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  return {
    accountId: "",
    amount: "",
    categoryId: "",
    description: "",
    destinationAccountId: "",
    operationDate: `${year}-${month}-${day}`,
    operationType: "income",
    propertyId: "",
  };
}

export function editDraftFromOperation(
  operation: ManualOperationDto,
): ManualOperationDraft | null {
  const operationType = operation.money?.operationType;
  if (!operation.money || !operationType || operationType === "adjustment") {
    return null;
  }
  return {
    accountId:
      operationType === "transfer"
        ? (operation.sourceAccount?.id ?? "")
        : (operation.account?.id ?? ""),
    amount: operation.money.amount,
    categoryId: operation.category?.id ?? "",
    description: operation.description,
    destinationAccountId: operation.destinationAccount?.id ?? "",
    operationDate: operation.operationDate,
    operationType,
    propertyId: operation.property?.id ?? "",
  };
}

export function operationTypeLabel(value: ManualOperationType): string {
  if (value === "expense") {
    return "расход";
  }
  return value === "transfer" ? "перевод" : "доход";
}

type AccountSelectProps = {
  error: string[] | undefined;
  id: string;
  label: string;
  onChange: (value: string) => void;
  options: { id: string; name: string; currency: string }[];
  value: string;
};

function AccountSelect({
  error,
  id,
  label,
  onChange,
  options,
  value,
}: AccountSelectProps) {
  const errorId = `${id}-error`;
  return (
    <Field
      {...fieldErrorProps(error, errorId)}
      htmlFor={id}
      label={label}
      required
    >
      <select
        aria-describedby={describedBy(error, errorId)}
        aria-invalid={Boolean(error)}
        id={id}
        onChange={(event) => onChange(event.currentTarget.value)}
        required
        value={value}
      >
        <option value="">Выберите счёт</option>
        {options.map((account) => (
          <option key={account.id} value={account.id}>
            {account.name} · {account.currency}
          </option>
        ))}
      </select>
    </Field>
  );
}

type ReferenceSelectProps = {
  error: string[] | undefined;
  id: string;
  label: string;
  onChange: (value: string) => void;
  options: { id: string; name: string }[];
  value: string;
};

function ReferenceSelect({
  error,
  id,
  label,
  onChange,
  options,
  value,
}: ReferenceSelectProps) {
  const errorId = `${id}-error`;
  return (
    <Field {...fieldErrorProps(error, errorId)} htmlFor={id} label={label}>
      <select
        aria-describedby={describedBy(error, errorId)}
        aria-invalid={Boolean(error)}
        id={id}
        onChange={(event) => onChange(event.currentTarget.value)}
        value={value}
      >
        <option value="">Без значения</option>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.name}
          </option>
        ))}
      </select>
    </Field>
  );
}

function parseManualOperationType(value: string): ManualOperationType {
  if (value === "expense" || value === "transfer") {
    return value;
  }
  return "income";
}

function fieldErrorProps(
  errors: string[] | undefined,
  errorId: string,
): { error: string; errorId: string } | Record<string, never> {
  const error = errors?.[0];
  return error ? { error, errorId } : {};
}

function describedBy(
  errors: string[] | undefined,
  errorId: string,
): string | undefined {
  return errors ? errorId : undefined;
}
