import type { components } from "../../api/generated/schema";
import { Field } from "../../ui/field/field";
import { Fieldset } from "../../ui/field/fieldset";
import type { FormErrorSummaryItem } from "../../ui/field/form-error-summary";
import type { ManualLedgerDto, ManualOperationDto } from "./manual-ledger-api";
import styles from "./manual-ledger.module.css";

export type ManualOperationType =
  | components["schemas"]["ManualIncomeExpenseCreateApiRequest"]["operationType"]
  | components["schemas"]["ManualTransferCreateApiRequest"]["operationType"];

export type ManualOperationDraft = {
  accountId: string;
  amount: string;
  categoryId: string;
  description: string;
  destinationAccountId: string;
  operationDate: string;
  operationType: ManualOperationType | "";
  propertyId: string;
};

type ManualOperationFieldsProps = {
  draft: ManualOperationDraft;
  fieldErrors: Record<string, string[]>;
  idPrefix: string;
  layout?: "panel" | "expanded";
  onChange: (draft: ManualOperationDraft) => void;
  options: ManualLedgerDto["filterOptions"];
};

export function ManualOperationFields({
  draft,
  fieldErrors,
  idPrefix,
  layout = "panel",
  onChange,
  options,
}: ManualOperationFieldsProps) {
  const isTransfer = draft.operationType === "transfer";
  const selectedCurrency = options.accounts.find(
    (account) => account.id === draft.accountId,
  )?.currency;
  return (
    <div className={styles.operationFormFields}>
      <Fieldset
        {...fieldErrorProps(
          fieldErrors.operationType,
          `${idPrefix}-type-error`,
        )}
        legend="Тип операции"
        required
      >
        <div className={styles.operationTypeChoices}>
          {operationTypeOptions.map((option) => {
            const id = `${idPrefix}-type-${option.value}`;
            return (
              <label
                className={styles.operationTypeChoice}
                data-operation-type={option.value}
                htmlFor={id}
                key={option.value}
              >
                <input
                  checked={draft.operationType === option.value}
                  id={id}
                  name={`${idPrefix}-operation-type`}
                  onChange={(event) =>
                    onChange({
                      ...draft,
                      operationType: parseManualOperationType(
                        event.currentTarget.value,
                      ),
                    })
                  }
                  required
                  type="radio"
                  value={option.value}
                />
                <span>{option.label}</span>
              </label>
            );
          })}
        </div>
      </Fieldset>

      <div className={styles.operationFieldFlow} data-layout={layout}>
        <AccountSelect
          error={
            isTransfer ? fieldErrors.sourceAccountId : fieldErrors.accountId
          }
          id={`${idPrefix}-account`}
          label={isTransfer ? "Счёт списания" : "Счёт"}
          name={isTransfer ? "sourceAccountId" : "accountId"}
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
            name="destinationAccountId"
            onChange={(destinationAccountId) =>
              onChange({ ...draft, destinationAccountId })
            }
            options={options.accounts.filter(
              (account) => account.id !== draft.accountId,
            )}
            value={draft.destinationAccountId}
          />
        ) : null}
        <div className={styles.operationFieldPair}>
          <Field
            {...fieldErrorProps(fieldErrors.amount, `${idPrefix}-amount-error`)}
            htmlFor={`${idPrefix}-amount`}
            label={
              <>
                Сумма
                {selectedCurrency ? (
                  <span aria-hidden="true"> · {selectedCurrency}</span>
                ) : null}
              </>
            }
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
              name="amount"
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
              name="operationDate"
              onChange={(event) =>
                onChange({ ...draft, operationDate: event.currentTarget.value })
              }
              required
              type="date"
              value={draft.operationDate}
            />
          </Field>
        </div>
        {!isTransfer ? (
          <>
            <ReferenceSelect
              error={fieldErrors.categoryId}
              id={`${idPrefix}-category`}
              label="Категория"
              name="categoryId"
              onChange={(categoryId) => onChange({ ...draft, categoryId })}
              options={options.categories}
              value={draft.categoryId}
            />
            <ReferenceSelect
              error={fieldErrors.propertyId}
              id={`${idPrefix}-property`}
              label="Объект"
              name="propertyId"
              onChange={(propertyId) => onChange({ ...draft, propertyId })}
              options={options.properties}
              value={draft.propertyId}
            />
          </>
        ) : null}
        <Field htmlFor={`${idPrefix}-description`} label="Описание">
          <input
            id={`${idPrefix}-description`}
            name="description"
            onChange={(event) =>
              onChange({ ...draft, description: event.currentTarget.value })
            }
            value={draft.description}
          />
        </Field>
      </div>
    </div>
  );
}

const operationTypeOptions: {
  label: string;
  value: ManualOperationType;
}[] = [
  { value: "income", label: "Доход" },
  { value: "expense", label: "Расход" },
  { value: "transfer", label: "Перевод" },
];

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
    operationType: "",
    propertyId: "",
  };
}

export function editDraftFromOperation(
  operation: ManualOperationDto,
): ManualOperationDraft | null {
  const operationType = operation.operationType;
  if (!operation.money || operationType === "adjustment") {
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

export function operationTypeLabel(
  value: ManualOperationDraft["operationType"],
): string {
  if (value === "expense") {
    return "расход";
  }
  if (value === "transfer") {
    return "перевод";
  }
  return value === "income" ? "доход" : "операцию";
}

type AccountSelectProps = {
  error: string[] | undefined;
  id: string;
  label: string;
  name: string;
  onChange: (value: string) => void;
  options: { id: string; name: string; currency: string }[];
  value: string;
};

function AccountSelect({
  error,
  id,
  label,
  name,
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
        name={name}
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
  name: string;
  onChange: (value: string) => void;
  options: { id: string; name: string }[];
  value: string;
};

function ReferenceSelect({
  error,
  id,
  label,
  name,
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
        name={name}
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

function parseManualOperationType(
  value: string,
): ManualOperationDraft["operationType"] {
  if (value === "income" || value === "expense" || value === "transfer") {
    return value;
  }
  return "";
}

export function manualOperationErrorSummaryItems(
  fieldErrors: Record<string, string[]>,
  idPrefix: string,
): FormErrorSummaryItem[] {
  const fields: Record<string, { fieldId: string; label: string }> = {
    accountId: { fieldId: `${idPrefix}-account`, label: "Счёт" },
    sourceAccountId: {
      fieldId: `${idPrefix}-account`,
      label: "Счёт списания",
    },
    destinationAccountId: {
      fieldId: `${idPrefix}-destination-account`,
      label: "Счёт зачисления",
    },
    amount: { fieldId: `${idPrefix}-amount`, label: "Сумма" },
    operationType: {
      fieldId: `${idPrefix}-type-income`,
      label: "Тип операции",
    },
    operationDate: { fieldId: `${idPrefix}-date`, label: "Дата" },
    categoryId: { fieldId: `${idPrefix}-category`, label: "Категория" },
    propertyId: { fieldId: `${idPrefix}-property`, label: "Объект" },
  };

  return Object.entries(fieldErrors).flatMap(([name, messages]) => {
    const field = fields[name];
    if (!field) {
      return [];
    }
    return messages.map((message) => ({ ...field, message }));
  });
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
