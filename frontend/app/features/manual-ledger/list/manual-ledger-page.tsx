import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import type { SessionDto } from "../../../api/session";
import { AppShell } from "../../../shell/app-shell";
import { Button } from "../../../ui/button/button";
import { PageHeader } from "../../../ui/page-header/page-header";
import { RequestState } from "../../../ui/request-state/request-state";
import { WorkbenchPanel } from "../../../ui/workbench-panel/workbench-panel";
import type {
  ManualLedgerDto,
  ManualOperationDto,
} from "../api/manual-ledger-api";
import { ManualOperationCreate } from "../operation/manual-operation-create";
import { ManualOperationRow } from "../operation/manual-operation-row";
import {
  manualOperationsTotalLabel,
  toManualOperationRowModel,
} from "../operation/manual-ledger-model";
import {
  manualLedgerAppliedFilters,
  manualLedgerFiltersAreActive,
} from "./manual-ledger-filter-query";
import { ManualLedgerFilters } from "./manual-ledger-filters";
import { ManualLedgerPageSize } from "./manual-ledger-page-size";
import {
  manualLedgerPaginationItems,
  manualLedgerPaginationRangeLabel,
  manualLedgerPageUrl,
} from "./manual-ledger-pagination";
import { ManualLedgerSearch } from "./manual-ledger-search";
import {
  emptyManualLedgerLocalChanges,
  reconcileManualLedgerLocalChanges,
  recordManualOperationDeletion,
  recordManualOperationUpdate,
  visibleManualOperations,
} from "./manual-ledger-reconciliation";
import styles from "../manual-ledger.module.css";

type ManualLedgerPageProps = {
  ledger: ManualLedgerDto;
  navigationPending?: boolean;
  onOperationDeleted?: (operationId: string) => void;
  onRefresh?: () => void;
  onOperationUpdated?: (operation: ManualOperationDto) => void;
  session: SessionDto;
};

export function ManualLedgerPage({
  ledger,
  navigationPending = false,
  onOperationDeleted,
  onRefresh,
  onOperationUpdated,
  session,
}: ManualLedgerPageProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const [localChanges, setLocalChanges] = useState(
    emptyManualLedgerLocalChanges,
  );
  const [workingOperationId, setWorkingOperationId] = useState<string | null>(
    null,
  );
  const [editingOperationId, setEditingOperationId] = useState<string | null>(
    null,
  );
  const [createOpen, setCreateOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const filtersActive = manualLedgerFiltersAreActive(location.search);
  const [panelPending, setPanelPending] = useState(false);
  const appliedFilters = manualLedgerAppliedFilters(
    location.search,
    ledger.filterOptions,
  );
  const reconciledLocalChanges = reconcileManualLedgerLocalChanges(
    localChanges,
    ledger.items,
  );
  const deletedItemsOnPage = ledger.items.filter(
    (operation) => reconciledLocalChanges.deleted[operation.id],
  ).length;
  const visibleTotal = ledger.pagination.total - deletedItemsOnPage;
  const rows = visibleManualOperations(
    ledger.items,
    reconciledLocalChanges,
  ).map(toManualOperationRowModel);
  const showPageSize = ledger.filterOptions.perPage.some(
    (option) => visibleTotal > option,
  );

  function operationUpdated(operation: ManualOperationDto) {
    setLocalChanges((current) =>
      recordManualOperationUpdate(
        reconcileManualLedgerLocalChanges(current, ledger.items),
        operation,
      ),
    );
    onOperationUpdated?.(operation);
  }

  function operationDeleted(operationId: string) {
    if (workingOperationId === operationId) {
      setWorkingOperationId(null);
    }
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
    setLocalChanges((current) =>
      recordManualOperationDeletion(
        reconcileManualLedgerLocalChanges(current, ledger.items),
        operationId,
      ),
    );
    onOperationDeleted?.(operationId);
  }

  function closeCreate() {
    setCreateOpen(false);
    setPanelPending(false);
  }

  function openEdit(operationId: string) {
    setWorkingOperationId(operationId);
    setEditingOperationId(operationId);
  }

  function closeEdit() {
    setEditingOperationId(null);
    setWorkingOperationId(null);
  }
  return (
    <AppShell session={session}>
      <section className={styles.page}>
        <section aria-busy={navigationPending} className={styles.workbench}>
          <div className={styles.workbenchHeader}>
            <PageHeader
              description={
                ledger.capabilities.readonlyReason ??
                "Доходы, расходы и переводы, созданные вручную."
              }
              eyebrow={manualOperationsTotalLabel(visibleTotal)}
              title="Ручные операции"
            />
          </div>

          <section aria-label="Инструменты списка" className={styles.listTools}>
            <div className={styles.listToolActions}>
              <ManualLedgerSearch
                key={new URLSearchParams(location.search).get("search") ?? ""}
                disabled={editingOperationId !== null || navigationPending}
              />
              <Button
                aria-controls="manual-ledger-filter-region"
                aria-expanded={filtersOpen}
                disabled={editingOperationId !== null || navigationPending}
                onClick={() => setFiltersOpen((current) => !current)}
              >
                {filtersOpen ? "Скрыть фильтры" : "Показать фильтры"}
                {appliedFilters.length > 0 ? (
                  <span aria-hidden="true"> ({appliedFilters.length})</span>
                ) : null}
              </Button>
              {ledger.capabilities.canCreate ? (
                <Button
                  aria-haspopup="dialog"
                  disabled={editingOperationId !== null}
                  onClick={() => setCreateOpen(true)}
                  tone="primary"
                >
                  Добавить операцию
                </Button>
              ) : null}
            </div>
            {appliedFilters.length > 0 ? (
              <div className={styles.activeFilterSummary}>
                <ul
                  aria-label="Применённые фильтры"
                  className={styles.appliedFilters}
                >
                  {appliedFilters.map((filter) => (
                    <li key={filter}>{filter}</li>
                  ))}
                </ul>
                <Link className={styles.resetLink} to={location.pathname}>
                  Сбросить все
                </Link>
              </div>
            ) : null}
          </section>

          {filtersOpen ? (
            <div
              className={styles.filterRegion}
              id="manual-ledger-filter-region"
            >
              <ManualLedgerFilters
                key={location.search}
                navigationPending={navigationPending}
                onClose={() => setFiltersOpen(false)}
                options={ledger.filterOptions}
                perPage={ledger.pagination.perPage}
              />
            </div>
          ) : null}

          <span aria-live="polite" className={styles.navigationStatus}>
            {navigationPending ? "Обновляем операции…" : ""}
          </span>

          <section
            aria-label="Список операций"
            className={styles.listRegion}
            data-empty={rows.length === 0 ? "true" : undefined}
          >
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
              <ol className={styles.list}>
                {rows.map((operation) => (
                  <li key={operation.id}>
                    <ManualOperationRow
                      csrfToken={session.csrfToken}
                      isEditing={editingOperationId === operation.id}
                      isTargeted={ledger.targetOperationId === operation.id}
                      isWorking={workingOperationId === operation.id}
                      onDeleted={operationDeleted}
                      onEdit={openEdit}
                      onEditClosed={closeEdit}
                      {...(onRefresh === undefined ? {} : { onRefresh })}
                      onOperationUpdated={operationUpdated}
                      onWorkStarted={() => setWorkingOperationId(operation.id)}
                      operation={operation}
                    />
                  </li>
                ))}
              </ol>
            )}
          </section>

          <footer className={styles.workbenchFooter}>
            <span aria-live="polite" className={styles.paginationSummary}>
              {manualLedgerPaginationRangeLabel(
                ledger.pagination.page,
                ledger.pagination.perPage,
                visibleTotal,
              )}
            </span>
            {showPageSize ? (
              <ManualLedgerPageSize
                disabled={editingOperationId !== null || navigationPending}
                options={ledger.filterOptions.perPage}
                value={ledger.pagination.perPage}
              />
            ) : null}
            {ledger.pagination.totalPages > 1 ? (
              <nav aria-label="Страницы операций" className={styles.pagination}>
                <ul>
                  <li className={styles.previousPage}>
                    {ledger.pagination.hasPrevious ? (
                      <Link
                        to={manualLedgerPageUrl(
                          location.search,
                          ledger.pagination.page - 1,
                        )}
                      >
                        Назад
                      </Link>
                    ) : null}
                  </li>
                  {manualLedgerPaginationItems(
                    ledger.pagination.page,
                    ledger.pagination.totalPages,
                  ).map((item) =>
                    typeof item === "number" ? (
                      <li key={item}>
                        {item === ledger.pagination.page ? (
                          <span
                            aria-current="page"
                            className={styles.currentPage}
                          >
                            <span className="visually-hidden">Страница </span>
                            {item}
                          </span>
                        ) : (
                          <Link to={manualLedgerPageUrl(location.search, item)}>
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
                    {ledger.pagination.hasNext ? (
                      <Link
                        to={manualLedgerPageUrl(
                          location.search,
                          ledger.pagination.page + 1,
                        )}
                      >
                        Дальше
                      </Link>
                    ) : null}
                  </li>
                </ul>
              </nav>
            ) : null}
          </footer>
        </section>
      </section>

      {createOpen ? (
        <WorkbenchPanel
          description="Доход, расход или перевод вручную."
          disabled={panelPending}
          onClose={closeCreate}
          title="Новая операция"
        >
          <ManualOperationCreate
            csrfToken={session.csrfToken}
            onClose={closeCreate}
            onPendingChange={setPanelPending}
            options={ledger.filterOptions}
          />
        </WorkbenchPanel>
      ) : null}
    </AppShell>
  );
}
