import { useRef, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router";

import type { SessionDto } from "../../api/session";
import { formatMoneyAmount } from "../../shared/money/format-money";
import { AppShell } from "../../shell/app-shell";
import { ActionStack } from "../../ui/action-stack/action-stack";
import { AppliedFilterSummary } from "../../ui/applied-filter-summary/applied-filter-summary";
import { BackLink } from "../../ui/back-link/back-link";
import { Badge } from "../../ui/badge/badge";
import { Button, ButtonLink, RouterButtonLink } from "../../ui/button/button";
import { ExpansionPanel } from "../../ui/expansion-panel/expansion-panel";
import { Field } from "../../ui/field/field";
import { FormActions } from "../../ui/field/form-layout";
import { MoneyValue } from "../../ui/money-value/money-value";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import { StatusLabel } from "../../ui/status-label/status-label";
import { Tag } from "../../ui/tag/tag";
import { WorkbenchRow } from "../../ui/workbench-row/workbench-row";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchPagination } from "../../ui/workbench-pagination/workbench-pagination";
import { WorkbenchContent } from "../../ui/workbench-content/workbench-content";
import { WorkbenchFilterRegion } from "../../ui/workbench-content/workbench-filter-region";
import { WorkbenchStatus } from "../../ui/workbench-content/workbench-status";
import { WorkbenchHeader } from "../../ui/workbench-surface/workbench-header";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import { WorkbenchSearch } from "../../ui/workbench-toolbar/workbench-search";
import { WorkbenchToolbar } from "../../ui/workbench-toolbar/workbench-toolbar";
import { ToastViewport, useToastQueue } from "../../ui/toast/toast";
import type { AccountDetailDto } from "./api/account-detail-api";
import type { AccountSummaryDto } from "./api/accounts-api";
import {
  accountBalanceTone,
  accountMovementAppliedFilters,
  accountMovementsLabel,
  accountTypeLabels,
  movementView,
  operationSources,
  operationStatuses,
  operationTypes,
} from "./account-detail-model";
import { AccountSettingsPanel } from "./account-settings-panel";
import {
  ImportedOperationCorrectionPanel,
  type ImportedOperationCorrectionPanelHandle,
} from "./imported-operation-correction-panel";
import styles from "./account-detail-page.module.css";

type Props = {
  detail: AccountDetailDto;
  navigationPending?: boolean;
  session: SessionDto;
};

export function AccountDetailPage({
  detail,
  navigationPending = false,
  session,
}: Props) {
  const location = useLocation();
  const navigate = useNavigate();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [editingMovement, setEditingMovement] = useState<
    AccountDetailDto["items"][number] | null
  >(null);
  const [movementOverrides, setMovementOverrides] = useState<
    Record<
      string,
      {
        sourceVersion: number;
        value: AccountDetailDto["items"][number];
      }
    >
  >({});
  const [accountOverride, setAccountOverride] = useState<{
    sourceUpdatedAt: string;
    value: AccountDetailDto["account"];
  } | null>(null);
  const { dismissToast, showToast, toast } = useToastQueue();
  const account =
    accountOverride?.sourceUpdatedAt === detail.account.updatedAt
      ? accountOverride.value
      : detail.account;
  const params = new URLSearchParams(location.search);
  const reportsReturnPath = safeReportsReturnPath(params.get("return_to"));
  const resetTarget = accountDetailResetTarget(
    location.pathname,
    reportsReturnPath,
  );
  const appliedFilters = accountMovementAppliedFilters(
    location.search,
    detail.filterOptions,
  );
  const filtersActive = appliedFilters.length > 0;
  const movements = detail.items.map((movement) => {
    const override = movementOverrides[movement.operationId];
    return override?.sourceVersion === movement.version
      ? override.value
      : movement;
  });

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const search = new URLSearchParams(location.search);
    const value = new FormData(event.currentTarget).get("search");
    const normalized =
      typeof value === "string" ? value.trim().replace(/\s+/g, " ") : "";
    setOrDelete(search, "search", normalized);
    search.delete("page");
    void navigate(queryUrl(location.pathname, search));
  }

  function commitAccount(committed: AccountSummaryDto, message: string) {
    setAccountOverride({
      sourceUpdatedAt: detail.account.updatedAt,
      value: {
        ...account,
        name: committed.name,
        accountType: committed.accountType,
        currency: committed.currency,
        initialBalance: committed.initialBalance,
        balance: committed.balance,
        isActive: committed.isActive,
        updatedAt: committed.updatedAt,
        capabilities: {
          canUpdate: true,
          canArchive: committed.capabilities.canArchive,
          canRestore: committed.capabilities.canRestore,
        },
      },
    });
    setSettingsOpen(false);
    showToast({ message });
  }

  function commitMovement(committed: AccountDetailDto["items"][number]) {
    const source = detail.items.find(
      (movement) => movement.operationId === committed.operationId,
    );
    setMovementOverrides((current) => ({
      ...current,
      [committed.operationId]: {
        sourceVersion: source?.version ?? committed.version,
        value: committed,
      },
    }));
    setEditingMovement(null);
    showToast({ message: "Исправления операции сохранены." });
  }

  return (
    <AppShell session={session}>
      <PageFrame mobileTop="compact" spacing="block">
        <WorkbenchSurface
          aria-busy={navigationPending}
          className={styles.workbench}
        >
          <WorkbenchHeader>
            <BackLink
              className={styles.backLink}
              to={reportsReturnPath ?? "/accounts"}
            >
              {reportsReturnPath ? "Вернуться в отчёт" : "Все счета"}
            </BackLink>
            <PageHeader
              actions={
                <div className={styles.headerActions}>
                  <div className={styles.balanceBlock}>
                    <span>Текущий баланс</span>
                    <MoneyValue
                      amount={formatMoneyAmount(account.balance, null)}
                      currency={account.currency}
                      size="prominent"
                      tone={accountBalanceTone(account.balance)}
                    />
                    <small>
                      Начальный{" "}
                      {formatMoneyAmount(account.initialBalance, null)}{" "}
                      {account.currency}
                    </small>
                  </div>
                  {account.capabilities.canUpdate ? (
                    <Button
                      data-account-settings-trigger
                      icon="edit"
                      onClick={() => setSettingsOpen(true)}
                      tone="secondary"
                    >
                      Настройки счёта
                    </Button>
                  ) : null}
                </div>
              }
              description={`Движения денег по счёту · ${accountTypeLabels[account.accountType]} · ${account.isActive ? "активный" : "в архиве"}.`}
              eyebrow={accountMovementsLabel(detail.pagination.total)}
              title={account.name}
            />
          </WorkbenchHeader>

          <WorkbenchToolbar>
            <div className={styles.listToolActions}>
              <WorkbenchSearch
                ariaLabel="Поиск проводок"
                className={styles.searchPlacement}
                inputId="movement-search"
                inputLabel="Поиск по описанию"
                inputProps={{ defaultValue: params.get("search") ?? "" }}
                key={params.get("search") ?? ""}
                onSubmit={submitSearch}
                placeholder="Поиск по описанию"
              />
              <Button
                aria-controls="account-detail-filter-region"
                aria-expanded={filtersOpen}
                icon="filter"
                onClick={() => setFiltersOpen((value) => !value)}
              >
                {filtersOpen ? "Скрыть фильтры" : "Показать фильтры"}
                {appliedFilters.length ? (
                  <Badge>{appliedFilters.length}</Badge>
                ) : null}
              </Button>
            </div>
            <AppliedFilterSummary
              filters={filtersOpen ? [] : appliedFilters}
              resetTo={resetTarget}
            />
          </WorkbenchToolbar>

          {filtersOpen ? (
            <AccountMovementFilters
              detail={detail}
              onClose={() => setFiltersOpen(false)}
            />
          ) : null}

          <WorkbenchStatus>
            {navigationPending ? "Обновляем проводки…" : ""}
          </WorkbenchStatus>

          <WorkbenchContent
            aria-label="Проводки счёта"
            isEmpty={movements.length === 0}
          >
            {movements.length ? (
              <ol className={styles.list}>
                {movements.map((movement) => (
                  <li key={movement.operationId}>
                    <AccountMovementRow
                      accountId={account.id}
                      categories={detail.filterOptions.categories}
                      csrfToken={session.csrfToken}
                      isEditing={
                        editingMovement?.operationId === movement.operationId
                      }
                      movement={movement}
                      onEdit={setEditingMovement}
                      onEditClosed={() => setEditingMovement(null)}
                      onMovementCommitted={commitMovement}
                      properties={detail.filterOptions.properties}
                    />
                  </li>
                ))}
              </ol>
            ) : (
              <WorkbenchEmptyState
                action={
                  filtersActive ? (
                    <RouterButtonLink icon="filter" to={resetTarget}>
                      Сбросить фильтры
                    </RouterButtonLink>
                  ) : undefined
                }
                icon={filtersActive ? "search" : "operations"}
                kind={filtersActive ? "filtered" : "primary"}
                title={
                  filtersActive
                    ? "По этим фильтрам проводок нет"
                    : "Проводок пока нет"
                }
              >
                {filtersActive
                  ? "Измените условия поиска или сбросьте фильтры."
                  : "Подтверждённые движения по этому счёту появятся здесь."}
              </WorkbenchEmptyState>
            )}
          </WorkbenchContent>

          <AccountDetailFooter
            detail={detail}
            disabled={navigationPending || editingMovement !== null}
          />
        </WorkbenchSurface>
      </PageFrame>
      <ToastViewport onDismiss={dismissToast} toast={toast} />
      {settingsOpen ? (
        <AccountSettingsPanel
          account={account}
          csrfToken={session.csrfToken}
          onClose={() => setSettingsOpen(false)}
          onCommitted={commitAccount}
        />
      ) : null}
    </AppShell>
  );
}

function AccountMovementRow({
  accountId,
  categories,
  csrfToken,
  isEditing,
  movement,
  onEdit,
  onEditClosed,
  onMovementCommitted,
  properties,
}: {
  accountId: string;
  categories: AccountDetailDto["filterOptions"]["categories"];
  csrfToken: string;
  isEditing: boolean;
  movement: AccountDetailDto["items"][number];
  onEdit: (movement: AccountDetailDto["items"][number]) => void;
  onEditClosed: () => void;
  onMovementCommitted: (movement: AccountDetailDto["items"][number]) => void;
  properties: AccountDetailDto["filterOptions"]["properties"];
}) {
  const editButtonRef = useRef<HTMLButtonElement>(null);
  const correctionPanelRef =
    useRef<ImportedOperationCorrectionPanelHandle>(null);
  const view = movementView(movement);
  const sourceTarget = movementSourceTarget(movement);
  const problem =
    movement.status === "needs_review" || movement.status === "duplicate";
  const editPanelId = `account-operation-edit-panel-${movement.operationId}`;

  function closeEdit() {
    onEditClosed();
    queueMicrotask(() => editButtonRef.current?.focus());
  }

  function commitMovement(committed: AccountDetailDto["items"][number]) {
    onMovementCommitted(committed);
    queueMicrotask(() => editButtonRef.current?.focus());
  }

  return (
    <WorkbenchRow
      aside={
        sourceTarget.url ? (
          <ActionStack
            primary={
              movement.capabilities.canEditReviewFields ? (
                <Button
                  aria-controls={editPanelId}
                  aria-expanded={isEditing}
                  data-imported-operation-edit
                  icon="edit"
                  onClick={() =>
                    isEditing
                      ? correctionPanelRef.current?.requestClose()
                      : onEdit(movement)
                  }
                  ref={editButtonRef}
                  tone="secondary"
                >
                  {isEditing ? "Закрыть" : "Исправить"}
                </Button>
              ) : (
                <ButtonLink href={sourceTarget.url} icon="source">
                  {sourceTarget.label}
                </ButtonLink>
              )
            }
            secondary={
              movement.capabilities.canEditReviewFields ? (
                <ButtonLink
                  href={sourceTarget.url}
                  icon="source"
                  tone="secondary"
                >
                  {sourceTarget.label}
                </ButtonLink>
              ) : undefined
            }
          />
        ) : (
          <StatusLabel tone="neutral">Системная операция</StatusLabel>
        )
      }
      date={movement.operationDate}
      description={view.description}
      expansion={
        movement.capabilities.canEditReviewFields && isEditing ? (
          <ExpansionPanel
            id={editPanelId}
            title="Исправить операцию"
            titleId={`${editPanelId}-title`}
          >
            <ImportedOperationCorrectionPanel
              accountId={accountId}
              categories={categories}
              csrfToken={csrfToken}
              movement={movement}
              onClose={closeEdit}
              onCommitted={commitMovement}
              properties={properties}
              ref={correctionPanelRef}
            />
          </ExpansionPanel>
        ) : undefined
      }
      financialHierarchy
      id={`operation-${movement.operationId}`}
      meta={
        <>
          <Tag tone={view.typeTone}>{view.typeLabel}</Tag>
          {movement.transferRoute ? (
            <>
              <Tag tone="transfer">{movement.transferRoute}</Tag>
              <span>Не влияет на прибыль</span>
            </>
          ) : (
            <>
              <Tag tone={movement.category ? "category" : "neutral"}>
                {movement.category?.name ?? "Без категории"}
              </Tag>
              {movement.property ? (
                <span>Объект: {movement.property.name}</span>
              ) : null}
            </>
          )}
          <StatusLabel
            tone={view.statusTone}
            variant={problem ? "soft" : "plain"}
          >
            {view.statusLabel}
          </StatusLabel>
        </>
      }
      state={isEditing ? "working" : "default"}
      value={
        <MoneyValue
          amount={view.amount}
          currency={movement.currency}
          tone={view.moneyTone}
        />
      }
      workflowState={problem ? "problem" : "default"}
    />
  );
}

function movementSourceTarget(movement: AccountDetailDto["items"][number]): {
  label: string;
  url: string | null;
} {
  if (movement.sourceTarget.kind === "manual") {
    return {
      label: "Открыть операцию",
      url: `/app/ledger/manual?operation_id=${movement.operationId}#operation-${movement.operationId}`,
    };
  }
  if (
    movement.sourceTarget.kind === "import" &&
    movement.sourceTarget.uploadedDocumentId &&
    movement.sourceTarget.rawTransactionId
  ) {
    return {
      label: "Открыть импорт",
      url: `/app/imports/documents/${movement.sourceTarget.uploadedDocumentId}/review#raw-${movement.sourceTarget.rawTransactionId}`,
    };
  }
  if (movement.sourceTarget.kind === "import") {
    return { label: "Найти импорт", url: "/app/imports" };
  }
  return { label: "Системная операция", url: null };
}

function AccountMovementFilters({
  detail,
  onClose,
}: {
  detail: AccountDetailDto;
  onClose: () => void;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [draft, setDraft] = useState(() =>
    Object.fromEntries(new URLSearchParams(location.search)),
  );

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const search = new URLSearchParams();
    for (const key of [
      "date_from",
      "date_to",
      "source",
      "type",
      "status",
      "category_id",
      "property_id",
    ]) {
      setOrDelete(search, key, draft[key] ?? "");
    }
    setOrDelete(
      search,
      "search",
      new URLSearchParams(location.search).get("search") ?? "",
    );
    setOrDelete(
      search,
      "per_page",
      new URLSearchParams(location.search).get("per_page") ?? "",
    );
    setOrDelete(
      search,
      "return_to",
      safeReportsReturnPath(
        new URLSearchParams(location.search).get("return_to"),
      ) ?? "",
    );
    onClose();
    void navigate(queryUrl(location.pathname, search));
  }

  return (
    <WorkbenchFilterRegion id="account-detail-filter-region">
      <form className={styles.filterForm} onSubmit={apply}>
        <div className={styles.filterGrid}>
          <FilterField
            id="movement-status"
            label="Статус"
            onChange={(value) => setDraft({ ...draft, status: value })}
            options={operationStatuses}
            value={draft.status ?? "confirmed"}
          />
          <Field htmlFor="movement-date-from" label="Дата от">
            <input
              id="movement-date-from"
              onChange={(event) =>
                setDraft({ ...draft, date_from: event.currentTarget.value })
              }
              type="date"
              value={draft.date_from ?? ""}
            />
          </Field>
          <Field htmlFor="movement-date-to" label="Дата до">
            <input
              id="movement-date-to"
              onChange={(event) =>
                setDraft({ ...draft, date_to: event.currentTarget.value })
              }
              type="date"
              value={draft.date_to ?? ""}
            />
          </Field>
          <FilterField
            id="movement-source"
            label="Источник"
            onChange={(value) => setDraft({ ...draft, source: value })}
            options={operationSources}
            value={draft.source ?? ""}
          />
          <FilterField
            id="movement-type"
            label="Тип"
            onChange={(value) => setDraft({ ...draft, type: value })}
            options={operationTypes}
            value={draft.type ?? ""}
          />
          <FilterField
            id="movement-category"
            label="Категория"
            onChange={(value) => setDraft({ ...draft, category_id: value })}
            options={detail.filterOptions.categories.map((item) => ({
              label: item.name,
              value: item.id,
            }))}
            value={draft.category_id ?? ""}
          />
          <FilterField
            id="movement-property"
            label="Объект"
            onChange={(value) => setDraft({ ...draft, property_id: value })}
            options={detail.filterOptions.properties.map((item) => ({
              label: item.name,
              value: item.id,
            }))}
            value={draft.property_id ?? ""}
          />
        </div>
        <FormActions layout="split">
          <RouterButtonLink
            onClick={onClose}
            to={accountDetailResetTarget(
              location.pathname,
              safeReportsReturnPath(
                new URLSearchParams(location.search).get("return_to"),
              ),
            )}
          >
            Сбросить
          </RouterButtonLink>
          <Button icon="filterApply" tone="primary" type="submit">
            Применить
          </Button>
        </FormActions>
      </form>
    </WorkbenchFilterRegion>
  );
}

function FilterField({
  id,
  label,
  onChange,
  options,
  value,
}: {
  id: string;
  label: string;
  onChange: (value: string) => void;
  options: { label: string; value: string }[];
  value: string;
}) {
  return (
    <Field htmlFor={id} label={label}>
      <select
        id={id}
        onChange={(event) => onChange(event.currentTarget.value)}
        value={value}
      >
        <option value="">Все</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </Field>
  );
}

function AccountDetailFooter({
  detail,
  disabled,
}: {
  detail: AccountDetailDto;
  disabled: boolean;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const start =
    detail.pagination.total === 0
      ? 0
      : (detail.pagination.page - 1) * detail.pagination.perPage + 1;
  const end = Math.min(
    detail.pagination.page * detail.pagination.perPage,
    detail.pagination.total,
  );
  const showPageSize = detail.filterOptions.perPage.some(
    (option) => detail.pagination.total > option,
  );

  return (
    <WorkbenchPagination
      ariaLabel="Страницы проводок"
      currentPage={detail.pagination.page}
      getPageHref={(page) => pageUrl(location.pathname, location.search, page)}
      hasNext={detail.pagination.hasNext}
      hasPrevious={detail.pagination.hasPrevious}
      {...(showPageSize
        ? {
            pageSize: {
              disabled,
              id: "account-detail-page-size",
              onChange: (pageSize: number) => {
                if (!detail.filterOptions.perPage.includes(pageSize)) return;
                const search = new URLSearchParams(location.search);
                search.set("per_page", String(pageSize));
                search.delete("page");
                void navigate(queryUrl(location.pathname, search));
              },
              options: detail.filterOptions.perPage,
              value: detail.pagination.perPage,
            },
          }
        : {})}
      summary={
        detail.pagination.total === 0
          ? "0 проводок"
          : `${start}–${end} из ${detail.pagination.total}`
      }
      totalPages={detail.pagination.totalPages}
    />
  );
}

function setOrDelete(search: URLSearchParams, key: string, value: string) {
  if (value) search.set(key, value);
  else search.delete(key);
}

function queryUrl(pathname: string, search: URLSearchParams): string {
  const value = search.toString();
  return value ? `${pathname}?${value}` : pathname;
}

function pageUrl(pathname: string, current: string, page: number): string {
  const search = new URLSearchParams(current);
  search.set("page", String(page));
  return queryUrl(pathname, search);
}

function safeReportsReturnPath(value: string | null): string | null {
  if (!value || !value.startsWith("/")) return null;
  const parsed = new URL(value, "http://booker-tee.local");
  if (
    parsed.origin !== "http://booker-tee.local" ||
    parsed.pathname !== "/app/reports"
  ) {
    return null;
  }
  return `${parsed.pathname}${parsed.search}${parsed.hash}`;
}

function accountDetailResetTarget(
  pathname: string,
  reportsReturnPath: string | null,
): string {
  if (!reportsReturnPath) return pathname;
  const search = new URLSearchParams({ return_to: reportsReturnPath });
  return `${pathname}?${search.toString()}`;
}
