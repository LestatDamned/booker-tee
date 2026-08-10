import { useState } from "react";
import { useLocation } from "react-router";

import type { SessionDto } from "../../api/session";
import { formatIsoDate } from "../../shared/date/format-date";
import { AppShell } from "../../shell/app-shell";
import { AppliedFilterSummary } from "../../ui/applied-filter-summary/applied-filter-summary";
import { Button, ButtonLink, RouterButtonLink } from "../../ui/button/button";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchFilterRegion } from "../../ui/workbench-content/workbench-filter-region";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import { WorkbenchToolbar } from "../../ui/workbench-toolbar/workbench-toolbar";
import type { ReportOverviewDto } from "./api/reports-api";
import {
  reportAllTimeSearch,
  reportAppliedFilters,
  reportCurrentMonthSearch,
  reportCurrentMonthRange,
  reportMonthlyExportHref,
  reportMonthSearch,
} from "./report-filter-query";
import { ReportFilters } from "./report-filters";
import { ReportBreakdowns } from "./report-breakdowns";
import { ReportUncategorizedNotice } from "./report-uncategorized";
import {
  ReportAccountBalances,
  ReportPeriodSummary,
} from "./report-period-overview";
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
  const detailedFilters = filters.filter(
    (filter) =>
      !filter.startsWith("Период") &&
      (filter !== `Валюта: ${overview.summary.currency}` ||
        overview.summary.currency !== session.workspace.defaultCurrency),
  );
  const currentMonthSelected = isCurrentMonth(overview);
  const allTimeSelected = isAllTime(overview);
  const exportHref = reportMonthlyExportHref(overview);

  return (
    <AppShell session={session}>
      <PageFrame
        className={styles.page}
        data-report-workspace="true"
        spacing="none"
      >
        <WorkbenchSurface
          aria-busy={navigationPending}
          aria-label="Параметры отчёта"
          className={styles.controls}
        >
          <WorkbenchToolbar
            aria-label="Управление отчётом"
            className={styles.toolbar}
          >
            <div className={styles.reportIdentity}>
              <span>
                {overview.workspaceName} · {overview.summary.currency}
              </span>
              <h1>Отчёты</h1>
            </div>
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
                ←
              </RouterButtonLink>
              <strong className={styles.periodLabel}>
                {periodLabel(overview)}
              </strong>
              <RouterButtonLink
                aria-label="Следующий месяц"
                to={{
                  pathname: location.pathname,
                  search: reportMonthSearch(overview, 1, location.search),
                }}
              >
                →
              </RouterButtonLink>
            </nav>
            <div className={styles.toolbarActions}>
              <RouterButtonLink
                aria-current={currentMonthSelected ? "page" : undefined}
                to={{
                  pathname: location.pathname,
                  search: reportCurrentMonthSearch(overview, location.search),
                }}
                tone={currentMonthSelected ? "primary" : "secondary"}
              >
                Этот месяц
              </RouterButtonLink>
              <RouterButtonLink
                aria-current={allTimeSelected ? "page" : undefined}
                to={{
                  pathname: location.pathname,
                  search: reportAllTimeSearch(overview, location.search),
                }}
                tone={allTimeSelected ? "primary" : "secondary"}
              >
                Всё время
              </RouterButtonLink>
              {exportHref ? (
                <ButtonLink href={exportHref}>Скачать отчёт</ButtonLink>
              ) : (
                <span
                  aria-label="Выберите полный месяц, чтобы скачать отчёт"
                  className={styles.exportDisabled}
                  role="group"
                  tabIndex={0}
                  title="Выберите полный месяц, чтобы скачать отчёт"
                >
                  <Button disabled>Скачать отчёт</Button>
                </span>
              )}
              <Button
                aria-controls="report-filter-region"
                aria-expanded={filtersOpen}
                disabled={navigationPending}
                icon="filter"
                onClick={() => setFiltersOpen((current) => !current)}
              >
                Фильтры
                {detailedFilters.length > 0
                  ? ` · ${detailedFilters.length}`
                  : ""}
              </Button>
            </div>
          </WorkbenchToolbar>

          <AppliedFilterSummary
            filters={filtersOpen ? [] : detailedFilters}
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

        {hasAccounts ? <ReportPeriodSummary overview={overview} /> : null}

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

        {hasReportData ? (
          <div className={styles.analysisLayout}>
            <div data-report-primary-analysis="true">
              <ReportBreakdowns overview={overview} />
            </div>
            {hasAccounts ? <ReportAccountBalances overview={overview} /> : null}
          </div>
        ) : null}

        {hasReportData ? (
          <ReportUncategorizedNotice overview={overview} />
        ) : null}
      </PageFrame>
    </AppShell>
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

function periodLabel(overview: ReportOverviewDto): string {
  const { dateFrom, dateTo } = overview.appliedFilters;
  if (dateFrom && dateTo)
    return `${formatDate(dateFrom)} — ${formatDate(dateTo)}`;
  if (dateFrom) return `с ${formatDate(dateFrom)}`;
  if (dateTo) return `по ${formatDate(dateTo)}`;
  return "всё время";
}

function isAllTime(overview: ReportOverviewDto): boolean {
  return (
    overview.appliedFilters.dateFrom === null &&
    overview.appliedFilters.dateTo === null
  );
}

function isCurrentMonth(overview: ReportOverviewDto): boolean {
  const currentMonth = reportCurrentMonthRange();
  return (
    overview.appliedFilters.dateFrom === currentMonth.dateFrom &&
    overview.appliedFilters.dateTo === currentMonth.dateTo
  );
}

function formatDate(value: string): string {
  return formatIsoDate(value);
}
