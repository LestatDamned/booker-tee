import { Link, useLocation, useNavigate } from "react-router";

import { Icon } from "../../ui/icon/icon";
import type { ImportDocumentListDto } from "./api/import-documents-api";
import {
  importDocumentPageUrl,
  importDocumentPaginationItems,
  importDocumentPaginationRangeLabel,
} from "./import-document-filter-query";
import styles from "./import-document-list-page.module.css";

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

  function changePageSize(nextValue: string) {
    const pageSize = Number(nextValue);
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

  return (
    <footer className={styles.paginationFooter}>
      <span aria-live="polite" className={styles.paginationSummary}>
        {importDocumentPaginationRangeLabel(
          pagination.page,
          pagination.perPage,
          pagination.total,
        )}
      </span>
      {smallestPageSize !== undefined &&
      documents.summary.totalDocumentCount > smallestPageSize ? (
        <label className={styles.pageSize} htmlFor="import-page-size">
          На странице
          <select
            disabled={disabled}
            id="import-page-size"
            onChange={(event) => changePageSize(event.currentTarget.value)}
            value={String(pagination.perPage)}
          >
            {documents.filterOptions.perPage.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {pagination.totalPages > 1 ? (
        <nav aria-label="Страницы документов" className={styles.pagination}>
          <ul>
            <li className={styles.previousPage}>
              {pagination.hasPrevious ? (
                <Link
                  to={importDocumentPageUrl(
                    location.search,
                    pagination.page - 1,
                  )}
                >
                  <Icon name="back" size={16} />
                  Назад
                </Link>
              ) : null}
            </li>
            {importDocumentPaginationItems(
              pagination.page,
              pagination.totalPages,
            ).map((item) =>
              typeof item === "number" ? (
                <li key={item}>
                  {item === pagination.page ? (
                    <span aria-current="page" className={styles.currentPage}>
                      <span className="visually-hidden">Страница </span>
                      {item}
                    </span>
                  ) : (
                    <Link to={importDocumentPageUrl(location.search, item)}>
                      <span className="visually-hidden">Страница </span>
                      {item}
                    </Link>
                  )}
                </li>
              ) : (
                <li aria-hidden="true" key={item}>
                  …
                </li>
              ),
            )}
            <li className={styles.nextPage}>
              {pagination.hasNext ? (
                <Link
                  to={importDocumentPageUrl(
                    location.search,
                    pagination.page + 1,
                  )}
                >
                  Дальше
                  <Icon name="forward" size={16} />
                </Link>
              ) : null}
            </li>
          </ul>
        </nav>
      ) : null}
    </footer>
  );
}
