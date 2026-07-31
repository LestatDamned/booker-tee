import type { ReportOverviewDto } from "./api/reports-api";

export type ReportFilterDraft = {
  dateFrom: string;
  dateTo: string;
  currency: string;
  accountId: string;
  categoryId: string;
  propertyId: string;
};

export function reportFilterDraft(
  overview: ReportOverviewDto,
): ReportFilterDraft {
  const filters = overview.appliedFilters;
  return {
    dateFrom: filters.dateFrom ?? "",
    dateTo: filters.dateTo ?? "",
    currency: filters.currency,
    accountId: filters.accountId ?? "",
    categoryId: filters.categoryId ?? "",
    propertyId: filters.propertyId ?? "",
  };
}

export function reportFilterSearch(
  draft: ReportFilterDraft,
  currentSearch: string,
): string {
  const search = new URLSearchParams(currentSearch);
  setOrDelete(search, "date_from", draft.dateFrom);
  setOrDelete(search, "date_to", draft.dateTo);
  setOrDelete(search, "currency", draft.currency);
  setOrDelete(search, "account_id", draft.accountId);
  setOrDelete(search, "category_id", draft.categoryId);
  setOrDelete(search, "property_id", draft.propertyId);
  search.delete("uncategorized_page");
  return `?${search.toString()}`;
}

export function reportMonthSearch(
  overview: ReportOverviewDto,
  offset: number,
  currentSearch: string,
): string {
  const filters = reportFilterDraft(overview);
  const anchor = filters.dateFrom || filters.dateTo || todayIso();
  const monthStart = addMonths(`${anchor.slice(0, 7)}-01`, offset);
  filters.dateFrom = monthStart;
  filters.dateTo = monthEnd(monthStart);
  return reportFilterSearch(filters, currentSearch);
}

export function reportCurrentMonthSearch(
  overview: ReportOverviewDto,
  currentSearch: string,
): string {
  const filters = reportFilterDraft(overview);
  const start = `${todayIso().slice(0, 7)}-01`;
  filters.dateFrom = start;
  filters.dateTo = monthEnd(start);
  return reportFilterSearch(filters, currentSearch);
}

export function reportAllTimeSearch(
  overview: ReportOverviewDto,
  currentSearch: string,
): string {
  const filters = reportFilterDraft(overview);
  filters.dateFrom = "";
  filters.dateTo = "";
  return reportFilterSearch(filters, currentSearch);
}

export function reportAppliedFilters(overview: ReportOverviewDto): string[] {
  const filters = overview.appliedFilters;
  const labels = [`Валюта: ${filters.currency}`];
  if (filters.dateFrom && filters.dateTo) {
    labels.push(`Период: ${filters.dateFrom}–${filters.dateTo}`);
  } else if (filters.dateFrom) {
    labels.push(`Период от: ${filters.dateFrom}`);
  } else if (filters.dateTo) {
    labels.push(`Период до: ${filters.dateTo}`);
  }
  const account = overview.filterOptions.accounts.find(
    (item) => item.id === filters.accountId,
  );
  const category = overview.filterOptions.categories.find(
    (item) => item.id === filters.categoryId,
  );
  const property = overview.filterOptions.properties.find(
    (item) => item.id === filters.propertyId,
  );
  if (account) labels.push(`Счёт: ${account.name}`);
  if (category) labels.push(`Категория: ${category.name}`);
  if (property) labels.push(`Объект: ${property.name}`);
  return labels;
}

function addMonths(monthStart: string, offset: number): string {
  const [year = 0, month = 1] = monthStart.split("-").map(Number);
  const value = new Date(Date.UTC(year, month - 1 + offset, 1));
  return value.toISOString().slice(0, 10);
}

function monthEnd(monthStart: string): string {
  const [year = 0, month = 1] = monthStart.split("-").map(Number);
  const value = new Date(Date.UTC(year, month, 0));
  return value.toISOString().slice(0, 10);
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function setOrDelete(search: URLSearchParams, key: string, value: string) {
  if (value) search.set(key, value);
  else search.delete(key);
}
