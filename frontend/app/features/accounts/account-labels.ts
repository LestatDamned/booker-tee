import type { AccountType } from "./api/accounts-api";

export const accountTypeLabels: Record<AccountType, string> = {
  cash: "Наличные",
  card: "Карта",
  deposit: "Вклад",
  checking: "Расчётный",
  debt: "Долг",
  other: "Другой",
};

export function accountCountLabel(count: number): string {
  return `${count} ${pluralize(count, "счёт", "счёта", "счетов")}`;
}

export function movementCountLabel(count: number): string {
  return `${count} ${pluralize(count, "проводка", "проводки", "проводок")}`;
}

function pluralize(
  count: number,
  one: string,
  few: string,
  many: string,
): string {
  const tens = count % 100;
  const units = count % 10;
  if (tens >= 11 && tens <= 14) return many;
  if (units === 1) return one;
  if (units >= 2 && units <= 4) return few;
  return many;
}
