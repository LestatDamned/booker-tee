import { todayIsoDate } from "../../shared/date/format-date";
import type { ReportOverviewDto } from "./api/reports-api";

export type ReportCategorySort =
  "turnover" | "name" | "income" | "expense" | "result";
export type ReportCategorySortDirection = "asc" | "desc";

const categorySorts = new Set<ReportCategorySort>([
  "turnover",
  "name",
  "income",
  "expense",
  "result",
]);

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
  search.delete("breakdown");
  search.delete("metric");
  const categorySort = reportCategorySort(currentSearch);
  const categorySortDirection = reportCategorySortDirection(currentSearch);
  setCategorySort(search, categorySort, categorySortDirection);
  return `?${search.toString()}`;
}

export function reportCategorySort(currentSearch: string): ReportCategorySort {
  const value = new URLSearchParams(currentSearch).get("category_sort");
  return categorySorts.has(value as ReportCategorySort)
    ? (value as ReportCategorySort)
    : "turnover";
}

export function reportCategorySortDirection(
  currentSearch: string,
): ReportCategorySortDirection {
  return new URLSearchParams(currentSearch).get("category_sort_dir") === "asc"
    ? "asc"
    : "desc";
}

export function reportCategorySortSearch(
  currentSearch: string,
  sort: ReportCategorySort,
): string {
  const search = new URLSearchParams(currentSearch);
  const currentSort = reportCategorySort(currentSearch);
  const currentDirection = reportCategorySortDirection(currentSearch);
  const direction =
    currentSort === sort
      ? currentDirection === "desc"
        ? "asc"
        : "desc"
      : sort === "name"
        ? "asc"
        : "desc";
  setCategorySort(search, sort, direction);
  return `?${search.toString()}`;
}

function setCategorySort(
  search: URLSearchParams,
  sort: ReportCategorySort,
  direction: ReportCategorySortDirection,
) {
  if (sort === "turnover" && direction === "desc") {
    search.delete("category_sort");
    search.delete("category_sort_dir");
    return;
  }
  search.set("category_sort", sort);
  if (direction === "desc") search.delete("category_sort_dir");
  else search.set("category_sort_dir", direction);
}

export function reportMonthSearch(
  overview: ReportOverviewDto,
  offset: number,
  currentSearch: string,
  now: Date = new Date(),
): string {
  const filters = reportFilterDraft(overview);
  const anchor = filters.dateFrom || filters.dateTo || todayIsoDate(now);
  const monthStart = addMonths(`${anchor.slice(0, 7)}-01`, offset);
  filters.dateFrom = monthStart;
  filters.dateTo = monthEnd(monthStart);
  return reportFilterSearch(filters, currentSearch);
}

export function reportCurrentMonthSearch(
  overview: ReportOverviewDto,
  currentSearch: string,
  now: Date = new Date(),
): string {
  const filters = reportFilterDraft(overview);
  const range = reportCurrentMonthRange(now);
  filters.dateFrom = range.dateFrom;
  filters.dateTo = range.dateTo;
  return reportFilterSearch(filters, currentSearch);
}

export function reportCurrentMonthRange(now: Date = new Date()): {
  dateFrom: string;
  dateTo: string;
} {
  const dateFrom = `${todayIsoDate(now).slice(0, 7)}-01`;
  return { dateFrom, dateTo: monthEnd(dateFrom) };
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

export function reportMonthlyExportHref(
  overview: ReportOverviewDto,
): string | null {
  const { currency, dateFrom, dateTo } = overview.appliedFilters;
  if (!dateFrom || !dateTo || !dateFrom.endsWith("-01")) return null;
  if (dateTo !== monthEnd(dateFrom)) return null;
  const search = new URLSearchParams({
    month: dateFrom.slice(0, 7),
    currency,
  });
  return `/api/v1/reports/export.xlsx?${search.toString()}`;
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

function setOrDelete(search: URLSearchParams, key: string, value: string) {
  if (value) search.set(key, value);
  else search.delete(key);
}
