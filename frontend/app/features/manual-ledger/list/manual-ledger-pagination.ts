export function manualLedgerPageUrl(
  currentSearch: string,
  page: number,
): string {
  const search = new URLSearchParams(currentSearch);
  search.set("page", String(page));
  return `?${search.toString()}`;
}

export function manualLedgerPaginationRangeLabel(
  page: number,
  perPage: number,
  total: number,
): string {
  if (total === 0) return "0 операций";
  const first = (page - 1) * perPage + 1;
  const last = Math.min(page * perPage, total);
  return `${first}–${last} из ${total}`;
}
