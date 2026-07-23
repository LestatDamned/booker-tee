import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import { Button } from "../../ui/button/button";
import { Field } from "../../ui/field/field";
import type { ImportDocumentListDto } from "./api/import-documents-api";
import {
  importDocumentFilterDraft,
  importDocumentFilterSearch,
} from "./import-document-filter-query";
import styles from "./import-document-list-page.module.css";

type ImportDocumentFiltersProps = {
  navigationPending: boolean;
  onClose: () => void;
  options: ImportDocumentListDto["filterOptions"];
};

export function ImportDocumentFilters({
  navigationPending,
  onClose,
  options,
}: ImportDocumentFiltersProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const [draft, setDraft] = useState(() =>
    importDocumentFilterDraft(location.search, options),
  );

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onClose();
    void navigate({
      pathname: location.pathname,
      search: importDocumentFilterSearch(draft, location.search),
    });
  }

  return (
    <form className={styles.filterForm} onSubmit={applyFilters}>
      <div className={styles.filterGrid}>
        <Field htmlFor="import-filter-account" label="Счёт">
          <select
            id="import-filter-account"
            onChange={(event) =>
              setDraft({ ...draft, accountId: event.currentTarget.value })
            }
            value={draft.accountId}
          >
            <option value="">Все счета</option>
            {options.accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name} · {account.currency}
              </option>
            ))}
          </select>
        </Field>
        <Field htmlFor="import-filter-period-from" label="Период выписки от">
          <input
            id="import-filter-period-from"
            onChange={(event) =>
              setDraft({ ...draft, periodFrom: event.currentTarget.value })
            }
            type="date"
            value={draft.periodFrom}
          />
        </Field>
        <Field htmlFor="import-filter-period-to" label="Период выписки до">
          <input
            id="import-filter-period-to"
            onChange={(event) =>
              setDraft({ ...draft, periodTo: event.currentTarget.value })
            }
            type="date"
            value={draft.periodTo}
          />
        </Field>
        <Field htmlFor="import-filter-sort" label="Сортировка">
          <select
            id="import-filter-sort"
            onChange={(event) =>
              setDraft({
                ...draft,
                sort:
                  event.currentTarget.value === "created_at_asc"
                    ? "created_at_asc"
                    : "created_at_desc",
              })
            }
            value={draft.sort}
          >
            <option value="created_at_desc">Сначала новые</option>
            <option value="created_at_asc">Сначала старые</option>
          </select>
        </Field>
      </div>
      <div className={styles.filterActions}>
        <Button
          icon="filterApply"
          isLoading={navigationPending}
          tone="primary"
          type="submit"
        >
          Применить
        </Button>
        <Link
          className={styles.resetLink}
          onClick={onClose}
          to={location.pathname}
        >
          Сбросить все
        </Link>
      </div>
    </form>
  );
}
