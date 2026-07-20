import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import type { SessionDto } from "../../api/session";
import { AppShell } from "../../shell/app-shell";
import { PageHeader } from "../../ui/page-header/page-header";
import { RequestState } from "../../ui/request-state/request-state";
import type { ManualLedgerDto, ManualOperationDto } from "./manual-ledger-api";
import {
  ManualLedgerFilters,
  manualLedgerFiltersAreActive,
} from "./manual-ledger-filters";
import { ManualOperationCreate } from "./manual-operation-create";
import styles from "./manual-ledger.module.css";
import {
  manualOperationsTotalLabel,
  toManualOperationRowModel,
} from "./manual-ledger-model";
import { ManualOperationRow } from "./manual-operation-row";

type ManualLedgerPageProps = {
  ledger: ManualLedgerDto;
  onOperationDeleted?: (operationId: string) => void;
  onRefresh?: () => void;
  onOperationUpdated?: (operation: ManualOperationDto) => void;
  session: SessionDto;
};

export function ManualLedgerPage({
  ledger,
  onOperationDeleted,
  onRefresh,
  onOperationUpdated,
  session,
}: ManualLedgerPageProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const [updatedOperations, setUpdatedOperations] = useState<
    Record<string, ManualOperationDto>
  >({});
  const [deletedOperationIds, setDeletedOperationIds] = useState<
    Record<string, true>
  >({});

  const filtersActive = manualLedgerFiltersAreActive(location.search);
  const deletedItemsOnPage = ledger.items.filter(
    (operation) => deletedOperationIds[operation.id],
  ).length;
  const visibleTotal = ledger.pagination.total - deletedItemsOnPage;
  const rows = ledger.items
    .filter((operation) => !deletedOperationIds[operation.id])
    .map((operation) => {
      const updated = updatedOperations[operation.id];
      return toManualOperationRowModel(
        updated && updated.version > operation.version ? updated : operation,
      );
    });

  function operationUpdated(operation: ManualOperationDto) {
    setUpdatedOperations((current) => ({
      ...current,
      [operation.id]: operation,
    }));
    onOperationUpdated?.(operation);
  }

  function operationDeleted(operationId: string) {
    if (ledger.targetOperationId === operationId) {
      const search = new URLSearchParams(location.search);
      search.delete("operation_id");
      void navigate(
        {
          pathname: location.pathname,
          search: search.size > 0 ? `?${search.toString()}` : "",
          hash: "",
        },
        { replace: true },
      );
      return;
    }
    setDeletedOperationIds((current) => ({ ...current, [operationId]: true }));
    onOperationDeleted?.(operationId);
  }
  return (
    <AppShell session={session}>
      <section className={styles.page}>
        <PageHeader
          description={
            ledger.capabilities.readonlyReason ??
            "Доходы, расходы и переводы, созданные вручную."
          }
          eyebrow={manualOperationsTotalLabel(visibleTotal)}
          title="Ручные операции"
        />

        <ManualOperationCreate
          canCreate={ledger.capabilities.canCreate}
          csrfToken={session.csrfToken}
          options={ledger.filterOptions}
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
                csrfToken={session.csrfToken}
                isTargeted={ledger.targetOperationId === operation.id}
                key={operation.id}
                onDeleted={operationDeleted}
                {...(onRefresh === undefined ? {} : { onRefresh })}
                onOperationUpdated={operationUpdated}
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
