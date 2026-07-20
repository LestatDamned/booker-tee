import { Link, useLocation } from "react-router";

import type { SessionDto } from "../../api/session";
import { AppShell } from "../../shell/app-shell";
import { PageHeader } from "../../ui/page-header/page-header";
import { RequestState } from "../../ui/request-state/request-state";
import type { ManualLedgerDto } from "./manual-ledger-api";
import {
  ManualLedgerFilters,
  manualLedgerFiltersAreActive,
} from "./manual-ledger-filters";
import styles from "./manual-ledger.module.css";
import {
  manualOperationsTotalLabel,
  toManualOperationRowModel,
} from "./manual-ledger-model";
import { ManualOperationRow } from "./manual-operation-row";

type ManualLedgerPageProps = {
  ledger: ManualLedgerDto;
  session: SessionDto;
};

export function ManualLedgerPage({ ledger, session }: ManualLedgerPageProps) {
  const location = useLocation();
  const filtersActive = manualLedgerFiltersAreActive(location.search);
  const rows = ledger.items.map(toManualOperationRowModel);
  return (
    <AppShell session={session}>
      <section className={styles.page}>
        <PageHeader
          description={
            ledger.capabilities.readonlyReason ??
            "Доходы, расходы и переводы, созданные вручную."
          }
          eyebrow={manualOperationsTotalLabel(ledger.pagination.total)}
          title="Ручные операции"
        />

        <ManualLedgerFilters
          key={location.search}
          options={ledger.filterOptions}
          paginationPerPage={ledger.pagination.perPage}
        />

        {rows.length === 0 ? (
          <RequestState
            message={
              filtersActive
                ? "Измените условия поиска или сбросьте фильтры."
                : "Созданные вручную операции появятся здесь."
            }
            status="empty"
            title={
              filtersActive
                ? "По этим фильтрам операций нет"
                : "Операций пока нет"
            }
          />
        ) : (
          <div className={styles.list}>
            {rows.map((operation) => (
              <ManualOperationRow
                isTargeted={ledger.targetOperationId === operation.id}
                key={operation.id}
                operation={operation}
              />
            ))}
          </div>
        )}

        {ledger.pagination.totalPages > 1 ? (
          <nav aria-label="Страницы операций" className={styles.pagination}>
            {ledger.pagination.hasPrevious ? (
              <Link to={pageUrl(location.search, ledger.pagination.page - 1)}>
                Назад
              </Link>
            ) : (
              <span />
            )}
            <span>
              Страница {ledger.pagination.page} из{" "}
              {ledger.pagination.totalPages}
            </span>
            {ledger.pagination.hasNext ? (
              <Link to={pageUrl(location.search, ledger.pagination.page + 1)}>
                Дальше
              </Link>
            ) : (
              <span />
            )}
          </nav>
        ) : null}
      </section>
    </AppShell>
  );
}

function pageUrl(currentSearch: string, page: number): string {
  const search = new URLSearchParams(currentSearch);
  search.set("page", String(page));
  return `?${search.toString()}`;
}
