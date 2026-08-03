import type { AccountType, CreateAccountDraft } from "./api/accounts-api";

export type AccountFieldErrors = Partial<
  Record<keyof CreateAccountDraft, string>
>;

export function validateAccountDraft(
  draft: CreateAccountDraft,
): AccountFieldErrors {
  const errors: AccountFieldErrors = {};
  if (!draft.name.trim()) {
    errors.name = "Введите название счёта.";
  }
  if (!draft.accountType) {
    errors.accountType = "Выберите тип счёта.";
  }
  if (!/^[A-Za-z]{3}$/.test(draft.currency.trim())) {
    errors.currency = "Введите трёхбуквенный код валюты.";
  }
  if (!/^[+-]?\d+(?:[.,]\d{1,2})?$/.test(draft.initialBalance.trim())) {
    errors.initialBalance = "Введите сумму с точностью до двух знаков.";
  }
  return errors;
}

export function emptyAccountDraft(
  accountTypes: AccountType[],
  defaultCurrency: string,
): CreateAccountDraft {
  return {
    name: "",
    accountType: accountTypes[0] ?? "card",
    currency: defaultCurrency,
    initialBalance: "0.00",
  };
}

export function accountDraftIsDirty(
  draft: CreateAccountDraft,
  initialDraft: CreateAccountDraft,
): boolean {
  return (
    draft.name !== initialDraft.name ||
    draft.accountType !== initialDraft.accountType ||
    draft.currency !== initialDraft.currency ||
    draft.initialBalance !== initialDraft.initialBalance
  );
}

export function accountFieldErrors(
  fieldErrors: Record<string, string[]>,
): AccountFieldErrors {
  const errors: AccountFieldErrors = {};
  const mappings: Array<[keyof CreateAccountDraft, string]> = [
    ["accountType", "accountType"],
    ["currency", "currency"],
    ["initialBalance", "initialBalance"],
    ["name", "name"],
  ];
  for (const [field, serverField] of mappings) {
    const message = fieldErrors[serverField]?.[0];
    if (message) errors[field] = message;
  }
  return errors;
}

export function firstInvalidAccountField(
  errors: AccountFieldErrors,
): keyof CreateAccountDraft | null {
  for (const field of [
    "name",
    "accountType",
    "currency",
    "initialBalance",
  ] as const) {
    if (errors[field]) return field;
  }
  return null;
}

export function accountFormSummaryErrors(errors: AccountFieldErrors) {
  const fields: Array<{
    field: keyof CreateAccountDraft;
    fieldId: string;
    label: string;
  }> = [
    { field: "name", fieldId: "account-name", label: "Название" },
    { field: "accountType", fieldId: "account-type", label: "Тип" },
    { field: "currency", fieldId: "account-currency", label: "Валюта" },
    {
      field: "initialBalance",
      fieldId: "account-initial-balance",
      label: "Начальный баланс",
    },
  ];
  return fields.flatMap(({ field, fieldId, label }) =>
    errors[field] ? [{ fieldId, label, message: errors[field] }] : [],
  );
}
