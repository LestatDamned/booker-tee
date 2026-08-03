import { Link, useLocation } from "react-router";

import {
  decimalSign,
  formatMoneyAmount,
} from "../../shared/money/format-money";
import { ButtonLink } from "../../ui/button/button";
import { Icon, type IconName } from "../../ui/icon/icon";
import { MoneyValue, type MoneyTone } from "../../ui/money-value/money-value";
import { ResponsiveRecordCollection } from "../../ui/responsive-record-collection/responsive-record-collection";
import type { ReportOverviewDto } from "./api/reports-api";
import {
  reportCategorySort,
  reportCategorySortDirection,
  reportCategorySortSearch,
  type ReportCategorySort,
  type ReportCategorySortDirection,
} from "./report-filter-query";
import { reportUncategorizedCorrectionHref } from "./report-uncategorized";
import styles from "./reports-page.module.css";

type CategoryRow = ReportOverviewDto["categoryRows"][number];
type FlowKind = "income" | "expense";

export function ReportBreakdowns({
  overview,
}: {
  overview: ReportOverviewDto;
}) {
  const location = useLocation();
  const sort = reportCategorySort(location.search);
  const sortDirection = reportCategorySortDirection(location.search);
  const rows = sortCategoryRows(overview.categoryRows, sort, sortDirection);
  const uncategorizedHref = reportUncategorizedCorrectionHref(overview);

  return (
    <section
      aria-labelledby="report-breakdowns-title"
      className={styles.analysisSection}
    >
      <header className={styles.analysisHeader}>
        <h2 id="report-breakdowns-title">Деньги по категориям</h2>
      </header>

      {rows.length > 0 ? (
        <ResponsiveRecordCollection
          mobileList={
            <CategoryFlowList
              currentSearch={location.search}
              overview={overview}
              rows={rows}
              uncategorizedHref={uncategorizedHref}
            />
          }
          table={
            <CategoryFlowTable
              currentSearch={location.search}
              overview={overview}
              rows={rows}
              sort={sort}
              sortDirection={sortDirection}
              uncategorizedHref={uncategorizedHref}
            />
          }
        />
      ) : (
        <p className={styles.matrixEmpty}>
          За выбранный период нет доходов или расходов по категориям.
        </p>
      )}
    </section>
  );
}

function CategoryFlowTable({
  currentSearch,
  overview,
  rows,
  sort,
  sortDirection,
  uncategorizedHref,
}: {
  currentSearch: string;
  overview: ReportOverviewDto;
  rows: CategoryRow[];
  sort: ReportCategorySort;
  sortDirection: ReportCategorySortDirection;
  uncategorizedHref: string | null;
}) {
  return (
    <table className={styles.flowMatrix}>
      <caption className="visually-hidden">
        Поступления, расходы и итог по категориям
      </caption>
      <thead>
        <tr>
          <CategorySortHeader
            currentSearch={currentSearch}
            label="Категория"
            sort="name"
            selectedSort={sort}
            sortDirection={sortDirection}
          />
          <CategorySortHeader
            currentSearch={currentSearch}
            label="Поступления"
            sort="income"
            selectedSort={sort}
            sortDirection={sortDirection}
          />
          <CategorySortHeader
            currentSearch={currentSearch}
            label="Расходы"
            sort="expense"
            selectedSort={sort}
            sortDirection={sortDirection}
          />
          <CategorySortHeader
            currentSearch={currentSearch}
            label="Итог"
            sort="result"
            selectedSort={sort}
            sortDirection={sortDirection}
          />
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.categoryId ?? "system:uncategorized"}>
            <th scope="row">
              {categoryIdentityView(row, currentSearch, uncategorizedHref)}
            </th>
            <td>
              <FlowValue
                amount={row.income}
                currency={row.currency}
                kind="income"
              />
            </td>
            <td>
              <FlowValue
                amount={row.expense}
                currency={row.currency}
                kind="expense"
              />
            </td>
            <td className={styles.resultCell}>
              <ResultValue amount={row.profit} currency={row.currency} />
            </td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <th scope="row">Итого</th>
          <td>
            <FlowValue
              amount={overview.summary.income}
              currency={overview.summary.currency}
              kind="income"
            />
          </td>
          <td>
            <FlowValue
              amount={overview.summary.expense}
              currency={overview.summary.currency}
              kind="expense"
            />
          </td>
          <td className={styles.resultCell}>
            <ResultValue
              amount={overview.summary.profit}
              currency={overview.summary.currency}
            />
          </td>
        </tr>
      </tfoot>
    </table>
  );
}

function CategorySortHeader({
  currentSearch,
  label,
  selectedSort,
  sort,
  sortDirection,
}: {
  currentSearch: string;
  label: string;
  selectedSort: ReportCategorySort;
  sort: Exclude<ReportCategorySort, "turnover">;
  sortDirection: ReportCategorySortDirection;
}) {
  const selected = selectedSort === sort;
  const nextDirection = selected
    ? sortDirection === "desc"
      ? "по возрастанию"
      : "по убыванию"
    : sort === "name"
      ? "по возрастанию"
      : "по убыванию";
  const indicator: IconName = selected
    ? sortDirection === "asc"
      ? "sortAscending"
      : "sortDescending"
    : "sort";
  return (
    <th
      aria-sort={
        selected
          ? sortDirection === "asc"
            ? "ascending"
            : "descending"
          : undefined
      }
      scope="col"
    >
      <Link
        aria-current={selected ? "page" : undefined}
        aria-label={`${label}: сортировать ${nextDirection}`}
        className={styles.matrixSortLink}
        to={{
          search: reportCategorySortSearch(currentSearch, sort),
        }}
      >
        <span>{label}</span>
        <Icon
          className={styles.matrixSortIndicator}
          name={indicator}
          size="0.875rem"
          weight="bold"
        />
      </Link>
    </th>
  );
}

function CategoryFlowList({
  currentSearch,
  overview,
  rows,
  uncategorizedHref,
}: {
  currentSearch: string;
  overview: ReportOverviewDto;
  rows: CategoryRow[];
  uncategorizedHref: string | null;
}) {
  return (
    <>
      <ol aria-label="Движение денег по категориям">
        {rows.map((row) => (
          <li
            data-responsive-record
            key={row.categoryId ?? "system:uncategorized"}
          >
            <div className={styles.matrixMobileHeader}>
              {categoryIdentityView(row, currentSearch, uncategorizedHref)}
              <div className={styles.matrixMobileResult}>
                <span>Итог</span>
                <ResultValue amount={row.profit} currency={row.currency} />
              </div>
            </div>
            <div className={styles.matrixMobileFlows}>
              <MobileFlowValue
                amount={row.income}
                currency={row.currency}
                kind="income"
              />
              <MobileFlowValue
                amount={row.expense}
                currency={row.currency}
                kind="expense"
              />
            </div>
          </li>
        ))}
      </ol>
      <div
        aria-label="Итого по категориям"
        className={styles.matrixMobileTotals}
      >
        <strong>Итого</strong>
        <FlowValue
          amount={overview.summary.income}
          currency={overview.summary.currency}
          kind="income"
        />
        <FlowValue
          amount={overview.summary.expense}
          currency={overview.summary.currency}
          kind="expense"
        />
        <ResultValue
          amount={overview.summary.profit}
          currency={overview.summary.currency}
        />
      </div>
    </>
  );
}

function MobileFlowValue({
  amount,
  currency,
  kind,
}: {
  amount: string;
  currency: string;
  kind: FlowKind;
}) {
  return (
    <div className={styles.matrixMobileFlow} data-tone={kind}>
      <span>{kind === "income" ? "Поступления" : "Расходы"}</span>
      <FlowValue amount={amount} currency={currency} kind={kind} />
    </div>
  );
}

function FlowValue({
  amount,
  currency,
  kind,
}: {
  amount: string;
  currency: string;
  kind: FlowKind;
}) {
  const sign = decimalSign(amount) ?? 0;
  return (
    <MoneyValue
      amount={formatMoneyAmount(amount, sign === 0 ? null : kind)}
      currency={currency}
      currencyVisibility="accessible"
      size="compact"
      tone={sign === 0 ? "neutral" : kind}
    />
  );
}

function ResultValue({
  amount,
  currency,
}: {
  amount: string;
  currency: string;
}) {
  const sign = decimalSign(amount) ?? 0;
  return (
    <MoneyValue
      amount={formatMoneyAmount(amount, sign > 0 ? "income" : null)}
      currency={currency}
      currencyVisibility="accessible"
      size="compact"
      tone={resultTone(sign)}
    />
  );
}

function categoryIdentityView(
  row: CategoryRow,
  currentSearch: string,
  uncategorizedHref: string | null,
) {
  if (row.categoryId === null) {
    return uncategorizedHref ? (
      <ButtonLink
        className={styles.matrixCategoryLink!}
        data-record-identity
        href={uncategorizedHref}
        tone="ghost"
      >
        Без категории
      </ButtonLink>
    ) : (
      <strong>Без категории</strong>
    );
  }
  return (
    <ButtonLink
      aria-label={`Открыть все операции категории «${categoryDisplayName(row)}»`}
      className={styles.matrixCategoryLink!}
      data-record-identity
      href={categoryDetailHref(row, currentSearch)}
      tone="ghost"
    >
      {row.name}
      {row.isActive ? "" : " · архив"}
    </ButtonLink>
  );
}

function categoryDisplayName(row: CategoryRow): string {
  return row.isActive ? row.name : `${row.name} · архив`;
}

function categoryDetailHref(row: CategoryRow, currentSearch: string): string {
  const query = new URLSearchParams();
  const current = new URLSearchParams(currentSearch);
  for (const key of ["date_from", "date_to", "currency"] as const) {
    const value = current.get(key);
    if (value) query.set(key, value);
  }
  query.set("return_to", `/app/reports${currentSearch}`);
  return `/app/categories/${row.categoryId}${query.size ? `?${query.toString()}` : ""}`;
}

type DecimalMagnitude = { coefficient: bigint; scale: number };

function parseMagnitude(value: string): DecimalMagnitude {
  const normalized = value.replace(/^[-+]/, "");
  const [integer = "0", fraction = ""] = normalized.split(".");
  return {
    coefficient: BigInt(`${integer}${fraction}` || "0"),
    scale: fraction.length,
  };
}

function resultTone(sign: -1 | 0 | 1): MoneyTone {
  if (sign > 0) return "profit";
  if (sign < 0) return "expense";
  return "neutral";
}

function compareMagnitude(left: string, right: string): number {
  return compareDecimalMagnitude(parseMagnitude(left), parseMagnitude(right));
}

function compareDecimalMagnitude(
  left: DecimalMagnitude,
  right: DecimalMagnitude,
): number {
  const leftAligned = left.coefficient * 10n ** BigInt(right.scale);
  const rightAligned = right.coefficient * 10n ** BigInt(left.scale);
  return leftAligned < rightAligned ? -1 : leftAligned > rightAligned ? 1 : 0;
}

function addMagnitude(left: string, right: string): DecimalMagnitude {
  const leftValue = parseMagnitude(left);
  const rightValue = parseMagnitude(right);
  const scale = Math.max(leftValue.scale, rightValue.scale);
  return {
    coefficient:
      leftValue.coefficient * 10n ** BigInt(scale - leftValue.scale) +
      rightValue.coefficient * 10n ** BigInt(scale - rightValue.scale),
    scale,
  };
}

function compareGrossFlow(left: CategoryRow, right: CategoryRow) {
  return compareDecimalMagnitude(
    addMagnitude(left.income, left.expense),
    addMagnitude(right.income, right.expense),
  );
}

function sortCategoryRows(
  rows: CategoryRow[],
  sort: ReportCategorySort,
  direction: ReportCategorySortDirection,
): CategoryRow[] {
  return [...rows].sort((left, right) => {
    let comparison: number;
    if (sort === "name") {
      comparison = categoryDisplayName(left).localeCompare(
        categoryDisplayName(right),
        "ru",
      );
    } else if (sort === "turnover") {
      comparison = compareGrossFlow(left, right);
    } else if (sort === "result") {
      comparison = compareSignedDecimal(left.profit, right.profit);
    } else {
      comparison = compareMagnitude(left[sort], right[sort]);
    }
    return (
      (direction === "asc" ? comparison : -comparison) ||
      categoryDisplayName(left).localeCompare(categoryDisplayName(right), "ru")
    );
  });
}

function compareSignedDecimal(left: string, right: string): number {
  const leftSign = decimalSign(left) ?? 0;
  const rightSign = decimalSign(right) ?? 0;
  if (leftSign !== rightSign) return leftSign < rightSign ? -1 : 1;
  const magnitudeComparison = compareMagnitude(left, right);
  return leftSign < 0 ? -magnitudeComparison : magnitudeComparison;
}
