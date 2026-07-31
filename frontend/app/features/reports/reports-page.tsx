import { useState } from "react";
import { useLocation } from "react-router";

import type { SessionDto } from "../../api/session";
import { formatMoneyAmount } from "../../shared/money/format-money";
import { AppShell } from "../../shell/app-shell";
import { AppliedFilterSummary } from "../../ui/applied-filter-summary/applied-filter-summary";
import { Button, ButtonLink, RouterButtonLink } from "../../ui/button/button";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { MoneyValue } from "../../ui/money-value/money-value";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import { ResponsiveRecordCollection } from "../../ui/responsive-record-collection/responsive-record-collection";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchFilterRegion } from "../../ui/workbench-content/workbench-filter-region";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import { WorkbenchToolbar } from "../../ui/workbench-toolbar/workbench-toolbar";
import type { ReportOverviewDto } from "./api/reports-api";
import {
  reportAllTimeSearch,
  reportAppliedFilters,
  reportCurrentMonthSearch,
  reportMonthSearch,
} from "./report-filter-query";
import { ReportFilters } from "./report-filters";
import styles from "./reports-page.module.css";

export function ReportsPage({
  navigationPending = false,
  overview,
  session,
}: {
  navigationPending?: boolean;
  overview: ReportOverviewDto;
  session: SessionDto;
}) {
  const location = useLocation();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const hasAccounts = overview.filterOptions.accounts.length > 0;
  const hasReportData =
    overview.summary.income !== "0.00" ||
    overview.summary.expense !== "0.00" ||
    overview.categoryRows.length > 0 ||
    overview.propertyRows.length > 0;
  const filters = reportAppliedFilters(overview);

  return (
    <AppShell session={session}>
      <PageFrame className={styles.page} spacing="none">
        <PageHeader
          description="Подтверждённые доходы и расходы без внутренних переводов и смешения валют."
          eyebrow={`${overview.workspaceName} · ${periodLabel(overview)}`}
          title="Отчёты"
        />

        <WorkbenchSurface
          aria-busy={navigationPending}
          aria-label="Параметры отчёта"
          className={styles.controls}
        >
          <WorkbenchToolbar className={styles.toolbar}>
            <nav
              aria-label="Навигация по периоду отчёта"
              className={styles.periodNav}
            >
              <RouterButtonLink
                aria-label="Предыдущий месяц"
                to={{
                  pathname: location.pathname,
                  search: reportMonthSearch(overview, -1, location.search),
                }}
              >
                Предыдущий
              </RouterButtonLink>
              <RouterButtonLink
                aria-label="Следующий месяц"
                to={{
                  pathname: location.pathname,
                  search: reportMonthSearch(overview, 1, location.search),
                }}
              >
                Следующий
              </RouterButtonLink>
              <RouterButtonLink
                to={{
                  pathname: location.pathname,
                  search: reportCurrentMonthSearch(overview, location.search),
                }}
                tone="primary"
              >
                Этот месяц
              </RouterButtonLink>
              <RouterButtonLink
                to={{
                  pathname: location.pathname,
                  search: reportAllTimeSearch(overview, location.search),
                }}
              >
                Всё время
              </RouterButtonLink>
            </nav>
            <Button
              aria-controls="report-filter-region"
              aria-expanded={filtersOpen}
              disabled={navigationPending}
              icon="filter"
              onClick={() => setFiltersOpen((current) => !current)}
            >
              Точные фильтры
            </Button>
          </WorkbenchToolbar>

          <AppliedFilterSummary
            filters={filtersOpen ? [] : filters}
            resetTo={location.pathname}
          />

          {filtersOpen ? (
            <WorkbenchFilterRegion id="report-filter-region">
              <ReportFilters
                key={location.search}
                navigationPending={navigationPending}
                onClose={() => setFiltersOpen(false)}
                overview={overview}
              />
            </WorkbenchFilterRegion>
          ) : null}
        </WorkbenchSurface>

        <section aria-label="Финансовый результат" className={styles.kpis}>
          <Metric
            amount={overview.summary.income}
            currency={overview.summary.currency}
            label="Доходы"
            tone="income"
          />
          <Metric
            amount={overview.summary.expense}
            currency={overview.summary.currency}
            label="Расходы"
            tone="expense"
          />
          <Metric
            amount={overview.summary.profit}
            currency={overview.summary.currency}
            label="Прибыль"
            tone="profit"
          />
        </section>

        {!hasAccounts ? (
          <WorkbenchEmptyState
            action={
              <ButtonLink href="/app/accounts" icon="accounts" tone="primary">
                Создать счёт
              </ButtonLink>
            }
            icon="accounts"
            title="Сначала создайте счёт"
          >
            Счёт нужен, чтобы загрузить выписку и получить подтверждённые
            операции.
          </WorkbenchEmptyState>
        ) : !hasReportData ? (
          <ReportEmptyState overview={overview} />
        ) : null}

        {overview.accountBalances.length > 0 ? (
          <section className={styles.balanceSection}>
            <div className={styles.sectionHeading}>
              <div>
                <p className={styles.sectionEyebrow}>Снимок средств</p>
                <h2>{balanceHeading(overview.balanceAsOf)}</h2>
              </div>
              <InlineNotice tone="information">
                Период доходов и расходов не меняет начальную дату баланса.
              </InlineNotice>
            </div>
            <ResponsiveRecordCollection
              mobileList={<BalanceCards overview={overview} />}
              table={<BalanceTable overview={overview} />}
            />
          </section>
        ) : null}

        {hasReportData ? (
          <InlineNotice title="Следующие разрезы" tone="neutral">
            Детализация по категориям и объектам будет подключена во втором
            slice.
          </InlineNotice>
        ) : null}
      </PageFrame>
    </AppShell>
  );
}

function Metric({
  amount,
  currency,
  label,
  tone,
}: {
  amount: string;
  currency: string;
  label: string;
  tone: "income" | "expense" | "profit";
}) {
  return (
    <article className={styles.metric} data-tone={tone}>
      <span>{label}</span>
      <MoneyValue
        amount={formatMoneyAmount(
          amount,
          tone === "income" ? "income" : tone === "expense" ? "expense" : null,
        )}
        currency={currency}
        size="prominent"
        tone={tone}
      />
    </article>
  );
}

function ReportEmptyState({ overview }: { overview: ReportOverviewDto }) {
  if (overview.nextReviewDocumentId) {
    return (
      <WorkbenchEmptyState
        action={
          <ButtonLink
            href={`/app/imports/documents/${overview.nextReviewDocumentId}/review`}
            icon="imports"
            tone="primary"
          >
            Проверить строки
          </ButtonLink>
        }
        icon="imports"
        title="Отчёт пока пуст"
      >
        Есть выписка со строками на проверке. В отчёт входят только
        подтверждённые операции.
      </WorkbenchEmptyState>
    );
  }
  return (
    <WorkbenchEmptyState
      action={
        <ButtonLink href="/app/imports" icon="imports" tone="primary">
          Открыть импорты
        </ButtonLink>
      }
      icon="reports"
      title="По этим условиям данных нет"
    >
      Измените фильтры или подтвердите доходы и расходы из выписки. Переводы в
      прибыль не входят.
    </WorkbenchEmptyState>
  );
}

function BalanceTable({ overview }: { overview: ReportOverviewDto }) {
  return (
    <table className={styles.table}>
      <caption className="visually-hidden">Балансы счетов</caption>
      <thead>
        <tr>
          <th scope="col">Счёт</th>
          <th scope="col">Валюта</th>
          <th scope="col">Баланс</th>
        </tr>
      </thead>
      <tbody>
        {overview.accountBalances.map((account) => (
          <tr key={account.accountId}>
            <td>
              <RouterButtonLink
                to={`/accounts/${account.accountId}`}
                tone="ghost"
              >
                {account.name}
                {account.isActive ? "" : " · архив"}
              </RouterButtonLink>
            </td>
            <td>{account.currency}</td>
            <td className={styles.balanceAmount}>
              <MoneyValue
                amount={formatMoneyAmount(account.balance, null)}
                currency={account.currency}
                tone={
                  positiveMoney(account.balance) ? "balancePositive" : "neutral"
                }
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function BalanceCards({ overview }: { overview: ReportOverviewDto }) {
  return (
    <ul className={styles.balanceCards}>
      {overview.accountBalances.map((account) => (
        <li key={account.accountId}>
          <RouterButtonLink to={`/accounts/${account.accountId}`} tone="ghost">
            {account.name}
            {account.isActive ? "" : " · архив"}
          </RouterButtonLink>
          <MoneyValue
            amount={formatMoneyAmount(account.balance, null)}
            currency={account.currency}
            tone={
              positiveMoney(account.balance) ? "balancePositive" : "neutral"
            }
          />
        </li>
      ))}
    </ul>
  );
}

function periodLabel(overview: ReportOverviewDto): string {
  const { dateFrom, dateTo } = overview.appliedFilters;
  if (dateFrom && dateTo)
    return `${formatDate(dateFrom)} — ${formatDate(dateTo)}`;
  if (dateFrom) return `с ${formatDate(dateFrom)}`;
  if (dateTo) return `по ${formatDate(dateTo)}`;
  return "всё время";
}

function balanceHeading(dateValue: string | null): string {
  return dateValue ? `Балансы на ${formatDate(dateValue)}` : "Текущие балансы";
}

function formatDate(value: string): string {
  const [year, month, day] = value.split("-");
  return `${day}.${month}.${year}`;
}

function positiveMoney(value: string): boolean {
  return !value.startsWith("-") && !/^0+(?:\.0+)?$/.test(value);
}
