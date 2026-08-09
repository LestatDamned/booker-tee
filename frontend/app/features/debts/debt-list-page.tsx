import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router";

import type { SessionDto } from "../../api/session";
import { formatMoneyAmount } from "../../shared/money/format-money";
import { AppShell } from "../../shell/app-shell";
import { Button, RouterButtonLink } from "../../ui/button/button";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { MoneyValue } from "../../ui/money-value/money-value";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import {
  SelectionTabLink,
  SelectionTabs,
} from "../../ui/selection-tabs/selection-tabs";
import { WorkbenchContent } from "../../ui/workbench-content/workbench-content";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchHeader } from "../../ui/workbench-surface/workbench-header";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import { WorkbenchSearch } from "../../ui/workbench-toolbar/workbench-search";
import { WorkbenchToolbar } from "../../ui/workbench-toolbar/workbench-toolbar";
import type { AccountSummaryDto } from "../accounts/api/accounts-api";
import type { DebtPortfolioDto } from "./api/debts-api";
import { DebtCreatePanel } from "./debt-create-panel";
import { DebtRecords } from "./debt-records";
import styles from "./debts.module.css";

export function DebtListPage({
  accounts,
  portfolio,
  session,
}: {
  accounts: AccountSummaryDto[];
  portfolio: DebtPortfolioDto;
  session: SessionDto;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [createOpen, setCreateOpen] = useState(false);
  const query = debtListQuery(location.search);
  const counts = {
    active: portfolio.items.filter((debt) => debt.isActive).length,
    archived: portfolio.items.filter((debt) => !debt.isActive).length,
  };
  const debts = portfolio.items.filter(
    (debt) =>
      debt.isActive === (query.view === "active") &&
      [debt.name, debt.kind, debt.currency].some((value) =>
        value
          .toLocaleLowerCase("ru")
          .includes(query.search.toLocaleLowerCase("ru")),
      ),
  );

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const search = new FormData(event.currentTarget).get("search");
    void navigate(
      debtListUrl(query.view, typeof search === "string" ? search : ""),
    );
  }

  return (
    <AppShell session={session}>
      <PageFrame>
        <WorkbenchSurface className={styles.workbench}>
          <WorkbenchHeader>
            <PageHeader
              description="Выданные и полученные займы, кредитные карты и ипотека. Основной долг и проценты учитываются отдельно."
              eyebrow={debtCountLabel(debts.length)}
              title="Долги"
            />
            {portfolio.totals.length ? (
              <div aria-label="Итоги по валютам" className={styles.totals}>
                {portfolio.totals.map((total) => (
                  <section className={styles.total} key={total.currency}>
                    <h2>{total.currency}</h2>
                    <dl>
                      <div>
                        <dt>Мне должны</dt>
                        <dd>
                          <MoneyValue
                            amount={formatMoneyAmount(total.receivable, null)}
                            currency={total.currency}
                            tone="income"
                          />
                        </dd>
                      </div>
                      <div>
                        <dt>Я должен</dt>
                        <dd>
                          <MoneyValue
                            amount={formatMoneyAmount(total.payable, null)}
                            currency={total.currency}
                            tone="expense"
                          />
                        </dd>
                      </div>
                      <div>
                        <dt>Чистая позиция</dt>
                        <dd>
                          <MoneyValue
                            amount={formatMoneyAmount(total.netPosition, null)}
                            currency={total.currency}
                          />
                        </dd>
                      </div>
                    </dl>
                  </section>
                ))}
              </div>
            ) : null}
          </WorkbenchHeader>

          <WorkbenchToolbar>
            <div className={styles.toolbar}>
              <WorkbenchSearch
                ariaLabel="Поиск долгов"
                inputId="debt-search"
                inputLabel="Поиск по названию, виду или валюте"
                inputProps={{ defaultValue: query.search }}
                key={query.search}
                onSubmit={submitSearch}
                placeholder="Название, вид или валюта"
              />
              <SelectionTabs as="nav" aria-label="Состояние долгов">
                <SelectionTabLink
                  count={counts.active}
                  selected={query.view === "active"}
                  to={debtListUrl("active", query.search)}
                >
                  Активные
                </SelectionTabLink>
                <SelectionTabLink
                  count={counts.archived}
                  selected={query.view === "archived"}
                  to={debtListUrl("archived", query.search)}
                >
                  Архив
                </SelectionTabLink>
              </SelectionTabs>
              {portfolio.capabilities.canCreate ? (
                <Button
                  icon="plus"
                  onClick={() => setCreateOpen(true)}
                  tone="primary"
                >
                  Добавить долг
                </Button>
              ) : null}
            </div>
          </WorkbenchToolbar>

          {!portfolio.capabilities.canCreate ? (
            <InlineNotice
              className={styles.notice}
              title="Долги доступны только для просмотра"
              tone="information"
            >
              Финансовые изменения доступны владельцу, администратору или
              редактору workspace.
            </InlineNotice>
          ) : null}

          <WorkbenchContent aria-label="Долги" isEmpty={debts.length === 0}>
            {debts.length ? (
              <DebtRecords debts={debts} />
            ) : (
              <WorkbenchEmptyState
                action={
                  query.search ? (
                    <RouterButtonLink
                      icon="search"
                      to={debtListUrl(query.view, "")}
                    >
                      Очистить поиск
                    </RouterButtonLink>
                  ) : portfolio.items.length === 0 &&
                    portfolio.capabilities.canCreate ? (
                    <Button
                      icon="plus"
                      onClick={() => setCreateOpen(true)}
                      tone="primary"
                    >
                      Добавить первый долг
                    </Button>
                  ) : undefined
                }
                icon={query.search ? "search" : "accounts"}
                kind={query.search ? "filtered" : "primary"}
                title={
                  query.search
                    ? "По этому запросу долгов нет"
                    : query.view === "archived"
                      ? "Архив пока пуст"
                      : "Пока нет долгов"
                }
              >
                {query.search
                  ? "Измените запрос или очистите поиск."
                  : "Добавьте существующий долг или запишите новый заём."}
              </WorkbenchEmptyState>
            )}
          </WorkbenchContent>
        </WorkbenchSurface>
      </PageFrame>

      {createOpen ? (
        <DebtCreatePanel
          accounts={accounts}
          csrfToken={session.csrfToken}
          defaultCurrency={session.workspace.defaultCurrency}
          onClose={() => setCreateOpen(false)}
          onCreated={(detail) =>
            void navigate(`/debts/${detail.debt.accountId}`)
          }
        />
      ) : null}
    </AppShell>
  );
}

type DebtListView = "active" | "archived";

function debtListQuery(search: string): { search: string; view: DebtListView } {
  const params = new URLSearchParams(search);
  return {
    search: params.get("search")?.trim() ?? "",
    view: params.get("view") === "archived" ? "archived" : "active",
  };
}

function debtListUrl(view: DebtListView, search: string): string {
  const params = new URLSearchParams();
  if (view === "archived") params.set("view", view);
  if (search.trim()) params.set("search", search.trim());
  const query = params.toString();
  return query ? `/debts?${query}` : "/debts";
}

function debtCountLabel(count: number): string {
  return `${count} ${count === 1 ? "долг" : count >= 2 && count <= 4 ? "долга" : "долгов"}`;
}
