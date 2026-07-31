import type { ReactNode } from "react";
import { useLocation } from "react-router";

import { formatMoneyAmount } from "../../shared/money/format-money";
import { ButtonLink, RouterButtonLink } from "../../ui/button/button";
import { MoneyValue } from "../../ui/money-value/money-value";
import { ResponsiveRecordCollection } from "../../ui/responsive-record-collection/responsive-record-collection";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import type { ReportOverviewDto } from "./api/reports-api";
import {
  reportCategorySort,
  reportCategorySortSearch,
  type ReportCategorySortField,
} from "./report-filter-query";
import styles from "./reports-page.module.css";

type CategoryRow = ReportOverviewDto["categoryRows"][number];
type PropertyRow = ReportOverviewDto["propertyRows"][number];

const categoryColumns: ReadonlyArray<{
  field: ReportCategorySortField;
  label: string;
}> = [
  { field: "name", label: "Категория" },
  { field: "income", label: "Доходы" },
  { field: "expense", label: "Расходы" },
  { field: "profit", label: "Итог" },
];

export function ReportBreakdowns({
  overview,
}: {
  overview: ReportOverviewDto;
}) {
  const location = useLocation();
  const sort = reportCategorySort(location.search);
  const categories = sortCategoryRows(overview.categoryRows, sort);

  return (
    <div className={styles.breakdowns}>
      <BreakdownSection
        description={`Результат подтверждённых операций в ${overview.summary.currency}.`}
        eyebrow="Структура результата"
        title="По категориям"
      >
        {categories.length > 0 ? (
          <>
            <CategoryMobileSort
              currentPath={location.pathname}
              currentSearch={location.search}
              sort={sort}
            />
            <ResponsiveRecordCollection
              mobileList={
                <CategoryCards
                  currentSearch={location.search}
                  rows={categories}
                />
              }
              table={
                <CategoryTable
                  currentPath={location.pathname}
                  currentSearch={location.search}
                  rows={categories}
                  sort={sort}
                />
              }
            />
          </>
        ) : (
          <WorkbenchEmptyState
            icon="categories"
            title="Нет данных по категориям"
          >
            В выбранном периоде нет подтверждённых доходов или расходов с
            подходящими условиями.
          </WorkbenchEmptyState>
        )}
      </BreakdownSection>

      <BreakdownSection
        description={`Доходы и расходы, связанные с объектами, в ${overview.summary.currency}.`}
        eyebrow="Связи операций"
        title="По объектам"
      >
        {overview.propertyRows.length > 0 ? (
          <ResponsiveRecordCollection
            mobileList={<PropertyCards rows={overview.propertyRows} />}
            table={<PropertyTable rows={overview.propertyRows} />}
          />
        ) : (
          <WorkbenchEmptyState icon="properties" title="Нет данных по объектам">
            Подтверждённые операции за этот период не связаны с объектами.
          </WorkbenchEmptyState>
        )}
      </BreakdownSection>
    </div>
  );
}

function CategoryMobileSort({
  currentPath,
  currentSearch,
  sort,
}: {
  currentPath: string;
  currentSearch: string;
  sort: ReturnType<typeof reportCategorySort>;
}) {
  return (
    <nav
      aria-label="Сортировка категорий"
      className={styles.mobileSortControls}
    >
      {categoryColumns.map((column) => (
        <RouterButtonLink
          aria-current={sort.field === column.field ? "page" : undefined}
          aria-label={`Сортировать категории: ${column.label}. ${sortLabel(sort, column.field)}`}
          key={column.field}
          to={{
            pathname: currentPath,
            search: reportCategorySortSearch(currentSearch, column.field),
          }}
          tone={sort.field === column.field ? "primary" : "secondary"}
        >
          {column.label}
          {sort.field === column.field
            ? sort.direction === "asc"
              ? " ↑"
              : " ↓"
            : ""}
        </RouterButtonLink>
      ))}
    </nav>
  );
}

function BreakdownSection({
  children,
  description,
  eyebrow,
  title,
}: {
  children: ReactNode;
  description: string;
  eyebrow: string;
  title: string;
}) {
  return (
    <section className={styles.breakdownSection}>
      <header className={styles.breakdownHeading}>
        <div>
          <p className={styles.sectionEyebrow}>{eyebrow}</p>
          <h2>{title}</h2>
        </div>
        <p>{description}</p>
      </header>
      {children}
    </section>
  );
}

function CategoryTable({
  currentPath,
  currentSearch,
  rows,
  sort,
}: {
  currentPath: string;
  currentSearch: string;
  rows: CategoryRow[];
  sort: ReturnType<typeof reportCategorySort>;
}) {
  return (
    <table className={styles.table}>
      <caption className="visually-hidden">
        Доходы, расходы и прибыль по категориям
      </caption>
      <thead>
        <tr>
          {categoryColumns.map((column) => (
            <th
              aria-sort={
                sort.field === column.field
                  ? sort.direction === "asc"
                    ? "ascending"
                    : "descending"
                  : "none"
              }
              className={
                column.field === "name" ? undefined : styles.moneyColumn
              }
              key={column.field}
              scope="col"
            >
              <RouterButtonLink
                aria-label={`${column.label}. ${sortLabel(sort, column.field)}`}
                className={styles.sortControl}
                to={{
                  pathname: currentPath,
                  search: reportCategorySortSearch(currentSearch, column.field),
                }}
                tone="ghost"
              >
                {column.label}
                {sort.field === column.field
                  ? sort.direction === "asc"
                    ? " ↑"
                    : " ↓"
                  : ""}
              </RouterButtonLink>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={categoryIdentity(row)}>
            <td>{categoryIdentityView(row, currentSearch)}</td>
            <MoneyCells row={row} />
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CategoryCards({
  currentSearch,
  rows,
}: {
  currentSearch: string;
  rows: CategoryRow[];
}) {
  return (
    <ol className={styles.breakdownCards}>
      {rows.map((row) => (
        <li data-responsive-record key={categoryIdentity(row)}>
          <div className={styles.recordHeading}>
            {categoryIdentityView(row, currentSearch)}
          </div>
          <MoneyFacts row={row} />
        </li>
      ))}
    </ol>
  );
}

function PropertyTable({ rows }: { rows: PropertyRow[] }) {
  return (
    <table className={styles.table}>
      <caption className="visually-hidden">
        Доходы, расходы и прибыль по объектам
      </caption>
      <thead>
        <tr>
          <th scope="col">Объект</th>
          <th className={styles.moneyColumn} scope="col">
            Доходы
          </th>
          <th className={styles.moneyColumn} scope="col">
            Расходы
          </th>
          <th className={styles.moneyColumn} scope="col">
            Прибыль
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.propertyId}>
            <td>
              <strong>{row.name}</strong>
              {row.isActive ? null : <span> · архив</span>}
            </td>
            <MoneyCells row={row} />
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function PropertyCards({ rows }: { rows: PropertyRow[] }) {
  return (
    <ol className={styles.breakdownCards}>
      {rows.map((row) => (
        <li data-responsive-record key={row.propertyId}>
          <div className={styles.recordHeading}>
            <strong>{row.name}</strong>
            {row.isActive ? null : <span> · архив</span>}
          </div>
          <MoneyFacts row={row} />
        </li>
      ))}
    </ol>
  );
}

function MoneyCells({ row }: { row: CategoryRow | PropertyRow }) {
  return (
    <>
      <td className={styles.moneyColumn}>
        <ReportMoney
          amount={row.income}
          currency={row.currency}
          kind="income"
        />
      </td>
      <td className={styles.moneyColumn}>
        <ReportMoney
          amount={row.expense}
          currency={row.currency}
          kind="expense"
        />
      </td>
      <td className={styles.moneyColumn}>
        <ReportMoney
          amount={row.profit}
          currency={row.currency}
          kind="profit"
        />
      </td>
    </>
  );
}

function MoneyFacts({ row }: { row: CategoryRow | PropertyRow }) {
  return (
    <dl className={styles.moneyFacts}>
      <div>
        <dt>Доходы</dt>
        <dd>
          <ReportMoney
            amount={row.income}
            currency={row.currency}
            kind="income"
          />
        </dd>
      </div>
      <div>
        <dt>Расходы</dt>
        <dd>
          <ReportMoney
            amount={row.expense}
            currency={row.currency}
            kind="expense"
          />
        </dd>
      </div>
      <div>
        <dt>Прибыль</dt>
        <dd>
          <ReportMoney
            amount={row.profit}
            currency={row.currency}
            kind="profit"
          />
        </dd>
      </div>
    </dl>
  );
}

function ReportMoney({
  amount,
  currency,
  kind,
}: {
  amount: string;
  currency: string;
  kind: "income" | "expense" | "profit";
}) {
  return (
    <MoneyValue
      amount={formatMoneyAmount(amount, kind === "profit" ? null : kind)}
      currency={currency}
      tone={kind}
    />
  );
}

function categoryIdentityView(row: CategoryRow, currentSearch: string) {
  if (row.categoryId === null) return <strong>Без категории</strong>;
  return (
    <ButtonLink
      data-record-identity
      href={categoryDetailHref(row, currentSearch)}
      tone="ghost"
    >
      {row.name}
      {row.isActive ? "" : " · архив"}
    </ButtonLink>
  );
}

function categoryDetailHref(row: CategoryRow, currentSearch: string): string {
  const query = new URLSearchParams();
  const current = new URLSearchParams(currentSearch);
  for (const key of ["date_from", "date_to"] as const) {
    const value = current.get(key);
    if (value) query.set(key, value);
  }
  return `/categories/${row.categoryId}${query.size ? `?${query.toString()}` : ""}`;
}

function sortCategoryRows(
  rows: CategoryRow[],
  sort: ReturnType<typeof reportCategorySort>,
): CategoryRow[] {
  const direction = sort.direction === "asc" ? 1 : -1;
  return [...rows].sort((left, right) => {
    const primary =
      sort.field === "name"
        ? compareNames(left.name, right.name)
        : compareDecimalStrings(left[sort.field], right[sort.field]);
    if (primary !== 0) return primary * direction;
    const byName = compareNames(left.name, right.name);
    if (byName !== 0) return byName;
    return categoryIdentity(left).localeCompare(categoryIdentity(right));
  });
}

function compareNames(left: string, right: string): number {
  return left.localeCompare(right, "ru", { sensitivity: "base" });
}

function compareDecimalStrings(left: string, right: string): number {
  const [leftInteger, leftFraction = ""] = left.replace(/^\+/, "").split(".");
  const [rightInteger, rightFraction = ""] = right
    .replace(/^\+/, "")
    .split(".");
  const scale = Math.max(leftFraction.length, rightFraction.length);
  const leftScaled = BigInt(`${leftInteger}${leftFraction.padEnd(scale, "0")}`);
  const rightScaled = BigInt(
    `${rightInteger}${rightFraction.padEnd(scale, "0")}`,
  );
  return leftScaled < rightScaled ? -1 : leftScaled > rightScaled ? 1 : 0;
}

function categoryIdentity(row: CategoryRow): string {
  return row.categoryId ?? "system:uncategorized";
}

function sortLabel(
  sort: ReturnType<typeof reportCategorySort>,
  field: ReportCategorySortField,
): string {
  if (sort.field !== field) {
    return field === "name"
      ? "Сортировать по возрастанию"
      : "Сортировать по убыванию";
  }
  return sort.direction === "asc"
    ? "Сейчас по возрастанию; переключить на убывание"
    : "Сейчас по убыванию; переключить на возрастание";
}
