import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import type { SessionDto } from "../../api/session";
import { formatMoneyAmount } from "../../shared/money/format-money";
import { AppShell } from "../../shell/app-shell";
import { Badge } from "../../ui/badge/badge";
import { Button, ButtonLink } from "../../ui/button/button";
import { Field } from "../../ui/field/field";
import { FormActions } from "../../ui/field/form-layout";
import { Icon } from "../../ui/icon/icon";
import { MoneyValue } from "../../ui/money-value/money-value";
import { PageHeader } from "../../ui/page-header/page-header";
import { RequestState } from "../../ui/request-state/request-state";
import { StatusLabel } from "../../ui/status-label/status-label";
import { Tag } from "../../ui/tag/tag";
import { WorkbenchRow } from "../../ui/workbench-row/workbench-row";
import type { AccountDetailDto } from "./api/account-detail-api";
import type { AccountSummaryDto } from "./api/accounts-api";
import {
  accountBalanceTone,
  accountMovementsLabel,
  accountTypeLabels,
  movementView,
  operationSources,
  operationStatuses,
  operationTypes,
} from "./account-detail-model";
import { AccountSettingsPanel } from "./account-settings-panel";
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
  const [accountOverride, setAccountOverride] = useState<{
    sourceUpdatedAt: string;
    value: AccountDetailDto["account"];
  } | null>(null);
  const [feedback, setFeedback] = useState("");
  const account =
    accountOverride?.sourceUpdatedAt === detail.account.updatedAt
      ? accountOverride.value
      : detail.account;
  const params = new URLSearchParams(location.search);
  const appliedCount = activeFilterCount(params);

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
    setFeedback(message);
  }

  return (
    <AppShell session={session}>
      <main className={styles.page}>
        <section aria-busy={navigationPending} className={styles.workbench}>
          <div className={styles.workbenchHeader}>
            <Link className={styles.backLink} to="/accounts">
              <Icon name="back" />
              Все счета
            </Link>
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
                      onClick={() => {
                        setFeedback("");
                        setSettingsOpen(true);
                      }}
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
          </div>

          <section aria-label="Инструменты списка" className={styles.listTools}>
            <div className={styles.listToolActions}>
              <form
                aria-label="Поиск проводок"
                className={styles.searchForm}
                onSubmit={submitSearch}
                role="search"
              >
                <label className="visually-hidden" htmlFor="movement-search">
                  Поиск по описанию
                </label>
                <input
                  defaultValue={params.get("search") ?? ""}
                  id="movement-search"
                  key={params.get("search") ?? ""}
                  name="search"
                  placeholder="Поиск по описанию"
                  type="search"
                />
                <Button icon="search" type="submit">
                  Найти
                </Button>
              </form>
              <Button
                aria-controls="account-detail-filter-region"
                aria-expanded={filtersOpen}
                icon="filter"
                onClick={() => setFiltersOpen((value) => !value)}
              >
                {filtersOpen ? "Скрыть фильтры" : "Показать фильтры"}
                {appliedCount ? <Badge>{appliedCount}</Badge> : null}
              </Button>
            </div>
            {appliedCount ? (
              <div className={styles.activeFilterSummary}>
                <span>Применено фильтров: {appliedCount}</span>
                <Link className={styles.resetLink} to={location.pathname}>
                  Сбросить все
                </Link>
              </div>
            ) : null}
          </section>

          {filtersOpen ? (
            <AccountMovementFilters
              detail={detail}
              onClose={() => setFiltersOpen(false)}
            />
          ) : null}

          <span aria-live="polite" className={styles.navigationStatus}>
            {navigationPending ? "Обновляем проводки…" : feedback}
          </span>

          <section
            aria-label="Проводки счёта"
            className={styles.listRegion}
            data-empty={detail.items.length === 0 ? "true" : undefined}
          >
            {detail.items.length ? (
              <ol className={styles.list}>
                {detail.items.map((movement) => (
                  <li key={movement.operationId}>
                    <AccountMovementRow movement={movement} />
                  </li>
                ))}
              </ol>
            ) : (
              <RequestState
                message={
                  appliedCount
                    ? "Измените условия поиска или сбросьте фильтры."
                    : "Подтверждённые движения по этому счёту появятся здесь."
                }
                status="empty"
                title={
                  appliedCount
                    ? "По этим фильтрам проводок нет"
                    : "Проводок пока нет"
                }
              />
            )}
          </section>

          <AccountDetailFooter detail={detail} />
        </section>
      </main>
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
  movement,
}: {
  movement: AccountDetailDto["items"][number];
}) {
  const view = movementView(movement);
  const sourceTarget = movementSourceTarget(movement);
  const problem =
    movement.status === "needs_review" || movement.status === "duplicate";
  return (
    <WorkbenchRow
      aside={
        sourceTarget.url ? (
          <ButtonLink href={sourceTarget.url} icon="source">
            {sourceTarget.label}
          </ButtonLink>
        ) : (
          <StatusLabel tone="neutral">Системная операция</StatusLabel>
        )
      }
      date={movement.operationDate}
      description={view.description}
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
    onClose();
    void navigate(queryUrl(location.pathname, search));
  }

  return (
    <div className={styles.filterRegion} id="account-detail-filter-region">
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
        <FormActions>
          <Button icon="filterApply" tone="primary" type="submit">
            Применить
          </Button>
          <Link
            className={styles.resetLink}
            onClick={onClose}
            to={location.pathname}
          >
            Сбросить
          </Link>
        </FormActions>
      </form>
    </div>
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

function AccountDetailFooter({ detail }: { detail: AccountDetailDto }) {
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
  return (
    <footer className={styles.workbenchFooter}>
      <span>
        Показано {start}–{end} из {detail.pagination.total}
      </span>
      <label className={styles.pageSize}>
        <span>На странице</span>
        <select
          aria-label="Проводок на странице"
          onChange={(event) => {
            const search = new URLSearchParams(location.search);
            search.set("per_page", event.currentTarget.value);
            search.delete("page");
            void navigate(queryUrl(location.pathname, search));
          }}
          value={detail.pagination.perPage}
        >
          {detail.filterOptions.perPage.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
      <nav aria-label="Страницы проводок" className={styles.pagination}>
        {detail.pagination.hasPrevious ? (
          <Link
            to={pageUrl(
              location.pathname,
              location.search,
              detail.pagination.page - 1,
            )}
          >
            <Icon name="back" size={16} /> Назад
          </Link>
        ) : (
          <span />
        )}
        <strong>
          Страница {detail.pagination.page} из {detail.pagination.totalPages}
        </strong>
        {detail.pagination.hasNext ? (
          <Link
            to={pageUrl(
              location.pathname,
              location.search,
              detail.pagination.page + 1,
            )}
          >
            Дальше <Icon name="forward" size={16} />
          </Link>
        ) : (
          <span />
        )}
      </nav>
    </footer>
  );
}

function activeFilterCount(search: URLSearchParams): number {
  return [...search.entries()].filter(
    ([key, value]) =>
      value &&
      !["page", "per_page"].includes(key) &&
      !(key === "status" && value === "confirmed"),
  ).length;
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
