import { useLocation, useNavigate } from "react-router";

import { WorkbenchPagination } from "../../ui/workbench-pagination/workbench-pagination";
import type { ImportDocumentListDto } from "./api/import-documents-api";
import {
  importDocumentPageUrl,
  importDocumentPaginationRangeLabel,
} from "./import-document-filter-query";

export function ImportDocumentPagination({
  disabled,
  documents,
}: {
  disabled: boolean;
  documents: ImportDocumentListDto;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const { pagination } = documents;
  const smallestPageSize = documents.filterOptions.perPage[0];

  function changePageSize(pageSize: number) {
    if (!documents.filterOptions.perPage.includes(pageSize)) {
      return;
    }
    const search = new URLSearchParams(location.search);
    search.set("page", "1");
    search.set("per_page", String(pageSize));
    void navigate({
      pathname: location.pathname,
      search: `?${search.toString()}`,
    });
  }

  const showPageSize =
    smallestPageSize !== undefined &&
    documents.summary.totalDocumentCount > smallestPageSize;

  return (
    <WorkbenchPagination
      ariaLabel="Страницы документов"
      currentPage={pagination.page}
      getPageHref={(page) => importDocumentPageUrl(location.search, page)}
      hasNext={pagination.hasNext}
      hasPrevious={pagination.hasPrevious}
      {...(showPageSize
        ? {
            pageSize: {
              disabled,
              id: "import-page-size",
              onChange: changePageSize,
              options: documents.filterOptions.perPage,
              value: pagination.perPage,
            },
          }
        : {})}
      summary={importDocumentPaginationRangeLabel(
        pagination.page,
        pagination.perPage,
        pagination.total,
      )}
      totalPages={pagination.totalPages}
    />
  );
}
