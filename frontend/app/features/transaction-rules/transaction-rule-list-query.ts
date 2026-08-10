import type {
  TransactionRuleDirectoryDto,
  TransactionRuleDirectoryStatus,
} from "./api/transaction-rules-api";

const defaultPageSize = 50;
const pageSizes = [25, 50, 100] as const;

export type TransactionRuleListQuery = {
  categoryId: string;
  page: number;
  pageSize: number;
  q: string;
  ruleId: string;
  status: TransactionRuleDirectoryStatus;
};

export function transactionRuleListQuery(
  search: string,
): TransactionRuleListQuery {
  const params = new URLSearchParams(search);
  const status = params.get("status");
  return {
    q: normalizeSearch(params.get("q") ?? ""),
    categoryId: validUuid(params.get("category_id")),
    ruleId: validUuid(params.get("rule_id")),
    status: status === "active" || status === "disabled" ? status : "all",
    page: positiveInteger(params.get("page"), 1),
    pageSize: validPageSize(params.get("page_size")),
  };
}

export function transactionRuleListSearch(
  query: TransactionRuleListQuery,
): string {
  const params = new URLSearchParams();
  if (query.q) params.set("q", normalizeSearch(query.q));
  if (query.categoryId) params.set("category_id", query.categoryId);
  if (query.ruleId) params.set("rule_id", query.ruleId);
  if (query.status !== "all") params.set("status", query.status);
  if (query.page !== 1) params.set("page", String(query.page));
  if (query.pageSize !== defaultPageSize) {
    params.set("page_size", String(query.pageSize));
  }
  const value = params.toString();
  return value ? `?${value}` : "";
}

export function transactionRuleApiSearch(search: string): string {
  return transactionRuleListSearch(transactionRuleListQuery(search));
}

export function transactionRuleStatusUrl(
  currentSearch: string,
  status: TransactionRuleDirectoryStatus,
): string {
  const query = transactionRuleListQuery(currentSearch);
  return transactionRuleListSearch({ ...query, page: 1, ruleId: "", status });
}

export function transactionRulePageUrl(
  currentSearch: string,
  page: number,
): string {
  const query = transactionRuleListQuery(currentSearch);
  return transactionRuleListSearch({
    ...query,
    page: Math.max(1, page),
    ruleId: "",
  });
}

export function transactionRuleSearchUrl(
  currentSearch: string,
  q: string,
): string {
  const query = transactionRuleListQuery(currentSearch);
  return transactionRuleListSearch({
    ...query,
    page: 1,
    q: normalizeSearch(q),
    ruleId: "",
  });
}

export function transactionRuleFilterUrl(
  currentSearch: string,
  categoryId: string,
): string {
  const query = transactionRuleListQuery(currentSearch);
  return transactionRuleListSearch({
    ...query,
    categoryId,
    page: 1,
    ruleId: "",
  });
}

export function transactionRulePageSizeUrl(
  currentSearch: string,
  pageSize: number,
): string {
  const query = transactionRuleListQuery(currentSearch);
  return transactionRuleListSearch({
    ...query,
    page: 1,
    pageSize: pageSizes.includes(pageSize as (typeof pageSizes)[number])
      ? pageSize
      : defaultPageSize,
    ruleId: "",
  });
}

export function transactionRuleAppliedFilters(
  directory: TransactionRuleDirectoryDto,
): string[] {
  const filters: string[] = [];
  if (directory.appliedFilters.q) {
    filters.push(`Поиск: ${directory.appliedFilters.q}`);
  }
  const category = directory.references.categories.find(
    (item) => item.id === directory.appliedFilters.categoryId,
  );
  if (category) filters.push(`Категория: ${category.name}`);
  return filters;
}

export function transactionRuleRangeLabel(
  page: number,
  pageSize: number,
  total: number,
): string {
  if (total === 0) return "0 правил";
  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);
  return `${first}–${last} из ${total}`;
}

function normalizeSearch(value: string): string {
  return value.trim().replace(/\s+/g, " ").slice(0, 200);
}

function validUuid(value: string | null): string {
  return value &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      value,
    )
    ? value
    : "";
}

function positiveInteger(value: string | null, fallback: number): number {
  if (!value || !/^\d+$/.test(value)) return fallback;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= 1 ? parsed : fallback;
}

function validPageSize(value: string | null): number {
  const parsed = positiveInteger(value, defaultPageSize);
  return pageSizes.includes(parsed as (typeof pageSizes)[number])
    ? parsed
    : defaultPageSize;
}
