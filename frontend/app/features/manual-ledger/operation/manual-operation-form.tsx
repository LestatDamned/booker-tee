import { useRef, type RefObject } from "react";

import { Field } from "../../../ui/field/field";
import { Fieldset } from "../../../ui/field/fieldset";
import type { FormErrorSummaryItem } from "../../../ui/field/form-error-summary";
import { SearchableSelect } from "../../../ui/searchable-select/searchable-select";
import type { ManualOperationFormOptions } from "../api/manual-ledger-api";
import styles from "../manual-ledger.module.css";
import type {
  ManualOperationDraft,
  ManualOperationType,
} from "./manual-operation-draft";

type ManualOperationFieldsProps = {
  draft: ManualOperationDraft;
  fieldErrors: Record<string, string[]>;
  idPrefix: string;
  layout?: "panel" | "expanded";
  onChange: (draft: ManualOperationDraft) => void;
  options: ManualOperationFormOptions;
};

export function ManualOperationFields({
  draft,
  fieldErrors,
  idPrefix,
  layout = "panel",
  onChange,
  options,
}: ManualOperationFieldsProps) {
  const categoryRef = useRef<HTMLInputElement>(null);
  const isTransfer = draft.operationType === "transfer";
  const accountOptions = options.accounts.filter((account) =>
    accountSupports(account, draft.operationType),
  );
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
                  onChange={(event) => {
                    const operationType = parseManualOperationType(
                      event.currentTarget.value,
                    );
                    const account = options.accounts.find(
                      (item) => item.id === draft.accountId,
                    );
                    onChange({
                      ...draft,
                      operationType,
                      accountId:
                        account && accountSupports(account, operationType)
                          ? draft.accountId
                          : "",
                    });
                  }}
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
          options={accountOptions}
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
            options={accountOptions.filter(
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
            <CategorySelect
              error={fieldErrors.categoryId}
              id={`${idPrefix}-category`}
              inputRef={categoryRef}
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

function accountSupports(
  account: ManualOperationFormOptions["accounts"][number],
  operationType: ManualOperationDraft["operationType"],
): boolean {
  if (operationType === "transfer") return account.canTransfer;
  if (operationType === "income") return account.canRecordIncome;
  return account.canRecordExpense;
}

type CategorySelectProps = {
  error: string[] | undefined;
  id: string;
  inputRef: RefObject<HTMLInputElement | null>;
  name: string;
  onChange: (value: string) => void;
  options: { id: string; name: string }[];
  value: string;
};

function CategorySelect({
  error,
  id,
  inputRef,
  name,
  onChange,
  options,
  value,
}: CategorySelectProps) {
  const errorId = `${id}-error`;
  return (
    <Field {...fieldErrorProps(error, errorId)} htmlFor={id} label="Категория">
      <SearchableSelect
        aria-describedby={describedBy(error, errorId)}
        aria-invalid={Boolean(error)}
        id={id}
        inputRef={inputRef}
        name={name}
        onChange={onChange}
        options={[
          { label: "Без категории", value: "" },
          ...options.map((option) => ({
            label: option.name,
            value: option.id,
          })),
        ]}
        placeholder="Найти категорию"
        value={value}
      />
    </Field>
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
