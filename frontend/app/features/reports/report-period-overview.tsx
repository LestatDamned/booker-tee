import type { ReactNode } from "react";
import { useLocation } from "react-router";

import { formatMoneyAmount } from "../../shared/money/format-money";
import { Icon } from "../../ui/icon/icon";
import { MoneyValue, type MoneyTone } from "../../ui/money-value/money-value";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import type { ReportOverviewDto } from "./api/reports-api";
import styles from "./reports-page.module.css";

type AccountBalance = ReportOverviewDto["accountBalances"][number];

export function ReportPeriodSummary({
  overview,
}: {
  overview: ReportOverviewDto;
}) {
  return (
    <WorkbenchSurface
      aria-label="Итог периода"
      className={styles.periodSummarySurface}
    >
      <PeriodSummary overview={overview} />
    </WorkbenchSurface>
  );
}

export function ReportAccountBalances({
  overview,
}: {
  overview: ReportOverviewDto;
}) {
  const location = useLocation();
  return (
    <WorkbenchSurface
      aria-label="Распределение денег по счетам"
      className={styles.accountsComparison}
      data-report-account-support="true"
    >
      <AccountBalanceComparison
        overview={overview}
        reportSearch={location.search}
      />
    </WorkbenchSurface>
  );
}

function PeriodSummary({ overview }: { overview: ReportOverviewDto }) {
  const resultSign = decimalSign(overview.summary.profit);
  return (
    <article className={styles.periodSummary} data-report-period-summary="true">
      <header className={styles.periodSummaryHeader}>
        <p className={styles.sectionEyebrow}>Итог периода</p>
        <MoneyValue
          amount={formatMoneyAmount(overview.summary.profit, null)}
          currency={overview.summary.currency}
          size="prominent"
          tone={resultTone(resultSign)}
        />
        <p className={styles.resultLabel}>{resultLabel(resultSign)}</p>
      </header>

      <div className={styles.summaryGroups}>
        <SummaryGroup label="Денежный поток">
          <FlowSummaryFact
            amount={overview.summary.income}
            currency={overview.summary.currency}
            kind="income"
            label="Доходы"
          />
          <FlowSummaryFact
            amount={overview.summary.expense}
            currency={overview.summary.currency}
            kind="expense"
            label="Расходы"
          />
        </SummaryGroup>

        <SummaryGroup label="Общий остаток">
          <SummaryFact
            amount={formatMoneyAmount(
              overview.balanceSummary.openingBalance,
              null,
            )}
            currency={overview.balanceSummary.currency}
            label="На начало"
            tone="neutral"
          />
          <SummaryFact
            amount={formatMoneyAmount(
              overview.balanceSummary.closingBalance,
              null,
            )}
            currency={overview.balanceSummary.currency}
            label="На конец"
            tone="neutral"
          />
        </SummaryGroup>
      </div>
    </article>
  );
}

function SummaryGroup({
  children,
  label,
}: {
  children: ReactNode;
  label: string;
}) {
  return (
    <section aria-label={label} className={styles.summaryGroup}>
      <p className={styles.summaryGroupLabel}>{label}</p>
      <dl className={styles.summaryFacts}>{children}</dl>
    </section>
  );
}

function FlowSummaryFact({
  amount,
  currency,
  kind,
  label,
}: {
  amount: string;
  currency: string;
  kind: "income" | "expense";
  label: string;
}) {
  const sign = decimalSign(amount);
  return (
    <SummaryFact
      amount={formatMoneyAmount(amount, sign === 0 ? null : kind)}
      currency={currency}
      label={label}
      tone={sign === 0 ? "neutral" : kind}
    />
  );
}

function SummaryFact({
  amount,
  currency,
  label,
  tone,
}: {
  amount: string;
  currency: string;
  label: string;
  tone: MoneyTone;
}) {
  return (
    <div className={styles.summaryFact}>
      <dt>{label}</dt>
      <dd>
        <MoneyValue amount={amount} currency={currency} tone={tone} />
      </dd>
    </div>
  );
}

function AccountBalanceComparison({
  overview,
  reportSearch,
}: {
  overview: ReportOverviewDto;
  reportSearch: string;
}) {
  const rows = overview.accountBalances;
  return (
    <article>
      <header className={styles.accountsHeader}>
        <div>
          <p className={styles.sectionEyebrow}>Где находятся деньги</p>
          <h2>Остатки по счетам</h2>
        </div>
        <span className={styles.accountsCurrency}>
          {overview.balanceSummary.currency}
        </span>
      </header>

      {rows.length > 0 ? (
        <ol
          aria-label="Остатки по счетам за период"
          className={styles.accountMobileList}
        >
          {rows.map((row) => (
            <AccountBalanceRecord
              key={row.accountId}
              overview={overview}
              reportSearch={reportSearch}
              row={row}
            />
          ))}
        </ol>
      ) : (
        <p className={styles.accountsEmpty}>
          В выбранной валюте нет счетов с остатком или движением за период.
        </p>
      )}
    </article>
  );
}

function AccountBalanceRecord({
  overview,
  reportSearch,
  row,
}: {
  overview: ReportOverviewDto;
  reportSearch: string;
  row: AccountBalance;
}) {
  return (
    <li data-responsive-record>
      <a
        aria-label={`Открыть операции счёта «${accountName(row)}»`}
        className={styles.accountRecordLink}
        data-record-identity
        href={accountDetailHref(row.accountId, overview, reportSearch)}
      >
        <strong>{accountName(row)}</strong>
        <span>
          Операции
          <Icon name="forward" size="1rem" weight="bold" />
        </span>
      </a>
      <dl className={styles.accountBalanceFacts}>
        <div>
          <dt>На начало</dt>
          <dd>
            <AccountMoney amount={row.openingBalance} currency={row.currency} />
          </dd>
        </div>
        <div>
          <dt>На конец</dt>
          <dd>
            <AccountMoney amount={row.closingBalance} currency={row.currency} />
          </dd>
        </div>
        <div>
          <dt>Изменение</dt>
          <dd>
            <AccountChange amount={row.balanceChange} currency={row.currency} />
          </dd>
        </div>
      </dl>
    </li>
  );
}

function AccountMoney({
  amount,
  currency,
}: {
  amount: string;
  currency: string;
}) {
  return (
    <MoneyValue
      amount={formatMoneyAmount(amount, null)}
      currency={currency}
      currencyVisibility="accessible"
      size="compact"
    />
  );
}

function AccountChange({
  amount,
  currency,
}: {
  amount: string;
  currency: string;
}) {
  const sign = decimalSign(amount);
  return (
    <MoneyValue
      amount={formatMoneyAmount(amount, sign > 0 ? "income" : null)}
      currency={currency}
      currencyVisibility="accessible"
      size="compact"
      tone={changeTone(sign)}
    />
  );
}

function accountDetailHref(
  accountId: string,
  overview: ReportOverviewDto,
  reportSearch: string,
): string {
  const query = new URLSearchParams();
  if (overview.appliedFilters.dateFrom) {
    query.set("date_from", overview.appliedFilters.dateFrom);
  }
  if (overview.appliedFilters.dateTo) {
    query.set("date_to", overview.appliedFilters.dateTo);
  }
  query.set("status", "confirmed");
  if (overview.appliedFilters.categoryId) {
    query.set("category_id", overview.appliedFilters.categoryId);
  }
  if (overview.appliedFilters.propertyId) {
    query.set("property_id", overview.appliedFilters.propertyId);
  }
  query.set("return_to", `/app/reports${reportSearch}`);
  return `/app/accounts/${accountId}${query.size ? `?${query.toString()}` : ""}`;
}

function accountName(row: AccountBalance): string {
  return row.isActive ? row.name : `${row.name} · архив`;
}

function decimalSign(value: string): -1 | 0 | 1 {
  const normalized = value.replace(/^[+-]/, "").replace(/[.,]/, "");
  if (/^0*$/.test(normalized)) return 0;
  return value.startsWith("-") ? -1 : 1;
}

function resultLabel(sign: -1 | 0 | 1): string {
  if (sign > 0) return "Положительный результат";
  if (sign < 0) return "Отрицательный результат";
  return "Доходы и расходы равны";
}

function resultTone(sign: -1 | 0 | 1): MoneyTone {
  if (sign > 0) return "profit";
  if (sign < 0) return "expense";
  return "neutral";
}

function changeTone(sign: -1 | 0 | 1): MoneyTone {
  if (sign > 0) return "balancePositive";
  if (sign < 0) return "expense";
  return "neutral";
}
