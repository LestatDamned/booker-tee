export function safeReportsReturnPath(value: string | null): string | null {
  if (!value || !value.startsWith("/")) return null;
  const parsed = new URL(value, "http://booker-tee.local");
  if (
    parsed.origin !== "http://booker-tee.local" ||
    parsed.pathname !== "/app/reports"
  ) {
    return null;
  }
  return `${parsed.pathname}${parsed.search}${parsed.hash}`;
}

export function categoryDetailApiSearch(currentSearch: string): string {
  const search = new URLSearchParams(currentSearch);
  search.delete("return_to");
  const value = search.toString();
  return value ? `?${value}` : "";
}

export function categoryDetailResetTarget(
  pathname: string,
  reportsReturnPath: string | null,
): string {
  if (!reportsReturnPath) return pathname;
  const search = new URLSearchParams({ return_to: reportsReturnPath });
  return `${pathname}?${search.toString()}`;
}

export function categoryDetailPageUrl(
  pathname: string,
  currentSearch: string,
  page: number,
): string {
  const search = new URLSearchParams(currentSearch);
  search.set("operations_page", String(page));
  return queryUrl(pathname, search);
}

export function categoryDetailSearchUrl(
  pathname: string,
  currentSearch: string,
  value: string,
): string {
  const search = new URLSearchParams(currentSearch);
  const normalized = value.trim();
  if (normalized) search.set("search", normalized);
  else search.delete("search");
  search.delete("operations_page");
  return queryUrl(pathname, search);
}

export function categoryDetailPageSizeUrl(
  pathname: string,
  currentSearch: string,
  pageSize: number,
): string {
  const search = new URLSearchParams(currentSearch);
  search.set("operations_page_size", String(pageSize));
  search.delete("operations_page");
  return queryUrl(pathname, search);
}

export function queryUrl(pathname: string, search: URLSearchParams): string {
  const value = search.toString();
  return value ? `${pathname}?${value}` : pathname;
}
