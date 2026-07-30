import type { CreateAccountDraft } from "./api/accounts-api";

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
