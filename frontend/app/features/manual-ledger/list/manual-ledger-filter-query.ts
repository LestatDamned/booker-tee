import type { components } from "../../../api/generated/schema";

type FilterOptions = {
  accounts: components["schemas"]["OperationsFilterOptionsApiResponse"]["accounts"];
  categories: components["schemas"]["OperationsFilterOptionsApiResponse"]["categories"];
  properties: components["schemas"]["OperationsFilterOptionsApiResponse"]["properties"];
  sources?: components["schemas"]["OperationsFilterOptionsApiResponse"]["sources"];
};

export type ManualLedgerFilterDraft = {
  accountId: string;
  categoryId: string;
  dateFrom: string;
  dateTo: string;
  operationType: string;
  propertyId: string;
  search: string;
  source: string;
  status: string;
};

export const manualOperationTypeFilters = [
  { value: "income", label: "доход" },
  { value: "expense", label: "расход" },
  { value: "transfer", label: "перевод" },
  { value: "adjustment", label: "корректировка" },
];

export const manualOperationStatusFilters = [
  { value: "all", label: "все статусы" },
  { value: "draft", label: "черновик" },
  { value: "needs_review", label: "нужна проверка" },
  { value: "ignored", label: "отменено" },
  { value: "duplicate", label: "дубликат" },
];

const filterNames = [
  "date_from",
  "date_to",
  "type",
  "status",
  "account_id",
  "category_id",
  "property_id",
  "search",
  "source",
] as const;

export const operationSourceFilters = [
  { value: "manual", label: "вручную" },
  { value: "bank_pdf", label: "импорт" },
  { value: "debt", label: "долг" },
  { value: "system", label: "система" },
] satisfies ReadonlyArray<{
  value: components["schemas"]["OperationSource"];
  label: string;
}>;

export function manualLedgerFilterDraft(
  currentSearch: string,
  options: FilterOptions,
): ManualLedgerFilterDraft {
  const search = new URLSearchParams(currentSearch);
  return {
    accountId: validOption(search.get("account_id"), options.accounts),
    categoryId: validOption(search.get("category_id"), options.categories),
    dateFrom: validDate(search.get("date_from")),
    dateTo: validDate(search.get("date_to")),
    operationType: validOption(search.get("type"), manualOperationTypeFilters),
    propertyId: validOption(search.get("property_id"), options.properties),
    search: search.get("search") ?? "",
    source: validOption(
      search.get("source"),
      options.sources?.map((value) => ({ value })) ?? [],
    ),
    status: validOption(search.get("status"), manualOperationStatusFilters),
  };
}

export function manualLedgerFilterSearch(
  draft: ManualLedgerFilterDraft,
  perPage: number,
): string {
  const search = new URLSearchParams();
  append(search, "date_from", draft.dateFrom);
  append(search, "date_to", draft.dateTo);
  append(search, "type", draft.operationType);
  append(search, "status", draft.status);
  append(search, "account_id", draft.accountId);
  append(search, "category_id", draft.categoryId);
  append(search, "property_id", draft.propertyId);
  append(search, "search", draft.search.trim().replace(/\s+/g, " "));
  append(search, "source", draft.source);
  search.set("page", "1");
  search.set("per_page", String(perPage));
  return `?${search.toString()}`;
}

export function manualLedgerFiltersAreActive(currentSearch: string): boolean {
  const search = new URLSearchParams(currentSearch);
  return filterNames.some((name) => {
    const value = search.get(name);
    if (name === "date_from" || name === "date_to") {
      return Boolean(validDate(value));
    }
    if (name === "type") {
      return Boolean(validOption(value, manualOperationTypeFilters));
    }
    if (name === "status") {
      return Boolean(validOption(value, manualOperationStatusFilters));
    }
    if (name === "source") {
      return Boolean(validOption(value, operationSourceFilters));
    }
    if (name.endsWith("_id")) {
      return Boolean(value && /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(value));
    }
    return Boolean(value?.trim());
  });
}

export function manualLedgerAppliedFilters(
  currentSearch: string,
  options: FilterOptions,
): string[] {
  const draft = manualLedgerFilterDraft(currentSearch, options);
  const filters: string[] = [];
  addAppliedFilter(filters, "От", draft.dateFrom);
  addAppliedFilter(filters, "До", draft.dateTo);
  addAppliedFilter(
    filters,
    "Статус",
    optionLabel(draft.status, manualOperationStatusFilters),
  );
  addAppliedFilter(
    filters,
    "Тип",
    optionLabel(draft.operationType, manualOperationTypeFilters),
  );
  addAppliedFilter(
    filters,
    "Счёт",
    optionLabel(draft.accountId, options.accounts),
  );
  addAppliedFilter(
    filters,
    "Категория",
    optionLabel(draft.categoryId, options.categories),
  );
  addAppliedFilter(
    filters,
    "Объект",
    optionLabel(draft.propertyId, options.properties),
  );
  addAppliedFilter(filters, "Поиск", draft.search.trim());
  addAppliedFilter(
    filters,
    "Источник",
    optionLabel(draft.source, operationSourceFilters),
  );
  return filters;
}

export function manualLedgerClassificationFiltersAreActive(
  draft: ManualLedgerFilterDraft,
): boolean {
  return Boolean(
    draft.operationType ||
    draft.accountId ||
    draft.categoryId ||
    draft.propertyId ||
    draft.source,
  );
}

function addAppliedFilter(filters: string[], label: string, value: string) {
  if (value) {
    filters.push(`${label}: ${value}`);
  }
}

function optionLabel(
  value: string,
  options: readonly (
    { id: string; name: string } | { value: string; label: string }
  )[],
): string {
  if (!value) {
    return "";
  }
  const option = options.find((candidate) => optionValue(candidate) === value);
  if (!option) {
    return "";
  }
  return "name" in option ? option.name : option.label;
}

function append(search: URLSearchParams, name: string, value: string) {
  if (value) {
    search.set(name, value);
  }
}

function validDate(value: string | null): string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return "";
  }
  return Number.isNaN(Date.parse(`${value}T00:00:00Z`)) ? "" : value;
}

function validOption(
  value: string | null,
  options: readonly ({ id: string } | { value: string } | number)[],
): string {
  if (!value) {
    return "";
  }
  return options.some((option) => optionValue(option) === value) ? value : "";
}

function optionValue(
  option: { id: string } | { value: string } | number,
): string {
  if (typeof option === "number") {
    return String(option);
  }
  return "id" in option ? option.id : option.value;
}
