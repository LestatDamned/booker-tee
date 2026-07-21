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

export function manualLedgerPaginationItems(
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
