import type { AccountDetailDto } from "./api/account-detail-api";
import {
  decimalSign,
  formatMoneyAmount,
} from "../../shared/money/format-money";
import type { MoneyTone } from "../../ui/money-value/money-value";
import type { StatusTone } from "../../ui/status-label/status-label";
import type { TagTone } from "../../ui/tag/tag";

type Movement = AccountDetailDto["items"][number];

export const accountTypeLabels = {
  cash: "Наличные",
  card: "Карта",
  deposit: "Вклад",
  checking: "Расчётный",
  debt: "Долг",
  other: "Другой",
} as const;

export const operationTypes: {
  label: string;
  value: Movement["operationType"];
}[] = [
  { label: "Доход", value: "income" },
  { label: "Расход", value: "expense" },
  { label: "Перевод", value: "transfer" },
  { label: "Корректировка", value: "adjustment" },
];

export const operationStatuses: {
  label: string;
  value: Movement["status"];
}[] = [
  { label: "Черновик", value: "draft" },
  { label: "Нужна проверка", value: "needs_review" },
  { label: "Подтверждено", value: "confirmed" },
  { label: "Отменено", value: "ignored" },
  { label: "Дубликат", value: "duplicate" },
];

export const operationSources: {
  label: string;
  value: Movement["source"];
}[] = [
  { label: "Вручную", value: "manual" },
  { label: "Импорт", value: "bank_pdf" },
  { label: "Долги", value: "debt" },
  { label: "Система", value: "system" },
];

const statusTone: Record<Movement["status"], StatusTone> = {
  confirmed: "success",
  draft: "warning",
  duplicate: "danger",
  ignored: "neutral",
  needs_review: "warning",
};

const typeTone: Record<Movement["operationType"], TagTone> = {
  adjustment: "adjustment",
  expense: "expense",
  income: "income",
  transfer: "transfer",
};

export function movementView(movement: Movement) {
  return {
    amount: formatMoneyAmount(movement.amount, null),
    description: movement.description || "Без описания",
    statusLabel:
      operationStatuses.find((item) => item.value === movement.status)?.label ??
      movement.status,
    statusTone: statusTone[movement.status],
    typeLabel:
      operationTypes.find((item) => item.value === movement.operationType)
        ?.label ?? movement.operationType,
    typeTone: typeTone[movement.operationType],
    moneyTone: movement.operationType as MoneyTone,
  };
}

export function accountBalanceTone(balance: string): MoneyTone {
  const sign = decimalSign(balance);
  if (sign === 1) return "balancePositive";
  if (sign === -1) return "expense";
  return "neutral";
}

export function accountMovementsLabel(total: number): string {
  const remainder100 = total % 100;
  const remainder10 = total % 10;
  if (remainder10 === 1 && remainder100 !== 11) return `${total} проводка`;
  if ([2, 3, 4].includes(remainder10) && ![12, 13, 14].includes(remainder100)) {
    return `${total} проводки`;
  }
  return `${total} проводок`;
}

export function accountMovementAppliedFilters(
  currentSearch: string,
  options: AccountDetailDto["filterOptions"],
): string[] {
  const search = new URLSearchParams(currentSearch);
  const filters: string[] = [];
  addFilter(
    filters,
    "Статус",
    search.get("status") === "confirmed"
      ? ""
      : optionLabel(search.get("status"), operationStatuses),
  );
  addFilter(filters, "От", search.get("date_from") ?? "");
  addFilter(filters, "До", search.get("date_to") ?? "");
  addFilter(
    filters,
    "Источник",
    optionLabel(search.get("source"), operationSources),
  );
  addFilter(filters, "Тип", optionLabel(search.get("type"), operationTypes));
  addFilter(
    filters,
    "Категория",
    optionLabel(search.get("category_id"), options.categories),
  );
  addFilter(
    filters,
    "Объект",
    optionLabel(search.get("property_id"), options.properties),
  );
  addFilter(filters, "Поиск", search.get("search")?.trim() ?? "");
  return filters;
}

function addFilter(filters: string[], label: string, value: string) {
  if (value) filters.push(`${label}: ${value}`);
}

function optionLabel(
  value: string | null,
  options: readonly (
    { id: string; name: string } | { label: string; value: string }
  )[],
): string {
  if (!value) return "";
  const option = options.find((candidate) =>
    "id" in candidate ? candidate.id === value : candidate.value === value,
  );
  if (!option) return "";
  return "name" in option ? option.name : option.label;
}
