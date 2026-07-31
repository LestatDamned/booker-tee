import { Link } from "react-router";

import { Icon } from "../icon/icon";
import styles from "./workbench-pagination.module.css";

type WorkbenchPaginationPageSize = {
  disabled?: boolean;
  id: string;
  label?: string;
  onChange: (value: number) => void;
  options: readonly number[];
  value: number;
};

type WorkbenchPaginationProps = {
  ariaLabel: string;
  currentPage: number;
  getPageHref: (page: number) => string;
  hasNext: boolean;
  hasPrevious: boolean;
  pageSize?: WorkbenchPaginationPageSize;
  summary: string;
  totalPages: number;
};

export function WorkbenchPagination({
  ariaLabel,
  currentPage,
  getPageHref,
  hasNext,
  hasPrevious,
  pageSize,
  summary,
  totalPages,
}: WorkbenchPaginationProps) {
  const items = paginationItems(currentPage, totalPages);

  return (
    <footer className={styles.footer}>
      <span aria-live="polite" className={styles.summary}>
        {summary}
      </span>
      {pageSize ? (
        <label className={styles.pageSize} htmlFor={pageSize.id}>
          {pageSize.label ?? "На странице"}
          <select
            disabled={pageSize.disabled}
            id={pageSize.id}
            onChange={(event) =>
              pageSize.onChange(Number(event.currentTarget.value))
            }
            value={String(pageSize.value)}
          >
            {pageSize.options.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {totalPages > 1 ? (
        <nav aria-label={ariaLabel} className={styles.pagination}>
          <ul>
            <li className={styles.previousPage}>
              {hasPrevious ? (
                <Link to={getPageHref(currentPage - 1)}>
                  <Icon name="back" size={16} />
                  Назад
                </Link>
              ) : null}
            </li>
            {items.map((item) =>
              typeof item === "number" ? (
                <li key={item}>
                  {item === currentPage ? (
                    <span
                      aria-current="page"
                      aria-label={`Страница ${item}`}
                      className={styles.currentPage}
                    >
                      {item}
                    </span>
                  ) : (
                    <Link
                      aria-label={`Страница ${item}`}
                      to={getPageHref(item)}
                    >
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
              {hasNext ? (
                <Link to={getPageHref(currentPage + 1)}>
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

function paginationItems(
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
