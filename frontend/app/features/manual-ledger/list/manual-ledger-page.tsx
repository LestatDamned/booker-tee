import { useState } from "react";
import { useLocation, useNavigate } from "react-router";

import type { SessionDto } from "../../../api/session";
import { AppShell } from "../../../shell/app-shell";
import { AppliedFilterSummary } from "../../../ui/applied-filter-summary/applied-filter-summary";
import { Badge } from "../../../ui/badge/badge";
import { Button, RouterButtonLink } from "../../../ui/button/button";
import { PageFrame } from "../../../ui/page-frame/page-frame";
import { PageHeader } from "../../../ui/page-header/page-header";
import { WorkbenchEmptyState } from "../../../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchPanel } from "../../../ui/workbench-panel/workbench-panel";
import { WorkbenchPagination } from "../../../ui/workbench-pagination/workbench-pagination";
import { WorkbenchContent } from "../../../ui/workbench-content/workbench-content";
import { WorkbenchFilterRegion } from "../../../ui/workbench-content/workbench-filter-region";
import { WorkbenchStatus } from "../../../ui/workbench-content/workbench-status";
import { WorkbenchHeader } from "../../../ui/workbench-surface/workbench-header";
import { WorkbenchSurface } from "../../../ui/workbench-surface/workbench-surface";
import { WorkbenchToolbar } from "../../../ui/workbench-toolbar/workbench-toolbar";
import { ToastViewport, useToastQueue } from "../../../ui/toast/toast";
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
import {
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
  const { dismissToast, showToast, toast } = useToastQueue();

  const filtersActive = manualLedgerFiltersAreActive(location.search);
  const [panelPending, setPanelPending] = useState(false);
  const appliedFilters = manualLedgerAppliedFilters(
    location.search,
    ledger.filterOptions,
  );
  const displayedItems =
    ledger.targetOperation &&
    !ledger.items.some(
      (operation) => operation.id === ledger.targetOperation?.id,
    )
      ? [ledger.targetOperation, ...ledger.items]
      : ledger.items;
  const reconciledLocalChanges = reconcileManualLedgerLocalChanges(
    localChanges,
    displayedItems,
  );
  const deletedItemsOnPage = ledger.items.filter(
    (operation) => reconciledLocalChanges.deleted[operation.id],
  ).length;
  const visibleTotal = ledger.pagination.total - deletedItemsOnPage;
  const rows = visibleManualOperations(
    displayedItems,
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
      <PageFrame>
        <WorkbenchSurface
          aria-busy={navigationPending}
          className={styles.workbench}
        >
          <WorkbenchHeader>
            <PageHeader
              description={
                ledger.capabilities.readonlyReason ??
                "Доходы, расходы и переводы, созданные вручную."
              }
              eyebrow={manualOperationsTotalLabel(visibleTotal)}
              title="Ручные операции"
            />
          </WorkbenchHeader>

          <WorkbenchToolbar>
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
                icon="filter"
              >
                {filtersOpen ? "Скрыть фильтры" : "Показать фильтры"}
                {appliedFilters.length > 0 ? (
                  <Badge>{appliedFilters.length}</Badge>
                ) : null}
              </Button>
              {ledger.capabilities.canCreate ? (
                <Button
                  aria-haspopup="dialog"
                  disabled={editingOperationId !== null}
                  onClick={() => setCreateOpen(true)}
                  tone="primary"
                  icon="plus"
                >
                  Добавить операцию
                </Button>
              ) : null}
            </div>
            <AppliedFilterSummary
              filters={filtersOpen ? [] : appliedFilters}
              resetTo={location.pathname}
            />
          </WorkbenchToolbar>

          {filtersOpen ? (
            <WorkbenchFilterRegion id="manual-ledger-filter-region">
              <ManualLedgerFilters
                key={location.search}
                navigationPending={navigationPending}
                onClose={() => setFiltersOpen(false)}
                options={ledger.filterOptions}
                perPage={ledger.pagination.perPage}
              />
            </WorkbenchFilterRegion>
          ) : null}

          <WorkbenchStatus>
            {navigationPending ? "Обновляем операции…" : ""}
          </WorkbenchStatus>

          <WorkbenchContent
            aria-label="Список операций"
            isEmpty={rows.length === 0}
          >
            {rows.length === 0 ? (
              <WorkbenchEmptyState
                action={
                  filtersActive ? (
                    <RouterButtonLink icon="filter" to={location.pathname}>
                      Сбросить фильтры
                    </RouterButtonLink>
                  ) : ledger.capabilities.canCreate ? (
                    <Button
                      icon="plus"
                      onClick={() => setCreateOpen(true)}
                      tone="primary"
                    >
                      Добавить первую операцию
                    </Button>
                  ) : undefined
                }
                icon={filtersActive ? "search" : "operations"}
                kind={filtersActive ? "filtered" : "primary"}
                title={
                  filtersActive
                    ? "По этим фильтрам операций нет"
                    : "Операций пока нет"
                }
              >
                {filtersActive
                  ? "Измените условия поиска или сбросьте фильтры."
                  : "Созданные вручную операции появятся здесь."}
              </WorkbenchEmptyState>
            ) : (
              <ol className={styles.list}>
                {rows.map((operation) => (
                  <li key={operation.id}>
                    <ManualOperationRow
                      csrfToken={session.csrfToken}
                      isEditing={editingOperationId === operation.id}
                      isWorking={workingOperationId === operation.id}
                      onDeleted={operationDeleted}
                      onEdit={openEdit}
                      onEditClosed={closeEdit}
                      {...(onRefresh === undefined ? {} : { onRefresh })}
                      onOperationUpdated={operationUpdated}
                      onWorkStarted={() => setWorkingOperationId(operation.id)}
                      onSuccess={(message) => showToast({ message })}
                      operation={operation}
                    />
                  </li>
                ))}
              </ol>
            )}
          </WorkbenchContent>

          <WorkbenchPagination
            ariaLabel="Страницы операций"
            currentPage={ledger.pagination.page}
            getPageHref={(page) => manualLedgerPageUrl(location.search, page)}
            hasNext={ledger.pagination.hasNext}
            hasPrevious={ledger.pagination.hasPrevious}
            {...(showPageSize
              ? {
                  pageSize: {
                    disabled: editingOperationId !== null || navigationPending,
                    id: "manual-ledger-page-size",
                    onChange: (pageSize: number) => {
                      if (!ledger.filterOptions.perPage.includes(pageSize)) {
                        return;
                      }
                      const search = new URLSearchParams(location.search);
                      search.set("page", "1");
                      search.set("per_page", String(pageSize));
                      void navigate({
                        pathname: location.pathname,
                        search: `?${search.toString()}`,
                      });
                    },
                    options: ledger.filterOptions.perPage,
                    value: ledger.pagination.perPage,
                  },
                }
              : {})}
            summary={manualLedgerPaginationRangeLabel(
              ledger.pagination.page,
              ledger.pagination.perPage,
              visibleTotal,
            )}
            totalPages={ledger.pagination.totalPages}
          />
        </WorkbenchSurface>
      </PageFrame>

      <ToastViewport onDismiss={dismissToast} toast={toast} />

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
            onCreated={() => showToast({ message: "Ручная операция создана." })}
            onPendingChange={setPanelPending}
            options={ledger.filterOptions}
          />
        </WorkbenchPanel>
      ) : null}
    </AppShell>
  );
}
