import type { ImportDocumentListDto } from "./api/import-documents-api";

export type ImportDocumentFilterDraft = {
  accountId: string;
  periodFrom: string;
  periodTo: string;
  sort: "created_at_desc" | "created_at_asc";
};

export function importDocumentFilterDraft(
  currentSearch: string,
  options: ImportDocumentListDto["filterOptions"],
): ImportDocumentFilterDraft {
  const search = new URLSearchParams(currentSearch);
  const requestedAccountId = search.get("account_id") ?? "";
  return {
    accountId: options.accounts.some(
      (account) => account.id === requestedAccountId,
    )
      ? requestedAccountId
      : "",
    periodFrom: validIsoDate(search.get("period_from")),
    periodTo: validIsoDate(search.get("period_to")),
    sort:
      search.get("sort") === "created_at_asc"
        ? "created_at_asc"
        : "created_at_desc",
  };
}

export function importDocumentFilterSearch(
  draft: ImportDocumentFilterDraft,
  currentSearch: string,
): string {
  const search = new URLSearchParams(currentSearch);
  setOrDelete(search, "account_id", draft.accountId);
  setOrDelete(search, "period_from", draft.periodFrom);
  setOrDelete(search, "period_to", draft.periodTo);
  if (draft.sort === "created_at_asc") {
    search.set("sort", draft.sort);
  } else {
    search.delete("sort");
  }
  search.set("page", "1");
  return `?${search.toString()}`;
}

export function importDocumentStateUrl(
  currentSearch: string,
  state: string | null,
): string {
  const search = new URLSearchParams(currentSearch);
  setOrDelete(search, "state", state ?? "");
  search.set("page", "1");
  return `?${search.toString()}`;
}

export function importDocumentPageUrl(
  currentSearch: string,
  page: number,
): string {
  const search = new URLSearchParams(currentSearch);
  search.set("page", String(page));
  return `?${search.toString()}`;
}

export function importDocumentFiltersAreActive(currentSearch: string): boolean {
  const search = new URLSearchParams(currentSearch);
  return ["state", "account_id", "period_from", "period_to"].some((key) =>
    Boolean(search.get(key)),
  );
}

export function importDocumentAdvancedFilterCount(
  currentSearch: string,
): number {
  const search = new URLSearchParams(currentSearch);
  return (
    Number(Boolean(search.get("account_id"))) +
    Number(Boolean(search.get("period_from") || search.get("period_to")))
  );
}

export function importDocumentPaginationRangeLabel(
  page: number,
  perPage: number,
  total: number,
): string {
  if (total === 0) {
    return "0 документов";
  }
  const first = (page - 1) * perPage + 1;
  const last = Math.min(page * perPage, total);
  return `${first}–${last} из ${total}`;
}

export function importDocumentPaginationItems(
  currentPage: number,
  totalPages: number,
): (number | string)[] {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }
  const pages = [
    ...new Set([1, currentPage - 1, currentPage, currentPage + 1, totalPages]),
  ]
    .filter((page) => page >= 1 && page <= totalPages)
    .sort((left, right) => left - right);
  return pages.flatMap((page, index) => {
    const previous = pages[index - 1];
    return previous !== undefined && page - previous > 1
      ? [`ellipsis-${previous}`, page]
      : [page];
  });
}

function validIsoDate(value: string | null): string {
  return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : "";
}

function setOrDelete(search: URLSearchParams, key: string, value: string) {
  if (value) {
    search.set(key, value);
  } else {
    search.delete(key);
  }
}
